import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .client import SofaScoreClient
from .quality import validate_team_stats
from .storage import CheckpointStore

LOGGER = logging.getLogger(__name__)
PERIOD_ALIASES = {
    "ALL": "ALL",
    "1ST": "1ST",
    "2ND": "2ND",
    "EXTRA": "ET",
    "ET": "ET",
    "ET1": "ET1",
    "ET2": "ET2",
}
FRACTION_RE = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)"
    r"\s*\((-?\d+(?:\.\d+)?)%\)\s*$"
)
PERCENT_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)%\s*$")


def _safe_numeric(value):
    if value is None or value == "":
        return np.nan
    if isinstance(value, (int, float, np.number)):
        return float(value)
    text = str(value).strip().replace(",", "")
    percent = PERCENT_RE.match(text)
    if percent:
        return float(percent.group(1)) / 100
    try:
        return float(text)
    except ValueError:
        return value


def flatten_statistics(event_id, payload, payload_hash=None, fetched_at=None):
    """Return source-faithful, long-form statistics rows."""
    rows = []
    fetched_at = fetched_at or datetime.now(timezone.utc).isoformat()
    for period in payload.get("statistics", []) or []:
        period_name = PERIOD_ALIASES.get(
            str(period.get("period", "")).upper(),
            str(period.get("period", "")).upper(),
        )
        for group in period.get("groups", []) or []:
            group_name = group.get("groupName")
            for item in group.get("statisticsItems", []) or []:
                rows.append(
                    {
                        "event_id": int(event_id),
                        "period": period_name,
                        "group_name": group_name,
                        "stat_name": item.get("name"),
                        "stat_key": item.get("key"),
                        "home_value_raw": item.get("home"),
                        "away_value_raw": item.get("away"),
                        "home_numeric_value": item.get("homeValue"),
                        "away_numeric_value": item.get("awayValue"),
                        "home_total": item.get("homeTotal"),
                        "away_total": item.get("awayTotal"),
                        "value_type": item.get("valueType"),
                        "payload_hash": payload_hash,
                        "fetched_at": fetched_at,
                    }
                )
    return rows


def statistics_rows_to_wide(long_frame):
    if long_frame.empty:
        return pd.DataFrame(columns=["event_id", "side"])

    records = []
    identity = ["event_id", "period", "stat_name"]
    # SofaScore repeats overview statistics in detailed groups. The value is
    # the same; retaining the first source occurrence gives a stable schema.
    source = long_frame.drop_duplicates(identity, keep="first")
    for row in source.itertuples(index=False):
        stat = f"{row.period}_{row.stat_name}"
        for side in ("home", "away"):
            raw = getattr(row, f"{side}_value_raw")
            numeric = getattr(row, f"{side}_numeric_value")
            total = getattr(row, f"{side}_total")
            fraction = FRACTION_RE.match(str(raw)) if raw is not None else None
            if fraction:
                records.extend(
                    [
                        (row.event_id, side, f"{stat}_won", float(fraction.group(1))),
                        (row.event_id, side, f"{stat}_total", float(fraction.group(2))),
                        (
                            row.event_id,
                            side,
                            f"{stat}_pct",
                            float(fraction.group(3)) / 100,
                        ),
                    ]
                )
            elif pd.notna(total) and pd.notna(numeric):
                records.extend(
                    [
                        (row.event_id, side, f"{stat}_won", float(numeric)),
                        (row.event_id, side, f"{stat}_total", float(total)),
                        (
                            row.event_id,
                            side,
                            f"{stat}_pct",
                            float(numeric) / float(total) if total else np.nan,
                        ),
                    ]
                )
            else:
                records.append((row.event_id, side, stat, _safe_numeric(raw)))

    values = pd.DataFrame(
        records,
        columns=["event_id", "side", "feature", "value"],
    )
    wide = (
        values.pivot_table(
            index=["event_id", "side"],
            columns="feature",
            values="value",
            aggfunc="first",
            dropna=False,
        )
        .reset_index()
        .rename_axis(columns=None)
    )
    for column in wide.columns:
        if column not in {"event_id", "side"}:
            wide[column] = pd.to_numeric(wide[column], errors="coerce")
    return wide


