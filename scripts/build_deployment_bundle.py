import json
import shutil
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "deployment"

MODEL_FILES = (
    "models/outcome/logistic_baseline.joblib",
    "models/outcome/metadata.json",
    "models/scoreline/dixon_coles.joblib",
)

OPTIONAL_DATA_FILES = (
    "data/predictions/tournament_probabilities.parquet",
    "data/predictions/pred_scoreline_samples.parquet",
    "data/canonical/fct_odds_snapshots.parquet",
    "data/features/feature_coverage_report.csv",
    "data/run_logs/pipeline_run_log.json",
)

DISPLAY_COLUMNS = {
    "event_id",
    "kickoff_utc",
    "team_id",
    "opponent",
    "opponent_id",
    "goals_for",
    "goals_against",
    "result",
    "elo_pre",
    "elo_post",
    "team_confederation",
    "team_displayed_ranking",
}

COMPUTED_FEATURES = {
    "competition_type",
    "round_name",
    "neutral_site",
    "elo_difference",
    "ranking_difference",
    "rest_days",
    "fixture_congestion_14d",
    "confederation_matchup",
}


def copy_file(relative_path):
    source = ROOT / relative_path
    if not source.exists():
        return False
    destination = DESTINATION / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def required_master_columns():
    outcome = joblib.load(ROOT / MODEL_FILES[0])
    scoreline = joblib.load(ROOT / MODEL_FILES[2])
    features = set(outcome["features"]) | set(scoreline["features"])
    source_features = {
        feature.removeprefix("opponent_")
        if feature.startswith("opponent_")
        else feature
        for feature in features - COMPUTED_FEATURES
    }
    return DISPLAY_COLUMNS | source_features


def build():
    for relative_path in MODEL_FILES:
        if not copy_file(relative_path):
            raise FileNotFoundError(
                f"Missing {relative_path}; run scripts/train_models.py first"
            )

    source_master = ROOT / "data/features/team_match_feature_master.parquet"
    master = pd.read_parquet(source_master)
    columns = sorted(required_master_columns() & set(master.columns))
    compact_master = master.loc[:, columns]
    master_destination = DESTINATION / "data/features/team_match_feature_master.parquet"
    master_destination.parent.mkdir(parents=True, exist_ok=True)
    compact_master.to_parquet(master_destination, index=False, compression="zstd")

    copy_file("data/canonical/dim_teams.parquet")
    matches = pd.read_parquet(
        ROOT / "data/canonical/fct_matches.parquet", columns=["event_id"]
    )
    matches_destination = DESTINATION / "data/canonical/fct_matches.parquet"
    matches_destination.parent.mkdir(parents=True, exist_ok=True)
    matches.to_parquet(matches_destination, index=False, compression="zstd")

    copied_optional = [path for path in OPTIONAL_DATA_FILES if copy_file(path)]
    metadata = json.loads((ROOT / MODEL_FILES[1]).read_text(encoding="utf-8"))
    manifest = {
        "dataset_version": metadata["dataset_version"],
        "master_rows": len(compact_master),
        "master_columns": len(compact_master.columns),
        "model_files": list(MODEL_FILES),
        "optional_data_files": copied_optional,
    }
    (DESTINATION / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    build()
