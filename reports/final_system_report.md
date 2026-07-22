# Final system report

## Materialized scale

```json
{
  "registered_teams": [
    48,
    13
  ],
  "historical_teams": [
    246,
    8
  ],
  "matches": [
    9709,
    53
  ],
  "team_matches": [
    19418,
    34
  ],
  "team_match_stats": [
    9866,
    282
  ],
  "feature_master": [
    19166,
    1984
  ],
  "tournament_simulations": [
    50000,
    2
  ],
  "statistics_team_year_rows": 1279,
  "statistics_events": 4933,
  "outcome_model": {
    "dataset_version": "6ddd46b8fcbeb020",
    "training_cutoff": "2021-01-12 16:30:00+00:00",
    "validation_cutoff": "2023-11-16 17:00:00+00:00",
    "train_rows": 6708,
    "validation_rows": 1437,
    "test_rows": 1438,
    "metrics": {
      "log_loss": 0.8618966046721029,
      "brier_score": 0.5079161961906685,
      "accuracy": 0.6084840055632823
    },
    "elo_metrics": {
      "log_loss": 0.8975805560900164,
      "brier_score": 0.5235924897191802,
      "accuracy": 0.5980528511821975
    },
    "world_cup_backtests": {
      "2014": {
        "log_loss": 1.0763781167120021,
        "brier_score": 0.6177789446574393,
        "accuracy": 0.532258064516129,
        "matches": 62
      },
      "2018": {
        "log_loss": 1.0173415839230047,
        "brier_score": 0.6110383807087407,
        "accuracy": 0.5081967213114754,
        "matches": 61
      },
      "2022": {
        "log_loss": 1.0521370848430938,
        "brier_score": 0.6121574408674963,
        "accuracy": 0.49206349206349204,
        "matches": 63
      }
    }
  },
  "advanced_outcome_champion": {
    "log_loss": 0.8553559629684756,
    "brier_score": 0.5043166982637002,
    "accuracy": 0.6119610570236439,
    "xgboost_blend_weight": 0.4,
    "validation_log_loss": 0.8466021570129533
  }
}
```

## Validation

- Python tests: 19 passed.
- Ruff lint and format checks pass.
- Docker Compose configuration validates.
- dbt built 14 models and all 10 warehouse data tests passed.
- The Airflow warehouse/dbt DAG completed all tasks successfully.
- Spark produced the canonical, team-match, and stats-for/against outputs; the pandas/Spark parity test passed.
- PostgreSQL, MinIO, MLflow, Spark, Airflow, REST, gRPC, Streamlit, Kafka, and Redis were started and health-checked locally.
- Kafka contains all six planned live-data topics.

## Honest external-data boundary

The odds import, no-vig, EV, and closing-line contracts are implemented, but no real bookmaker snapshots were supplied. ROI/CLV is therefore reported as unavailable rather than estimated from fabricated prices.

The optional GCP deployment is provided as Terraform but was not applied because project, billing, registry, and public-access decisions require the user's cloud authority.