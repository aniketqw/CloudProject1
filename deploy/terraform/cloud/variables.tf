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
  type = string
}

variable "public_host" {
  type = string
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
  sensitive = true
}

variable "kafka_api_secret" {
  type      = string
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
variable "kafka_cluster_id" {
  type = string
}

variable "kafka_rest_endpoint" {
  type = string
}

variable "kafka_admin_api_key" {
  type        = string
  sensitive   = true
  description = "Confluent topic-administrator key. Different from kafka_api_key, which the applications use."
}

variable "kafka_admin_api_secret" {
  type      = string
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
