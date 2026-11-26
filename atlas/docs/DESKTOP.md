# VISTAN Desktop · aplicación nativa para macOS

VISTAN Desktop **no es una aplicación nueva**: es una ventana nativa de macOS (Tauri 2) para el VISTAN de siempre.
- La interfaz es la misma (`frontend/`).
- El backend es el mismo (`backend/`, FastAPI).
- Los datos son los mismos (`data/atlas.db`).

VISTAN Web (`http://127.0.0.1:<puerto>` en el navegador) sigue funcionando igual. Ambas versiones comparten la **misma instancia** y la **misma base de datos**.

## Por qué Tauri
- Usa el WebView del propio sistema (WKWebView). La app ocupa unos pocos MB y no incluye un Chromium (Electron pesaría más de 150 MB).
- El código nativo es Rust, y la interfaz solo puede pedir una **lista cerrada de acciones** (*capabilities*).
- Reutiliza la interfaz React tal cual. No hace falta reescribir nada ni mantener dos frontends.
- El backend sigue siendo el proyecto Python existente. No se empaqueta otra copia, así que no hay datos duplicados.

## Cómo funciona
```
VISTAN.app (Rust/Tauri)
 ├─ arranca → pantalla nativa de inicio (ui/index.html)
 ├─ busca un VISTAN en marcha ── data/runtime.json + /api/system/health ("app": "vistan")
 │    ├─ existe (VISTAN Web, servicio de macOS…) → lo reutiliza (no lo detiene al salir)
 │    ├─ servicio de macOS instalado (autostart.sh) → launchctl kickstart
 │    └─ no existe → scripts/start.sh en 127.0.0.1:<puerto libre> (grupo de procesos propio)
 ├─ ventana principal → http://127.0.0.1:<puerto>/ (la interfaz de siempre)
 ├─ vigilancia cada 4 s → reconexión o reinicio controlado (máx. 5 en 10 min)
 └─ ⌘Q / cierre de sesión → detiene SOLO el backend que arrancó ella
```

## Funcionalidades
| | |
|---|---|
| Ventana | <ul><li>Barra de título integrada (los botones del semáforo sobre la cabecera de VISTAN).</li><li>Modo oscuro, redimensionable, pantalla completa (⌃⌘F), minimizar y zoom.</li><li>Recuerda el tamaño y la posición.</li></ul> |
| Dock | <ul><li>Cerrar la ventana (⌘W o el botón rojo) la oculta y la app sigue en el Dock.</li><li>Al hacer clic en el Dock vuelve a aparecer.</li><li>⌘Q sale.</li></ul> |
| Menú nativo | <ul><li>Menús: VISTAN, Edición (copiar/pegar), Visualización, Ir (⌘1…⌘9), Sistema y Ventana.</li><li>Atajos: ⌘, abre Configuración; ⇧⌘, abre Permisos y privacidad; ⌘R recarga; ⌘[ / ⌘] van atrás y adelante.</li></ul> |
| Atajo global | ⌥Espacio (configurable) muestra u oculta VISTAN desde cualquier app. |
| Notificaciones | <ul><li>Nativas de macOS.</li><li>Los recordatorios y la campana existentes las usan sin cambios: el puente sustituye la API `Notification` del navegador.</li></ul> |
| Archivos | <ul><li>Selector nativo de macOS en todos los botones de subir documentos e imágenes.</li><li>También se puede arrastrar y soltar.</li><li>VISTAN solo lee lo que eliges.</li></ul> |
| Micrófono | Solo con tu autorización (`NSMicrophoneUsageDescription`). Se puede probar desde Permisos y privacidad. |
| Portapapeles | Copia nativa (⌘C/⌘V del menú Edición). |
| Enlaces externos | Siempre en tu navegador predeterminado. La ventana de VISTAN nunca navega a otras webs. |
| Inicio automático | Opcional: abrir al iniciar sesión (LaunchAgent del usuario). |
| Una sola instancia | <ul><li>Abrir la app otra vez enfoca la ventana existente.</li><li>Nunca se lanzan dos backends sobre los mismos datos (también desde `start.sh`).</li></ul> |
| Actualizar | Menú Sistema › Actualizar VISTAN…: hace `git pull --ff-only` tras pedirte confirmación y reinicia el backend. Avisa si la propia app necesita recompilarse. |
| Permisos y privacidad | Ventana secundaria nativa (`/desktop`) con el estado del sistema, los permisos y las pruebas. |

