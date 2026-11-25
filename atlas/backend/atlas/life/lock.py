"""Bloqueo con PIN de LIFE OS (contactos, decisiones, errores, patrimonio, visión…). Opcional: si no hay PIN, VISTAN
sigue protegido por ser local/Tailscale. Con PIN, cada navegador debe desbloquear y recibe una cookie de sesión
HttpOnly que caduca. El PIN solo se guarda como hash PBKDF2 en el llavero del sistema."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Request

from atlas.integrations.secrets import delete_secret, get_secret, set_secret

KEY = "life_pin_hash"
COOKIE = "vistan_life"
TTL = 12 * 3600
_sessions: dict[str, float] = {}
_fails: list[float] = []


def _hash(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000).hex()


def enabled() -> bool:
    return bool(get_secret(KEY))


def verify(pin: str) -> bool:
    stored = get_secret(KEY)
    if not stored:
        return True
    now = time.time()
    _fails[:] = [t for t in _fails if now - t < 300]
    if len(_fails) >= 5:
        raise HTTPException(429, "Demasiados intentos: espera 5 minutos")
    salt, h = stored.split("$", 1)
    ok = hmac.compare_digest(_hash(pin, bytes.fromhex(salt)), h)
    if not ok:
        _fails.append(now)
    return ok


def set_pin(pin: str) -> None:
    if not (4 <= len(pin) <= 12 and pin.isdigit()):
        raise HTTPException(422, "El PIN debe tener entre 4 y 12 cifras")
    salt = secrets.token_bytes(16)
    set_secret(KEY, f"{salt.hex()}${_hash(pin, salt)}")
    _sessions.clear()


def remove_pin() -> None:
    delete_secret(KEY)
    _sessions.clear()


def new_session() -> str:
    tok = secrets.token_urlsafe(32)
    _sessions[tok] = time.time() + TTL
    return tok


def end_session(tok: str | None) -> None:
    if tok:
        _sessions.pop(tok, None)


def unlocked(request: Request) -> bool:
    if not enabled():
        return True
    tok = request.cookies.get(COOKIE)
    exp = _sessions.get(tok or "")
    return bool(exp and exp > time.time())


def require(request: Request) -> None:
    """Dependencia FastAPI para las rutas privadas de LIFE OS."""
    if not unlocked(request):
        raise HTTPException(423, {"locked": True, "message": "LIFE OS está bloqueado: introduce tu PIN"})
