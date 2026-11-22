# Demo runbook: commands you run yourself, and what each one proves

Use this to show each requirement in person. Every block says what to run, what you should see, what it proves, and which picture was taken (`P` = picture to capture or already captured in `docs/evidence/`). Status: **commands marked [run] were run during this project; [to run] will be run and photographed at the next live window.** Update the status here as each one is done.

Common setup (once per terminal):
```bash
cd "<repo>/CloudProject1"
set -a; source .env; set +a                       # loads every TF_VAR_* and DOCKER_HOST; prints nothing
export CLOUDSDK_AUTH_ACCESS_TOKEN="$(gcloud auth application-default print-access-token)"
gcloud container clusters get-credentials "${TF_VAR_prefix}-gke" --zone "$TF_VAR_zone"   # needs gke-gcloud-auth-plugin
kubectl get nodes                                 # 3 nodes Ready
```
If the auth plugin is missing, `deploy/kubecfg` style token files were used in this project (see the scratchpad helper described in trace T-062); installing the plugin is simpler: `gcloud components install gke-gcloud-auth-plugin`.

## A. Infrastructure as Code
| Step | Command | You should see | Proves | Responsible code | Status |
|---|---|---|---|---|---|
| A-1 | `terraform -chdir=deploy/terraform/cloud apply` | "Apply complete! Resources: ~96 added" (about 12 minutes) | One command builds everything, including images | `deploy/terraform/cloud/` all `.tf` files; entry `main.tf`; images and jar: `artifacts.tf`; Argo CD: `argocd.tf` + `deploy/terraform/modules/argocd/main.tf` | [run] P: `evidence/02-platform` |
| A-2 | `terraform -chdir=deploy/terraform/cloud plan` | "No changes. Your infrastructure matches the configuration." | Code equals reality | `terraform plan` over the same files; state in `deploy/terraform/state/` (bucket) via `versions.tf` backend | [run] `evidence/12-plan-no-changes/` |
| A-3 | `ls deploy/terraform/cloud/*.tf \| wc -l; find . -name '*.tf.json' \| wc -l` | the .tf count, then 0 | HCL only, no generated JSON | `deploy/terraform/cloud/` (16 `.tf` files, no generated JSON) | [run] |
| A-4 | `gcloud container clusters list; gcloud sql instances list; gcloud dataproc clusters list --region $TF_VAR_region` | GKE, Cloud SQL and Dataproc exist | Created by Terraform | `gke.tf`, `database.tf`, `dataproc.tf`, sizes in `deploy/profiles.json` | [run] |
| A-5 | `terraform -chdir=deploy/terraform/cloud apply -var paused=true` then `-var paused=false` | nodes go to 0 and SQL stops; then everything returns, data kept | Pause is Terraform, not Python | `variables.tf` (`paused`), `gke.tf` (node count 0), `database.tf` (`activation_policy`), `argocd.tf` (ZooKeeper budget off) | [run] T-061, T-066 |
| A-6 | Teardown, two commands: `TF_VAR_deletion_protection=false TF_VAR_force_destroy_buckets=true TF_VAR_firestore_delete_on_destroy=true terraform -chdir=deploy/terraform/cloud apply` then the same variables with `destroy` | "Destroy complete" in about 15 minutes; only the free network connection may remain | One-step teardown without manual help | `variables.tf` switches (`deletion_protection`, `force_destroy_buckets`, `firestore_delete_on_destroy`), `kafka.tf`, helper `deploy/argo_unstick.sh` started by `argocd.tf` (`terraform_data.argo_unstick`) | [run] T-086 |

