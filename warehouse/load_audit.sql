SELECT load_id, dataset_name, started_at, finished_at, row_count, status,
       error_message
FROM raw.load_audit
ORDER BY started_at DESC;
