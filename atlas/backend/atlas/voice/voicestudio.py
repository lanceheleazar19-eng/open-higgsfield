"""Cliente de VoiceStudio (https://github.com/debpalash/VoiceStudio), la app de voz local.

VISTAN no instala ni ejecuta modelos de voz: habla con la API local de VoiceStudio
(por defecto http://127.0.0.1:3900, compatible con OpenAI). Sin VoiceStudio abierto,
todo responde «no disponible» y la interfaz sigue usando la voz del navegador.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

import httpx

from atlas.config import get_settings

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
MAX_TEXT = 4096
FORMATS = {"mp3": "audio/mpeg", "wav": "audio/wav", "opus": "audio/ogg", "aac": "audio/aac", "flac": "audio/flac"}


class VoiceStudioError(RuntimeError):
    pass


# Tiempos reales de síntesis (segundos por frase) medidos en esta sesión del núcleo
_timings: list[dict] = []


def _record(chars: int, ms: int, ok: bool) -> None:
    _timings.append({"chars": chars, "ms": ms, "ok": ok, "at": time.time()})
    del _timings[:-30]


def timings() -> dict:
    ok = [t["ms"] for t in _timings if t["ok"]]
    return {"count": len(_timings), "errors": sum(1 for t in _timings if not t["ok"]),
            "last_ms": ok[-1] if ok else None, "avg_ms": round(sum(ok) / len(ok)) if ok else None}


def _base() -> str:
    return get_settings().voicestudio_url.rstrip("/")


def is_local(url: str | None = None) -> bool:
    return (urlparse(url or _base()).hostname or "") in LOOPBACK


def _headers() -> dict[str, str]:
    key = get_settings().voicestudio_api_key
    # La clave solo viaja por HTTPS o al propio equipo (nunca en claro por la red)
    if key and (is_local() or _base().startswith("https://")):
        return {"Authorization": f"Bearer {key}"}
    return {}


def status(timeout: float = 1.5) -> dict:
    """Estado real: responde o no, latencia medida y voces que expone VoiceStudio."""
    url = _base()
    out: dict = {"url": url, "local": is_local(url), "reachable": False, "ping_ms": None,
                 "protocol": None, "voices": [], "error": None, "synthesis": timings()}
    t0 = time.perf_counter()
    try:
        r = httpx.get(f"{url}/.well-known/voicestudio-speech", headers=_headers(), timeout=timeout)
        out["ping_ms"] = round((time.perf_counter() - t0) * 1000)
        if r.status_code == 401:
            out["error"] = "VoiceStudio pide credenciales (ATLAS_VOICESTUDIO_API_KEY)"
            return out
        r.raise_for_status()
        doc = r.json() if "json" in r.headers.get("content-type", "") else {}
        out["reachable"] = True
        out["protocol"] = doc.get("protocol") or doc.get("version")
    except (httpx.HTTPError, ValueError):
        out["error"] = "VoiceStudio no está abierto o no responde"
        return out
    try:
        v = httpx.get(f"{url}/v1/audio/voices", headers=_headers(), timeout=timeout + 1.5)
        v.raise_for_status()
        data = v.json()
        items = data.get("voices", data) if isinstance(data, dict) else data
        out["voices"] = [{"id": str(x.get("voice_id") or x.get("id")), "name": str(x.get("name") or x.get("voice_id")),
                          "type": x.get("type"), "language": x.get("language")}
                         for x in items if isinstance(x, dict) and (x.get("voice_id") or x.get("id"))]
    except (httpx.HTTPError, ValueError, AttributeError):
        out["error"] = "VoiceStudio responde, pero no se pudo leer la lista de voces"
    return out


def speak(text: str, voice: str | None = None, speed: float = 1.0, fmt: str = "mp3",
          language: str | None = "es", timeout: float = 180.0) -> tuple[bytes, str]:
    """Sintetiza `text` con VoiceStudio. Devuelve (audio, content-type)."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Texto vacío")
    if len(text) > MAX_TEXT:
        raise ValueError(f"Máximo {MAX_TEXT} caracteres por petición")
    if fmt not in FORMATS:
        raise ValueError("Formato no soportado")
    body: dict = {"input": text, "voice": voice or "default", "response_format": fmt,
                  "speed": max(0.25, min(4.0, float(speed)))}
    if language:
        body["language"] = language
    t0 = time.perf_counter()
    try:
        r = httpx.post(f"{_base()}/v1/audio/speech", json=body, headers=_headers(), timeout=timeout)
    except httpx.HTTPError as exc:
        _record(len(text), round((time.perf_counter() - t0) * 1000), False)
        raise VoiceStudioError("VoiceStudio no está abierto o no responde") from exc
    _record(len(text), round((time.perf_counter() - t0) * 1000), r.status_code < 400)
    if r.status_code >= 400:
        detail = ""
        try:
            j = r.json()
            detail = (j.get("error") or {}).get("message") if isinstance(j.get("error"), dict) else j.get("detail") or ""
        except ValueError:
            pass
        raise VoiceStudioError(f"VoiceStudio respondió {r.status_code}" + (f": {str(detail)[:200]}" if detail else ""))
    return r.content, r.headers.get("content-type", FORMATS[fmt]).split(";")[0]
