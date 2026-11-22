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
      zone             = var.zone
      subnetwork       = google_compute_subnetwork.subnet.id
      internal_ip_only = true
      service_account  = google_service_account.identities["flink"].email
      # Google always adds the last three to Dataproc clusters. Listing only cloud-platform made every later
      # plan read back a difference and try to replace the whole cluster.
      service_account_scopes = [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/cloud.useraccounts.readonly",
        "https://www.googleapis.com/auth/devstorage.read_write",
        "https://www.googleapis.com/auth/logging.write",
      ]
      tags = ["${var.prefix}-dataproc"]
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

    # With zero workers (the demo profile) Google stores no machine type or disk for this group.
    # Setting them anyway made every plan read back a difference that forces replacing the cluster.
    worker_config {
      num_instances = local.capacity.flink_workers
      machine_type  = local.capacity.flink_workers == 0 ? null : local.capacity.flink_machine

      dynamic "disk_config" {
        for_each = local.capacity.flink_workers == 0 ? [] : [1]
        content {
          boot_disk_size_gb = local.capacity.flink_disk_gb
          boot_disk_type    = "pd-standard"
        }
      }
    }

    software_config {
      image_version       = "3.0.4-debian13"
      optional_components = ["FLINK"]
      override_properties = {
        "dataproc:dataproc.logging.stackdriver.enable"                    = "true"
        "dataproc:dataproc.monitoring.stackdriver.enable"                 = "true"
        "dataproc:dataproc.logging.stackdriver.job.driver.enable"         = "true"
        "dataproc:dataproc.logging.stackdriver.job.yarn.container.enable" = "true"
        "dataproc:jobs.file-backed-output.enable"                         = "true"
        "dataproc:dataproc.allow.zero.workers"                            = local.capacity.flink_workers == 0 ? "true" : "false"
        "flink:jobmanager.memory.process.size"                            = "1024m"
        "flink:taskmanager.memory.process.size"                           = "2048m"
        "flink:taskmanager.numberOfTaskSlots"                             = "1"
        # Root cause of the failing job: the Dataproc Flink image already ships the Kafka connector, and the job jar bundles
        # its own copy, so the two class loaders disagreed (LinkageError: loader constraint violation). Parent first uses one copy.
        "flink:classloader.resolve-order"           = "parent-first"
        "yarn:yarn.nodemanager.resource.memory-mb"  = var.compute_profile == "demo" ? "4096" : "8192"
        "yarn:yarn.scheduler.maximum-allocation-mb" = var.compute_profile == "demo" ? "4096" : "8192"
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

# The Flink job id is derived from the release settings. Dataproc keeps finished jobs after a cluster is deleted, so a
# rebuild with identical settings reused the id of a dead job and the launcher refused to submit. This value changes
# whenever the cluster is created or replaced, so every cluster generation gets its own job id.
resource "random_id" "analytics_run" {
  byte_length = 4

  lifecycle {
    replace_triggered_by = [google_dataproc_cluster.flink]
  }
}
