import math

import numpy as np


def poisson_probability(goals, expected_goals):
    return math.exp(-expected_goals) * expected_goals**goals / math.factorial(goals)


def score_matrix(home_xg, away_xg, max_goals=10, dixon_coles_rho=-0.08):
    matrix = np.array(
        [
            [
                poisson_probability(home, home_xg) * poisson_probability(away, away_xg)
                for away in range(max_goals + 1)
            ]
            for home in range(max_goals + 1)
        ],
        dtype=float,
    )
    # Low-score dependence correction from Dixon-Coles.
    corrections = {
        (0, 0): 1 - home_xg * away_xg * dixon_coles_rho,
        (0, 1): 1 + home_xg * dixon_coles_rho,
        (1, 0): 1 + away_xg * dixon_coles_rho,
        (1, 1): 1 - dixon_coles_rho,
    }
    for (home, away), correction in corrections.items():
        matrix[home, away] *= max(correction, 0)
    return matrix / matrix.sum()


def market_probabilities(matrix):
    home = np.arange(matrix.shape[0])[:, None]
    away = np.arange(matrix.shape[1])[None, :]
    total = home + away
    result = {
        "home_win": float(matrix[home > away].sum()),
        "draw": float(matrix[home == away].sum()),
        "away_win": float(matrix[home < away].sum()),
        "btts_yes": float(matrix[(home > 0) & (away > 0)].sum()),
    }
    for line in (1.5, 2.5, 3.5):
        result[f"over_{str(line).replace('.', '_')}"] = float(
            matrix[total > line].sum()
        )
        result[f"under_{str(line).replace('.', '_')}"] = float(
            matrix[total < line].sum()
        )
    return result
