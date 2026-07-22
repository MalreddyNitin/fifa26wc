from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "team_match_features.csv"
MASTER_OUTPUT_CSV = BASE_DIR / "team_match_master_advanced.csv"
MODEL_FEATURES_OUTPUT_CSV = BASE_DIR / "prematch_model_features.csv"
MODEL_TARGETS_OUTPUT_CSV = BASE_DIR / "prematch_model_targets.csv"
COVERAGE_OUTPUT_CSV = BASE_DIR / "feature_coverage_report.csv"
REDUNDANCY_OUTPUT_CSV = BASE_DIR / "feature_redundancy_report.csv"

AGAINST_STAT_COLS = [
    "ALL_Total shots",
    "ALL_Shots on target",
    "ALL_Corner kicks",
    "ALL_Expected goals",
    "ALL_Touches in penalty area",
]

FORM_STAT_COLS = [
    "ALL_Total shots",
    "ALL_Shots on target",
    "ALL_Corner kicks",
    "ALL_Ball possession",
    "ALL_Passes",
    "ALL_Accurate passes",
    "ALL_Final third entries",
    "ALL_Touches in penalty area",
    "ALL_Expected goals",
    "ALL_Big chances",
    "ALL_Clearances",
    "ALL_Interceptions",
    "ALL_Recoveries",
    "ALL_Goalkeeper saves",
    "goals_for",
    "goals_against",
    "goal_diff",
]

COUNTRY_ALIASES = {
    "bosnia & herzegovina": "bosnia and herzegovina",
    "cote d'ivoire": "ivory coast",
    "c\u00f4te d'ivoire": "ivory coast",
    "c�te d'ivoire": "ivory coast",
    "england": "england",
    "korea republic": "south korea",
    "republic of ireland": "ireland",
    "turkiye": "turkey",
    "t\u00fcrkiye": "turkey",
    "t�rkiye": "turkey",
    "united states": "united states",
    "usa": "united states",
    "west germany": "germany",
}

CONFEDERATIONS = {
    # UEFA
    "Albania": "UEFA",
    "Andorra": "UEFA",
    "Austria": "UEFA",
    "Azerbaijan": "UEFA",
    "Belarus": "UEFA",
    "Belgium": "UEFA",
    "Bosnia & Herzegovina": "UEFA",
    "Bulgaria": "UEFA",
    "Croatia": "UEFA",
    "Czechia": "UEFA",
    "Czechoslovakia": "UEFA",
    "Denmark": "UEFA",
    "England": "UEFA",
    "Estonia": "UEFA",
    "Finland": "UEFA",
    "France": "UEFA",
    "Germany": "UEFA",
    "Greece": "UEFA",
    "Hungary": "UEFA",
    "Iceland": "UEFA",
    "Ireland": "UEFA",
    "Israel": "UEFA",
    "Italy": "UEFA",
    "Kazakhstan": "UEFA",
    "Kosovo": "UEFA",
    "Latvia": "UEFA",
    "Liechtenstein": "UEFA",
    "Lithuania": "UEFA",
    "Luxembourg": "UEFA",
    "Malta": "UEFA",
    "Moldova": "UEFA",
    "Montenegro": "UEFA",
    "Netherlands": "UEFA",
    "North Macedonia": "UEFA",
    "Northern Ireland": "UEFA",
    "Norway": "UEFA",
    "Poland": "UEFA",
    "Portugal": "UEFA",
    "Romania": "UEFA",
    "Russia": "UEFA",
    "San Marino": "UEFA",
    "Scotland": "UEFA",
    "Serbia": "UEFA",
    "Slovakia": "UEFA",
    "Slovenia": "UEFA",
    "Spain": "UEFA",
    "Sweden": "UEFA",
    "Switzerland": "UEFA",
    "T\u00fcrkiye": "UEFA",
    "Ukraine": "UEFA",
    "USSR": "UEFA",
    "Wales": "UEFA",
    "West Germany": "UEFA",
    "Yugoslavia": "UEFA",
    # CONMEBOL
    "Argentina": "CONMEBOL",
    "Brazil": "CONMEBOL",
    "Chile": "CONMEBOL",
    "Colombia": "CONMEBOL",
    "Ecuador": "CONMEBOL",
    "Paraguay": "CONMEBOL",
    "Peru": "CONMEBOL",
    "Uruguay": "CONMEBOL",
    # CONCACAF
    "Costa Rica": "CONCACAF",
    "Honduras": "CONCACAF",
    "Mexico": "CONCACAF",
    "Panama": "CONCACAF",
    "Trinidad and Tobago": "CONCACAF",
    "USA": "CONCACAF",
    # CAF
    "Algeria": "CAF",
    "Cameroon": "CAF",
    "C\u00f4te d'Ivoire": "CAF",
    "DR Congo": "CAF",
    "Egypt": "CAF",
    "Ghana": "CAF",
    "Morocco": "CAF",
    "Nigeria": "CAF",
    "Senegal": "CAF",
    "Tunisia": "CAF",
    # AFC
    "Australia": "AFC",
    "Iran": "AFC",
    "Japan": "AFC",
    "Kuwait": "AFC",
    # OFC
    "New Zealand": "OFC",
}

