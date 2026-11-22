resource "google_container_cluster" "gke" {
  name                     = "${var.prefix}-gke"
  location                 = var.zone
  network                  = google_compute_network.vpc.id
  subnetwork               = google_compute_subnetwork.subnet.id
  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = var.deletion_protection

  release_channel {
    channel = "REGULAR"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = var.admin_cidr
      display_name = "team-deployer"
    }

    dynamic "cidr_blocks" {
      for_each = var.admin_cidrs
      content {
        cidr_block   = cidr_blocks.value
        display_name = "extra-admin"
      }
    }
  }

  network_policy {
    enabled  = true
    provider = "CALICO"
  }

  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
  }

  addons_config {
    network_policy_config {
      disabled = false
    }
  }

  depends_on = [google_compute_router_nat.nat]
}

resource "google_container_node_pool" "apps" {
  name               = "apps"
  location           = var.zone
  cluster            = google_container_cluster.gke.name
  initial_node_count = local.capacity.gke_nodes
  node_count         = var.paused ? 0 : null # paused: no nodes, so no node charges

  dynamic "autoscaling" {
    for_each = var.paused ? [] : [1]
    content {
      min_node_count = local.capacity.gke_nodes
      max_node_count = local.capacity.gke_max_nodes
    }
  }

  node_config {
    machine_type    = local.capacity.gke_machine
    disk_size_gb    = local.capacity.gke_disk_gb
    service_account = google_service_account.identities["node"].email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    disk_type       = "pd-standard"

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  lifecycle {
    ignore_changes = [initial_node_count]
  }
}
