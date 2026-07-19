"""Stage 1 — hard filters on geography and sector.

Filters are deliberately *forgiving*: an unknown company attribute or an
unconstrained fund is treated as "no constraint" (pass), never as a failure —
we don't want thin SME data to wipe out the whole shortlist.
"""

from __future__ import annotations

_GEO_WILDCARDS = {"global", "any", "worldwide", "international"}


def _tokens(*values: object) -> list[str]:
    out: list[str] = []
    for v in values:
        if isinstance(v, str) and v.strip():
            out.append(v.strip().lower())
        elif isinstance(v, (list, tuple)):
            out.extend(t.strip().lower() for t in v if isinstance(t, str) and t.strip())
    return out


def _overlap(company_tokens: list[str], fund_tokens: list[str]) -> bool:
    for c in company_tokens:
        for f in fund_tokens:
            if c == f or c in f or f in c:
                return True
    return False


def sector_ok(company, fund) -> bool | None:
    """True/False on sector overlap; None when unconstrained/unknown (=> pass)."""
    fund_sectors = _tokens(fund.sectors)
    company_sectors = _tokens(company.industry, company.sub_industry)
    if not fund_sectors or not company_sectors:
        return None
    return _overlap(company_sectors, fund_sectors)


def geo_ok(company, fund) -> bool | None:
    """True/False on geography overlap; None when unconstrained/unknown (=> pass)."""
    fund_geos = _tokens(fund.geographies)
    if not fund_geos or any(w in fund_geos for w in _GEO_WILDCARDS):
        return None
    company_geos = _tokens(company.location_country, company.location_region)
    if not company_geos:
        return None
    return _overlap(company_geos, fund_geos)


def passes_hard_filters(company, fund) -> tuple[bool, dict]:
    """Return (passed, matched_on). None sub-results count as pass."""
    s = sector_ok(company, fund)
    g = geo_ok(company, fund)
    passed = (s is not False) and (g is not False)
    return passed, {"sector": s, "geo": g}
