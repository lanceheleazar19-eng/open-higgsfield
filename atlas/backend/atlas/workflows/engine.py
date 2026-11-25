"""Workflow Engine: secuencias de pasos (consultar, analizar, coordinar agentes, crear, notificar…),
programables, reanudables y con autorización para los pasos sensibles."""

import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.models import (Approval, Document, Goal, Memory, Project, Research, Task, Transaction, Workflow, WorkflowRun,
                          WorkoutSession)
from atlas.security.policy import needs_approval, notify, request_approval
from atlas.services.activity import log_activity

# tipo → (nivel, etiqueta, parámetros)
STEP_TYPES: dict[str, tuple[str, str, list[str]]] = {
    "daily_briefing": ("READ", "Resumen del día", []),
    "weekly_review": ("READ", "Revisión semanal", []),
    "project_analysis": ("READ", "Análisis de proyecto", ["project_id"]),
    "insights": ("READ", "Detecciones proactivas", []),
    "agent": ("READ", "Consultar a los agentes", ["prompt", "agents"]),
    "research": ("EXECUTE", "Investigar en internet", ["question"]),
    "create_task": ("WRITE", "Crear tarea", ["title"]),
    "save_memory": ("WRITE", "Guardar en memoria", ["content"]),
    "notify": ("WRITE", "Notificarme", ["title"]),
    "backup": ("EXECUTE", "Copia de seguridad", []),
}

BUILTINS = [
    {"key": "daily_briefing", "name": "Daily Briefing", "schedule": "daily 08:00", "enabled": True,
     "description": "Resumen diario de tareas, calendario, objetivos, finanzas y alertas.",
     "steps": [{"type": "daily_briefing"}, {"type": "insights"}, {"type": "notify", "params": {"title": "Daily Briefing"}}]},
    {"key": "weekly_review", "name": "Weekly Review", "schedule": "weekly 6 20:00", "enabled": True,
     "description": "Revisión del domingo: progreso, tareas, entrenos, gastos, objetivos y decisiones de la semana.",
     "steps": [{"type": "weekly_review"}, {"type": "notify", "params": {"title": "Weekly Review"}}]},
    {"key": "project_analysis", "name": "Project Analysis", "schedule": None, "enabled": True,
     "description": "Estado de un proyecto: avance, bloqueos, riesgos y próximos pasos.",
     "steps": [{"type": "project_analysis"}, {"type": "notify", "params": {"title": "Análisis de proyecto"}}]},
    {"key": "research_workflow", "name": "Research Workflow", "schedule": None, "enabled": True,
     "description": "Investigación completa con fuentes y conclusiones (te avisa al terminar).",
     "steps": [{"type": "research"}]},
]


def ensure_builtins(db: Session) -> None:
    for b in BUILTINS:
        if not db.scalar(select(Workflow).where(Workflow.key == b["key"])):
            db.add(Workflow(key=b["key"], name=b["name"], description=b["description"], steps=b["steps"],
                            schedule=b["schedule"], enabled=b["enabled"], builtin=True))
    db.commit()


# ---------- Pasos ----------
def _briefing(db: Session, prefs: dict) -> str:
    from atlas.services.alerts import build_alerts
    from atlas.services.assistant import briefing
    from atlas.services.dashboard import build_dashboard
    d = build_dashboard(db, prefs)
    d["alerts"] = build_alerts(d)
    text = briefing(d)
    try:
        from zoneinfo import ZoneInfo as _Z

        from atlas.life.service import briefing_lines
        extra = briefing_lines(db, datetime.now(_Z(str(prefs.get("timezone") or "Europe/Madrid"))).date())
        if extra:
            text += "\n\nLIFE OS:\n" + "\n".join(extra)
    except Exception:  # noqa: BLE001 - el briefing base nunca debe fallar por LIFE OS
        pass
    return text


