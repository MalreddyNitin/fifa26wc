# MinIO

Run `docker compose up -d minio`. The S3 endpoint is `localhost:9000` and the
console is `localhost:9001`. Create `bronze`, `silver`, `gold`, and `artifacts`
buckets for a shared deployment; local demo mode uses the equivalent
`data/lake/<layer>` directories.