## B. Services, REST, gRPC, queues, function
Port-forward once: `kubectl -n food port-forward svc/customer-service 8083:8083 &` (also `restaurant-api 8084`, `order-service 8081`, `payment-service 8086`, `notification-api 8088`).
| Step | Command | You should see | Proves | Responsible code | Status |
|---|---|---|---|---|---|
| B-1 | create customer, address, restaurant, menu item (`POST /customers`, `/customers/<id>/addresses`, `/restaurants`, `PUT /restaurants/<id>/menu/meal`) | JSON with ids | REST between client and services | `customer_service/` (customers), `restaurant_service/http_api.py` + `repository.py` (restaurants, menu in Firestore) | [run] `evidence/07-order-flow/` |
| B-2 | `curl -X POST localhost:8081/orders -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-order-0001' -d '{"customer_id":1,"address_id":1,"restaurant_id":"<id>","items":[{"item_id":"meal","quantity":1}]}'` | HTTP 201, total 10000 (from the menu) | REST plus gRPC: Order asked Restaurant for the price | `order_service/event_producer.py` (`POST /orders`), gRPC client `order_service/dependencies.py` (`grpc.insecure_channel`), server `restaurant_service/restaurant_service.py`, contract `restaurant_service/restaurant.proto` | [run] |
| B-3 | `kubectl -n food logs deploy/order-service --tail=30` | request lines from the order service | the same call in the logs | `common/logging.py` (log format), `order_service/event_producer.py` | [to run] P |
| B-4 | `curl -X POST localhost:8086/payments/orders/<order id> -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-pay-0001' -d '{"expected_version":1,"scenario":"success"}'`, then `curl localhost:8081/orders/<id>` | order PAID within about 10 s | queue (Kafka), scheduler, ZooKeeper lease, worker | `payment_service/api.py` (`/payments/orders/<id>`), `task_scheduler/` (tasks), `payment_service/worker.py` (worker), `order_service/event_consumer.py` (status back to the order) | [run] |
| B-5 | `kubectl run kc --rm -i --restart=Never --image=python:3.12-slim ...` consumer script (see `evidence/07-order-flow/ORDER-FLOW.md`) | an `OrderCreated` message | Kafka really carries the event | `order_service/outbox.py` (Kafka producer, transactional outbox), `order_service/events.py`; topics `deploy/terraform/cloud/kafka.tf` | [run] |
| B-6 | `gcloud storage ls -r gs://$TF_VAR_project_id-$TF_VAR_prefix-receipts/` and `gcloud functions logs read ${TF_VAR_prefix}-notification-transport --gen2 --region $TF_VAR_region --limit 5` | a receipt object and function log lines | Pub/Sub, Eventarc and the serverless function | `notification_service/consumer.py` and `cloud_transport.py` (publish to Pub/Sub), function `functions/notification_transport/main.py`, Pub/Sub topic, Eventarc trigger and function `deploy/terraform/cloud/messaging.tf`, bucket `storage.tf` | [run] |
| B-7 | open `https://<ip-with-dashes>.sslip.io` (name from `kubectl -n food get ingress`) | page loads with a valid certificate (login prompt) | external HTTPS | `deploy/charts/food/templates/ingress.yaml` (certificate, ingress), hostname `main.tf` (`local.public_host`), address `network.tf` | [run] |

## C. Autoscaling and load
| Step | Command | You should see | Proves | Responsible code | Status |
|---|---|---|---|---|---|
| C-1 | `kubectl -n food get hpa` | two HPAs, min 2, max 4 | HPAs on two services | `deploy/charts/food/templates/workloads.yaml` (HorizontalPodAutoscaler block), values `deploy/charts/food/values.yaml` (`hpa`), minimum in `argocd.tf` | [run] |
| C-2 | in `deploy/charts/food/values.yaml` set `loadTest.enabled: true`, a new `runId`, `VUS: "20"`; `git commit; git push origin iac-integration` | Argo CD starts the k6 job within about 3 minutes | load test through GitOps | `deploy/charts/food/templates/load.yaml` (k6 job), script `deploy/charts/food/load/sustained.js` (copy `load/sustained.js`), switch in `values.yaml` (`loadTest`) | [run] |
| C-3 | `kubectl -n food get hpa -w` | replicas rise to 4 under load, fall after | scale-out and scale-in | `workloads.yaml` (HPA behaviour), resource sizes `argocd.tf` (`http_resources`) | [run] `evidence/17-load-tuning/` P |
| C-4 | `kubectl -n food logs job/food-load-<runId> \| grep K6_SUMMARY` | requests, rate, p95 under 2000 ms | thresholds passed | thresholds in `load/sustained.js` (`thresholds`) | [run] |
| C-5 | Cloud console, Monitoring, Dashboards, "food platform" | tiles with pod and CPU series | Cloud Monitoring shows it | `deploy/terraform/cloud/monitoring.tf` (dashboard and alert policies) | [run] P `evidence/20-flink-and-console/` |

