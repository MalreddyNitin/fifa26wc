\connect worldcup
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS features;
CREATE SCHEMA IF NOT EXISTS predictions;
CREATE TABLE IF NOT EXISTS raw.load_audit (
  load_id text PRIMARY KEY,
  dataset_name text NOT NULL,
  started_at timestamptz NOT NULL,
  finished_at timestamptz,
  row_count bigint,
  status text NOT NULL,
  error_message text
);
