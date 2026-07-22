import pandas as pd

from world_cup_intelligence.statistics import (
    add_coverage_flags,
    flatten_statistics,
    sanitize_statistics,
    statistics_rows_to_wide,
)


def test_statistics_normalization_splits_percentages_and_fractions():
    payload = {
        "statistics": [
            {
                "period": "ALL",
                "groups": [
                    {
                        "groupName": "Passing",
                        "statisticsItems": [
                            {
                                "name": "Ball possession",
                                "home": "55%",
                                "away": "45%",
                            },
                            {
                                "name": "Crosses",
                                "home": "4/10 (40%)",
                                "away": "2/8 (25%)",
                            },
                        ],
                    }
                ],
            }
        ]
    }
    long_frame = pd.DataFrame(flatten_statistics(42, payload))
    wide = add_coverage_flags(statistics_rows_to_wide(long_frame))
    home = wide.loc[wide["side"].eq("home")].iloc[0]
    assert home["ALL_Ball possession"] == 0.55
    assert home["ALL_Crosses_won"] == 4
    assert home["ALL_Crosses_total"] == 10
    assert home["ALL_Crosses_pct"] == 0.4
    assert bool(home["has_statistics"])


def test_impossible_source_percentage_is_quarantined():
    frame = pd.DataFrame(
        {
            "event_id": [1, 1],
            "side": ["home", "away"],
            "ALL_Dribbles_pct": [2.0, 0.5],
            "ALL_Ball possession": [0.0, 0.0],
        }
    )
    clean, issues = sanitize_statistics(frame)
    assert pd.isna(clean.loc[clean["side"].eq("home"), "ALL_Dribbles_pct"]).all()
    assert clean["ALL_Ball possession"].isna().all()
    assert len(issues) == 2
