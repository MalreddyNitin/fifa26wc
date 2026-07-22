# Kafka topics

| Topic | Key | Purpose |
|---|---|---|
| `raw-match-updates` | message ID | replayable source envelopes |
| `raw-odds-updates` | snapshot ID | timestamped market snapshots |
| `validated-match-updates` | message ID | schema-valid deduplicated events |
| `live-features` | event ID | watermark-aware feature snapshots |
| `live-predictions` | event ID | latest in-game probabilities |
| `pipeline-errors` | source key | dead-letter records |

Schemas include a `schema_version`. Consumers commit offsets only after publish,
use stable message IDs for idempotency, and retain raw JSONL replay files.
Consumer lag is exposed through Kafka group offsets.
