import numpy as np

from world_cup_intelligence.odds import (
    expected_value,
    remove_vig,
    to_decimal_odds,
)


def test_odds_conversions_and_vig_removal():
    assert to_decimal_odds(150, "american") == 2.5
    assert to_decimal_odds(-200, "american") == 1.5
    probabilities = remove_vig([2.0, 3.5, 4.0])
    assert np.isclose(probabilities.sum(), 1)
    assert np.isclose(expected_value(0.5, 2.2), 0.1)
