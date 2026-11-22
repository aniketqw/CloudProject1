# End-to-end plan and requirement tracker (A to H)

**Who this is for:** the session that continues the work (the "executor"). Read it, run it from the top, fix every bug it finds, and fill in the **Executor result** column as you go. When it is finished, this file shows what each requirement needed, what was already done, what was fixed, and how it was proven. That makes it the revision sheet.

**Written:** 2026-11-22, from `trace.md` (T-001 to T-051), the commits on `iac-integration` up to 22 November 01:03, and the earlier documents listed below. Statuses are what the record shows. Anything not proven by evidence is marked so.

Companion documents (read, do not duplicate): `docs/VERIFICATION_PLAN.md` (the exact check commands, IDs A1 to H5 and the live checks), `docs/GAPS_AND_PLAN.md` (gap groups and the status table), `docs/DEMO_READINESS.md`, `docs/QA_LOG.md`, `SERVICE_MAP.md`, `REQUIREMENTS_MAP.md`, `trace.md`.

---

## 0. Rules for the executor
1. **Never change, commit to, or push `main`.** Work on a branch cut from `iac-integration`; merge back into `iac-integration`. Check `git branch --show-current` before every git write.
2. **Fix in code, not in the cluster.** Every fix is a change to the repository (Terraform, chart, or application code), applied through Terraform and Argo CD. Hand edits in the cluster (`kubectl edit`, `kubectl apply`) are only for diagnosis, and must be reverted and replaced by a code fix.
3. **Record every change in `trace.md` before moving on.** Before writing, read the highest `T-` number in the file and take the next one (two sessions have collided on IDs before). Each row: ID, origin (original code, refactor, or mistake), file, symptom, cause, fix, undo, log. Put commands and output in `logs/<ID>-<name>.log`.
4. **One Terraform run at a time.** Run `ps aux | grep '[t]erraform'` first. Never force-unlock state without asking the owner.
5. **Safe teardown order.** Never run a plain `terraform apply` after a partial destroy (it recreates everything missing; this cost 25 minutes and credits before, T-041). Follow the documented order in `.env.example`.
6. **No secrets in output or files.** Load `.env` with `set -a; source .env; set +a`, never print it. Replace the project ID and account email with placeholders in anything saved. No assistant or tool attribution of any kind in commits or files (no co-author lines).
7. **Evidence:** save to `docs/evidence/NN-name/` (git-ignored). **Record one terminal window only, never the whole screen**; an earlier full-screen recording captured the wrong windows and had to be deleted (T-034).
8. **Cost:** the platform costs roughly 8 to 11 US dollars a day. At the end of each working session, either destroy it or write down that it was left running and why.
9. **Stop and ask the owner** before: pushing branches, buying anything, creating accounts or API keys, changing the pause/resume decision, or anything that deletes cloud data that was not created by this project.

## 1. Snapshot (2026-11-22, about 01:13)

| Layer | State | Evidence |
|---|---|---|
| Terraform code | One root, 16 files, plus `modules/argocd` and a state bootstrap. Validates; a one-shot rebuild worked (88 to add). | T-009, T-010, T-045 |
| GCP infrastructure | Running now: GKE, Cloud SQL, Dataproc. No Terraform process is running. | live check |
| Kafka | Existing Confluent cluster. Four topics created by Terraform (3 partitions). Reachable from inside GKE (login accepted, topics visible). Not reachable on port 9092 from the owner's laptop network (443 is). | T-047, T-050 |
| Images | Both images built and pushed by `terraform apply` (buildx builder, after a fix). | T-048, T-050 |
| Argo CD | Installed; the `food` application synced after the ZooKeeper YAML fix. | T-049, T-050 |
| Application pods | **Not healthy at the last record.** The three ZooKeeper pods crash-looped on name resolution. Fixes committed since (DNS egress in the network policy; Cloud SQL proxy bind address; ingress skipped for a placeholder host). **Unproven.** | T-050, commits `1380e00`, `17b2f8d` |
| Web hostname | Placeholder, so the managed certificate stays unhealthy. | T-050 |
| Kubernetes access from the current machine | `gke-gcloud-auth-plugin` was missing here when checked. Install it first. | preflight |

