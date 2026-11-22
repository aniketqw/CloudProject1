# Summary of the executor run, 2026-11-22

| Req | Result | Evidence | Note |
|---|---|---|---|
| A IaC | PARTIAL | `docs/evidence/12-plan-no-changes/`, `02-platform/`, `04-rebuild/` | One apply, plan shows No changes. Confluent cluster still manual (code written, not applied). |
| B | PASS (order path) | `07-order-flow/` | REST, gRPC, Kafka, Pub/Sub, function, receipt, HTTPS name. |
| C | PARTIAL | `08-hpa-load/` | 1 to 4 replicas; p95 threshold crossed on demo nodes. |
| D | PARTIAL | `10-gitops/` | Sync and self-heal proven; build-on-push written, not proven. |
| E | BLOCKED | none | Job RUNNING but its YARN application fails; cause unknown. |
| F | PARTIAL | `09-failover/` | Leader failover shown; reclaim and quorum loss not run. |
| G | PASS | `07-order-flow/` | SQL, Firestore, Cloud Storage. |
| H | PARTIAL | `11-observability/` | Grafana, Prometheus, alert policies; no channel, no screenshots. |

Not done in this run: hardening S1 to S13 (skipped, not started), cleanup N2 to N8, the clean second rebuild with the full verification plan (P6), screenshots and screen recordings.
Cost: platform about 8 to 11 US dollars a day on the three-node profile (roughly 11 to 14 now); it ran for about two days in total across tests. The platform was destroyed at the end (see the trace row for the teardown).

Blockers and what only the owner can do: (1) Confluent Cloud management API key (A4); (2) write access and repository variables for the tracked repository (D4); (3) approval to create an SSH key / OS Login identity to read YARN logs on the Dataproc master, or enable the Component Gateway (E); (4) a decision on the pause/resume Python tooling.
