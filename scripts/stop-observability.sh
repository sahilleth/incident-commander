#!/usr/bin/env bash
# Stop observability port-forwards started by setup-observability.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PF_FILE="$ROOT/.observability/port-forwards.pid"

if [[ ! -f "$PF_FILE" ]]; then
  echo "No port-forward PID file at $PF_FILE"
  exit 0
fi

while read -r pid; do
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    echo "Stopped PID $pid"
  fi
done < "$PF_FILE"

rm -f "$PF_FILE"
echo "Observability port-forwards stopped."
