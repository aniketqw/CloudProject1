# Summary of the executor run, updated 2026-11-22 (after the fourth live window)

| Req | Result | Evidence | Note |
|---|---|---|---|
| A IaC | PARTIAL | `02-platform/`, `04-rebuild/`, `05-final-teardown/`, `12-plan-no-changes/` | One apply, plan No changes, two-command teardown, unattended start-up. Not run from a fully empty project. |
| B | PASS | `07-order-flow/` | REST, gRPC, Kafka, Pub/Sub, function, receipt, HTTPS name. |
| C | PASS | `08-hpa-load/`, `17-load-tuning/`, `14-screenshots/`, `15-cloud-monitoring/` | Scale-out and in; k6 thresholds passed with 20 users; Web UI stateless in Cloud SQL (T-094). |
| D | PASS | `10-gitops/`, `14-screenshots/`, `19-build-on-push/` | Sync, self-heal, UI, and build-on-push on the owner's fork. |
| E | PASS (Kafka is now Apache Kafka on a VM, T-109) | `16-flink-results/`, `13-logs/`, `20-flink-and-console/` | Results in Firestore; duplicates and invalid events ignored; Flink dashboard captured. |
| F | PASS | `09-failover/`, `18-zookeeper-acl/` | Failover, worker deletion, quorum loss, access control, watches (T-100; the watch change tested on a real ZooKeeper container, not re-run on the cloud). |
| G | PASS | `07-order-flow/`, `16-flink-results/` | SQL, Firestore, Cloud Storage. |
| H | PASS | `11-observability/`, `13-logs/`, `14-screenshots/`, `21-alert-email/` | Dashboards with real traffic, log queries, alerts, and the alert email arrived. |

Hardening and cleanup: done S1 (gRPC TLS), S2, S3 (Web UI state), S6 (generated Argo admin password), S7, S9, S10 (digest pinning), S13 (budget alert), F5 access control and watches, N4, N5, N6, N7, N8 (T-099, T-101 to T-104). Not done on purpose: S8 (customer-managed key on the state bucket: a mistake would lock Terraform out of its state, T-105); S4 beyond watches; N2 and N3 (original documents). Not run: an empty-project rebuild, a Cloud Monitoring console picture (needs a Google sign-in), screen recordings.

Cost: about 11 to 14 US dollars a day while the platform is up; four live windows so far, each destroyed afterwards. Nothing chargeable is running now.

Owner items still open: none required. Optional: decide whether to do the remaining hardening.