def _eur(c: int) -> str:
    return f"{c / 100:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def weekly_review(db: Session, tz: str) -> str:
    now = datetime.utcnow()
    since = now - timedelta(days=7)
    today = datetime.now(ZoneInfo(tz)).date()
    done = db.scalar(select(func.count(Task.id)).where(Task.completed_at >= since)) or 0
    created = db.scalar(select(func.count(Task.id)).where(Task.created_at >= since)) or 0
    overdue = db.scalar(select(func.count(Task.id)).where(Task.status == "pending", Task.due_at < now)) or 0
    workouts = db.scalar(select(func.count(WorkoutSession.id)).where(WorkoutSession.performed_on > today - timedelta(days=7))) or 0
    spent = db.scalar(select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
        Transaction.kind == "expense", Transaction.occurred_on > today - timedelta(days=7))) or 0
    earned = db.scalar(select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
        Transaction.kind == "income", Transaction.occurred_on > today - timedelta(days=7))) or 0
    decisions = [m.content for m in db.scalars(select(Memory).where(Memory.kind == "decision", Memory.created_at >= since).limit(5))]
    research = [r.question for r in db.scalars(select(Research).where(Research.status == "done", Research.updated_at >= since).limit(5))]
    from atlas.services.goals import snapshot
    goals = snapshot(db, today)
    lines = [f"Semana hasta el {today:%d/%m}:",
             f"• Tareas: {done} completadas, {created} nuevas, {overdue} atrasadas ahora.",
             f"• Entrenamiento: {workouts} sesión(es) registradas (tu rutina es de 4 días).",
             f"• Dinero real: {_eur(int(spent))} de gastos y {_eur(int(earned))} de ingresos registrados."]
    if goals:
        behind = [g["title"] for g in goals if g.get("pace") in ("behind", "overdue")]
        lines.append(f"• Objetivos activos: {len(goals)}" + (f"; van por detrás: {', '.join(behind)}." if behind else "; ninguno va por detrás."))
    if decisions:
        lines.append("• Decisiones guardadas: " + "; ".join(decisions))
    if research:
        lines.append("• Investigaciones terminadas: " + "; ".join(research))
    from atlas.life.service import week_lines
    life = week_lines(db, today)
    if life:
        lines.append("LIFE OS:")
        lines += life
    if not any([done, created, workouts, spent, earned, goals, decisions, life]):
        lines.append("No hay actividad registrada esta semana.")
    return "\n".join(lines)


def project_analysis(db: Session, project_id: int | None, prefs: dict) -> str:
    p = db.get(Project, project_id) if project_id else None
    if not p:
        raise ValueError("Elige un proyecto para analizar")
    now = datetime.utcnow()
    tasks = list(db.scalars(select(Task).where(Task.project_id == p.id)))
    open_t = [t for t in tasks if t.status == "pending"]
    done_t = [t for t in tasks if t.status == "done"]
    late = [t for t in open_t if t.due_at and t.due_at < now]
    notes = db.scalar(select(func.count(Memory.id)).where(Memory.project_id == p.id)) or 0
    docs = db.scalar(select(func.count(Document.id)).where(Document.project_id == p.id)) or 0
    last = max(filter(None, [p.updated_at, *[t.updated_at for t in tasks]]), default=p.created_at)
    pct = round(100 * len(done_t) / len(tasks)) if tasks else None
    prio = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    nxt = sorted(open_t, key=lambda t: (prio.get(t.priority, 2), t.due_at or datetime.max))[:3]
    risks = []
    if late:
        risks.append(f"{len(late)} tarea(s) atrasada(s): " + ", ".join(t.title for t in late[:3]))
    if not open_t:
        risks.append("No hay ninguna tarea abierta: falta definir el siguiente paso.")
    if (now - last).days >= 14:
        risks.append(f"Sin actividad desde hace {(now - last).days} días.")
    lines = [f"Proyecto «{p.name}» ({p.status})", p.description or "",
             f"• Avance: {len(done_t)}/{len(tasks)} tareas hechas" + (f" ({pct} %)" if pct is not None else "") + ".",
             f"• Notas: {notes} · Documentos: {docs} · Última actividad: {last:%d/%m/%Y}.",
             "• Riesgos/bloqueos: " + ("; ".join(risks) if risks else "ninguno detectado con los datos registrados."),
             "• Próximos pasos: " + ("; ".join(t.title for t in nxt) if nxt else "crea la primera tarea del proyecto.")]
    return "\n".join(x for x in lines if x)


