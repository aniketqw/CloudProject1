# Cloud deployment handoff and local source recovery

Prepared: 14 November 2026. Updated: 15 November 2026.

## 1. What is ready

The preserved, verified application baseline is commit **f82c4da7557d7c43993a50e06bf843182ed161a6**. The smaller capacity profile and lifecycle helpers were published to `main` in commit **2f05f2f76f2bacf5ede91378503d2345f7cc6dcb**. Start cloud deployment from the current `origin/main`, which includes those helpers; use the older baseline only for independent source recovery. Real-cloud validation is still pending.

The eight assigned services are implemented: Customer, Restaurant, Order, Task Scheduler, Kitchen Workflow, Delivery Assignment, Payment and Notification. Restaurant Service includes Flink streaming analytics. The UI has separate customer, kitchen, courier and operations pages, interactive charts and an execution graph showing real task prerequisites.

| Local verification completed | Result |
| --- | --- |
| Python application regressions | 332 passed in the updated source |
| Notification function contracts | 6 passed |
| JavaScript behavior checks | 3 passed |
| End-to-end ordering, payment retry, kitchen, courier and notification flow | Passed |
| Isolated Flink duplicate handling and checkpoint recovery contract | Passed |
| Prometheus targets and local observability check | 12 targets; passed |
| Browser charts, graph interaction and live updates | Checked |

The updated Python suite includes the lifecycle and database-pool contracts. Full Compose/browser/Flink execution evidence listed above was obtained for the preserved application baseline; the smaller managed-cloud profile has not been executed on GCP. These results verify local behavior and contracts. **GCP deployment, managed-service integration, public HTTPS and final cloud load/HPA acceptance remain to be completed before deployment can be considered finished.** Payments and notification delivery remain simulations for this assignment. Couriers use synthetic identities and explicit manual/scripted actions.

### Implementation scope and deployment responsibilities

The agreed application features and deployment helpers are implemented. No additional service, UI page or business workflow is planned for the current scope. The deployment operator's work is to configure accounts and resources, publish the release, deploy it and collect real cloud evidence. The first GCP deployment may still require focused configuration changes or bug fixes; the locally passing tests do not establish that every managed-service integration works.

| Area | Already supplied | Deployment responsibility |
| --- | --- | --- |
| Application | Eight domain services, simulated payments/notification delivery and synthetic courier actions | Run the complete order flow against the deployed services |
| Interface | Separate customer, kitchen, courier and operations pages, charts and task-dependency graph | Verify HTTPS access, interactions and live updates |
| Coordination | ZooKeeper ensemble, scheduling, ownership/leases, dependencies and recovery logic | Verify the actual GKE ensemble and abandoned-work recovery |
| Streaming analytics | Restaurant-owned Flink pipeline and savepoint/restart helpers | Verify managed Dataproc execution, committed results and restored state |
| Infrastructure | Unified Terraform roots, Helm charts, GitOps manifests and private secret-input prompts | Supply the reviewed settings, arrange permissions and apply the plans |
| Scaling and operations | Load workload, two HPAs, telemetry and pause/resume helpers | Run the required sustained load and a real pause/resume rehearsal |

Use this execution order: **section 5 checkout/tools -> section 6 settings/secrets -> section 7 infrastructure -> section 8 release build -> section 9 Git publication -> section 10 GitOps/DNS -> section 11 cloud acceptance -> section 14 pause/resume rehearsal**. Run stages individually and stop on the first failure. Plan/apply pairs require review between the two commands; do not paste the entire guide into one unattended shell run.

## 2. Source code preserved for independent recovery

A source-only recovery copy has been created locally:

- Local Git tag: `local-verified-f82c4da`, pointing to the verified commit above.
- Frozen source directory: `.local-build/recovery/food-delivery-f82c4da/verified-source/`.
- Source ZIP: `.local-build/recovery/food-delivery-f82c4da/verified-source.zip`.
- Per-file SHA-256 manifest: `.local-build/recovery/food-delivery-f82c4da/source-manifest.json`.
- Inventory: **247 tracked source/configuration files**.
- ZIP SHA-256: `5410adf2fb43125ea980a2e4a4c51608efe23f539a2238964454a3f7fc85501e`.

There are **no Docker image exports, private environment files, credentials, runtime database records or Git history in this source backup**. The recovery folder is ignored by Git and will not be pushed. The local tag has not been pushed.

Keep an additional copy of this small source ZIP and manifest somewhere outside the working checkout, such as your own backup folder. A Git-ignored folder can still be deleted by disk cleanup or `git clean -fdx`. Do not edit the frozen copy while deployment changes are being tested.

