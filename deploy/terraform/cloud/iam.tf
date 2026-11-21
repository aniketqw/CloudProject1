resource "google_service_account" "identities" {
  for_each   = toset(["node", "sql", "firestore", "combined", "notify", "secrets", "flink", "function", "trigger", "build", "launcher"])
  account_id = "${var.prefix}-${each.value}"
  depends_on = [google_project_service.apis]
}

resource "google_project_iam_custom_role" "launcher" {
  role_id     = "${replace(var.prefix, "-", "_")}DataprocLauncher"
  title       = "Food Dataproc job launcher"
  permissions = ["dataproc.jobs.create", "dataproc.jobs.get", "dataproc.jobs.list", "dataproc.clusters.use"]
}

resource "google_project_iam_member" "role_0" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.identities["node"].email}"
}

resource "google_project_iam_member" "role_1" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.identities["node"].email}"
}

resource "google_project_iam_member" "role_2" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.identities["node"].email}"
}

resource "google_project_iam_member" "role_3" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.identities["sql"].email}"
}

resource "google_project_iam_member" "role_4" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.identities["combined"].email}"
}

resource "google_project_iam_member" "role_5" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.identities["notify"].email}"
}

resource "google_project_iam_member" "role_6" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.identities["firestore"].email}"
}

resource "google_project_iam_member" "role_7" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.identities["combined"].email}"
}

resource "google_project_iam_member" "role_8" {
  project = var.project_id
  role    = "roles/dataproc.worker"
  member  = "serviceAccount:${google_service_account.identities["flink"].email}"
}

resource "google_project_iam_member" "role_9" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.identities["flink"].email}"
}

resource "google_project_iam_member" "role_10" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.identities["flink"].email}"
}

resource "google_project_iam_member" "role_11" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.identities["trigger"].email}"
}

resource "google_project_iam_member" "role_12" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.identities["build"].email}"
}

resource "google_project_iam_member" "launcher" {
  project = var.project_id
  role    = google_project_iam_custom_role.launcher.name
  member  = "serviceAccount:${google_service_account.identities["launcher"].email}"
}

resource "google_service_account_iam_member" "wif_sql" {
  service_account_id = google_service_account.identities["sql"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[food/food-sql]"
}

resource "google_service_account_iam_member" "wif_firestore" {
  service_account_id = google_service_account.identities["firestore"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[food/food-firestore]"
}

resource "google_service_account_iam_member" "wif_combined" {
  service_account_id = google_service_account.identities["combined"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[food/food-combined]"
}

resource "google_service_account_iam_member" "wif_notification" {
  service_account_id = google_service_account.identities["notify"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[food/food-notification]"
}

resource "google_service_account_iam_member" "wif_eso" {
  service_account_id = google_service_account.identities["secrets"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[food/food-eso]"
}

resource "google_service_account_iam_member" "pubsub_token" {
  service_account_id = google_service_account.identities["trigger"].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
  depends_on         = [google_pubsub_topic.dispatch]
}

resource "google_service_account_iam_member" "wif_launcher" {
  service_account_id = google_service_account.identities["launcher"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[food/food-launcher]"
}

resource "google_service_account_iam_member" "launcher_actas" {
  service_account_id = google_service_account.identities["flink"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.identities["launcher"].email}"
}
