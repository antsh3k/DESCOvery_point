"""Hard filters — overlap and forgiving-missing behaviour."""

from types import SimpleNamespace

from app.services.matching.filters import geo_ok, passes_hard_filters, sector_ok
from tests.fakes import make_fund


def _company(**kw) -> SimpleNamespace:
    base = dict(
        industry=None, sub_industry=None, location_country=None, location_region=None
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


def test_hard_fail_on_sector_mismatch():
    company = _company(industry="Healthcare", location_country="UK")
    passed, _ = passes_hard_filters(company, make_fund(sectors=["Software"]))
    assert passed is False