To check the ZIP in PowerShell, from the project root:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath .local-build/recovery/food-delivery-f82c4da/verified-source.zip
git rev-parse local-verified-f82c4da
```

If later changes break the code, use the frozen source directory or extract the ZIP to a separate working folder. You can then build and run that baseline yourself using the local commands in section 3. The local demo does not require GCP or Confluent access.

This preserves application code. It does not restore previous orders, Kafka offsets, cloud resources or database contents. The local Firestore emulator holds its data in memory; replacing/stopping it can lose its current contents. Do not use `docker compose down -v` or Docker volume pruning to recover code.

## 3. Running the local baseline later

No new recovery stack was started and no images were exported for this handoff. The following commands are instructions for a future source rebuild if needed.

Use PowerShell in the recovered source folder, with Docker Desktop running Linux containers and Python installed. Close other full demo stacks deliberately if memory is limited; running several copies can exhaust Docker memory.

```powershell
python -m deploy.build
docker compose -p food-assignment --env-file .env.local.example --env-file .env.assignment.example -f compose.yaml -f compose.assignment.yaml up -d --wait --wait-timeout 240
python -m deploy.verify smoke
python -m deploy.verify telemetry
```

`deploy.build` builds the application's runtime images from source when you choose to run it. It does not deploy to GCP without the release/publish flags used later in this guide.

| Local interface | URL |
| --- | --- |
| Application | http://127.0.0.1:3010 |
| Grafana | http://127.0.0.1:13000 |
| Prometheus | http://127.0.0.1:19090 |
| Flink | http://127.0.0.1:18092 |

Use the checked-in example environment files for this isolated local demo. Do not substitute cloud credentials, point it at a shared database, or mount a cloud service-account file. The local examples contain dummy local settings.

The project name above is `food-assignment`. It deliberately uses the normal local stack's ports and named volumes. Run one copy of that stack at a time; a recovered checkout is not a separate database backup.

## 4. Deployment prerequisites

Use individual accounts. Do not share account passwords or put secrets in chat.

| Requirement | What to confirm before provisioning |
| --- | --- |
| GCP project | Correct project ID and access for the deployer |
| Billing | Intended billing account is linked, verified and usable; check credit expiry and spending personally |
| Permissions | Deployer can enable APIs, manage the resources below, create service accounts and set the narrowly scoped IAM bindings defined in Terraform |
| Quotas | Sufficient regional CPU, VM, GKE, Cloud SQL and Dataproc capacity for the actual Terraform plan |
| Region/zone | Both belong together and support the selected managed resources and pinned runtime versions |
| DNS | A real hostname under your control; permission to add its A record |
| Confluent | Existing Kafka cluster endpoints/ID plus separate application and topic-administration credentials |
| GitHub | Ability to push a deployment branch and an immutable release tag |
| Deployment owner | One person coordinates Terraform state, release changes, secret versions and cleanup |

The infrastructure includes GKE, Cloud SQL, Firestore, Cloud Storage, Artifact Registry, Secret Manager, Pub/Sub, a notification function/trigger, managed Dataproc/Flink, networking, DNS when configured, and observability. Review the plan against the assignment and your budget before applying it.

A deployer needs appropriate access to these systems; giving every deployer the Owner role is unnecessary. Runtime identities and their permissions are declared in `deploy/terraform/cloud/main.tf.json`.

Previously public Confluent credentials must be replaced **and the old keys revoked by their owner**. Any previously public database password must be changed if that account/database is still active. Removing credentials from Git does not invalidate them. Do not reuse them for deployment.

### Information and access to arrange first

Collect non-secret identifiers and grant access through individual accounts before starting. This guide must never become a place to record actual passwords or API secrets.

| Item | What the deployment operator needs | Where it is used |
| --- | --- | --- |
| GCP | Project ID, region/zone, intended billing account, usable credits and required quotas | Non-secret configuration and reviewed infrastructure plan |
| GCP deployer | Permission to enable APIs, create the declared resources and manage the required service accounts/IAM; IAP/OS Login access for the lifecycle workflow | Individual CLI login and Application Default Credentials; see section 14 for lifecycle access |
| Network administration | The deployer's restricted public IPv4 CIDR; update it deliberately if their network changes | `admin_cidr` restricts cluster administration |
| Existing Firestore | Whether the intended default database already exists | Set `create_firestore` deliberately; do not attempt to recreate a shared database |
| Existing Confluent cluster | Cluster ID, Kafka bootstrap address and Kafka REST endpoint | Non-secret configuration |
| Confluent application identity | A fresh cluster-specific application API key/secret and the permissions used by the producers, consumers and Flink transactions | Hidden `deploy.secret_inputs cloud` prompts |
| Confluent topic administration | A separate authorized cluster-specific key/secret for topic administration | Hidden `deploy.secret_inputs kafka` prompts |
| Git repository | Read access for GitOps and write access for the deployment branch/release tag | Credential-free repository URL and published immutable release |
| DNS | A real hostname and ability to set its A record; an existing managed-zone name if using Cloud DNS | `public_host` and optional `dns_zone` |
| Release and state | A new unused release/image label, stable resource prefix and globally unique private state-bucket name | `git_revision`, `image_tag`, `prefix` and `state_bucket` |
| Application access | A non-secret operator username and a newly chosen passphrase | Username in configuration; passphrase entered only through the hidden prompt |

GCP CLI access and Application Default Credentials are configured with the two login commands in section 5. Use authorized individual access; routine deployment does not require sharing personal login credentials or downloading a service-account JSON key. See [Google local ADC setup](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment).

The Kafka Terraform root configures four topics in an **existing** Confluent cluster: `orders`, `kitchen_status`, `delivery_assignments` and `restaurant_analytics_results`. New topics default to three partitions. Before adopting existing topics, record their actual partition counts and writable settings in the ignored Kafka input using `topic_partitions` and `topic_configs`, then import each existing topic into the selected remote state. Preserve its partition count; Kafka cannot reduce it. The root keeps topic deletion protection enabled and manages retention separately through `retention_days`. Review the resulting plan to confirm that existing topics are updated in place and no topics are replaced or deleted. It does not create the Confluent account/cluster, issue API keys or grant the application's Kafka ACLs. The Confluent owner must arrange that access beforehand, including consumer-group and transactional-ID permissions. Creating an API key alone is not a substitute for granting its principal the required permissions. See [Confluent API-key documentation](https://docs.confluent.io/cloud/current/security/authenticate/workload-identities/service-accounts/api-keys/overview.html).

Argo CD must be able to read the selected repository and release tag. If using a private repository, arrange its controller-side read credentials separately through protected configuration; never embed a token in the repository URL.

The supplied analytics job runs on GCP Dataproc. No Confluent-managed Flink service or managed connector is required by this deployment. The infrastructure creates a new Cloud SQL application password; existing local database credentials are not deployment inputs. Check both providers' actual billing/trial expiry before a presentation or long pause.

## 5. Prepare the deployment checkout and tools

Work on a deployment branch based on the current published `main`, keeping the recovery baseline tag intact. The commands below are for the deployment operator to run; this handoff has not created that branch or deployed anything.

On a new machine, first clone into a new folder. Skip this block if already in the intended checkout:

```powershell
git clone https://github.com/utkarsharora100/CloudProject1.git CloudProject1-cloud
Set-Location CloudProject1-cloud
```

From that checkout, check for local changes before switching branches. Preserve any existing work:

```powershell
git status --short
git fetch origin
git switch -c cloud-deploy origin/main
```

If `cloud-deploy` already exists, inspect/use it instead of overwriting it. Confirm its source includes `deploy/lifecycle.py` and `deploy/profiles.json` before proceeding. The older recovery commit does not include the later lifecycle helpers.

Install Git, Python 3.12, Docker with Linux containers, Terraform 1.6 or newer, Helm, Google Cloud CLI, kubectl and the GKE authentication plugin. Start Docker Desktop before building release artifacts. Node.js is needed for the local JavaScript verification scripts. Java/Maven compilation runs inside the build container.

Check tool availability before authenticating or provisioning:

```powershell
$requiredTools = 'git', 'py', 'docker', 'terraform', 'helm', 'gcloud', 'kubectl', 'gke-gcloud-auth-plugin'
foreach ($tool in $requiredTools) {
    Get-Command $tool -ErrorAction Stop | Select-Object Name, CommandType
}
py -3.12 --version
```

`$ErrorActionPreference = 'Stop'` alone does not make Windows PowerShell stop on every native CLI error. Check each command's result and stop if it fails; in an automation script, test `$LASTEXITCODE` after each native command.

Create a private Python environment without changing PowerShell execution policy:

```powershell
py -3.12 -m venv .venv
$deployPython = Join-Path (Get-Location).Path '.venv\Scripts\python.exe'
& $deployPython -m pip install -r requirements.txt
gcloud auth login
gcloud auth application-default login
```

Keep this PowerShell session, or recreate `$deployPython` when opening another one. The deployment verification helper also invokes `python` internally; put the virtual environment's Scripts directory first on this session's PATH:

```powershell
$env:PATH = (Join-Path (Get-Location).Path '.venv\Scripts') + [IO.Path]::PathSeparator + $env:PATH
```

Do not download service-account JSON keys for routine deployment. Use your authorized account and the workload identities created by the infrastructure.

## 6. Fill one non-secret configuration file

Copy the template:

```powershell
Copy-Item -LiteralPath deploy/config.example.json -Destination deploy/config.team.json
```

Edit `deploy/config.team.json` locally. It is ignored by Git. Use the 17 fields below with their original JSON types. Older configuration files may omit `compute_profile`; it defaults to `demo`.

| Field | Meaning |
| --- | --- |
| `project_id` | Actual GCP project ID |
| `region` | Region, for example `asia-south1` if suitable |
| `zone` | Zone within that region |
| `prefix` | Short resource prefix; keep stable after provisioning |
| `public_host` | Real DNS hostname, without `https://` |
| `git_repository` | Credential-free HTTPS repository URL |
| `git_revision` | Use a new release tag, for example `cloud-release-v1` |
| `image_tag` | Use the same unique immutable release label; never `latest`, `dev` or `local` |
| `kafka_bootstrap` | Confluent broker hostname and `:9092` |
| `kafka_cluster_id` | Actual `lkc-...` cluster ID |
| `kafka_rest_endpoint` | Credential-free HTTPS cluster REST endpoint |
| `dns_zone` | Existing GCP managed-zone name, or an empty string for externally managed DNS |
| `admin_cidr` | Deployer's actual public IPv4 with `/32`, or another deliberately restricted CIDR |
| `create_firestore` | JSON `true` for a new default database; `false` if the intended database already exists |
| `state_bucket` | Globally unique private Terraform state-bucket name |
| `operator_user` | Non-secret username for the shared assignment operator gate |
| `compute_profile` | Use `demo` for the small presentation deployment; `standard` requires explicit owner agreement |

