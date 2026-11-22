# E. Stream processing (Flink)

## 1. The requirement
A stateful Flink job reads the orders topic and writes windowed results.

## 2. Original code
Java job and a Python launcher existed; never run on the cloud. The launcher derived the job id only from settings.

## 3. Changes
Job id now includes a value that changes with each Dataproc cluster (T-067, original-code defect), Dataproc replace-every-plan fixes (T-029, T-030).

## 4. See it working
`gcloud dataproc jobs list --region asia-south1`; results on the `restaurant_analytics_results` topic and in Firestore `restaurant_analytics_v1`.

## 5. Evidence
None beyond the trace row T-073.

## 6. Result
BLOCKED, 2026-11-22. The job is submitted and shows RUNNING, but its YARN application fails about a minute after deployment and no results appeared. The cause is unknown because YARN logs were not reachable without SSH to the Dataproc master.

## 7. Open
Read the YARN logs (needs SSH approval or the Component Gateway), fix the cause, then show results and that a duplicate and an invalid event do not change counts.
