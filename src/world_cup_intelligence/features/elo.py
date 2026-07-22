import pandas as pd

IMPORTANCE = {
    "friendly": 10,
    "nations_league": 20,
    "continental_qualifier": 25,
    "world_cup_qualifier": 30,
    "continental_championship": 40,
    "world_cup": 50,
    "other": 20,
}


def expected_score(rating, opponent_rating, home_adjustment=0.0):
    return 1 / (1 + 10 ** ((opponent_rating - rating - home_adjustment) / 400))


def build_elo_history(matches, initial_rating=1500.0, home_advantage=55.0):
    ratings = {}
    rows = []
    ordered = matches.sort_values(["kickoff_utc", "event_id"], kind="stable")
    for match in ordered.itertuples(index=False):
        home = match.home_team_id
        away = match.away_team_id
        home_pre = ratings.get(home, initial_rating)
        away_pre = ratings.get(away, initial_rating)
        neutral = bool(match.neutral_site) if pd.notna(match.neutral_site) else False
        advantage = 0.0 if neutral else home_advantage
        expected_home = expected_score(home_pre, away_pre, advantage)
        expected_away = 1 - expected_home
        home_post, away_post = home_pre, away_pre
        if bool(match.training_eligible):
            home_goals = float(match.home_score_regulation)
            away_goals = float(match.away_score_regulation)
            actual_home = (
                1.0
                if home_goals > away_goals
                else (0.5 if home_goals == away_goals else 0.0)
            )
            goal_margin = abs(home_goals - away_goals)
            margin = (
                1.0
                if goal_margin <= 1
                else (1.5 if goal_margin == 2 else (11 + goal_margin) / 8)
            )
            k = IMPORTANCE.get(match.competition_type, 20) * margin
            delta = k * (actual_home - expected_home)
            home_post = home_pre + delta
            away_post = away_pre - delta
            ratings[home] = home_post
            ratings[away] = away_post
        rows.extend(
            [
                {
                    "event_id": match.event_id,
                    "team_id": home,
                    "opponent_id": away,
                    "side": "home",
                    "elo_pre": home_pre,
                    "opponent_elo_pre": away_pre,
                    "elo_post": home_post,
                    "elo_expected_score": expected_home,
                },
                {
                    "event_id": match.event_id,
                    "team_id": away,
                    "opponent_id": home,
                    "side": "away",
                    "elo_pre": away_pre,
                    "opponent_elo_pre": home_pre,
                    "elo_post": away_post,
                    "elo_expected_score": expected_away,
                },
            ]
        )
    result = pd.DataFrame(rows)
    result["elo_difference"] = result["elo_pre"] - result["opponent_elo_pre"]
    return result
