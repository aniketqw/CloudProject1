# Illustrated report: what the pictures show

The pictures live in `docs/evidence/` (git-ignored, local only, because some show the project name or a commit author address). Paths below are relative to this file. Dates are 2026-11-22 unless stated.

## 1. Argo CD (requirement D, GitOps)
![All Argo CD applications](evidence/14-screenshots/argocd-applications.png)
*The two applications, `food` and `food-platform`, both Synced and Healthy.*

![The food application tree](evidence/14-screenshots/argocd-food-tree.png)
*Top bar: app health Healthy, sync status Synced to the `iac-integration` branch, last sync OK, auto sync enabled. The tree below shows each service as a Deployment with healthy pods (for example customer-service 2 pods). Left: 65 resources Synced, 0 OutOfSync, 114 Healthy, 0 Degraded.*

![Argo CD during the load test](evidence/14-screenshots/argocd-hpa-during-load.png)
*The same application while the k6 job ran, with the autoscaled services at their maximum replicas.*

How it was made: an optional read-only view (`argocd_anonymous_view`) and a port-forward to `argocd-server`; the page was captured with headless Chrome.

## 2. Grafana and Prometheus (requirement H)
![Grafana during the load test](evidence/14-screenshots/grafana-during-load.png)
*Six panels with real data. Requests per second rise from about 22 to about 35 when the load starts (10:49), p95 latency stays near 450 ms, Kubernetes ready pods go from 35 to 40 as the autoscaler adds replicas, pod restarts stay at 0. "No data" in two panels is expected: no 5xx errors occurred and the reachability panel has no series in this setup.*

Note: `evidence/14-screenshots/grafana-application-dashboard.png` (the idle view) was overwritten by a bad capture and must be taken again at the next live window.

## 3. Cloud resources before and after the first build (requirement A)
Before the apply and after it, Google Cloud console pages (project name hidden in the files' README, visible in the images):

| Page | Before | After |
|---|---|---|
| Dashboard | ![](evidence/02-platform/before-01-dashboard.jpg) | ![](evidence/02-platform/after-01-dashboard.jpg) |
| Storage | ![](evidence/02-platform/before-02-storage.jpg) | ![](evidence/02-platform/after-02-storage.jpg) |
| Kubernetes | ![](evidence/02-platform/before-03-kubernetes.jpg) | ![](evidence/02-platform/after-03-kubernetes.jpg) |
| Cloud SQL | ![](evidence/02-platform/before-04-cloud-sql.jpg) | ![](evidence/02-platform/after-04-cloud-sql.jpg) |
| Dataproc | ![](evidence/02-platform/before-05-dataproc.jpg) | ![](evidence/02-platform/after-05-dataproc.jpg) |
| Service accounts | ![](evidence/02-platform/before-06-service-accounts.jpg) | ![](evidence/02-platform/after-06-service-accounts.jpg) |
| Pub/Sub | ![](evidence/02-platform/before-07-pubsub.jpg) | ![](evidence/02-platform/after-07-pubsub.jpg) |
| Secret Manager | ![](evidence/02-platform/before-08-secret-manager.jpg) | ![](evidence/02-platform/after-08-secret-manager.jpg) |
| Cloud Run functions | ![](evidence/02-platform/before-09-cloud-run-functions.jpg) | ![](evidence/02-platform/after-09-cloud-run-functions.jpg) |
| Monitoring | ![](evidence/02-platform/before-10-monitoring.jpg) | ![](evidence/02-platform/after-10-monitoring.jpg) |

Also: alert policies ![](evidence/02-platform/after-11-alert-policies.jpg) and the platform dashboard ![](evidence/02-platform/after-12-platform-dashboard.jpg). Animated before and after: `evidence/02-platform/before-02-platform.gif`, `after-02-platform.gif`.

## 4. After the teardown, and after the one-command rebuild
Destroyed state (dashboard, storage, Kubernetes, Cloud SQL, Dataproc, service accounts): `evidence/03-destroy/*.jpg`. Rebuilt state: `evidence/04-rebuild/*.jpg`.

## 5. What has no picture yet
Order flow, ZooKeeper failover, the k6 summary and the Flink results are shown as text and tables, not pictures: see `evidence/07-order-flow/`, `09-failover/`, `17-load-tuning/`, `16-flink-results/`. At the next live window I will add: the Flink dashboard, the Cloud Monitoring console, the order in the web UI, an Argo CD view of a Git change turning OutOfSync then Synced, and the replacement for the idle Grafana picture.

## 6. Build-on-push, the stateless Web UI and Flink (second live run)
![Argo CD after build-on-push](evidence/14-screenshots/argocd-after-build-on-push.png)
*Requirement D. The "Last sync" box shows the author `build-image` (the GitHub Actions bot) and the comment "Release image ci-d9bde5ba6f": a source change was built by the workflow, the new tag was committed to Git, and Argo CD synced it. The tree shows each service's new ReplicaSet at revision 2.*

![Flink dashboard](evidence/20-flink-and-console/flink-running-jobs.png)
*Requirement E. The Apache Flink dashboard (opened through the Dataproc Component Gateway) lists one running job, "Restaurant Service - stateful kitchen-load analytics", with its two tasks RUNNING.*

![YARN applications](evidence/20-flink-and-console/yarn-applications.png)
*The same job as a YARN application on the managed Dataproc cluster.*

Text evidence with no picture: ZooKeeper refuses unauthenticated reads (`evidence/18-zookeeper-acl/`), the build-on-push run steps (`evidence/19-build-on-push/`), the alert test (`evidence/21-alert-email/`), and the Web UI rows in Cloud SQL (trace T-094).
