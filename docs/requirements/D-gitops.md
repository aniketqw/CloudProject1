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
`docs/evidence/10-gitops/`.

## 6. Result
PARTIAL, 2026-11-22. Git change synced (load test on and off); self-heal reverted a hand scale in about 9 s. Build-on-push is written but not proven.

## 7. Open
Prove build-on-push (needs write access and repository variables). A stuck sync sometimes needed the operation cleared (diagnosis, not a fix).
