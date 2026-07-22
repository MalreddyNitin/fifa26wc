import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .models.scoreline import market_probabilities, score_matrix
from .prematch import (
    PrematchLookupError,
    event_from_payload,
    fetch_sofascore_event,
    fetched_at_utc,
    parse_sofascore_event_id,
)


class PredictionService:
    def __init__(self, root):
        self.root = Path(root)
        outcome_path = self.root / "models/outcome/logistic_baseline.joblib"
        scoreline_path = self.root / "models/scoreline/dixon_coles.joblib"
        if not outcome_path.exists() or not scoreline_path.exists():
            raise FileNotFoundError(
                "Model artifacts are missing; run scripts/train_models.py"
            )
        self.outcome = joblib.load(outcome_path)
        self.scoreline = joblib.load(scoreline_path)
        self.master = pd.read_parquet(
            self.root / "data/features/team_match_feature_master.parquet"
        )
        self.teams = pd.read_parquet(self.root / "data/canonical/dim_teams.parquet")
        self.source_team_ids = {
            int(row.sofascore_team_id): row
            for row in self.teams.itertuples(index=False)
        }
        metadata_path = self.root / "models/outcome/metadata.json"
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    def _latest(self, team_id, before_kickoff=None, exclude_event_id=None):
        rows = self.master.loc[self.master["team_id"].eq(team_id)]
        if before_kickoff is not None and pd.notna(before_kickoff):
            kickoff = pd.to_datetime(before_kickoff, utc=True)
            rows = rows.loc[pd.to_datetime(rows["kickoff_utc"], utc=True).lt(kickoff)]
        if exclude_event_id is not None:
            rows = rows.loc[rows["event_id"].ne(exclude_event_id)]
        if rows.empty:
            raise KeyError(f"No pre-match history is available for team: {team_id}")
        return rows.sort_values("kickoff_utc").iloc[-1]

    def _fixture_congestion(self, team_id, kickoff_utc):
        if kickoff_utc is None or pd.isna(kickoff_utc):
            return None
        kickoff = pd.to_datetime(kickoff_utc, utc=True)
        dates = pd.to_datetime(
            self.master.loc[self.master["team_id"].eq(team_id), "kickoff_utc"],
            utc=True,
        )
        return int(
            dates.ge(kickoff - pd.Timedelta(days=14)).mul(dates.lt(kickoff)).sum()
        )

    def fixture_features(self, home_team_id, away_team_id, context=None):
        context = context or {}
        kickoff = context.get("kickoff_utc")
        event_id = context.get("event_id")
        home = self._latest(home_team_id, kickoff, event_id)
        away = self._latest(away_team_id, kickoff, event_id)
        columns = set(self.outcome["features"] + self.scoreline["features"])
        row = {}
        for column in columns:
            if column == "elo_difference":
                row[column] = home.get("elo_post", home.get("elo_pre", 1500)) - (
                    away.get("elo_post", away.get("elo_pre", 1500))
                )
            elif column == "ranking_difference":
                home_rank = context.get(
                    "home_displayed_ranking", home.get("team_displayed_ranking", np.nan)
                )
                away_rank = context.get(
                    "away_displayed_ranking", away.get("team_displayed_ranking", np.nan)
                )
                home_rank = np.nan if home_rank is None else home_rank
                away_rank = np.nan if away_rank is None else away_rank
                row[column] = home_rank - away_rank
            elif column == "neutral_site":
                neutral = context.get("neutral_site", 1)
                row[column] = np.nan if neutral is None else neutral
            elif column == "competition_type":
                row[column] = context.get("competition_type", "world_cup")
            elif column == "round_name":
                row[column] = context.get("round_name", "fixture")
            elif column == "rest_days" and kickoff is not None:
                row[column] = max(
                    0.0,
                    (
                        pd.to_datetime(kickoff, utc=True)
                        - pd.to_datetime(home["kickoff_utc"], utc=True)
                    ).total_seconds()
                    / 86_400,
                )
            elif column == "fixture_congestion_14d" and kickoff is not None:
                row[column] = self._fixture_congestion(home_team_id, kickoff)
            elif column == "confederation_matchup":
                row[column] = (
                    f"{home.get('team_confederation', 'UNK')}_vs_"
                    f"{away.get('team_confederation', 'UNK')}"
                )
            elif column.startswith("opponent_"):
                source = column.removeprefix("opponent_")
                row[column] = away.get(source, np.nan)
            else:
                row[column] = home.get(column, np.nan)
        return pd.DataFrame([row])

    def predict_match(self, home_team_id, away_team_id, context=None):
        features = self.fixture_features(home_team_id, away_team_id, context=context)
        probabilities = self.outcome["model"].predict_proba(
            features[self.outcome["features"]]
        )[0]
        result = {
            f"probability_{label}": float(probability)
            for label, probability in zip(self.outcome["classes"], probabilities)
        }
        home_xg = float(
            np.clip(
                self.scoreline["models"]["home"].predict(
                    features[self.scoreline["features"]]
                )[0],
                0.05,
                6,
            )
        )
        away_xg = float(
            np.clip(
                self.scoreline["models"]["away"].predict(
                    features[self.scoreline["features"]]
                )[0],
                0.05,
                6,
            )
        )
        markets = market_probabilities(score_matrix(home_xg, away_xg))
        prediction = {
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "home_expected_goals": home_xg,
            "away_expected_goals": away_xg,
            **result,
            **markets,
            "model_version": self.metadata["dataset_version"],
        }
        if context:
            prediction["prematch_context"] = {
                key: value
                for key, value in context.items()
                if key
                in {
                    "event_id",
                    "kickoff_utc",
                    "tournament_name",
                    "competition_type",
                    "round_name",
                    "venue_name",
                    "venue_city",
                    "venue_country",
                    "neutral_site",
                }
            }
        return prediction

    def predict_sofascore_link(self, sofascore_url):
        event_id = parse_sofascore_event_id(sofascore_url)
        payload = fetch_sofascore_event(event_id)
        event_data = payload.get("event", payload)
        home_source_id = event_data.get("homeTeam", {}).get("id")
        away_source_id = event_data.get("awayTeam", {}).get("id")
        home_team = self.source_team_ids.get(int(home_source_id or -1))
        away_team = self.source_team_ids.get(int(away_source_id or -1))
        unsupported = []
        if home_team is None:
            unsupported.append(
                event_data.get("homeTeam", {}).get("name", home_source_id)
            )
        if away_team is None:
            unsupported.append(
                event_data.get("awayTeam", {}).get("name", away_source_id)
            )
        if unsupported:
            raise PrematchLookupError(
                "The model has no trained team history for: "
                + ", ".join(map(str, unsupported))
            )
        event = event_from_payload(
            event_id,
            payload,
            home_country=getattr(home_team, "country_name", home_team.team_name),
            away_country=getattr(away_team, "country_name", away_team.team_name),
        )
        context = event.as_dict()
        context["fetched_at_utc"] = fetched_at_utc()
        prediction = self.predict_match(
            home_team.team_id,
            away_team.team_id,
            context=context,
        )
        prediction["sofascore_url"] = str(sofascore_url)
        prediction["source"] = "SofaScore public event metadata"
        return prediction

    def team_form(self, team_id, matches=5):
        rows = (
            self.master.loc[self.master["team_id"].eq(team_id)]
            .sort_values("kickoff_utc")
            .tail(matches)
        )
        if rows.empty:
            raise KeyError(f"Unknown team: {team_id}")
        columns = [
            "event_id",
            "kickoff_utc",
            "team_id",
            "opponent_id",
            "goals_for",
            "goals_against",
            "result",
            "elo_pre",
            "elo_post",
        ]
        return rows[[c for c in columns if c in rows]].to_dict("records")
