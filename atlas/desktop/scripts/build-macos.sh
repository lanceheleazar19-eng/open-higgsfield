#!/usr/bin/env bash
# Compila VISTAN Desktop en tu Mac y deja VISTAN.app y el DMG en atlas/desktop/dist/.
#   ./atlas/desktop/scripts/build-macos.sh
# Firma: sin certificado de Apple se firma «ad-hoc» (funciona en tu Mac, pero NO está firmada por Apple ni notarizada).
# Con certificado Developer ID, exporta antes APPLE_SIGNING_IDENTITY (y APPLE_ID, APPLE_PASSWORD, APPLE_TEAM_ID para notarizar).
set -euo pipefail
DESK="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$DESK/.." && pwd)"
OUT="$DESK/dist"

[ "$(uname)" = "Darwin" ] || { echo "✖ Este script es para macOS."; exit 1; }
xcode-select -p >/dev/null 2>&1 || { echo "✖ Faltan las herramientas de línea de comandos de Xcode. Instálalas con:  xcode-select --install"; exit 1; }
command -v npm >/dev/null || { echo "✖ Falta Node.js (https://nodejs.org, versión LTS)."; exit 1; }
[ -x "$HOME/.cargo/bin/cargo" ] && export PATH="$HOME/.cargo/bin:$PATH"
if ! command -v cargo >/dev/null; then
  echo "Rust no está instalado. Solo hace falta para compilar la app (unos 1,5 GB en ~/.rustup y ~/.cargo)."
  read -r -p "¿Instalarlo ahora con el instalador oficial (rustup.rs)? [s/N] " r
  [[ "$r" =~ ^[sS]$ ]] || { echo "Cancelado. Puedes instalarlo tú desde https://rustup.rs y repetir."; exit 1; }
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
  export PATH="$HOME/.cargo/bin:$PATH"
fi

echo "▸ Preparando VISTAN (backend e interfaz)…"
ATLAS_PREPARE_ONLY=1 "$ROOT/scripts/start.sh"

echo "▸ Preparando herramientas de compilación…"
cd "$DESK"
npm install --no-fund --no-audit

if [ -z "${APPLE_SIGNING_IDENTITY:-}" ]; then
  echo "▸ Sin certificado de Apple: firma ad-hoc (válida en este Mac; no notarizada)."
  export APPLE_SIGNING_IDENTITY="-"
fi

echo "▸ Compilando VISTAN.app y el DMG (la primera vez tarda varios minutos)…"
npx tauri build --bundles app,dmg

BUNDLE="$DESK/src-tauri/target/release/bundle"
mkdir -p "$OUT"
rm -rf "$OUT/VISTAN.app"
ditto "$BUNDLE/macos/VISTAN.app" "$OUT/VISTAN.app"
DMG="$(ls -t "$BUNDLE"/dmg/*.dmg | head -1)"
cp -f "$DMG" "$OUT/"
echo
echo "✅ Listo:"
echo "   App: $OUT/VISTAN.app"
echo "   DMG: $OUT/$(basename "$DMG")"
codesign -dv "$OUT/VISTAN.app" 2>&1 | grep -E "^(Signature|Authority|TeamIdentifier)" | sed 's/^/   /' || true
if [ "$APPLE_SIGNING_IDENTITY" = "-" ]; then
  echo "   Firma: ad-hoc (no firmada por Apple ni notarizada). Es normal para uso propio en este Mac."
fi

if [ -t 0 ]; then
  read -r -p "¿Instalar VISTAN en /Applications ahora? [s/N] " r
  if [[ "$r" =~ ^[sS]$ ]]; then
    if [ -d /Applications/VISTAN.app ]; then
      read -r -p "Ya existe /Applications/VISTAN.app. ¿Reemplazarla? (tus datos no están dentro de la app) [s/N] " r2
      [[ "$r2" =~ ^[sS]$ ]] || { echo "No se ha tocado la app instalada."; exit 0; }
      osascript -e 'tell application "VISTAN" to quit' >/dev/null 2>&1 || true
      sleep 1
      rm -rf /Applications/VISTAN.app
    fi
    ditto "$OUT/VISTAN.app" /Applications/VISTAN.app
    echo "✅ Instalada en /Applications. Ábrela desde Launchpad, Spotlight o el Dock."
  fi
fi