WORLD_CUP_HOSTS = {
    1966: {"england"},
    1970: {"mexico"},
    1974: {"germany"},
    1978: {"argentina"},
    1982: {"spain"},
    1986: {"mexico"},
    1990: {"italy"},
    1994: {"united states"},
    1998: {"france"},
    2002: {"japan", "south korea"},
    2006: {"germany"},
    2010: {"south africa"},
    2014: {"brazil"},
    2018: {"russia"},
    2022: {"qatar"},
    2026: {"canada", "mexico", "united states"},
}

EURO_HOSTS = {
    1968: {"italy"},
    1980: {"italy"},
    1988: {"germany"},
    1992: {"sweden"},
    1996: {"england"},
    2000: {"belgium", "netherlands"},
    2004: {"portugal"},
    2008: {"austria", "switzerland"},
    2012: {"poland", "ukraine"},
    2016: {"france"},
    2021: {
        "azerbaijan",
        "denmark",
        "england",
        "germany",
        "hungary",
        "italy",
        "netherlands",
        "romania",
        "russia",
        "scotland",
        "spain",
    },
    2024: {"germany"},
}

NATIONS_LEAGUE_HOSTS = {
    2019: {"portugal"},
    2021: {"italy"},
}

IMPORTANCE_WEIGHTS = {
    "friendly": 1,
    "nations_league": 2,
    "continental_qualifier": 3,
    "world_cup_qualifier": 4,
    "continental_championship": 5,
    "world_cup": 6,
}


def normalize_country(value):
    if pd.isna(value):
        return pd.NA
    cleaned = str(value).strip().lower()
    return COUNTRY_ALIASES.get(cleaned, cleaned)


def nullable_comparison(left, right):
    available = left.notna() & right.notna()
    values = pd.Series(left.eq(right), index=left.index, dtype="Int64")
    return values.where(available)


def classify_competition(row):
    text = " ".join(
        str(row.get(col, ""))
        for col in ["tournament", "unique_tournament", "season"]
        if pd.notna(row.get(col))
    ).lower()

    if "friendly" in text:
        return "friendly"
    if "nations league" in text:
        return "nations_league"
    if "world cup qual" in text or "world championship qual" in text:
        return "world_cup_qualifier"
    if "qualification" in text or "qualifier" in text:
        return "continental_qualifier"
    if "world cup" in text or "world championship" in text:
        return "world_cup"
    if "euro" in text:
        return "continental_championship"
    return "other"


def infer_stage(row):
    if pd.notna(row.get("round_name")):
        return str(row["round_name"])

    tournament = str(row.get("tournament", "")).lower()
    if "qualification playoff" in tournament:
        return "Qualification playoff"
    if "qualification" in tournament or "qual." in tournament:
        return "Qualification group"
    if "knockout" in tournament:
        return "Knockout"
    if "finals" in tournament:
        return "Finals"
    if "group" in tournament or "gr." in tournament:
        return "Group stage"
    return pd.NA


def tournament_hosts(row):
    competition_type = row["competition_type"]
    year = row["date"].year

    if competition_type == "world_cup":
        return WORLD_CUP_HOSTS.get(year)
    if competition_type == "continental_championship":
        return EURO_HOSTS.get(year)
    if competition_type == "nations_league":
        return NATIONS_LEAGUE_HOSTS.get(year)
    return None


def host_flag(country, hosts):
    if hosts is None or pd.isna(country):
        return pd.NA
    return int(country in hosts)


