"""Numeric range scoring."""

from decimal import Decimal
from types import SimpleNamespace

from app.services.matching.numeric import numeric_score, range_fit
from tests.fakes import make_fund


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


def test_numeric_score_excludes_missing_metrics():
    company = SimpleNamespace(ebitda_estimate_usd_m=4, revenue_estimate_usd_m=None)
    fund = make_fund(ebitda_min_usd_m=2, ebitda_max_usd_m=30)
    score, detail = numeric_score(company, fund)
    assert score == 100.0  # ebitda in band; revenue unknown is excluded
    assert detail["assessed"] == ["ebitda"]


def test_numeric_score_none_when_nothing_assessable():
    company = SimpleNamespace(ebitda_estimate_usd_m=None, revenue_estimate_usd_m=None)
    fund = make_fund()
    score, detail = numeric_score(company, fund)
    assert score is None
    assert detail["assessed"] == []
