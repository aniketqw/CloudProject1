# Service Map: which files belong to which service

Paths are relative to the repo root. Descriptions come from each file's own opening docstring. Files marked "(no docstring)" are described from their imports and names only. Ports and infrastructure come from `DESIGN.md`, `compose.yaml` and the Terraform in `deploy/terraform/cloud/`.

The whole system is one Python image (`Dockerfile.local`) that runs a different module per workload (`deploy/process_runner.py`), plus a Java Flink job and a Cloud Function.

## The eight services

### 1. Customer Service: customer profiles and delivery addresses
- **Code** (`customer_service/`): `customer_service.py` (Flask API and logic, no docstring), `models.py` (customer-owned tables), `validation.py` (field validation that never echoes personal data).
- **Port / state:** 8083, MySQL. Autoscaled (HPA).
- **Unit tests:** `tests/test_customer_service.py`. **Local scripts:** `local/customer_smoke_test.py`.

### 2. Restaurant Service: menus, opening status, preparation estimates
- **Code** (`restaurant_service/`):
  - `restaurant_service.py` (gRPC API), `restaurant.proto` (its contract), `restaurant_pb2.py` and `restaurant_pb2_grpc.py` (generated from the proto).
  - `http_api.py` (HTTP facade, no docstring), `domain.py` (validated restaurant data), `repository.py` (Firestore access, no docstring).
  - Streaming analytics: `analytics_api.py` (read-only aggregate API), `analytics_contract.py` (counts and window bounds only), `analytics_results.py` (Kafka results into Firestore), and `analytics/` (the Java Flink job: `pom.xml`, `Dockerfile`, `src/main/java/.../RestaurantAnalytics.java`).
- **Ports / state:** gRPC 50051, HTTP 8084, analytics API 8091. Firestore. The Flink job runs on Dataproc, reading Kafka `orders` and writing `restaurant_analytics_results`.
- **Unit tests:** `tests/test_restaurant_service.py`, `tests/test_analytics_contract.py`. **Local scripts:** `local/restaurant_smoke_test.py`, `local/analytics_smoke_test.py`.

### 3. Order Service: creates orders and keeps their state
- **Code** (`order_service/`): `domain.py` (request contracts, idempotency hashes, lifecycle rules), `models.py` (order tables), `schema.py`, `storage.py` (no docstring), `events.py` (atomic order event plus outbox write), `outbox.py` (at-least-once Kafka relay), `event_producer.py` and `event_consumer.py` (no docstring; the consumer is the "kitchen-worker"), `dependencies.py` (calls to Customer, Restaurant and Scheduler, no docstring).
- **Port / state:** 8081, MySQL (orders, outbox, idempotency). Kafka topic `orders`. gRPC client to Restaurant. Autoscaled (HPA).
- **Unit tests:** `tests/test_order_service.py`, `tests/test_order_outbox.py`, `tests/order_fixtures.py`. **Local scripts:** `local/order_smoke_test.py`, `local/order_recovery_test.py`.

### 4. Task Scheduler: creates tasks, assigns leases, reclaims abandoned work
- **Code** (`task_scheduler/`): `store.py` (the core: transactional scheduler state and fenced leases, 474 lines), `domain.py` (immutable task graphs), `models.py`, `schema.py`, `storage.py`, `leader.py` (ZooKeeper leader election with SQL epochs), `coordination.py`, `fencing.py` (fence destination writes with a ZooKeeper proof), `worker.py`, `api.py`, `runtime.py` (heartbeat and HTTP helpers).
- **Port / state:** 8085, MySQL plus a 3-node ZooKeeper. Runs as API, leader and worker replicas.
- **Unit tests:** `tests/test_task_scheduler.py`. **Local scripts:** `local/scheduler_smoke_test.py`, `local/scheduler_recovery_test.py`.

### 5. Kitchen Workflow Service: acceptance and preparation stages
- **Code** (`kitchen_workflow/`): `store.py` (durable kitchen actions), `domain.py`, `models.py`, `schema.py`, `api.py`, `worker.py`, `projection.py` (monotonic Firestore view), `sync.py`.
- **Port / state:** 8087, MySQL, Firestore projection, Kafka consumer (publishes `kitchen_status`).
- **Unit tests:** `tests/test_kitchen_workflow.py`. **Local scripts:** `local/kitchen_smoke_test.py`, `local/kitchen_recovery_test.py`.

### 6. Delivery Assignment Service: allocates couriers, tracks assignments
- **Code** (`delivery_assignment_service/`): `store.py` (atomic courier allocation), `domain.py` (synthetic fleet inputs), `models.py`, `schema.py`, `policy.py` (eligibility shared with the scheduler), `outbox.py` (ordered publication), `worker.py`, `api.py`, `das.py` (compatibility entry point), plus a separate `Dockerfile` and `Dockerfile.dockerignore`.
- **Port / state:** 8082, MySQL. Kafka outbox to `delivery_assignments`.
- **Unit tests:** `tests/test_delivery_service.py`. **Local scripts:** `local/delivery_smoke_test.py`, `local/delivery_recovery_test.py`, `local/delivery_demo.py`.

### 7. Payment Service: simulated payment success, failure and safe retries
- **Code** (`payment_service/`): `store.py` (durable simulated payments with atomic order and outbox writes), `provider.py` (SQL-backed simulated provider), `domain.py`, `models.py`, `schema.py`, `api.py`, `worker.py`, `fencing.py` (compatibility import of the shared fencing protocol).
- **Port / state:** 8086, MySQL. Checks the scheduler's fencing proof before committing.
- **Unit tests:** `tests/test_payment_service.py`. **Local scripts:** `local/payment_smoke_test.py`, `local/payment_recovery_test.py`.