Do not use template placeholder values. Do not add API keys/passwords to this file.

For the first deployment, replace the template's `git_revision` and `image_tag` with the same new, unused release label, such as `cloud-release-v1`. The template's `dev` revision is not the immutable release used by this runbook. Choose the label before rendering, but create its Git tag only after the generated deployment manifests are committed in section 9. This makes the release tag resolve to the commit containing its own deployment configuration. Do not point the first deployment directly at the baseline commit: that commit does not contain the generated `deploy/environments/team` files.

```powershell
$config = Get-Content -Raw -LiteralPath deploy/config.team.json | ConvertFrom-Json
gcloud config set project $config.project_id
gcloud auth application-default set-quota-project $config.project_id
gcloud services enable storage.googleapis.com --project $config.project_id
& $deployPython -m deploy.configure
& $deployPython -m deploy.secret_inputs cloud
& $deployPython -m deploy.secret_inputs kafka
```

The private prompts collect application Kafka credentials and a new operator password for the cloud root, and topic-administration credentials for the Kafka root. Input is not echoed. Their ignored private files must not be staged. The helper refuses to overwrite an existing private-input file; inspect its existence privately before deciding whether to replace it.

Cloud SQL's new application password is generated by Terraform. Application secrets are stored in Secret Manager, and the generated deployment refers to specific versions.

