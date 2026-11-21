# Argo CD plus the two Applications it runs. Terraform creates the Applications directly and passes
# the facts about this project (project ID, buckets, service accounts, secret versions) inline, so
# nothing project-specific is committed to Git. Git holds the charts and the image tag only:
# changing deploy/environments/team/image.yaml and pushing is how an application update rolls out.
locals {
  # One source of truth for the release: Terraform builds this tag, and Argo CD deploys it from Git.
  image_tag = yamldecode(file("${local.repo_root}/deploy/environments/team/image.yaml")).imageTag

  chart_values = jsondecode(file("${local.repo_root}/deploy/charts/food/values.yaml"))
  demo         = var.compute_profile == "demo"

  small_resources = { requests = { cpu = "25m", memory = "128Mi" }, limits = { cpu = "500m", memory = "512Mi" } }
  http_resources  = { requests = { cpu = "50m", memory = "128Mi" }, limits = { cpu = "1000m", memory = "512Mi" } }
  sync_resources  = { requests = { cpu = "50m", memory = "192Mi" }, limits = { cpu = "500m", memory = "512Mi" } }

  # The demo profile shrinks the workloads so everything fits on two small nodes.
  demo_workloads = merge(
    { for name, w in local.chart_values.workloads : name => { resources = local.small_resources } if local.demo && !can(w.factory) && !can(w.port) },
    { for name in ["customer-service", "order-service"] : name => { resources = local.http_resources } if local.demo },
    { for name in ["kitchen-sync"] : name => { resources = local.sync_resources } if local.demo },
  )
  demo_pool_env = { for k, v in { DB_POOL_SIZE = "2", DB_MAX_OVERFLOW = "0", DB_POOL_TIMEOUT = "10" } : k => v if local.demo }

  # Overrides only: Argo CD merges these over deploy/charts/food/values.yaml.
  food_values = {
    projectId          = var.project_id
    clusterName        = google_container_cluster.gke.name
    clusterLocation    = var.zone
    imageRepository    = "${var.region}-docker.pkg.dev/${var.project_id}/${var.prefix}-app/app"
    host               = local.public_host
    publicOrigin       = "https://${local.public_host}"
    cloudSqlConnection = google_sql_database_instance.database.connection_name
    computeProfile     = var.compute_profile
    resources          = local.capacity.resources
    sqlProxyResources  = local.capacity.sql_proxy_resources

    env = merge(local.demo_pool_env, {
      KAFKA_RETENTION_DAYS         = tostring(var.kafka_retention_days)
      DEPLOYMENT_ZONE              = var.zone
      CLOUD_LIFECYCLE_PROTOCOL     = "1"
      PROJECT_ID                   = var.project_id
      KAFKA_BOOTSTRAP_SERVERS      = var.kafka_bootstrap
      NOTIFICATION_RECEIPTS_BUCKET = google_storage_bucket.receipts.name
      NOTIFICATION_DISPATCH_TOPIC  = google_pubsub_topic.dispatch.name
    })

    serviceAccounts = {
      for key, account in { sql = "sql", firestore = "firestore", combined = "combined", notification = "notify", eso = "secrets", launcher = "launcher" } :
      key => google_service_account.identities[account].email
    }

    managedFlink = {
      env = {
        REGION                   = var.region
        DATAPROC_CLUSTER         = google_dataproc_cluster.flink.name
        KAFKA_SECRET_VERSION     = "projects/${var.project_id}/secrets/${google_secret_manager_secret.config["kafka"].secret_id}/versions/${google_secret_manager_secret_version.config["kafka"].version}"
        ANALYTICS_CHECKPOINT_URI = "gs://${google_storage_bucket.checkpoints.name}/flink"
        ANALYTICS_JAR_URI        = "gs://${google_storage_bucket.artifacts.name}/${local.jar_name}"
        ANALYTICS_CONTROL_URI    = "gs://${google_storage_bucket.checkpoints.name}/lifecycle/analytics.json"
        ANALYTICS_RELEASE        = local.image_tag
      }
    }

    # A placeholder (.invalid) host can never get a Google-managed certificate, and the sync would wait for it forever.
    ingress = { enabled = !endswith(local.public_host, ".invalid"), ipName = google_compute_global_address.web.name }

    secrets = {
      db    = google_secret_manager_secret.config["db-password"].secret_id
      kafka = google_secret_manager_secret.config["kafka"].secret_id
      web   = google_secret_manager_secret.config["web-access"].secret_id
      versions = {
        db    = google_secret_manager_secret_version.config["db-password"].version
        kafka = google_secret_manager_secret_version.config["kafka"].version
        web   = google_secret_manager_secret_version.config["web-access"].version
      }
    }

    hpa       = { for k, v in { max = 4 } : k => v if local.demo }
    workloads = local.demo_workloads
  }

  sync_policy = {
    automated   = { prune = true, selfHeal = true }
    syncOptions = ["CreateNamespace=true", "ServerSideApply=true"]
  }
}

module "argocd" {
  source = "../modules/argocd"

  applications = {
    "food-platform" = {
      additionalAnnotations = { "argocd.argoproj.io/sync-wave" = "0" }
      source                = { repoURL = var.git_repository, targetRevision = var.git_revision, path = "deploy/charts/platform" }
      destination           = { server = "https://kubernetes.default.svc", namespace = "platform" }
      syncPolicy            = local.sync_policy
    }
    "food" = {
      additionalAnnotations = { "argocd.argoproj.io/sync-wave" = "10" }
      source = {
        repoURL        = var.git_repository
        targetRevision = var.git_revision
        path           = "deploy/charts/food"
        helm = {
          valueFiles   = ["../../environments/team/image.yaml"]
          valuesObject = local.food_values
        }
      }
      destination = { server = "https://kubernetes.default.svc", namespace = "food" }
      syncPolicy  = local.sync_policy
    }
  }

  depends_on = [google_container_node_pool.apps]
}