## D. GitOps
| Step | Command | You should see | Proves | Responsible code | Status |
|---|---|---|---|---|---|
| D-1 | `kubectl -n argocd port-forward svc/argocd-server 8443:443 &` then open https://localhost:8443 (read-only view needs `TF_VAR_argocd_anonymous_view=true`) | applications `food` and `food-platform`, Synced, Healthy | controller installed and tracking Git | Argo CD install `deploy/terraform/modules/argocd/main.tf`; the two applications `argocd.tf` (`module "argocd"`); read-only option `argocd_anonymous_view` in `variables.tf` | [run] P `evidence/14-screenshots/` |
| D-2 | `kubectl -n argocd get applications` | both Synced Healthy | same, in text | same files; sync settings in `argocd.tf` (`local.sync_policy`: automated, prune, selfHeal, retry) | [run] |
| D-3 | edit a chart value, push, `kubectl -n argocd get application food -w` | OutOfSync, then Synced | updates flow from Git | `deploy/charts/food/` is what Argo CD renders; branch from `git_revision` variable | [run] |
| D-4 | `kubectl -n food scale deploy web-ui --replicas=3; sleep 10; kubectl -n food get deploy web-ui` | back to 1 replica | self-heal | `argocd.tf` `sync_policy.automated.selfHeal = true` | [run] |
| D-5 | change application source, push; the workflow builds, tags, commits `imageTag`; Argo rolls it out | new pods with the new tag | build-on-push | `.github/workflows/build-image.yml`, Google side `deploy/terraform/cloud/cicd.tf`, release tag `deploy/environments/team/image.yaml` | [run] `evidence/19-build-on-push/` |
| D-6 | `grep -rn "kubectl apply" deploy/ \| wc -l` | 0 | no kubectl apply in the deploy path | deployment path = `deploy/terraform/` and `deploy/charts/`; no `kubectl apply` in them | [run] |

## E. Flink
| Step | Command | You should see | Proves | Responsible code | Status |
|---|---|---|---|---|---|
| E-1 | `gcloud dataproc jobs list --region $TF_VAR_region` | `food-analytics-...` RUNNING | job on a managed cluster | submit step `deploy/dataproc_submit.py` run by `deploy/charts/food/templates/analytics-job.yaml` (PostSync hook); cluster `deploy/terraform/cloud/dataproc.tf` | [run] |
| E-2 | Cloud console, Dataproc, cluster, Web Interfaces, Flink | job RUNNING, checkpoints completing | the streaming job | job code `restaurant_service/analytics/src/main/java/org/fooddelivery/analytics/RestaurantAnalytics.java` | [to run] P (needs a Google sign-in) |
| E-3 | place orders for a minute or two, then `curl -H "Authorization: Bearer $CLOUDSDK_AUTH_ACCESS_TOKEN" "https://firestore.googleapis.com/v1/projects/$TF_VAR_project_id/databases/(default)/documents/restaurant_analytics_v1"` | one document per restaurant per minute | results appear | windows in `RestaurantAnalytics.java` (`Windows`), results copied by `restaurant_service/analytics_results.py`, collection `restaurant_analytics_v1` (`database.tf`) | [run] `evidence/16-flink-results/` |
| E-4 | publish a duplicate and a malformed event to `orders` (script in the evidence README) | window counts unchanged | duplicates and invalid events ignored | dedup and validation in `RestaurantAnalytics.java` (validated events, unique orders), contract `restaurant_service/analytics_contract.py` | [run] |
| E-5 | `gcloud logging read 'logName:"dataproc.job.yarn.container"' --limit 5` | Flink container lines | job logs reach Cloud Logging | log properties in `dataproc.tf` (`override_properties`) | [run] `evidence/13-logs/` |

