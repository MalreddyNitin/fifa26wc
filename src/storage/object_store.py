from pathlib import Path

import pandas as pd


class ObjectStore:
    """S3-compatible logical layout backed by files in local demo mode."""

    def __init__(self, local_root="data/lake"):
        self.local_root = Path(local_root)

    def write_parquet(self, frame, layer, dataset, partitions=None):
        directory = self.local_root / layer / dataset
        for key, value in (partitions or {}).items():
            directory /= f"{key}={value}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "part-00000.parquet"
        frame.to_parquet(path, index=False)
        return path

    def read_parquet(self, layer, dataset):
        return pd.read_parquet(self.local_root / layer / dataset)
