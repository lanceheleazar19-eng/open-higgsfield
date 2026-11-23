#!/usr/bin/env bash
# Arranca ATLAS (macOS / Linux). Instala o actualiza lo necesario automáticamente.
# Uso: ./scripts/start.sh            (añade --rebuild para forzar recompilar la interfaz)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

hash_of() { (shasum -a 256 "$@" 2>/dev/null || sha256sum "$@") | awk '{print $1}' | tr -d '\n'; }

# ---------- Backend (Python) ----------
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
# Reinstala dependencias solo si pyproject.toml ha cambiado desde la última vez
DEPS_HASH="$(hash_of pyproject.toml)"
if [ "$(cat .venv/.atlas-deps 2>/dev/null || true)" != "$DEPS_HASH" ]; then
  echo "▸ Instalando dependencias del backend…"
  if command -v uv >/dev/null; then uv pip install -q --python .venv -e ".[dev]"; else .venv/bin/pip install -q -e ".[dev]"; fi
  echo "$DEPS_HASH" > .venv/.atlas-deps
fi
if [ ! -f .env ] && [ -f .env.example ]; then cp .env.example .env; fi

# ---------- Frontend (interfaz) ----------
cd "$ROOT/frontend"
if ! command -v npm >/dev/null; then
  echo "✖ Falta Node.js. Instálalo desde https://nodejs.org (versión LTS) y vuelve a ejecutar este script."
  exit 1
fi
LOCK_HASH="$(hash_of package-lock.json)"
if [ ! -d node_modules ] || [ "$(cat node_modules/.atlas-deps 2>/dev/null || true)" != "$LOCK_HASH" ]; then
  echo "▸ Instalando dependencias de la interfaz…"
  npm install --no-fund --no-audit
  echo "$LOCK_HASH" > node_modules/.atlas-deps
fi
# Recompila si no hay build, si se pide, o si el código es más nuevo que el build
if [ ! -f dist/index.html ] || [ "${1:-}" = "--rebuild" ] || \
   [ -n "$(find src index.html package.json vite.config.ts -newer dist/index.html -print -quit 2>/dev/null)" ]; then
  echo "▸ Compilando la interfaz…"
  npm run build
fi

# ---------- Arranque ----------
[ "${ATLAS_PREPARE_ONLY:-}" = "1" ] && exit 0  # autostart.sh solo quiere preparar
cd "$ROOT/backend"
echo "▸ Arrancando ATLAS… (Ctrl+C para detener)"
exec .venv/bin/python -m atlas
