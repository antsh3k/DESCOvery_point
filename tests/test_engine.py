"""End-to-end matching engine behaviour (LLM faked)."""

import threading
import time

from app.schemas.company import CompanyProfile
from app.schemas.match import FitJudgment
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
        check_size_min_usd_m=None,
        check_size_max_usd_m=None,
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

    # Fund with no size bands still scores — mandate falls back to the LLM's
    # sector-centrality judgment, so the gap never penalises it.
    nf = by_id[str(no_financials.id)]
    assert nf.mandate_score == 90.0  # size missing → mandate = LLM mandate_fit
    assert nf.composite_score is not None


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


async def test_run_match_without_llm_is_size_only():
    good = make_fund(name="Good", sectors=["Software"], geographies=["UK"])
    results = await run_match(_company(), [good], weights=DEFAULT_WEIGHTS, llm=None)
    r = results[0]
    assert r.strategy_score is None
    assert r.value_creation_score is None
    assert r.mandate_score == 100.0  # deterministic size fit only
    assert r.composite_score == 100.0
    assert r.rank == 1


async def test_llm_judge_top_k_caps_by_deterministic_size_fit():
    # Three funds pass hard filters with distinct size fits (via distinct
    # check-size bands); capping at 2 must judge the two best-sized ones and
    # exclude the worst-sized one for cost, without ever calling the LLM on it.
    best = make_fund(
        name="Best size", sectors=["Software"], geographies=["UK"],
        check_size_min_usd_m=1, check_size_max_usd_m=200,  # implied EV (32) comfortably inside
    )
    middling = make_fund(
        name="Middling size", sectors=["Software"], geographies=["UK"],
        check_size_min_usd_m=25, check_size_max_usd_m=40,  # implied EV (32) inside, tight band
    )
    worst = make_fund(
        name="Worst size", sectors=["Software"], geographies=["UK"],
        check_size_min_usd_m=500, check_size_max_usd_m=600,  # implied EV (32) far below band
    )

    results = await run_match(
        _company(), [best, middling, worst],
        weights=DEFAULT_WEIGHTS, llm=FakeLLM(), llm_judge_top_k=2,
    )
    by_id = {r.fund_id: r for r in results}

    judged = [by_id[str(f.id)] for f in (best, middling)]
    for r in judged:
        assert r.strategy_score is not None  # reached the LLM judge

    cut = by_id[str(worst.id)]
    assert cut.strategy_score is None  # never reached the LLM judge
    assert cut.excluded is True  # cut for cost, dropped from the shortlist
    assert cut.rank is None


async def test_llm_judge_calls_run_concurrently_not_sequentially():
    funds = [
        make_fund(name=f"Fund {i}", sectors=["Software"], geographies=["UK"])
        for i in range(5)
    ]

    class SlowConcurrencyTrackingLLM(FakeLLM):
        def __init__(self):
            self.lock = threading.Lock()
            self.in_flight = 0
            self.max_in_flight = 0

        def judge_fit(self, *, company, fund):
            with self.lock:
                self.in_flight += 1
                self.max_in_flight = max(self.max_in_flight, self.in_flight)
            time.sleep(0.05)
            with self.lock:
                self.in_flight -= 1
            return FitJudgment(
                mandate_fit=90.0, strategy_fit=80.0, value_creation_fit=70.0,
                justification="ok", plausible_fit=True,
            )

    llm = SlowConcurrencyTrackingLLM()
    await run_match(_company(), funds, weights=DEFAULT_WEIGHTS, llm=llm)

    # A sequential for-loop could never have more than 1 in flight at once.
    assert llm.max_in_flight > 1


async def test_on_progress_reports_zero_then_each_completion_up_to_total():
    funds = [
        make_fund(name=f"Fund {i}", sectors=["Software"], geographies=["UK"])
        for i in range(3)
    ]
    events: list[tuple[int, int]] = []

    await run_match(
        _company(), funds, weights=DEFAULT_WEIGHTS, llm=FakeLLM(),
        on_progress=lambda done, total: events.append((done, total)),
    )

    # An initial (0, total) so the UI has the total before any completion,
    # then exactly one event per judged fund (concurrent completion order
    # isn't guaranteed, so check the set of counts reached, not the sequence).
    assert events[0] == (0, 3)
    assert len(events) == 4  # the initial 0 + one per fund
    assert {done for done, _ in events} == {0, 1, 2, 3}
    assert all(total == 3 for _, total in events)


async def test_on_progress_not_called_without_llm():
    good = make_fund(name="Good", sectors=["Software"], geographies=["UK"])
    events: list[tuple[int, int]] = []

    await run_match(
        _company(), [good], weights=DEFAULT_WEIGHTS, llm=None,
        on_progress=lambda done, total: events.append((done, total)),
    )

    assert events == []
