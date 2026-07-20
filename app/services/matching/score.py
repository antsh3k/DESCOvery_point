"""Composite scoring with missingness-aware weight renormalisation.

Three pillars are combined here (see the rubric): **mandate** fit (is the target
in the fund's box — size + sector centrality), **strategy** fit (is this the
fund's kind of deal), and **value_creation** fit (is this fund especially good
*for* this company). A fourth pillar — executability/timing — is defined in the
rubric but not yet scored (no fund vintage/dry-powder data), so it is omitted.
"""

from __future__ import annotations

DEFAULT_WEIGHTS = {"mandate": 0.40, "strategy": 0.35, "value_creation": 0.25}


def compose(
    *,
    mandate: float | None,
    strategy: float | None,
    value_creation: float | None,
    weights: dict[str, float],
) -> tuple[float | None, dict[str, float]]:
    """Weighted composite over the dimensions that have a value.

    Missing dimensions are dropped and the remaining weights renormalised to sum
    to 1, so a company with no financials (or a fund with no assessable strategy
    signal) is never penalised for the gap. Returns (composite, effective_weights);
    composite is None when nothing is available.
    """
    dims = {
        "mandate": (mandate, weights.get("mandate", 0.0)),
        "strategy": (strategy, weights.get("strategy", 0.0)),
        "value_creation": (value_creation, weights.get("value_creation", 0.0)),
    }
    present = {k: (v, w) for k, (v, w) in dims.items() if v is not None and w > 0}
    total_w = sum(w for _, w in present.values())
    if not present or total_w == 0:
        return None, {}
    effective = {k: w / total_w for k, (_, w) in present.items()}
    composite = sum(v * effective[k] for k, (v, _) in present.items())
    return round(composite, 2), {k: round(w, 4) for k, w in effective.items()}