## 7. Plan and apply infrastructure in order

Terraform state and saved plans can contain secrets. Keep `.local-build`, all state/plan files, `secrets.auto.tfvars.json` and all private Terraform input files out of Git and screenshots.

The stage helper's default command **only plans**. After review, `--apply-reviewed` (also available as `--apply`) applies that exact saved file. It does not create another plan. A private SHA-256 receipt detects a changed plan, configuration, capacity policy or private input and requires a fresh review.

Use the helper for every stage so its lifecycle guard can reject changes while the application is paused. Do not bypass it with direct Terraform apply commands.

Run each pair separately. **Review each plan before its corresponding apply.** Stop on errors or unexpected destruction.

```powershell
& $deployPython -m deploy.cloud_stage state
# Review the state-bucket plan, then:
& $deployPython -m deploy.cloud_stage state --apply-reviewed

& $deployPython -m deploy.cloud_stage cloud
# Review resources, IAM, networking, region and cost, then:
& $deployPython -m deploy.cloud_stage cloud --apply-reviewed

& $deployPython -m deploy.cloud_stage kafka
# Review topic changes, then:
& $deployPython -m deploy.cloud_stage kafka --apply-reviewed
```

For the default `demo` capacity, no capacity acknowledgment flag is needed. A reviewed `standard` cloud plan/apply additionally requires `--allow-standard-capacity`; do not select it without owner agreement.

The state root bootstraps the private state bucket. Subsequent roots use separate prefixes in that remote backend. Preserve the bootstrap root's local state and provide a private state handover to the designated deployment owner; cloning source does not recover Terraform ownership.

If expected Kafka topics already exist, import them into the correct Terraform resource addresses after checking their configuration. Do not delete/recreate shared topics just to make apply succeed. The application key needs the actual topic, consumer-group and transactional-ID permissions required by the application and Flink, while topic administration uses its separate key.

Do not run the older service-specific Terraform fragments. Use the unified roots under `deploy/terraform/`.

## 8. Render the real deployment and publish release artifacts

After cloud apply succeeds and its outputs have been captured:

```powershell
& $deployPython -m deploy.configure --cloud-outputs .local-build/config/team/cloud-outputs.json
& $deployPython -m deploy.build --release --publish
```

This publishes the application image to the configured Artifact Registry and the compiled Restaurant analytics JAR to the artifact bucket. The function source ZIP is assembled from an explicit allowlist for Terraform's function deployment. Keep the build contexts restricted; do not add the whole checkout or private configuration.

The generated deployment files are:

- `deploy/environments/team/food-values.json`
- `deploy/environments/team/applications.yaml`

They contain cloud resource identifiers and pinned Secret Manager version references, not secret values. Verify that both point to the intended project, hostname, repository revision and release artifact. Do not share the private `cloud-outputs.json` wholesale as a substitute for reviewing these files.

## 9. Publish the reviewed GitOps configuration

Stage only the intended public configuration. Review paths, contents and credentials before committing; do not use `git add .`.

```powershell
git add -- deploy/environments/team/food-values.json deploy/environments/team/applications.yaml
git diff --cached --name-only
git diff --cached --check
# Inspect the staged public configuration privately and scan it for secrets.
git commit -m "Configure first cloud deployment"
git tag cloud-release-v1
git push -u origin cloud-deploy
git push origin cloud-release-v1
```

Use your actual chosen release label if it differs from `cloud-release-v1`. Never move an existing release tag to a different commit. Publish the branch/tag before bootstrapping Argo CD, so its configured revision is available.

Secrets, local data, credentials, Terraform state/plans, image exports and local recovery files must remain excluded. This guide is the only new Markdown exception; other local planning/API documents remain ignored.

