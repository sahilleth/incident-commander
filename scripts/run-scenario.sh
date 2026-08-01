#!/usr/bin/env bash
# Run a live failure scenario and investigate with incident-commander.
# Usage: ./scripts/run-scenario.sh <scenario-name>
# Scenarios: bad-deploy | imagepull | oom | crashloop-runtime
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLUSTER_NAME="incident-commander"
CONTEXT="kind-${CLUSTER_NAME}"
NAMESPACE="${NAMESPACE:-default}"
SERVICE="${SERVICE:-payment-api}"
SCENARIO="${1:-}"

if [[ -z "$SCENARIO" ]]; then
  echo "Usage: $0 <scenario>"
  echo "  bad-deploy          — bad rollout + NPE logs"
  echo "  imagepull           — ImagePullBackOff"
  echo "  oom                 — OOMKilled (low memory limit)"
  echo "  crashloop-runtime   — crashloop + dependency errors (no deploy story)"
  exit 1
fi

case "$SCENARIO" in
  bad-deploy) MANIFEST="bad-deploy-payment-api.yaml" ;;
  imagepull) MANIFEST="imagepull-payment-api.yaml" ;;
  oom) MANIFEST="oom-payment-api.yaml" ;;
  crashloop-runtime) MANIFEST="crashloop-runtime-payment-api.yaml" ;;
  *)
    echo "Unknown scenario: $SCENARIO"
    exit 1
    ;;
esac

if ! kubectl config get-contexts -o name 2>/dev/null | grep -qx "$CONTEXT"; then
  echo "Cluster $CONTEXT not found. Run: ./scripts/setup-k8s.sh"
  exit 1
fi

kubectl config use-context "$CONTEXT"

restore() {
  if [[ "${KEEP_BROKEN:-}" == "1" ]]; then
    echo "KEEP_BROKEN=1 — leaving broken deployment in place"
    return
  fi
  echo ""
  echo "Restoring healthy payment-api deployment..."
  kubectl apply -f "$ROOT/k8s/sample-payment-api.yaml"
  kubectl rollout status "deployment/$SERVICE" -n "$NAMESPACE" --timeout=120s
}

trap restore EXIT

echo "==> Scenario: $SCENARIO ($MANIFEST)"
kubectl apply -f "$ROOT/k8s/scenarios/$MANIFEST"

echo "==> Waiting for failure signals (up to 120s)..."
for _ in $(seq 1 24); do
  crash=$(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE" -o jsonpath='{range .items[*]}{.status.containerStatuses[0].state.waiting.reason}{"\n"}{end}' 2>/dev/null \
    | grep -cE 'CrashLoopBackOff|ImagePullBackOff|ErrImagePull' || true)
  oom=$(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE" -o jsonpath='{range .items[*]}{.status.containerStatuses[0].lastState.terminated.reason}{"\n"}{end}' 2>/dev/null \
    | grep -c OOMKilled || true)
  restarts=$(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE" \
    -o jsonpath='{range .items[*]}{.status.containerStatuses[0].restartCount}{"\n"}{end}' \
    | awk '{s+=$1} END {print s+0}')
  if [[ "$crash" -ge 1 ]] || [[ "$oom" -ge 1 ]] || [[ "${restarts:-0}" -ge 2 ]]; then
    echo "Signals: image/crash=$crash oom=$oom restarts=$restarts"
    break
  fi
  sleep 5
done

echo "==> Waiting 20s for log shipping..."
sleep 20
kubectl get pods -n "$NAMESPACE" -l app="$SERVICE"
echo ""

cd "$ROOT"
if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/.venv/bin/activate"
fi

python3 << PY
import asyncio
from incident_commander.config import get_settings
from incident_commander.orchestrator.commander import IncidentCommander
from incident_commander.state.store import IncidentStore

async def main():
    s = get_settings()
    store = IncidentStore(s.incident_db_path)
    await store.init()
    cmd = IncidentCommander(s, store)
    inc = await cmd.open_incident(
        service="payment-api",
        trigger=f"scenario:${SCENARIO}",
        namespace="default",
        dedupe_minutes=0,
    )
    print(f"\nINCIDENT {inc.incident_id} status={inc.status.value}")
    for e in inc.timeline:
        print(f"  [{e.source}] {e.event[:100]}")
    for h in inc.hypotheses[:3]:
        print(f"  {h.id} ({h.confidence:.0%}): {h.description[:90]}")
    for p in inc.approvals_pending:
        print(f"  APPROVAL {p.id}: {p.action.type}")

asyncio.run(main())
PY

echo ""
echo "UI: incident-commander serve → http://localhost:8080/"
