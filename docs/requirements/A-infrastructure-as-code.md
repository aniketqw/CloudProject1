# A. Infrastructure as Code

## 1. The requirement
All cloud infrastructure, on every provider, is created by Terraform with one entry point and a plain `terraform apply`; no Python provisioning.

## 2. Original code
Terraform was generated as JSON by Python and applied by a Python wrapper in five stages. Several original defects only showed on a real run.

## 3. Changes (trace IDs)
- One HCL root `deploy/terraform/cloud/` plus `modules/argocd` and a state bootstrap (T-001 to T-021). Images and the Flink jar are built by apply (T-048). Optional Kafka, one `.env` (T-022 to T-026).
- Original-code defects fixed: workload-identity ordering (T-027), function source permission (T-028), Dataproc replaced on every plan (T-029, T-030), bucket force destroy (T-038), Firestore leftover (T-039), Flink job id reuse after a rebuild (T-067).
- Teardown switches and a documented order (T-035, T-038, T-044, T-051, T-057). New switches: `paused` (T-061, T-066), derived hostname (T-059).
- Written, not applied: Confluent cluster in Terraform (T-071).
- Mistakes of mine: a plain apply after a partial destroy (T-041), a laptop network change (T-062, T-063).

## 4. See it working
`set -a; source .env; set +a; terraform -chdir=deploy/terraform/cloud apply` then `terraform -chdir=deploy/terraform/cloud plan` (expect "No changes").

## 5. Evidence
`docs/evidence/02-platform/`, `04-rebuild/`, `12-plan-no-changes/` (plan after apply: No changes).

## 6. Result
PARTIAL, 2026-11-22. One apply builds everything (108 resources, no errors, four times from the post-teardown state); a plan after it shows No changes. Teardown is two documented commands (about 15 minutes) and repeatable (T-086, T-093, T-098). The platform now starts without hand syncs (about 19 minutes to a running Flink job, T-096) after the fixes in T-090 and T-095. The existing Confluent cluster is accepted as the Kafka provider. Pause is a Terraform variable. Not proven: a run from a completely empty project (the VPC, APIs and state bucket survive a teardown).

## 7. Open
A rebuild from an empty project with zero manual steps.