def add_coverage_flags(wide):
    result = wide.copy()
    names = [str(column).casefold() for column in result.columns]

    def columns_containing(*tokens):
        return [
            column
            for column, name in zip(result.columns, names)
            if all(token in name for token in tokens)
        ]

    result["has_statistics"] = True
    result["has_xg"] = result[columns_containing("expected goals")].notna().any(axis=1)
    result["has_first_half_stats"] = (
        result[[c for c in result if str(c).startswith("1ST_")]].notna().any(axis=1)
    )
    result["has_extra_time_stats"] = (
        result[[c for c in result if str(c).startswith(("ET_", "ET1_", "ET2_"))]]
        .notna()
        .any(axis=1)
    )
    result["has_distance_data"] = (
        result[columns_containing("distance")].notna().any(axis=1)
    )
    return result


def sanitize_statistics(wide):
    """Quarantine impossible source percentages without inventing values."""
    result = wide.copy()
    issues = []
    percentage_columns = [column for column in result if str(column).endswith("_pct")]
    for column in percentage_columns:
        invalid = result[column].notna() & ~result[column].between(0, 1)
        for row in result.loc[invalid, ["event_id", "side", column]].itertuples(
            index=False
        ):
            issues.append(
                {
                    "event_id": row.event_id,
                    "side": row.side,
                    "field": column,
                    "raw_normalized_value": row[2],
                    "issue": "percentage outside [0, 1]",
                }
            )
        result.loc[invalid, column] = np.nan

    possession_columns = [
        column for column in result if str(column).endswith("Ball possession")
    ]
    for column in possession_columns:
        pairs = result.pivot(index="event_id", columns="side", values=column).dropna()
        if not {"home", "away"}.issubset(pairs.columns):
            continue
        totals = pairs["home"] + pairs["away"]
        invalid_events = totals.index[~np.isclose(totals, 1.0, atol=0.03)]
        for event_id in invalid_events:
            issues.append(
                {
                    "event_id": event_id,
                    "side": "both",
                    "field": column,
                    "raw_normalized_value": float(totals.loc[event_id]),
                    "issue": "home and away possession do not sum to 1",
                }
            )
        result.loc[result["event_id"].isin(invalid_events), column] = np.nan
    return result, pd.DataFrame(
        issues,
        columns=[
            "event_id",
            "side",
            "field",
            "raw_normalized_value",
            "issue",
        ],
    )


