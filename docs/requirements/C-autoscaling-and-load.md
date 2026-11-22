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
`docs/evidence/08-hpa-load/` (timeline and k6 summary).

## 6. Result
PARTIAL, 2026-11-22. Replicas rose from 1 to 4 (maximum) within about a minute; 66,045 requests at about 116 per second, 0 failed. The k6 p95 latency threshold was crossed (p95 3.4 s) on the small demo nodes. Scale-in after the load was not captured in the saved timeline.

## 7. Open
Capture scale-in; larger nodes or a lower target to meet the latency threshold; a monitoring screenshot during load.
