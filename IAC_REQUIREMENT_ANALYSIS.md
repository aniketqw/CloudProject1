# Requirement Analysis Log

This file records, requirement by requirement, what the repo has, whether the requirement is met, and what must change. Paths are relative to the repo root.

---

## Requirement 1: Infrastructure as Code

### Original text
> All cloud infrastructure (networks, clusters, databases, storage, IAM policies, etc.) across all cloud providers must be provisioned exclusively using an Infrastructure as Code (IaC) platform (e.g., Terraform).
>
> Needs `.tf` files and should work with `terraform apply`, not by using subprocess in Python.

### Rephrased
Every cloud resource must be declared in Terraform. One `terraform init && terraform apply` should create the whole environment. No Python (subprocess, SDK or CLI such as `gcloud`, `kubectl`, `docker`) may create or change cloud resources.

### System summary (for context)
Food-delivery platform with 8 Python/Flask services, a Flink analytics job (Java), and a web UI. It targets GCP (GKE, Cloud SQL MySQL, Firestore, GCS, Pub/Sub, Eventarc, Cloud Functions v2, Dataproc, Secret Manager, Artifact Registry) plus Confluent Cloud Kafka. No AWS or Azure. Local dev uses Docker Compose with emulators.

### Observation: IaC files found
- **No `*.tf` files exist.** Terraform is written as JSON, one root per stage:

| Root | Contents |
|---|---|
| `deploy/terraform/state/main.tf.json` | GCS bucket for Terraform state (local state) |
| `deploy/terraform/cloud/main.tf.json` | Main GCP stack: APIs, VPC, subnet, NAT, firewalls, private service access, GKE cluster and node pool, Dataproc, Cloud SQL, Firestore, 3 GCS buckets, Secret Manager, Pub/Sub, Eventarc, Cloud Function v2, Artifact Registry, DNS record (optional), static IPs, 11 service accounts, IAM bindings, Workload Identity |
| `deploy/terraform/kafka/main.tf.json` | 4 Confluent Kafka topics in an existing cluster |
| `deploy/terraform/controller/main.tf.json` | Argo CD via `helm_release` |
| `deploy/terraform/gitops/main.tf.json` | Argo root `Application` via `kubernetes_manifest` |

- Providers: google 7.25.0, random 3.7.2, confluent 2.50.0, helm 3.1.1, kubernetes 2.38.0.
- Other IaC: two Helm charts (`deploy/charts/platform`, `deploy/charts/food`) and Argo CD Applications (`deploy/environments/example/applications.yaml`). These are applied by Argo CD, not by Terraform.
- Stale files: `customer_service/`, `order_service/` and `restaurant_service/` each hold a `.terraform.lock.hcl` with no `.tf` file next to it.
- No Pulumi, CloudFormation, Bicep, Makefile, shell deploy scripts or CI workflows.

### Coverage

| Category | Where it is defined | In Terraform? |
|---|---|---|
| VPC, subnet, NAT, firewall, private service access | cloud root | Yes |
| GKE cluster and node pool | cloud root | Yes |
| Dataproc cluster | cloud root | Yes |
| Cloud SQL, Firestore | cloud root | Yes |
| GCS buckets | cloud root | Yes |
| Pub/Sub, Eventarc, Cloud Function | cloud root | Yes |
| IAM, service accounts, Workload Identity | cloud root | Yes |
| Secret Manager | cloud root | Yes |
| Artifact Registry repos | cloud root | Yes |
| Kafka topics | kafka root | Yes |
| Argo CD and root app | controller and gitops roots | Yes, but needs a live cluster and kubeconfig first |
| K8s workloads, HPAs, Ingress, certificates, ExternalSecrets | Helm via Argo CD | No |
| Monitoring (Prometheus, Grafana, dashboards) | Helm via Argo CD | No (no `google_monitoring_*`) |
| Container images and Flink jar (build and push) | `deploy/build.py` | No (docker, gcloud) |
| Function source ZIP | `deploy/configure.py:68-70` | No (Terraform only uploads it) |
| Flink job submission | `deploy/dataproc_submit.py` | No (Dataproc REST) |
| DB schemas, Firestore seed | `deploy/initialize.py` | No (Argo hook) |
| Pause and resume (GKE, SQL, Dataproc) | `deploy/lifecycle_cloud.py` | No (REST, kubectl, gcloud ssh) |
| GCP project and billing, gcloud auth | manual | No |
| Confluent cluster, API keys, ACLs | manual | No |
| Cloud DNS zone | manual (record is optional in Terraform) | No |

