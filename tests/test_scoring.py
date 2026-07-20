"""Composite scoring and the missingness renormalisation rule."""

from app.services.matching.score import DEFAULT_WEIGHTS, compose


def test_all_dimensions_present():
    composite, eff = compose(
        mandate=80, strategy=60, value_creation=40, weights=DEFAULT_WEIGHTS
    )
    # 0.40*80 + 0.35*60 + 0.25*40 = 63.0
    assert composite == 63.0
    assert set(eff) == {"mandate", "strategy", "value_creation"}


def test_missing_dimension_is_not_downscored():
    """A fund with no assessable strategy signal must not be penalised for the gap."""
    composite, eff = compose(
        mandate=80, strategy=None, value_creation=40, weights=DEFAULT_WEIGHTS
    )
    # Weights renormalise over {mandate, value_creation}: 0.40/0.65 and 0.25/0.65.
    expected = 80 * (0.40 / 0.65) + 40 * (0.25 / 0.65)
    assert composite == round(expected, 2)
    assert "strategy" not in eff
    assert abs(sum(eff.values()) - 1.0) < 1e-9


def test_all_missing_returns_none():
    composite, eff = compose(
        mandate=None, strategy=None, value_creation=None, weights=DEFAULT_WEIGHTS
    )
    assert composite is None
    assert eff == {}
