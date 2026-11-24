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


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("finance.summary", "READ", "Resumen del mes, presupuestos y evolución (dinero real)", _finance),
    Tool("finance.recent", "READ", "Últimos movimientos registrados", _finance_recent),
    Tool("gym.snapshot", "READ", "Entrenamiento: rutina de hoy, volumen, progresión y estancamientos", _gym),
    Tool("nutrition.today", "READ", "Calorías y macros de hoy, objetivos y últimos 7 días", _nutrition),
    Tool("health.week", "READ", "Pasos, sueño y actividad de Apple Salud (7 días)", _health),
    Tool("trading.stats", "READ", "Estadísticas del paper trading (simulación)", _trading),
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
    Tool("system.diagnose", "READ", "Estado técnico de ATLAS y errores recientes", _system),
]}

# Acciones de escritura/ejecución (se invocan desde órdenes explícitas o workflows; pasan por la política)
ACTIONS = {
    "task.create": ("WRITE", "Crear una tarea"),
    "memory.save": ("WRITE", "Guardar un recuerdo"),
    "finance.record": ("WRITE", "Apuntar un gasto o ingreso (solo registro, nunca un pago)"),
    "gym.log": ("WRITE", "Registrar series de entrenamiento"),
    "meal.log": ("WRITE", "Registrar una comida"),
    "research.start": ("EXECUTE", "Investigar en internet (busca y lee webs públicas)"),
    "notify": ("WRITE", "Crear una notificación en ATLAS"),
    "backup.create": ("EXECUTE", "Hacer una copia de seguridad de la base de datos"),
    "settings.change": ("ADMIN", "Cambiar configuraciones críticas (modelos, permisos, credenciales)"),
}
