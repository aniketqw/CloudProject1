# Summary of the executor run, 2026-11-22 (second live run included)

| Req | Result | Evidence | Note |
|---|---|---|---|
| A IaC | PARTIAL | `12-plan-no-changes/`, `02-platform/`, `04-rebuild/`, `05-final-teardown/` | One apply, plan shows No changes; last teardown used the two documented commands only (about 15 minutes, no watcher, no state surgery); a clean rebuild from empty with zero manual steps not repeated. |
| B | PASS (order path) | `07-order-flow/` | REST, gRPC, Kafka, Pub/Sub, function, receipt, HTTPS name. |
| C | PASS | `08-hpa-load/`, `17-load-tuning/`, `14-screenshots/`, `15-cloud-monitoring/` | Scale-out and in; k6 thresholds passed with 20 users (p95 832 ms). |
| D | PARTIAL | `10-gitops/`, `14-screenshots/` | Sync, self-heal, UI shown; build-on-push BLOCKED (no admin on the tracked repository). |
| E | PASS | `16-flink-results/`, `13-logs/` | Three root causes fixed; results in Firestore; duplicates and invalid events do not change counts. |
| F | PASS | `09-failover/`, trace T-084 | Leader failover, worker deletion, quorum loss and recovery. |
| G | PASS | `07-order-flow/`, `16-flink-results/` | SQL, Firestore, Cloud Storage. |
| H | PARTIAL | `11-observability/`, `13-logs/`, `14-screenshots/` | Dashboards with real traffic, log queries, alerts; email channel written, no address given. |

Hardening and cleanup done: S2 (replicas and disruption budgets), S9 (extra allowed addresses), S10 (scanning API), H4 variable, N5, N6. Skipped with reason: S1 (needs certificates or a mesh), S3 (web UI state move), S4 (ZooKeeper watches and ACLs), S6 (SSO), S7 (done differently: larger master), S8, S13 (needs billing admin), N2 to N4, N7, N8 (original documents are not edited; duplicates are used by the local compose files; shims left). Not run: P6 clean second rebuild from empty, screen recordings.

Cost: about 11 to 14 US dollars a day on the current profile (three small nodes, a 4 vCPU Dataproc master, Cloud SQL); the platform ran about 2 days in total across tests and was destroyed at the end.

Blockers that need the owner: (1) admin rights on the tracked repository (or Argo CD pointed at a repository the owner controls) for build-on-push; (2) an email address in `TF_VAR_alert_email` to prove the alert email; (3) a decision on keeping the Python Flink savepoint tooling.
