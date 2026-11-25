"""Herramientas reales de los agentes. Cada una declara su nivel de permiso (READ/WRITE/EXECUTE/ADMIN)
y devuelve datos de tu base de datos o de servicios conectados. Ninguna inventa resultados."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session


@dataclass
class Ctx:
    db: Session
    prefs: dict
    text: str
    tz: str

    @property
    def today(self) -> date:
        return datetime.now(ZoneInfo(self.tz)).date()


@dataclass
class Tool:
    name: str
    level: str
    description: str
    fn: Callable[[Ctx], object]
    external: bool = False  # sale a internet


def _finance(c: Ctx) -> dict:
    from atlas.finance.service import summary
    s = summary(c.db, c.today)
    return {k: s[k] for k in ("month", "income_cents", "expense_cents", "net_cents", "savings_rate", "balance_cents",
                              "by_category", "budgets", "months")} | {"nota": "importes en céntimos; dinero REAL registrado"}


def _finance_recent(c: Ctx) -> list:
    from atlas.finance.service import to_dict
    from atlas.models import Transaction
    return [to_dict(t) for t in c.db.scalars(select(Transaction).order_by(Transaction.occurred_on.desc(), Transaction.id.desc()).limit(15))]


def _gym(c: Ctx) -> dict:
    from atlas.gym import service as g
    return g.snapshot(c.db, c.today)


def _nutrition(c: Ctx) -> dict:
    from atlas.nutrition import service as n
    cfg = c.prefs.get("nutrition_profile")
    return {"hoy": n.day_totals(c.db, c.today), "objetivos": n.compute_targets(cfg, n.latest_weight(c.db)) if cfg else None,
            "ultimos_7_dias": n.week_series(c.db, c.today), "peso_actual": n.latest_weight(c.db)}


def _health(c: Ctx) -> dict:
    from atlas.api.health import snapshot
    return snapshot(c.db, c.today)


def _trading(c: Ctx) -> dict:
    from atlas.trading.service import stats
    cap = c.prefs.get("paper_capital")
    s = stats(c.db, float(cap) if cap else None)
    return {k: v for k, v in s.items() if k != "curve"} | {"aviso": "SIMULACIÓN: capital virtual, nunca dinero real"}


def _desk(c: Ctx) -> dict:
    """Trading Desk (simulación): cuentas, posiciones, estadísticas, riesgo y patrones del diario."""
    from datetime import timezone as _tz

    from atlas.desk import engine, tutor
    accs = engine.ensure_accounts(c.db)
    start = datetime.now(ZoneInfo(c.tz)).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(_tz.utc).replace(tzinfo=None)
    out = {}
    for a in accs:
        ctx = tutor.context(c.db, a, None, None, start)
        out[a.kind] = {k: ctx[k] for k in ("cuenta", "posiciones_abiertas", "ordenes_pendientes", "estadisticas", "patrones_del_diario")}
    return out | {"aviso": "PAPER TRADING: dinero virtual. El agente nunca ejecuta operaciones por su cuenta."}


def _betting(c: Ctx) -> dict:
    """Paper Betting (dinero ficticio): bankroll, rendimiento, calibración y últimos pronósticos."""
    from atlas.bets import engine
    from atlas.models import BtBet
    a = engine.analytics(c.db)
    recent = [engine.bet_dict(c.db, b) for b in c.db.scalars(select(BtBet).order_by(BtBet.id.desc()).limit(8))]
    return {k: v for k, v in a.items() if k != "curve"} | {"ultimos": recent,
            "aviso": "SIMULACIÓN con dinero ficticio. No prometer ganancias ni recomendar perseguir pérdidas."}


# ───────── LIFE OS ─────────

def _life_opps(c: Ctx) -> list:
    from atlas.life import service as sv
    from atlas.models import LfOpportunity
    return [{"nombre": o.name, "estado": o.status, "problema": o.problem, "cliente": o.customer, "mercado": o.market,
             "economia_estimada": sv.economics(o.economics or {}), "puntuacion": sv.opp_score(o.scores or {}),
             "proximas_acciones": o.next_actions, "riesgos": o.risks, "informe_ia": (o.report or {}).get("resumen")}
            for o in c.db.scalars(select(LfOpportunity).order_by(LfOpportunity.updated_at.desc()).limit(10))]


def _life_wealth(c: Ctx) -> dict:
    from atlas.life import service as sv
    return {"patrimonio": sv.networth(c.db), "ahorro_real": sv.savings_stats(c.db, c.today, 6),
            "aviso": "patrimonio: separa valores reales de estimados; el dinero virtual (trading/apuestas) no cuenta"}


def _life_learning(c: Ctx) -> list:
    from atlas.life import service as sv
    from atlas.models import LfSubject
    return [{"materia": s.name, **{k: v for k, v in sv.mastery(c.db, s.id).items() if k != "rule"}}
            for s in sv.ensure_subjects(c.db) if isinstance(s, LfSubject)]


def _life_sims(c: Ctx) -> list:
    from atlas.models import LfSimulation
    return [{"area": s.area, "escenario": s.title, "fecha": s.finished_at.date().isoformat() if s.finished_at else None,
             "criterios": (s.debrief or {}).get("criterios"), "a_mejorar": (s.debrief or {}).get("a_mejorar")}
            for s in c.db.scalars(select(LfSimulation).where(LfSimulation.status == "finished").order_by(LfSimulation.id.desc()).limit(8))]


def _life_discipline(c: Ctx) -> dict:
    from atlas.life import service as sv
    r = sv.discipline_report(c.db, c.today)
    return {"habitos": [{k: h[k] for k in ("name", "category", "compliance_30d", "streak", "best_streak", "done_today", "due_today")} for h in r["habits"]],
            "compromisos_vencidos": r["overdue_commitments"], "cumplimiento_compromisos_90d": r["commitment_rate_90d"],
            "hallazgos": r["findings"], "datos_automaticos": r["auto"]}


def _life_contacts(c: Ctx) -> dict:
    from atlas.models import LfContact
    cs = list(c.db.scalars(select(LfContact)))
    return {"total": len(cs), "seguimientos_pendientes": [{"nombre": x.name, "empresa": x.company, "fecha": x.next_followup.isoformat()}
                                                           for x in cs if x.next_followup and x.next_followup <= c.today + timedelta(days=7)],
            "aviso": "datos privados: no compartir fuera de VISTAN"}


def _life_decisions(c: Ctx) -> dict:
    from atlas.life import service as sv
    from atlas.models import LfDecision
    ds = list(c.db.scalars(select(LfDecision).order_by(LfDecision.day.desc()).limit(10)))
    return {"decisiones": [{"titulo": d.title, "fecha": d.day.isoformat(), "decision": d.decision, "confianza": d.confidence,
                            "esperado": d.expected_result, "real": d.actual_result, "resultado": d.outcome} for d in ds],
            "calibracion": sv.decision_calibration(c.db)}


def _life_failures(c: Ctx) -> dict:
    from atlas.life import service as sv
    from atlas.models import LfFailure
    return {"errores": [{"titulo": f.title, "tipo": f.kind, "causas": f.causes, "lecciones": f.lessons, "etiquetas": f.tags}
                        for f in c.db.scalars(select(LfFailure).order_by(LfFailure.day.desc()).limit(10))],
            "patrones": sv.failure_patterns(c.db)}


def _life_goals(c: Ctx) -> dict:
    from atlas.life import service as sv
    return {"estancados": sv.stalled_goals(c.db, c.today)}


def _life_radar(c: Ctx) -> list:
    from atlas.models import LfRadar, Research
    out = []
    for rd in c.db.scalars(select(LfRadar).order_by(LfRadar.id.desc()).limit(5)):
        r = c.db.get(Research, rd.research_id)
        out.append({"busqueda": rd.query, "enfoque": rd.lens, "estado": r.status if r else None,
                    "conclusion": (r.report or {}).get("summary") if r and isinstance(r.report, dict) else None,
                    "confianza": r.confidence if r else None, "fuentes": len((r.state or {}).get("sources", [])) if r else 0,
                    "fecha": rd.created_at.date().isoformat()})
    return out


def _life_vision(c: Ctx) -> list:
    from atlas.models import LfVision
    return [{"seccion": v.section, "contenido": v.content[:600]} for v in c.db.scalars(select(LfVision)) if v.content]


def _tasks(c: Ctx) -> dict:
    from atlas.services import tasks as t
    return {"hoy": t.summary(c.db, c.tz), "semana": t.plan_week(c.db, c.tz)}


def _goals(c: Ctx) -> list:
    from atlas.services.goals import snapshot
    return snapshot(c.db, c.today)


def _calendar(c: Ctx) -> list:
    from atlas.models import CalendarEvent
    now = datetime.utcnow()
    z = ZoneInfo(c.tz)
    return [{"titulo": e.title, "inicio": e.start_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(z).isoformat(timespec="minutes"),
             "lugar": e.location, "origen": e.source}
            for e in c.db.scalars(select(CalendarEvent).where(CalendarEvent.start_at >= now - timedelta(hours=2),
                                                              CalendarEvent.start_at <= now + timedelta(days=14))
                                  .order_by(CalendarEvent.start_at).limit(25))]


def _insights(c: Ctx) -> list:
    from atlas.services.insights import detect
    return [{k: i[k] for k in ("title", "what", "recommendation")} for i in detect(c.db, c.prefs)]


def _memory(c: Ctx) -> list:
    from atlas.services import memory as m
    return [{"id": x.id, "contenido": x.content, "tipo": x.kind, "fecha": x.updated_at.date().isoformat()}
            for x in m.search_memories(c.db, c.text, limit=8)]


def _memory_stats(c: Ctx) -> dict:
    from atlas.services.memory import counts
    from atlas.models import Entity, Relation
    return counts(c.db) | {"entidades": c.db.scalar(select(func.count(Entity.id))),
                           "relaciones": c.db.scalar(select(func.count(Relation.id)))}


def _docs(c: Ctx) -> list:
    from atlas.knowledge.service import search
    return search(c.db, c.text, k=5)


def _research_recent(c: Ctx) -> list:
    from atlas.models import Research
    return [{"id": r.id, "pregunta": r.question, "estado": r.status, "confianza": r.confidence,
             "resumen": (r.report or {}).get("summary")}
            for r in c.db.scalars(select(Research).order_by(Research.created_at.desc()).limit(5))]


def _projects(c: Ctx) -> list:
    from atlas.models import Project, Task
    out = []
    for p in c.db.scalars(select(Project).where(Project.status.in_(("active", "paused"))).order_by(Project.updated_at.desc()).limit(10)):
        open_t = c.db.scalar(select(func.count(Task.id)).where(Task.project_id == p.id, Task.status == "pending")) or 0
        done_t = c.db.scalar(select(func.count(Task.id)).where(Task.project_id == p.id, Task.status == "done")) or 0
        out.append({"id": p.id, "nombre": p.name, "estado": p.status, "descripcion": p.description,
                    "tareas_abiertas": open_t, "tareas_hechas": done_t})
    return out


def _security(c: Ctx) -> dict:
    from atlas.brain.providers import CLOUD
    from atlas.integrations.secrets import get_secret
    from atlas.models import ActivityLog, Approval
    from atlas.security.policy import NEVER, policy
    from atlas.services.backup import list_backups
    return {"politica": policy(c.prefs), "nunca": NEVER,
            "aprobaciones_pendientes": c.db.scalar(select(func.count(Approval.id)).where(Approval.status == "pending")),
            "credenciales_configuradas": [n for n in ("gmail_app_password", "icloud_app_password", "health_token",
                                                      *[f"{p}_api_key" for p in CLOUD]) if get_secret(n)],
            "ultimas_acciones_sensibles": [a.summary for a in c.db.scalars(
                select(ActivityLog).where(ActivityLog.module == "security").order_by(ActivityLog.id.desc()).limit(8))],
            "copias_de_seguridad": list_backups()[:3]}


def _system(c: Ctx) -> dict:
    import platform
    import sys

    from atlas import __version__
    from atlas.brain.orchestrator import brain_status
    from atlas.models import ModelCall, Research, WorkflowRun
    since = datetime.utcnow() - timedelta(days=7)
    errors = [f"{m.provider}:{m.model} → {m.error}" for m in c.db.scalars(
        select(ModelCall).where(ModelCall.ok.is_(False), ModelCall.created_at >= since).order_by(ModelCall.id.desc()).limit(5))]
    errors += [f"Investigación #{r.id}: {r.error}" for r in c.db.scalars(select(Research).where(Research.status == "error").limit(3))]
    errors += [f"Workflow run #{w.id}: {w.output}" for w in c.db.scalars(select(WorkflowRun).where(WorkflowRun.status == "error").limit(3))]
    return {"version": __version__, "python": sys.version.split()[0], "sistema": platform.platform(),
            "ia": {k: v for k, v in brain_status(c.prefs).items() if k in ("reachable", "model", "note")},
            "errores_recientes": errors}


def _progress(c: Ctx) -> dict:
    from atlas.progress.service import facts, gather
    g = gather(c.db, c.today, c.prefs)
    return {"hechos": facts(g), "tendencia_peso": g["weight_trend"], "tendencia_volumen": g["tonnage_trend"],
            "tendencia_frecuencia": g["sessions_trend"], "fotos": len(g["photos"]),
            "nota": "tendencias calculadas con todos los registros; una variación de un día no es tendencia"}


def _physique(c: Ctx) -> list:
    from atlas.models import Analysis
    return [{"fecha": a.created_at.date().isoformat(), "tipo": a.kind, "fiabilidad": a.result.get("fiabilidad"),
             "observaciones": a.result.get("observaciones"), "a_trabajar": a.result.get("a_trabajar"),
             "cambios": a.result.get("cambios"), "aviso": "observaciones visuales, no medidas"}
            for a in c.db.scalars(select(Analysis).where(Analysis.kind.in_(("physique", "compare"))).order_by(Analysis.id.desc()).limit(2))]


def _meal_photos(c: Ctx) -> list:
    from atlas.models import MealPhoto
    since = datetime.utcnow() - timedelta(days=7)
    return [{"fecha": m.eaten_at.isoformat(timespec="minutes"), "comida": m.meal, "descripcion": m.description,
             "estado": m.status, "totales_estimados": (m.analysis or {}).get("totals"), "calidad": (m.analysis or {}).get("quality")}
            for m in c.db.scalars(select(MealPhoto).where(MealPhoto.eaten_at >= since).order_by(MealPhoto.eaten_at.desc()).limit(10))]


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("progress.trends", "READ", "Progreso: tendencias reales de peso, entreno y nutrición", _progress),
    Tool("physique.latest", "READ", "Últimos análisis de tus fotos de físico", _physique),
    Tool("meals.photos", "READ", "Comidas fotografiadas de los últimos 7 días", _meal_photos),
    Tool("finance.summary", "READ", "Resumen del mes, presupuestos y evolución (dinero real)", _finance),
    Tool("finance.recent", "READ", "Últimos movimientos registrados", _finance_recent),
    Tool("gym.snapshot", "READ", "Entrenamiento: rutina de hoy, volumen, progresión y estancamientos", _gym),
    Tool("nutrition.today", "READ", "Calorías y macros de hoy, objetivos y últimos 7 días", _nutrition),
    Tool("health.week", "READ", "Pasos, sueño y actividad de Apple Salud (7 días)", _health),
    Tool("trading.stats", "READ", "Estadísticas del registro manual de paper trading (simulación)", _trading),
    Tool("betting.summary", "READ", "Paper Betting: bankroll ficticio, aciertos, ROI, calibración y últimos pronósticos", _betting),
    Tool("trading.desk", "READ", "Trading Desk: cuentas virtuales, posiciones, riesgo, estadísticas y diario", _desk),
    Tool("life.opportunities", "READ", "Oportunidades de negocio, economía estimada y puntuación", _life_opps),
    Tool("life.wealth", "READ", "Patrimonio neto (real vs estimado) y ahorro real mensual", _life_wealth),
    Tool("life.learning", "READ", "Academia: nivel de dominio por materia según evaluaciones", _life_learning),
    Tool("life.simulations", "READ", "Simulaciones de liderazgo y comunicación y sus evaluaciones", _life_sims),
    Tool("life.discipline", "READ", "Hábitos, rachas, cumplimiento y compromisos incumplidos", _life_discipline),
    Tool("life.contacts", "READ", "CRM personal: seguimientos pendientes (datos privados)", _life_contacts),
    Tool("life.decisions", "READ", "Diario de decisiones y calibración de tu confianza", _life_decisions),
    Tool("life.failures", "READ", "Errores registrados, lecciones y patrones", _life_failures),
    Tool("life.goals", "READ", "Objetivos estancados", _life_goals),
    Tool("life.radar", "READ", "Radar de oportunidades (investigaciones con fuentes)", _life_radar),
    Tool("life.vision", "READ", "Tu visión de vida (Legacy)", _life_vision),
    Tool("tasks.overview", "READ", "Tareas de hoy y plan de la semana", _tasks),
    Tool("goals.snapshot", "READ", "Objetivos con su ritmo", _goals),
    Tool("calendar.upcoming", "READ", "Eventos de los próximos 14 días", _calendar),
    Tool("insights.detect", "READ", "Detecciones proactivas sobre tus datos", _insights),
    Tool("memory.search", "READ", "Busca en tu memoria lo relacionado con la petición", _memory),
    Tool("memory.stats", "READ", "Tamaño de la memoria y del grafo", _memory_stats),
    Tool("docs.search", "READ", "Busca en tus documentos (RAG) con fuentes", _docs),
    Tool("research.recent", "READ", "Investigaciones recientes y sus conclusiones", _research_recent),
    Tool("projects.list", "READ", "Proyectos activos con su avance", _projects),
    Tool("security.status", "READ", "Permisos, aprobaciones, credenciales (solo nombres) y copias", _security),
    Tool("system.diagnose", "READ", "Estado técnico de VISTAN y errores recientes", _system),
]}

# Acciones de escritura/ejecución (se invocan desde órdenes explícitas o workflows; pasan por la política)
ACTIONS = {
    "task.create": ("WRITE", "Crear una tarea"),
    "memory.save": ("WRITE", "Guardar un recuerdo"),
    "finance.record": ("WRITE", "Apuntar un gasto o ingreso (solo registro, nunca un pago)"),
    "gym.log": ("WRITE", "Registrar series de entrenamiento"),
    "meal.log": ("WRITE", "Registrar una comida"),
    "research.start": ("EXECUTE", "Investigar en internet (busca y lee webs públicas)"),
    "notify": ("WRITE", "Crear una notificación en VISTAN"),
    "backup.create": ("EXECUTE", "Hacer una copia de seguridad de la base de datos"),
    "settings.change": ("ADMIN", "Cambiar configuraciones críticas (modelos, permisos, credenciales)"),
}
