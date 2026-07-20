"""Hard filters — overlap and forgiving-missing behaviour."""

from types import SimpleNamespace

from app.services.matching.filters import (
    geo_ok,
    passes_hard_filters,
    sector_ok,
    size_ok,
)
from tests.fakes import make_fund


def _company(**kw) -> SimpleNamespace:
    base = dict(
        industry=None,
        sub_industry=None,
        location_country=None,
        location_region=None,
        ebitda_estimate_usd_m=None,
        revenue_estimate_usd_m=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_sector_overlap_true():
    company = _company(industry="Software")
    assert sector_ok(company, make_fund(sectors=["Software", "SaaS"])) is True


def test_sector_mismatch_false():
    company = _company(industry="Healthcare")
    assert sector_ok(company, make_fund(sectors=["Software"])) is False


def test_unknown_company_sector_is_no_constraint():
    company = _company(industry=None)
    assert sector_ok(company, make_fund(sectors=["Software"])) is None


def test_geo_wildcard_passes():
    company = _company(location_country="US")
    assert geo_ok(company, make_fund(geographies=["Global"])) is None


def test_geo_mismatch_false():
    company = _company(location_country="US")
    assert geo_ok(company, make_fund(geographies=["UK"])) is False


def test_passes_hard_filters_treats_none_as_pass():
    company = _company(industry="Software")  # geo unknown
    passed, matched_on = passes_hard_filters(company, make_fund(geographies=["UK"]))
    assert passed is True
    assert matched_on["sector"] is True
    assert matched_on["geo"] is None


def test_sector_mismatch_does_not_gate():
    # Sector is informational only — a mismatch must not exclude when geo is fine.
    company = _company(industry="Healthcare", location_country="UK")
    passed, matched_on = passes_hard_filters(company, make_fund(sectors=["Software"]))
    assert passed is True
    assert matched_on["sector"] is False


def test_hard_fail_on_geo_mismatch():
    company = _company(industry="Software", location_country="US")
    passed, _ = passes_hard_filters(company, make_fund(geographies=["UK"]))
    assert passed is False


def test_size_unknown_is_no_constraint():
    company = _company()  # no disclosed financials
    assert size_ok(company, make_fund(ebitda_min_usd_m=2, ebitda_max_usd_m=30)) is None


def test_soft_size_miss_does_not_gate():
    # 60 vs a 2-30 band is out of band but within 10x — scored, not gated.
    company = _company(location_country="UK", ebitda_estimate_usd_m=60)
    passed, matched_on = passes_hard_filters(company, make_fund())
    assert matched_on["size"] is True
    assert passed is True


def test_gross_size_mismatch_gates():
    # 5000 EBITDA vs a 2-30 band is >10x the ceiling — a clear disqualifier.
    company = _company(location_country="UK", ebitda_estimate_usd_m=5000)
    passed, matched_on = passes_hard_filters(company, make_fund())
    assert matched_on["size"] is False
    assert passed is False
