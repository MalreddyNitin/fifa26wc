import pandas as pd

from world_cup_intelligence.canonical import build_canonical_facts


def test_match_expands_to_two_reconciled_team_rows():
    matches = pd.DataFrame(
        {
            "event_id": [1],
            "home_sofascore_team_id": [10],
            "away_sofascore_team_id": [20],
            "home_team_name": ["Alpha"],
            "away_team_name": ["Beta"],
            "kickoff_timestamp": [pd.Timestamp("2020-01-01", tz="UTC")],
            "match_date": [pd.Timestamp("2020-01-01")],
            "status_type": ["finished"],
            "tournament_name": ["Friendly"],
            "unique_tournament_name": ["Friendly"],
            "season_name": ["2020"],
            "round_number": [1],
            "round_name": ["Round 1"],
            "venue_id": [1],
            "venue_name": ["Ground"],
            "venue_city": ["City"],
            "venue_country": ["Alpha"],
            "neutral_site": [0],
            "home_score_90": [2],
            "away_score_90": [1],
            "home_score": [2],
            "away_score": [1],
            "home_displayed_ranking": [10],
            "away_displayed_ranking": [20],
        }
    )
    registry = pd.DataFrame(
        {
            "team_id": ["alpha", "beta"],
            "team_name": ["Alpha", "Beta"],
            "sofascore_team_id": [10, 20],
            "fifa_code": ["ALP", "BET"],
            "confederation": ["A", "B"],
            "world_cup_group": ["A", "A"],
            "host_country_flag": [False, False],
        }
    )
    stats = pd.DataFrame({"event_id": [1, 1], "side": ["home", "away"]})
    _, _, team_matches, _ = build_canonical_facts(matches, registry, stats)
    assert len(team_matches) == 2
    assert set(team_matches["result"]) == {"win", "loss"}
    assert team_matches["goals_for"].sum() == team_matches["goals_against"].sum()