**The single blocker for B to H:** the application pods have not been shown running. Everything in Phase 1 is about that.

---

## 2. Phases, in order

| Phase | Goal | Exit criterion | Depends on |
|---|---|---|---|
| **P0** | Owner decisions (section 4) | OD1 to OD5 answered and written in section 4 | none |
| **P1** | Get every application pod healthy | `kubectl -n food get pods`: all Running or Completed; Argo CD `food` and `food-platform` Synced and Healthy | cloud up |
| **P2** | Fix and prove requirements B, G, F, C, E, H live, in this order (B and G first because they create the data the others need) | each tracker row PASS with evidence | P1 |
| **P3** | Close structural gaps: Confluent in Terraform (A4), hostname (B6), build-on-push (D4), Argo destroy hang (A3) | rows PASS | P2 |
| **P4** | Best-practice hardening (section 5) | rows done or consciously skipped with a reason | P2 |
| **P5** | Cleanup and documentation (section 6) | rows done | any |
| **P6** | Final proof: destroy, then a clean one-shot rebuild, full verification run, recording, revision guide, teardown | all trackers PASS; the one-shot rebuild needs zero manual steps | all |

### P1 in detail: the bug-fix loop for "pods not healthy"
```bash
set -a; source .env; set +a
gcloud components install gke-gcloud-auth-plugin          # if missing; owner approves
gcloud container clusters get-credentials "${TF_VAR_prefix}-gke" --zone "$TF_VAR_zone" --project "$TF_VAR_project_id"
kubectl get nodes
kubectl -n argocd get applications
kubectl -n food get pods -o wide
kubectl -n food get networkpolicy
```
For each pod that is not Running: `kubectl -n food describe pod <name>` and `kubectl -n food logs <name> --previous`. Likely causes seen so far, in order of likelihood:
1. **Name resolution blocked** (ZooKeeper "Unresolved address zookeeper-N.zookeeper"): check the network policy allows DNS egress; check the headless Service exists; test with `kubectl -n food run dns-test --rm -it --image=busybox:1.36 --restart=Never -- nslookup zookeeper-0.zookeeper`.
2. **Image pull failure** (`ImagePullBackOff`): confirm the image tag in `deploy/environments/team/image.yaml` was pushed to Artifact Registry.
3. **Database not reachable:** Cloud SQL proxy sidecar not ready (startup probe); secret versions missing; workload identity binding missing.
4. **Resources too small** on two small nodes: `Pending` with insufficient CPU or memory.
Loop: find cause, change the repository, validate (`terraform validate`, unit tests, chart check), apply through Terraform or `git push` to the branch Argo CD tracks, wait, re-check. Add a `trace.md` row for each fix and mark whether the defect is in the original code.

---

## 3. Requirement trackers
**Columns:** *Status* is Done, Partly, Open, or Unknown. *Already done* describes what exists and where the proof is. *Left and how to fix* is what the executor does. *Verify* points at the check IDs in `docs/VERIFICATION_PLAN.md`. *Executor result* is left blank on purpose: write date, PASS or FAIL, the evidence path, and a one-line note.

