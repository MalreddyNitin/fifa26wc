# Cloud smoke test

Status: not run. The optional Terraform deployment requires a user-selected
GCP project, billing account, container registry, and public-access policy.
Local container configuration is validated independently. After deployment,
verify `/health`, `/ready`, a scheduled incremental ingestion, BigQuery row
reconciliation, bucket least-privilege access, and active billing thresholds.
