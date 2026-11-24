"""Orquestador del cerebro: elige proveedor y modelo, construye el contexto y
transmite la respuesta. Si no hay IA disponible, responde el intérprete local."""

import json
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
                provider: LLMProvider | None = None, memory: dict | None = None, task: str = "chat") -> Iterator[dict]:
    """Eventos: status → delta* → done (o error). `d` = datos del dashboard con alertas.
    El Model Router decide si esta tarea va a un proveedor en la nube (solo con tu API key y política)."""
    import time

    from atlas.brain import router
    clean = [{"role": m["role"], "content": str(m["content"])[:4000]} for m in history[-MAX_HISTORY:]
             if m.get("role") in ("user", "assistant") and m.get("content")]
    choice = router.cloud_choice(task, prefs) if provider is None else None
    if choice:
        prov_name, model = choice
        yield {"type": "status", "state": "thinking", "model": f"{prov_name}:{model}"}
        messages = [{"role": "system", "content": system_prompt(d, memory)}, *clean, {"role": "user", "content": text}]
        produced = False
        try:
            for chunk in router.stream_cloud(prov_name, model, messages, task, prefs):
                produced = True
                yield {"type": "delta", "text": chunk}
            yield {"type": "done", "mode": "ai", "model": f"{model}", "provider": prov_name}
            return
        except ProviderError as exc:
            if produced:
                yield {"type": "error", "message": str(exc)}
                return
            # la nube falló sin responder: seguimos con Ollama/local
    provider = provider or get_provider()
    status = brain_status(prefs, provider)
    if not status["configured"]:
        r = local_answer(text, d, memory)
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
    messages = [{"role": "system", "content": system_prompt(d, memory)}, *clean_history, {"role": "user", "content": text}]
    produced = False
    t0 = time.perf_counter()
    try:
        for chunk in provider.chat_stream(model, messages):
            produced = True
            yield {"type": "delta", "text": chunk}
    except ProviderError as exc:
        router.record(provider.name, model, task, t0, False, str(exc), prefs=prefs)
        if produced:
            yield {"type": "error", "message": str(exc)}
            return
        # Sin respuesta del modelo: respondemos en modo local para no dejar al usuario sin nada
        r = local_answer(text, d, memory)
        yield {"type": "delta", "text": r["reply"]}
        yield {"type": "done", "mode": "local", "model": None, "reason": str(exc)}
        return
    router.record(provider.name, model, task, t0, True, prefs=prefs)
    yield {"type": "done", "mode": "ai", "model": model, "provider": provider.name}


SUGGEST_PROMPT = """Analiza el último mensaje del USUARIO y extrae solo información personal duradera y útil
que un asistente personal debería recordar: preferencias, objetivos, decisiones tomadas o datos estables
sobre su vida, trabajo, salud, proyectos o finanzas. NO extraigas preguntas, saludos, peticiones puntuales,
opiniones de VISTAN ni datos que ya estén en la lista de recuerdos existentes.
Responde SOLO con JSON: {"recuerdos": [{"contenido": "frase breve en tercera persona o neutra",
"tipo": "preferencia|objetivo|decision|dato", "temporal": true|false}]}. Máximo 3. Si no hay nada, {"recuerdos": []}."""

KIND_FROM_ES = {"preferencia": "preference", "objetivo": "goal", "decision": "decision", "decisión": "decision",
                "dato": "fact", "nota": "note"}


def suggest_memories(prefs: dict, user_text: str, assistant_text: str, existing: list[str],
                     provider: LLMProvider | None = None) -> list[dict]:
    """Pide al modelo candidatos a recordar. Nunca guarda: solo propone (el usuario decide)."""
    provider = provider or get_provider()
    status = brain_status(prefs, provider)
    if not status["configured"]:
        return []
    messages = [
        {"role": "system", "content": SUGGEST_PROMPT},
        {"role": "user", "content": json.dumps({"mensaje_usuario": user_text, "respuesta_atlas": assistant_text[:1500],
                                                "recuerdos_existentes": existing[:30]}, ensure_ascii=False)},
    ]
    try:
        data = provider.complete_json(status["model"], messages)
    except ProviderError:
        return []
    out = []
    for item in (data.get("recuerdos") or [])[:3] if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("contenido") or "").strip()
        if len(content) < 8 or len(content) > 300:
            continue
        out.append({"content": content, "kind": KIND_FROM_ES.get(str(item.get("tipo", "")).lower(), "fact"),
                    "temporary": bool(item.get("temporal"))})
    return out