## F. ZooKeeper
| Step | Command | You should see | Proves | Responsible code | Status |
|---|---|---|---|---|---|
| F-1 | `kubectl -n food get pods -l app=zookeeper` | 3 pods 1/1 | ensemble healthy | `deploy/charts/food/templates/zookeeper.yaml` (StatefulSet, headless Service, budget) | [run] |
| F-2 | `kubectl -n food port-forward svc/task-api 8085:8085 &; curl localhost:8085/scheduler` | leader name and epoch | who is leader | `task_scheduler/leader.py` (election), `task_scheduler/api.py` (`/scheduler`), `task_scheduler/coordination.py` | [run] |
| F-3 | `kubectl -n food delete pod <leader>`; repeat F-2 | another leader, higher epoch | election after failure | `task_scheduler/leader.py`, epoch and fencing `task_scheduler/fencing.py` | [run] `evidence/09-failover/` |
| F-4 | `kubectl -n food delete pod -l app=payment-worker` right after a payment | order still PAID, one capture | no duplicate work | leases `task_scheduler/coordination.py` (`create_lease`), worker loop `payment_service/worker.py`, fencing `payment_service/fencing.py` | [run] |
| F-5 | `kubectl -n food delete pod zookeeper-1 zookeeper-2 --grace-period=0 --force`; repeat F-2 | unavailable for seconds, then back, epoch higher | quorum loss and recovery | session handling `coordination.py` (`strict_session`, `live`), `zookeeper.yaml` (3 replicas, `podManagementPolicy: Parallel`) | [run] |
| F-6 | unauthenticated ZooKeeper read is refused (after the ACL work) | `NoAuth` | access control | ACL work: `task_scheduler/coordination.py` (planned) | [run] `evidence/18-zookeeper-acl/` |

## G. Data stores
| Step | Command | You should see | Proves | Responsible code | Status |
|---|---|---|---|---|---|
| G-1 | `curl localhost:8081/orders/<id>` | the order | Cloud SQL | `order_service/models.py`, `storage.py`, `common/database_options.py`; instance `database.tf` | [run] |
| G-2 | `curl localhost:8084/restaurants/<id>` | the restaurant | Firestore | `restaurant_service/repository.py`; Firestore `database.tf` | [run] |
| G-3 | B-6 above | receipt object | Cloud Storage | `storage.tf` (receipts bucket), `functions/notification_transport/main.py` | [run] |

## H. Observability
| Step | Command | You should see | Proves | Responsible code | Status |
|---|---|---|---|---|---|
| H-1 | `kubectl -n monitoring port-forward svc/food-platform-grafana 3030:80 &` open http://localhost:3030 , dashboard "Supper - application and Kubernetes" | six panels with data | dashboard | dashboard `deploy/charts/platform/dashboards/system.json`; Grafana and Prometheus installed by the `food-platform` application (`deploy/charts/platform/`); metrics `common/observability.py`, `deploy/charts/food/templates/metrics.yaml` | [run] P `evidence/14-screenshots/` |
| H-2 | `kubectl -n monitoring port-forward svc/monitoring-prometheus 9090:9090 &; curl 'localhost:9090/api/v1/targets?state=active'` | targets up | Prometheus scraping | `deploy/charts/platform/templates/` (scrape configuration), `metrics.yaml` | [run] |
| H-3 | `gcloud logging read 'resource.type="k8s_container" AND resource.labels.namespace_name="food"' --limit 5` | container logs | central logging | `common/logging.py`, `dataproc.tf` log properties | [run] `evidence/13-logs/` |
| H-4 | `gcloud monitoring policies list` | three policies, one email channel | alerts | `deploy/terraform/cloud/monitoring.tf` (policies, `google_monitoring_notification_channel.email`), `variables.tf` (`alert_email`) | [run] `evidence/21-alert-email/` |

How the pictures were taken: browser pages with headless Chrome driven over its debugging port (`docs/evidence/14-screenshots/`), console pages with a signed-in browser. Rules: one terminal window only for recordings; nothing with passwords or tokens.
