variable "project_id" {
  description = "Your GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "US"
}

variable "gcs_bucket_name" {
  description = "Name of the GCS bucket for the data lake"
  type        = string
  default     = "solana-validator-data-lake"
}

variable "bq_dataset_id" {
  description = "BigQuery dataset ID for the warehouse"
  type        = string
  default     = "solana_validator_economics"
}