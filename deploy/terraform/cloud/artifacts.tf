# Everything the deployment needs that is built from this repository, produced by apply itself.
locals {
  repo_root = "${path.module}/../../.."
  app_image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.prefix}-app/app:${local.image_tag}"
  jar_name  = "restaurant-analytics-${local.image_tag}.jar"

  # Rebuild only when a source file changes (build outputs, state and git data are skipped).
  source_hash = sha1(join(",", [
    for f in sort(fileset(local.repo_root, "**/*.{py,proto,html,css,js,txt,json,xml,java,yaml}")) :
    "${f}:${filesha1("${local.repo_root}/${f}")}"
    if !startswith(f, ".local-build") && !startswith(f, ".git/") && !contains(split("/", f), ".terraform") && !startswith(f, "tests/") && !startswith(f, "logs/")
  ]))
  analytics_hash = sha1(join(",", [
    for f in sort(fileset("${local.repo_root}/restaurant_service/analytics", "**")) :
    "${f}:${filesha1("${local.repo_root}/restaurant_service/analytics/${f}")}"
  ]))
}

# --- Cloud Function source: zipped by Terraform, uploaded in messaging.tf
data "archive_file" "function" {
  type        = "zip"
  output_path = "${local.repo_root}/.local-build/artifacts/notification-function.zip"

  source {
    content  = file("${local.repo_root}/functions/notification_transport/main.py")
    filename = "main.py"
  }

  source {
    content  = file("${local.repo_root}/functions/notification_transport/requirements.txt")
    filename = "requirements.txt"
  }
}

# --- Application image: built from Dockerfile.local and pushed to Artifact Registry
resource "docker_image" "app" {
  count = var.build_artifacts ? 1 : 0
  name  = local.app_image

  build {
    context    = abspath(local.repo_root)
    dockerfile = abspath("${local.repo_root}/Dockerfile.local")
    builder    = "default"     # buildx: the provider's classic builder fails with a 403 on Docker Desktop
    platform   = "linux/amd64" # GKE nodes are Intel; an ARM image built on an Apple-silicon Mac would not start
  }

  triggers = {
    source = local.source_hash
  }
}

resource "docker_registry_image" "app" {
  count         = var.build_artifacts ? 1 : 0
  name          = docker_image.app[0].name
  keep_remotely = true

  depends_on = [google_artifact_registry_repository.app]
}

# --- Flink job jar: built inside the analytics image, then copied out and uploaded
resource "docker_image" "analytics" {
  count = var.build_artifacts ? 1 : 0
  name  = "food-restaurant-analytics:${local.image_tag}"

  build {
    context    = abspath("${local.repo_root}/restaurant_service/analytics")
    dockerfile = abspath("${local.repo_root}/restaurant_service/analytics/Dockerfile")
    builder    = "default"
    platform   = "linux/amd64"
  }

  triggers = {
    source = local.analytics_hash
  }
}

# Terraform cannot copy a file out of an image, so this is the one scripted step. It runs
# inside apply, only when the analytics source changes, and needs Docker and gcloud.
resource "terraform_data" "flink_jar" {
  count            = var.build_artifacts ? 1 : 0
  triggers_replace = [local.analytics_hash, local.image_tag, google_storage_bucket.artifacts.name]

  provisioner "local-exec" {
    interpreter = ["bash", "-ec"]
    command     = <<-EOT
      jar="$(mktemp -d)/${local.jar_name}"
      cid="$(docker create ${docker_image.analytics[0].name})"
      trap 'docker rm -f "$cid" >/dev/null' EXIT
      docker cp "$cid:/opt/flink/usrlib/restaurant-analytics.jar" "$jar"
      # Use the same credentials Terraform uses (application default); the interactive gcloud login can expire mid-apply.
      export CLOUDSDK_AUTH_ACCESS_TOKEN="$(gcloud auth application-default print-access-token)"
      gcloud storage cp "$jar" "gs://${google_storage_bucket.artifacts.name}/${local.jar_name}" --project "${var.project_id}"
    EOT
  }

  depends_on = [google_storage_bucket_iam_member.flink_artifacts]
}
