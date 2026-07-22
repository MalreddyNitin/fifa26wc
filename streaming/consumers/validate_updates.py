import json
import os

from confluent_kafka import Consumer, Producer
from jsonschema import Draft202012Validator


def load_validator():
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / ("schemas/match_update.schema.json")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


def main():
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": "match-update-validator-v1",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    producer = Producer({"bootstrap.servers": bootstrap})
    validator = load_validator()
    consumer.subscribe(["raw-match-updates"])
    seen = set()
    while True:
        message = consumer.poll(1)
        if message is None:
            continue
        try:
            payload = json.loads(message.value())
            validator.validate(payload)
            if payload["message_id"] not in seen:
                producer.produce(
                    "validated-match-updates",
                    key=payload["message_id"],
                    value=message.value(),
                )
                seen.add(payload["message_id"])
            consumer.commit(message)
        except Exception as exc:
            producer.produce(
                "pipeline-errors",
                key=message.key(),
                value=json.dumps({"error": repr(exc), "raw": message.value().decode()}),
            )
            consumer.commit(message)
        producer.poll(0)


if __name__ == "__main__":
    main()
