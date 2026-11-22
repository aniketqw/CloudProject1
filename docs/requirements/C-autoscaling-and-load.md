# C. Autoscaling and load

## 1. The requirement
Services scale with load (HPA) and a load test shows it.

## 2. Original code
HPAs and a k6 job existed, never run on the cloud. Two demo nodes could not hold the application.

## 3. Changes
Three nodes in the demo profile (T-056, T-058). Load test run through Git and Argo CD (`loadTest.enabled`, then set back).

## 4. See it working
Set `loadTest.enabled: true` with a new `runId` in `deploy/charts/food/values.yaml`, push, watch `kubectl get hpa -n food -w`.

## 5. Evidence
`docs/evidence/08-hpa-load/`, `17-load-tuning/` (timelines and k6 summaries of runs 1, 3 and 4), `14-screenshots/grafana-during-load.png`, `15-cloud-monitoring/`.

## 6. Result
PASS, 2026-11-22. Scale-out and scale-in shown (replicas 1 to 4 within a minute of the load, then 4 to 3 to 2 after it ended). Tuning: 60 and 40 virtual users saturated the demo (p95 3.4 s and 4.0 s, threshold 2 s); with 20 users k6 passed its thresholds: 35,573 requests at 108 per second, p95 832 ms, 2 failures in 35,573. The tuning (fewer virtual users, minimum 2 replicas) is recorded in `docs/evidence/17-load-tuning/`.

## 7. Open
The Cloud Monitoring console page could not be screenshotted without a Google sign-in; the dashboard and its data are shown through the API (`15-cloud-monitoring/`).
