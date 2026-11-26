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
    from atlas.metabrain.llm import compat_conf
    c = compat_conf()
    if c:
        out.append({"id": f"compat:{c['model']}", "provider": "compat", "model": c["model"], "local": False, "label": c["label"]})
    if out:  # el propio META-BRAIN compite con los mismos modelos y herramientas reales
        out.append({"id": "vistan:meta-brain", "provider": "vistan", "model": "meta-brain", "local": None,
                    "label": "VISTAN META-BRAIN (router + agentes + memoria + verificación)"})
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
    if provider == "vistan":
        return _call_vistan(messages)
    from atlas.metabrain.llm import make
    prov = make(provider)
    if not prov:
        raise ProviderError(f"{provider}: sin clave")
    text = "".join(prov.chat_stream(model, messages))
    return text, dict(getattr(prov, "last_usage", None) or {})


def _call_vistan(messages: list[dict]) -> tuple[str, dict]:
    """El META-BRAIN resuelve la prueba con su proceso completo (modo automático). Uso agregado de todas sus llamadas."""
    from atlas.db import session_scope
    from atlas.metabrain import engine
    text = "\n\n".join(m["content"] for m in messages if m["role"] in ("system", "user"))
    with session_scope() as db:
        r = engine.run_sync(db, text, "auto", source="bench")
        if r.status != "done":
            raise ProviderError(f"META-BRAIN: {r.error or r.status}")
        return r.answer or "", {"in": r.tokens_in, "out": r.tokens_out, "calls": r.calls, "meta_run": r.id, "cost": r.cost_usd}


NUM_RX = re.compile(r"-?\d+(?:[.,]\d+)?")


def _last_number(text: str) -> float | None:
    nums = NUM_RX.findall(text.replace("\u00a0", " "))
    for n in reversed(nums):
        try:
            return float(n.replace(",", "."))
        except ValueError:
            continue
    return None


def _code(output: str) -> str:
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", output, re.S)
    return (m.group(1) if m else output).strip()


def _score(test: dict, output: str, judge: tuple[str, str] | None, prefs: dict, db=None) -> tuple[float | None, str]:  # noqa: ANN001
    chk, exp = test.get("check", "none"), str(test.get("expected") or "")
    if chk == "live":
        from atlas.metabrain.bench import live_value
        real = live_value(db, exp) if db is not None else None
        if real is None:
            return None, "dato real no disponible"
        got = _last_number(output)
        return (100.0 if got is not None and abs(got - float(real)) < 1e-9 else 0.0), f"dato real de VISTAN = {real}"
    if chk == "number":
        got = _last_number(output)
        try:
            want = float(exp.replace(",", "."))
        except ValueError:
            return None, "número esperado no válido"
        return (100.0 if got is not None and abs(got - want) <= max(1e-6, abs(want) * 1e-6) else 0.0), "número"
    if chk == "python":
        from atlas.lab.sandbox import run_python
        res = run_python(_code(output) + "\n\n" + exp)
        return (100.0 if res["status"] == "ok" else 0.0), f"tests en el sandbox ({res['status']})"
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
        from atlas.metabrain.governance import killed
        if killed(prefs):
            run.status, run.error, run.finished_at = "error", "Kill switch activo", datetime.utcnow()
            db.commit()
            return
        run.status = "running"
        db.commit()
        results = []
        for i, t in enumerate(suite.tests):
            if killed(get_prefs(db)):
                run.error = "Kill switch activado durante la prueba"
                break
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
                if provider != "vistan":  # las llamadas internas del META-BRAIN ya quedan registradas una a una
                    router.record(provider, model, "lab_arena", t0, True, usage=usage, prefs=prefs)
                if t.get("check") == "consistency":
                    outs = [out]
                    for _ in range(max(1, int(t.get("repeat", 3))) - 1):
                        o2, u2 = _call(provider, model, msgs, prefs)
                        outs.append(o2)
                        for k in ("in", "out"):
                            if usage.get(k) is not None and u2.get(k) is not None:
                                usage[k] += u2[k]
                    norm = [re.sub(r"[^a-z0-9áéíóúñ]+", " ", o.lower()).strip() for o in outs]
                    agree = max(norm.count(x) for x in norm) / len(norm)
                    right = sum(1 for o in outs if str(t.get("expected") or "").lower() in o.lower()) if t.get("expected") else None
                    score = round(agree * 100 * (right / len(outs) if right is not None else 1), 1)
                    how = f"consistencia {round(agree * len(outs))}/{len(outs)}" + (f" · correctas {right}/{len(outs)}" if right is not None else "")
                    out = "\n---\n".join(outs)
                else:
                    score, how = _score(t, out, judge, prefs, db)
                price = (router.config(prefs)["prices"] or {}).get(f"{provider}:{model}")
                cost = usage.get("cost") if provider == "vistan" else None
                if price and usage.get("in") is not None and usage.get("out") is not None:
                    cost = round((usage["in"] * float(price.get("in", 0)) + usage["out"] * float(price.get("out", 0))) / 1e6, 6)
                results.append({"i": i, "output": out[:8000], "latency_ms": ms, "tokens_in": usage.get("in"), "tokens_out": usage.get("out"),
                                "cost_usd": cost, "score": score, "scored_by": how, "error": None, "rag": ctx_note,
                                "category": t.get("category"), "meta_run": usage.get("meta_run"), "calls": usage.get("calls")})
            except (ProviderError, httpx.HTTPError) as exc:
                if provider != "vistan":
                    router.record(provider, model, "lab_arena", t0, False, str(exc), prefs=prefs)
                results.append({"i": i, "output": None, "latency_ms": round((time.perf_counter() - t0) * 1000), "tokens_in": None,
                                "tokens_out": None, "cost_usd": None, "score": None, "scored_by": None, "error": str(exc)[:300],
                                "category": t.get("category")})
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
                       "cost_usd": round(sum(costs), 6) if costs else None,
                       "by_category": {c: round(sum(v) / len(v), 1) for c, v in _by_cat(results).items()}}
        run.status = "done" if ok else "error"
        run.error = None if ok else "Todas las pruebas fallaron"
        run.finished_at = datetime.utcnow()
        db.commit()


def _by_cat(results: list[dict]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for r in results:
        if r.get("category") and r.get("score") is not None:
            out.setdefault(r["category"], []).append(r["score"])
    return out


def start(run_id: int) -> None:
    threading.Thread(target=run_suite, args=(run_id,), name=f"arena-{run_id}", daemon=True).start()
