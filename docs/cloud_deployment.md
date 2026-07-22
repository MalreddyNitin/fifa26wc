# Optional GCP deployment

The selected cloud architecture uses Cloud Storage for the lake, BigQuery for
warehouse marts, Cloud Run for API/dashboard containers, and a dedicated
least-privilege service account. Terraform also enforces bucket versioning,
service scaling limits, and a monthly billing budget.

```powershell
cd infrastructure/gcp
terraform init
terraform plan -var project_id=... -var billing_account=... `
  -var api_image=... -var dashboard_image=...
terraform apply
```

Cloud credentials, billing account selection, DNS/public access policy, and
the actual production apply are intentionally user-controlled external
actions. Secrets belong in Secret Manager and are referenced at deployment;
they are never placed in Terraform variables or repository files.
