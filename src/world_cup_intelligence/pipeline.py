import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml

from .client import SofaScoreClient
from .quality import validate_matches, validate_team_events
from .registry import build_aliases, load_team_registry
from .storage import CheckpointStore

LOGGER = logging.getLogger(__name__)
COUNTRY_ALIASES = {
    "usa": "united states",
    "united states of america": "united states",
    "korea republic": "south korea",
    "republic of korea": "south korea",
    "czech republic": "czechia",
    "ivory coast": "côte d'ivoire",
    "turkiye": "türkiye",
}


def normalize_country_name(value):
    if pd.isna(value):
        return pd.NA
    normalized = str(value).strip().casefold()
    return COUNTRY_ALIASES.get(normalized, normalized)


def timestamp_to_datetime(value):
    if value is None:
        return pd.NaT
    if abs(value) > 10_000_000_000:
        value /= 1000
    return pd.to_datetime(value, unit="s", utc=True)


def safe_nested(data, *keys):
    value = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def flatten_team_event(event, registry_team_id):
    start = timestamp_to_datetime(event.get("startTimestamp"))
    home_score = event.get("homeScore", {})
    away_score = event.get("awayScore", {})
    return {
        "registry_team_id": registry_team_id,
        "event_id": event.get("id"),
        "match_date": start.tz_localize(None) if pd.notna(start) else pd.NaT,
        "kickoff_timestamp": start,
        "home_sofascore_team_id": safe_nested(event, "homeTeam", "id"),
        "away_sofascore_team_id": safe_nested(event, "awayTeam", "id"),
        "home_team_name": safe_nested(event, "homeTeam", "name"),
        "away_team_name": safe_nested(event, "awayTeam", "name"),
        "home_score": home_score.get("current"),
        "away_score": away_score.get("current"),
        "home_score_90": home_score.get("normaltime"),
        "away_score_90": away_score.get("normaltime"),
        "home_score_after_extra_time": home_score.get("overtime"),
        "away_score_after_extra_time": away_score.get("overtime"),
        "home_penalties": home_score.get("penalties"),
        "away_penalties": away_score.get("penalties"),
        "status_type": safe_nested(event, "status", "type"),
        "status_description": safe_nested(event, "status", "description"),
        "tournament_id": safe_nested(event, "tournament", "id"),
        "tournament_name": safe_nested(event, "tournament", "name"),
        "unique_tournament_id": safe_nested(
            event, "tournament", "uniqueTournament", "id"
        ),
        "unique_tournament_name": safe_nested(
            event, "tournament", "uniqueTournament", "name"
        ),
        "season_id": safe_nested(event, "season", "id"),
        "season_name": safe_nested(event, "season", "name"),
        "round_number": safe_nested(event, "roundInfo", "round"),
        "round_name": safe_nested(event, "roundInfo", "name"),
        "slug": event.get("slug"),
        "custom_id": event.get("customId"),
    }


def flatten_event_detail(event_id, payload):
    event = payload.get("event", payload)
    return {
        "event_id": event_id,
        "venue_id": safe_nested(event, "venue", "id"),
        "venue_name": safe_nested(event, "venue", "name"),
        "venue_city": safe_nested(event, "venue", "city", "name"),
        "venue_country": safe_nested(event, "venue", "country", "name"),
        "venue_capacity": safe_nested(event, "venue", "capacity"),
        "venue_latitude": safe_nested(event, "venue", "venueCoordinates", "latitude"),
        "venue_longitude": safe_nested(event, "venue", "venueCoordinates", "longitude"),
        "home_displayed_ranking": safe_nested(event, "homeTeam", "ranking"),
        "away_displayed_ranking": safe_nested(event, "awayTeam", "ranking"),
    }


