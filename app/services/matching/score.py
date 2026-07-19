"""Composite scoring with missingness-aware weight renormalisation."""

from __future__ import annotations

DEFAULT_WEIGHTS = {"thesis": 0.40, "numeric": 0.35, "strategy": 0.25}


def compose(
    *,
    thesis: float | None,
    numeric: float | None,
    strategy: float | None,
    weights: dict[str, float],
) -> tuple[float | None, dict[str, float]]:
    """Weighted composite over the dimensions that have a value.

    Missing dimensions are dropped and the remaining weights renormalised to sum
    to 1, so a company with no financials is never penalised for the gap. Returns
    (composite, effective_weights); composite is None when nothing is available.
    """
    dims = {
        "thesis": (thesis, weights.get("thesis", 0.0)),
        "numeric": (numeric, weights.get("numeric", 0.0)),
        "strategy": (strategy, weights.get("strategy", 0.0)),
    }
    present = {k: (v, w) for k, (v, w) in dims.items() if v is not None and w > 0}
    total_w = sum(w for _, w in present.values())
    if not present or total_w == 0:
        return None, {}
    effective = {k: w / total_w for k, (_, w) in present.items()}
    composite = sum(v * effective[k] for k, (v, _) in present.items())
    return round(composite, 2), {k: round(w, 4) for k, w in effective.items()}
