variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "zone" {
  type = string
}

variable "prefix" {
  type = string
}

variable "kafka_bootstrap" {
  type    = string
  default = ""
}

variable "public_host" {
  type        = string
  default     = ""
  description = "Public web name. Empty means use <ip-with-dashes>.sslip.io, a free name that points at the reserved web address."
}

variable "paused" {
  type        = bool
  default     = false
  description = "true stops the billable compute that Terraform can stop: GKE nodes go to zero and Cloud SQL stops. Dataproc cannot be stopped by Terraform."
}

variable "dns_zone" {
  type    = string
  default = ""
}

variable "admin_cidr" {
  type = string
}

variable "kafka_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "kafka_api_secret" {
  type      = string
  default   = ""
  sensitive = true
}

variable "operator_user" {
  type = string
}

variable "operator_password_hash" {
  type      = string
  sensitive = true
}

variable "create_firestore" {
  type    = bool
  default = true
}

variable "compute_profile" {
  type    = string
  default = "demo"

  validation {
    condition     = contains(["demo", "standard"], var.compute_profile)
    error_message = "Select demo or explicitly opt in to standard capacity."
  }
}

# -- Kafka topics (formerly the separate kafka root)
variable "enable_kafka" {
  type        = bool
  default     = true
  description = "Create the Kafka topics. Set false until a Confluent cluster exists; the services that need Kafka will not work without it."
}

variable "kafka_cluster_id" {
  type    = string
  default = ""
}

variable "kafka_rest_endpoint" {
  type    = string
  default = ""
}

variable "kafka_admin_api_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Confluent topic-administrator key. Different from kafka_api_key, which the applications use."
}

variable "kafka_admin_api_secret" {
  type      = string
  default   = ""
  sensitive = true
}

variable "kafka_retention_days" {
  type    = number
  default = 21

  validation {
    condition     = var.kafka_retention_days >= 7 && var.kafka_retention_days <= 30 && floor(var.kafka_retention_days) == var.kafka_retention_days
    error_message = "Select 7 to 30 whole retention days and keep the pause within the safe margin."
  }
}

# -- GitOps (formerly the separate gitops root)
variable "git_repository" {
  type = string
}

variable "git_revision" {
  type = string
}

# -- Build artifacts
variable "build_artifacts" {
  type        = bool
  default     = true
  description = "Build and push the images and Flink jar during apply (needs Docker and gcloud on this machine). Set false when they were published already."
}

# -- Monitoring
variable "alert_notification_channels" {
  type        = list(string)
  default     = []
  description = "Existing Cloud Monitoring notification channel IDs to notify. Empty keeps alerts visible in the console only."
}

variable "admin_cidrs" {
  type        = list(string)
  default     = []
  description = "Extra addresses (x.x.x.x/32) allowed to reach the cluster API besides admin_cidr, for example a second network."
}

variable "alert_email" {
  type        = string
  default     = ""
  description = "Address that receives the alert emails. Empty creates no email channel."
}

# -- Teardown
variable "deletion_protection" {
  type        = bool
  default     = true
  description = "Keeps the GKE cluster and the Cloud SQL instance from being deleted. To tear the platform down: apply once with this set to false, then run terraform destroy."
}

variable "force_destroy_buckets" {
  type        = bool
  default     = false
  description = "Lets terraform destroy delete the receipts, checkpoints and artifacts buckets even when they hold files. Leave false normally; set true (and apply once) before tearing down."
}

variable "firestore_delete_on_destroy" {
  type        = bool
  default     = false
  description = "By default terraform destroy leaves the Firestore database in place (ABANDON), which makes the next apply fail with 'already exists'. Set true (and apply once) before tearing down."
}
