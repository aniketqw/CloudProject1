resource "google_storage_bucket" "receipts" {
  name                        = "${var.project_id}-${var.prefix}-receipts"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy_buckets

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket" "checkpoints" {
  name                        = "${var.project_id}-${var.prefix}-checkpoints"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy_buckets

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket" "artifacts" {
  name                        = "${var.project_id}-${var.prefix}-artifacts"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy_buckets

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "notify_read" {
  bucket = google_storage_bucket.receipts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.identities["notify"].email}"
}

resource "google_storage_bucket_iam_member" "function_write" {
  bucket = google_storage_bucket.receipts.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.identities["function"].email}"
}

resource "google_storage_bucket_iam_member" "function_read" {
  bucket = google_storage_bucket.receipts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.identities["function"].email}"
}

resource "google_storage_bucket_iam_member" "flink_state" {
  bucket = google_storage_bucket.checkpoints.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.identities["flink"].email}"
}

resource "google_storage_bucket_iam_member" "flink_artifacts" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.identities["flink"].email}"
}

resource "google_storage_bucket_iam_member" "build_source" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.identities["build"].email}"
}

resource "google_storage_bucket_iam_member" "launcher_control" {
  bucket = google_storage_bucket.checkpoints.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.identities["launcher"].email}"

  condition {
    title      = "ReadAnalyticsControlOnly"
    expression = "resource.name == \"projects/_/buckets/${google_storage_bucket.checkpoints.name}/objects/lifecycle/analytics.json\""
  }
}