def _exec_step(db: Session, run: WorkflowRun, step: dict, prefs: dict, tz: str, outputs: list[str]) -> str:
    t, params = step["type"], {**(step.get("params") or {}), **{k: v for k, v in run.params.items() if k in STEP_TYPES[step["type"]][2]}}
    if t == "daily_briefing":
        return _briefing(db, prefs)
    if t == "weekly_review":
        return weekly_review(db, tz)
    if t == "project_analysis":
        return project_analysis(db, int(params["project_id"]) if params.get("project_id") else None, prefs)
    if t == "insights":
        from atlas.services.insights import detect
        ins = detect(db, prefs)
        return "\n".join(f"• {i['title']}: {i['recommendation']}" for i in ins) or "Sin detecciones nuevas."
    if t == "agent":
        from atlas.agents.core import answer
        agents = params.get("agents") or None
        if isinstance(agents, str):
            agents = [a.strip() for a in agents.split(",") if a.strip()]
        return answer(db, str(params.get("prompt") or "Resume mi situación actual"), prefs, tz, agents, source="workflow")["result"] or ""
    if t == "research":
        q = str(params.get("question") or "").strip()
        if len(q) < 4:
            raise ValueError("Falta la pregunta de investigación")
        from atlas.research import engine
        r = Research(question=q, status="queued", state={})
        db.add(r)
        db.flush()
        db.commit()
        engine.start(r.id)
        return f"Investigación #{r.id} iniciada: «{q}». Te avisaré al terminar."
    if t == "create_task":
        from atlas.services.tasks import create_task
        title = str(params.get("title") or "").strip()
        if not title:
            raise ValueError("Falta el título de la tarea")
        tk = create_task(db, title=title, priority=params.get("priority", "medium"), category=params.get("category"))
        return f"Tarea creada: «{tk.title}»."
    if t == "save_memory":
        from atlas.services import memory as mem
        content = str(params.get("content") or "\n".join(outputs)).strip()[:2000]
        m, created = mem.remember(db, content, kind=params.get("kind", "note"), source="manual")
        return ("Guardado en memoria." if created else "Ya estaba en memoria.")
    if t == "notify":
        body = "\n\n".join(o for o in outputs if o)[:4000] or str(params.get("body") or "")
        notify(db, str(params.get("title") or "VISTAN"), body, link=f"/workflows?run={run.id}")
        return "Notificación creada."
    if t == "backup":
        from atlas.services.backup import backup_db
        p = backup_db("workflow")
        return f"Copia guardada: {p.name}" if p else "No hay base de datos SQLite que copiar."
    raise ValueError(f"Paso desconocido: {t}")


def execute(db: Session, run: WorkflowRun) -> WorkflowRun:
    """Ejecuta desde `run.next_step`. Se detiene si un paso necesita autorización."""
    from atlas.services.preferences import get_prefs
    prefs = get_prefs(db)
    tz = str(prefs["timezone"])
    wf = db.get(Workflow, run.workflow_id)
    steps = wf.steps or []
    log = list(run.log or [])
    outputs = [e.get("output", "") for e in log if e.get("ok") and e.get("type") not in ("notify",)]
    approved = set(run.params.get("_approved", []))
    run.status = "running"
    while run.next_step < len(steps):
        i = run.next_step
        step = steps[i]
        level = STEP_TYPES.get(step.get("type"), ("ADMIN",))[0]
        if level != "READ" and needs_approval(level, prefs) and i not in approved:
            a = request_approval(db, f"workflow.{step['type']}", level, f"«{wf.name}» quiere: {STEP_TYPES[step['type']][1]}",
                                 {"step": i, "params": step.get("params") or {}}, workflow_run_id=run.id)
            run.status = "awaiting_approval"
            log.append({"step": i, "type": step["type"], "level": level, "ok": None, "output": f"Esperando autorización (#{a.id})"})
            run.log = log
            db.commit()
            return run
        t0 = time.perf_counter()
        try:
            out = _exec_step(db, run, step, prefs, tz, outputs)
            ok = True
        except Exception as exc:  # noqa: BLE001
            out, ok = f"Error: {exc}", False
        log.append({"step": i, "type": step["type"], "level": level, "ok": ok, "output": out,
                    "ms": int((time.perf_counter() - t0) * 1000)})
        run.log = log
        if not ok:
            run.status, run.output, run.finished_at = "error", out, datetime.utcnow()
            db.commit()
            return run
        if step["type"] != "notify":
            outputs.append(out)
        run.next_step = i + 1
        db.commit()
    run.status = "done"
    run.output = "\n\n".join(o for o in outputs if o)
    run.finished_at = datetime.utcnow()
    wf.last_run_at = datetime.utcnow()
    log_activity(db, "workflows", "run", f"{wf.name}: completado")
    db.commit()
    return run


