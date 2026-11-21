# Change Trace

Every change made to this repo for the IaC work is recorded here, grouped by purpose, so each change can be found, understood and removed.

## How to read this file
- Changes are grouped into **Groups** (A, B, C, ...). Each group is one purpose, with a short "what and why" paragraph.
- Each entry has an ID `T-NNN`, in the order the change was made.
- **Action:** `ADDED`, `MODIFIED`, `DELETED` or `RENAMED`.
- **Relevance:** why the change matters for the requirement. This is the part to read if you only want to understand the work.
- **Undo:** the exact step to reverse it.
- **Log:** the matching file in `logs/` with the commands and their output.

## Rules
1. No change is made without an entry here, written in the same step.
2. Commands are logged in `logs/<ID>-<short-name>.log`.
3. When a new file replaces an old one, the old file is deleted and the deletion gets its own entry (Group C).
4. Entries are not rewritten after the fact, except to add `REVERTED on <date>` or to regroup them.

## Branches
**Hard rule: `main` is never changed.** No commit, merge, reset, rebase or push is made on `main` (or to `origin/main`).

| Branch | Cut from | Purpose |
|---|---|---|
| `main` | (original) | Untouched. Still at commit `a0057c8`, identical to `origin/main`. |
| `iac-integration` | `main` | Integration branch. Finished work branches are merged into it, never into `main`. |
| `iac-hcl-conversion` | `main` | Working branch for the IaC (Terraform) changes in this file. Merged into `iac-integration` when green. |

Git history so far (2026-11-21):
- `78168d5` on `iac-hcl-conversion`: "Convert Terraform to HCL and merge into one cloud root" (Groups B to F, code only).
- `9387052` on `iac-integration`: merge of `iac-hcl-conversion` (no fast-forward, so the merge is visible).
- Commit messages carry no co-author or tool attribution.
- `main` is still `a0057c8`.

Docs in git: the repo's `.gitignore` ignores `*.md` and `*.log` ("source-only Git update"). At the owner's request `trace.md`, `IAC_REQUIREMENT_ANALYSIS.md` and `logs/` were added with `git add -f`; `.gitignore` itself was left unchanged. New docs and logs must be force-added the same way. Local usernames and paths were replaced with placeholders in the logs before publishing.

Any later work branch follows the same path: cut from `main`, merged into `iac-integration`. Merging into `main` is the owner's decision.
- Undo this work: delete the branch (`git branch -D iac-hcl-conversion`; also `iac-integration` if it was merged there). `main` is unaffected.

---

## Group A: Analysis and tracking setup
Purpose: record what the repo had and set up the tracing, before changing any code.

| ID | Action | Path | What | Relevance | Undo | Log |
|---|---|---|---|---|---|---|
| T-001 | ADDED | `IAC_REQUIREMENT_ANALYSIS.md` | Requirement 1 analysis: files found, coverage table, verdict (not met), list of changes needed. | Defines the work. Every later group maps to a numbered change in its "Changes needed" list. | `rm IAC_REQUIREMENT_ANALYSIS.md` | none (read-only exploration) |
| T-002 | ADDED | `trace.md` | This file. | Lets every change be found and reversed; basis for the revision guide. | `rm trace.md` | none |
| T-003 | ADDED | `logs/README.md` (folder `logs/`) | Folder and naming rule for per-change logs. | Raw evidence for the revision guide. | `rm -r logs` | none |

## Group B: Convert Terraform from JSON to HCL (`.tf`)
Purpose: analysis change #1. The repo had **no `.tf` files**, only `main.tf.json`. Terraform treats `main.tf` and `main.tf.json` in the same folder as one configuration, so the HCL files replace the JSON ones rather than sitting next to them. Resource names, variables and outputs were kept identical so nothing about the deployed shape changes.

| ID | Action | Path | What | Relevance | Undo | Log |
|---|---|---|---|---|---|---|
| T-004 | ADDED | `deploy/terraform/state/main.tf` | HCL version of the state-bucket root (2 resources). | Requirement asks for Terraform `.tf` code. | `git rm` the file, restore the JSON (see C) | `logs/T-004-convert-small-roots.log` |
| T-004 | ADDED | `deploy/terraform/kafka/main.tf` | HCL version of the Kafka topics root (4 topics via `for_each`). | Same. | same | same |
| T-004 | ADDED | `deploy/terraform/controller/main.tf` | HCL version of the Argo CD root. Helm values are now written as an HCL object wrapped in `jsonencode(...)` instead of one long escaped string. | Same, and the Helm values are now readable and reviewable. | same | same |
| T-004 | ADDED | `deploy/terraform/gitops/main.tf` | HCL version of the Argo root Application. | Same. | same | same |
| T-005 | ADDED | `deploy/terraform/cloud/main.tf` | HCL version of the main GCP stack: 67 resources (network, GKE, Cloud SQL, Firestore, buckets, Pub/Sub, Eventarc, function, Dataproc, secrets, IAM). Nested settings were marked as blocks or attributes using the provider schemas. | The main infrastructure of the project, now in readable Terraform. | same | `logs/T-005-convert-cloud-root.log` |

