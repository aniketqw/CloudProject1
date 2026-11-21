resource "google_compute_network" "vpc" {
  name                    = "${var.prefix}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "subnet" {
  name                     = "${var.prefix}-subnet"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = "10.40.0.0/20"
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.44.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.45.0.0/20"
  }
}

resource "google_compute_router" "router" {
  name    = "${var.prefix}-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.prefix}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

resource "google_compute_global_address" "private" {
  name          = "${var.prefix}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_compute_global_address" "web" {
  name       = "${var.prefix}-web-ip"
  depends_on = [google_project_service.apis]
}

resource "google_service_networking_connection" "private" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private.name]
}

resource "google_dns_record_set" "web" {
  count        = var.dns_zone == "" ? 0 : 1
  managed_zone = var.dns_zone
  name         = "${local.public_host}."
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.web.address]
}

resource "google_compute_firewall" "dataproc_internal" {
  name        = "${var.prefix}-dataproc-internal"
  network     = google_compute_network.vpc.id
  source_tags = ["${var.prefix}-dataproc"]
  target_tags = ["${var.prefix}-dataproc"]

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }
}

resource "google_compute_firewall" "dataproc_iap" {
  name          = "${var.prefix}-dataproc-iap"
  network       = google_compute_network.vpc.id
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["${var.prefix}-dataproc"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}
