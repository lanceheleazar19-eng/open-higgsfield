"""Model Testing Arena: mismo conjunto de pruebas en varios modelos REALMENTE configurados (Ollama instalado o nube con
clave). Mide latencia real, tokens que informa el proveedor (si no, N/D), coste según tus precios configurados y
puntúa con comprobaciones deterministas (exacta, contiene, regex) o con un modelo juez (marcado como tal)."""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime

import httpx

from atlas.brain import router
from atlas.brain.base import ProviderError
from atlas.config import get_settings


def available_models(prefs: dict) -> list[dict]:
    out = []
    try:
        r = httpx.get(f"{get_settings().ollama_url}/api/tags", timeout=2.5)
        for m in r.json().get("models", []):
            if "embed" not in m["name"].lower():
                out.append({"id": f"ollama:{m['name']}", "provider": "ollama", "model": m["name"], "local": True})
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    cfg = router.config(prefs)
    for p in router.CLOUD:
        model = cfg["providers"][p]["model"]
        if model and router.has_key(p):
            out.append({"id": f"{p}:{model}", "provider": p, "model": model, "local": False})
    return out


def _call(provider: str, model: str, messages: list[dict], prefs: dict) -> tuple[str, dict]:
    """Devuelve (texto, uso). Usa la API del proveedor directamente para obtener tokens reales."""
    if provider == "ollama":
        r = httpx.post(f"{get_settings().ollama_url}/api/chat", json={"model": model, "messages": messages, "stream": False,
                                                                     "options": {"temperature": 0}}, timeout=httpx.Timeout(240, connect=3))
        if r.status_code != 200:
            raise ProviderError(f"Ollama devolvió {r.status_code}")
        import json as _json
        lines = [ln for ln in r.text.splitlines() if ln.strip()]
        try:
            chunks = [_json.loads(ln) for ln in lines] if len(lines) > 1 else [r.json()]
        except ValueError as exc:
            raise ProviderError("Respuesta de Ollama no válida") from exc
        text = "".join((c.get("message") or {}).get("content", "") for c in chunks)
        last = chunks[-1] if chunks else {}
        return text, {"in": last.get("prompt_eval_count"), "out": last.get("eval_count")}
    prov = router.make_cloud(provider)
    if not prov:
        raise ProviderError(f"{provider}: sin clave")
    text = "".join(prov.chat_stream(model, messages))
    return text, dict(getattr(prov, "last_usage", None) or {})


def _score(test: dict, output: str, judge: tuple[str, str] | None, prefs: dict) -> tuple[float | None, str]:
    chk, exp = test.get("check", "none"), str(test.get("expected") or "")
    if chk == "exact":
        return (100.0 if output.strip().lower() == exp.strip().lower() else 0.0), "exacta"
    if chk == "contains":
        return (100.0 if exp.lower() in output.lower() else 0.0), "contiene"
    if chk == "regex":
        try:
            return (100.0 if re.search(exp, output, re.I | re.S) else 0.0), "regex"
        except re.error:
            return None, "regex no válida"
    if chk == "judge" and judge:
        msgs = [{"role": "system", "content": 'Eres un evaluador estricto. Puntúa de 0 a 100 si la RESPUESTA cumple el CRITERIO. Responde SOLO con un número.'},
                {"role": "user", "content": f"PREGUNTA:\n{test['prompt']}\n\nCRITERIO:\n{exp or 'respuesta correcta, clara y razonada'}\n\nRESPUESTA:\n{output[:6000]}"}]
        try:
            txt, _ = _call(judge[0], judge[1], msgs, prefs)
            m = re.search(r"\d{1,3}", txt)
            return (min(100.0, float(m.group())) if m else None), f"juez {judge[0]}:{judge[1]}"
        except (ProviderError, httpx.HTTPError):
            return None, "juez no disponible"
    return None, "sin comprobación"


