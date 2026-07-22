# Streaming latency

The optional local-live profile is started with
`docker compose --profile live up -d`. End-to-end latency is measured from the
source `observed_at` timestamp to `prediction_timestamp`; stale UI state is
flagged after 60 seconds. Production measurements require a selected live
event and are not fabricated in the batch report.
