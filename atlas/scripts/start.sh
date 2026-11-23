#!/usr/bin/env bash
# Arranca ATLAS (Linux / macOS). Instala dependencias la primera vez.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

if [ ! -x .venv/bin/python ]; then
  echo "▸ Creando entorno Python…"
  if command -v uv >/dev/null; then uv venv -q .venv; else python3 -m venv .venv; fi
fi
if ! .venv/bin/python -c "import atlas" 2>/dev/null; then
  echo "▸ Instalando backend…"
  if command -v uv >/dev/null; then uv pip install -q --python .venv -e ".[dev]"; else .venv/bin/pip install -q -e ".[dev]"; fi
fi
[ -f .env ] || cp .env.example .env

cd "$ROOT/frontend"
if [ ! -d node_modules ]; then echo "▸ Instalando frontend…"; npm install --no-fund --no-audit; fi
if [ ! -f dist/index.html ] || [ "${1:-}" = "--rebuild" ]; then echo "▸ Compilando interfaz…"; npm run build; fi

cd "$ROOT/backend"
echo "▸ ATLAS en http://127.0.0.1:${ATLAS_PORT:-8000}"
exec .venv/bin/python -m atlas
