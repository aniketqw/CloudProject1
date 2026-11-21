resource "google_secret_manager_secret" "config" {
  for_each  = toset(["db-password", "kafka", "web-access"])
  secret_id = "${var.prefix}-${each.value}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "config" {
  for_each    = google_secret_manager_secret.config
  secret      = each.value.id
  secret_data = local.secret_values[each.key]
}

resource "google_secret_manager_secret_iam_member" "eso" {
  for_each  = google_secret_manager_secret.config
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.identities["secrets"].email}"
}

resource "google_secret_manager_secret_iam_member" "flink" {
  secret_id = google_secret_manager_secret.config["kafka"].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.identities["flink"].email}"
}
