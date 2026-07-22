# Data lake layout

- `data/raw` / `bronze`: immutable SofaScore JSON and request metadata, keyed by
  endpoint and source identifier.
- `data/canonical` / `silver`: typed, deduplicated Parquet facts and dimensions.
- `data/features` / `gold`: leakage-safe feature marts.
- `models`, `mlruns`, and `reports` / `artifacts`: versioned model outputs.

Every raw object has a SHA-256 payload hash, fetch timestamp, endpoint, HTTP
status, and pipeline run ID. Writes are content-addressed and idempotent. Raw
history should be retained; derived partitions can be rebuilt from it.