## 10. Connect the cluster and bootstrap GitOps

```powershell
& $deployPython -m deploy.cloud_stage kubeconfig
& $deployPython -m deploy.cloud_stage controller
# Review the controller plan, then:
& $deployPython -m deploy.cloud_stage controller --apply-reviewed

& $deployPython -m deploy.cloud_stage gitops
# Review the root Application plan, then:
& $deployPython -m deploy.cloud_stage gitops --apply-reviewed
```

The generated kubeconfig is private and ignored at `.local-build/cloud/kubeconfig`. Terraform bootstraps the controllers/root Application; Argo CD owns the application manifests. Avoid competing manual `kubectl apply` or Helm releases for those same workloads.

Use explicit kubeconfig/context for cloud inspection:

```powershell
$config = Get-Content -Raw -LiteralPath deploy/config.team.json | ConvertFrom-Json
$cloudKubeconfig = Join-Path (Get-Location).Path '.local-build/cloud/kubeconfig'
$cloudContext = "gke_$($config.project_id)_$($config.zone)_$($config.prefix)-gke"
kubectl --kubeconfig $cloudKubeconfig --context $cloudContext get applications -n argocd
kubectl --kubeconfig $cloudKubeconfig --context $cloudContext get pods,jobs,hpa,ingress -n food
kubectl --kubeconfig $cloudKubeconfig --context $cloudContext get externalsecrets -n food
```

Check resources in the actual plan/outputs for the reserved external IP. If `dns_zone` was empty, create the hostname's A record through its DNS owner. Wait for DNS to resolve correctly and the managed certificate to become Active before opening the real `https://` hostname.

Keep internal APIs, databases, Kafka access, ZooKeeper, metrics and administrative consoles private. Access operational consoles with authorized port forwarding. The browser must never receive cloud keys or service passwords.

## 11. Cloud acceptance checklist

Do not call deployment complete just because pods are Running.

1. Root/platform/food Argo Applications are Synced and Healthy at the intended release.
2. Schema/bootstrap jobs complete and all eight services become ready.
3. Three ZooKeeper members form the intended ensemble; scheduler leadership, worker ownership and lease recovery are visible.
4. External Secrets resolve the pinned versions; Cloud SQL and Firestore reads/writes succeed.
5. Create synthetic customer/address/menu data through the application. Place an order and verify payment, kitchen acceptance/preparation, courier assignment, pickup and delivery.
6. Test a payment decline with a safe retry and a no-courier case. Pickup must wait for both preparation and a valid assignment.
7. Notification tasks finish only after durable transport receipts. Source events, identities and customer/courier streams must remain correctly scoped.
8. Managed Flink is RUNNING with successful checkpoints. Real committed results appear in Restaurant analytics; duplicates do not double-count.
9. Verify the cream/black multi-page UI, charts, execution graph, browser refresh and live updates through HTTPS.
10. Verify actual metrics/log ingestion and dashboards without exposing customer addresses, secrets or private lease/session proofs.
11. Complete the cloud load/scaling run below and retain honest evidence.

The cloud operator password is a shared assignment access gate. This is not a production identity system with individual end-user authorization.

### Cloud load and HPA evidence

The Helm load job is disabled by default. After basic acceptance, review `loadTest` and `hpa` in `deploy/charts/food/values.yaml` and the generated deployment values. Enable the load test in the deployment values, choose a fresh `loadTest.runId`, review its traffic/duration, and commit a new GitOps release. The Job name is `food-load-<runId>`.

The release configuration must remain internally consistent: update the relevant Git revisions/root configuration for a new release and follow the managed Flink release rules below. Do not move the first release tag merely to trigger a load job.

Capture against the actual completed cloud job:

```powershell
$loadJob = Read-Host 'Actual food-load-<runId> Job name'
& $deployPython -m deploy.capture_scaling --kubeconfig $cloudKubeconfig --context $cloudContext --job $loadJob --scope gke
```

The capture checks actual GCE-backed nodes, CPU and memory HPA metrics, both selected services scaling out, successful k6 completion and nonnegative timing bounds. Keep the resulting private evidence under `.local-build/evidence/`. Local unit tests and local scale-out are not substitutes for this GKE result.

## 12. Troubleshooting and controlled changes

| Symptom | Check first |
| --- | --- |
| Permission/API/billing failure | Correct account/project, linked verified billing, API permissions and quotas |
| Argo cannot fetch/render | Release tag exists remotely; deployment files are committed at that tag; charts/dependencies are available |
| Pending pods | Actual scheduling events, node capacity, PVCs and resource requests |
| Secret resolution failure | Workload identity bindings, Secret Manager access and the specific enabled secret versions |
| SQL errors | Proxy identity, instance connection name, schema job and private networking |
| Kafka/Flink auth errors | Correct broker/cluster, application key, topics, consumer groups and transaction permissions |
| No final analytics window | Job/checkpoints, valid event times, watermark progress and read-committed results; a quiet window can wait for progress |
| Notification remains pending | Function trigger, Pub/Sub and receipt storage; do not manually force task success |
| HPA shows unknown metrics | Metrics availability, pod requests and the target workload; retain failed evidence |
| HTTPS/certificate pending | Real hostname A record, reserved IP, ingress and certificate status |

