# Google Cloud Monitoring: alerts and a dashboard for the managed services.
# (The in-cluster Prometheus and Grafana stack is installed by Argo CD from deploy/charts/platform.)

resource "google_monitoring_alert_policy" "sql_cpu" {
  display_name          = "${var.prefix}: Cloud SQL CPU above 80%"
  combiner              = "OR"
  notification_channels = var.alert_notification_channels

  conditions {
    display_name = "Cloud SQL CPU utilization"

    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${var.project_id}:${google_sql_database_instance.database.name}\" AND metric.type = \"cloudsql.googleapis.com/database/cpu/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "gke_node_cpu" {
  display_name          = "${var.prefix}: GKE node CPU above 85%"
  combiner              = "OR"
  notification_channels = var.alert_notification_channels

  conditions {
    display_name = "GKE node CPU allocatable utilization"

    condition_threshold {
      filter          = "resource.type = \"k8s_node\" AND resource.labels.cluster_name = \"${google_container_cluster.gke.name}\" AND metric.type = \"kubernetes.io/node/cpu/allocatable_utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.85
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "notification_function_errors" {
  display_name          = "${var.prefix}: notification function returning errors"
  combiner              = "OR"
  notification_channels = var.alert_notification_channels

  conditions {
    display_name = "Cloud Run 5xx responses for the notification function"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"${google_cloudfunctions2_function.notification.name}\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_dashboard" "platform" {
  dashboard_json = jsonencode({
    displayName = "${var.prefix} platform"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Cloud SQL CPU utilization"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type = \"cloudsql_database\" AND metric.type = \"cloudsql.googleapis.com/database/cpu/utilization\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN" }
                  }
                }
              }]
            }
          }
        },
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "GKE node CPU allocatable utilization"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type = \"k8s_node\" AND resource.labels.cluster_name = \"${google_container_cluster.gke.name}\" AND metric.type = \"kubernetes.io/node/cpu/allocatable_utilization\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN" }
                  }
                }
              }]
            }
          }
        },
        {
          yPos   = 4
          width  = 12
          height = 4
          widget = {
            title = "Notification function requests by response class"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"${google_cloudfunctions2_function.notification.name}\" AND metric.type = \"run.googleapis.com/request_count\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE", groupByFields = ["metric.label.response_code_class"], crossSeriesReducer = "REDUCE_SUM" }
                  }
                }
              }]
            }
          }
        },
      ]
    }
  })

  depends_on = [google_project_service.apis]
}
