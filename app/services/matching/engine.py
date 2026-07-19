"""Four-stage matching orchestration.

Stage 1  hard filters (geo, sector)
Stage 2  soft numeric range scoring
Stage 3  LLM thesis/strategy judge (passed candidates only)
Stage 4  LLM re-rank + 'why this fits' rationale over the top N

The LLM is optional: without it, stages 3-4 are skipped and results are ranked
on the numeric score alone, so the engine still returns a usable shortlist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from starlette.concurrency import run_in_threadpool

from app.schemas.company import CompanyProfile
from app.services.llm.base import LLMClient, LLMError
from app.services.matching.filters import passes_hard_filters
from app.services.matching.numeric import numeric_score
from app.services.matching.score import compose

logger = logging.getLogger(__name__)

RERANK_TOP_N = 10


@dataclass(slots=True)
class MatchResult:
    fund_id: str
    passed_hard_filters: bool
    numeric_score: float | None = None
    thesis_score: float | None = None
    strategy_score: float | None = None
    composite_score: float | None = None
    matched_on: dict = field(default_factory=dict)
    rationale: str | None = None
    rank: int | None = None
    weights_used: dict = field(default_factory=dict)


async def run_match(
    company: CompanyProfile,
    funds: list,
    *,
    weights: dict[str, float],
    llm: LLMClient | None = None,
    top_n: int = RERANK_TOP_N,
) -> list[MatchResult]:
    results: list[MatchResult] = []

    for fund in funds:
        passed, matched_on = passes_hard_filters(company, fund)
        num, num_detail = numeric_score(company, fund)
        matched_on["numeric"] = num_detail

        thesis = strategy = None
        rationale = None
        if passed and llm is not None:
            thesis, strategy, rationale = await _judge(llm, company, fund)

        composite, effective = compose(
            thesis=thesis, numeric=num, strategy=strategy, weights=weights
        )
        results.append(
            MatchResult(
                fund_id=str(fund.id),
                passed_hard_filters=passed,
                numeric_score=num,
                thesis_score=thesis,
                strategy_score=strategy,
                composite_score=composite,
                matched_on=matched_on,
                rationale=rationale,
                weights_used=effective,
            )
        )

    passed_results = [r for r in results if r.passed_hard_filters]
    passed_results.sort(key=lambda r: _sort_key(r.composite_score), reverse=True)

    if llm is not None and passed_results:
        await _rerank(llm, company, funds, passed_results[:top_n])

    for i, r in enumerate(passed_results, start=1):
        if r.rank is None:  # rerank may have set ranks for the top N
            r.rank = i

    return results


async def _judge(
    llm: LLMClient, company: CompanyProfile, fund
) -> tuple[float | None, float | None, str | None]:
    try:
        judgment = await run_in_threadpool(
            llm.judge_thesis, company=company, fund=fund_to_public(fund)
        )
        return judgment.thesis_score, judgment.strategy_score, judgment.justification
    except LLMError as exc:
        logger.warning("thesis judge failed for fund %s: %s", fund.id, exc)
        return None, None, None


async def _rerank(
    llm: LLMClient, company: CompanyProfile, funds: list, top: list[MatchResult]
) -> None:
    by_id = {str(f.id): f for f in funds}
    candidates = [
        {
            **fund_to_public(by_id[r.fund_id]),
            "numeric_score": r.numeric_score,
            "thesis_score": r.thesis_score,
            "strategy_score": r.strategy_score,
            "composite_score": r.composite_score,
        }
        for r in top
    ]
    try:
        result = await run_in_threadpool(
            llm.rerank, company=company, candidates=candidates
        )
    except LLMError as exc:
        logger.warning("rerank failed: %s", exc)
        return

    by_result = {r.fund_id: r for r in top}
    for item in sorted(result.items, key=lambda i: i.rank):
        r = by_result.get(item.fund_id)
        if r is not None:
            r.rank = item.rank
            r.rationale = item.rationale or r.rationale


def fund_to_public(fund) -> dict:
    """A JSON-safe view of a fund's mandate for the LLM."""
    return {
        "fund_id": str(fund.id),
        "name": fund.name,
        "firm": fund.firm,
        "sectors": fund.sectors,
        "geographies": fund.geographies,
        "check_size_min_usd_m": _num(fund.check_size_min_usd_m),
        "check_size_max_usd_m": _num(fund.check_size_max_usd_m),
        "ebitda_min_usd_m": _num(fund.ebitda_min_usd_m),
        "ebitda_max_usd_m": _num(fund.ebitda_max_usd_m),
        "revenue_min_usd_m": _num(fund.revenue_min_usd_m),
        "revenue_max_usd_m": _num(fund.revenue_max_usd_m),
        "stage": fund.stage,
        "thesis": fund.thesis,
    }


def _num(value) -> float | None:
    return float(value) if value is not None else None


def _sort_key(composite: float | None) -> float:
    return composite if composite is not None else -1.0
