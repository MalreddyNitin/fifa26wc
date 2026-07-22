import json
import math
import os
from datetime import datetime, timezone


def live_probabilities(home_score, away_score, minute):
    remaining = max(0, 90 - minute)
    difference = home_score - away_score
    home = 1 / (1 + math.exp(-(difference * 1.35 + remaining / 180)))
    draw = math.exp(-abs(difference) * 1.4) * (remaining / 90) * 0.32
    away = max(0, 1 - home - draw)
    total = home + draw + away
    return {
        "home_win": home / total,
        "draw": draw / total,
        "away_win": away / total,
    }


def main():
    from confluent_kafka import Consumer, Producer
    from redis import Redis

    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": "live-inference-v1",
            "auto.offset.reset": "latest",
        }
    )
    producer = Producer({"bootstrap.servers": bootstrap})
    store = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))
    consumer.subscribe(["live-features"])
    while True:
        message = consumer.poll(1)
        if message is None:
            continue
        feature = json.loads(message.value())
        prediction = {
            **feature,
            **live_probabilities(
                feature.get("home_score", 0),
                feature.get("away_score", 0),
                feature.get("minute", 0),
            ),
            "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        encoded = json.dumps(prediction)
        store.set(f"live:{feature['event_id']}", encoded)
        producer.produce(
            "live-predictions",
            key=str(feature["event_id"]),
            value=encoded,
        )
        producer.poll(0)


if __name__ == "__main__":
    main()
