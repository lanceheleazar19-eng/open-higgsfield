"""`python -m atlas` arranca el servidor. Si el puerto está ocupado, prueba los siguientes
(salvo con ATLAS_STRICT_PORT=1, que usa VISTAN Desktop: ahí el puerto lo elige la app).

Al arrancar escribe `data/runtime.json` (pid, puerto, versión) para que VISTAN Desktop y VISTAN Web
reutilicen la MISMA instancia y la misma base de datos en vez de lanzar otra."""

import atexit
import json
import os
import signal
import socket
import time

import uvicorn

from atlas import __version__
from atlas.config import get_settings


def _free_port(host: str, start: int, tries: int = 20) -> int | None:
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # igual que uvicorn: un puerto con conexiones en TIME_WAIT (tras un cierre brusco) se puede reutilizar
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return None


def runtime_file():  # noqa: ANN201
    return get_settings().resolved_data_dir / "runtime.json"


def _write_runtime(host: str, port: int) -> None:
    f = runtime_file()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"app": "vistan", "pid": os.getpid(), "host": host, "port": port, "version": __version__,
                                 "started_at": int(time.time()), "launcher": os.environ.get("ATLAS_LAUNCHER", "web")}))
    except OSError:
        return

    def _cleanup() -> None:
        try:
            if json.loads(f.read_text()).get("pid") == os.getpid():
                f.unlink()
        except (OSError, ValueError):
            pass
    atexit.register(_cleanup)

    def _on_term(signum, frame) -> None:  # noqa: ANN001, ARG001
        # uvicorn vuelve a lanzar SIGTERM tras cerrar ordenadamente; sin esto el proceso muere sin limpiar runtime.json
        _cleanup()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, _on_term)


def _running_instance() -> int | None:
    """Puerto de un VISTAN que ya funciona con estos mismos datos (para no lanzar otro sobre la misma base de datos)."""
    import urllib.request
    try:
        info = json.loads(runtime_file().read_text())
        port = int(info["port"])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/system/health", timeout=3) as r:  # noqa: S310 - solo 127.0.0.1
            return port if json.loads(r.read()).get("app") == "vistan" else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def main() -> None:
    s = get_settings()
    running = _running_instance()
    if running:
        # Sale con éxito: launchd no lo reintenta y VISTAN Desktop/Web comparten la instancia existente
        print(f"\n  ✅ VISTAN ya está funcionando con estos datos → http://127.0.0.1:{running}\n", flush=True)
        return
    strict = os.environ.get("ATLAS_STRICT_PORT") == "1"
    port = _free_port(s.host, s.port, 1 if strict else 20)
    if port is None:
        raise SystemExit(f"✖ El puerto {s.port} está ocupado." if strict else
                         f"✖ No hay puertos libres entre {s.port} y {s.port + 19}. Cierra otros programas o usa ATLAS_PORT=…")
    if port != s.port:
        print(f"▸ El puerto {s.port} está ocupado por otro programa; uso el {port}.")
    _write_runtime(s.host, port)
    print(f"\n  ✅ VISTAN listo → abre en el navegador: http://{s.host}:{port}\n", flush=True)
    uvicorn.run("atlas.main:app", host=s.host, port=port, reload=False, log_level="warning")


if __name__ == "__main__":
    main()
