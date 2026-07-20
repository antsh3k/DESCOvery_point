"""Deterministic size fit — the company's scale vs the fund's mandate bands.

This is the *quantitative* half of the Mandate-fit pillar (the semantic half —
sector/thesis centrality — is judged by the LLM and blended in the engine).

The company's size is compared against whatever bands the fund actually
publishes — EBITDA, revenue, and check size (enterprise value) — and the mean of
the available fits is returned. Two recoveries keep a size signal alive where a
naive EBITDA-only comparison would give up:

* Many funds publish *only* a check-size band. We compare it against an implied
  enterprise value derived from the company's EBITDA (or revenue as a fallback).
* Many SMEs disclose *only* headcount. We impute a rough revenue from it so the
  company still lands somewhere on the fund's size axes.

Both recoveries use coarse, sector-agnostic multiples — they turn "no signal"
into "approximate signal", not a precise valuation, and are flagged in the
detail so the UI can mark them as inferred.

Missingness rule (unchanged): an axis we cannot assess is excluded from the
mean, never scored as zero. If nothing is assessable the score is ``None`` and
its weight is redistributed downstream (see :mod:`.score`).
"""

from __future__ import annotations

# Coarse conversions used only to recover a size signal when a direct
# comparison isn't possible. Deliberately rough and sector-agnostic.
EV_EBITDA_MULTIPLE = 8.0  # implied enterprise value per unit of EBITDA
EV_REVENUE_MULTIPLE = 1.5  # fallback EV per unit of revenue when EBITDA unknown
REVENUE_PER_EMPLOYEE_USD_M = 0.2  # ~$200k revenue/head, last-resort headcount proxy


def range_fit(value: float | None, lo: float | None, hi: float | None) -> float | None:
    """Score a value against a [lo, hi] band in 0-100, or None if not assessable.

    - Inside the band (or the open side of a one-sided band) → 100.
    - Outside → linear decay over one bound-width, floored at 0.

    Inputs are coerced to float so ORM ``Decimal`` mandates mix cleanly with
    float company estimates.
    """
    if value is None or (lo is None and hi is None):
        return None
    value = float(value)
    lo = float(lo) if lo is not None else None
    hi = float(hi) if hi is not None else None
    if lo is not None and value < lo:
        scale = lo if lo > 0 else 1.0
        return max(0.0, 100.0 * (1 - (lo - value) / scale))
    if hi is not None and value > hi:
        scale = hi if hi > 0 else 1.0
        return max(0.0, 100.0 * (1 - (value - hi) / scale))
    return 100.0


def _company_revenue(company) -> tuple[float | None, bool]:
    """Best available revenue in USD m and whether it was imputed from headcount."""
    rev = getattr(company, "revenue_estimate_usd_m", None)
    if rev is not None:
        return float(rev), False
    employees = getattr(company, "size_employees", None)
    if employees:
        return float(employees) * REVENUE_PER_EMPLOYEE_USD_M, True
    return None, False


def _company_ev(company) -> tuple[float | None, bool]:
    """Implied enterprise value in USD m and whether it rests on an imputed input.

    Prefers EBITDA (the cleanest EV proxy), falls back to revenue, and finally to
    a headcount-derived revenue. The boolean is True whenever the estimate leans
    on anything softer than disclosed EBITDA.
    """
    ebitda = getattr(company, "ebitda_estimate_usd_m", None)
    if ebitda is not None:
        return float(ebitda) * EV_EBITDA_MULTIPLE, False
    rev, rev_imputed = _company_revenue(company)
    if rev is not None:
        return rev * EV_REVENUE_MULTIPLE, True
    return None, False


def size_fit(company, fund) -> tuple[float | None, dict]:
    """Mean of available size fits (EBITDA, revenue, check size); None if none assessable."""
    revenue, revenue_imputed = _company_revenue(company)
    ev, ev_imputed = _company_ev(company)

    metrics = {
        "ebitda": range_fit(
            getattr(company, "ebitda_estimate_usd_m", None),
            fund.ebitda_min_usd_m,
            fund.ebitda_max_usd_m,
        ),
        "revenue": range_fit(revenue, fund.revenue_min_usd_m, fund.revenue_max_usd_m),
        "check_size": range_fit(
            ev, fund.check_size_min_usd_m, fund.check_size_max_usd_m
        ),
    }
    available = {k: v for k, v in metrics.items() if v is not None}
    if not available:
        return None, {"metrics": metrics, "assessed": [], "imputed": []}

    imputed = []
    if "revenue" in available and revenue_imputed:
        imputed.append("revenue")
    if "check_size" in available and ev_imputed:
        imputed.append("check_size")

    score = sum(available.values()) / len(available)
    return score, {
        "metrics": metrics,
        "assessed": sorted(available),
        "imputed": imputed,
    }