def derive_match_fields(matches):
    result = matches.copy()
    result["home_sofascore_displayed_ranking"] = result["home_displayed_ranking"]
    result["away_sofascore_displayed_ranking"] = result["away_displayed_ranking"]
    home_country = result["home_team_name"].map(normalize_country_name)
    away_country = result["away_team_name"].map(normalize_country_name)
    venue_country = result["venue_country"].map(normalize_country_name)
    result["home_team_playing_in_own_country"] = pd.Series(
        pd.NA, index=result.index, dtype="Int64"
    )
    result["away_team_playing_in_own_country"] = pd.Series(
        pd.NA, index=result.index, dtype="Int64"
    )
    result["neutral_site"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    venue_known = venue_country.notna()
    result.loc[venue_known, "home_team_playing_in_own_country"] = (
        venue_country.loc[venue_known].eq(home_country.loc[venue_known])
    ).astype(int)
    result.loc[venue_known, "away_team_playing_in_own_country"] = (
        venue_country.loc[venue_known].eq(away_country.loc[venue_known])
    ).astype(int)
    result.loc[venue_known, "neutral_site"] = (
        ~venue_country.loc[venue_known].eq(home_country.loc[venue_known])
        & ~venue_country.loc[venue_known].eq(away_country.loc[venue_known])
    ).astype(int)
    result["home_host_team"] = result["home_team_playing_in_own_country"]
    result["away_host_team"] = result["away_team_playing_in_own_country"]
    result["result_90"] = pd.NA
    score_known = result[["home_score_90", "away_score_90"]].notna().all(axis=1)
    result.loc[
        score_known & (result["home_score_90"] > result["away_score_90"]),
        "result_90",
    ] = "home_win"
    result.loc[
        score_known & (result["home_score_90"] == result["away_score_90"]),
        "result_90",
    ] = "draw"
    result.loc[
        score_known & (result["home_score_90"] < result["away_score_90"]),
        "result_90",
    ] = "away_win"
    return result


class AllTeamIngestionPipeline:
    def __init__(self, root, teams_config, pipeline_config):
        self.root = Path(root)
        self.teams_config = Path(teams_config)
        self.pipeline_config = Path(pipeline_config)
        self.settings = yaml.safe_load(self.pipeline_config.read_text(encoding="utf-8"))
        self.run_id = str(uuid.uuid4())
        self.started_at = datetime.now(timezone.utc)
        self.canonical_root = self.root / self.settings["canonical_root"]
        self.canonical_root.mkdir(parents=True, exist_ok=True)
        self.run_log_root = self.root / self.settings["run_log_root"]
        self.run_log_root.mkdir(parents=True, exist_ok=True)
        self.checkpoints = CheckpointStore(self.root / self.settings["checkpoint_root"])
        self.client = SofaScoreClient(
            raw_root=self.root / self.settings["raw_root"],
            pipeline_run_id=self.run_id,
            request_interval=self.settings["request_interval_seconds"],
            retries=self.settings["request_retries"],
            timeout=self.settings["request_timeout_seconds"],
            legacy_cache_root=self.root / ".sofascore_cache",
        )
        self.metrics = {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "teams_succeeded": 0,
            "teams_failed": 0,
            "event_pages_fetched": 0,
            "event_details_fetched": 0,
            "errors": [],
        }

    def materialize_registry(self):
        registry = load_team_registry(self.teams_config)
        required = ["sofascore_team_id", "sofascore_slug"]
        missing = registry[required].isna().any(axis=1)
        if missing.any():
            unresolved = registry.loc[missing, "team_id"].tolist()
            raise ValueError(f"Resolve SofaScore IDs before ingestion: {unresolved}")
        registry.to_parquet(
            self.canonical_root / "dim_teams.parquet",
            index=False,
        )
        build_aliases(registry).to_parquet(
            self.canonical_root / "team_name_aliases.parquet",
            index=False,
        )
        return registry

    def _existing_events(self):
        path = self.canonical_root / "all_world_cup_team_events.parquet"
        if path.exists():
            return pd.read_parquet(path)
        return pd.DataFrame()

    def fetch_team_events(self, registry, max_pages=None):
        checkpoint = self.checkpoints.load("team_events")
        rows = []
        since = pd.Timestamp(self.settings["historical_since_date"])
        overlap = timedelta(days=self.settings["recent_refetch_days"])
        page_limit = (
            max_pages if max_pages is not None else self.settings["max_event_pages"]
        )

        for team in registry.itertuples(index=False):
            LOGGER.info("Fetching events for %s", team.team_name)
            latest_checkpoint = checkpoint.get(team.team_id, {}).get(
                "latest_match_date"
            )
            cutoff = since
            history_complete = checkpoint.get(team.team_id, {}).get(
                "history_complete",
                False,
            )
            if latest_checkpoint and history_complete:
                cutoff = max(
                    since,
                    pd.Timestamp(latest_checkpoint) - overlap,
                )
            team_rows = []
            reached_cutoff = False
            try:
                for page in range(page_limit):
                    response = self.client.get_json(
                        (f"team/{int(team.sofascore_team_id)}/events/last/{page}"),
                        "team_events",
                        {
                            "team_id": team.team_id,
                            "page": f"{page:03d}",
                        },
                    )
                    if response is None:
                        reached_cutoff = True
                        break
                    self.metrics["event_pages_fetched"] += 1
                    events = response.payload.get("events", [])
                    if not events:
                        reached_cutoff = True
                        break

                    page_dates = []
                    for event in events:
                        row = flatten_team_event(event, team.team_id)
                        if pd.notna(row["match_date"]):
                            page_dates.append(row["match_date"])
                        if pd.isna(row["match_date"]) or row["match_date"] >= cutoff:
                            team_rows.append(row)

                    if page_dates and min(page_dates) < cutoff:
                        reached_cutoff = True
                        break

                rows.extend(team_rows)
                latest = max(
                    (
                        row["match_date"]
                        for row in team_rows
                        if pd.notna(row["match_date"])
                    ),
                    default=None,
                )
                checkpoint[team.team_id] = {
                    "latest_match_date": (
                        latest.isoformat() if latest is not None else None
                    ),
                    "history_complete": (history_complete or reached_cutoff),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                self.checkpoints.save("team_events", checkpoint)
                self.metrics["teams_succeeded"] += 1
            except Exception as exc:
                LOGGER.exception("Team ingestion failed: %s", team.team_id)
                self.metrics["teams_failed"] += 1
                self.metrics["errors"].append(
                    {"scope": team.team_id, "error": repr(exc)}
                )

        fetched = pd.DataFrame(rows)
        existing = self._existing_events()
        combined = pd.concat([existing, fetched], ignore_index=True)
        combined = combined.drop_duplicates(
            ["registry_team_id", "event_id"],
            keep="last",
        )
        combined = combined.sort_values(
            ["registry_team_id", "match_date", "event_id"],
            kind="stable",
        )
        validate_team_events(combined)
        combined.to_parquet(
            self.canonical_root / "all_world_cup_team_events.parquet",
            index=False,
        )
        return combined

    def enrich_matches(self, team_events, max_details=None):
        match_columns = [
            col for col in team_events.columns if col != "registry_team_id"
        ]
        matches = (
            team_events[match_columns]
            .drop_duplicates("event_id", keep="last")
            .sort_values(["match_date", "event_id"], kind="stable")
        )
        output_path = self.canonical_root / "all_world_cup_matches.parquet"
        existing = (
            pd.read_parquet(output_path) if output_path.exists() else pd.DataFrame()
        )
        completed = set(
            existing.loc[
                existing.get("details_fetched", False).fillna(False),
                "event_id",
            ]
            if len(existing) and "details_fetched" in existing
            else []
        )
        detail_checkpoint = self.checkpoints.load("event_details")
        details_by_event = {
            int(event_id): row
            for event_id, row in detail_checkpoint.items()
            if row.get("details_fetched")
        }
        completed.update(details_by_event)
        details = list(details_by_event.values())
        pending = [
            int(event_id)
            for event_id in matches["event_id"].dropna().unique()
            if event_id not in completed
        ]
        if max_details is not None:
            pending = pending[:max_details]

        def fetch_detail(event_id):
            try:
                response = self.client.get_json(
                    f"event/{event_id}",
                    "event_details",
                    {"event_id": event_id},
                    legacy_cache_group="event_details",
                    legacy_cache_key=event_id,
                )
                if response is None:
                    return {
                        "event_id": event_id,
                        "details_fetched": False,
                    }, None
                row = flatten_event_detail(event_id, response.payload)
                row["details_fetched"] = True
                return row, None
            except Exception as exc:
                return None, exc

        workers = int(self.settings.get("event_detail_workers", 4))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            fetched_rows = executor.map(fetch_detail, pending)
            for position, (row, error) in enumerate(
                fetched_rows,
                start=1,
            ):
                event_id = pending[position - 1]
                if error is not None:
                    LOGGER.error(
                        "Event detail failed: %s: %r",
                        event_id,
                        error,
                    )
                    self.metrics["errors"].append(
                        {
                            "scope": f"event:{event_id}",
                            "error": repr(error),
                        }
                    )
                    continue

                details.append(row)
                if row["details_fetched"]:
                    detail_checkpoint[str(event_id)] = row
                    self.metrics["event_details_fetched"] += 1
                if position % 25 == 0:
                    self.checkpoints.save(
                        "event_details",
                        detail_checkpoint,
                    )
                if position % 100 == 0:
                    LOGGER.info(
                        "Enriched %s / %s pending event details",
                        position,
                        len(pending),
                    )

        self.checkpoints.save("event_details", detail_checkpoint)
        detail_frame = pd.DataFrame(details)
        if len(existing):
            existing_details = existing[
                [
                    col
                    for col in [
                        "event_id",
                        "venue_id",
                        "venue_name",
                        "venue_city",
                        "venue_country",
                        "venue_capacity",
                        "venue_latitude",
                        "venue_longitude",
                        "home_displayed_ranking",
                        "away_displayed_ranking",
                        "details_fetched",
                    ]
                    if col in existing.columns
                ]
            ]
            detail_frame = pd.concat(
                [existing_details, detail_frame],
                ignore_index=True,
            ).drop_duplicates("event_id", keep="last")

        matches = matches.merge(
            detail_frame,
            on="event_id",
            how="left",
            validate="one_to_one",
        )
        matches["details_fetched"] = matches["details_fetched"].fillna(False)
        matches = derive_match_fields(matches)
        validate_matches(matches)
        matches.to_parquet(output_path, index=False)
        failures = matches.loc[
            ~matches["details_fetched"],
            ["event_id"],
        ].copy()
        failures["status_code"] = pd.NA
        failures["error_message"] = "event detail unavailable"
        failures.to_csv(
            self.canonical_root / "event_enrichment_failures.csv",
            index=False,
        )
        coverage_fields = [
            "venue_name",
            "venue_country",
            "venue_latitude",
            "home_displayed_ranking",
            "away_displayed_ranking",
            "home_score_90",
            "away_score_90",
        ]
        coverage = pd.DataFrame(
            {
                "field": coverage_fields,
                "non_null_count": [
                    matches[field].notna().sum() for field in coverage_fields
                ],
                "coverage": [
                    matches[field].notna().mean() for field in coverage_fields
                ],
            }
        )
        coverage.to_csv(
            self.canonical_root / "event_metadata_coverage.csv",
            index=False,
        )
        enriched_path = self.canonical_root / "all_world_cup_matches_enriched.parquet"
        matches.to_parquet(enriched_path, index=False)
        return matches

    def build_coverage(self, registry, team_events):
        now = pd.Timestamp.now()
        summary = (
            team_events.groupby("registry_team_id", dropna=False)
            .agg(
                earliest_match=("match_date", "min"),
                latest_match=("match_date", "max"),
                event_count=("event_id", "nunique"),
                completed_match_count=(
                    "status_type",
                    lambda values: values.eq("finished").sum(),
                ),
                upcoming_match_count=(
                    "match_date",
                    lambda values: values.gt(now).sum(),
                ),
            )
            .reset_index()
        )
        coverage = registry[
            ["team_id", "team_name", "fifa_code", "world_cup_group"]
        ].merge(
            summary,
            left_on="team_id",
            right_on="registry_team_id",
            how="left",
        )
        coverage = coverage.drop(columns=["registry_team_id"])
        count_cols = [
            "event_count",
            "completed_match_count",
            "upcoming_match_count",
        ]
        coverage[count_cols] = coverage[count_cols].fillna(0).astype(int)
        coverage.to_csv(
            self.canonical_root / "event_ingestion_coverage.csv",
            index=False,
        )
        return coverage

    def write_run_log(self, status):
        self.metrics["status"] = status
        self.metrics["finished_at"] = datetime.now(timezone.utc).isoformat()
        path = self.run_log_root / f"pipeline_run_{self.run_id}.json"
        path.write_text(
            json.dumps(self.metrics, indent=2),
            encoding="utf-8",
        )
        latest = self.run_log_root / "pipeline_run_log.json"
        latest.write_text(
            json.dumps(self.metrics, indent=2),
            encoding="utf-8",
        )
        return latest

    def run(self, max_pages=None, max_details=None, skip_enrichment=False):
        status = "failed"
        try:
            registry = self.materialize_registry()
            events = self.fetch_team_events(registry, max_pages=max_pages)
            matches = (
                events.drop_duplicates("event_id")
                if skip_enrichment
                else self.enrich_matches(events, max_details=max_details)
            )
            self.build_coverage(registry, events)
            status = (
                "partial_success"
                if self.metrics["teams_failed"] or self.metrics["errors"]
                else "success"
            )
            return registry, events, matches
        finally:
            self.write_run_log(status)

    def run_enrichment_only(self, max_details=None):
        status = "failed"
        try:
            registry = self.materialize_registry()
            events_path = self.canonical_root / "all_world_cup_team_events.parquet"
            if not events_path.exists():
                raise FileNotFoundError("Run event discovery before enrichment")
            events = pd.read_parquet(events_path)
            matches = self.enrich_matches(
                events,
                max_details=max_details,
            )
            self.build_coverage(registry, events)
            status = "partial_success" if self.metrics["errors"] else "success"
            return registry, events, matches
        finally:
            self.write_run_log(status)
