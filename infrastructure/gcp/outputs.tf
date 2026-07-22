output "api_url" { value = google_cloud_run_v2_service.api.uri }
output "dashboard_url" { value = google_cloud_run_v2_service.dashboard.uri }
output "lake_bucket" { value = google_storage_bucket.lake.name }
