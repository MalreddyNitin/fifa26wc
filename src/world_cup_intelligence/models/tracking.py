import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def dataset_version(paths, feature_names=None):
    digest = hashlib.sha256()
    for path in sorted(map(Path, paths), key=str):
        digest.update(path.name.encode())
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    for name in feature_names or []:
        digest.update(str(name).encode())
    return digest.hexdigest()[:16]


class LocalRun:
    def __init__(self, root, experiment, parameters):
        self.run_id = str(uuid.uuid4())
        self.directory = Path(root) / experiment / self.run_id
        self.directory.mkdir(parents=True, exist_ok=True)
        self.record = {
            "run_id": self.run_id,
            "experiment": experiment,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "parameters": parameters,
            "metrics": {},
            "artifacts": [],
        }
        self.mlflow_run_id = None

    def log_metrics(self, **metrics):
        self.record["metrics"].update(
            {key: float(value) for key, value in metrics.items() if value is not None}
        )

    def log_artifact(self, path):
        self.record["artifacts"].append(str(Path(path).resolve()))

    def close(self):
        self.record["finished_at"] = datetime.now(timezone.utc).isoformat()
        (self.directory / "run.json").write_text(
            json.dumps(self.record, indent=2, default=str),
            encoding="utf-8",
        )


@contextmanager
def tracked_run(root, experiment, parameters):
    """Track locally and mirror to MLflow when a tracking server is configured."""
    root = Path(root)
    run = LocalRun(root / "local_runs", experiment, parameters)
    mlflow_run = None
    try:
        import mlflow

        uri = os.getenv("MLFLOW_TRACKING_URI")
        if not uri:
            tracking_root = root / "tracking"
            tracking_root.mkdir(parents=True, exist_ok=True)
            uri = tracking_root.resolve().as_uri()
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(experiment)
        mlflow_run = mlflow.start_run(run_name=run.run_id)
        run.mlflow_run_id = mlflow_run.info.run_id
        mlflow.log_params(parameters)
    except Exception:
        mlflow_run = None
    try:
        yield run
    finally:
        if mlflow_run is not None:
            import mlflow

            mlflow.log_metrics(run.record["metrics"])
            for artifact in run.record["artifacts"]:
                path = Path(artifact)
                if path.exists():
                    mlflow.log_artifact(path)
            mlflow.end_run()
        run.close()
