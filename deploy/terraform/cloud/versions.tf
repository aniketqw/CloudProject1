terraform {
  required_version = ">=1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.25.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.7.2"
    }
    confluent = {
      source  = "confluentinc/confluent"
      version = "2.50.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "3.1.1"
    }
  }
  backend "gcs" {}
}

