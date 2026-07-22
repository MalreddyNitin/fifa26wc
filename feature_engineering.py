from pathlib import Path

import numpy as np
import pandas as pd


INPUT_CSV = Path(__file__).resolve().parent / "matches_enriched.csv"
OUTPUT_CSV = Path(__file__).resolve().parent / "team_match_features.csv"

EXTRA_ROLLING_COLS = [
    "goals_for",
    "goals_against",
    "goal_diff",
]

REQUIRED_COLS = [
    "event_id",
    "date",
    "side",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
]


def nullable_binary(condition, available):
    values = pd.Series(condition, index=available.index, dtype="Int64")
    return values.where(available)


def build_team_match_features(matches_df):
    missing_cols = [col for col in REQUIRED_COLS if col not in matches_df.columns]
    if missing_cols:
        raise ValueError(f"Input CSV is missing required columns: {missing_cols}")

    team_match_df = matches_df.copy()
    invalid_sides = team_match_df.loc[
        ~team_match_df["side"].isin(["home", "away"]),
        "side",
    ].unique()
    if len(invalid_sides):
        raise ValueError(
            f"'side' must contain only 'home' or 'away'; found {invalid_sides}"
        )

    is_home = team_match_df["side"].eq("home")

    team_match_df["team"] = np.where(
        is_home,
        team_match_df["home_team"],
        team_match_df["away_team"],
    )
    team_match_df["opponent"] = np.where(
        is_home,
        team_match_df["away_team"],
        team_match_df["home_team"],
    )
    team_match_df["goals_for"] = np.where(
        is_home,
        team_match_df["home_score"],
        team_match_df["away_score"],
    )
    team_match_df["goals_against"] = np.where(
        is_home,
        team_match_df["away_score"],
        team_match_df["home_score"],
    )

    missing_rankings = [
        col
        for col in ["home_fifa_ranking", "away_fifa_ranking"]
        if col not in team_match_df.columns
    ]
    if missing_rankings:
        print(
            "FIFA ranking source columns are unavailable; "
            "ranking features will be empty."
        )

    home_ranking = team_match_df.get(
        "home_fifa_ranking",
        pd.Series(np.nan, index=team_match_df.index),
    )
    away_ranking = team_match_df.get(
        "away_fifa_ranking",
        pd.Series(np.nan, index=team_match_df.index),
    )
    team_match_df["team_fifa_ranking"] = np.where(
        is_home,
        home_ranking,
        away_ranking,
    )
    team_match_df["opponent_fifa_ranking"] = np.where(
        is_home,
        away_ranking,
        home_ranking,
    )

    team_match_df["is_home"] = is_home.astype(int)
    team_match_df["is_away"] = team_match_df["side"].eq("away").astype(int)

    scores_available = team_match_df[
        ["goals_for", "goals_against"]
    ].notna().all(axis=1)
    team_match_df["result"] = pd.Series(
        np.select(
            [
                team_match_df["goals_for"] > team_match_df["goals_against"],
                team_match_df["goals_for"] == team_match_df["goals_against"],
                team_match_df["goals_for"] < team_match_df["goals_against"],
            ],
            ["win", "draw", "loss"],
            default=None,
        ),
        index=team_match_df.index,
        dtype="string",
    ).where(scores_available)
    team_match_df["points"] = (
        team_match_df["result"]
        .map({"win": 3, "draw": 1, "loss": 0})
        .astype("Int64")
    )
    team_match_df["goal_diff"] = (
        team_match_df["goals_for"] - team_match_df["goals_against"]
    )
    team_match_df["team_scored"] = nullable_binary(
        team_match_df["goals_for"].gt(0),
        team_match_df["goals_for"].notna(),
    )
    team_match_df["team_conceded"] = nullable_binary(
        team_match_df["goals_against"].gt(0),
        team_match_df["goals_against"].notna(),
    )

    team_match_df["date"] = pd.to_datetime(
        team_match_df["date"],
        errors="raise",
    )
    team_match_df = team_match_df.sort_values(
        ["team", "date", "event_id"],
        kind="stable",
    ).reset_index(drop=True)

    all_stat_cols = [
        col for col in team_match_df.columns if col.startswith("ALL_")
    ]
    available_rolling_cols = [
        *all_stat_cols,
        *[
            col
            for col in EXTRA_ROLLING_COLS
            if col in team_match_df.columns
        ],
    ]

    team_match_df[available_rolling_cols] = team_match_df[
        available_rolling_cols
    ].apply(pd.to_numeric, errors="coerce")

    rolling_features = {}
    for col in available_rolling_cols:
        for window in (5, 10):
            rolling_features[f"rolling_{col}_{window}"] = (
                team_match_df
                .groupby("team", sort=False)[col]
                .transform(
                    lambda values: (
                        values.shift(1)
                        .rolling(window, min_periods=1)
                        .mean()
                    )
                )
            )

    rolling_df = pd.DataFrame(rolling_features, index=team_match_df.index)
    team_match_df = pd.concat([team_match_df, rolling_df], axis=1)
    rolling_feature_cols = list(rolling_features)
    opponent_rolling = team_match_df[
        ["event_id", "team", *rolling_feature_cols]
    ].rename(
        columns={
            "team": "opponent",
            **{
                col: f"opponent_{col}"
                for col in rolling_feature_cols
            },
        }
    )

    if opponent_rolling.duplicated(["event_id", "opponent"]).any():
        raise ValueError("Duplicate event/opponent rows prevent a safe merge")

    team_match_df = team_match_df.merge(
        opponent_rolling,
        on=["event_id", "opponent"],
        how="left",
        validate="one_to_one",
    )

    return team_match_df


def main():
    matches_df = pd.read_csv(INPUT_CSV)
    team_match_df = build_team_match_features(matches_df)
    team_match_df.to_csv(OUTPUT_CSV, index=False)

    rolling_count = sum(
        col.startswith("rolling_")
        for col in team_match_df.columns
    )
    opponent_rolling_count = sum(
        col.startswith("opponent_rolling_")
        for col in team_match_df.columns
    )
    print(f"Saved {len(team_match_df):,} rows to {OUTPUT_CSV.name}")
    print(
        f"Created {rolling_count} team rolling features and "
        f"{opponent_rolling_count} opponent rolling features"
    )


if __name__ == "__main__":
    main()