def start(db: Session, wf: Workflow, params: dict | None = None, trigger: str = "manual") -> WorkflowRun:
    run = WorkflowRun(workflow_id=wf.id, params=params or {}, trigger=trigger, log=[])
    db.add(run)
    db.flush()
    wf.last_run_at = datetime.utcnow()
    return execute(db, run)


def resume_after_approval(db: Session, a: Approval) -> None:
    run = db.get(WorkflowRun, a.workflow_run_id) if a.workflow_run_id else None
    if not run or run.status != "awaiting_approval":
        return
    step = a.payload.get("step")
    if a.status == "approved":
        run.params = {**run.params, "_approved": [*run.params.get("_approved", []), step]}
        run.log = [e for e in run.log if not (e.get("step") == step and e.get("ok") is None)]
        execute(db, run)
    else:
        run.status, run.finished_at = "error", datetime.utcnow()
        run.output = "Cancelado: no autorizaste un paso sensible."
        db.commit()


# ---------- Programación ----------
def due(schedule: str | None, last: datetime | None, now_local: datetime, tz: ZoneInfo) -> bool:
    """«daily HH:MM» o «weekly D HH:MM» (D: 0=lunes…6=domingo). `last` en UTC naive."""
    if not schedule:
        return False
    parts = schedule.split()
    try:
        if parts[0] == "daily":
            h, m = map(int, parts[1].split(":"))
            slot = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
            if slot > now_local:
                slot -= timedelta(days=1)
        elif parts[0] == "weekly":
            d, (h, m) = int(parts[1]), map(int, parts[2].split(":"))
            slot = now_local.replace(hour=h, minute=m, second=0, microsecond=0) - timedelta(days=(now_local.weekday() - d) % 7)
            if slot > now_local:
                slot -= timedelta(days=7)
        else:
            return False
    except (ValueError, IndexError):
        return False
    if now_local - slot > timedelta(hours=12):
        return False  # si el Mac estuvo apagado, no recuperamos ejecuciones muy antiguas
    slot_utc = slot.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return last is None or last < slot_utc


def tick() -> list[int]:
    """Lanza los workflows programados que tocan ahora. Devuelve los ids de las ejecuciones."""
    from atlas.db import session_scope
    from atlas.services.preferences import get_prefs
    ran = []
    with session_scope() as db:
        tz = ZoneInfo(str(get_prefs(db)["timezone"]))
        now_local = datetime.now(tz)
        for wf in db.scalars(select(Workflow).where(Workflow.enabled.is_(True), Workflow.schedule.is_not(None))):
            if due(wf.schedule, wf.last_run_at, now_local, tz):
                ran.append(start(db, wf, trigger="schedule").id)
    return ran


def maintenance() -> None:
    """Tareas del sistema: copia de seguridad diaria automática."""
    from atlas.services.backup import backup_db, list_backups
    bk = list_backups()
    if not bk or datetime.fromisoformat(bk[0]["created_at"]) < datetime.now() - timedelta(hours=24):
        backup_db("diaria")


def run_dict(r: WorkflowRun, wf: Workflow | None = None) -> dict:
    return {"id": r.id, "workflow_id": r.workflow_id, "workflow": wf.name if wf else None, "status": r.status,
            "trigger": r.trigger, "params": {k: v for k, v in r.params.items() if not k.startswith("_")},
            "log": r.log, "output": r.output, "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None}


def wf_dict(w: Workflow) -> dict:
    return {"id": w.id, "key": w.key, "name": w.name, "description": w.description, "steps": w.steps,
            "schedule": w.schedule, "enabled": w.enabled, "builtin": w.builtin,
            "last_run_at": w.last_run_at.isoformat() if w.last_run_at else None,
            "needs": sorted({p for s in w.steps for p in STEP_TYPES.get(s.get("type"), ("", "", []))[2]
                             if p in ("project_id", "question") and not (s.get("params") or {}).get(p)})}


def run_in_thread(fn, *args) -> None:  # noqa: ANN001
    threading.Thread(target=fn, args=args, daemon=True).start()
