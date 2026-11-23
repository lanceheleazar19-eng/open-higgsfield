#!/usr/bin/env bash
# Ejecuta todas las pruebas de ATLAS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "== Backend ==";  (cd "$ROOT/backend" && .venv/bin/pytest -q -p no:warnings)
echo "== Frontend =="; (cd "$ROOT/frontend" && npx tsc -b && npx vitest run)
