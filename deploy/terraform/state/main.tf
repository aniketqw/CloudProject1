terraform {
  required_version = ">=1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.25.0"
    }
  }
}

variable "project_id" {
  type = string
}

variable "state_bucket" {
  type = string
}

variable "region" {
  type = string
}

provider "google" {
  project = var.project_id
}

resource "google_project_service" "storage" {
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_storage_bucket" "state" {
  name                        = var.state_bucket
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.storage]

  lifecycle {
    prevent_destroy = true
  }
}

output "bucket" {
  value = google_storage_bucket.state.name
}
