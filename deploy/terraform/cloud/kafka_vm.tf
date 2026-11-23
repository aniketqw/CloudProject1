# Apache Kafka on Google Cloud: one KRaft broker in Docker on a Compute Engine VM inside the VPC. Applications on GKE and the
# Flink job on Dataproc reach it by its private address; clients log in with SASL/PLAIN over TLS, and the certificate is
# signed by the internal CA that also signs the gRPC certificate. The four topics are created by the VM's start-up script.
locals {
  kafka_topics = ["orders", "kitchen_status", "delivery_assignments", "restaurant_analytics_results"]
}

resource "random_password" "kafka_sasl" {
  length  = 32
  special = false
}

resource "google_compute_address" "kafka" {
  name         = "${var.prefix}-kafka-ip"
  region       = var.region
  subnetwork   = google_compute_subnetwork.subnet.id
  address_type = "INTERNAL"
}

resource "tls_private_key" "kafka_server" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}

resource "tls_cert_request" "kafka_server" {
  private_key_pem = tls_private_key.kafka_server.private_key_pem
  dns_names       = ["kafka", "${var.prefix}-kafka"]
  ip_addresses    = [google_compute_address.kafka.address]

  subject {
    common_name = "${var.prefix}-kafka"
  }
}

resource "tls_locally_signed_cert" "kafka_server" {
  cert_request_pem      = tls_cert_request.kafka_server.cert_request_pem
  ca_private_key_pem    = tls_private_key.grpc_ca.private_key_pem
  ca_cert_pem           = tls_self_signed_cert.grpc_ca.cert_pem
  validity_period_hours = 24 * 365
  allowed_uses          = ["digital_signature", "key_encipherment", "server_auth"]
}

resource "google_service_account" "kafka" {
  account_id   = "${var.prefix}-kafka"
  display_name = "Apache Kafka broker VM"
}

resource "google_project_iam_member" "kafka_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.kafka.email}"
}

resource "google_secret_manager_secret_iam_member" "kafka_broker" {
  secret_id = google_secret_manager_secret.config["kafka-broker"].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.kafka.email}"
}

resource "google_compute_firewall" "kafka" {
  name        = "${var.prefix}-kafka"
  network     = google_compute_network.vpc.id
  description = "Kafka clients: GKE nodes and pods, and the Dataproc VMs (same subnet)."

  allow {
    protocol = "tcp"
    ports    = ["9092"]
  }

  source_ranges = ["10.40.0.0/20", "10.44.0.0/16"]
  target_tags   = ["kafka"]
}

resource "google_compute_instance" "kafka" {
  name         = "${var.prefix}-kafka"
  machine_type = local.capacity.kafka_machine
  zone         = var.zone
  tags         = ["kafka"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 30
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id
    network_ip = google_compute_address.kafka.address
  }

  service_account {
    email  = google_service_account.kafka.email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = templatefile("${path.module}/kafka_startup.sh.tftpl", {
    ip            = google_compute_address.kafka.address
    broker_secret = google_secret_manager_secret.config["kafka-broker"].secret_id
    project       = var.project_id
    topics        = join(" ", local.kafka_topics)
    retention_ms  = var.kafka_retention_days * 86400000
  })

  # Kafka's PEM keystore needs a PKCS8 key (private_key_pem_pkcs8; the default ECDSA PEM is the older SEC1 format).
  # The start-up script only runs at boot, so a new broker secret replaces the VM (the data lives on its boot disk, and
  # the script creates the topics again).
  lifecycle {
    replace_triggered_by = [google_secret_manager_secret_version.config["kafka-broker"]]
  }

  allow_stopping_for_update = true

  depends_on = [
    google_secret_manager_secret_version.config,
    google_secret_manager_secret_iam_member.kafka_broker,
    google_compute_router_nat.nat,
  ]
}

output "kafka_bootstrap" {
  value = "${google_compute_address.kafka.address}:9092"
}
