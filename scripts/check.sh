#!/usr/bin/env bash
# Run all project health checks — exit non-zero on any failure.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Python compile"
python3 -m compileall -q src tests scripts

echo "==> Install editable package"
python3 -m pip install -e ".[dev]" -q

echo "==> Unit + eval tests (heuristic, no Groq)"
pytest -q

echo "==> Eval CLI"
incident-commander eval

echo "==> All checks passed"
