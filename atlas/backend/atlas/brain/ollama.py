"""Proveedor Ollama (modelos locales). API: https://github.com/ollama/ollama/blob/main/docs/api.md"""

import json
from collections.abc import Iterator

import httpx

from atlas.brain.base import LLMProvider, ModelInfo, ProviderError, ProviderStatus

CHAT_OPTIONS = {"temperature": 0.4, "num_ctx": 6144}


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def status(self) -> ProviderStatus:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            r.raise_for_status()
            models = [
                ModelInfo(
                    name=m["name"],
                    size_bytes=int(m.get("size") or 0),
                    parameter_size=(m.get("details") or {}).get("parameter_size"),
                    family=(m.get("details") or {}).get("family"),
                )
                for m in r.json().get("models", [])
            ]
            return ProviderStatus(self.name, True, models)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            return ProviderStatus(self.name, False, error=f"Ollama no responde en {self.base_url} ({type(exc).__name__})")

    def chat_stream(self, model: str, messages: list[dict]) -> Iterator[str]:
        payload = {"model": model, "messages": messages, "stream": True, "options": CHAT_OPTIONS, "keep_alive": "15m"}
        timeout = httpx.Timeout(self.timeout, connect=3.0)
        try:
            with httpx.stream("POST", f"{self.base_url}/api/chat", json=payload, timeout=timeout) as r:
                if r.status_code != 200:
                    body = r.read().decode(errors="replace")
                    try:
                        body = json.loads(body).get("error", body)
                    except ValueError:
                        pass
                    raise ProviderError(f"Ollama devolvió {r.status_code}: {body}")
                for line in r.iter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise ProviderError(f"Ollama: {chunk['error']}")
                    text = (chunk.get("message") or {}).get("content") or ""
                    if text:
                        yield text
                    if chunk.get("done"):
                        return
        except httpx.HTTPError as exc:
            raise ProviderError(f"No se pudo conectar con Ollama en {self.base_url}: {type(exc).__name__}") from exc

    def complete_json(self, model: str, messages: list[dict]) -> dict:
        """`messages` puede incluir "images": [base64] (modelos de visión)."""
        payload = {"model": model, "messages": messages, "stream": False, "format": "json",
                   "options": {"temperature": 0.1, "num_ctx": 4096},
                   # Los modelos de visión pesan mucho: se liberan enseguida para no frenar el chat ni la voz
                   "keep_alive": "1m" if any(m.get("images") for m in messages) else "15m"}
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=httpx.Timeout(self.timeout, connect=3.0))
        except httpx.HTTPError as exc:
            raise ProviderError(f"No se pudo conectar con Ollama: {type(exc).__name__}") from exc
        if r.status_code != 200:
            raise ProviderError(f"Ollama devolvió {r.status_code}")
        try:
            return json.loads(r.json()["message"]["content"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Respuesta JSON inválida del modelo") from exc
