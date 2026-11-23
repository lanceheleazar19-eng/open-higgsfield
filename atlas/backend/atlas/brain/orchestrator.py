"""Orquestador del cerebro: elige proveedor y modelo, construye el contexto y
transmite la respuesta. Si no hay IA disponible, responde el intérprete local."""

from collections.abc import Iterator

from atlas.brain.base import LLMProvider, ModelInfo, ProviderError, ProviderStatus
from atlas.brain.context import system_prompt
from atlas.brain.ollama import OllamaProvider
from atlas.config import get_settings
from atlas.services.assistant import answer as local_answer

# Preferencia para la elección automática (buen español y tamaño razonable primero)
PREFERRED = ("qwen2.5", "qwen3", "llama3.1", "llama3.2", "gemma3", "gemma2", "mistral", "phi4", "llama3")
MAX_HISTORY = 12  # mensajes previos que se envían como contexto


def get_provider() -> LLMProvider:
    return OllamaProvider(get_settings().ollama_url)


def _usable(models: list[ModelInfo]) -> list[ModelInfo]:
    return [m for m in models if "embed" not in m.name.lower()]


def pick_model(models: list[ModelInfo], preferred: str | None) -> str | None:
    usable = _usable(models)
    names = [m.name for m in usable]
    if preferred and preferred in names:
        return preferred
    for family in PREFERRED:
        for n in names:
            if n.lower().startswith(family):
                return n
    return names[0] if names else None


def brain_status(prefs: dict, provider: LLMProvider | None = None) -> dict:
    provider = provider or get_provider()
    st: ProviderStatus = provider.status()
    chosen = pick_model(st.models, prefs.get("ai_model") or None) if st.reachable else None
    wanted = prefs.get("ai_model") or None
    note = None
    if not st.reachable:
        note = "Ollama no detectado. Ábrelo en tu ordenador (debe escuchar en " + getattr(provider, "base_url", "?") + ")."
    elif not chosen:
        note = "Ollama no tiene modelos. Ejecuta: ollama pull qwen2.5:7b"
    elif wanted and wanted != chosen:
        note = f"El modelo elegido ({wanted}) no está instalado; uso {chosen}."
    return {
        "provider": provider.name,
        "url": getattr(provider, "base_url", None),
        "reachable": st.reachable,
        "models": [m.__dict__ for m in _usable(st.models)],
        "model": chosen,
        "preferred": wanted,
        "configured": bool(chosen),
        "error": st.error,
        "note": note,
    }


def chat_events(d: dict, prefs: dict, text: str, history: list[dict],
                provider: LLMProvider | None = None) -> Iterator[dict]:
    """Eventos: status → delta* → done (o error). `d` = datos del dashboard con alertas."""
    provider = provider or get_provider()
    status = brain_status(prefs, provider)
    if not status["configured"]:
        r = local_answer(text, d)
        yield {"type": "delta", "text": r["reply"]}
        yield {"type": "done", "mode": "local", "model": None, "reason": status["note"]}
        return

    model = status["model"]
    yield {"type": "status", "state": "thinking", "model": model}
    clean_history = [
        {"role": m["role"], "content": str(m["content"])[:4000]}
        for m in history[-MAX_HISTORY:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    messages = [{"role": "system", "content": system_prompt(d)}, *clean_history, {"role": "user", "content": text}]
    produced = False
    try:
        for chunk in provider.chat_stream(model, messages):
            produced = True
            yield {"type": "delta", "text": chunk}
    except ProviderError as exc:
        if produced:
            yield {"type": "error", "message": str(exc)}
            return
        # Sin respuesta del modelo: respondemos en modo local para no dejar al usuario sin nada
        r = local_answer(text, d)
        yield {"type": "delta", "text": r["reply"]}
        yield {"type": "done", "mode": "local", "model": None, "reason": str(exc)}
        return
    yield {"type": "done", "mode": "ai", "model": model, "provider": provider.name}