### Why it is not met
1. **Not one apply.** There are 5 roots applied in order through `deploy/cloud_stage.py`, which runs terraform through Python `subprocess` and applies a saved plan. `CLOUD_DEPLOYMENT_HANDOFF.md` (line 245) says not to run `terraform apply` directly.
2. **Cluster dependency.** `controller` and `gitops` need `gcloud container clusters get-credentials` and a kubeconfig, so they cannot be in the same apply as the cluster as written.
3. **Generated inputs.** Backend config and tfvars files are written by `deploy/configure.py`, and secrets by interactive prompts in `deploy/secret_inputs.py`. The `cloud` root also uses a partial `gcs {}` backend.
4. **Artifacts built outside Terraform.** A plain apply fails because the function ZIP does not exist. Images and the Flink jar are pushed by docker and gcloud.
5. **Runtime resources created by scripts.** Flink job submission and DB schema creation run from Python through Argo hooks. Pause and resume mutates infrastructure through REST and kubectl.
6. **Manual prerequisites.** The GCP project, auth, Confluent cluster and keys, and the DNS zone are created by hand.
7. **Format.** No `.tf` files, so a reviewer looking for Terraform will not find any.

### Verdict
**Partly met.** Most cloud resources are declared in Terraform, but the requirement "provisioned exclusively by IaC, with one `terraform apply` and no Python subprocess" is **not fulfilled**.

### Changes needed
1. Convert `main.tf.json` files to HCL (`main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`).
2. Merge into one root module (optionally split into `modules/`) with one backend and a committed `terraform.tfvars.example`. Keep the state-bucket bootstrap as a documented, single exception.
3. Configure the `kubernetes` and `helm` providers from the `google_container_cluster` outputs so Argo CD and the root app install in the same apply, with no kubeconfig step.
4. Produce artifacts from Terraform: `archive_file` for the function ZIP, and Cloud Build or a build resource for images and the Flink jar. At minimum, document pre-built image tags.
5. Replace Python provisioning:
   - Flink job as a Terraform resource (`google_dataproc_job` or a Kubernetes Job).
   - Schema and seed as a Terraform-managed Job.
   - Pause and resume as a `paused` variable applied with `terraform apply`.
6. Add what is missing: `google_monitoring_*` dashboards and alerts, and optionally the DNS zone and the Kafka cluster (confluent provider).
7. Pass secrets as `TF_VAR_*` or from Secret Manager instead of prompts.
8. Delete the stale `.terraform.lock.hcl` files and update the handoff doc to `terraform init && terraform apply`.

---

### Progress on Requirement 1 changes (details in `trace.md`)
| # | Change | Status |
|---|---|---|
| 1 | Convert JSON to HCL `.tf` | **Done** (Groups B, C, D in trace.md) |
| 2 | Merge into one root module | **Done** (Group E); state bucket bootstrap stays separate |
| 3 | Remove cluster-before-apply dependency | **Done** (Group E): helm provider built from the cluster; Argo root app via Helm chart |
| 4 | Move artifact production into Terraform | **Done** (Group G), not run against a real project; the Flink jar copy is one `local-exec` step |
| 5 | Replace Python provisioning | Not started |
| 6 | Add monitoring and other missing infra | **Done** for monitoring (Group I); DNS zone and Kafka cluster stay outside Terraform |
| 7 | Secrets as variables | **Done** (Group I): `TF_VAR_*`, `secret_inputs.py` removed |
| 8 | Delete stale lock files, update handoff doc | Lock files **done**; handoff doc not started |
