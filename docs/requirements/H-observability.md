# H. Observability

## 1. The requirement
Metrics, dashboards, logs and alerts are in place as code.

## 2. Original code
Prometheus, Grafana, dashboards and alert policies were declared.

## 3. Changes
None needed in this round; the dashboard title "Supper" was checked and left (product name, T-070).

## 4. See it working
Port-forward Grafana (`monitoring`, service `food-platform-grafana`) and Prometheus; `gcloud monitoring policies list`.

## 5. Evidence
`docs/evidence/11-observability/`.

## 6. Result
PARTIAL, 2026-11-22. Grafana healthy with the application dashboard; Prometheus 32 targets up with `food_*` metrics; three alert policies enabled. No screenshots, no log queries run, no notification channel.

## 7. Open
Email notification channel in Terraform; panel screenshots under load; the two log queries.
