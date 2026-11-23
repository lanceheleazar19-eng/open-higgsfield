#!/usr/bin/env bash
# Arranca ATLAS (Linux / macOS). Instala dependencias la primera vez.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

if [ ! -x .venv/bin/python ]; then
  echo "▸ Creando entorno Python…"
  if command -v uv >/dev/null; then
    # uv descarga un Python moderno si el del sistema es antiguo (macOS trae 3.9)
    uv venv -q --python ">=3.11" .venv
  else
    PY=""
    for c in python3.13 python3.12 python3.11 python3; do
      if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then PY="$c"; break; fi
    done
    if [ -z "$PY" ]; then
      echo "✖ Necesitas Python 3.11 o superior. La forma más fácil: instala uv con"
      echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
      echo "  y vuelve a ejecutar este script."
      exit 1
    fi
    "$PY" -m venv .venv
  fi
fi
if ! .venv/bin/python -c "import atlas" 2>/dev/null; then
  echo "▸ Instalando backend…"
  if command -v uv >/dev/null; then uv pip install -q --python .venv -e ".[dev]"; else .venv/bin/pip install -q -e ".[dev]"; fi
fi
[ -f .env ] || cp .env.example .env

cd "$ROOT/frontend"
if ! command -v npm >/dev/null; then
  echo "✖ Falta Node.js. Instálalo desde https://nodejs.org (versión LTS) y vuelve a ejecutar este script."
  exit 1
fi
if [ ! -d node_modules ]; then echo "▸ Instalando frontend…"; npm install --no-fund --no-audit; fi
if [ ! -f dist/index.html ] || [ "${1:-}" = "--rebuild" ]; then echo "▸ Compilando interfaz…"; npm run build; fi

cd "$ROOT/backend"
echo "▸ ATLAS en http://127.0.0.1:${ATLAS_PORT:-8000}"
exec .venv/bin/python -m atlas