def prior_match_count_within_days(dates, days):
    values = dates.to_numpy(dtype="datetime64[ns]")
    lower_bounds = values - np.timedelta64(days, "D")
    starts = np.searchsorted(values, lower_bounds, side="left")
    return pd.Series(
        np.arange(len(values)) - starts,
        index=dates.index,
        dtype="int64",
    )


def add_elo_features(df, initial_rating=1500.0, k_factor=20.0):
    matches = (
        df[
            [
                "event_id",
                "date",
                "home_team",
                "away_team",
                "home_score",
                "away_score",
                "venue_country_normalized",
            ]
        ]
        .drop_duplicates("event_id")
        .sort_values(["date", "event_id"], kind="stable")
    )

    ratings = {}
    previous_changes = {}
    event_values = {}

    for match in matches.itertuples(index=False):
        home = match.home_team
        away = match.away_team
        home_pre = ratings.get(home, initial_rating)
        away_pre = ratings.get(away, initial_rating)
        home_previous_change = previous_changes.get(home, np.nan)
        away_previous_change = previous_changes.get(away, np.nan)

        venue = match.venue_country_normalized
        home_country = normalize_country(home)
        away_country = normalize_country(away)
        if pd.notna(venue) and venue == home_country:
            home_advantage = 60.0
        elif pd.notna(venue) and venue == away_country:
            home_advantage = -60.0
        else:
            home_advantage = 0.0

        expected_home = 1 / (
            1 + 10 ** ((away_pre - home_pre - home_advantage) / 400)
        )
        home_change = 0.0
        away_change = 0.0

        if pd.notna(match.home_score) and pd.notna(match.away_score):
            if match.home_score > match.away_score:
                actual_home = 1.0
            elif match.home_score < match.away_score:
                actual_home = 0.0
            else:
                actual_home = 0.5

            home_change = k_factor * (actual_home - expected_home)
            away_change = -home_change
            ratings[home] = home_pre + home_change
            ratings[away] = away_pre + away_change
            previous_changes[home] = home_change
            previous_changes[away] = away_change

        event_values[match.event_id] = {
            "home_elo_pre": home_pre,
            "away_elo_pre": away_pre,
            "home_elo_change_previous_match": home_previous_change,
            "away_elo_change_previous_match": away_previous_change,
        }

    elo = pd.DataFrame.from_dict(event_values, orient="index")
    elo.index.name = "event_id"
    elo = elo.reset_index()
    df = df.merge(elo, on="event_id", how="left", validate="many_to_one")

    is_home = df["side"].eq("home")
    df["team_elo_pre"] = np.where(
        is_home, df["home_elo_pre"], df["away_elo_pre"]
    )
    df["opponent_elo_pre"] = np.where(
        is_home, df["away_elo_pre"], df["home_elo_pre"]
    )
    df["elo_difference"] = df["team_elo_pre"] - df["opponent_elo_pre"]
    df["team_elo_change_previous_match"] = np.where(
        is_home,
        df["home_elo_change_previous_match"],
        df["away_elo_change_previous_match"],
    )
    df["opponent_elo_change_previous_match"] = np.where(
        is_home,
        df["away_elo_change_previous_match"],
        df["home_elo_change_previous_match"],
    )
    return df.drop(
        columns=[
            "home_elo_pre",
            "away_elo_pre",
            "home_elo_change_previous_match",
            "away_elo_change_previous_match",
        ]
    )


def add_against_stats(df):
    available = [col for col in AGAINST_STAT_COLS if col in df.columns]
    opponent_match_stats = df[["event_id", "team", *available]].rename(
        columns={
            "team": "opponent",
            **{col: f"{col}_against" for col in available},
        }
    )
    if opponent_match_stats.duplicated(["event_id", "opponent"]).any():
        raise ValueError("Cannot attach against stats: duplicate event/team rows")
    return df.merge(
        opponent_match_stats,
        on=["event_id", "opponent"],
        how="left",
        validate="one_to_one",
    )


