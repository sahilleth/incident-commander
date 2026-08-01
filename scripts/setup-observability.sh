#!/usr/bin/env bash
# Install Prometheus + Loki (+ promtail, kube-state-metrics) on the kind cluster.
set -euo pipefail

CLUSTER_NAME="incident-commander"
CONTEXT="kind-${CLUSTER_NAME}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MON_DIR="$ROOT/k8s/monitoring"

if ! command -v kubectl >/dev/null; then
  echo "kubectl not found"
  exit 1
fi

if ! kubectl config get-contexts -o name 2>/dev/null | grep -qx "$CONTEXT"; then
  echo "Cluster context $CONTEXT not found. Run: ./scripts/setup-k8s.sh"
  exit 1
fi

kubectl config use-context "$CONTEXT"

echo "Applying monitoring manifests..."
kubectl apply -f "$MON_DIR/namespace.yaml"
kubectl apply -f "$MON_DIR/kube-state-metrics.yaml"
kubectl apply -f "$MON_DIR/prometheus.yaml"
kubectl apply -f "$MON_DIR/loki.yaml"
kubectl apply -f "$MON_DIR/promtail.yaml"

echo "Waiting for monitoring workloads..."
kubectl rollout status deployment/kube-state-metrics -n monitoring --timeout=180s
kubectl rollout status deployment/prometheus -n monitoring --timeout=180s
kubectl rollout status deployment/loki -n monitoring --timeout=180s
kubectl rollout status daemonset/promtail -n monitoring --timeout=180s

echo ""
echo "Observability stack installed in namespace: monitoring"
echo ""
echo "Prometheus: http://localhost:9090  (kind host port — no port-forward needed)"
echo "Loki:       http://localhost:3100  (kind host port — no port-forward needed)"
echo ""
echo "Add to .env:"
echo "  LOG_BACKEND=loki"
echo "  PROMETHEUS_URL=http://localhost:9090"
echo "  LOKI_URL=http://localhost:3100"
echo ""
echo "Verify: incident-commander doctor"

# Quick reachability check when kind host ports are wired
if curl -sf "http://localhost:9090/-/ready" >/dev/null 2>&1; then
  echo "Prometheus reachable on localhost:9090"
else
  echo "WARN: localhost:9090 not reachable — recreate cluster with:"
  echo "  KIND_RECREATE=1 ./scripts/setup-k8s.sh"
fi

if curl -sf "http://localhost:3100/ready" >/dev/null 2>&1; then
  echo "Loki reachable on localhost:3100"
else
  echo "WARN: localhost:3100 not reachable — recreate cluster with:"
  echo "  KIND_RECREATE=1 ./scripts/setup-k8s.sh"
fi