def run_suite(run_id: int) -> None:
    from atlas.db import session_scope
    from atlas.models import IxArenaRun, IxArenaSuite
    from atlas.services.preferences import get_prefs
    with session_scope() as db:
        run = db.get(IxArenaRun, run_id)
        suite = db.get(IxArenaSuite, run.suite_id)
        prefs = get_prefs(db)
        provider, model = run.model.split(":", 1)
        judge = tuple(run.judge.split(":", 1)) if run.judge else None
        run.status = "running"
        db.commit()
        results = []
        for i, t in enumerate(suite.tests):
            msgs = []
            if t.get("system"):
                msgs.append({"role": "system", "content": t["system"]})
            ctx_note = None
            if t.get("rag"):
                from atlas.knowledge.service import search
                hits = search(db, t["prompt"], k=4)
                ctx = "\n\n".join(f"[{h.get('title') or h.get('document')}] {h.get('text') or h.get('snippet') or ''}" for h in hits)[:6000]
                msgs.append({"role": "system", "content": "Responde usando SOLO estos fragmentos de documentos (cítalos):\n" + (ctx or "(sin resultados)")})
                ctx_note = f"{len(hits)} fragmentos recuperados (RAG)"
            msgs.append({"role": "user", "content": t["prompt"]})
            t0 = time.perf_counter()
            try:
                out, usage = _call(provider, model, msgs, prefs)
                ms = round((time.perf_counter() - t0) * 1000)
                router.record(provider, model, "lab_arena", t0, True, usage=usage, prefs=prefs)
                score, how = _score(t, out, judge, prefs)
                price = (router.config(prefs)["prices"] or {}).get(f"{provider}:{model}")
                cost = None
                if price and usage.get("in") is not None and usage.get("out") is not None:
                    cost = round((usage["in"] * float(price.get("in", 0)) + usage["out"] * float(price.get("out", 0))) / 1e6, 6)
                results.append({"i": i, "output": out[:8000], "latency_ms": ms, "tokens_in": usage.get("in"), "tokens_out": usage.get("out"),
                                "cost_usd": cost, "score": score, "scored_by": how, "error": None, "rag": ctx_note})
            except (ProviderError, httpx.HTTPError) as exc:
                router.record(provider, model, "lab_arena", t0, False, str(exc), prefs=prefs)
                results.append({"i": i, "output": None, "latency_ms": round((time.perf_counter() - t0) * 1000), "tokens_in": None,
                                "tokens_out": None, "cost_usd": None, "score": None, "scored_by": None, "error": str(exc)[:300]})
            run.results = list(results)
            db.commit()
        ok = [r for r in results if not r["error"]]
        scored = [r["score"] for r in ok if r["score"] is not None]
        lat = [r["latency_ms"] for r in ok]
        toks = [r["tokens_out"] for r in ok if r["tokens_out"] is not None]
        costs = [r["cost_usd"] for r in ok if r["cost_usd"] is not None]
        run.summary = {"tests": len(results), "errors": len(results) - len(ok), "reliability_pct": round(len(ok) / len(results) * 100, 1) if results else None,
                       "avg_score": round(sum(scored) / len(scored), 1) if scored else None, "scored": len(scored),
                       "avg_latency_ms": round(sum(lat) / len(lat)) if lat else None, "p_max_latency_ms": max(lat) if lat else None,
                       "tokens_out": sum(toks) if toks else None, "tokens_per_s": round(sum(toks) / (sum(lat) / 1000), 1) if toks and lat and len(toks) == len(lat) else None,
                       "cost_usd": round(sum(costs), 6) if costs else None}
        run.status = "done" if ok else "error"
        run.error = None if ok else "Todas las pruebas fallaron"
        run.finished_at = datetime.utcnow()
        db.commit()


def start(run_id: int) -> None:
    threading.Thread(target=run_suite, args=(run_id,), name=f"arena-{run_id}", daemon=True).start()
