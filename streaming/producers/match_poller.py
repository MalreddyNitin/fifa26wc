import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import requests


def envelope(event_id, payload, observed_at=None):
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return {
        "schema_version": "1.0",
        "message_id": f"{event_id}:{digest}",
        "event_id": int(event_id),
        "observed_at": observed_at,
        "payload": payload,
    }


def main():
    from confluent_kafka import Producer

    event_ids = [int(value) for value in os.environ["LIVE_EVENT_IDS"].split(",")]
    interval = float(os.getenv("POLL_INTERVAL_SECONDS", "15"))
    producer = Producer(
        {"bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")}
    )
    replay = Path(os.getenv("REPLAY_PATH", "data/streaming/replay.jsonl"))
    replay.parent.mkdir(parents=True, exist_ok=True)
    while True:
        for event_id in event_ids:
            response = requests.get(
                f"https://www.sofascore.com/api/v1/event/{event_id}",
                impersonate="chrome",
                timeout=20,
            )
            response.raise_for_status()
            message = envelope(event_id, response.json())
            encoded = json.dumps(message)
            with replay.open("a", encoding="utf-8") as stream:
                stream.write(encoded + "\n")
            producer.produce(
                "raw-match-updates",
                key=message["message_id"],
                value=encoded,
            )
        producer.flush()
        time.sleep(interval)


if __name__ == "__main__":
    main()
