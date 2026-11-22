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
`docs/evidence/11-observability/`, `13-logs/`, `14-screenshots/grafana-*.png`, `15-cloud-monitoring/`.

## 6. Result
PARTIAL, 2026-11-22. Grafana dashboard screenshots with real traffic (idle and under load), Prometheus targets up, the log queries run (application, Dataproc, Flink containers, function), three alert policies enabled. The email notification channel is written in Terraform (`alert_email`) but no address was provided, so no email was sent.

## 7. Open
The address is set in `.env`; apply once more and trigger an alert to see the email (not run).
