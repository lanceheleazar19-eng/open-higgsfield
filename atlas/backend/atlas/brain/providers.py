"""Proveedores en la nube (OpenAI, Anthropic, Google Gemini). Solo se usan si TÚ pones su API key
(guardada en el Llavero) y la política de privacidad lo permite. Sin key: no se simula nada."""

import json
import re
from collections.abc import Iterator

import httpx

from atlas.brain.base import LLMProvider, ModelInfo, ProviderError, ProviderStatus

TIMEOUT = httpx.Timeout(120.0, connect=8.0)


def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ("user", "assistant")]
    return system, rest


def _json_from_text(t: str) -> dict:
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        raise ProviderError("El modelo no devolvió JSON")
    try:
        return json.loads(m.group(0))
    except ValueError as exc:
        raise ProviderError("JSON inválido del modelo") from exc


def _sse(r: httpx.Response) -> Iterator[dict]:
    for line in r.iter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            yield json.loads(data)
        except ValueError:
            continue


def _err(r: httpx.Response, who: str) -> ProviderError:
    body = r.read().decode(errors="replace")[:300]
    if r.status_code in (401, 403):
        return ProviderError(f"{who}: API key no válida o sin permiso ({r.status_code})")
    if r.status_code == 429:
        return ProviderError(f"{who}: límite de uso o saldo agotado (429)")
    return ProviderError(f"{who} devolvió {r.status_code}: {body}")


class CloudProvider(LLMProvider):
    label = "cloud"

    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=TIMEOUT)
        self.last_usage: dict = {}


class OpenAIProvider(CloudProvider):
    name, label = "openai", "OpenAI"
    base_url = "https://api.openai.com/v1"

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def status(self) -> ProviderStatus:
        try:
            r = self.client.get(f"{self.base_url}/models", headers=self._h(), timeout=8.0)
        except httpx.HTTPError as exc:
            return ProviderStatus(self.name, False, error=f"Sin conexión con OpenAI ({type(exc).__name__})")
        if r.status_code != 200:
            return ProviderStatus(self.name, False, error=str(_err(r, "OpenAI")))
        ids = sorted(m["id"] for m in r.json().get("data", []) if re.match(r"(gpt|o\d|chatgpt)", m["id"]))
        return ProviderStatus(self.name, True, [ModelInfo(i) for i in ids])

    def chat_stream(self, model: str, messages: list[dict]) -> Iterator[str]:
        self.last_usage = {}
        body = {"model": model, "messages": messages, "stream": True, "stream_options": {"include_usage": True}}
        try:
            with self.client.stream("POST", f"{self.base_url}/chat/completions", headers=self._h(), json=body) as r:
                if r.status_code != 200:
                    raise _err(r, "OpenAI")
                for ev in _sse(r):
                    if ev.get("usage"):
                        self.last_usage = {"in": ev["usage"].get("prompt_tokens"), "out": ev["usage"].get("completion_tokens")}
                    for ch in ev.get("choices") or []:
                        t = (ch.get("delta") or {}).get("content")
                        if t:
                            yield t
        except httpx.HTTPError as exc:
            raise ProviderError(f"Sin conexión con OpenAI: {type(exc).__name__}") from exc

    def complete_json(self, model: str, messages: list[dict]) -> dict:
        body = {"model": model, "messages": messages, "response_format": {"type": "json_object"}}
        try:
            r = self.client.post(f"{self.base_url}/chat/completions", headers=self._h(), json=body)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Sin conexión con OpenAI: {type(exc).__name__}") from exc
        if r.status_code != 200:
            raise _err(r, "OpenAI")
        j = r.json()
        u = j.get("usage") or {}
        self.last_usage = {"in": u.get("prompt_tokens"), "out": u.get("completion_tokens")}
        return _json_from_text(j["choices"][0]["message"]["content"] or "")


