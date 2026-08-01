#!/usr/bin/env bash
# Optional fallback: kubectl port-forward when kind host ports are not wired.
set -euo pipefail

CLUSTER_NAME="incident-commander"
CONTEXT="kind-${CLUSTER_NAME}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if curl -sf "http://localhost:9090/-/ready" >/dev/null 2>&1 && \
   curl -sf "http://localhost:3100/ready" >/dev/null 2>&1; then
  echo "Prometheus and Loki are already reachable on localhost:9090 and :3100."
  echo "No port-forward needed (kind host ports are wired)."
  exit 0
fi

if ! kubectl config get-contexts -o name 2>/dev/null | grep -qx "$CONTEXT"; then
  echo "Cluster context $CONTEXT not found. Run: ./scripts/setup-k8s.sh"
  exit 1
fi

kubectl config use-context "$CONTEXT"

cleanup() {
  echo ""
  echo "Stopping port-forwards..."
  jobs -p | xargs kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Kind host ports not detected — using kubectl port-forward."
echo "For permanent access, recreate the cluster:"
echo "  KIND_RECREATE=1 ./scripts/setup-k8s.sh && ./scripts/setup-observability.sh"
echo ""
echo "Forwarding Prometheus localhost:9090 and Loki localhost:3100..."
echo "Leave this terminal open while using incident-commander."
echo ""

kubectl port-forward -n monitoring svc/prometheus 9090:9090 &
kubectl port-forward -n monitoring svc/loki 3100:3100 &
wait