Note: the `kafka`, `controller` and `gitops` files from this group were later merged into the single cloud root (Group E).

How it was verified: `terraform init -backend=false` and `terraform validate` pass for all five roots (run in a scratch copy so no `.terraform/` or lock changes landed in the repo). A script compared resource, variable and output names between the old JSON and the new HCL: all five roots match (67 resources in the cloud root).

## Group C: Remove files that the new ones replace
Purpose: per the working rule, anything made unnecessary by a change is deleted and recorded.

| ID | Action | Path | What | Relevance | Undo | Log |
|---|---|---|---|---|---|---|
| T-007 | DELETED | `deploy/terraform/{state,kafka,controller,gitops,cloud}/main.tf.json` (5 files) | Old JSON Terraform, replaced by Group B. Two configs in one folder would conflict. | Leaves exactly one definition of the infrastructure. | `git checkout main -- deploy/terraform/<root>/main.tf.json` and delete `main.tf` | `logs/T-007-remove-superseded.log` |
| T-008 | DELETED | `customer_service/.terraform.lock.hcl`, `order_service/.terraform.lock.hcl`, `restaurant_service/.terraform.lock.hcl` | Stale lock files from old per-service Terraform whose `.tf` files no longer exist (analysis change #8). | Removes leftovers that suggested Terraform lived in the service folders. | `git checkout main -- <path>` | same |

## Group D: Keep the existing tooling working after the rename
Purpose: other files referenced `main.tf.json` by name or parsed it as JSON. They were adjusted so nothing breaks. These scripts are expected to be removed or replaced in later groups (analysis changes #2 to #5).

| ID | Action | Path | What | Relevance | Undo | Log |
|---|---|---|---|---|---|---|
| T-006 | MODIFIED | `deploy/cloud_stage.py` (line 18) | Plan-input hashing now globs `*.tf` instead of `*.tf.json`. | Without it the saved-plan receipt would ignore the Terraform source and stop detecting changes. | `git checkout main -- deploy/cloud_stage.py` | `logs/T-006-dependent-code.log` |
| T-006 | MODIFIED | `deploy/local_cluster.py` | The local kind harness used to load the JSON and edit it. It now copies the `.tf` files and swaps text (drops the backend, renames the app, changes the path and namespace, adds the Argo exclusion setting). It asserts each pattern exists, so a future edit to the `.tf` will fail loudly. | Keeps the local test cluster path working on HCL. | `git checkout main -- deploy/local_cluster.py` | same |
| T-006 | MODIFIED | `tests/test_cloud_lifecycle.py` | One test parsed the JSON for settings; it now checks the same facts in the `.tf` text (profile default, shared `profiles.json`, max nodes, Flink workers, SQL deletion protection). | Keeps the guard tests meaningful. | `git checkout main -- tests/test_cloud_lifecycle.py` | same |
| T-006 | MODIFIED | `tests/test_lifecycle_cloud.py` | Test fixtures create `main.tf` instead of `main.tf.json`. | Keeps fixtures matching the real filenames. | `git checkout main -- tests/test_lifecycle_cloud.py` | same |

Test result: the two edited test files pass (42 tests). The full suite shows 11 import errors (Flask, Flask-SQLAlchemy and `google.api_core` are not installed here). The **same 11 errors occur on the untouched original commit**, so they are not caused by these changes.

## Group E: One Terraform root instead of five (analysis changes #2 and #3)
Purpose: the old flow needed five separate applies, with the Argo CD stages needing a kubeconfig from the cluster created earlier. Now `deploy/terraform/cloud/` is the single root: network, GKE, databases, storage, messaging, Dataproc, Kafka topics and Argo CD all come from one `terraform apply`. Only the one-time state-bucket bootstrap (`deploy/terraform/state/`) stays separate, because the state bucket must exist before any backend can use it.

| ID | Action | Path | What | Relevance | Undo | Log |
|---|---|---|---|---|---|---|
| T-009 | ADDED | `deploy/terraform/modules/argocd/{main,variables,versions}.tf` | Shared module: installs Argo CD and the root Application. The Application is created through the `argocd-apps` Helm chart (2.0.8), not `kubernetes_manifest`, which needs the cluster to exist at plan time and would fail on a new cluster. | Lets Argo CD install in the same apply as the cluster. Used by the cloud root and by the local test cluster, so there is one definition. | `git rm -r deploy/terraform/modules` | `logs/T-009-argocd-module.log` |
| T-010 | MODIFIED | `deploy/terraform/cloud/main.tf` | Now holds locals, providers (google, confluent, helm), data sources and the API list. The helm provider is built from the cluster created in the same apply (endpoint, token, CA certificate) instead of a kubeconfig file. | Removes the "cluster must exist and kubeconfig must be fetched first" step. | `git checkout main -- deploy/terraform/cloud/` | `logs/T-010-merge-roots.log` |
| T-010 | ADDED | `deploy/terraform/cloud/{versions,variables,network,iam,gke,database,storage,secrets,messaging,dataproc,outputs}.tf` | The previous single `main.tf` split by theme with a script (no resource text was retyped). | Easier to read, review and teach from. Resource names are unchanged. | delete them and restore `main.tf` from `main` | same |
| T-010 | ADDED | `deploy/terraform/cloud/kafka.tf` | The four Kafka topics, moved from the old `kafka` root. Uses a separate **topic-administrator** credential (`kafka_admin_api_key/secret`) because the application credential (`kafka_api_key/secret`) is a different Confluent key. | Kafka topics now come from the same apply. | delete the file | same |
| T-010 | ADDED | `deploy/terraform/cloud/argocd.tf` | Calls the shared module, after the node pool exists. | Argo CD and the root app come from the same apply. | delete the file | same |
| T-010 | MODIFIED | `deploy/terraform/cloud/.terraform.lock.hcl` | Regenerated for google, random, confluent and helm on four platforms (Windows, Linux, macOS Intel and Apple silicon). | The merged root uses two more providers. | `git checkout main -- deploy/terraform/cloud/.terraform.lock.hcl` | same |
| T-010 | DELETED | `deploy/terraform/kafka/`, `deploy/terraform/controller/`, `deploy/terraform/gitops/` | The three roots now merged into `cloud`, including their lock files. | One definition of each thing. | `git checkout main -- deploy/terraform/<root>` | same |

New and renamed input variables for the cloud root: `kafka_cluster_id`, `kafka_rest_endpoint`, `kafka_retention_days` (was `retention_days`), `kafka_admin_api_key`, `kafka_admin_api_secret`, `git_repository`, `git_revision`. Removed: `kubeconfig_path`, `kube_context`, `cluster_id`, `rest_endpoint`.

How it was verified: `terraform init`, `terraform validate` and `terraform fmt -check` pass for the merged root and the module (in a scratch copy mirroring the repo layout). The generated local-cluster config also validates.

## Group F: Keep the tooling consistent with the single root
Purpose: the Python tooling and tests assumed five stages. They were changed so nothing points at roots that no longer exist. These scripts are the ones the requirement wants removed in the next groups (analysis change #5).

| ID | Action | Path | What | Relevance | Undo | Log |
|---|---|---|---|---|---|---|
| T-011 | MODIFIED | `deploy/cloud_stage.py` | Stages are now `state`, `cloud`, `kubeconfig`. The `kafka`, `controller` and `gitops` stages were removed. The Kafka retention receipt that pause/resume reads is now written after the `cloud` apply. | Matches the single root without losing the retention safety check. | `git checkout main -- deploy/cloud_stage.py` | `logs/T-011-validation.log` |
| T-011 | MODIFIED | `deploy/configure.py` | Writes one `cloud.tfvars.json` containing the Kafka and Git values, and only a `cloud` backend file. | One input file for one root. | `git checkout main -- deploy/configure.py` | same |
| T-011 | MODIFIED | `deploy/secret_inputs.py` | No `cloud`/`kafka` scope. One run asks for both Kafka key pairs and the operator passphrase and writes one ignored secrets file in the cloud root. | One secrets file for one root; keeps the two Kafka credentials separate. | `git checkout main -- deploy/secret_inputs.py` | same |
| T-011 | MODIFIED | `deploy/local_cluster.py` (replaces the T-006 edit) | The local kind harness now generates a small root that calls the shared Argo CD module, instead of editing copies of the old roots. | Same Argo CD definition is exercised locally. | `git checkout main -- deploy/local_cluster.py` | same |
| T-011 | MODIFIED | `tests/test_cloud_lifecycle.py` | Reads all `*.tf` files in the cloud root instead of one file. | The settings are now spread over several files. | `git checkout main -- tests/test_cloud_lifecycle.py` | same |
| T-011 | MODIFIED | `tests/test_lifecycle_cloud.py` | Kafka-receipt test now runs the `cloud` stage; the cloud-stage test mocks the state store; fixture holds `kafka_retention_days`. | Tests follow the new behaviour. | `git checkout main -- tests/test_lifecycle_cloud.py` | same |

Test result: the two edited test files pass (42 tests). The full suite shows the same 11 import errors as the untouched original commit (Flask, Flask-SQLAlchemy and `google.api_core` are not installed here).

Known gap: `CLOUD_DEPLOYMENT_HANDOFF.md` is an original document and was **not** edited. It still describes the old five-stage commands (`cloud_stage kafka`, `controller`, `gitops`, `secret_inputs kafka`). The new instructions will go in the revision guide.

---

## Not done yet (from the analysis, for the next groups)
Move artifact building (function ZIP, images, Flink jar) into Terraform; replace Python provisioning (Flink submit, schema init, pause/resume); add monitoring resources; secrets as variables; update the handoff doc. Each will become a new group above.

## Revision guide
To be written after the work is complete. It will follow these groups in order, and for each one explain what was done, why, how to repeat it on another project, and how it was verified.
