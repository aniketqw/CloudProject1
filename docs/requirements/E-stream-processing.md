# E. Stream processing (Flink)

## 1. The requirement
A stateful Flink job reads the orders topic and writes windowed results.

## 2. Original code
Java job and a Python launcher existed; never run on the cloud. The launcher derived the job id only from settings.

## 3. Changes
T-067 (job id per cluster), T-076 (logs), T-077 (class loader), T-078 (master size), T-079 (transactional prefix), T-029 and T-030 (replace-every-plan). All original-code defects except the size.

## 4. See it working
`gcloud dataproc jobs list --region asia-south1`; results on the `restaurant_analytics_results` topic and in Firestore `restaurant_analytics_v1`.

## 5. Evidence
`docs/evidence/16-flink-results/` (README and Firestore windows), `13-logs/`.

## 6. Result
PASS, 2026-11-22. After three root causes were found through the YARN container logs now in Cloud Logging (class loader clash with the shipped Kafka connector, a master too small, a transactional id prefix shared by dead runs) the job stayed RUNNING, completed checkpoints, and wrote windowed results to the topic and to Firestore. A duplicate and two invalid events left the window count unchanged.

## 7. Open
A 1-worker cluster is not allowed by Dataproc (0 or 2 or more); the demo uses a larger single master (T-078).
