output "data_lake_bucket" {
  description = "GCS bucket name for the data lake"
  value       = google_storage_bucket.data_lake.name
}

output "warehouse_dataset_id" {
  description = "BigQuery warehouse dataset ID"
  value       = google_bigquery_dataset.warehouse.dataset_id
}

output "staging_dataset_id" {
  description = "BigQuery staging dataset ID"
  value       = google_bigquery_dataset.staging.dataset_id
}

output "project_id" {
  description = "GCP project ID"
  value       = var.project_id
}