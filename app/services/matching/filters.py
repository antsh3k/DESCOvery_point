"""Stage 1 — hard filters on geography and gross size mismatch.

Filters are deliberately *forgiving*: an unknown company attribute or an
unconstrained fund is treated as "no constraint" (pass), never as a failure —
we don't want thin SME data to wipe out the whole shortlist. Two things gate:

* a clear **geography** mismatch, and
* a **gross size** mismatch — a *disclosed* company metric more than an order of
  magnitude outside the fund's published band, on *every* axis we can assess.

Sector and transactability (does ownership allow this fund's deal type?) are
judged semantically downstream by the LLM rather than by brittle string matching
here: sector taxonomies and free-text stage/ownership rarely align on a
substring, so gating on them would wrongly wipe out otherwise-plausible funds.
"""

from __future__ import annotations

_GEO_WILDCARDS = {"global", "any", "worldwide", "international"}

# A disclosed metric this many multiples beyond a band edge is a gross mismatch.
# Deliberately large so only unmistakable misses gate; soft misses are scored.
_GROSS_SIZE_FACTOR = 10.0


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


def _grossly_out(value, lo, hi) -> bool | None:
    """True if ``value`` is > _GROSS_SIZE_FACTOR beyond the band; None if not assessable."""
    if value is None or (lo is None and hi is None):
        return None
    value = float(value)
    lo = float(lo) if lo is not None else None
    hi = float(hi) if hi is not None else None
    if lo is not None and lo > 0 and value < lo / _GROSS_SIZE_FACTOR:
        return True
    if hi is not None and hi > 0 and value > hi * _GROSS_SIZE_FACTOR:
        return True
    return False


def size_ok(company, fund) -> bool | None:
    """False only when *every* disclosed size metric is grossly outside the band.

    Uses disclosed EBITDA/revenue only — never the coarse implied enterprise
    value used for soft scoring — so exclusion always rests on a hard number vs a
    hard band. Unanimity across assessable axes keeps one noisy metric from
    gating. None when nothing is assessable (=> pass).
    """
    checks = [
        _grossly_out(
            getattr(company, "ebitda_estimate_usd_m", None),
            fund.ebitda_min_usd_m,
            fund.ebitda_max_usd_m,
        ),
        _grossly_out(
            getattr(company, "revenue_estimate_usd_m", None),
            fund.revenue_min_usd_m,
            fund.revenue_max_usd_m,
        ),
    ]
    assessed = [c for c in checks if c is not None]
    if not assessed:
        return None
    return not all(assessed)


def passes_hard_filters(company, fund) -> tuple[bool, dict]:
    """Return (passed, matched_on).

    Geography and gross size are hard gates — a clear miss on either excludes a
    fund. Sector overlap is *informational only* (surfaced in ``matched_on`` for
    the UI and the LLM judge): sector taxonomies rarely align on a substring
    (``"Apparel & Fashion"`` vs a fund's ``"Consumer"``), so letting sector fail
    the gate would wrongly wipe out otherwise-plausible funds. Whether the thesis
    and deal type actually fit is left to Stage 3's LLM judge.
    """
    s = sector_ok(company, fund)
    g = geo_ok(company, fund)
    size = size_ok(company, fund)
    passed = g is not False and size is not False
    return passed, {"sector": s, "geo": g, "size": size}