def add_lagged_features(df):
    all_cols = [col for col in df.columns if col.startswith("ALL_")]
    raw_all_cols = [col for col in all_cols if not col.endswith("_against")]
    count_sources = [*raw_all_cols, "goals_for", "goals_against", "goal_diff"]
    count_sources = [col for col in count_sources if col in df.columns]

    against_cols = [
        f"{col}_against"
        for col in AGAINST_STAT_COLS
        if f"{col}_against" in df.columns
    ]
    form_sources = [
        col for col in [*FORM_STAT_COLS, *against_cols] if col in df.columns
    ]
    generated = {}

    for col in count_sources:
        numeric = pd.to_numeric(df[col], errors="coerce")
        for window in (5, 10):
            generated[f"rolling_{col}_count_{window}"] = (
                numeric.groupby(df["team"], sort=False)
                .transform(
                    lambda values: (
                        values.shift(1)
                        .rolling(window, min_periods=1)
                        .count()
                    )
                )
            )

    for col in against_cols:
        numeric = pd.to_numeric(df[col], errors="coerce")
        for window in (5, 10):
            generated[f"rolling_{col}_{window}"] = (
                numeric.groupby(df["team"], sort=False)
                .transform(
                    lambda values: (
                        values.shift(1)
                        .rolling(window, min_periods=1)
                        .mean()
                    )
                )
            )
            generated[f"rolling_{col}_count_{window}"] = (
                numeric.groupby(df["team"], sort=False)
                .transform(
                    lambda values: (
                        values.shift(1)
                        .rolling(window, min_periods=1)
                        .count()
                    )
                )
            )

    for col in form_sources:
        numeric = pd.to_numeric(df[col], errors="coerce")
        generated[f"ewm_{col}_5"] = (
            numeric.groupby(df["team"], sort=False)
            .transform(
                lambda values: (
                    values.shift(1)
                    .ewm(span=5, min_periods=1, adjust=False)
                    .mean()
                )
            )
        )
        generated[f"rolling_std_{col}_5"] = (
            numeric.groupby(df["team"], sort=False)
            .transform(
                lambda values: (
                    values.shift(1)
                    .rolling(5, min_periods=2)
                    .std()
                )
            )
        )

        short_col = f"rolling_{col}_5"
        long_col = f"rolling_{col}_10"
        if short_col in df.columns:
            short_values = df[short_col]
        else:
            short_values = generated.get(short_col)
        if long_col in df.columns:
            long_values = df[long_col]
        else:
            long_values = generated.get(long_col)
        if short_values is not None and long_values is not None:
            generated[f"trend_{col}_5_vs_10"] = short_values - long_values

    generated_df = pd.DataFrame(generated, index=df.index)
    df = pd.concat([df, generated_df], axis=1)
    return df, list(generated)


def add_opponent_prematch_features(df, feature_cols):
    opponent_features = df[["event_id", "team", *feature_cols]].rename(
        columns={
            "team": "opponent",
            **{col: f"opponent_{col}" for col in feature_cols},
        }
    )
    if opponent_features.duplicated(["event_id", "opponent"]).any():
        raise ValueError("Cannot attach opponent features: duplicate keys")
    return df.merge(
        opponent_features,
        on=["event_id", "opponent"],
        how="left",
        validate="one_to_one",
    )


def add_clear_for_against_aliases(df):
    aliases = {
        "shots": "ALL_Total shots",
        "shots_on_target": "ALL_Shots on target",
        "corners": "ALL_Corner kicks",
        "xg": "ALL_Expected goals",
        "penalty_area_touches": "ALL_Touches in penalty area",
    }
    additions = {}

    for label, source in aliases.items():
        for window in (5, 10):
            for prefix in ("", "opponent_"):
                for_col = f"{prefix}rolling_{source}_{window}"
                against_col = f"{prefix}rolling_{source}_against_{window}"
                if for_col in df.columns:
                    additions[
                        f"{prefix}rolling_{label}_for_{window}"
                    ] = df[for_col]
                if against_col in df.columns:
                    additions[
                        f"{prefix}rolling_{label}_against_{window}"
                    ] = df[against_col]

    return pd.concat([df, pd.DataFrame(additions, index=df.index)], axis=1)


