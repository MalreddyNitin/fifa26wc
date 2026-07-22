# Warehouse architecture

The reproducible local target is PostgreSQL 16, organized into `raw`,
`staging`, `analytics`, `features`, and `predictions` schemas. This keeps the
portfolio runnable without cloud credentials. The Parquet contracts and dbt
models are portable to BigQuery or Snowflake by changing the adapter and
quoting rules. Loads are audited and keyed by dataset; fact models use
`event_id` (and `side` where applicable) as their incremental grain.
