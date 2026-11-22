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
| Step | Command | You should see | Proves | Status |
|---|---|---|---|---|
| A-1 | `terraform -chdir=deploy/terraform/cloud apply` | "Apply complete! Resources: ~96 added" (about 12 minutes) | One command builds everything, including images | [run] P: `evidence/02-platform` |
| A-2 | `terraform -chdir=deploy/terraform/cloud plan` | "No changes. Your infrastructure matches the configuration." | Code equals reality | [run] `evidence/12-plan-no-changes/` |
| A-3 | `ls deploy/terraform/cloud/*.tf \| wc -l; find . -name '*.tf.json' \| wc -l` | the .tf count, then 0 | HCL only, no generated JSON | [run] |
| A-4 | `gcloud container clusters list; gcloud sql instances list; gcloud dataproc clusters list --region $TF_VAR_region` | GKE, Cloud SQL and Dataproc exist | Created by Terraform | [run] |
| A-5 | `terraform -chdir=deploy/terraform/cloud apply -var paused=true` then `-var paused=false` | nodes go to 0 and SQL stops; then everything returns, data kept | Pause is Terraform, not Python | [run] T-061, T-066 |
| A-6 | Teardown, two commands: `TF_VAR_deletion_protection=false TF_VAR_force_destroy_buckets=true TF_VAR_firestore_delete_on_destroy=true terraform -chdir=deploy/terraform/cloud apply` then the same variables with `destroy` | "Destroy complete" in about 15 minutes; only the free network connection may remain | One-step teardown without manual help | [run] T-086 |

## B. Services, REST, gRPC, queues, function
Port-forward once: `kubectl -n food port-forward svc/customer-service 8083:8083 &` (also `restaurant-api 8084`, `order-service 8081`, `payment-service 8086`, `notification-api 8088`).
| Step | Command | You should see | Proves | Status |
|---|---|---|---|---|
| B-1 | create customer, address, restaurant, menu item (`POST /customers`, `/customers/<id>/addresses`, `/restaurants`, `PUT /restaurants/<id>/menu/meal`) | JSON with ids | REST between client and services | [run] `evidence/07-order-flow/` |
| B-2 | `curl -X POST localhost:8081/orders -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-order-0001' -d '{"customer_id":1,"address_id":1,"restaurant_id":"<id>","items":[{"item_id":"meal","quantity":1}]}'` | HTTP 201, total 10000 (from the menu) | REST plus gRPC: Order asked Restaurant for the price | [run] |
| B-3 | `kubectl -n food logs deploy/order-service --tail=30` | request lines from the order service | the same call in the logs | [to run] P |
| B-4 | `curl -X POST localhost:8086/payments/orders/<order id> -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-pay-0001' -d '{"expected_version":1,"scenario":"success"}'`, then `curl localhost:8081/orders/<id>` | order PAID within about 10 s | queue (Kafka), scheduler, ZooKeeper lease, worker | [run] |
| B-5 | `kubectl run kc --rm -i --restart=Never --image=python:3.12-slim ...` consumer script (see `evidence/07-order-flow/ORDER-FLOW.md`) | an `OrderCreated` message | Kafka really carries the event | [run] |
| B-6 | `gcloud storage ls -r gs://$TF_VAR_project_id-$TF_VAR_prefix-receipts/` and `gcloud functions logs read ${TF_VAR_prefix}-notification-transport --gen2 --region $TF_VAR_region --limit 5` | a receipt object and function log lines | Pub/Sub, Eventarc and the serverless function | [run] |
| B-7 | open `https://<ip-with-dashes>.sslip.io` (name from `kubectl -n food get ingress`) | page loads with a valid certificate (login prompt) | external HTTPS | [run] |

## C. Autoscaling and load
| Step | Command | You should see | Proves | Status |
|---|---|---|---|---|
| C-1 | `kubectl -n food get hpa` | two HPAs, min 2, max 4 | HPAs on two services | [run] |
| C-2 | in `deploy/charts/food/values.yaml` set `loadTest.enabled: true`, a new `runId`, `VUS: "20"`; `git commit; git push origin iac-integration` | Argo CD starts the k6 job within about 3 minutes | load test through GitOps | [run] |
| C-3 | `kubectl -n food get hpa -w` | replicas rise to 4 under load, fall after | scale-out and scale-in | [run] `evidence/17-load-tuning/` P |
| C-4 | `kubectl -n food logs job/food-load-<runId> \| grep K6_SUMMARY` | requests, rate, p95 under 2000 ms | thresholds passed | [run] |
| C-5 | Cloud console, Monitoring, Dashboards, "food platform" | tiles with pod and CPU series | Cloud Monitoring shows it | [to run] P (Chrome) |

