"""Self-Evaluation Engine: métricas calculadas SOLO con registros reales (ejecuciones del META-BRAIN, llamadas a modelos,
investigaciones, benchmarks y tu feedback). Las recomendaciones salen de reglas sobre esos datos y nunca cambian código ni
configuración por sí solas: te proponen qué probar, y tú decides."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.metabrain import llm
from atlas.models import IxArenaRun, IxArenaSuite, MbRun, Research


def _pct(a: int, b: int) -> float | None:
    return round(a / b * 100, 1) if b else None


def evaluate(db: Session, days: int = 30) -> dict:
    since = datetime.utcnow() - timedelta(days=days)
    runs = list(db.scalars(select(MbRun).where(MbRun.created_at >= since)))
    fin = [r for r in runs if r.status in ("done", "error", "cancelled")]
    done = [r for r in runs if r.status == "done"]
    lat = sorted(r.duration_ms for r in done if r.duration_ms)
    ver = [r.verification for r in done if (r.verification or {}).get("checked")]
    checked = sum(v["checked"] for v in ver)
    supported = sum(v["supported"] for v in ver)
    high = sum(1 for r in done if any(i.get("gravedad") == "alta" for i in (r.critique or {}).get("issues", [])))
    fb = [r.feedback for r in runs if r.feedback is not None]
    costs = [r.cost_usd for r in done if r.cost_usd is not None]
    by_mode: dict[str, dict] = {}
    for r in fin:
        m = by_mode.setdefault(r.mode, {"runs": 0, "done": 0, "lat": []})
        m["runs"] += 1
        if r.status == "done":
            m["done"] += 1
            if r.duration_ms:
                m["lat"].append(r.duration_ms)
    modes = {k: {"runs": v["runs"], "completion_pct": _pct(v["done"], v["runs"]),
                 "avg_ms": round(sum(v["lat"]) / len(v["lat"])) if v["lat"] else None} for k, v in by_mode.items()}
    # Calidad de fuentes: fiabilidad de las fuentes leídas en investigaciones del periodo
    rel = {"alta": 0, "media": 0, "baja": 0}
    for rs in db.scalars(select(Research).where(Research.created_at >= since, Research.status == "done")):
        for s in (rs.state or {}).get("sources", []):
            if s.get("read") and s.get("reliability") in rel:
                rel[s["reliability"]] += 1
    models = llm.stats(days)
    bench = []
    for r in db.scalars(select(IxArenaRun).where(IxArenaRun.status == "done").order_by(IxArenaRun.id.desc()).limit(40)):
        suite = db.get(IxArenaSuite, r.suite_id)
        bench.append({"suite": suite.name if suite else r.suite_id, "model": r.model, "avg_score": (r.summary or {}).get("avg_score"),
                      "reliability_pct": (r.summary or {}).get("reliability_pct"), "avg_latency_ms": (r.summary or {}).get("avg_latency_ms"),
                      "at": r.created_at.isoformat()})
    metrics = {
        "runs": len(runs), "finished": len(fin), "completion_pct": _pct(len(done), len(fin)),
        "error_pct": _pct(sum(1 for r in fin if r.status == "error"), len(fin)),
        "avg_latency_ms": round(sum(lat) / len(lat)) if lat else None, "p95_latency_ms": lat[min(len(lat) - 1, int(len(lat) * .95))] if lat else None,
        "verified_claims": checked, "supported_pct": _pct(supported, checked), "runs_with_high_issues_pct": _pct(high, len(done)),
        "cost_usd": round(sum(costs), 4) if costs else None, "calls": sum(r.calls or 0 for r in runs),
        "feedback": {"count": len(fb), "positive_pct": _pct(sum(1 for f in fb if f > 0), len(fb))},
        "source_quality": {**rel, "high_pct": _pct(rel["alta"], sum(rel.values()))},
    }
    return {"days": days, "metrics": metrics, "by_mode": modes, "models": models, "benchmarks": bench,
            "recommendations": recommendations(metrics, models, modes),
            "note": "Todo se calcula con registros reales. Sin datos suficientes se muestra N/D. Ninguna mejora se aplica sola."}


def recommendations(m: dict, models: list[dict], modes: dict) -> list[str]:
    rec = []
    for s in models:
        if s["calls"] >= 10 and s["error_rate"] >= 20:
            alt = [x for x in models if x["id"] != s["id"] and x["calls"] >= 10 and x["error_rate"] < s["error_rate"] / 2]
            rec.append(f"{s['id']} falla en el {s['error_rate']} % de {s['calls']} llamadas"
                       + (f"; {alt[0]['id']} tiene un {alt[0]['error_rate']} % con {alt[0]['calls']} llamadas: considera preferirlo para esas tareas." if alt else "."))
    if m["verified_claims"] >= 10 and (m["supported_pct"] or 0) < 60:
        rec.append(f"Solo el {m['supported_pct']} % de los hechos verificados tiene respaldo textual: usa el modo investigación o añade documentos a Conocimiento.")
    if m["finished"] >= 10 and (m["error_pct"] or 0) >= 20:
        rec.append(f"El {m['error_pct']} % de las ejecuciones termina en error: revisa la traza de las fallidas (límites, modelos caídos).")
    c = modes.get("council")
    if c and c["runs"] >= 5 and c["avg_ms"] and c["avg_ms"] > 180000:
        rec.append(f"El consejo tarda de media {round(c['avg_ms'] / 1000)} s: reduce el número de especialistas en Gobierno o usa un modelo más rápido.")
    if m["feedback"]["count"] >= 5 and (m["feedback"]["positive_pct"] or 0) < 50:
        rec.append(f"Solo el {m['feedback']['positive_pct']} % de tus valoraciones es positiva: compara modelos en el Benchmark Center.")
    if not rec:
        rec.append("Sin recomendaciones: no hay datos suficientes o los indicadores están dentro de los umbrales.")
    return rec
