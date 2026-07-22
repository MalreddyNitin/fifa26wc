import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from world_cup_intelligence.inference import PredictionService
from world_cup_intelligence.prematch import PrematchLookupError

ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[2]))
app = FastAPI(title="World Cup Intelligence API", version="1.0.0")


class MatchRequest(BaseModel):
    home_team_id: str
    away_team_id: str


class SofaScoreLinkRequest(BaseModel):
    sofascore_url: str = Field(min_length=20, max_length=500)


class SimulationRequest(BaseModel):
    simulations: int = Field(default=50_000, ge=100, le=500_000)


@lru_cache
def service():
    return PredictionService(ROOT)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    try:
        instance = service()
        return {
            "status": "ready",
            "model_version": instance.metadata["dataset_version"],
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/teams")
def teams():
    frame = pd.read_parquet(ROOT / "data/canonical/dim_teams.parquet")
    return frame.to_dict("records")


@app.get("/teams/{team_id}/form")
def team_form_alias(team_id: str, matches: int = 5):
    return team_form(team_id, matches)


@app.post("/v1/predict-match")
def predict_match(request: MatchRequest):
    if request.home_team_id == request.away_team_id:
        raise HTTPException(422, "Teams must differ")
    try:
        return service().predict_match(request.home_team_id, request.away_team_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/v1/predict-sofascore-link")
def predict_sofascore_link(request: SofaScoreLinkRequest):
    try:
        return service().predict_sofascore_link(request.sofascore_url)
    except PrematchLookupError as exc:
        raise HTTPException(422, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/v1/predict-markets")
def predict_markets(request: MatchRequest):
    return predict_match(request)


@app.get("/matches/{event_id}/prediction")
def prediction_for_match(event_id: int):
    matches = pd.read_parquet(
        ROOT / "data/canonical/fct_matches.parquet",
        filters=[("event_id", "=", event_id)],
    )
    if matches.empty:
        raise HTTPException(404, f"Unknown event_id: {event_id}")
    match = matches.iloc[0]
    return service().predict_match(match["home_team_id"], match["away_team_id"])


@app.get("/matches/{event_id}/markets")
def markets_for_match(event_id: int):
    return prediction_for_match(event_id)


@app.get("/v1/team-form/{team_id}")
def team_form(team_id: str, matches: int = 5):
    try:
        return service().team_form(team_id, matches=max(1, min(matches, 20)))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/v1/simulate-tournament")
def simulate_tournament(request: SimulationRequest):
    # The production endpoint returns the last validated simulation artifact;
    # expensive regeneration is an orchestrated batch operation.
    path = ROOT / "data/predictions/tournament_probabilities.parquet"
    if not path.exists():
        raise HTTPException(503, "Tournament simulation is not materialized")
    frame = pd.read_parquet(path)
    return {
        "requested_simulations": request.simulations,
        "artifact_simulations": 50_000,
        "probabilities": frame.to_dict("records"),
    }


@app.post("/simulate/world-cup")
def simulate_tournament_alias(request: SimulationRequest):
    return simulate_tournament(request)


@app.get("/pipeline/status")
def pipeline_status():
    path = ROOT / "data/run_logs/pipeline_run_log.json"
    if not path.exists():
        raise HTTPException(503, "Pipeline run log is not materialized")
    import json

    return json.loads(path.read_text(encoding="utf-8"))
