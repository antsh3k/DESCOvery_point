"""Deterministic size fit — the quantitative half of Mandate fit."""

from decimal import Decimal
from types import SimpleNamespace

from app.services.matching.mandate import range_fit, size_fit
from tests.fakes import make_fund


def _company(**kw) -> SimpleNamespace:
    base = dict(
        ebitda_estimate_usd_m=None, revenue_estimate_usd_m=None, size_employees=None
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_range_fit_accepts_decimal_bounds():
    # ORM mandates arrive as Decimal; a float company value must still work.
    assert range_fit(4.0, Decimal("8"), Decimal("20")) == 50.0


def test_range_fit_within_band():
    assert range_fit(10, 5, 20) == 100.0


def test_range_fit_below_band_decays():
    # value 4, lo 8 → 100*(1 - (8-4)/8) = 50
    assert range_fit(4, 8, 20) == 50.0


def test_range_fit_missing_value_or_band_is_none():
    assert range_fit(None, 5, 20) is None
    assert range_fit(10, None, None) is None


def test_size_fit_scores_ebitda_and_implied_check_size():
    # EBITDA in band; revenue unknown is excluded; check size assessed via the
    # EBITDA-implied enterprise value (4 * 8 = 32, inside the 10-100 band).
    company = _company(ebitda_estimate_usd_m=4)
    fund = make_fund(ebitda_min_usd_m=2, ebitda_max_usd_m=30)
    score, detail = size_fit(company, fund)
    assert score == 100.0
    assert detail["assessed"] == ["check_size", "ebitda"]
    assert detail["imputed"] == []  # EV from disclosed EBITDA is not imputed


def test_size_fit_recovers_signal_from_headcount_only():
    # Only headcount known → revenue and EV are imputed, but a size signal survives.
    company = _company(size_employees=100)
    fund = make_fund()
    score, detail = size_fit(company, fund)
    assert score == 100.0
    assert detail["assessed"] == ["check_size", "revenue"]
    assert sorted(detail["imputed"]) == ["check_size", "revenue"]


def test_size_fit_none_when_nothing_assessable():
    company = _company()
    fund = make_fund(
        ebitda_min_usd_m=None,
        ebitda_max_usd_m=None,
        revenue_min_usd_m=None,
        revenue_max_usd_m=None,
        check_size_min_usd_m=None,
        check_size_max_usd_m=None,
    )
    score, detail = size_fit(company, fund)
    assert score is None
    assert detail["assessed"] == []


def test_size_fit_falls_back_to_aum_implied_check_size_band():
    # No explicit check-size band, but AUM is disclosed (the common case for
    # EDGAR-sourced funds): $1,000m AUM implies a $50-150m check-size band
    # (5-15%), and a $60m-implied EV (EBITDA 7.5 * 8) sits inside it.
    company = _company(ebitda_estimate_usd_m=7.5)
    fund = make_fund(
        ebitda_min_usd_m=None, ebitda_max_usd_m=None,
        revenue_min_usd_m=None, revenue_max_usd_m=None,
        check_size_min_usd_m=None, check_size_max_usd_m=None,
        gross_asset_value_usd=1_000_000_000,  # raw USD, i.e. $1,000m
    )
    score, detail = size_fit(company, fund)
    assert score == 100.0
    assert detail["assessed"] == ["check_size"]
    assert detail["imputed"] == ["check_size"]  # implied from AUM, flagged for the UI


def test_size_fit_ignores_aum_when_fund_has_its_own_check_size_band():
    # An implied AUM band must never override a fund's own disclosed band.
    company = _company(ebitda_estimate_usd_m=4)
    fund = make_fund(
        ebitda_min_usd_m=None, ebitda_max_usd_m=None,
        revenue_min_usd_m=None, revenue_max_usd_m=None,
        check_size_min_usd_m=10, check_size_max_usd_m=20,
        gross_asset_value_usd=1_000_000_000,  # would imply $50-150m if used
    )
    score, detail = size_fit(company, fund)
    # EV = 4 * 8 = 32, outside the fund's real 10-20 band, not the AUM-implied one.
    assert detail["imputed"] == []
    assert score is not None and score < 100.0
