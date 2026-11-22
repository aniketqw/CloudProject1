# Optional cost guard: a monthly budget on the billing account with an email alert at 50, 90 and 100 percent.
# Off by default (billing_account_id = ""). Creating a budget needs the Billing Account Administrator role (or Costs
# Manager) on the billing account, which a project owner does not have automatically.
variable "billing_account_id" {
  type        = string
  default     = ""
  description = "Billing account id (the part after billingAccounts/). Empty creates no budget."
}

variable "budget_usd" {
  type        = number
  default     = 50
  description = "Monthly budget in US dollars."
}

resource "google_billing_budget" "monthly" {
  count           = var.billing_account_id == "" ? 0 : 1
  billing_account = var.billing_account_id
  display_name    = "${var.prefix} monthly budget"

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_usd)
    }
  }

  dynamic "threshold_rules" {
    for_each = [0.5, 0.9, 1.0]
    content {
      threshold_percent = threshold_rules.value
    }
  }

  all_updates_rule {
    monitoring_notification_channels = google_monitoring_notification_channel.email[*].id
    disable_default_iam_recipients   = false
  }

  depends_on = [google_project_service.apis]
}
