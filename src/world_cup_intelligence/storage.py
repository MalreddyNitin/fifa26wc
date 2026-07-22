import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def payload_hash(payload):
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class RawJsonStore:
    def __init__(self, root):
        self.root = Path(root)

    def write(
        self,
        payload,
        category,
        partitions,
        request_url,
        endpoint,
        http_status,
        pipeline_run_id,
        fetched_at=None,
    ):
        fetched_at = fetched_at or datetime.now(timezone.utc)
        digest = payload_hash(payload)
        directory = self.root / "sofascore" / category
        for key, value in partitions.items():
            directory /= f"{key}={value}"
        directory /= f"fetch_date={fetched_at.date().isoformat()}"
        directory.mkdir(parents=True, exist_ok=True)

        payload_path = directory / f"{digest}.json"
        metadata_path = directory / f"{digest}.meta.json"
        if not payload_path.exists():
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
        if not metadata_path.exists():
            metadata = {
                "request_url": request_url,
                "endpoint": endpoint,
                "fetch_timestamp": fetched_at.isoformat(),
                "http_status": http_status,
                "payload_hash": digest,
                "pipeline_run_id": pipeline_run_id,
            }
            metadata_path.write_text(
                json.dumps(metadata, indent=2),
                encoding="utf-8",
            )
        return payload_path, digest


class CheckpointStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def load(self, name):
        path = self.root / f"{name}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, name, data):
        path = self.root / f"{name}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(path)
