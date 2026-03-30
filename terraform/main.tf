terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_storage_bucket" "data_lake" {
  name          = "${var.gcs_bucket_name}-${var.project_id}"
  location      = "us-central1"
  storage_class = "STANDARD"
  force_destroy = true

  lifecycle_rule {
    condition {
      age = 180
    }
    action {
      type = "Delete"
    }
  }

  uniform_bucket_level_access = true
}

resource "google_bigquery_dataset" "warehouse" {
  dataset_id    = var.bq_dataset_id
  friendly_name = "Solana Validator Economics"
  description   = "Warehouse for Solana validator reward and profitability data."
  location      = "us-central1"

  default_table_expiration_ms = 7776000000

  labels = {
    project = "solana-validator-economics"
  }
}

resource "google_bigquery_dataset" "staging" {
  dataset_id    = "${var.bq_dataset_id}_staging"
  friendly_name = "Solana Staging"
  description   = "Raw ingested data from the Solana public BigQuery dataset."
  location      = "us-central1"

  default_table_expiration_ms = 7776000000

  labels = {
    project = "solana-validator-economics"
  }
}