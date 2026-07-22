from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_ODDS_COLUMNS = [
    "event_id",
    "bookmaker",
    "market",
    "selection",
    "odds",
    "odds_format",
    "snapshot_utc",
    "kickoff_utc",
]


def to_decimal_odds(value, odds_format):
    value = float(value)
    fmt = str(odds_format).casefold()
    if fmt == "decimal":
        return value
    if fmt == "american":
        return 1 + (value / 100 if value > 0 else 100 / abs(value))
    if fmt == "fractional":
        numerator, denominator = map(float, str(value).split("/"))
        return 1 + numerator / denominator
    raise ValueError(f"Unsupported odds format: {odds_format}")


def remove_vig(decimal_odds):
    implied = 1 / np.asarray(decimal_odds, dtype=float)
    return implied / implied.sum()


def expected_value(model_probability, decimal_odds):
    return float(model_probability) * float(decimal_odds) - 1


def normalize_odds(frame):
    missing = [c for c in REQUIRED_ODDS_COLUMNS if c not in frame]
    if missing:
        raise ValueError(f"Odds input is missing columns: {missing}")
    result = frame.copy()
    result["snapshot_utc"] = pd.to_datetime(result["snapshot_utc"], utc=True)
    result["kickoff_utc"] = pd.to_datetime(result["kickoff_utc"], utc=True)
    result["decimal_odds"] = [
        to_decimal_odds(value, fmt)
        for value, fmt in zip(result["odds"], result["odds_format"])
    ]
    result["is_prematch"] = result["snapshot_utc"].lt(result["kickoff_utc"])
    keys = ["event_id", "bookmaker", "market", "snapshot_utc"]
    result["no_vig_probability"] = result.groupby(keys)["decimal_odds"].transform(
        lambda values: remove_vig(values)
    )
    return result.drop_duplicates([*keys, "selection"], keep="last")


def calculate_edges(odds, predictions):
    joined = odds.merge(
        predictions,
        on=["event_id", "market", "selection"],
        how="inner",
        validate="many_to_one",
    )
    joined = joined.loc[joined["is_prematch"]].copy()
    joined["fair_odds"] = 1 / joined["model_probability"]
    joined["edge"] = joined["model_probability"] - joined["no_vig_probability"]
    joined["expected_value"] = [
        expected_value(probability, price)
        for probability, price in zip(
            joined["model_probability"], joined["decimal_odds"]
        )
    ]
    return joined


def import_odds(input_path, output_root):
    input_path = Path(input_path)
    frame = (
        pd.read_parquet(input_path)
        if input_path.suffix.casefold() == ".parquet"
        else pd.read_csv(input_path)
    )
    result = normalize_odds(frame)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output_root / "fct_odds_snapshots.parquet", index=False)
    return result
