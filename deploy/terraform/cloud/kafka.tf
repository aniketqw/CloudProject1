# Topics in an EXISTING Confluent cluster (the cluster and API keys are created outside Terraform).
resource "confluent_kafka_topic" "application" {
  for_each         = var.enable_kafka ? toset(["orders", "kitchen_status", "delivery_assignments", "restaurant_analytics_results"]) : toset([])
  topic_name       = each.value
  partitions_count = 3

  config = {
    "retention.ms" = tostring(var.kafka_retention_days * 86400000)
  }

  lifecycle {
    precondition {
      condition     = var.kafka_cluster_id != "" && var.kafka_rest_endpoint != "" && var.kafka_admin_api_key != ""
      error_message = "enable_kafka is true but the Confluent cluster id, REST endpoint and admin API key are not set."
    }
  }
}
