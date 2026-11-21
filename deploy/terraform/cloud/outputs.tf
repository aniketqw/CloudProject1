output "cluster_name" {
  value = google_container_cluster.gke.name
}

output "cluster_zone" {
  value = var.zone
}

output "sql_connection" {
  value = google_sql_database_instance.database.connection_name
}

output "public_ip" {
  value = google_compute_global_address.web.address
}

output "receipts_bucket" {
  value = google_storage_bucket.receipts.name
}

output "artifacts_bucket" {
  value = google_storage_bucket.artifacts.name
}

output "checkpoints_bucket" {
  value = google_storage_bucket.checkpoints.name
}

output "dataproc_cluster" {
  value = google_dataproc_cluster.flink.name
}

output "kafka_secret_version" {
  value = google_secret_manager_secret_version.config["kafka"].name
}

output "secret_versions" {
  value = { for name, secret in google_secret_manager_secret_version.config : name => secret.version }
}

output "image_tag" {
  value       = local.image_tag
  description = "Release tag read from deploy/environments/team/image.yaml."

  precondition {
    condition     = !contains(["latest", "dev", "local"], lower(local.image_tag))
    error_message = "Use an immutable release image tag in deploy/environments/team/image.yaml."
  }
}
