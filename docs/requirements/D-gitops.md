# D. GitOps

## 1. The requirement
All application updates are managed by a GitOps controller.

## 2. Original code
Argo CD tracked the chart repository. Source-code changes needed a manual image build.

## 3. Changes
Argo applications created by Terraform (T-021), ingress sync wave (T-060). Written, not proven: build-on-push workflow and workload identity (T-072).

## 4. See it working
Change a value in the chart, push to `iac-integration`; watch `kubectl get application -n argocd`. Scale a deployment by hand and watch it revert.

## 5. Evidence
`docs/evidence/10-gitops/`, `14-screenshots/argocd-*.png` (the Argo UI images show the commit author's name and address; keep them local).

## 6. Result
PARTIAL, 2026-11-22. Git change synced (load test on and off, release v1 to v2); self-heal reverted a hand scale in about 9 s; Argo CD UI screenshots saved. Build-on-push is written but BLOCKED: the tracked repository belongs to another account where this user has push but not admin rights, so the five repository variables the workflow needs cannot be set and Actions cannot be enabled.

## 7. Open
Prove build-on-push (needs admin on the tracked repository or a repository the owner controls). Syncs sometimes waited for an already completed hook Job; a 300 s sync timeout and 40 retries now cover it, but one stale failed launcher Job still had to be deleted by hand once.
