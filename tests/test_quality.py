import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from world_cup_intelligence.quality import (  # noqa: E402
    DataQualityError,
    assert_rolling_excludes_current,
    validate_matches,
    validate_team_stats,
)


class DataQualityTests(unittest.TestCase):
    def test_match_validation_rejects_negative_goals(self):
        frame = pd.DataFrame(
            {
                "event_id": [1],
                "home_score": [-1],
                "away_score": [0],
            }
        )
        with self.assertRaises(DataQualityError):
            validate_matches(frame)

    def test_team_stats_require_unique_event_side(self):
        frame = pd.DataFrame(
            {
                "event_id": [1, 1],
                "side": ["home", "home"],
            }
        )
        with self.assertRaises(DataQualityError):
            validate_team_stats(frame)

    def test_rolling_validation_uses_previous_matches_only(self):
        frame = pd.DataFrame(
            {
                "team": ["A", "A", "A", "B", "B"],
                "shots": [10, 20, 30, 5, 7],
                "rolling_shots_2": [
                    float("nan"),
                    10,
                    15,
                    float("nan"),
                    5,
                ],
            }
        )
        assert_rolling_excludes_current(
            frame,
            "shots",
            "rolling_shots_2",
            2,
        )


if __name__ == "__main__":
    unittest.main()
