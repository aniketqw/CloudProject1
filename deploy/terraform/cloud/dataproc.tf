resource "google_dataproc_cluster" "flink" {
  name                          = "${var.prefix}-flink"
  region                        = var.region
  graceful_decommission_timeout = "120s"

  cluster_config {
    staging_bucket = google_storage_bucket.artifacts.name
    temp_bucket    = google_storage_bucket.checkpoints.name

    # Component Gateway: opens the Flink and YARN web UIs from the Cloud console
    # even though the cluster has no external IP.
    endpoint_config {
      enable_http_port_access = true
    }

    gce_cluster_config {
      zone                   = var.zone
      subnetwork             = google_compute_subnetwork.subnet.id
      internal_ip_only       = true
      service_account        = google_service_account.identities["flink"].email
      service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
      tags                   = ["${var.prefix}-dataproc"]
      metadata = {
        "enable-oslogin" = "TRUE"
      }
    }

    master_config {
      num_instances = 1
      machine_type  = local.capacity.flink_machine

      disk_config {
        boot_disk_size_gb = local.capacity.flink_disk_gb
        boot_disk_type    = "pd-standard"
      }
    }

    worker_config {
      num_instances = local.capacity.flink_workers
      machine_type  = local.capacity.flink_machine

      disk_config {
        boot_disk_size_gb = local.capacity.flink_disk_gb
        boot_disk_type    = "pd-standard"
      }
    }

    software_config {
      image_version       = "3.0.4-debian13"
      optional_components = ["FLINK"]
      override_properties = {
        "dataproc:dataproc.logging.stackdriver.enable"    = "true"
        "dataproc:dataproc.monitoring.stackdriver.enable" = "true"
        "dataproc:jobs.file-backed-output.enable"         = "true"
        "dataproc:dataproc.allow.zero.workers"            = local.capacity.flink_workers == 0 ? "true" : "false"
        "flink:jobmanager.memory.process.size"            = "1024m"
        "flink:taskmanager.memory.process.size"           = "2048m"
        "flink:taskmanager.numberOfTaskSlots"             = "1"
        "yarn:yarn.nodemanager.resource.memory-mb"        = var.compute_profile == "demo" ? "4096" : "8192"
        "yarn:yarn.scheduler.maximum-allocation-mb"       = var.compute_profile == "demo" ? "4096" : "8192"
      }
    }
  }

  depends_on = [
    google_project_iam_member.role_8,
    google_storage_bucket_iam_member.flink_state,
    google_storage_bucket_iam_member.flink_artifacts,
    google_compute_router_nat.nat,
    google_compute_firewall.dataproc_internal,
  ]
}
