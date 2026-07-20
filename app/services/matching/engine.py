"""Four-stage matching orchestration.

Stage 1  hard filters — geography and gross size mismatch exclude a fund
Stage 2  deterministic size fit (the quantitative half of Mandate fit) —
         cheap, no LLM call; computed for every fund that passes Stage 1
Stage 3  LLM fit judge, on the top ``llm_judge_top_k`` Stage-1 survivors
         ranked by Stage 2's score — scores three axes (mandate/strategy/
         value-creation) and decides `plausible_fit`, which excludes clear
         sector/deal mismatches so they never reach the shortlist
Stage 4  LLM re-rank + 'why this fits' rationale over the top N

Three pillars are scored and composed (see the rubric):
* **mandate** — size fit (deterministic, Stage 2) blended with the LLM's
  sector/thesis-centrality judgment (`mandate_fit`);
* **strategy** — the LLM's deal/playbook judgment (`strategy_fit`);
* **value_creation** — the LLM's "why this fund for this company" judgment.

Stage 1 alone doesn't bound cost: it's deliberately lenient (never excludes on
an unknown attribute), so at a large fund universe most candidates survive it.
Stage 3 is the expensive step — one LLM call per fund — so Stage 1 survivors
are ranked by two free signals before the cap: Stage 2's deterministic size
fit, and (when a ``company_embedding`` is supplied) cosine similarity between
that embedding and the fund's stored thesis embedding — a semantic read on
whether the fund's actual thesis relates to this business, which sector
substring-matching can't reliably answer (see :mod:`.filters`). The judge
calls for the capped set run concurrently rather than one at a time. A fund
cut by the cap is excluded from the shortlist (cost, not merit) rather than
shown unscored.

The LLM is optional: without it, stages 3-4 are skipped and results are ranked
on the deterministic size fit alone (geo/size filtering still applies), so the
engine still returns a usable shortlist.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from starlette.concurrency import run_in_threadpool

from app.schemas.company import CompanyProfile
from app.services.llm.base import LLMClient, LLMError
from app.services.matching.embeddings import semantic_fit
from app.services.matching.filters import passes_hard_filters
from app.services.matching.mandate import size_fit
from app.services.matching.score import compose

logger = logging.getLogger(__name__)

RERANK_TOP_N = 10
# How many Stage-1 survivors ever reach the LLM judge, ranked by Stage 2's
# free deterministic score. Bounds cost/latency at a large fund universe;
# irrelevant at the small ones this was originally sized for.
LLM_JUDGE_TOP_K = 100
_JUDGE_CONCURRENCY = 8


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
    llm_judge_top_k: int = LLM_JUDGE_TOP_K,
    company_embedding: list[float] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[MatchResult]:
    results: list[MatchResult] = []
    fund_by_id: dict[str, object] = {}
    # (result, pre_filter_rank) — the rank is a Stage-3-selection aid only,
    # never shown to the user or folded into mandate_score.
    judge_candidates: list[tuple[MatchResult, float | None]] = []

    # Stages 1-2: hard filter + free deterministic size fit, for every fund.
    for fund in funds:
        passed, matched_on = passes_hard_filters(company, fund)
        size, size_detail = size_fit(company, fund)
        semantic = semantic_fit(company_embedding, fund)
        matched_on["size_detail"] = size_detail
        matched_on["semantic_score"] = semantic

        result = MatchResult(
            fund_id=str(fund.id),
            passed_hard_filters=passed,
            mandate_score=size,
            matched_on=matched_on,
        )
        results.append(result)
        fund_by_id[result.fund_id] = fund
        if passed and llm is not None:
            judge_candidates.append((result, _mean_present(size, semantic)))

    # Stage 3: the expensive step. Rank Stage-1 survivors by the free size fit
    # and semantic similarity (whichever are present) and only send the top
    # `llm_judge_top_k` to the LLM, concurrently; the rest are cut for cost,
    # not merit, and excluded from the shortlist.
    if judge_candidates:
        judge_candidates.sort(
            key=lambda rc: rc[1] if rc[1] is not None else -1.0,
            reverse=True,
        )
        to_judge = [r for r, _ in judge_candidates[:llm_judge_top_k]]
        for r, _ in judge_candidates[llm_judge_top_k:]:
            r.excluded = True

        sem = asyncio.Semaphore(_JUDGE_CONCURRENCY)
        total = len(to_judge)
        judged = 0
        if on_progress:
            on_progress(0, total)

        async def _judge_one(result: MatchResult) -> None:
            nonlocal judged
            async with sem:
                fund = fund_by_id[result.fund_id]
                mandate_fit, strategy, value_creation, rationale, plausible = await _judge(
                    llm, company, fund
                )
                # Mandate fit = the deterministic size fit and the LLM's
                # sector-centrality judgment, averaged over whichever is present.
                result.mandate_score = _mean_present(result.mandate_score, mandate_fit)
                result.strategy_score = strategy
                result.value_creation_score = value_creation
                result.rationale = rationale
                result.excluded = not plausible
            # Outside the semaphore block: a plain int increment has no `await`
            # in between, so it's safe without a lock on asyncio's single thread.
            judged += 1
            if on_progress:
                on_progress(judged, total)

        await asyncio.gather(*(_judge_one(r) for r in to_judge))

    for result in results:
        composite, effective = compose(
            mandate=result.mandate_score,
            strategy=result.strategy_score,
            value_creation=result.value_creation_score,
            weights=weights,
        )
        result.composite_score = composite
        result.weights_used = effective

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