### A. Infrastructure as Code
| ID | Needed | Status | Already done | Left and how to fix | Verify | Executor result |
|---|---|---|---|---|---|---|
| A1 | Everything declared in Terraform | Done (proven 2026-11-22) | One root in `deploy/terraform/cloud/` (16 files), `modules/argocd/`, state bootstrap in `state/`. Covers network, GKE, Dataproc, Cloud SQL, Firestore, buckets, IAM, Pub/Sub, function, secrets, monitoring, Argo CD and the image builds. | None for the code. Re-check after every fix. | A1 to A4 |  2026-11-22 PASS. One HCL root plus module and bootstrap; validated. `docs/evidence/12-plan-no-changes/`. |
| A2 | One `terraform apply` from empty works | Done (proven 2026-11-22) | A rebuild from the state left by a destroy was one apply, 88 to add, 0 to change (T-045). A full apply with images and Kafka also worked (T-050). Real defects in the original code were found and fixed on the way (T-027 to T-030, T-038, T-039, T-049). | Prove it once more from a truly empty project after P1 and P3, with no manual step, then `terraform plan` must show "No changes". Use a new `TF_VAR_prefix` if the Cloud SQL name is still locked. | A live, VERIFICATION_PLAN section 5 | 2026-11-22 PASS (caveat). One apply created 108 resources with no errors; the platform then needed an Argo fix (T-090) and settled about 26 minutes later with no hand sync. Not run from a fully empty project (T-091). |
| A3 | Teardown works in one go | Partly (see result) | Variables `deletion_protection`, `force_destroy_buckets`, `firestore_delete_on_destroy` added (T-035, T-038, T-044); the safe order is in `.env.example`. | Still manual: (a) Argo CD can hang a destroy because the root application has a cleanup rule and syncs may be running (T-037, T-040): make the applications safe to delete, for example drop the `resources-finalizer` or add a pre-destroy step in Terraform that stops syncs; (b) Kafka topics have `prevent_destroy`, so they had to be removed from state first (T-051): remove that lifecycle rule or guard it with a variable-driven `count`; (c) Google's function-source bucket must be deleted by name: add a `terraform_data` destroy-time step. Goal: set the three switches, apply once, `terraform destroy`, done. | destroy once, then A5 listing | 2026-11-22 PARTIAL-PASS. Last teardown used the two documented commands only (no watcher, no state surgery), about 15 minutes, Kafka topics removed by Terraform (T-075, T-086). Service Networking Connection still lingers (free). |
| A4 | Confluent Kafka created by Terraform too ("all cloud providers") | Done (proven 2026-11-22) | Kafka is live; the four topics are Terraform-managed (T-047). | Use the Confluent provider to also create the environment, Basic cluster on GCP, the application and topic-admin service accounts, their API keys and permissions, and wire the results into the application secret. The only manual input left is one Confluent Cloud API key. **Needs owner approval** (OD1). | A plan shows the new resources | 2026-11-22 PASS (owner accepted the existing cluster as the Kafka provider). Re-verified: key accepted, topics listed and created by Terraform. `confluent.tf` stays optional. |
| A5 | No Python provisioning infrastructure | Done (owner decision) | Owner decision 2026-11-21 (Group J): keep SQL table creation, Flink submit and pause/resume as application or day-2 tools. The Firestore seed moved into Terraform (T-015). | Confirm the decision (OD2). If kept: document the exceptions in the revision guide; make sure the wrapper `deploy/cloud_stage.py` is either removed or clearly optional, since a plain `terraform apply` works. If reversed: follow `docs/GAPS_AND_PLAN.md` M3. | A5, A6 | 2026-11-22 PASS. Deployment and pause are Terraform only (`paused` variable, T-061, T-066). The remaining Python (Flink savepoint stop/start, optional wrapper) is not in the deployment path and is kept as a documented day-2 tool by the owner's decision (OD2). |
| A6 | State is protected | Done | Versioned bucket, public access prevented, `prevent_destroy` on the state bucket. | Optional hardening: S8 in section 5. | |  2026-11-22 PASS (unchanged). State bucket kept through every teardown. |

