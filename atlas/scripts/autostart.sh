#!/usr/bin/env bash
# VISTAN en segundo plano en macOS (sin ventana de Terminal). Usa un LaunchAgent de tu usuario:
# arranca al iniciar sesión y se reinicia solo si se cae.
#   ./atlas/scripts/autostart.sh install     activar (y arrancar ya)
#   ./atlas/scripts/autostart.sh restart     reiniciar (p. ej. tras actualizar con git pull)
#   ./atlas/scripts/autostart.sh status      ¿está funcionando?
#   ./atlas/scripts/autostart.sh logs        ver el registro
#   ./atlas/scripts/autostart.sh uninstall   desactivar
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.atlas.personal"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/atlas.log"
PORT="${ATLAS_PORT:-8000}"
DOMAIN="gui/$(id -u)"

[ "$(uname)" = "Darwin" ] || { echo "✖ Este script es para macOS."; exit 1; }

esc() { sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' <<<"$1"; }

case "${1:-}" in
  install)
    # macOS no deja que los procesos en segundo plano entren en Documentos, Escritorio, Descargas ni iCloud Drive
    case "$ROOT" in
      "$HOME/Documents"*|"$HOME/Desktop"*|"$HOME/Downloads"*|"$HOME/Library/Mobile Documents"*)
        echo "✖ VISTAN está en una carpeta protegida por macOS ($ROOT)."
        echo "  En segundo plano no podría leerla. Muévelo a tu carpeta personal y repite:"
        echo "    ./atlas/scripts/autostart.sh uninstall && cd ~ && mv \"$(dirname "$ROOT")\" ~/ && cd ~/$(basename "$(dirname "$ROOT")") && ./atlas/scripts/autostart.sh install"
        exit 1 ;;
    esac
    # Prepara dependencias e interfaz ahora (con mensajes visibles), no en segundo plano
    echo "▸ Preparando VISTAN…"
    ATLAS_PREPARE_ONLY=1 "$ROOT/scripts/start.sh"
    if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 && ! launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
      echo "✖ El puerto $PORT está ocupado. Si tienes VISTAN abierto en otra Terminal, ciérralo con Ctrl+C y repite."
      exit 1
    fi
    mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
    cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$(esc "$ROOT/scripts/start.sh")</string></array>
  <key>WorkingDirectory</key><string>$(esc "$ROOT")</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$(esc "$PATH:/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin")</string>
    <key>ATLAS_PORT</key><string>$PORT</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>15</integer>
  <key>StandardOutPath</key><string>$(esc "$LOG")</string>
  <key>StandardErrorPath</key><string>$(esc "$LOG")</string>
</dict></plist>
PL
    # bootout es asíncrono: si se hace bootstrap antes de que macOS lo libere da «Bootstrap failed: 5».
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    for _ in $(seq 1 20); do launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1 || break; sleep 0.5; done
    launchctl enable "$DOMAIN/$LABEL" 2>/dev/null || true
    ok=0
    for i in 1 2 3 4 5; do
      if launchctl bootstrap "$DOMAIN" "$PLIST" 2>/dev/null; then ok=1; break; fi
      # Puede que ya esté cargado: en ese caso basta con reiniciarlo
      if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then launchctl kickstart -k "$DOMAIN/$LABEL" && ok=1 && break; fi
      sleep "$i"
    done
    if [ "$ok" != 1 ]; then
      echo "✖ macOS no ha aceptado el servicio en segundo plano."
      echo "  Arráncalo de momento en esta Terminal con: ./atlas/scripts/start.sh"
      exit 1
    fi
    echo "▸ Arrancando en segundo plano…"
    for _ in $(seq 1 30); do
      if curl -fsS "http://127.0.0.1:$PORT/api/system/health" >/dev/null 2>&1; then
        echo "✅ VISTAN funciona en segundo plano → http://127.0.0.1:$PORT"
        echo "   Arrancará solo cada vez que enciendas el Mac. Ya puedes cerrar la Terminal."
        TS=/Applications/Tailscale.app/Contents/MacOS/Tailscale
        if [ -x "$TS" ]; then "$TS" serve --bg "$PORT" >/dev/null 2>&1 && echo "   Tailscale apunta al puerto $PORT (móvil listo)."; fi
        exit 0
      fi
      sleep 1
    done
    echo "✖ No ha arrancado. Mira el registro con: ./atlas/scripts/autostart.sh logs"
    exit 1 ;;
  restart)
    launchctl kickstart -k "$DOMAIN/$LABEL" && echo "✅ VISTAN reiniciado." ;;
  status)
    if curl -fsS "http://127.0.0.1:$PORT/api/system/health" >/dev/null 2>&1; then echo "✅ VISTAN funcionando → http://127.0.0.1:$PORT"
    else echo "✖ VISTAN no responde en el puerto $PORT. Registro: ./atlas/scripts/autostart.sh logs"; fi ;;
  logs)
    tail -n 40 "$LOG" ;;
  uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "✅ Desactivado. VISTAN ya no arrancará solo (puedes seguir usando start.sh)." ;;
  *)
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//' ; exit 1 ;;
esac
