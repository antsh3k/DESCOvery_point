"""Stage 2 — soft numeric scoring on mandate ranges (EBITDA, revenue).

Missingness rule: a company metric we don't have is *excluded* from the mean,
never scored as zero. If no metric is available the numeric score is ``None``
and its weight is redistributed downstream (see :mod:`.score`).
"""

from __future__ import annotations


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


def numeric_score(company, fund) -> tuple[float | None, dict]:
    """Mean of available range fits; None when no metric can be assessed."""
    metrics = {
        "ebitda": range_fit(
            company.ebitda_estimate_usd_m,
            fund.ebitda_min_usd_m,
            fund.ebitda_max_usd_m,
        ),
        "revenue": range_fit(
            company.revenue_estimate_usd_m,
            fund.revenue_min_usd_m,
            fund.revenue_max_usd_m,
        ),
    }
    available = {k: v for k, v in metrics.items() if v is not None}
    if not available:
        return None, {"metrics": metrics, "assessed": []}
    score = sum(available.values()) / len(available)
    return score, {"metrics": metrics, "assessed": sorted(available)}
