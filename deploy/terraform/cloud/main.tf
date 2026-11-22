locals {
  secret_values = {
    "db-password"  = random_password.database.result
    "zk-auth"      = "food:${random_password.zookeeper.result}"
    "argocd-admin" = random_password.argocd_admin.result
    "grpc-tls"     = jsonencode({ ca = tls_self_signed_cert.grpc_ca.cert_pem, cert = tls_locally_signed_cert.grpc_server.cert_pem, key = tls_private_key.grpc_server.private_key_pem })
    "kafka"        = jsonencode({ api_key = var.kafka_api_key, api_secret = var.kafka_api_secret })
    "web-access"   = jsonencode({ username = var.operator_user, password_hash = var.operator_password_hash })
  }
  profiles = jsondecode(file("${path.module}/../../profiles.json"))
  capacity = local.profiles[var.compute_profile]

  # A real, free HTTPS name when none is given: sslip.io answers with the IP written in the name.
  public_host = var.public_host != "" ? var.public_host : "${replace(google_compute_global_address.web.address, ".", "-")}.sslip.io"
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
    "iap.googleapis.com", "oslogin.googleapis.com", "containerscanning.googleapis.com", "billingbudgets.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ----------------------------------------------- providers for Kafka and GitOps
# All four settings are given together or not at all; with enable_kafka = false the provider stays unconfigured.
provider "confluent" {
  cloud_api_key       = var.confluent_cloud_api_key != "" ? var.confluent_cloud_api_key : null
  cloud_api_secret    = var.confluent_cloud_api_secret != "" ? var.confluent_cloud_api_secret : null
  kafka_id            = var.enable_kafka ? var.kafka_cluster_id : null
  kafka_rest_endpoint = var.enable_kafka ? var.kafka_rest_endpoint : null
  kafka_api_key       = var.enable_kafka ? var.kafka_admin_api_key : null
  kafka_api_secret    = var.enable_kafka ? var.kafka_admin_api_secret : null
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
  # Only talk to Docker when images are really being built.
  disable_docker_daemon_check = !var.build_artifacts

  registry_auth {
    address  = "${var.region}-docker.pkg.dev"
    username = "oauth2accesstoken"
    password = data.google_client_config.default.access_token
  }
}
