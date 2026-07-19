"""End-to-end matching engine behaviour (LLM faked)."""

from app.schemas.company import CompanyProfile
from app.services.matching import run_match
from app.services.matching.score import DEFAULT_WEIGHTS
from tests.fakes import FakeLLM, make_fund


def _company() -> CompanyProfile:
    return CompanyProfile(
        industry="Software",
        location_country="UK",
        revenue_estimate_usd_m=20,
        ebitda_estimate_usd_m=4,
        summary="B2B SaaS for mid-market.",
    )


async def test_run_match_filters_scores_and_reranks():
    good = make_fund(name="Good SW", sectors=["Software"], geographies=["UK"])
    no_financials = make_fund(
        name="Other SW",
        sectors=["Software"],
        geographies=["Global"],
        ebitda_min_usd_m=None,
        ebitda_max_usd_m=None,
        revenue_min_usd_m=None,
        revenue_max_usd_m=None,
    )
    mismatch = make_fund(name="HC US", sectors=["Healthcare"], geographies=["US"])

    results = await run_match(
        _company(), [good, no_financials, mismatch], weights=DEFAULT_WEIGHTS, llm=FakeLLM()
    )
    by_id = {r.fund_id: r for r in results}

    # Sector + geo mismatch is filtered out.
    assert by_id[str(mismatch.id)].passed_hard_filters is False

    passed = [r for r in results if r.passed_hard_filters]
    assert {r.rank for r in passed} == {1, 2}
    for r in passed:
        assert r.composite_score is not None
        assert r.rationale.startswith("Why")  # supplied by rerank

    # Fund with no financials still scores (thesis+strategy only) — not penalised.
    assert by_id[str(no_financials.id)].numeric_score is None
    assert by_id[str(no_financials.id)].composite_score is not None


async def test_clear_sector_mismatch_is_excluded_even_when_geo_passes():
    # Healthcare-only fund in the company's geography: it clears the geo hard
    # filter but the LLM judge flags it a clear sector mismatch, so it must be
    # excluded from the ranked shortlist (not merely ranked last).
    software = make_fund(name="SW UK", sectors=["Software"], geographies=["UK"])
    healthcare = make_fund(name="HC UK", sectors=["Healthcare"], geographies=["UK"])

    results = await run_match(
        _company(), [software, healthcare], weights=DEFAULT_WEIGHTS, llm=FakeLLM()
    )
    by_id = {r.fund_id: r for r in results}

    hc = by_id[str(healthcare.id)]
    assert hc.passed_hard_filters is True  # geo was fine
    assert hc.excluded is True
    assert hc.rank is None  # dropped from the shortlist

    sw = by_id[str(software.id)]
    assert sw.excluded is False
    assert sw.rank == 1


async def test_run_match_without_llm_is_numeric_only():
    good = make_fund(name="Good", sectors=["Software"], geographies=["UK"])
    results = await run_match(_company(), [good], weights=DEFAULT_WEIGHTS, llm=None)
    r = results[0]
    assert r.thesis_score is None
    assert r.numeric_score == 100.0
    assert r.composite_score == 100.0
    assert r.rank == 1