class AnthropicProvider(CloudProvider):
    name, label = "anthropic", "Anthropic"
    base_url = "https://api.anthropic.com/v1"

    def _h(self) -> dict:
        return {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

    def status(self) -> ProviderStatus:
        try:
            r = self.client.get(f"{self.base_url}/models", headers=self._h(), timeout=8.0)
        except httpx.HTTPError as exc:
            return ProviderStatus(self.name, False, error=f"Sin conexión con Anthropic ({type(exc).__name__})")
        if r.status_code != 200:
            return ProviderStatus(self.name, False, error=str(_err(r, "Anthropic")))
        return ProviderStatus(self.name, True, [ModelInfo(m["id"]) for m in r.json().get("data", [])])

    def _body(self, model: str, messages: list[dict], stream: bool) -> dict:
        system, rest = _split_system(messages)
        b = {"model": model, "max_tokens": 4096, "messages": rest, "stream": stream}
        if system:
            b["system"] = system
        return b

    def chat_stream(self, model: str, messages: list[dict]) -> Iterator[str]:
        self.last_usage = {}
        try:
            with self.client.stream("POST", f"{self.base_url}/messages", headers=self._h(),
                                    json=self._body(model, messages, True)) as r:
                if r.status_code != 200:
                    raise _err(r, "Anthropic")
                for ev in _sse(r):
                    t = ev.get("type")
                    if t == "message_start":
                        self.last_usage["in"] = ((ev.get("message") or {}).get("usage") or {}).get("input_tokens")
                    elif t == "message_delta":
                        self.last_usage["out"] = (ev.get("usage") or {}).get("output_tokens")
                    elif t == "content_block_delta":
                        txt = (ev.get("delta") or {}).get("text")
                        if txt:
                            yield txt
                    elif t == "error":
                        raise ProviderError(f"Anthropic: {(ev.get('error') or {}).get('message', 'error')}")
        except httpx.HTTPError as exc:
            raise ProviderError(f"Sin conexión con Anthropic: {type(exc).__name__}") from exc

    def complete_json(self, model: str, messages: list[dict]) -> dict:
        msgs = [*messages[:-1], {"role": messages[-1]["role"],
                                 "content": messages[-1]["content"] + "\n\nResponde únicamente con un objeto JSON válido."}]
        try:
            r = self.client.post(f"{self.base_url}/messages", headers=self._h(), json=self._body(model, msgs, False))
        except httpx.HTTPError as exc:
            raise ProviderError(f"Sin conexión con Anthropic: {type(exc).__name__}") from exc
        if r.status_code != 200:
            raise _err(r, "Anthropic")
        j = r.json()
        u = j.get("usage") or {}
        self.last_usage = {"in": u.get("input_tokens"), "out": u.get("output_tokens")}
        return _json_from_text("".join(b.get("text", "") for b in j.get("content", [])))


class GeminiProvider(CloudProvider):
    name, label = "gemini", "Google Gemini"
    base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _h(self) -> dict:
        return {"x-goog-api-key": self.api_key}

    def status(self) -> ProviderStatus:
        try:
            r = self.client.get(f"{self.base_url}/models", headers=self._h(), timeout=8.0)
        except httpx.HTTPError as exc:
            return ProviderStatus(self.name, False, error=f"Sin conexión con Gemini ({type(exc).__name__})")
        if r.status_code != 200:
            return ProviderStatus(self.name, False, error=str(_err(r, "Gemini")))
        ms = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
              if "generateContent" in (m.get("supportedGenerationMethods") or [])]
        return ProviderStatus(self.name, True, [ModelInfo(m) for m in ms])

    def _body(self, messages: list[dict], json_mode: bool = False) -> dict:
        system, rest = _split_system(messages)
        b: dict = {"contents": [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                                for m in rest]}
        if system:
            b["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            b["generationConfig"] = {"responseMimeType": "application/json"}
        return b

    def _usage(self, ev: dict) -> None:
        u = ev.get("usageMetadata")
        if u:
            self.last_usage = {"in": u.get("promptTokenCount"), "out": u.get("candidatesTokenCount")}

    def chat_stream(self, model: str, messages: list[dict]) -> Iterator[str]:
        self.last_usage = {}
        try:
            with self.client.stream("POST", f"{self.base_url}/models/{model}:streamGenerateContent?alt=sse",
                                    headers=self._h(), json=self._body(messages)) as r:
                if r.status_code != 200:
                    raise _err(r, "Gemini")
                for ev in _sse(r):
                    self._usage(ev)
                    for c in ev.get("candidates") or []:
                        for p in (c.get("content") or {}).get("parts") or []:
                            if p.get("text"):
                                yield p["text"]
        except httpx.HTTPError as exc:
            raise ProviderError(f"Sin conexión con Gemini: {type(exc).__name__}") from exc

    def complete_json(self, model: str, messages: list[dict]) -> dict:
        try:
            r = self.client.post(f"{self.base_url}/models/{model}:generateContent", headers=self._h(),
                                 json=self._body(messages, json_mode=True))
        except httpx.HTTPError as exc:
            raise ProviderError(f"Sin conexión con Gemini: {type(exc).__name__}") from exc
        if r.status_code != 200:
            raise _err(r, "Gemini")
        j = r.json()
        self._usage(j)
        parts = ((j.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        return _json_from_text("".join(p.get("text", "") for p in parts))


CLOUD = {"openai": OpenAIProvider, "anthropic": AnthropicProvider, "gemini": GeminiProvider}