For deployment changes, prefer the config renderer and the generated deployment Helm values. Keep business logic, task dependencies, idempotency, payment/refund ownership and delivery capacity rules intact. Do not edit source to bypass a failed readiness or security check.

### Handling a first-deployment failure

1. Stop at the failing stage. Record the stage, timestamp, release commit/tag, resource type and a sanitized error summary. Keep raw logs, state, plans, kubeconfig and credential-bearing responses private.
2. Check account/project, billing/quota, API enablement, IAM, endpoints, secret versions and DNS before changing application code. A Kafka permission failure requires correcting access for the intended principal; it does not justify using a shared personal login.
3. For a settings correction, edit the ignored non-secret configuration and rerun the renderer as described in sections 6 and 8. Generate and review a fresh Terraform plan when its inputs change. Respect any existing resources or state after a partial apply; do not destroy them merely to retry.
4. If managed-runtime compatibility or an application defect requires a code change, make a focused fix on the deployment branch and run the relevant checks. Build and publish the affected release artifacts with a new immutable release label. Keep Git, image and analytics release identities consistent; use the stateful release procedure for a running Flink job.
5. Check the affected service/integration again, then continue from the correct stage. Keep failed evidence and mark unresolved checks as failed or not run. Do not disable required services, ZooKeeper members, HPAs, probes or credential safeguards to obtain a passing screen.

Keep the default `demo` profile while diagnosing. If measured capacity is insufficient, report scheduling events or measured resource pressure and review a deliberate sizing change; do not silently switch to the larger profile. Never change release identity or infrastructure while a lifecycle pause/resume operation is unfinished.

### Cloud rollback is separate from source recovery

The preserved local source is your independent fallback. Cloud rollback additionally requires coordination with live databases, Kafka, secrets, migrations and Flink state.

Argo CD's native rollback cannot be used while automated sync is enabled. Prefer a reviewed GitOps release/revert, or an explicitly coordinated change to sync policy. See [Argo CD automated sync documentation](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/).

Do not restore revoked secret versions when rolling back code. Do not assume a code rollback undoes database writes or Terraform changes.

Managed analytics uses stable release identities. An active matching release is reused; overlapping active releases and terminal reused identities are rejected. For a new stateful analytics release, take a durable Flink savepoint, coordinate stopping the prior job, use a new immutable release identity and set `ANALYTICS_SAVEPOINT` in `managedFlink.env`. Verify restored state and committed output. An old image tag alone is not a complete Flink rollback.

### Cost and cleanup

Review the actual plan and current pricing before provisioning. GKE nodes, Dataproc nodes, Cloud SQL, networking/NAT, load balancers, disks and retained storage can continue incurring costs even when the browser is closed. A credit balance alone does not establish how long this configuration can run.

