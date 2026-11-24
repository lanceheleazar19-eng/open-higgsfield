"""`python -m atlas` arranca el servidor. Si el puerto está ocupado, prueba los siguientes."""

import socket

import uvicorn

from atlas.config import get_settings


def _free_port(host: str, start: int, tries: int = 20) -> int | None:
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return None


def main() -> None:
    s = get_settings()
    port = _free_port(s.host, s.port)
    if port is None:
        raise SystemExit(f"✖ No hay puertos libres entre {s.port} y {s.port + 19}. Cierra otros programas o usa ATLAS_PORT=…")
    if port != s.port:
        print(f"▸ El puerto {s.port} está ocupado por otro programa; uso el {port}.")
    print(f"\n  ✅ VISTAN listo → abre en el navegador: http://{s.host}:{port}\n", flush=True)
    uvicorn.run("atlas.main:app", host=s.host, port=port, reload=False, log_level="warning")


if __name__ == "__main__":
    main()
