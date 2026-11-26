"""Intelligent Model Router del META-BRAIN. Se apoya en el Model Router de VISTAN (atlas/brain/router.py: privacidad,
preferencias por tarea, claves en el Llavero, límite de gasto, registro de llamadas) y añade:
- inventario REAL de proveedores y modelos (Ollama instalado y sus capacidades; nube solo con clave y modelo configurado;
  proveedor compatible con la API de OpenAI —Groq, Mistral, OpenRouter, LM Studio…— si tú lo configuras),
- cadena de candidatos con fallback ante errores, restricción de privacidad por contenido personal,
- presupuesto por ejecución (llamadas, tiempo, coste) y medición de latencia, tokens y coste.
Nunca se inventa un proveedor ni un modelo: si no hay ninguno accesible, se dice."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from atlas.brain import router
from atlas.brain.base import ProviderError
from atlas.brain.providers import CLOUD, OpenAIProvider, _json_from_text
from atlas.config import get_settings
from atlas.integrations.secrets import get_secret

LABELS = {"ollama": "Ollama (local)", "openai": "OpenAI", "anthropic": "Anthropic", "gemini": "Google Gemini", "compat": "Compatible OpenAI"}


class BudgetExceeded(Exception):
    pass


@dataclass
class Budget:
    """Límites de una ejecución: se comprueban antes de cada llamada a un modelo."""
    max_calls: int = 12
    max_seconds: int = 600
    max_cost_usd: float | None = None
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    priced: bool = False
    started: float = field(default_factory=time.perf_counter)
    models: list = field(default_factory=list)

    def check(self) -> None:
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"Límite de llamadas a modelos alcanzado ({self.max_calls})")
        if time.perf_counter() - self.started > self.max_seconds:
            raise BudgetExceeded(f"Límite de tiempo alcanzado ({self.max_seconds} s)")
        if self.max_cost_usd is not None and self.cost >= self.max_cost_usd:
            raise BudgetExceeded(f"Límite de coste alcanzado ({self.max_cost_usd} $)")

    def add(self, model: str, usage: dict, cost: float | None) -> None:
        self.calls += 1
        self.tokens_in += usage.get("in") or 0
        self.tokens_out += usage.get("out") or 0
        if cost is not None:
            self.cost += cost
            self.priced = True
        if model not in self.models:
            self.models.append(model)


# ───────── proveedor compatible con OpenAI (opcional) ─────────
def compat_conf() -> dict | None:
    base = get_secret("compat_base_url")
    model = get_secret("compat_model")
    if not base or not model:
        return None
    return {"base_url": base, "model": model, "label": get_secret("compat_label") or urlparse(base).netloc, "has_key": bool(get_secret("compat_api_key"))}


def valid_base_url(url: str) -> bool:
    u = urlparse(url.strip())
    local = u.hostname in ("localhost", "127.0.0.1", "::1")
    return bool(u.hostname) and (u.scheme == "https" or (u.scheme == "http" and local))


class CompatProvider(OpenAIProvider):
    name, label = "compat", "Compatible OpenAI"

    def __init__(self, api_key: str, base_url: str):
        super().__init__(api_key)
        self.base_url = base_url.rstrip("/")


def make(provider: str):  # noqa: ANN201
    if provider == "compat":
        c = compat_conf()
        return CompatProvider(get_secret("compat_api_key") or "none", c["base_url"]) if c else None
    return router.make_cloud(provider)


def cloud_configured(prefs: dict) -> list[tuple[str, str]]:
    cfg = router.config(prefs)
    out = [(p, cfg["providers"][p]["model"]) for p in CLOUD if cfg["providers"][p]["model"] and router.has_key(p)]
    c = compat_conf()
    if c:
        out.append(("compat", c["model"]))
    return out


# ───────── Ollama ─────────
_caps_cache: dict[str, tuple[float, list[str]]] = {}


def ollama_models() -> tuple[bool, list[dict]]:
    base = get_settings().ollama_url
    try:
        r = httpx.get(f"{base}/api/tags", timeout=2.5)
        models = r.json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return False, []
    out = []
    for m in models:
        name = m.get("name", "")
        caps = _capabilities(base, name)
        out.append({"name": name, "size_gb": round((m.get("size") or 0) / 1e9, 1), "family": (m.get("details") or {}).get("family"),
                    "params": (m.get("details") or {}).get("parameter_size"), "capabilities": caps})
    return True, out


def _capabilities(base: str, name: str) -> list[str]:
    """Capacidades que declara Ollama (/api/show). Si su versión no las informa, se deduce solo lo evidente."""
    hit = _caps_cache.get(name)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    caps: list[str] = []
    try:
        r = httpx.post(f"{base}/api/show", json={"model": name}, timeout=3)
        caps = list(r.json().get("capabilities") or [])
    except (httpx.HTTPError, ValueError):
        pass
    if not caps:
        low = name.lower()
        caps = ["embedding"] if "embed" in low else ["completion"] + (["vision"] if re.search(r"vl|vision|llava|moondream", low) else [])
        caps.append("(deducido del nombre)")
    _caps_cache[name] = (time.time(), caps)
    return caps


def _ollama_chat(model: str, messages: list[dict], json_mode: bool) -> tuple[str, dict]:
    body = {"model": model, "messages": messages, "stream": False, "options": {"temperature": 0.2}}
    if json_mode:
        body["format"] = "json"
    r = httpx.post(f"{get_settings().ollama_url}/api/chat", json=body, timeout=httpx.Timeout(300, connect=3))
    if r.status_code != 200:
        raise ProviderError(f"Ollama devolvió {r.status_code}: {r.text[:200]}")
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    try:
        chunks = [json.loads(ln) for ln in lines] if len(lines) > 1 else [r.json()]
    except ValueError as exc:
        raise ProviderError("Respuesta de Ollama no válida") from exc
    text = "".join((c.get("message") or {}).get("content", "") for c in chunks)
    last = chunks[-1] if chunks else {}
    return text, {"in": last.get("prompt_eval_count"), "out": last.get("eval_count")}


# ───────── selección ─────────
def _perf(days: int = 30) -> dict[str, dict]:
    """Rendimiento medido por proveedor:modelo (últimos `days` días) a partir del registro de llamadas."""
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from atlas.db import session_scope
    from atlas.models import ModelCall
    since = datetime.utcnow() - timedelta(days=days)
    out: dict[str, dict] = {}
    with session_scope() as db:
        for c in db.scalars(select(ModelCall).where(ModelCall.created_at >= since).order_by(ModelCall.id.desc()).limit(5000)):
            k = f"{c.provider}:{c.model}"
            s = out.setdefault(k, {"calls": 0, "errors": 0, "lat": []})
            s["calls"] += 1
            s["errors"] += 0 if c.ok else 1
            if c.ok:
                s["lat"].append(c.latency_ms)
    return out


def candidates(task: str, prefs: dict, local_only: bool = False, prefer: str | None = None) -> list[dict]:
    """Cadena ordenada de modelos REALES a probar para `task`, con el motivo de cada uno."""
    from atlas.brain.orchestrator import brain_status
    cfg = router.config(prefs)
    out: list[dict] = []

    def add(prov: str, model: str, why: str) -> None:
        if model and not any(c["provider"] == prov and c["model"] == model for c in out):
            out.append({"provider": prov, "model": model, "id": f"{prov}:{model}", "why": why})

    cloud = [] if local_only or cfg["privacy"] == "local_only" else cloud_configured(prefs)
    over = cfg["monthly_limit_usd"] is not None and router.month_cost() >= float(cfg["monthly_limit_usd"])
    if over:
        cloud = []
    if prefer and ":" in prefer:
        p, m = prefer.split(":", 1)
        if p == "ollama" or (p, m) in cloud:
            add(p, m, "elegido para diversidad del consejo")
    t = cfg["tasks"].get(task) or {}
    prov = t.get("provider") or "auto"
    for p, m in cloud:
        if p == prov:
            add(p, t.get("model") or m, f"tu preferencia para la tarea «{task}»")
    if cfg["privacy"] == "best_quality" and cloud:
        perf = _perf()
        ranked = sorted(cloud, key=lambda pm: (perf.get(f"{pm[0]}:{pm[1]}", {}).get("errors", 0) / max(1, perf.get(f"{pm[0]}:{pm[1]}", {}).get("calls", 1))))
        for p, m in ranked:
            add(p, m, "política «mejor calidad»: nube ordenada por tasa de errores medida")
    st = brain_status(prefs)
    if st["model"]:
        add("ollama", st["model"], "modelo local principal" + (" (privacidad: solo local)" if local_only else ""))
        for m in st["models"]:
            if m["name"] != st["model"]:
                add("ollama", m["name"], "fallback local")
                break
    # «local primero»: la nube solo entra si la eliges para la tarea (arriba); nunca como relleno automático
    return out


def _cost(prefs: dict, provider: str, model: str, usage: dict) -> float | None:
    price = (router.config(prefs)["prices"] or {}).get(f"{provider}:{model}")
    if price and usage.get("in") is not None and usage.get("out") is not None:
        return round((usage["in"] * float(price.get("in", 0)) + usage["out"] * float(price.get("out", 0))) / 1e6, 6)
    return None


def raw_call(provider: str, model: str, messages: list[dict], json_mode: bool = False) -> tuple[str, dict]:
    if provider == "ollama":
        return _ollama_chat(model, messages, json_mode)
    p = make(provider)
    if not p:
        raise ProviderError(f"{LABELS.get(provider, provider)}: sin configurar")
    if json_mode:
        data = p.complete_json(model, messages)
        return json.dumps(data, ensure_ascii=False), dict(getattr(p, "last_usage", None) or {})
    text = "".join(p.chat_stream(model, messages))
    return text, dict(getattr(p, "last_usage", None) or {})


def call(task: str, prefs: dict, messages: list[dict], *, json_mode: bool = False, local_only: bool = False,
         prefer: str | None = None, budget: Budget | None = None, tag: str = "meta") -> dict:
    """Llama al mejor candidato y, si falla, al siguiente (fallback). Registra cada intento."""
    chain = candidates(task, prefs, local_only, prefer)
    if not chain:
        raise ProviderError("No hay ningún modelo accesible: abre Ollama o configura un proveedor en Modelos."
                            + (" (Privacidad: esta petición solo puede usar modelos locales.)" if local_only else ""))
    errors: list[str] = []
    for c in chain:
        if budget:
            budget.check()
        t0 = time.perf_counter()
        try:
            text, usage = raw_call(c["provider"], c["model"], messages, json_mode)
            data = _json_from_text(text) if json_mode else None
        except (ProviderError, httpx.HTTPError) as exc:
            router.record(c["provider"], c["model"], tag[:16], t0, False, str(exc), prefs=prefs)
            errors.append(f"{c['id']}: {exc}"[:240])
            if budget:
                budget.calls += 1
            continue
        router.record(c["provider"], c["model"], tag[:16], t0, True, usage=usage, prefs=prefs)
        cost = _cost(prefs, c["provider"], c["model"], usage)
        if budget:
            budget.add(c["id"], usage, cost)
        return {"text": text, "data": data, "model": c["id"], "why": c["why"], "ms": int((time.perf_counter() - t0) * 1000),
                "usage": usage, "cost": cost, "fallback_errors": errors}
    raise ProviderError("Todos los modelos fallaron: " + " | ".join(errors))


# ───────── inventario y rendimiento ─────────
def inventory(prefs: dict) -> dict:
    cfg = router.config(prefs)
    reachable, models = ollama_models()
    providers = [{"id": "ollama", "label": LABELS["ollama"], "kind": "local", "configured": reachable and bool(models),
                  "reachable": reachable, "models": models, "note": None if reachable else "Ollama no responde en " + get_settings().ollama_url}]
    for p in CLOUD:
        model = cfg["providers"][p]["model"]
        key = router.has_key(p)
        providers.append({"id": p, "label": LABELS[p], "kind": "cloud", "configured": bool(key and model), "has_key": key, "model": model or None,
                          "note": None if key and model else ("Falta la API key" if not key else "Falta elegir el modelo en Modelos")})
    c = compat_conf()
    providers.append({"id": "compat", "label": c["label"] if c else LABELS["compat"], "kind": "cloud", "configured": bool(c),
                      "has_key": bool(c and c["has_key"]), "model": c["model"] if c else None, "base_url": c["base_url"] if c else None,
                      "note": None if c else "Opcional: Groq, Mistral, OpenRouter, LM Studio… (cualquier API compatible con OpenAI)"})
    return {"privacy": cfg["privacy"], "monthly_limit_usd": cfg["monthly_limit_usd"], "month_cost_usd": round(router.month_cost(), 4),
            "tasks": cfg["tasks"], "providers": providers}


def stats(days: int = 30) -> list[dict]:
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from atlas.db import session_scope
    from atlas.models import ModelCall
    since = datetime.utcnow() - timedelta(days=days)
    agg: dict[str, dict] = {}
    with session_scope() as db:
        for c in db.scalars(select(ModelCall).where(ModelCall.created_at >= since)):
            k = f"{c.provider}:{c.model}"
            a = agg.setdefault(k, {"id": k, "provider": c.provider, "model": c.model, "calls": 0, "errors": 0, "lat": [],
                                   "tokens_in": 0, "tokens_out": 0, "has_tokens": False, "cost": 0.0, "has_cost": False, "tasks": {}, "last_error": None})
            a["calls"] += 1
            a["tasks"][c.task] = a["tasks"].get(c.task, 0) + 1
            if not c.ok:
                a["errors"] += 1
                a["last_error"] = (c.error or "")[:160]
            else:
                a["lat"].append(c.latency_ms)
            if c.tokens_out is not None:
                a["has_tokens"] = True
                a["tokens_in"] += c.tokens_in or 0
                a["tokens_out"] += c.tokens_out or 0
            if c.cost_usd is not None:
                a["has_cost"] = True
                a["cost"] += c.cost_usd
    out = []
    for a in agg.values():
        lat = sorted(a.pop("lat"))
        out.append({**a, "error_rate": round(a["errors"] / a["calls"] * 100, 1),
                    "p50_ms": lat[len(lat) // 2] if lat else None, "p95_ms": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None,
                    "tokens_in": a["tokens_in"] if a["has_tokens"] else None, "tokens_out": a["tokens_out"] if a["has_tokens"] else None,
                    "cost_usd": round(a["cost"], 6) if a["has_cost"] else None})
    return sorted(out, key=lambda x: -x["calls"])
