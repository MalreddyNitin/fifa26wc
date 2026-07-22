import numpy as np

from world_cup_intelligence.models.scoreline import (
    market_probabilities,
    score_matrix,
)


def test_scoreline_probabilities_are_normalized_and_consistent():
    matrix = score_matrix(1.6, 1.1)
    markets = market_probabilities(matrix)
    assert np.isclose(matrix.sum(), 1)
    assert np.isclose(markets["home_win"] + markets["draw"] + markets["away_win"], 1)
    assert markets["over_1_5"] >= markets["over_2_5"]
    assert markets["over_2_5"] >= markets["over_3_5"]