## D. GitOps
| Step | Command | You should see | Proves | Status |
|---|---|---|---|---|
| D-1 | `kubectl -n argocd port-forward svc/argocd-server 8443:443 &` then open https://localhost:8443 (read-only view needs `TF_VAR_argocd_anonymous_view=true`) | applications `food` and `food-platform`, Synced, Healthy | controller installed and tracking Git | [run] P `evidence/14-screenshots/` |
| D-2 | `kubectl -n argocd get applications` | both Synced Healthy | same, in text | [run] |
| D-3 | edit a chart value, push, `kubectl -n argocd get application food -w` | OutOfSync, then Synced | updates flow from Git | [run] |
| D-4 | `kubectl -n food scale deploy web-ui --replicas=3; sleep 10; kubectl -n food get deploy web-ui` | back to 1 replica | self-heal | [run] |
| D-5 | change application source, push; the workflow builds, tags, commits `imageTag`; Argo rolls it out | new pods with the new tag | build-on-push | [to run] after the fork work |
| D-6 | `grep -rn "kubectl apply" deploy/ \| wc -l` | 0 | no kubectl apply in the deploy path | [run] |

## E. Flink
| Step | Command | You should see | Proves | Status |
|---|---|---|---|---|
| E-1 | `gcloud dataproc jobs list --region $TF_VAR_region` | `food-analytics-...` RUNNING | job on a managed cluster | [run] |
| E-2 | Cloud console, Dataproc, cluster, Web Interfaces, Flink | job RUNNING, checkpoints completing | the streaming job | [to run] P (Chrome) |
| E-3 | place orders for a minute or two, then `curl -H "Authorization: Bearer $CLOUDSDK_AUTH_ACCESS_TOKEN" "https://firestore.googleapis.com/v1/projects/$TF_VAR_project_id/databases/(default)/documents/restaurant_analytics_v1"` | one document per restaurant per minute | results appear | [run] `evidence/16-flink-results/` |
| E-4 | publish a duplicate and a malformed event to `orders` (script in the evidence README) | window counts unchanged | duplicates and invalid events ignored | [run] |
| E-5 | `gcloud logging read 'logName:"dataproc.job.yarn.container"' --limit 5` | Flink container lines | job logs reach Cloud Logging | [run] `evidence/13-logs/` |

## F. ZooKeeper
| Step | Command | You should see | Proves | Status |
|---|---|---|---|---|
| F-1 | `kubectl -n food get pods -l app=zookeeper` | 3 pods 1/1 | ensemble healthy | [run] |
| F-2 | `kubectl -n food port-forward svc/task-api 8085:8085 &; curl localhost:8085/scheduler` | leader name and epoch | who is leader | [run] |
| F-3 | `kubectl -n food delete pod <leader>`; repeat F-2 | another leader, higher epoch | election after failure | [run] `evidence/09-failover/` |
| F-4 | `kubectl -n food delete pod -l app=payment-worker` right after a payment | order still PAID, one capture | no duplicate work | [run] |
| F-5 | `kubectl -n food delete pod zookeeper-1 zookeeper-2 --grace-period=0 --force`; repeat F-2 | unavailable for seconds, then back, epoch higher | quorum loss and recovery | [run] |
| F-6 | unauthenticated ZooKeeper read is refused (after the ACL work) | `NoAuth` | access control | [to run] |

## G. Data stores
| Step | Command | You should see | Proves | Status |
|---|---|---|---|---|
| G-1 | `curl localhost:8081/orders/<id>` | the order | Cloud SQL | [run] |
| G-2 | `curl localhost:8084/restaurants/<id>` | the restaurant | Firestore | [run] |
| G-3 | B-6 above | receipt object | Cloud Storage | [run] |

## H. Observability
| Step | Command | You should see | Proves | Status |
|---|---|---|---|---|
| H-1 | `kubectl -n monitoring port-forward svc/food-platform-grafana 3030:80 &` open http://localhost:3030 , dashboard "Supper - application and Kubernetes" | six panels with data | dashboard | [run] P `evidence/14-screenshots/` |
| H-2 | `kubectl -n monitoring port-forward svc/monitoring-prometheus 9090:9090 &; curl 'localhost:9090/api/v1/targets?state=active'` | targets up | Prometheus scraping | [run] |
| H-3 | `gcloud logging read 'resource.type="k8s_container" AND resource.labels.namespace_name="food"' --limit 5` | container logs | central logging | [run] `evidence/13-logs/` |
| H-4 | `gcloud monitoring policies list` | three policies, one email channel | alerts | [run], email [to run] |

How the pictures were taken: browser pages with headless Chrome driven over its debugging port (`docs/evidence/14-screenshots/`), console pages with a signed-in browser. Rules: one terminal window only for recordings; nothing with passwords or tokens.
