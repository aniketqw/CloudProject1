#!/bin/bash
# Runs in the background during `terraform destroy`. Argo CD's cascade delete hangs when a sync is still in flight
# (for example one waiting on a health check that will never pass), so this clears the in-flight operation of every
# application that is being deleted. Needs gcloud, curl and python3; talks to the cluster API directly, no kubectl.
# Usage: argo_unstick.sh <project> <zone> <cluster> <log file>
set -u
PROJECT="$1"; ZONE="$2"; CLUSTER="$3"; LOG="$4"
TOKEN="$(gcloud auth application-default print-access-token 2>/dev/null || gcloud auth print-access-token)"
INFO="$(gcloud container clusters describe "$CLUSTER" --zone "$ZONE" --project "$PROJECT" --format='value(endpoint,masterAuth.clusterCaCertificate)' 2>/dev/null)" || exit 0
ENDPOINT="$(echo "$INFO" | cut -f1)"
CA="$(mktemp)"; echo "$INFO" | cut -f2 | base64 -d > "$CA"
API="https://$ENDPOINT/apis/argoproj.io/v1alpha1/namespaces/argocd/applications"
: > "$LOG"
for _ in $(seq 1 120); do
  NAMES="$(curl -s --max-time 10 --cacert "$CA" -H "Authorization: Bearer $TOKEN" "$API" | python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit()
for i in d.get("items",[]):
    if i["metadata"].get("deletionTimestamp"): print(i["metadata"]["name"])')"
  for N in $NAMES; do
    curl -s --max-time 10 --cacert "$CA" -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/merge-patch+json" -d '{"operation":null}' "$API/$N" >/dev/null && echo "$(date +%H:%M:%S) cleared sync on $N" >> "$LOG"
  done
  sleep 10
done
rm -f "$CA"