def add_context_features(df):
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    df = df.sort_values(
        ["team", "date", "event_id"],
        kind="stable",
    ).reset_index(drop=True)

    df["prior_matches_count"] = df.groupby("team", sort=False).cumcount()
    df["rolling_matches_available_5"] = df["prior_matches_count"].clip(upper=5)
    df["rolling_matches_available_10"] = df["prior_matches_count"].clip(upper=10)
    df["days_since_last_match"] = (
        df.groupby("team", sort=False)["date"].diff().dt.days
    )
    for days in (30, 90):
        df[f"matches_last_{days}_days"] = (
            df.groupby("team", sort=False)["date"]
            .transform(lambda dates: prior_match_count_within_days(dates, days))
            .astype("Int64")
        )

    rest = df[
        [
            "event_id",
            "team",
            "days_since_last_match",
            "matches_last_30_days",
            "matches_last_90_days",
        ]
    ].rename(
        columns={
            "team": "opponent",
            "days_since_last_match": "opponent_days_since_last_match",
            "matches_last_30_days": "opponent_matches_last_30_days",
            "matches_last_90_days": "opponent_matches_last_90_days",
        }
    )
    df = df.merge(
        rest,
        on=["event_id", "opponent"],
        how="left",
        validate="one_to_one",
    )
    df["rest_difference"] = (
        df["days_since_last_match"]
        - df["opponent_days_since_last_match"]
    )

    df["team_country_normalized"] = df["team"].map(normalize_country)
    df["opponent_country_normalized"] = df["opponent"].map(normalize_country)
    df["venue_country_normalized"] = df["venue_country"].map(normalize_country)
    df["team_playing_in_own_country"] = nullable_comparison(
        df["team_country_normalized"],
        df["venue_country_normalized"],
    )
    df["opponent_playing_in_own_country"] = nullable_comparison(
        df["opponent_country_normalized"],
        df["venue_country_normalized"],
    )

    df["team_confederation"] = df["team"].map(CONFEDERATIONS).astype("string")
    df["opponent_confederation"] = (
        df["opponent"].map(CONFEDERATIONS).astype("string")
    )
    df["same_confederation"] = nullable_comparison(
        df["team_confederation"],
        df["opponent_confederation"],
    )
    df["confederation_matchup"] = (
        df["team_confederation"].fillna("Unknown")
        + "_vs_"
        + df["opponent_confederation"].fillna("Unknown")
    )

    df["competition_name"] = df["unique_tournament"].fillna(df["tournament"])
    df["competition_type"] = df.apply(classify_competition, axis=1)
    df["competition_importance"] = (
        df["competition_type"].map(IMPORTANCE_WEIGHTS).astype("Int64")
    )
    df["season_name"] = df["season"]
    df["stage_name"] = df.apply(infer_stage, axis=1).astype("string")
    df["round_number"] = pd.to_numeric(df["round"], errors="coerce")

    hosts = df.apply(tournament_hosts, axis=1)
    df["team_is_host_country"] = pd.Series(
        [
            host_flag(country, host_set)
            for country, host_set in zip(df["team_country_normalized"], hosts)
        ],
        dtype="Int64",
    )
    df["opponent_is_host_country"] = pd.Series(
        [
            host_flag(country, host_set)
            for country, host_set in zip(
                df["opponent_country_normalized"], hosts
            )
        ],
        dtype="Int64",
    )
    return df


