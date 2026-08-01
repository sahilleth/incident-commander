#!/usr/bin/env bash
# Start local kind cluster + sample deployment for Incident Commander
set -euo pipefail

CLUSTER_NAME="incident-commander"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KIND_CONFIG="$ROOT/k8s/kind-config.yaml"

if ! command -v kind >/dev/null; then
  echo "Install kind: brew install kind"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop first."
  exit 1
fi

cluster_has_host_ports() {
  local container="incident-commander-control-plane"
  if ! docker ps --format '{{.Names}}' | grep -qx "$container"; then
    return 1
  fi
  docker port "$container" 2>/dev/null | grep -q '9090' && \
    docker port "$container" 2>/dev/null | grep -q '3100'
}

if kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
  if cluster_has_host_ports; then
    echo "Cluster $CLUSTER_NAME already exists (host ports 9090/3100 wired)"
  else
    echo "Cluster $CLUSTER_NAME exists but lacks host port mappings for Prometheus/Loki."
    if [[ "${KIND_RECREATE:-}" == "1" ]]; then
      echo "KIND_RECREATE=1 — deleting and recreating cluster with port mappings..."
      kind delete cluster --name "$CLUSTER_NAME"
    else
      echo ""
      echo "Recreate the cluster to wire localhost:9090 and :3100 (no port-forward needed):"
      echo "  KIND_RECREATE=1 ./scripts/setup-k8s.sh"
      echo ""
      exit 1
    fi
  fi
fi

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
  echo "Creating kind cluster: $CLUSTER_NAME (Prometheus :9090, Loki :3100 on host)..."
  kind create cluster --name "$CLUSTER_NAME" --config "$KIND_CONFIG"
fi

kubectl config use-context "kind-${CLUSTER_NAME}"
kubectl apply -f "$ROOT/k8s/sample-payment-api.yaml"
kubectl rollout status deployment/payment-api --timeout=120s

echo ""
echo "Cluster ready. Context: kind-${CLUSTER_NAME}"
echo "Sample deployment: payment-api (default namespace)"
echo "Host URLs (after setup-observability): http://localhost:9090  http://localhost:3100"
echo ""
echo "Next:"
echo "  ./scripts/setup-observability.sh"
echo "  cd $ROOT && source .venv/bin/activate"
echo "  incident-commander doctor"
echo "  incident-commander open payment-api --namespace default"
