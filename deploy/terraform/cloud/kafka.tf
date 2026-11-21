# Topics in an EXISTING Confluent cluster (the cluster and API keys are created outside Terraform).
resource "confluent_kafka_topic" "application" {
  for_each         = toset(["orders", "kitchen_status", "delivery_assignments", "restaurant_analytics_results"])
  topic_name       = each.value
  partitions_count = 3

  config = {
    "retention.ms" = tostring(var.kafka_retention_days * 86400000)
  }

  lifecycle {
    prevent_destroy = true
  }
}