Set billing alerts and assign a cleanup owner. An **alerts-only budget does not cap spending**; check the scope and availability of any separate spend-cap feature rather than assuming it covers this deployment. See [Google Cloud budgets and alerts](https://docs.cloud.google.com/billing/docs/how-to/budgets).

Do not use Terraform destroy or deletion of the Argo root Application as a casual rollback. Plan cleanup with the owner, understand cascading deletion, preserve required state/backups and handle deletion protection deliberately.

## 13. Final deployment handover

Return a sanitized deployment record with the items below. Use explicit **passed**, **failed** or **not run** status and actual test timestamps; unexecuted cloud checks must remain not run.

| Handover item | Evidence to provide |
| --- | --- |
| Release | Git commit/tag, application image identity and analytics artifact identity |
| Environment | Project ID, region/zone, deployed capacity profile and resource inventory |
| Public access | Working HTTPS URL, DNS and certificate readiness |
| Application | Readiness of all eight services and a synthetic order's payment, kitchen, assignment, pickup, delivery and notification results |
| Failure/recovery behavior | Payment retry, unavailable-courier behavior and scheduler ownership/lease recovery results |
| Managed integrations | Cloud SQL/Firestore persistence, receipt-confirmed function transport and actual Flink checkpoints/results |
| Scaling | Actual sustained-load result and scale-out evidence for both required HPAs |
| Pause/resume | A completed cloud rehearsal, restored analytics state and healthy services afterward |
| Operations | Metrics/log visibility, actual observed usage/cost, credit-expiry dates and a pause/cleanup owner |
| Ownership and gaps | Protected state location and access owner, bootstrap-state handover, unresolved issues and checks not run |

Keep full state, plans, private inputs, raw evidence/logs and recovery journals in protected storage. Share only sanitized evidence; omit customer contact/address data, private lease/session proofs and credentials. A fresh source clone does not transfer Terraform state ownership or the local recovery ZIPs.

Pass access through IAM and approved secret storage, not credential-bearing documents or screenshots. Personal names/student IDs and `task_divison.txt` remain deferred until the required information is supplied.

Keep the source baseline and its local recovery tag unchanged while the cloud work proceeds.

## 14. Low-cost demonstration profile and pause/resume

Published to `main` on 15 November 2026. The default `compute_profile` is `demo`. Build the release application image from this updated source before using the lifecycle workflow.

| Setting | Demo default |
| --- | --- |
| GKE worker pool | Three `e2-standard-2` nodes; normal and maximum node count both three |
| GKE boot disks | 30 GB standard persistent disks per node |
| Managed analytics | One `e2-standard-2` master/worker VM; zero separate worker VMs |
| Managed analytics disk | 30 GB standard persistent disk |
| Cloud SQL | `db-g1-small`, 10 GB storage, maximum 50 connections |
| Kafka event retention | 21 days by default; applied-policy receipt required before pausing |
| Application MySQL pools | Two connections per API process, one per SQL background process, no overflow |
| Application resource requests | Normally 50m CPU / 128 MiB; small background workers request 25m CPU |
| Required coordination | Three ZooKeeper members and two scheduler/worker replicas are preserved |
| Autoscaling evidence | Customer and Order retain independent CPU + memory HPAs; demo maximum is four replicas each |

The single-node managed cluster is suitable for a small demonstration, but it is not a multi-machine analytics availability design. See [Google's single-node cluster documentation](https://docs.cloud.google.com/managed-spark/docs/concepts/configuring-clusters/single-node-clusters).

The demo capacity has passed local configuration, contract and regression checks. It has **not** yet passed a live GKE sizing/load test. Do not claim its latency or cloud recovery requirements passed until they are measured. If the required cloud test does not fit, review the cause and obtain the project owner's agreement before selecting larger capacity. The optional `standard` profile requires `--allow-standard-capacity` on the cloud stage; it is never selected automatically.

For an existing deployment, changing the analytics topology or machine type can replace its Dataproc cluster. This profile is intended for a reviewed first deployment. Do not apply a replacement plan over existing data without a separate savepoint/migration review.

### Operator prerequisites for lifecycle commands

Install the Python dependencies and CLI tools from section 5. Use your authorized personal account and ADC; do not create service-account key files.

The operator needs permission to inspect/control the selected GKE node pool, inspect the Compute Engine instance group, start/stop the selected SQL and Dataproc resources, and read/write the private lifecycle records in the checkpoint bucket. Its Kubernetes access must permit reading and temporarily scaling the owned workloads and patching the three owned Argo Applications.

Flink savepoints run through IAP SSH to the private master. The infrastructure adds only TCP 22 from the IAP range `35.235.240.0/20` to the Dataproc-tagged VMs, enables OS Login and enables the related APIs. The owner must grant the operator appropriate IAP Tunnel User, OS Login and Service Account User access to the analytics VM identity. Permission to create infrastructure does not necessarily include these operational permissions. See [IAP access requirements](https://docs.cloud.google.com/iap/docs/using-tcp-forwarding).

Use the isolated kubeconfig generated by `deploy.cloud_stage kubeconfig`. Lifecycle commands always specify its explicit context and check the actual cluster endpoint before a new pause.

### Safe offline previews

These commands require no GCP credentials, make no cloud requests and do not start Docker:

```powershell
& $deployPython -m deploy.lifecycle pause --dry-run --example
& $deployPython -m deploy.lifecycle resume --dry-run --example
```

For your actual configuration, omit `--example`. A pause/resume invocation without `--execute` also produces only an offline plan; it does not inspect or mutate cloud resources.

### Before the first pause

Complete the initial deployment, confirm a successful synthetic order and run the required cloud load test. Finish any active initialization, load or GitOps jobs. Apply the Kafka stage through the reviewed helper; after success it records the configured retention policy privately in GCS. Check Confluent consumer lag and clear any existing backlog before a long pause. Do not shorten topic retention or delete events while the application is paused.

Keep the release and configuration unchanged throughout a pause/resume cycle. Rendered values, the deployed image, the active analytics specification and the GitOps revision must match. The old baseline image does not contain this lifecycle protocol; publish a new immutable image/release from the updated source first.

```powershell
& $deployPython -m deploy.lifecycle status
& $deployPython -m deploy.lifecycle check
& $deployPython -m deploy.lifecycle pause --dry-run
```

`status` reads cloud state and reports node count, SQL activation, analytics cluster state and the recorded lifecycle phase. `check` verifies the expected release/capacity, application readiness, ZooKeeper quorum and GitOps health. Neither command changes cloud resources.

### Pause between sessions

After reviewing the preview:

```powershell
& $deployPython -m deploy.lifecycle pause --execute
& $deployPython -m deploy.lifecycle status
```

The pause operation:

1. Acquires a generation-fenced lease and records a recovery snapshot in the private checkpoint bucket.
2. Suspends automatic reconciliation for the root, platform and food Argo Applications, waiting for any in-progress reconciliation to finish.
3. Marks analytics submission as paused and disables node-pool autoscaling.
4. Stops the web entry point and application workloads; their SQL ledgers, outboxes and leases remain durable.
5. Stops the exact Flink job with a canonical GCS savepoint, without draining pending event-time windows. It verifies completed savepoint metadata and job termination before stopping its VM.
6. Scales ZooKeeper to zero with its persistent volumes retained, then removes the GKE node VMs.
7. Stops Cloud SQL and verifies the expected paused states.

Normal pause never runs Terraform destroy, deletes a cluster/database/bucket/topic, deletes a PVC, revokes credentials or clears Kafka offsets. The public application is unavailable while paused.

The private records are:

- `gs://<project>-<prefix>-checkpoints/lifecycle/journal.json`
- `gs://<project>-<prefix>-checkpoints/lifecycle/analytics.json`
- `gs://<project>-<prefix>-checkpoints/lifecycle/kafka-policy.json`
- Savepoints under `gs://<project>-<prefix>-checkpoints/flink/savepoints/<pause-id>/`

These records contain resource identities and recovery metadata, not credentials. Do not publish them or delete them to force a fresh start. The GCS generation checks prevent two lifecycle operators from overwriting each other.

### Resume before a rehearsal or presentation

Start well before the demonstration and leave time for readiness checks:

```powershell
& $deployPython -m deploy.lifecycle resume --dry-run
& $deployPython -m deploy.lifecycle resume --execute
& $deployPython -m deploy.lifecycle check
```

Resume verifies that the recorded resources were not recreated and that the release/profile still match. It starts SQL and the analytics VM, restores Flink from the recorded savepoint using a new stable run ID, restores application nodes, brings back ZooKeeper quorum and then starts application replicas. HPA-controlled APIs start at their configured minimum rather than their temporary load-test replica counts.

Autoscaling and the previous GitOps policies are restored after application readiness. GitOps hooks consult the shared analytics control record and reuse the resumed run. The operation verifies Healthy/Synced Applications and a RUNNING analytics job before reporting success.

**A lifecycle readiness PASS is not an end-to-end business or load-test PASS.** Place and complete a fresh synthetic order after resuming, check receipt-confirmed notifications and actual analytics output, and retain the required cloud evidence.

### Retention and pause duration

The topic policy now retains events for 21 days instead of seven. The helper requires the successful Kafka-apply receipt to match the intended cluster, broker and rendered retention policy. It sets a scheduling deadline one day inside that window and reports it in UTC through `status`.

With the default policy, resume within 20 days of pausing, and earlier if existing unprocessed events were already old. This deadline is a scheduling guard, not a measurement of every consumer's lag. Confirm the backlog is clear before pausing. Resume refuses an expired margin rather than silently assuming source events still exist. A missing receipt requires applying the reviewed Kafka stage; a missing savepoint, changed policy or expired window requires operator review.

Kafka retention is separate from GCP or Confluent trial expiry. Both accounts must remain usable through the pause and presentation. See [Confluent topic retention configuration](https://docs.confluent.io/cloud/current/topics/manage.html).

### Interrupted operations

Re-running the same command resumes recorded progress. A lost response after savepoint completion is reconciled from the deterministic GCS savepoint prefix, and a lost submission response reuses the same analytics run ID.

If another operator holds a live lease, the command stops. If the prior process died, first confirm it is no longer running. Only after its 30-minute lease has expired may an operator explicitly reclaim it:

```powershell
& $deployPython -m deploy.lifecycle pause --execute --recover
# Or, for an interrupted resume:
& $deployPython -m deploy.lifecycle resume --execute --recover
```

If the exact analytics job created during an unfinished resume is confirmed terminal, inspect its failure first. After correcting the cause without changing the recorded release, explicitly retry that restore:

```powershell
& $deployPython -m deploy.lifecycle resume --execute --retry-analytics
```

That option uses the same savepoint and a new runtime ID only after confirming the prior run ended. It does not silently start from empty state. Missing savepoint metadata, a changed release or a recreated resource requires operator review.

One deployment owner must coordinate Terraform and lifecycle operations; do not launch a Terraform apply concurrently with a pause/resume. Normal Terraform stages refuse to operate when a pause or lifecycle operation is already recorded as unfinished. Use the reviewed stage helper; direct Terraform commands can bypass that workflow guard. The state-bootstrap root remains a separate protected infrastructure operation.

### What still costs money while paused

Stopping compute is not a zero-bill guarantee. Retained database storage, disks, backups, buckets, registry artifacts, networking and an uncovered GKE control-plane fee can continue to be billed. Confluent billing is independent; this helper stops the application's Kafka clients but does not delete or alter the Kafka cluster.

Use Basic Kafka for the demonstration, keep data retention deliberate, check actual GCP/Confluent usage and credit expiry, and avoid extra managed connectors or processing products that the application does not use. Trial credits can cover eligible usage only while they remain valid. The cost estimates discussed during planning are not a provider quote or a proven operating cost.

### Remaining cloud acceptance

The deployment operator must still verify actual IAM/IAP access, infrastructure provisioning, DNS/certificate readiness, the managed function/receipt path, the complete order flow, managed Flink state restoration and both HPAs under the required sustained load. Run a full pause/resume rehearsal before presentation day.

The original source-only baseline remains intact. An additional source-only snapshot of the budget/lifecycle implementation, captured before its publication, is kept locally at `.local-build/recovery/budget-lifecycle-source.zip` with its SHA-256 manifest. Later documentation edits are not retroactively included in that frozen snapshot. It contains source/configuration only, without images, credentials, Terraform state or runtime data.