def add_coverage_and_knockout_features(df):
    advanced_cols = [
        col
        for col in [
            "ALL_Expected goals",
            "ALL_Final third entries",
            "ALL_Touches in penalty area",
            "ALL_Big chances",
        ]
        if col in df.columns
    ]
    first_half_cols = [col for col in df.columns if col.startswith("1ST_")]
    extra_time_cols = [
        col for col in df.columns if col.startswith(("ET1_", "ET2_"))
    ]
    all_cols = [col for col in df.columns if col.startswith("ALL_")]

    df["has_xg"] = df.get(
        "ALL_Expected goals",
        pd.Series(np.nan, index=df.index),
    ).notna().astype(int)
    df["has_advanced_stats"] = (
        df[advanced_cols].notna().any(axis=1).astype(int)
        if advanced_cols
        else 0
    )
    df["has_first_half_stats"] = (
        df[first_half_cols].notna().any(axis=1).astype(int)
        if first_half_cols
        else 0
    )
    df["has_extra_time_stats"] = (
        df[extra_time_cols].notna().any(axis=1).astype(int)
        if extra_time_cols
        else 0
    )
    df["has_distance_data"] = df.get(
        "ALL_Distance covered",
        pd.Series(np.nan, index=df.index),
    ).notna().astype(int)

    any_current_stats = (
        df[all_cols].notna().any(axis=1)
        if all_cols
        else pd.Series(False, index=df.index)
    )
    went_to_extra_time = pd.Series(pd.NA, index=df.index, dtype="Int64")
    went_to_extra_time.loc[any_current_stats] = 0
    went_to_extra_time.loc[df["has_extra_time_stats"].eq(1)] = 1
    df["went_to_extra_time"] = went_to_extra_time

    no_extra_time = df["went_to_extra_time"].eq(0).fillna(False)
    df["home_score_90"] = df["home_score"].where(no_extra_time)
    df["away_score_90"] = df["away_score"].where(no_extra_time)
    df["home_score_after_extra_time"] = np.nan
    df["away_score_after_extra_time"] = np.nan
    df["home_penalties"] = np.nan
    df["away_penalties"] = np.nan
    df["went_to_penalties"] = pd.Series(pd.NA, index=df.index, dtype="Int64")

    score_90_available = df[["home_score_90", "away_score_90"]].notna().all(axis=1)
    result_90 = np.select(
        [
            df["home_score_90"] > df["away_score_90"],
            df["home_score_90"] == df["away_score_90"],
            df["home_score_90"] < df["away_score_90"],
        ],
        ["home_win", "draw", "away_win"],
        default=None,
    )
    df["result_90"] = pd.Series(result_90, dtype="string").where(
        score_90_available
    )
    df.loc[df["went_to_extra_time"].eq(1), "result_90"] = "draw"

    knockout = df["stage_name"].str.lower().str.contains(
        "final|knockout|round of|quarter|semi",
        na=False,
    )
    winner = np.where(
        df["home_score"] > df["away_score"],
        df["home_team"],
        np.where(
            df["away_score"] > df["home_score"],
            df["away_team"],
            None,
        ),
    )
    df["qualified_team"] = pd.Series(winner, dtype="string").where(knockout)

    if "team_fifa_ranking" in df.columns:
        df["team_sofascore_displayed_ranking"] = df["team_fifa_ranking"]
    else:
        df["team_sofascore_displayed_ranking"] = np.nan
    if "opponent_fifa_ranking" in df.columns:
        df["opponent_sofascore_displayed_ranking"] = (
            df["opponent_fifa_ranking"]
        )
    else:
        df["opponent_sofascore_displayed_ranking"] = np.nan
    return df


def build_coverage_report(df):
    records = []
    for col in df.columns:
        series = df[col]
        numeric = pd.to_numeric(series, errors="coerce")
        numeric_non_null = numeric.notna()
        nonzero_rate = (
            numeric.loc[numeric_non_null].ne(0).mean()
            if numeric_non_null.any()
            else np.nan
        )
        non_null_rate = series.notna().mean()
        records.append(
            {
                "feature": col,
                "dtype": str(series.dtype),
                "non_null_rate": non_null_rate,
                "nonzero_rate_among_available": nonzero_rate,
                "unique_non_null_values": series.nunique(dropna=True),
                "low_coverage_below_20pct": non_null_rate < 0.20,
                "rare_nonzero_below_1pct": (
                    nonzero_rate < 0.01
                    if pd.notna(nonzero_rate)
                    else pd.NA
                ),
            }
        )
    return pd.DataFrame(records).sort_values(
        ["non_null_rate", "feature"],
        kind="stable",
    )


def build_redundancy_report(df):
    pairs = [
        ("ALL_Goalkeeper saves", "ALL_Total saves"),
        ("ALL_Tackles", "ALL_Total tackles"),
        ("ALL_Tackles", "ALL_Tackles won"),
        ("ALL_Duels", "ALL_Ground duels_pct"),
    ]
    records = []
    for left, right in pairs:
        if left not in df.columns or right not in df.columns:
            continue
        both = df[[left, right]].notna().all(axis=1)
        left_values = pd.to_numeric(df.loc[both, left], errors="coerce")
        right_values = pd.to_numeric(df.loc[both, right], errors="coerce")
        numeric_both = left_values.notna() & right_values.notna()
        records.append(
            {
                "left_feature": left,
                "right_feature": right,
                "rows_both_available": int(both.sum()),
                "equality_rate": (
                    left_values.eq(right_values).mean()
                    if len(left_values)
                    else np.nan
                ),
                "correlation": (
                    left_values.loc[numeric_both].corr(
                        right_values.loc[numeric_both]
                    )
                    if numeric_both.sum() > 1
                    else np.nan
                ),
            }
        )
    return pd.DataFrame(records)


