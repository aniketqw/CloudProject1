# Summary of the executor run, updated 2026-11-22 (after the fourth live window)

| Req | Result | Evidence | Note |
|---|---|---|---|
| A IaC | PARTIAL | `02-platform/`, `04-rebuild/`, `05-final-teardown/`, `12-plan-no-changes/` | One apply, plan No changes, two-command teardown, unattended start-up. Not run from a fully empty project. |
| B | PASS | `07-order-flow/` | REST, gRPC, Kafka, Pub/Sub, function, receipt, HTTPS name. |
| C | PASS | `08-hpa-load/`, `17-load-tuning/`, `14-screenshots/`, `15-cloud-monitoring/` | Scale-out and in; k6 thresholds passed with 20 users; Web UI stateless in Cloud SQL (T-094). |
| D | PASS | `10-gitops/`, `14-screenshots/`, `19-build-on-push/` | Sync, self-heal, UI, and build-on-push on the owner's fork. |
| E | PASS | `16-flink-results/`, `13-logs/`, `20-flink-and-console/` | Results in Firestore; duplicates and invalid events ignored; Flink dashboard captured. |
| F | PASS | `09-failover/`, `18-zookeeper-acl/` | Failover, worker deletion, quorum loss, access control, watches (T-100; the watch change tested on a real ZooKeeper container, not re-run on the cloud). |
| G | PASS | `07-order-flow/`, `16-flink-results/` | SQL, Firestore, Cloud Storage. |
| H | PASS | `11-observability/`, `13-logs/`, `14-screenshots/`, `21-alert-email/` | Dashboards with real traffic, log queries, alerts, and the alert email arrived. |

Hardening and cleanup: done S2, S7, S9, S10 (API only), S3 (Web UI state), F5 access control and watches, N5, N6, and N4, N7, N8 (T-099: the two duplicated files stay and a test keeps them identical, both shims are in use, the repeated trace ids are intentional). Not done: TLS for gRPC (S1), Argo admin password (S6), state bucket key (S8), image digests, budget alert (S13). Done: cleanup N4, N7, N8 are closed without deleting anything that is needed (T-099): the two duplicated files stay but a test keeps them identical, both shims are in use, the repeated trace ids are intentional. N2 and N3 are original documents and are left alone. Not run: an empty-project rebuild, a Cloud Monitoring console picture (needs a Google sign-in), screen recordings.

Cost: about 11 to 14 US dollars a day while the platform is up; four live windows so far, each destroyed afterwards. Nothing chargeable is running now.

Owner items still open: none required. Optional: decide whether to do the remaining hardening.
