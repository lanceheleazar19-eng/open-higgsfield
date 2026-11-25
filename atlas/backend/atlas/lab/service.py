"""Lógica del INNOVATION LAB: centro de mando, radar, analíticas y pasos de automatización.
Todas las cifras se cuentan en la base de datos; nada se estima ni se rellena."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.lab import sources as src
from atlas.models import (AgentRun, IxArenaRun, IxDiscovery, IxExperiment, IxIdea, IxLibraryItem, IxPatent, IxPrototype, IxResearch,
                          IxSandboxRun, IxScenario, IxTechnology, ModelCall, Research)

CATEGORIES = {
    "ai": "Inteligencia artificial", "robotics": "Robótica", "automation": "Automatización", "quantum": "Computación cuántica",
    "biotech": "Biotecnología", "nanotech": "Nanotecnología", "energy": "Energía", "materials": "Materiales avanzados",
    "aerospace": "Aeroespacial", "medtech": "Medicina tecnológica", "xr": "Realidad virtual y aumentada", "security": "Ciberseguridad",
    "hardware": "Hardware", "software": "Software", "hci": "Interfaces humano-máquina", "industry": "Nuevas tecnologías industriales",
}
MATURITY = {"academic": "Investigación académica", "prototype": "Prototipo", "commercial": "Producto comercial", "speculative": "Tecnología especulativa"}
EXP_STATES = ("IDEA", "PLANNED", "RUNNING", "PAUSED", "COMPLETED", "FAILED", "ARCHIVED")


def reliability_for(url: str | None) -> str:
    """Fiabilidad por tipo de fuente (heurística transparente, la misma que usa el Research Engine)."""
    if not url:
        return "baja"
    try:
        from atlas.research.engine import reliability
        r = reliability(url)
        return {"high": "alta", "medium": "media", "low": "baja"}.get(r, r if r in ("alta", "media", "baja") else "media")
    except Exception:  # noqa: BLE001
        host = urlparse(url).netloc
        return "alta" if any(x in host for x in ("arxiv.org", "nature.com", "science.org", "ieee.org", "acm.org", ".gov", ".edu", "doi.org", "openalex")) else "media"


def command_center(db: Session) -> dict:
    now = datetime.utcnow()
    week = now - timedelta(days=7)
    lab_rids = [r.research_id for r in db.scalars(select(IxResearch))]
    active_research = [r for r in db.scalars(select(Research).where(Research.status.in_(("queued", "running")))) if r.id in lab_rids]
    running = list(db.scalars(select(IxExperiment).where(IxExperiment.status == "RUNNING")))
    arena = list(db.scalars(select(IxArenaRun).where(IxArenaRun.status.in_(("queued", "running")))))
    calls = list(db.scalars(select(ModelCall).where(ModelCall.created_at >= week, ModelCall.task.like("lab%"))))
    agent_runs = [a for a in db.scalars(select(AgentRun).where(AgentRun.created_at >= week).order_by(AgentRun.id.desc())) if "innovation" in (a.agents or [])]
    return {
        "status": {"active_research": len(active_research), "running_experiments": len(running), "arena_running": len(arena),
                   "label": "activo" if (active_research or running or arena) else "en espera"},
        "live": [{"type": "research", "id": r.id, "label": r.question[:120], "progress": round(100 * len((r.state or {}).get("done", [])) / 5), "step": r.step} for r in active_research]
        + [{"type": "arena", "id": a.id, "label": f"Arena · {a.model}", "progress": None, "step": f"{len(a.results)} pruebas"} for a in arena],
        "counts": {"experiments": db.scalar(select(func.count(IxExperiment.id))) or 0, "running": len(running),
                   "prototypes": db.scalar(select(func.count(IxPrototype.id))) or 0,
                   "ideas_pending": db.scalar(select(func.count(IxIdea.id)).where(IxIdea.status.in_(("new", "exploring")))) or 0,
                   "discoveries_7d": db.scalar(select(func.count(IxDiscovery.id)).where(IxDiscovery.created_at >= week)) or 0,
                   "technologies": db.scalar(select(func.count(IxTechnology.id))) or 0,
                   "library": db.scalar(select(func.count(IxLibraryItem.id))) or 0},
        "running_experiments": [{"id": e.id, "name": e.name, "started_on": e.started_on.isoformat() if e.started_on else None} for e in running],
        "recent_discoveries": [{"id": d.id, "title": d.title, "category": d.category, "maturity": d.maturity, "source": d.source_name,
                                "reliability": d.reliability, "date": (d.published_on or d.created_at.date()).isoformat()}
                               for d in db.scalars(select(IxDiscovery).order_by(IxDiscovery.id.desc()).limit(8))],
        "emerging": [{"id": t.id, "name": t.name, "category": t.category, "maturity": t.maturity,
                      "discoveries": db.scalar(select(func.count(IxDiscovery.id)).where(IxDiscovery.technology_id == t.id)) or 0}
                     for t in db.scalars(select(IxTechnology).where(IxTechnology.watch.is_(True)).limit(12))],
        "recent_results": [{"id": e.id, "name": e.name, "status": e.status, "verdict": e.verdict, "date": e.updated_at.isoformat()}
                           for e in db.scalars(select(IxExperiment).where(IxExperiment.status.in_(("COMPLETED", "FAILED"))).order_by(IxExperiment.updated_at.desc()).limit(5))],
        "agents": [{"at": a.created_at.isoformat(), "request": a.request[:120], "agents": a.agents, "status": a.status} for a in agent_runs[:6]],
        "resources_7d": {"model_calls": len(calls), "errors": sum(1 for c in calls if not c.ok),
                         "avg_latency_ms": round(sum(c.latency_ms for c in calls) / len(calls)) if calls else None,
                         "tokens_out": sum(c.tokens_out or 0 for c in calls) or None,
                         "cost_usd": round(sum(c.cost_usd or 0 for c in calls), 4) if any(c.cost_usd for c in calls) else None,
                         "sandbox_runs": db.scalar(select(func.count(IxSandboxRun.id)).where(IxSandboxRun.created_at >= week)) or 0},
    }


def analytics(db: Session, start: date | None, end: date | None, category: str | None) -> dict:
    s = datetime.combine(start, datetime.min.time()) if start else datetime(2000, 1, 1)
    e = datetime.combine(end + timedelta(days=1), datetime.min.time()) if end else datetime.utcnow() + timedelta(days=1)

    def cat(q, col):  # noqa: ANN001, ANN202
        return q.where(col == category) if category else q
    lab = {r.research_id: r for r in db.scalars(select(IxResearch))}
    researches = [r for r in db.scalars(select(Research).where(Research.created_at >= s, Research.created_at < e))
                  if r.id in lab and (not category or lab[r.id].category == category)]
    exps = list(db.scalars(cat(select(IxExperiment).where(IxExperiment.created_at >= s, IxExperiment.created_at < e), IxExperiment.category)))
    protos = list(db.scalars(select(IxPrototype).where(IxPrototype.created_at >= s, IxPrototype.created_at < e)))
    ideas = list(db.scalars(cat(select(IxIdea).where(IxIdea.created_at >= s, IxIdea.created_at < e), IxIdea.category)))
    disc = list(db.scalars(cat(select(IxDiscovery).where(IxDiscovery.created_at >= s, IxDiscovery.created_at < e), IxDiscovery.category)))
    months: dict[str, Counter] = defaultdict(Counter)
    for x in exps:
        months[x.created_at.strftime("%Y-%m")]["experiments"] += 1
    for x in ideas:
        months[x.created_at.strftime("%Y-%m")]["ideas"] += 1
    for x in disc:
        months[x.created_at.strftime("%Y-%m")]["discoveries"] += 1
    for x in researches:
        months[x.created_at.strftime("%Y-%m")]["research"] += 1
    for x in protos:
        months[x.created_at.strftime("%Y-%m")]["prototypes"] += 1
    return {
        "research_done": sum(1 for r in researches if r.status == "done"), "research_total": len(researches),
        "experiments": len(exps), "experiments_completed": sum(1 for x in exps if x.status == "COMPLETED"),
        "experiments_supported": sum(1 for x in exps if x.verdict == "supported"), "experiments_refuted": sum(1 for x in exps if x.verdict == "refuted"),
        "experiments_failed": sum(1 for x in exps if x.status == "FAILED"),
        "prototypes": len(protos), "prototypes_done": sum(1 for x in protos if x.status == "done"),
        "ideas": len(ideas), "ideas_generated": sum(1 for x in ideas if x.origin == "generated"),
        "ideas_converted": sum(1 for x in ideas if x.experiment_id or x.prototype_id or x.opportunity_id or x.project_id),
        "hours": round(sum(x.hours for x in exps) + sum(x.hours for x in protos), 1),
        "costs": round(sum(x.cost for x in exps) + sum(x.cost for x in protos), 2),
        "technologies": len({d.technology_id for d in disc if d.technology_id}) or db.scalar(select(func.count(IxTechnology.id))) or 0,
        "discoveries": len(disc), "by_category": Counter(d.category for d in disc).most_common(),
        "by_maturity": Counter(d.maturity for d in disc).most_common(),
        "months": [{"month": m, **c} for m, c in sorted(months.items())],
        "scenarios": db.scalar(select(func.count(IxScenario.id))) or 0, "patents": db.scalar(select(func.count(IxPatent.id))) or 0,
        "note": "Un experimento solo cuenta como exitoso con veredicto «hipótesis respaldada» y resultados observados registrados.",
    }


def import_papers(db: Session, query: str, category: str, technology_id: int | None, sources_: list[str], limit: int = 8) -> dict:
    """Importa publicaciones REALES (arXiv/OpenAlex) como descubrimientos (sin duplicar)."""
    added, errors = [], []
    for s in sources_:
        try:
            items = src.arxiv(query, limit) if s == "arxiv" else src.openalex(query, limit)
        except src.SourceError as exc:
            errors.append(str(exc))
            continue
        for it in items:
            if not it.get("external_id") or db.scalar(select(IxDiscovery.id).where(IxDiscovery.external_id == it["external_id"])):
                continue
            d = IxDiscovery(title=it["title"][:400], category=category, technology_id=technology_id, kind="paper", maturity="academic",
                            description=(it.get("summary") or "")[:4000], source_name=it["source"], source_url=it["url"],
                            published_on=src.parse_date(it.get("published")), reliability=it["reliability"], origin=s,
                            external_id=it["external_id"], authors=it.get("authors") or [])
            db.add(d)
            added.append(it["title"])
    db.flush()
    return {"added": len(added), "titles": added[:20], "errors": errors}


def discoveries_from_research(db: Session, r: Research, category: str, technology_id: int | None) -> int:
    """Convierte las fuentes de una investigación terminada en descubrimientos (con su fiabilidad)."""
    n = 0
    for s in (r.state or {}).get("sources", [])[:20]:
        url = s.get("url")
        if not url or db.scalar(select(IxDiscovery.id).where(IxDiscovery.source_url == url)):
            continue
        db.add(IxDiscovery(title=(s.get("title") or url)[:400], category=category, technology_id=technology_id, kind="news", maturity="speculative",
                           description=(s.get("excerpt") or "")[:2000], source_name=urlparse(url).netloc, source_url=url,
                           reliability=reliability_for(url), origin="research", external_id=f"research:{r.id}:{url}"[:200]))
        n += 1
    db.flush()
    return n


# ───────── Pasos de automatización (se registran en el motor de Workflows existente) ─────────

def step_tech_watch(db: Session) -> str:
    techs = list(db.scalars(select(IxTechnology).where(IxTechnology.watch.is_(True))))
    if not techs:
        return "No hay tecnologías en seguimiento: añádelas en el Technology Radar."
    lines = []
    for t in techs[:6]:
        res = import_papers(db, t.name, t.category, t.id, ["arxiv", "openalex"], 5)
        lines.append(f"• {t.name}: {res['added']} publicaciones nuevas" + (f" (errores: {'; '.join(res['errors'])})" if res["errors"] else ""))
    db.commit()
    return "Seguimiento tecnológico:\n" + "\n".join(lines)


def step_arena(db: Session, params: dict) -> str:
    from atlas.lab import arena
    from atlas.models import IxArenaSuite
    suite = db.get(IxArenaSuite, int(params.get("suite_id") or 0)) if params.get("suite_id") else db.scalar(select(IxArenaSuite).order_by(IxArenaSuite.id.desc()))
    if not suite:
        return "No hay baterías de pruebas en el Model Testing Arena."
    from atlas.services.preferences import get_prefs
    models = arena.available_models(get_prefs(db))
    for m in models:
        run = IxArenaRun(suite_id=suite.id, model=m["id"])
        db.add(run)
        db.flush()
        db.commit()
        arena.start(run.id)
    return f"Comparación de modelos lanzada: «{suite.name}» en {len(models)} modelo(s) configurado(s)."


def step_experiments_review(db: Session) -> str:
    today = date.today()
    running = list(db.scalars(select(IxExperiment).where(IxExperiment.status == "RUNNING")))
    stale = [e for e in running if e.started_on and (today - e.started_on).days > 14]
    no_result = list(db.scalars(select(IxExperiment).where(IxExperiment.status == "COMPLETED", IxExperiment.verdict.is_(None))))
    lines = [f"• En curso: {len(running)}" + (f"; más de 14 días: {', '.join(e.name for e in stale)}" if stale else "")]
    if no_result:
        lines.append("• Completados sin veredicto (falta evaluar resultados): " + ", ".join(e.name for e in no_result))
    return "Revisión de experimentos:\n" + "\n".join(lines)


def step_lab_report(db: Session) -> str:
    a = analytics(db, date.today() - timedelta(days=7), date.today(), None)
    return (f"Informe semanal del laboratorio:\n• Investigaciones terminadas: {a['research_done']} de {a['research_total']}\n"
            f"• Experimentos nuevos: {a['experiments']} (respaldados {a['experiments_supported']}, refutados {a['experiments_refuted']}, fallidos {a['experiments_failed']})\n"
            f"• Prototipos: {a['prototypes']} · Ideas: {a['ideas']} (convertidas {a['ideas_converted']})\n"
            f"• Descubrimientos: {a['discoveries']} · Horas: {a['hours']} · Costes registrados: {a['costs']} €")


def step_patent_watch(db: Session) -> str:
    if not src.epo_configured():
        return "Seguimiento de patentes: falta configurar Espacenet (EPO OPS). Se omite sin inventar resultados."
    techs = list(db.scalars(select(IxTechnology).where(IxTechnology.watch.is_(True))))[:4]
    n = 0
    for t in techs:
        try:
            for p in src.epo_search(t.name, 5):
                if p["number"] and not db.scalar(select(IxPatent.id).where(IxPatent.number == p["number"])):
                    db.add(IxPatent(kind="external", title=p["title"][:400], number=p["number"], office=p["office"], applicants=p["applicants"],
                                    abstract=p["abstract"], url=p["url"], published_on=src.parse_date(p["published"]), technology=t.name, source="epo"))
                    n += 1
        except src.SourceError as exc:
            return f"Seguimiento de patentes: {exc}"
    db.commit()
    return f"Seguimiento de patentes: {n} nuevas registradas."