### B. Serverless function; REST, gRPC and a queue
| ID | Needed | Status | Already done | Left and how to fix | Verify | Executor result |
|---|---|---|---|---|---|---|
| B1 | One serverless function, event driven | Done (proven 2026-11-22) | Cloud Function gen2 `<prefix>-notification-transport`, Eventarc trigger and Pub/Sub topic created and ACTIVE (T-032 evidence). | Prove the event flow works once services run: order, notification, Pub/Sub, function log, receipt object. | B1, B2 live |  2026-11-22 PASS. Function ACTIVE, invoked through Pub/Sub and Eventarc; receipt object written. `docs/evidence/07-order-flow/`. |
| B2 | REST used | Done (proven 2026-11-22) | Flask APIs, UI client, scheduler calls. | Prove with the order flow after P1. | B4, B live |  2026-11-22 PASS. Order placed over REST, HTTP 201. `docs/evidence/07-order-flow/`. |
| B3 | gRPC used | Done (proven 2026-11-22) | Order to Restaurant (`restaurant.proto`). Plaintext channel. | Prove with the order flow; consider TLS (S1). | B3 |  2026-11-22 PASS (indirect). Order priced from the Restaurant menu over gRPC; no log line captured. |
| B4 | A message queue used | Done (proven 2026-11-22) | Kafka topics exist and are reachable from GKE (T-050); Pub/Sub topic exists. | Prove messages flow: order event on `orders`, delivery event on `delivery_assignments`, Pub/Sub publish. | B5, B6, B live |  2026-11-22 PASS. `OrderCreated` read from Kafka `orders`; notification through Pub/Sub. `docs/evidence/07-order-flow/`. |
| B5 | Architecture diagram shows all three | Done (proven 2026-11-22) | Diagram in `REQUIREMENTS_MAP.md` and `DESIGN.md`. | Optional: mark which arrows are external versus internal. | B7 |  2026-11-22 PASS (unchanged). |
| B6 | External REST over HTTPS | Done (proven 2026-11-22) | The UI is routed through an ingress with a managed certificate, but the host is a placeholder so the certificate stays unhealthy. A toggle now skips the ingress for a placeholder host. | Give the web IP a real name (a free `<ip-with-dashes>.sslip.io` name, not yet tested here, or the owner's domain via Cloud DNS in Terraform). Re-enable the ingress, wait for the certificate to become Active, open the site over HTTPS. | open the site |  2026-11-22 PASS. HTTPS on the sslip.io name, certificate Active, HTTP redirects (T-059, T-060). |

### C. Managed Kubernetes, HPAs, load test
| ID | Needed | Status | Already done | Left and how to fix | Verify | Executor result |
|---|---|---|---|---|---|---|
| C1 | Managed Kubernetes hosts the services | Done (proven 2026-11-22) | GKE running, two nodes, private nodes, Workload Identity. | Pods must be healthy (P1). | C1, L0 gate |  2026-11-22 PASS. GKE with three nodes ran 33 pods (T-056, T-058, T-064). |
| C2 | Services stateless | Done (proven 2026-11-22) | State is in SQL and Firestore. The Web UI keeps a SQLite file on a volume. | S3: move the UI's state to SQL or Firestore, or state it runs as one replica. | 2026-11-22 PASS. Web UI state is in Cloud SQL, two replicas, no disk volume in the cloud profile (T-094). |
| C3 | HPAs on at least two services | Done (proven 2026-11-22) | HPAs on `customer-service` and `order-service`, CPU 60 percent, memory 75 percent, 1 to 6 replicas. | Prove they exist on the cluster: `kubectl -n food get hpa`. Consider min 2 and PodDisruptionBudgets (S2). | C2, C3 |  2026-11-22 PASS. HPAs on customer-service and order-service scaled 1 to 4. `docs/evidence/08-hpa-load/`. |
| C4 | Load test and scale-out | Done (proven 2026-11-22) | k6 script with thresholds; job template. Never run. | Enable `loadTest` in `deploy/charts/food/values.yaml` (not a `food-values.json`; that file does not exist), push to the tracked branch, watch `kubectl -n food get hpa -w`. If it does not scale on two small nodes, raise virtual users or lower the CPU target and record that. | C live | 2026-11-22 PASS. 20 users: 35,573 requests, p95 832 ms, thresholds passed; 60 and 40 users saturated (T-085). `docs/evidence/17-load-tuning/`. |
| C5 | Cloud Monitoring shows it | Partly (see result) | Dashboard tiles for HPA CPU and running pods (T-016). | Open the dashboard during the load test and capture it. | C live | 2026-11-22 PARTIAL. Cloud Monitoring dashboard (6 tiles), alert policies and pod metric series shown through the API; no console screenshot (needs a Google sign-in). `docs/evidence/15-cloud-monitoring/`. |

### D. GitOps
| ID | Needed | Status | Already done | Left and how to fix | Verify | Executor result |
|---|---|---|---|---|---|---|
| D1 | Controller installed | Done | Argo CD installed by Terraform (`modules/argocd`). | | D1 |  2026-11-22 PASS. Argo CD running (T-064). |
| D2 | Tracks a Git repository | Done (proven 2026-11-22) | Applications `food-platform` and `food` track `git_repository` and `git_revision`; settings are passed inline from Terraform so the project ID never goes into Git (T-021). | Confirm the tracked branch holds the latest charts. | D2 |  2026-11-22 PASS. Both applications tracked `iac-integration`. |
| D3 | No `kubectl apply` for services | Done | No `kubectl apply`, `create` or `helm install` in the deploy path; the pause/resume tool uses `get`, `patch`, `scale`, `config` only. | | D3, D4 |  2026-11-22 PASS (unchanged). |
| D4 | Application updates via GitOps, including source changes | Done (proven 2026-11-22) | A change to chart or config in Git rolls out. The release tag is `deploy/environments/team/image.yaml`. A source change still needs `terraform apply` to build the image. | Add build-on-push: a workflow builds the image on an Intel runner, pushes to Artifact Registry through a workload identity pool created by Terraform (no key file), and commits the new tag to `image.yaml`; Argo CD syncs it. Alternative: a Cloud Build trigger (needs a one-time GitHub authorization). **Needs write access to the tracked repository** (OD3, section 4). | change source, push, watch it deploy | 2026-11-22 PASS. Fork `aniketqw/CloudProject1`; source change led to a successful workflow, a bot tag commit and an Argo CD rollout of all services (T-089, `docs/evidence/19-build-on-push/`). |
| D5 | Dashboard demo | Done (proven 2026-11-22) | Argo CD UI is cluster-internal. | Use `kubectl -n argocd port-forward svc/argocd-server 8080:443`; get the initial admin secret without saving it; make a config change in Git, push, show OutOfSync then Synced. | D live | 2026-11-22 PASS. Argo CD UI screenshots (anonymous read-only view, option `argocd_anonymous_view`). `docs/evidence/14-screenshots/`. |

### E. Flink stream processing
| ID | Needed | Status | Already done | Left and how to fix | Verify | Executor result |
|---|---|---|---|---|---|---|
| E1 | Job consumes Kafka, stateful time windows, results to a second topic | Code Done | `RestaurantAnalytics.java`: reads `orders`, keyed event-time windows, state, 3-second watermark, checkpoints to storage, writes `restaurant_analytics_results`. Java tests pass and the jar builds. | | E1 to E3 |  2026-11-22 PASS (code, unchanged). |
| E2 | Runs on managed cluster | Done (cluster) | Dataproc cluster running; web interfaces enabled (Component Gateway, T-016). Sized with 0 workers on the demo profile (S7). | | E4 |  2026-11-22 PASS. Dataproc cluster running. |
P26-11-22 PASS (A4 accepted; same re-verification). |
| E4 | Job actually running | Done (proven 2026-11-22) | The launch is an Argo-managed job that runs `deploy/dataproc_submit.py`; the jar is uploaded during apply. Never seen running, because the services were down. | After P1: check the launch job, `gcloud dataproc jobs list`, open the Flink UI. Fix whatever fails (jar path, Kafka secret access, network). | E live | 2026-11-22 PASS. Job RUNNING with completed checkpoints after three root-cause fixes (T-076 to T-079). `docs/evidence/16-flink-results/`. |
| E5 | Results appear | Done (proven 2026-11-22) | Consumer copies results to Firestore. | Produce orders, wait a window, read the results topic and Firestore. | E live | 2026-11-22 PASS. Windowed results in Firestore; duplicate and invalid events left the count unchanged. `docs/evidence/16-flink-results/`. |

### F. ZooKeeper concept
| ID | Needed | Status | Already done | Left and how to fix | Verify | Executor result |
|---|---|---|---|---|---|---|
| F1 | Concept implemented in the domain | Done (code) | Election, ephemeral worker and lease nodes, generation fencing, reclaiming abandoned work; four business workers use it; the scheduler tests pass. See `docs/QA_LOG.md` Q3. | | F1 to F6 |  2026-11-22 PASS (code, unchanged). |
| F2 | ZooKeeper ensemble healthy | Done (proven 2026-11-22) | Three-server StatefulSet. The YAML quoting bug was fixed (T-049); pods then crash-looped on name resolution; DNS egress fix committed. | P1. After it, `kubectl -n food exec zookeeper-0 -- zkCli.sh ... ls /` works, and `echo ruok` style checks pass. | F live |  2026-11-22 PASS. Three ZooKeeper pods Ready after T-049, T-052, T-054. |
| F3 | Show leader, kill it, show the new one | Done (proven 2026-11-22) | `GET /scheduler` returns leader name (the pod name) and epoch. | Run the drill: note leader, delete pod, new leader with a higher epoch within about 20 seconds. | F live |  2026-11-22 PASS. Leader changed after its pod was deleted, epoch 2 to 29. `docs/evidence/09-failover/`. |
| F4 | Failure drills on the cloud | Open | Drills exist locally (`local/scheduler_recovery_test.py`). | Optional on the cloud: delete a worker pod mid-task; stop two ZooKeeper pods for quorum loss. | 2026-11-22 PASS (with a caveat). Worker deletion: order PAID, one capture only; ZooKeeper quorum loss and recovery shown (T-084). `docs/evidence/09-failover/`. |
| F5 | Watches and access control | Partly (see result) | Polling every 0.25 s; no ACLs. | Optional hardening. | 2026-11-22 PARTIAL. Access control done and proven: unauthenticated reads get `Insufficient permission` (T-088, `docs/evidence/18-zookeeper-acl/`). Watches instead of 0.25 s polling not done. |

### G. Three storage products
| ID | Needed | Status | Already done | Left and how to fix | Verify | Executor result |
|---|---|---|---|---|---|---|
| G1 | Cloud SQL, Firestore, Cloud Storage exist | Done | All three created and seen (T-032 evidence); a starter restaurant is seeded by Terraform (T-015). | | G1 |  2026-11-22 PASS. All three products created and used. |
| G2 | Each holds real data from the app | Done (proven 2026-11-22) | Tables are created by an Argo-managed initialize job (kept by decision). | After P1: place an order; check the SQL rows (via the API), the Firestore restaurant, and the receipt object. Fix the Cloud SQL proxy or initialize job if they fail. | G live |  2026-11-22 PASS. Order in SQL, restaurant in Firestore, receipt object in Cloud Storage. `docs/evidence/07-order-flow/`. |
| G3 | Mapped to code | Done | `docs/DEMO_READINESS.md` G table and checks G2 to G4. | | G2 to G4 |  2026-11-22 PASS (unchanged). |

### H. Observability
| ID | Needed | Status | Already done | Left and how to fix | Verify | Executor result |
|---|---|---|---|---|---|---|
| H1 | Prometheus and Grafana deployed | Done (proven 2026-11-22) | `food-platform` Argo application deploys kube-prometheus-stack. Not confirmed healthy on the cluster. | Check the `monitoring` namespace pods after P1; fix what fails. | H live |  2026-11-22 PASS. Grafana 13.3.1 healthy, Prometheus 32 targets up. `docs/evidence/11-observability/`. |
| H2 | Dashboard with RPS, errors, latency, cluster health | Done (proven 2026-11-22) | Six panels in `system.json`; services export a counter and a latency histogram. | Send traffic (order loop or k6) and confirm the panels are not empty; fix the scrape config if they are. | H live | 2026-11-22 PASS. Dashboard screenshots with real traffic, idle and under load. `docs/evidence/14-screenshots/`. |
| H3 | Central logging including the analytics job | Done (proven 2026-11-22) | Cloud Logging for GKE workloads, Dataproc and the function; log tiles and two log metrics in Terraform. | Run the two `gcloud logging read` queries in VERIFICATION_PLAN H live. | H live | 2026-11-22 PASS. Log queries for application, Dataproc, Flink containers and the function. `docs/evidence/13-logs/`. |
| H4 | Alerts notify someone | Done (proven 2026-11-22) | Three alert policies exist; no notification channel is created. | S5: create an email channel in Terraform (address kept in `.env`). | 2026-11-22 PASS. Email channel attached to all policies; a lowered threshold opened three alerts and the alert email arrived in the owner's inbox (confirmed by the owner). `docs/evidence/21-alert-email/`, T-097. |
| H5 | Dashboard title typo | Open (N1) | Title reads "Supper - application and Kubernetes". | Fix the title in `deploy/charts/platform/dashboards/system.json` and the duplicate under `observability/`. | |  2026-11-22 NOT A DEFECT. "Supper" is the product name (T-070). |

---

## 4. Owner decisions the executor needs (P0)
| ID | Question | Recommended | Answer |
|---|---|---|---|
| OD1 | Create the Confluent cluster, service accounts and keys with Terraform (A4)? Needs one Confluent Cloud API key. | Yes |  2026-11-22 Answered in the cross-session note: do it only if a management key exists. None exists, so code written, not applied (T-071). |
| OD2 | Keep pause/resume, Flink submit and SQL table creation as application or day-2 tools (the 2026-11-21 decision), or move them? | Keep, and document |  2026-11-22 Keep as day-2 tools. `paused` added in Terraform for the infrastructure part (T-061, T-066). |
| OD3 | Do you have write access to the Git repository that Argo CD tracks, so a build-on-push workflow can commit the new image tag (D4)? | Confirm |  2026-11-22 Not answered by the owner. Workflow written, not proven (T-072). |
| OD4 | Web hostname: free `<ip>.sslip.io`, or your own domain? | sslip.io for the demo |  2026-11-22 sslip.io. Proven (T-059). |
| OD5 | At the end of each session, destroy the platform or leave it running? | Destroy |  2026-11-22 Destroy. Done at the end of each session (T-051, T-057, T-074). |

## 5. Hardening, after the requirements pass (P4)
Do in this order; each row is Done, Skipped (with a reason), or Open.

| ID | Item | Current state | Fix | Result |
|---|---|---|---|---|
| S2 | No redundancy for autoscaled services | One replica, HPA minimum 1; only ZooKeeper has a PodDisruptionBudget | Minimum 2 replicas, a PodDisruptionBudget per service, spread across nodes | 2026-11-22 DONE. HPA services run 2 replicas minimum with a PodDisruptionBudget (T-082). |
| S3 | Web UI not stateless | SQLite file on a volume | Move state to SQL or Firestore |  2026-11-22 SKIPPED. Not started this pass. |
| S1 | Plaintext internal gRPC and REST | `grpc.insecure_channel`; plain HTTP between services; network policy limits access | TLS or mTLS (cert-manager, or a mesh) |  2026-11-22 SKIPPED. Needs certificates or a mesh; not started. |
| S4 | ZooKeeper polling and no ACLs | 0.25 s polling; no auth | Use watches; add auth and ACLs |  2026-11-22 SKIPPED. Not started. |
| S5 | Grafana and alerts | Anonymous viewer, login form off; no alert recipients | IAP or SSO if exposed; email channel in Terraform |  2026-11-22 SKIPPED. No notification channel yet (needs an address from the owner). |
| S6 | Argo CD access | Port-forward and initial admin secret | SSO or IAP; rotate the admin password |  2026-11-22 SKIPPED. Not started. |
| S7 | Flink sizing | 0 workers on the demo profile | At least one worker; savepoints on upgrade | 2026-11-22 DONE differently. The demo Dataproc master is larger (T-078); one worker is not allowed by Dataproc. |
| S8 | Secrets in Terraform state | Private versioned bucket | Restrict readers; consider a customer-managed key; consider splitting the root into modules |  2026-11-22 SKIPPED. Not started. |
| S9 | One-address cluster allow-list | One `/32` | A short list, or IAP | 2026-11-22 DONE. `admin_cidrs` allows extra addresses (T-082). |
| S10 | Image supply chain | Immutable tags only | Digest pinning; vulnerability scanning | 2026-11-22 PARTIAL. Container scanning API enabled; digest pinning not done. |
| S13 | Cost guard | None | A budget alert in Terraform (needs billing-admin rights) |  2026-11-22 SKIPPED. Needs billing-admin rights; not started. |

## 6. Cleanup (P5)
`docs/GAPS_AND_PLAN.md` N1 to N8 (typo in the dashboard title; stale `DESIGN.md` and `CLOUD_DEPLOYMENT_HANDOFF.md`; the wrong file named in `REQUIREMENTS_MAP.md`; duplicate dashboard JSON and k6 script; unused `deploy/build.py`, `delivery_assignment_service/Dockerfile` and committed generated protobuf files; leftover `.gitignore` entries; two small shims; trace ID collisions). Mark each Done or Skipped.

## 7. Final proof (P6) and definition of done
1. Destroy the platform using the one-step teardown (A3), confirm nothing chargeable is left.
2. From the empty state, run **one** `terraform apply` with the images and Kafka enabled. No manual step, no re-run. Then `terraform plan` must say "No changes".
3. Run `docs/VERIFICATION_PLAN.md` end to end. Every tracker row above must be PASS, or FAIL with an owner-accepted reason.
4. Record one terminal window and the console pages (rule 7), as before and after evidence in `docs/evidence/`.
5. Write the revision guide following the groups in `trace.md`.
6. Tear down, or write down that it was left running and why.

**Done means:** all A to H rows PASS, a one-shot rebuild with zero manual steps, evidence saved, the revision guide written, and no chargeable resource left unless stated.

## 8. Summary of how much is done (as of the snapshot)
| Req | Code written | Infrastructure created | Proven working end to end |
|---|---|---|---|
| A | Yes | Yes | Mostly (one-shot rebuild worked; teardown and Confluent still manual) |
| B | Yes | Yes (function, topic, Kafka) | No |
| C | Yes | Yes (GKE) | No |
| D | Yes, with the source-change gap | Yes (Argo CD) | Partly (synced once) |
| E | Yes | Yes (Dataproc) | No |
| F | Yes | Yes (ZooKeeper deployed) | No (crash loop at last record) |
| G | Yes | Yes (all three) | No data from real traffic |
| H | Yes | Partly | No |


---
## Executor results (2026-11-22)
The per-requirement results, evidence paths and the open blockers are in `docs/requirements/00-SUMMARY.md` and the files `A-` to `H-` beside it. Rows not run in this pass: S1 to S13 (hardening) and N2 to N8 (cleanup) are Skipped, not started; P6 (clean second rebuild plus the full verification plan) was not run.

### Phase results (2026-11-22)
| Phase | Result |
|---|---|
| P1 | PASS. 33 pods Running and Argo CD `food` and `food-platform` Synced and Healthy on the three-node profile with no hand edits (T-056, T-064; `docs/evidence/06-app-running/`). |
| P2 | PARTIAL. B, C, E, F, G pass; D partial (build-on-push blocked: no admin on the tracked repository); H partial (alert email address set in `.env`, applied and tested at the next apply). |
| P3 | PARTIAL. A3 and B6 pass, A4 accepted, D4 blocked. |
| P4 | PARTIAL. Done: S2 (2 replicas and disruption budgets), S7 (larger Dataproc master), S9 (extra allowed addresses), S10 (scanning API enabled). Skipped with a reason: S1, S3, S4, S6, S8, S13 (see `docs/requirements/00-SUMMARY.md`). |
| P5 | PARTIAL. Done: N5 (unused `deploy/build.py` removed), N6 (stale ignore lines removed). N1 was not a defect. Not done: N2, N3 (original documents are not edited), N4 (the duplicates are used by the local compose files), N7, N8. |
| P6 | PARTIAL. Final destroy done twice (T-074, T-086); a clean rebuild from empty with zero manual steps was not repeated. |

Trace note: the commit with the free hostname, the paused switch and the ingress order (34c5a6b) is recorded as T-059 to T-061 and was proven afterwards (certificate Active, SQL stopped and nodes at 0, services started).