class StatisticsIngestionPipeline:
    def __init__(self, root, pipeline_config):
        self.root = Path(root)
        self.settings = yaml.safe_load(
            Path(pipeline_config).read_text(encoding="utf-8")
        )
        self.canonical_root = self.root / self.settings["canonical_root"]
        self.checkpoints = CheckpointStore(self.root / self.settings["checkpoint_root"])
        self.run_id = str(uuid.uuid4())
        self.client = SofaScoreClient(
            raw_root=self.root / self.settings["raw_root"],
            pipeline_run_id=self.run_id,
            request_interval=self.settings["request_interval_seconds"],
            retries=self.settings["request_retries"],
            timeout=self.settings["request_timeout_seconds"],
            legacy_cache_root=self.root / ".sofascore_cache",
        )

    def _eligible_events(self):
        matches = pd.read_parquet(self.canonical_root / "all_world_cup_matches.parquet")
        return matches.loc[
            matches["status_type"].eq("finished"),
            [
                "event_id",
                "match_date",
                "home_sofascore_team_id",
                "away_sofascore_team_id",
            ],
        ].copy()

    def run(self, max_events=None):
        events = self._eligible_events()
        checkpoint = self.checkpoints.load("statistics")
        finished = {
            int(event_id)
            for event_id, state in checkpoint.items()
            if state.get("status") in {"available", "unsupported"}
        }
        pending = [
            int(value)
            for value in events["event_id"].unique()
            if int(value) not in finished
        ]
        if max_events is not None:
            pending = pending[:max_events]

        def fetch(event_id):
            try:
                response = self.client.get_json(
                    f"event/{event_id}/statistics",
                    "statistics",
                    {"event_id": event_id},
                    legacy_cache_group="statistics",
                    legacy_cache_key=event_id,
                )
                now = datetime.now(timezone.utc).isoformat()
                if response is None or not response.payload.get("statistics"):
                    return event_id, "unsupported", [], None, now
                rows = flatten_statistics(
                    event_id,
                    response.payload,
                    response.payload_hash,
                    now,
                )
                return event_id, "available", rows, None, now
            except Exception as exc:  # retried by the client first
                return (
                    event_id,
                    "failed",
                    [],
                    repr(exc),
                    datetime.now(timezone.utc).isoformat(),
                )

        new_rows = []
        workers = int(self.settings.get("statistics_workers", 4))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for position, result in enumerate(
                executor.map(fetch, pending),
                start=1,
            ):
                event_id, status, rows, error, fetched_at = result
                checkpoint[str(event_id)] = {
                    "status": status,
                    "fetched_at": fetched_at,
                    "error": error,
                }
                new_rows.extend(rows)
                if position % 100 == 0:
                    LOGGER.info("Statistics processed %s / %s", position, len(pending))
        long_path = self.canonical_root / "team_match_statistics_raw.parquet"
        existing = pd.read_parquet(long_path) if long_path.exists() else pd.DataFrame()
        long_frame = pd.concat(
            [existing, pd.DataFrame(new_rows)],
            ignore_index=True,
        )
        if not long_frame.empty:
            long_frame = long_frame.drop_duplicates(
                ["event_id", "period", "group_name", "stat_name"],
                keep="last",
            )
        long_frame.to_parquet(long_path, index=False)

        wide, quality_issues = sanitize_statistics(statistics_rows_to_wide(long_frame))
        wide = add_coverage_flags(wide)
        validate_team_stats(wide)
        wide.to_parquet(
            self.canonical_root / "team_match_statistics_wide.parquet",
            index=False,
        )
        quality_issues.to_csv(
            self.canonical_root / "statistics_quality_issues.csv",
            index=False,
        )
        # Commit checkpoint state only after the normalized artifacts are
        # durable, so a killed run cannot skip payloads that never reached
        # Parquet.
        self.checkpoints.save("statistics", checkpoint)

        states = pd.DataFrame(
            [
                {
                    "event_id": int(event_id),
                    "status": state.get("status"),
                    "fetched_at": state.get("fetched_at"),
                    "error": state.get("error"),
                }
                for event_id, state in checkpoint.items()
            ]
        )
        failures = states.loc[states["status"].eq("failed")]
        failures.to_csv(
            self.canonical_root / "statistics_ingestion_failures.csv",
            index=False,
        )
        self._write_coverage(events, states)
        return long_frame, wide, states

    def _write_coverage(self, events, states):
        team_events = pd.read_parquet(
            self.canonical_root / "all_world_cup_team_events.parquet",
            columns=["registry_team_id", "event_id", "match_date"],
        )
        team_events = team_events.loc[team_events["event_id"].isin(events["event_id"])]
        covered = team_events.merge(states, on="event_id", how="left")
        covered["year"] = pd.to_datetime(covered["match_date"]).dt.year.astype("Int64")
        coverage = (
            covered.groupby(["registry_team_id", "year"], dropna=False)
            .agg(
                eligible_matches=("event_id", "nunique"),
                statistics_matches=(
                    "status",
                    lambda s: s.eq("available").sum(),
                ),
                unsupported_matches=(
                    "status",
                    lambda s: s.eq("unsupported").sum(),
                ),
                failed_matches=("status", lambda s: s.eq("failed").sum()),
            )
            .reset_index()
        )
        coverage["statistics_coverage"] = (
            coverage["statistics_matches"] / coverage["eligible_matches"]
        )
        coverage.to_csv(
            self.canonical_root / "statistics_coverage_by_team_year.csv",
            index=False,
        )
