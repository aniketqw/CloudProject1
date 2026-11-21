resource "random_password" "database" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "database" {
  name                = "${var.prefix}-sql"
  region              = var.region
  database_version    = "MYSQL_8_0"
  deletion_protection = true

  settings {
    tier              = local.capacity.sql_tier
    availability_type = "ZONAL"
    disk_size         = 10
    disk_autoresize   = true
    activation_policy = "ALWAYS"
    edition           = "ENTERPRISE"

    backup_configuration {
      enabled            = true
      binary_log_enabled = true
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }

    database_flags {
      name  = "max_connections"
      value = tostring(local.capacity.sql_max_connections)
    }
  }

  depends_on = [google_service_networking_connection.private]

  lifecycle {
    ignore_changes = [settings[0].activation_policy]
  }
}

resource "google_sql_database" "food" {
  name     = "food"
  instance = google_sql_database_instance.database.name
}

resource "google_sql_user" "app" {
  name     = "food_app"
  instance = google_sql_database_instance.database.name
  host     = "%"
  password = random_password.database.result
}

resource "google_firestore_database" "default" {
  count           = var.create_firestore ? 1 : 0
  name            = "(default)"
  location_id     = var.region
  type            = "FIRESTORE_NATIVE"
  deletion_policy = "ABANDON"
  depends_on      = [google_project_service.apis]
}

resource "google_firestore_index" "analytics" {
  collection = "restaurant_analytics_v1"

  fields {
    field_path = "restaurant_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "window_start"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.default]
}
