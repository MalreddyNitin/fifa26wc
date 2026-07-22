from pathlib import Path

import numpy as np
import pandas as pd

from .elo import build_elo_history


def build_feature_marts(team_matches, stats, matches):
    base = team_matches.merge(
        stats.drop(columns=["team_id", "opponent_id"], errors="ignore"),
        on=["event_id", "side"],
        how="left",
        validate="one_to_one",
    )
    elo = build_elo_history(matches)
    base = base.merge(
        elo,
        on=["event_id", "team_id", "opponent_id", "side"],
        how="left",
        validate="one_to_one",
    )
    # Canceled and postponed rows are retained in canonical facts but are not
    # matches and must not consume positions in match-count rolling windows.
    base = base.loc[
        base["training_eligible"] | base["status_type"].eq("notstarted")
    ].copy()
    base["ranking_difference"] = (
        base["team_displayed_ranking"] - base["opponent_displayed_ranking"]
    )
    base = base.sort_values(
        ["team_id", "kickoff_utc", "event_id"], kind="stable"
    ).reset_index(drop=True)
    prior_date = base.groupby("team_id", sort=False)["kickoff_utc"].shift(1)
    base["rest_days"] = (base["kickoff_utc"] - prior_date).dt.total_seconds() / 86_400
    base["fixture_congestion_14d"] = (
        base.groupby("team_id", sort=False)["kickoff_utc"]
        .transform(
            lambda s: s.apply(
                lambda value: (
                    (s.lt(value) & s.ge(value - pd.Timedelta(days=14))).sum()
                )
            )
        )
        .astype("Int64")
    )
    base["confederation_matchup"] = (
        base["team_confederation"].fillna("UNK")
        + "_vs_"
        + base["opponent_confederation"].fillna("UNK")
    )

    stat_cols = [
        column
        for column in stats.columns
        if column.startswith("ALL_") and pd.api.types.is_numeric_dtype(stats[column])
    ]
    source_cols = ["goals_for", "goals_against", "goal_difference", *stat_cols]
    source_cols = list(dict.fromkeys(c for c in source_cols if c in base))

    opponent_actual = base[["event_id", "team_id", *stat_cols]].rename(
        columns={
            "team_id": "opponent_id",
            **{column: f"against_{column}" for column in stat_cols},
        }
    )
    base = base.merge(
        opponent_actual,
        on=["event_id", "opponent_id"],
        how="left",
        validate="one_to_one",
    )
    against_cols = [f"against_{column}" for column in stat_cols]
    rolling_sources = [*source_cols, *against_cols]

    grouped = base.groupby("team_id", sort=False)
    generated = {}
    for column in rolling_sources:
        values = pd.to_numeric(base[column], errors="coerce")
        for window in (3, 5, 10):
            generated[f"rolling_{column}_{window}"] = values.groupby(
                base["team_id"], sort=False
            ).transform(lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean())
        generated[f"rolling_std_{column}_5"] = values.groupby(
            base["team_id"], sort=False
        ).transform(lambda s: s.shift(1).rolling(5, min_periods=2).std())
        generated[f"ewm_{column}_5"] = values.groupby(
            base["team_id"], sort=False
        ).transform(lambda s: s.shift(1).ewm(span=5, adjust=False).mean())
        generated[f"trend_{column}_3_minus_10"] = (
            generated[f"rolling_{column}_3"] - generated[f"rolling_{column}_10"]
        )
    base = pd.concat([base, pd.DataFrame(generated, index=base.index)], axis=1)
    base["prior_match_count"] = grouped.cumcount()
    base["prior_advanced_stats_count_10"] = (
        base.get("has_statistics", pd.Series(False, index=base.index))
        .eq(True)
        .astype(int)
        .groupby(base["team_id"], sort=False)
        .transform(lambda s: s.shift(1).rolling(10, min_periods=1).sum())
    )

    rolling_columns = [
        column for column in base if column.startswith(("rolling_", "ewm_", "trend_"))
    ]
    opponent = base[["event_id", "team_id", *rolling_columns]].rename(
        columns={
            "team_id": "opponent_id",
            **{column: f"opponent_{column}" for column in rolling_columns},
        }
    )
    base = base.merge(
        opponent,
        on=["event_id", "opponent_id"],
        how="left",
        validate="one_to_one",
    )
    return base.sort_values(
        ["kickoff_utc", "event_id", "side"], kind="stable"
    ).reset_index(drop=True)


def materialize_features(root):
    root = Path(root)
    canonical = root / "data" / "canonical"
    features = root / "data" / "features"
    features.mkdir(parents=True, exist_ok=True)
    team_matches = pd.read_parquet(canonical / "fct_team_matches.parquet")
    stats = pd.read_parquet(canonical / "fct_team_match_stats.parquet")
    matches = pd.read_parquet(canonical / "fct_matches.parquet")
    master = build_feature_marts(team_matches, stats, matches)
    common = [
        "event_id",
        "kickoff_utc",
        "team_id",
        "opponent_id",
        "side",
        "is_home",
        "competition_type",
        "round_name",
        "neutral_site",
        "elo_pre",
        "opponent_elo_pre",
        "elo_difference",
        "ranking_difference",
        "rest_days",
        "fixture_congestion_14d",
        "confederation_matchup",
        "prior_match_count",
        "prior_advanced_stats_count_10",
    ]
    leakage_safe = [
        column
        for column in master
        if column in common
        or column.startswith(("rolling_", "opponent_rolling_", "ewm_", "trend_"))
    ]
    targets = [
        "event_id",
        "team_id",
        "side",
        "result",
        "goals_for",
        "goals_against",
        "goal_difference",
        "training_eligible",
    ]
    master.to_parquet(features / "team_match_feature_master.parquet", index=False)
    for name in (
        "feat_match_outcome",
        "feat_scoreline",
        "feat_goal_markets",
        "feat_team_shots",
        "feat_team_corners",
    ):
        output_columns = list(dict.fromkeys([*leakage_safe, *targets]))
        master[output_columns].to_parquet(features / f"{name}.parquet", index=False)
    coverage = pd.DataFrame(
        {
            "feature": leakage_safe,
            "non_null_count": [master[c].notna().sum() for c in leakage_safe],
            "coverage": [master[c].notna().mean() for c in leakage_safe],
        }
    )
    coverage.to_csv(features / "feature_coverage_report.csv", index=False)
    elo_cols = [
        "event_id",
        "kickoff_utc",
        "team_id",
        "opponent_id",
        "side",
        "elo_pre",
        "opponent_elo_pre",
        "elo_post",
        "elo_expected_score",
        "elo_difference",
    ]
    master[elo_cols].to_parquet(features / "team_elo_history.parquet", index=False)
    comparable = master[["elo_pre", "team_displayed_ranking"]].dropna()
    correlation = (
        comparable["elo_pre"].corr(
            comparable["team_displayed_ranking"], method="spearman"
        )
        if len(comparable) >= 2
        else np.nan
    )
    report = root / "reports" / "elo_validation.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# Elo validation\n\n"
        f"- Team-match Elo rows: {len(master):,}\n"
        f"- Source-ranking comparison rows: {len(comparable):,}\n"
        f"- Spearman correlation: {correlation:.4f}\n\n"
        "The comparison is a sanity check only. SofaScore-displayed rankings "
        "on historical event pages are not assumed to be genuine point-in-time "
        "FIFA rankings and are excluded from the default model feature set.\n",
        encoding="utf-8",
    )
    return master, coverage
