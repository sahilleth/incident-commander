#!/usr/bin/env bash
# Build and upload incident-commander to PyPI (requires PyPI API token).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "${PYPI_API_TOKEN:-}" ]]; then
  echo "Set PYPI_API_TOKEN to your PyPI API token (pypi-...)."
  echo "Create one at: https://pypi.org/manage/account/token/"
  exit 1
fi

python3 -m pip install --upgrade build twine -q
rm -rf dist/
python3 -m build

echo "Uploading to PyPI..."
TWINE_USERNAME=__token__ TWINE_PASSWORD="$PYPI_API_TOKEN" \
  python3 -m twine upload dist/*

echo "Published. Verify: pip install incident-commander"