## Seguridad
- **Backend local:**
  - escucha solo en 127.0.0.1;
  - `TrustedHostMiddleware` rechaza cualquier `Host` que no sea 127.0.0.1, localhost o `*.ts.net` (Tailscale), lo que impide el *DNS rebinding*;
  - la identificación en `/api/system/health` evita confundir otro programa con VISTAN.
- **Puertos y procesos:**
  - si el puerto está ocupado por otro programa, la app no lo toca y usa el siguiente;
  - al salir solo se detiene el grupo de procesos que la app creó.
- **IPC mínima:**
  - la interfaz servida en `http://127.0.0.1:<puerto activo>` recibe en tiempo de ejecución una *capability* con 14 órdenes concretas más arrastrar y maximizar la ventana;
  - no hay plugin de *shell*, ni lectura de archivos, ni órdenes arbitrarias;
  - la pantalla de arranque tiene su propia capacidad, aún más reducida.
- **Claves API:**
  - siguen en el Llavero (vía backend);
  - la app nunca las lee ni las envía a la interfaz;
  - `desktop.json` solo guarda la carpeta del proyecto, el puerto preferido y el atajo.
- **Hardened Runtime:** `Entitlements.plist` solo declara el micrófono.

## Compilar e instalar (en tu Mac)
Requisitos:
- Herramientas de Xcode (`xcode-select --install`).
- Node.js.
- Rust: el script ofrece instalarlo y pide confirmación.

```bash
cd ~/open-higgsfield && git pull && ./atlas/desktop/scripts/build-macos.sh
```
Resultado:
- `atlas/desktop/dist/VISTAN.app`
- `atlas/desktop/dist/VISTAN_1.0.0_aarch64.dmg`

El script ofrece copiar la app a /Applications y pide confirmación antes de reemplazar una existente.

También se puede compilar en GitHub. El flujo **VISTAN Desktop (macOS)** (`.github/workflows/vistan-desktop-macos.yml`) deja el DMG como artefacto descargable.

### Firma y notarización
- Sin certificado, la app se firma **ad-hoc**:
  - abre sin problemas en el Mac donde se compila;
  - **no está firmada por Apple ni notarizada**;
  - si descargas el DMG del artefacto de GitHub, la primera vez macOS pedirá abrirla con clic derecho › Abrir, o desde Ajustes › Privacidad y seguridad.
- Con una cuenta de Apple Developer (99 USD/año), exporta antes de compilar estas variables, o crea los secretos `APPLE_*` en GitHub:
  - `APPLE_SIGNING_IDENTITY="Developer ID Application: …"`;
  - para notarizar: `APPLE_ID`, `APPLE_PASSWORD` (contraseña de app) y `APPLE_TEAM_ID`.

## Limitaciones conocidas
- La app necesita el proyecto en el Mac (`~/open-higgsfield/atlas` o la carpeta que elijas en la pantalla de inicio): usa ese backend y esos datos, no una copia. La primera apertura puede tardar si `start.sh` tiene que instalar dependencias o compilar la interfaz.
- El dictado por voz usa la Web Speech API. En WKWebView su disponibilidad depende de la versión de macOS. La síntesis de voz y el micrófono (getUserMedia) sí están disponibles.
- Las actualizaciones automáticas firmadas del propio binario (Tauri updater) requieren claves de firma y un servidor de versiones: están preparadas (versión en `tauri.conf.json`, aviso de recompilación), pero no activadas.
