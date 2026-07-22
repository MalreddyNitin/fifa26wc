import numpy as np
import pandas as pd


class DataQualityError(ValueError):
    pass


def validate_team_events(frame):
    errors = []
    if frame["event_id"].isna().any():
        errors.append("event_id contains nulls")
    if frame.duplicated(["registry_team_id", "event_id"]).any():
        errors.append("registry_team_id + event_id is not unique")
    if frame["match_date"].notna().any():
        invalid = frame["match_date"].dropna().gt(pd.Timestamp.now().normalize())
        scheduled = frame.loc[invalid.index, "status_type"].eq("notstarted")
        if (invalid & ~scheduled).any():
            errors.append("non-scheduled event has a future match date")
    if errors:
        raise DataQualityError("; ".join(errors))


def validate_matches(frame):
    errors = []
    if frame["event_id"].isna().any():
        errors.append("event_id contains nulls")
    if frame["event_id"].duplicated().any():
        errors.append("event_id is not unique")
    for col in ["home_score", "away_score"]:
        if col in frame and frame[col].dropna().lt(0).any():
            errors.append(f"{col} contains negative values")
    if errors:
        raise DataQualityError("; ".join(errors))


def validate_team_stats(frame):
    errors = []
    if frame.duplicated(["event_id", "side"]).any():
        errors.append("event_id + side is not unique")
    if not frame["side"].isin(["home", "away"]).all():
        errors.append("side contains values other than home/away")

    percentage_cols = [
        col
        for col in frame.columns
        if col.endswith("_pct") or "possession" in col.lower()
    ]
    for col in percentage_cols:
        numeric = pd.to_numeric(frame[col], errors="coerce").dropna()
        if ((numeric < 0) | (numeric > 1)).any():
            errors.append(f"{col} is outside [0, 1]")

    if {"event_id", "side", "ALL_Ball possession"}.issubset(frame.columns):
        possession = frame.pivot(
            index="event_id",
            columns="side",
            values="ALL_Ball possession",
        ).dropna()
        if len(possession):
            total = possession.get("home", np.nan) + possession.get("away", np.nan)
            if (~np.isclose(total, 1.0, atol=0.03)).any():
                errors.append("home and away possession do not sum to ~1")

    if errors:
        raise DataQualityError("; ".join(errors))


def assert_rolling_excludes_current(
    frame,
    source_col,
    rolling_col,
    window,
):
    expected = frame.groupby("team", sort=False)[source_col].transform(
        lambda values: (values.shift(1).rolling(window, min_periods=1).mean())
    )
    actual = frame[rolling_col]
    if not np.allclose(actual, expected, equal_nan=True):
        raise DataQualityError(f"{rolling_col} does not equal the shifted {source_col}")