### 8. Notification Service: order, preparation and delivery progress
- **Code** (`notification_service/`): `ingest.py` (idempotent materialization of facts), `consumer.py` (Kafka consumer, commits offsets after the database write), `store.py`, `domain.py` (fixed templates), `models.py`, `schema.py`, `policy.py`, `provider.py` (in-app transport), `reconcile.py`, `cloud_transport.py` (publishes to Pub/Sub, accepts delivery only after the function's GCS receipt), `worker.py`, `api.py`.
- **Cloud Function:** `functions/notification_transport/` (`main.py`, `requirements.txt`, `Dockerfile`, `tests/test_contract.py`) writes the receipt object to GCS.
- **Port / state:** 8088, MySQL, Kafka consumer, Pub/Sub, GCS.
- **Unit tests:** `tests/test_notification_service.py`. **Local scripts:** `local/notification_smoke_test.py`, `local/notification_recovery_test.py`, `local/function_bridge.py`.

## Not one of the eight, but part of the system

| Area | Files | What it is |
|---|---|---|
| Web UI (port 3000) | `web_ui/app.py`, `state.py`, `client.py`, `demo.py`, `analytics.py`, `templates/`, `static/` | Customer, kitchen, courier and operations pages. Calls the services over HTTP; keeps its own SQLite state. Tests: `tests/test_web_ui.py`, `tests/test_web_ui_poll.mjs`, `local/web_smoke_test.py`. |
| Shared code | `common/` (`deployment.py`, `kafka.py`, `database_options.py`, `observability.py`, `logging.py`, `web_access.py`) | Profiles (local or cloud), Kafka and database settings, logging and metrics, the operator access gate. |
| Runtime entry points | `deploy/process_runner.py`, `deploy/application.py`, `deploy/initialize.py` | How each workload starts (process wrapper, gunicorn app factory, ordered schema init). |
| Infrastructure as code | `deploy/terraform/cloud/` (single root), `deploy/terraform/modules/argocd/`, `deploy/terraform/state/` (one-time bucket bootstrap) | See the Terraform section below. |
| Kubernetes config | `deploy/charts/food/` (workloads, HPAs, ingress, ZooKeeper, init jobs), `deploy/charts/platform/` (monitoring, external-secrets), `deploy/environments/` | Applied by Argo CD from Git. |
| Deployment tooling (Python) | `deploy/cloud_stage.py`, `configure.py`, `secret_inputs.py`, `build.py`, `lifecycle*.py`, `dataproc_submit.py`, `flink_control.py`, `verify.py`, `capture_scaling.py`, `export_handoff.py`, `local_cluster.py`, `local_proxy.py`, `observability_check.py`, `capacity.py`, `commands.py`, `profiles.json` | Wrappers and operations around the infrastructure. Several of these are what the IaC requirement wants removed or replaced. |
| Local run and tests | `compose.yaml`, `compose.assignment.yaml`, `Dockerfile.local`, `local/`, `tests/` | Docker Compose with emulators; per-service smoke and recovery scripts. |
| Observability and load | `observability/`, `load/sustained.js` | Local Prometheus, Loki, Grafana and Fluent Bit configs; the k6 load test. |

## Things that look redundant (candidates for the refactor)
Checked on 2026-11-21:
- `observability/grafana/dashboards/system.json` and `deploy/charts/platform/dashboards/system.json` are **byte-identical**.
- `load/sustained.js` and `deploy/charts/food/load/sustained.js` are **byte-identical**.
- `restaurant_service/restaurant_pb2.py` and `restaurant_pb2_grpc.py` are committed, but `Dockerfile.local` regenerates them from the `.proto` during the build.
- `delivery_assignment_service/Dockerfile` (Python 3.10) is not used by the Terraform, the charts or Compose, which all use `Dockerfile.local` (Python 3.12). It is only named in the handoff export allowlist.
- `delivery_assignment_service/das.py` and `payment_service/fencing.py` are small compatibility shims.
- `deploy/` mixes runtime code that ships in the image with operator tooling. The image copies all `deploy/*.py`.

## Terraform: one entry point
**Today:** the entry point is `deploy/terraform/cloud/`. `terraform -chdir=deploy/terraform/cloud init` then `apply` creates the network, GKE, Cloud SQL, Firestore, buckets, Pub/Sub, Eventarc, the function, Dataproc, Kafka topics, secrets, IAM, Argo CD, and now builds and pushes the images. The only separate piece is `deploy/terraform/state/`, run once, because the remote-state bucket must exist before a backend can use it.

**Guideline:** HashiCorp's standard module structure is one root module (`main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`) with reusable pieces under `modules/`, applied from one directory. This is from my knowledge of their docs and was not re-fetched during this session. The current layout follows it, except the root lives under `deploy/terraform/cloud/` instead of a top-level folder and is not yet split into `modules/` (only `modules/argocd/` is).

**Options to make it even simpler:**
- (A) Keep it as is and document `terraform -chdir=deploy/terraform/cloud apply`. Least change.
- (B) Move the root to a top-level `terraform/` folder and split network, data, messaging, compute and iam into `modules/`. Most conventional, and good for the revision guide, but touches many paths.
- (C) Remove the state bootstrap step by creating the state bucket in the same root and migrating state once with `terraform init -migrate-state`. Fewer commands, but a two-pass first run.
