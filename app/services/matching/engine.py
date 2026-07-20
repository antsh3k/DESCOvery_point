"""Four-stage matching orchestration.

Stage 1  hard filters — geography and gross size mismatch exclude a fund
Stage 2  deterministic size fit (the quantitative half of Mandate fit)
Stage 3  LLM fit judge (passed candidates only) — scores three axes
         (mandate/strategy/value-creation) and decides `plausible_fit`, which
         excludes clear sector/deal mismatches so they never reach the shortlist
Stage 4  LLM re-rank + 'why this fits' rationale over the top N

Three pillars are scored and composed (see the rubric):
* **mandate** — size fit (deterministic, Stage 2) blended with the LLM's
  sector/thesis-centrality judgment (`mandate_fit`);
* **strategy** — the LLM's deal/playbook judgment (`strategy_fit`);
* **value_creation** — the LLM's "why this fund for this company" judgment.

The LLM is optional: without it, stages 3-4 are skipped and results are ranked
on the deterministic size fit alone (geo/size filtering still applies), so the
engine still returns a usable shortlist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from starlette.concurrency import run_in_threadpool

from app.schemas.company import CompanyProfile
from app.services.llm.base import LLMClient, LLMError
from app.services.matching.filters import passes_hard_filters
from app.services.matching.mandate import size_fit
from app.services.matching.score import compose

logger = logging.getLogger(__name__)

RERANK_TOP_N = 10


@dataclass(slots=True)
class MatchResult:
    fund_id: str
    passed_hard_filters: bool
    mandate_score: float | None = None
    strategy_score: float | None = None
    value_creation_score: float | None = None
    composite_score: float | None = None
    matched_on: dict = field(default_factory=dict)
    rationale: str | None = None
    rank: int | None = None
    weights_used: dict = field(default_factory=dict)
    # A fund the LLM judged a clear mismatch (or could not be scored at all) is
    # excluded from the ranked shortlist — it stays unranked so downstream
    # consumers drop it, just like a hard-filter failure.
    excluded: bool = False


def _mean_present(*values: float | None) -> float | None:
    """Mean of the non-None values, or None when all are missing."""
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


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
        size, size_detail = size_fit(company, fund)
        matched_on["size_detail"] = size_detail

        mandate_fit = strategy = value_creation = None
        rationale = None
        excluded = False
        if passed and llm is not None:
            mandate_fit, strategy, value_creation, rationale, plausible = await _judge(
                llm, company, fund
            )
            excluded = not plausible

        # Mandate fit = the deterministic size fit and the LLM's sector-centrality
        # judgment, averaged over whichever is present.
        mandate = _mean_present(size, mandate_fit)

        composite, effective = compose(
            mandate=mandate,
            strategy=strategy,
            value_creation=value_creation,
            weights=weights,
        )
        results.append(
            MatchResult(
                fund_id=str(fund.id),
                passed_hard_filters=passed,
                mandate_score=mandate,
                strategy_score=strategy,
                value_creation_score=value_creation,
                composite_score=composite,
                matched_on=matched_on,
                rationale=rationale,
                weights_used=effective,
                excluded=excluded,
            )
        )

    passed_results = [r for r in results if r.passed_hard_filters and not r.excluded]
    passed_results.sort(key=lambda r: _sort_key(r.composite_score), reverse=True)

    if llm is not None and passed_results:
        await _rerank(llm, company, funds, passed_results[:top_n])

    for i, r in enumerate(passed_results, start=1):
        if r.rank is None:  # rerank may have set ranks for the top N
            r.rank = i

    return results


async def _judge(
    llm: LLMClient, company: CompanyProfile, fund
) -> tuple[float | None, float | None, float | None, str | None, bool]:
    """Score a fund's fit. Returns (mandate_fit, strategy_fit, value_creation_fit,
    rationale, plausible_fit).

    Retries once on a transient model/parse error; if it still can't be scored,
    the fund is marked implausible so it drops out of the shortlist rather than
    appearing as an unscored, broken card.
    """
    public = fund_to_public(fund)
    for attempt in range(2):
        try:
            judgment = await run_in_threadpool(
                llm.judge_fit, company=company, fund=public
            )
            return (
                judgment.mandate_fit,
                judgment.strategy_fit,
                judgment.value_creation_fit,
                judgment.justification,
                judgment.plausible_fit,
            )
        except LLMError as exc:
            logger.warning(
                "fit judge failed for fund %s (attempt %d/2): %s",
                fund.id, attempt + 1, exc,
            )
    logger.warning("excluding fund %s: could not be scored", fund.id)
    return None, None, None, None, False


async def _rerank(
    llm: LLMClient, company: CompanyProfile, funds: list, top: list[MatchResult]
) -> None:
    by_id = {str(f.id): f for f in funds}
    candidates = [
        {
            **fund_to_public(by_id[r.fund_id]),
            "mandate_score": r.mandate_score,
            "strategy_score": r.strategy_score,
            "value_creation_score": r.value_creation_score,
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
