resource "google_pubsub_topic" "dispatch" {
  name                       = "${var.prefix}-notification-dispatch"
  message_retention_duration = "86400s"
  depends_on                 = [google_project_service.apis]
}

resource "google_pubsub_topic_iam_member" "publish" {
  topic  = google_pubsub_topic.dispatch.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.identities["notify"].email}"
}

resource "google_artifact_registry_repository" "app" {
  repository_id = "${var.prefix}-app"
  location      = var.region
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

resource "google_artifact_registry_repository" "functions" {
  repository_id = "${var.prefix}-functions"
  location      = var.region
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

resource "google_artifact_registry_repository_iam_member" "function_build" {
  repository = google_artifact_registry_repository.functions.name
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.identities["build"].email}"
}

resource "google_storage_bucket_object" "function" {
  name   = format("function-%s.zip", data.archive_file.function.output_sha256)
  bucket = google_storage_bucket.artifacts.name
  source = data.archive_file.function.output_path
}

resource "google_cloudfunctions2_function" "notification" {
  name     = "${var.prefix}-notification-transport"
  location = var.region

  build_config {
    runtime           = "python312"
    entry_point       = "deliver_notification"
    service_account   = google_service_account.identities["build"].name
    docker_repository = google_artifact_registry_repository.functions.id

    source {
      storage_source {
        bucket = google_storage_bucket.artifacts.name
        object = google_storage_bucket_object.function.name
      }
    }
  }

  service_config {
    available_memory      = "256M"
    available_cpu         = "1"
    min_instance_count    = 0
    max_instance_count    = 3
    timeout_seconds       = 30
    ingress_settings      = "ALLOW_INTERNAL_ONLY"
    service_account_email = google_service_account.identities["function"].email

    environment_variables = {
      APP_ENV                      = "cloud"
      CLOUD_DEPLOYMENT_ACK         = "assignment-private-network-v1"
      PROJECT_ID                   = var.project_id
      NOTIFICATION_RECEIPTS_BUCKET = google_storage_bucket.receipts.name
    }
  }

  depends_on = [
    google_project_iam_member.role_11,
    google_storage_bucket_iam_member.function_write,
    google_storage_bucket_iam_member.function_read,
    google_artifact_registry_repository_iam_member.function_build,
    google_service_account_iam_member.pubsub_token,
    google_project_iam_member.build_function_sources,
  ]
}

resource "google_cloud_run_service_iam_member" "function_invoke" {
  location = var.region
  service  = google_cloudfunctions2_function.notification.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.identities["trigger"].email}"
}

resource "google_eventarc_trigger" "notification" {
  name     = "${var.prefix}-notification-dispatch"
  location = var.region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.pubsub.topic.v1.messagePublished"
  }

  transport {
    pubsub {
      topic = google_pubsub_topic.dispatch.id
    }
  }

  destination {
    cloud_run_service {
      service = google_cloudfunctions2_function.notification.name
      region  = var.region
    }
  }

  service_account = google_service_account.identities["trigger"].email

  depends_on = [
    google_cloud_run_service_iam_member.function_invoke,
    google_project_iam_member.role_11,
  ]
}
