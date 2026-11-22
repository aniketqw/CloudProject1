# Optional: create the Confluent Kafka cluster, service accounts, keys and permissions in Terraform too.
# Off by default (create_confluent = false). Needs a Confluent Cloud management API key, which only the account owner can create.
# WRITTEN AND VALIDATED ONLY; never applied (no management key was available).
variable "create_confluent" {
  type        = bool
  default     = false
  description = "true creates the Confluent environment, a Basic cluster, two service accounts, their keys and the permissions."
}

variable "confluent_cloud_api_key" {
  type    = string
  default = ""
}

variable "confluent_cloud_api_secret" {
  type      = string
  default   = ""
  sensitive = true
}

variable "confluent_cloud" {
  type        = string
  default     = "GCP"
  description = "Cloud of the new Basic cluster. Check Confluent's region list for the nearest region to the deployment."
}

variable "confluent_region" {
  type        = string
  default     = "asia-south1"
  description = "Region of the new Basic cluster. Not verified against Confluent's current list."
}

resource "confluent_environment" "food" {
  count        = var.create_confluent ? 1 : 0
  display_name = "${var.prefix}-env"

  stream_governance {
    package = "ESSENTIALS"
  }
}

resource "confluent_kafka_cluster" "food" {
  count        = var.create_confluent ? 1 : 0
  display_name = "${var.prefix}-kafka"
  availability = "SINGLE_ZONE"
  cloud        = var.confluent_cloud
  region       = var.confluent_region
  basic {}

  environment {
    id = confluent_environment.food[0].id
  }
}

resource "confluent_service_account" "app" {
  count        = var.create_confluent ? 1 : 0
  display_name = "${var.prefix}-app"
  description  = "Used by the applications to read and write the four topics."
}

resource "confluent_service_account" "admin" {
  count        = var.create_confluent ? 1 : 0
  display_name = "${var.prefix}-topic-admin"
  description  = "Used by Terraform to create topics."
}

resource "confluent_role_binding" "admin" {
  count       = var.create_confluent ? 1 : 0
  principal   = "User:${confluent_service_account.admin[0].id}"
  role_name   = "CloudClusterAdmin"
  crn_pattern = confluent_kafka_cluster.food[0].rbac_crn
}

resource "confluent_role_binding" "app_read" {
  count       = var.create_confluent ? 1 : 0
  principal   = "User:${confluent_service_account.app[0].id}"
  role_name   = "DeveloperRead"
  crn_pattern = "${confluent_kafka_cluster.food[0].rbac_crn}/kafka=${confluent_kafka_cluster.food[0].id}/topic=*"
}

resource "confluent_role_binding" "app_write" {
  count       = var.create_confluent ? 1 : 0
  principal   = "User:${confluent_service_account.app[0].id}"
  role_name   = "DeveloperWrite"
  crn_pattern = "${confluent_kafka_cluster.food[0].rbac_crn}/kafka=${confluent_kafka_cluster.food[0].id}/topic=*"
}

resource "confluent_role_binding" "app_groups" {
  count       = var.create_confluent ? 1 : 0
  principal   = "User:${confluent_service_account.app[0].id}"
  role_name   = "DeveloperRead"
  crn_pattern = "${confluent_kafka_cluster.food[0].rbac_crn}/kafka=${confluent_kafka_cluster.food[0].id}/group=*"
}

resource "confluent_api_key" "app" {
  count        = var.create_confluent ? 1 : 0
  display_name = "${var.prefix}-app-key"

  owner {
    id          = confluent_service_account.app[0].id
    api_version = confluent_service_account.app[0].api_version
    kind        = confluent_service_account.app[0].kind
  }

  managed_resource {
    id          = confluent_kafka_cluster.food[0].id
    api_version = confluent_kafka_cluster.food[0].api_version
    kind        = confluent_kafka_cluster.food[0].kind

    environment {
      id = confluent_environment.food[0].id
    }
  }
}

resource "confluent_api_key" "admin" {
  count        = var.create_confluent ? 1 : 0
  display_name = "${var.prefix}-admin-key"

  owner {
    id          = confluent_service_account.admin[0].id
    api_version = confluent_service_account.admin[0].api_version
    kind        = confluent_service_account.admin[0].kind
  }

  managed_resource {
    id          = confluent_kafka_cluster.food[0].id
    api_version = confluent_kafka_cluster.food[0].api_version
    kind        = confluent_kafka_cluster.food[0].kind

    environment {
      id = confluent_environment.food[0].id
    }
  }

  depends_on = [confluent_role_binding.admin]
}

# Next step once a management key exists: point var.kafka_cluster_id, var.kafka_rest_endpoint, var.kafka_bootstrap and the
# four key variables at these resources (a second apply), so no Kafka value is typed into .env any more.
