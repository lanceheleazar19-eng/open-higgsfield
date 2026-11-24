"""Model Router: elige proveedor y modelo según la tarea, la privacidad, la disponibilidad y el coste.
Registra cada llamada (modelo, tiempo, errores, tokens y coste si conoces el precio)."""

import time
from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import func, select

from atlas.brain.base import LLMProvider, ProviderError
from atlas.brain.providers import CLOUD
from atlas.integrations.secrets import get_secret

TASKS = {"chat": "Conversación", "agents": "Agentes", "research": "Investigación", "json": "Tareas internas (JSON)",
         "vision": "Imágenes (físico y comidas)"}
PRIVACY = {
    "local_only": "Solo local (Ollama): nada sale de tu ordenador",
    "local_first": "Local primero; la nube solo si la eliges para una tarea",
    "best_quality": "Mejor calidad: usa la nube configurada y Ollama como respaldo",
}
DEFAULT = {"privacy": "local_first", "tasks": {t: {"provider": "auto", "model": ""} for t in TASKS},
           "providers": {p: {"model": ""} for p in CLOUD}, "prices": {}, "monthly_limit_usd": None}


def config(prefs: dict) -> dict:
    c = prefs.get("model_router") or {}
    out = {**DEFAULT, **{k: v for k, v in c.items() if k in DEFAULT}}
    out["tasks"] = {t: {**DEFAULT["tasks"][t], **(c.get("tasks", {}).get(t) or {})} for t in TASKS}
    out["providers"] = {p: {**DEFAULT["providers"][p], **(c.get("providers", {}).get(p) or {})} for p in CLOUD}
    return out


def has_key(provider: str) -> bool:
    return bool(get_secret(f"{provider}_api_key"))


def make_cloud(provider: str) -> LLMProvider | None:
    key = get_secret(f"{provider}_api_key")
    return CLOUD[provider](key) if key and provider in CLOUD else None


def month_cost() -> float:
    from atlas.db import session_scope
    from atlas.models import ModelCall
    start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with session_scope() as db:
        return float(db.scalar(select(func.coalesce(func.sum(ModelCall.cost_usd), 0.0)).where(ModelCall.created_at >= start)) or 0)


def cloud_choice(task: str, prefs: dict) -> tuple[str, str] | None:
    """(proveedor, modelo) en la nube que toca usar para `task`, o None → Ollama/local."""
    c = config(prefs)
    if c["privacy"] == "local_only":
        return None
    if c["monthly_limit_usd"] is not None and month_cost() >= float(c["monthly_limit_usd"]):
        return None  # límite de gasto alcanzado: solo local
    t = c["tasks"].get(task) or {}
    prov = t.get("provider") or "auto"
    if prov in CLOUD:
        model = t.get("model") or c["providers"][prov]["model"]
        return (prov, model) if model and has_key(prov) else None
    if prov == "ollama":
        return None
    if c["privacy"] == "best_quality" and task != "vision":  # las fotos solo salen si eliges proveedor expresamente
        for p in CLOUD:
            if c["providers"][p]["model"] and has_key(p):
                return p, c["providers"][p]["model"]
    return None


def record(provider: str, model: str, task: str, started: float, ok: bool, error: str | None = None,
           usage: dict | None = None, prefs: dict | None = None) -> None:
    from atlas.db import session_scope
    from atlas.models import ModelCall
    usage = usage or {}
    cost = None
    price = (config(prefs or {})["prices"] or {}).get(f"{provider}:{model}")
    if price and usage.get("in") is not None and usage.get("out") is not None:
        cost = round((usage["in"] * float(price.get("in", 0)) + usage["out"] * float(price.get("out", 0))) / 1e6, 6)
    try:
        with session_scope() as db:
            db.add(ModelCall(provider=provider, model=model or "?", task=task, ok=ok, error=(error or None) and error[:500],
                             latency_ms=int((time.perf_counter() - started) * 1000), tokens_in=usage.get("in"),
                             tokens_out=usage.get("out"), cost_usd=cost))
            db.commit()
    except Exception:  # noqa: BLE001 - registrar nunca debe romper una respuesta
        pass


def stream_cloud(provider: str, model: str, messages: list[dict], task: str, prefs: dict) -> Iterator[str]:
    p = make_cloud(provider)
    if not p:
        raise ProviderError(f"Falta la API key de {provider}")
    t0 = time.perf_counter()
    try:
        yield from p.chat_stream(model, messages)
    except ProviderError as exc:
        record(provider, model, task, t0, False, str(exc), prefs=prefs)
        raise
    record(provider, model, task, t0, True, usage=getattr(p, "last_usage", {}), prefs=prefs)


def complete_json(task: str, prefs: dict, messages: list[dict]) -> tuple[dict, str]:
    """JSON del mejor modelo disponible (nube si toca, si no Ollama). Devuelve (datos, 'proveedor:modelo')."""
    from atlas.brain.orchestrator import brain_status, get_provider
    choice = cloud_choice(task, prefs)
    if choice:
        p = make_cloud(choice[0])
        t0 = time.perf_counter()
        try:
            data = p.complete_json(choice[1], messages)  # type: ignore[union-attr]
            record(choice[0], choice[1], task, t0, True, usage=getattr(p, "last_usage", {}), prefs=prefs)
            return data, f"{choice[0]}:{choice[1]}"
        except ProviderError as exc:
            record(choice[0], choice[1], task, t0, False, str(exc), prefs=prefs)
    prov = get_provider()
    st = brain_status(prefs, prov)
    if not st["configured"]:
        raise ProviderError(st["note"] or "Sin modelo disponible")
    t0 = time.perf_counter()
    try:
        data = prov.complete_json(st["model"], messages)
    except ProviderError as exc:
        record("ollama", st["model"], task, t0, False, str(exc), prefs=prefs)
        raise
    record("ollama", st["model"], task, t0, True, prefs=prefs)
    return data, f"ollama:{st['model']}"


def complete_text(task: str, prefs: dict, messages: list[dict]) -> tuple[str, str]:
    from atlas.brain.orchestrator import brain_status, get_provider
    choice = cloud_choice(task, prefs)
    if choice:
        try:
            return "".join(stream_cloud(choice[0], choice[1], messages, task, prefs)), f"{choice[0]}:{choice[1]}"
        except ProviderError:
            pass
    prov = get_provider()
    st = brain_status(prefs, prov)
    if not st["configured"]:
        raise ProviderError(st["note"] or "Sin modelo disponible")
    t0 = time.perf_counter()
    try:
        out = "".join(prov.chat_stream(st["model"], messages))
    except ProviderError as exc:
        record("ollama", st["model"], task, t0, False, str(exc), prefs=prefs)
        raise
    record("ollama", st["model"], task, t0, True, prefs=prefs)
    return out, f"ollama:{st['model']}"


def any_model(prefs: dict) -> bool:
    from atlas.brain.orchestrator import brain_status
    return bool(brain_status(prefs)["configured"] or cloud_choice("json", prefs) or cloud_choice("chat", prefs))
