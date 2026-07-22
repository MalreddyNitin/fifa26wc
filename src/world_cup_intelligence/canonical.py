from pathlib import Path

import pandas as pd


def classify_competition(name):
    text = str(name or "").casefold()
    if "friendly" in text:
        return "friendly"
    if "nations league" in text:
        return "nations_league"
    if ("world cup" in text or "world championship" in text) and (
        "qual" in text or "qualification" in text
    ):
        return "world_cup_qualifier"
    if "qual" in text or "qualification" in text:
        return "continental_qualifier"
    if "world cup" in text or "world championship" in text:
        return "world_cup"
    if any(
        token in text
        for token in ("euro", "copa am", "africa cup", "asian cup", "gold cup")
    ):
        return "continental_championship"
    return "other"


def _registry_lookup(registry):
    return {int(row.sofascore_team_id): row for row in registry.itertuples(index=False)}


def build_team_dimension(matches, registry):
    lookup = _registry_lookup(registry)
    home = matches[["home_sofascore_team_id", "home_team_name"]].rename(
        columns={
            "home_sofascore_team_id": "sofascore_team_id",
            "home_team_name": "team_name",
        }
    )
    away = matches[["away_sofascore_team_id", "away_team_name"]].rename(
        columns={
            "away_sofascore_team_id": "sofascore_team_id",
            "away_team_name": "team_name",
        }
    )
    teams = pd.concat([home, away], ignore_index=True).drop_duplicates(
        "sofascore_team_id", keep="last"
    )
    rows = []
    for source in teams.itertuples(index=False):
        source_id = int(source.sofascore_team_id)
        registered = lookup.get(source_id)
        rows.append(
            {
                "team_id": (
                    registered.team_id
                    if registered is not None
                    else f"sofascore_{source_id}"
                ),
                "team_name": (
                    registered.team_name if registered is not None else source.team_name
                ),
                "sofascore_team_id": source_id,
                "fifa_code": (registered.fifa_code if registered is not None else None),
                "confederation": (
                    registered.confederation if registered is not None else None
                ),
                "world_cup_group": (
                    registered.world_cup_group if registered is not None else None
                ),
                "is_world_cup_2026_team": registered is not None,
                "host_country_flag": (
                    bool(registered.host_country_flag)
                    if registered is not None
                    else False
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("team_id").reset_index(drop=True)


def build_canonical_facts(matches, registry, statistics):
    matches = matches.copy()
    dim_teams = build_team_dimension(matches, registry)
    id_map = dim_teams.set_index("sofascore_team_id")["team_id"]
    confed_map = dim_teams.set_index("team_id")["confederation"]

    matches["home_team_id"] = matches["home_sofascore_team_id"].map(id_map)
    matches["away_team_id"] = matches["away_sofascore_team_id"].map(id_map)
    matches["kickoff_utc"] = pd.to_datetime(matches["kickoff_timestamp"], utc=True)
    matches["competition_type"] = (
        matches["unique_tournament_name"]
        .fillna(matches["tournament_name"])
        .map(classify_competition)
    )
    matches["home_score_regulation"] = matches["home_score_90"].fillna(
        matches["home_score"]
    )
    matches["away_score_regulation"] = matches["away_score_90"].fillna(
        matches["away_score"]
    )
    matches["training_eligible"] = matches["status_type"].eq("finished") & matches[
        ["home_score_regulation", "away_score_regulation"]
    ].notna().all(axis=1)
    matches["final_advancing_team_id"] = pd.NA
    decided = matches[["home_score", "away_score"]].notna().all(axis=1)
    matches.loc[
        decided & matches["home_score"].gt(matches["away_score"]),
        "final_advancing_team_id",
    ] = matches.loc[
        decided & matches["home_score"].gt(matches["away_score"]),
        "home_team_id",
    ]
    matches.loc[
        decided & matches["away_score"].gt(matches["home_score"]),
        "final_advancing_team_id",
    ] = matches.loc[
        decided & matches["away_score"].gt(matches["home_score"]),
        "away_team_id",
    ]
    fct_matches = matches.sort_values(
        ["kickoff_utc", "event_id"], kind="stable"
    ).reset_index(drop=True)

    base_fields = [
        "event_id",
        "kickoff_utc",
        "match_date",
        "status_type",
        "tournament_name",
        "unique_tournament_name",
        "competition_type",
        "season_name",
        "round_number",
        "round_name",
        "venue_id",
        "venue_name",
        "venue_city",
        "venue_country",
        "neutral_site",
        "training_eligible",
    ]
    rows = []
    for side in ("home", "away"):
        other = "away" if side == "home" else "home"
        block = fct_matches[base_fields].copy()
        block["side"] = side
        block["team_id"] = fct_matches[f"{side}_team_id"]
        block["opponent_id"] = fct_matches[f"{other}_team_id"]
        block["team"] = fct_matches[f"{side}_team_name"]
        block["opponent"] = fct_matches[f"{other}_team_name"]
        block["goals_for"] = fct_matches[f"{side}_score_regulation"]
        block["goals_against"] = fct_matches[f"{other}_score_regulation"]
        block["team_displayed_ranking"] = fct_matches[f"{side}_displayed_ranking"]
        block["opponent_displayed_ranking"] = fct_matches[f"{other}_displayed_ranking"]
        block["is_home"] = int(side == "home")
        block["is_away"] = int(side == "away")
        rows.append(block)
    team_matches = pd.concat(rows, ignore_index=True)
    targets_known = (
        team_matches[["goals_for", "goals_against"]].notna().all(axis=1)
        & team_matches["training_eligible"]
    )
    team_matches["result"] = pd.Series(pd.NA, index=team_matches.index, dtype="string")
    team_matches.loc[
        targets_known & team_matches["goals_for"].gt(team_matches["goals_against"]),
        "result",
    ] = "win"
    team_matches.loc[
        targets_known & team_matches["goals_for"].eq(team_matches["goals_against"]),
        "result",
    ] = "draw"
    team_matches.loc[
        targets_known & team_matches["goals_for"].lt(team_matches["goals_against"]),
        "result",
    ] = "loss"
    team_matches["points"] = (
        team_matches["result"].map({"win": 3, "draw": 1, "loss": 0}).astype("Int64")
    )
    team_matches["goal_difference"] = (
        team_matches["goals_for"] - team_matches["goals_against"]
    )
    team_matches["team_scored"] = (
        team_matches["goals_for"].gt(0).astype("Int64").where(targets_known)
    )
    team_matches["team_conceded"] = (
        team_matches["goals_against"].gt(0).astype("Int64").where(targets_known)
    )
    team_matches["team_confederation"] = team_matches["team_id"].map(confed_map)
    team_matches["opponent_confederation"] = team_matches["opponent_id"].map(confed_map)
    team_matches = team_matches.sort_values(
        ["kickoff_utc", "event_id", "side"], kind="stable"
    ).reset_index(drop=True)

    stat_facts = statistics.merge(
        team_matches[["event_id", "side", "team_id", "opponent_id"]],
        on=["event_id", "side"],
        how="left",
        validate="one_to_one",
    )
    return dim_teams, fct_matches, team_matches, stat_facts


def materialize_canonical(root):
    root = Path(root)
    source = root / "data" / "canonical"
    matches = pd.read_parquet(source / "all_world_cup_matches.parquet")
    registry = pd.read_parquet(source / "dim_teams.parquet")
    stats_path = source / "team_match_statistics_wide.parquet"
    statistics = (
        pd.read_parquet(stats_path)
        if stats_path.exists()
        else pd.DataFrame(columns=["event_id", "side"])
    )
    dim_teams, fct_matches, team_matches, stat_facts = build_canonical_facts(
        matches, registry, statistics
    )
    dim_teams.to_parquet(source / "dim_teams_all_historical.parquet", index=False)
    fct_matches.to_parquet(source / "fct_matches.parquet", index=False)
    team_matches.to_parquet(source / "fct_team_matches.parquet", index=False)
    stat_facts.to_parquet(source / "fct_team_match_stats.parquet", index=False)
    return dim_teams, fct_matches, team_matches, stat_facts
