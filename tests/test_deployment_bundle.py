from pathlib import Path

import pytest

from world_cup_intelligence.inference import PredictionService

ROOT = Path(__file__).resolve().parents[1]


def test_compact_deployment_bundle_predicts_without_full_lake():
    service = PredictionService(ROOT, artifact_root=ROOT / "deployment")
    prediction = service.predict_match(
        "canada",
        "mexico",
        context={
            "event_id": 99999999,
            "kickoff_utc": "2026-06-01T18:00:00+00:00",
            "competition_type": "world_cup",
            "round_name": "Group A",
            "neutral_site": 1,
        },
    )

    assert prediction["model_version"]
    assert prediction["home_team_id"] == "canada"
    assert prediction["away_team_id"] == "mexico"
    probability_sum = sum(prediction[key] for key in ("home_win", "draw", "away_win"))
    assert probability_sum == pytest.approx(1)
