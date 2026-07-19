"""Composite scoring and the missingness renormalisation rule."""

from app.services.matching.score import DEFAULT_WEIGHTS, compose


def test_all_dimensions_present():
    composite, eff = compose(
        thesis=80, numeric=60, strategy=40, weights=DEFAULT_WEIGHTS
    )
    # 0.40*80 + 0.35*60 + 0.25*40 = 63.0
    assert composite == 63.0
    assert set(eff) == {"thesis", "numeric", "strategy"}


def test_missing_numeric_is_not_downscored():
    """A company with no financials must not be penalised for the gap."""
    composite, eff = compose(
        thesis=80, numeric=None, strategy=40, weights=DEFAULT_WEIGHTS
    )
    # Weights renormalise over {thesis, strategy}: 0.40/0.65 and 0.25/0.65.
    expected = 80 * (0.40 / 0.65) + 40 * (0.25 / 0.65)
    assert composite == round(expected, 2)
    assert "numeric" not in eff
    assert abs(sum(eff.values()) - 1.0) < 1e-9


def test_all_missing_returns_none():
    composite, eff = compose(
        thesis=None, numeric=None, strategy=None, weights=DEFAULT_WEIGHTS
    )
    assert composite is None
    assert eff == {}
