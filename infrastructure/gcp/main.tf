terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_storage_bucket" "lake" {
  name                        = "${var.project_id}-world-cup-lake"
  location                    = var.region
  uniform_bucket_level_access = true
  versioning { enabled = true }
  lifecycle_rule {
    condition { age = 90 }
    action { type = "SetStorageClass"; storage_class = "NEARLINE" }
  }
}

resource "google_bigquery_dataset" "warehouse" {
  dataset_id = "world_cup_intelligence"
  location   = var.region
}

resource "google_service_account" "runtime" {
  account_id   = "world-cup-runtime"
  display_name = "World Cup runtime"
}

resource "google_storage_bucket_iam_member" "runtime_lake" {
  bucket = google_storage_bucket.lake.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name     = "world-cup-api"
  location = var.region
  template {
    service_account = google_service_account.runtime.email
    containers {
      image = var.api_image
      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
  }
}

resource "google_cloud_run_v2_service" "dashboard" {
  name     = "world-cup-dashboard"
  location = var.region
  template {
    service_account = google_service_account.runtime.email
    containers {
      image = var.dashboard_image
      env {
        name  = "API_BASE_URL"
        value = google_cloud_run_v2_service.api.uri
      }
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
  }
}

resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account
  display_name    = "World Cup monthly budget"
  amount {
    specified_amount {
      currency_code = "USD"
      units         = var.monthly_budget_usd
    }
  }
  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 0.9 }
  threshold_rules { threshold_percent = 1.0 }
}
