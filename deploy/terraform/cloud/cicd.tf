# Optional build-on-push: GitHub Actions builds the image and pushes it to Artifact Registry with no key file.
# Off by default (github_repository = ""). WRITTEN AND VALIDATED ONLY; not proven (needs write access to the tracked repository).
variable "github_repository" {
  type        = string
  default     = ""
  description = "owner/name of the repository whose workflow may push images. Empty disables build-on-push."
}

# A deleted workload identity pool keeps its id reserved for 30 days, so a fixed id made every rebuild fail with
# "already exists". A random suffix gives each deployment its own pool.
resource "random_id" "ci_pool" {
  count       = var.github_repository == "" ? 0 : 1
  byte_length = 3
}

resource "google_iam_workload_identity_pool" "github" {
  count                     = var.github_repository == "" ? 0 : 1
  workload_identity_pool_id = "${var.prefix}-github-${random_id.ci_pool[0].hex}"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count                              = var.github_repository == "" ? 0 : 1
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "github"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "ci" {
  count        = var.github_repository == "" ? 0 : 1
  account_id   = "${var.prefix}-ci"
  display_name = "Image builds from GitHub Actions (push only)"
}

resource "google_artifact_registry_repository_iam_member" "ci_push" {
  count      = var.github_repository == "" ? 0 : 1
  location   = google_artifact_registry_repository.app.location
  repository = google_artifact_registry_repository.app.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.ci[0].email}"
}

resource "google_service_account_iam_member" "ci_federation" {
  count              = var.github_repository == "" ? 0 : 1
  service_account_id = google_service_account.ci[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.github_repository}"
}

output "ci_workload_identity_provider" {
  value = var.github_repository == "" ? "" : google_iam_workload_identity_pool_provider.github[0].name
}

output "ci_service_account" {
  value = var.github_repository == "" ? "" : google_service_account.ci[0].email
}
