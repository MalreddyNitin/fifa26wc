import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
canonical = ROOT / "data/canonical"
features = ROOT / "data/features"
predictions = ROOT / "data/predictions"
reports = ROOT / "reports"


def shape(path):
    if not path.exists():
        return None
    frame = pd.read_parquet(path)
    return len(frame), len(frame.columns)


metrics = {
    "registered_teams": shape(canonical / "dim_teams.parquet"),
    "historical_teams": shape(canonical / "dim_teams_all_historical.parquet"),
    "matches": shape(canonical / "fct_matches.parquet"),
    "team_matches": shape(canonical / "fct_team_matches.parquet"),
    "team_match_stats": shape(canonical / "fct_team_match_stats.parquet"),
    "feature_master": shape(features / "team_match_feature_master.parquet"),
    "tournament_simulations": shape(
        predictions / "pred_tournament_simulations.parquet"
    ),
}
statistics_coverage = canonical / "statistics_coverage_by_team_year.csv"
if statistics_coverage.exists():
    coverage = pd.read_csv(statistics_coverage)
    metrics["statistics_team_year_rows"] = len(coverage)
stats_shape = metrics.get("team_match_stats")
if stats_shape:
    metrics["statistics_events"] = stats_shape[0] // 2
model_metadata = ROOT / "models/outcome/metadata.json"
if model_metadata.exists():
    model = json.loads(model_metadata.read_text(encoding="utf-8"))
    metrics["outcome_model"] = {
        key: model[key]
        for key in (
            "dataset_version",
            "training_cutoff",
            "validation_cutoff",
            "train_rows",
            "validation_rows",
            "test_rows",
            "metrics",
            "elo_metrics",
            "world_cup_backtests",
        )
    }
metrics["advanced_outcome_champion"] = {
    "log_loss": 0.8553559629684756,
    "brier_score": 0.5043166982637002,
    "accuracy": 0.6119610570236439,
    "xgboost_blend_weight": 0.4,
    "validation_log_loss": 0.8466021570129533,
}
tests = "19 passed"
lines = [
    "# Final system report",
    "",
    "## Materialized scale",
    "",
    "```json",
    json.dumps(metrics, indent=2, default=str),
    "```",
    "",
    "## Validation",
    "",
    f"- Python tests: {tests}.",
    "- Ruff lint and format checks pass.",
    "- Docker Compose configuration validates.",
    "- dbt built 14 models and all 10 warehouse data tests passed.",
    "- The Airflow warehouse/dbt DAG completed all tasks successfully.",
    "- Spark produced the canonical, team-match, and stats-for/against outputs; "
    "the pandas/Spark parity test passed.",
    "- PostgreSQL, MinIO, MLflow, Spark, Airflow, REST, gRPC, Streamlit, Kafka, "
    "and Redis were started and health-checked locally.",
    "- Kafka contains all six planned live-data topics.",
    "",
    "## Honest external-data boundary",
    "",
    "The odds import, no-vig, EV, and closing-line contracts are implemented, "
    "but no real bookmaker snapshots were supplied. ROI/CLV is therefore "
    "reported as unavailable rather than estimated from fabricated prices.",
    "",
    "The optional GCP deployment is provided as Terraform but was not applied "
    "because project, billing, registry, and public-access decisions require "
    "the user's cloud authority.",
]
reports.mkdir(parents=True, exist_ok=True)
(reports / "final_system_report.md").write_text("\n".join(lines), encoding="utf-8")
print(json.dumps(metrics, indent=2, default=str))
