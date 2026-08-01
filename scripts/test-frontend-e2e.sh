#!/usr/bin/env bash
# Smoke-test every REST endpoint the React UI uses (via API or Vite proxy).
set -euo pipefail

API="${FRONTEND_E2E_API:-http://localhost:8080/api}"
if curl -sf "http://localhost:3000/api/health" >/dev/null 2>&1; then
  API="http://localhost:3000/api"
  echo "==> Using Vite proxy: $API"
else
  echo "==> Using API directly: $API"
fi

fail() { echo "FAIL: $1"; exit 1; }
ok() { echo "OK: $1"; }

json() { python3 -c "import json,sys; print(json.load(sys.stdin)[$1])"; }

echo "==> health"
curl -sf "$API/health" | grep -q '"ok"' || fail "health"
ok "health"

echo "==> list incidents"
COUNT=$(curl -sf "$API/incidents" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
[[ "$COUNT" -ge 1 ]] || fail "list incidents (empty)"
ok "list incidents ($COUNT)"

ID=$(curl -sf "$API/incidents" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['incident_id'])")

echo "==> get incident $ID"
curl -sf "$API/incidents/$ID" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['incident_id']" || fail "get incident"
ok "get incident"

echo "==> postmortem"
curl -sf "$API/incidents/$ID/postmortem.md" | head -1 | grep -q '^#' || fail "postmortem"
ok "postmortem"

echo "==> create incident"
NEW=$(curl -sf -X POST "$API/incidents" \
  -H 'Content-Type: application/json' \
  -d '{"service":"payment-api","namespace":"default","trigger":"frontend-e2e","severity":"SEV3","environment":"prod"}')
NEW_ID=$(echo "$NEW" | python3 -c "import json,sys; print(json.load(sys.stdin)['incident_id'])")
ok "create incident $NEW_ID"

echo "==> investigate"
curl -sf -X POST "$API/incidents/$NEW_ID/investigate" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['incident_id']" || fail "investigate"
ok "investigate"

APR=$(curl -sf "$API/incidents/$NEW_ID" | python3 -c "
import json,sys
d=json.load(sys.stdin)
aps=d.get('approvals_pending') or []
print(aps[0]['id'] if aps else '')
")

if [[ -n "$APR" ]]; then
  echo "==> approve $APR"
  curl -sf -X POST "$API/incidents/$NEW_ID/approve" \
    -H 'Content-Type: application/json' \
    -d "{\"approval_id\":\"$APR\"}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['status'])" || fail "approve"
  ok "approve"
else
  echo "SKIP: approve (no pending approval on $NEW_ID)"
fi

echo ""
echo "All frontend API smoke tests passed."
