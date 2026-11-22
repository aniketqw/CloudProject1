# D. GitOps

## 1. The requirement
All application updates are managed by a GitOps controller.

## 2. Original code
Argo CD tracked the chart repository. Source-code changes needed a manual image build.

## 3. Changes
Argo applications created by Terraform (T-021), ingress sync wave and certificate health (T-060, T-080), retry and hook fixes (T-090). Build-on-push: workflow and workload identity (T-072), proven on the owner's fork (T-089).

## 4. See it working
Change a value in the chart, push to `iac-integration`; watch `kubectl get application -n argocd`. Scale a deployment by hand and watch it revert.

## 5. Evidence
`docs/evidence/10-gitops/`, `14-screenshots/argocd-*.png` (the Argo UI images show the commit author's name and address; keep them local).

## 6. Result
PASS, 2026-11-22. A Git change synced (load test on and off, release v1 to v2); a hand scale reverted in about 9 s; the Argo CD UI was captured. Build-on-push works on the fork `aniketqw/CloudProject1`: a source change ran the workflow (login, build, push, tag commit by the `build-image` bot) and Argo CD rolled every service to the new tag (`evidence/19-build-on-push/`, `14-screenshots/argocd-after-build-on-push.png`). The Argo UI images show the commit author's name and address; keep them local.

## 7. Open
The workflow works only while the platform exists (the Google pool is destroyed with it). A first sync on a fresh platform can take about 20 minutes (External Secrets starts late); it recovers by itself since T-090.
