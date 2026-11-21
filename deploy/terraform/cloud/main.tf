locals {
  secret_values = {
    "db-password" = random_password.database.result
    "kafka"       = jsonencode({ api_key = var.kafka_api_key, api_secret = var.kafka_api_secret })
    "web-access"  = jsonencode({ username = var.operator_user, password_hash = var.operator_password_hash })
  }
  profiles = jsondecode(file("${path.module}/../../profiles.json"))
  capacity = local.profiles[var.compute_profile]
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com", "container.googleapis.com", "sqladmin.googleapis.com",
    "servicenetworking.googleapis.com", "firestore.googleapis.com", "storage.googleapis.com",
    "pubsub.googleapis.com", "cloudfunctions.googleapis.com", "run.googleapis.com",
    "eventarc.googleapis.com", "cloudbuild.googleapis.com", "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com", "dataproc.googleapis.com", "logging.googleapis.com",
    "monitoring.googleapis.com", "iamcredentials.googleapis.com", "dns.googleapis.com",
    "iap.googleapis.com", "oslogin.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ----------------------------------------------- providers for Kafka and GitOps
provider "confluent" {
  kafka_id            = var.kafka_cluster_id
  kafka_rest_endpoint = var.kafka_rest_endpoint
  kafka_api_key       = var.kafka_admin_api_key
  kafka_api_secret    = var.kafka_admin_api_secret
}

data "google_client_config" "default" {}

# Built from the cluster created in this same apply, so no kubeconfig file or
# separate stage is needed.
provider "helm" {
  kubernetes = {
    host                   = "https://${google_container_cluster.gke.endpoint}"
    token                  = data.google_client_config.default.access_token
    cluster_ca_certificate = base64decode(google_container_cluster.gke.master_auth[0].cluster_ca_certificate)
  }
}

# Authenticates the docker provider to Artifact Registry with the same Google credentials.
provider "docker" {
  registry_auth {
    address  = "${var.region}-docker.pkg.dev"
    username = "oauth2accesstoken"
    password = data.google_client_config.default.access_token
  }
}
