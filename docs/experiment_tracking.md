# Experiment tracking

Training hashes the source Parquet bytes and ordered feature schema into a
dataset version. Each run records the chronological cutoff, row counts,
features, seed, parameters, metrics, and artifacts under `mlruns/`. When
`MLFLOW_TRACKING_URI` is configured, the same metadata is mirrored to MLflow.

Experiments use names such as `outcome-baselines`, `scoreline`, `shots`, and
`corners`. Registered artifacts must include preprocessing, ordered feature
names, target/class names, dataset version, and held-out metrics.
