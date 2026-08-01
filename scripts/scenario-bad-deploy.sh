#!/usr/bin/env bash
# Live scenario test: bad deploy → crashloop → incident-commander investigation.
# Restores healthy deployment on exit unless KEEP_BROKEN=1.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLUSTER_NAME="incident-commander"
CONTEXT="kind-${CLUSTER_NAME}"
NAMESPACE="${NAMESPACE:-default}"
SERVICE="${SERVICE:-payment-api}"

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
  echo "Cluster restored to healthy state."
}

trap restore EXIT

echo "==> Applying bad deploy scenario (crashloop + error logs)..."
kubectl apply -f "$ROOT/k8s/scenarios/bad-deploy-payment-api.yaml"

echo "==> Waiting for crashloop + error logs (up to 120s)..."
for _ in $(seq 1 24); do
  crash=$(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE" -o jsonpath='{range .items[*]}{.status.containerStatuses[0].state.waiting.reason}{"\n"}{end}' \
    | grep -c CrashLoopBackOff || true)
  restarts=$(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE" \
    -o jsonpath='{range .items[*]}{.status.containerStatuses[0].restartCount}{"\n"}{end}' \
    | awk '{s+=$1} END {print s+0}')
  if [[ "$crash" -ge 1 ]] || [[ "${restarts:-0}" -ge 2 ]]; then
    echo "Failure signals: crashloop_pods=$crash total_restarts=$restarts"
    break
  fi
  sleep 5
done

echo "==> Waiting 20s for Promtail → Loki log shipping..."
sleep 20

kubectl get pods -n "$NAMESPACE" -l app="$SERVICE"
echo ""

echo "==> Running incident-commander (live cluster + Prom + Loki + Groq)..."
cd "$ROOT"
if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/.venv/bin/activate"
fi

python3 << 'PY'
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
        trigger="scenario:bad-deploy",
        severity="SEV1",
        namespace="default",
        dedupe_minutes=0,
    )
    print()
    print("=" * 60)
    print(f"INCIDENT {inc.incident_id}  status={inc.status.value}")
    print("=" * 60)
    print("TIMELINE:")
    for e in inc.timeline:
        print(f"  [{e.source}] {e.event}")
    print()
    print("WORKERS:")
    for w in inc.worker_runs:
        print(f"  {w.worker}: {w.status} — {w.summary}")
    print()
    print("HYPOTHESES:")
    for h in inc.hypotheses:
        print(f"  {h.id} ({h.confidence:.0%}): {h.description}")
        for a in h.suggested_actions:
            print(f"    → {a.type}: {a.description} (approval={a.requires_approval})")
    if inc.approvals_pending:
        print()
        print("PENDING APPROVALS:")
        for p in inc.approvals_pending:
            print(f"  {p.id}: {p.action.type} — {p.action.description}")

asyncio.run(main())
PY

echo ""
echo "Done. Scenario report above."
echo "To inspect later: incident-commander list && incident-commander show <INC-ID>"