def select_model_features(df):
    identifiers = ["event_id", "date", "team", "opponent"]
    candidate_features = [
        "team_elo_pre",
        "opponent_elo_pre",
        "elo_difference",
        "team_elo_change_previous_match",
        "is_home",
        "neutral_site",
        "team_is_host_country",
        "opponent_is_host_country",
        "team_playing_in_own_country",
        "opponent_playing_in_own_country",
        "team_confederation",
        "opponent_confederation",
        "same_confederation",
        "competition_type",
        "competition_importance",
        "stage_name",
        "prior_matches_count",
        "rolling_matches_available_5",
        "days_since_last_match",
        "opponent_days_since_last_match",
        "rest_difference",
        "matches_last_30_days",
        "opponent_matches_last_30_days",
        "rolling_ALL_Total shots_count_5",
        "rolling_ALL_Expected goals_count_5",
        "rolling_goals_for_5",
        "rolling_goals_for_10",
        "rolling_goals_against_5",
        "rolling_goals_against_10",
        "rolling_goal_diff_5",
        "opponent_rolling_goals_for_5",
        "opponent_rolling_goals_against_5",
        "rolling_shots_for_5",
        "rolling_shots_against_5",
        "opponent_rolling_shots_for_5",
        "opponent_rolling_shots_against_5",
        "rolling_shots_on_target_for_5",
        "rolling_shots_on_target_against_5",
        "rolling_corners_for_5",
        "rolling_corners_against_5",
        "rolling_xg_for_5",
        "rolling_xg_against_5",
        "rolling_penalty_area_touches_for_5",
        "rolling_penalty_area_touches_against_5",
        "rolling_ALL_Ball possession_5",
        "rolling_ALL_Final third entries_5",
        "rolling_ALL_Recoveries_5",
        "ewm_ALL_Total shots_5",
        "rolling_std_ALL_Total shots_5",
        "trend_ALL_Total shots_5_vs_10",
    ]
    selected = [col for col in candidate_features if col in df.columns]
    return df[[*identifiers, *selected]].copy()


def build_targets(df):
    target_cols = [
        "event_id",
        "date",
        "team",
        "opponent",
        "home_score",
        "away_score",
        "goals_for",
        "goals_against",
        "result",
        "points",
        "goal_diff",
        "team_scored",
        "team_conceded",
        "result_90",
        "qualified_team",
    ]
    return df[[col for col in target_cols if col in df.columns]].copy()


def build_advanced_features(source_df):
    required = {
        "event_id",
        "date",
        "team",
        "opponent",
        "side",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "venue_country",
    }
    missing = sorted(required.difference(source_df.columns))
    if missing:
        raise ValueError(f"Input is missing required columns: {missing}")
    if source_df.duplicated(["event_id", "team"]).any():
        raise ValueError("Input contains duplicate event/team rows")

    df = add_context_features(source_df.copy())
    df = add_coverage_and_knockout_features(df)
    df = add_elo_features(df)
    df = add_against_stats(df)
    df, generated_lag_cols = add_lagged_features(df)

    opponent_feature_cols = [
        col
        for col in generated_lag_cols
        if col.startswith(
            ("rolling_", "ewm_", "rolling_std_", "trend_")
        )
    ]
    df = add_opponent_prematch_features(df, opponent_feature_cols)
    df = add_clear_for_against_aliases(df)
    return df


def main():
    source_df = pd.read_csv(INPUT_CSV)
    master_df = build_advanced_features(source_df)
    model_features_df = select_model_features(master_df)
    targets_df = build_targets(master_df)
    coverage_df = build_coverage_report(master_df)
    redundancy_df = build_redundancy_report(master_df)

    master_df.to_csv(MASTER_OUTPUT_CSV, index=False)
    model_features_df.to_csv(MODEL_FEATURES_OUTPUT_CSV, index=False)
    targets_df.to_csv(MODEL_TARGETS_OUTPUT_CSV, index=False)
    coverage_df.to_csv(COVERAGE_OUTPUT_CSV, index=False)
    redundancy_df.to_csv(REDUNDANCY_OUTPUT_CSV, index=False)

    predictor_count = len(model_features_df.columns) - 4
    print(
        f"Saved advanced master: {master_df.shape[0]:,} rows x "
        f"{master_df.shape[1]:,} columns"
    )
    print(
        f"Saved leakage-safe model table with {predictor_count} predictors"
    )
    print("Saved separate targets, coverage, and redundancy reports")


if __name__ == "__main__":
    main()
