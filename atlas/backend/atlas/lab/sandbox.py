"""Sandbox de experimentos de software: ejecuta Python en un PROCESO SEPARADO y restringido, nunca dentro de VISTAN.

Medidas (POSIX): carpeta temporal propia que se borra al terminar, entorno vacío (sin tus variables ni claves),
modo aislado de Python (-I: sin site-packages del usuario ni PYTHONPATH), límites de CPU, memoria, tamaño de archivos y
procesos, tiempo máximo, salida truncada, y bloqueo de red y de subprocesos dentro del intérprete.
Limitación honesta: no es una máquina virtual ni un contenedor; por eso cada ejecución requiere tu confirmación
explícita y se registra. No se ejecuta nunca código de forma automática."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time

MAX_CODE = 20_000
TIMEOUT_S = 10
MAX_OUT = 20_000

PRELUDE = r'''
import builtins, io, socket, sys, os as _o
_ROOT = _o.path.realpath(_o.getcwd())
def _blocked(*a, **k):
    raise PermissionError("Bloqueado en el sandbox de VISTAN")
def _inside(p):
    try:
        rp = _o.path.realpath(_o.fspath(p)) if not isinstance(p, int) else None
    except TypeError:
        return False
    return rp is not None and (rp == _ROOT or rp.startswith(_ROOT + _o.sep))
_real_open, _real_osopen = io.open, _o.open
def _open(file, *a, **k):
    if not _inside(file):
        raise PermissionError("Solo se puede leer/escribir dentro de la carpeta del sandbox")
    return _real_open(file, *a, **k)
def _osopen(path, *a, **k):
    if not _inside(path):
        raise PermissionError("Solo se puede leer/escribir dentro de la carpeta del sandbox")
    return _real_osopen(path, *a, **k)
builtins.open = io.open = _open
_o.open = _osopen
for _n in ("listdir", "scandir", "chdir", "rename", "replace", "symlink", "link", "chmod", "chown"):
    if hasattr(_o, _n):
        setattr(_o, _n, _blocked)
io.FileIO = _blocked
socket.socket = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
import os as _os, subprocess as _sp
for _n in ("system", "popen", "fork", "forkpty", "execv", "execve", "execvp", "execvpe", "spawnv", "spawnve", "kill", "killpg", "remove", "rmdir", "unlink"):
    if hasattr(_os, _n):
        setattr(_os, _n, _blocked)
_sp.Popen = _blocked
_sp.run = _blocked
_sp.call = _blocked
_sp.check_output = _blocked
try:
    import ctypes as _ct
    _ct.CDLL = _blocked
    del _ct
except ImportError:
    pass
del _os, _sp
'''

BANNED = ("import ctypes", "__import__", "importlib", "sys.modules", "_io", "_real_open", "_real_osopen", "_ROOT", "__builtins__", "_o.", "gc.get_referents")


def _limits() -> None:  # pragma: no cover - se ejecuta en el hijo
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_S, TIMEOUT_S))
        resource.setrlimit(resource.RLIMIT_FSIZE, (5_000_000, 5_000_000))
        try:
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        except (ValueError, OSError):
            pass  # macOS no siempre permite limitar la memoria virtual
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        except (ValueError, OSError):
            pass
    except ImportError:
        pass
    os.setsid()


def run_python(code: str) -> dict:
    if not code.strip():
        return {"status": "blocked", "stdout": "", "stderr": "Código vacío", "exit_code": None, "duration_ms": 0}
    if len(code) > MAX_CODE:
        return {"status": "blocked", "stdout": "", "stderr": f"Máximo {MAX_CODE} caracteres", "exit_code": None, "duration_ms": 0}
    low = code.replace(" ", "")
    for b in BANNED:
        if b.replace(" ", "") in low:
            return {"status": "blocked", "stdout": "", "stderr": f"Patrón no permitido en el sandbox: {b}", "exit_code": None, "duration_ms": 0}
    work = tempfile.mkdtemp(prefix="vistan-sandbox-")
    path = os.path.join(work, "main.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(PRELUDE + "\n" + code)
    env = {"PATH": "/usr/bin:/bin", "HOME": work, "TMPDIR": work, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    t0 = time.perf_counter()
    try:
        p = subprocess.run([sys.executable, "-I", "-B", path], cwd=work, env=env, capture_output=True, text=True,
                           timeout=TIMEOUT_S + 2, preexec_fn=_limits if os.name == "posix" else None)  # noqa: PLW1509
        status = "ok" if p.returncode == 0 else "limit" if p.returncode < 0 else "error"
        out, err, code_ = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as exc:
        status, out, err, code_ = "timeout", (exc.stdout or "") if isinstance(exc.stdout, str) else "", f"Tiempo máximo ({TIMEOUT_S} s) superado", None
    finally:
        shutil.rmtree(work, ignore_errors=True)
    err = (err or "").replace(path, "main.py")
    return {"status": status, "stdout": (out or "")[:MAX_OUT], "stderr": err[-MAX_OUT:], "exit_code": code_,
            "duration_ms": round((time.perf_counter() - t0) * 1000)}
