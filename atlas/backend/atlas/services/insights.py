"""Inteligencia proactiva: reglas sobre TUS datos que detectan algo útil y explican qué, por qué,
con qué datos y qué recomiendan. Nada se inventa: sin datos suficientes, la regla no dice nada."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.models import (CalendarEvent, Document, Goal, GoalProgress, Memory, Project, Routine, Task, Transaction,
                          WorkoutSession)

RULES = {
    "overdue_tasks": "Tareas atrasadas",
    "upcoming": "Fechas importantes próximas",
    "stalled_projects": "Proyectos estancados",
    "stalled_goals": "Objetivos sin progreso",
    "unusual_spending": "Gastos inusuales",
    "training_gap": "Pausa en el entrenamiento",
}


def config(prefs: dict) -> dict:
    c = prefs.get("proactive") or {}
    return {"enabled": c.get("enabled", True), "rules": {k: (c.get("rules") or {}).get(k, True) for k in RULES}}


def _eur(c: int) -> str:
    return f"{c / 100:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def detect(db: Session, prefs: dict) -> list[dict]:
    cfg = config(prefs)
    if not cfg["enabled"]:
        return []
    tz = ZoneInfo(str(prefs["timezone"]))
    now = datetime.utcnow()
    today = datetime.now(tz).date()
    on = cfg["rules"]
    out: list[dict] = []

    if on["overdue_tasks"]:
        overdue = list(db.scalars(select(Task).where(Task.status == "pending", Task.due_at.is_not(None), Task.due_at < now)
                                  .order_by(Task.due_at).limit(20)))
        if overdue:
            oldest = overdue[0]
            days = (now - oldest.due_at).days
            out.append({"id": f"overdue_tasks:{len(overdue)}:{oldest.id}", "rule": "overdue_tasks", "level": "warning",
                        "module": "tasks", "link": "/tasks", "title": f"{len(overdue)} tarea(s) atrasada(s)",
                        "what": f"La más antigua es «{oldest.title}», vencida hace {days} día(s).",
                        "why": "Las tareas atrasadas se acumulan y bloquean tu planificación de la semana.",
                        "data": f"{len(overdue)} tareas pendientes con fecha anterior a hoy.",
                        "recommendation": "Haz hoy la más importante y reprograma o elimina las que ya no tengan sentido."})

    if on["upcoming"]:
        soon = list(db.scalars(select(Goal).where(Goal.status == "active", Goal.deadline.is_not(None),
                                                  Goal.deadline >= today, Goal.deadline <= today + timedelta(days=14))))
        for g in soon:
            out.append({"id": f"upcoming:goal:{g.id}:{g.deadline}", "rule": "upcoming", "level": "info", "module": "goals",
                        "link": "/tasks", "title": f"Fecha límite de «{g.title}» en {(g.deadline - today).days} días",
                        "what": f"El objetivo vence el {g.deadline:%d/%m}. Valor actual: {g.current_value:g}"
                                + (f" de {g.target_value:g}" if g.target_value is not None else "") + ".",
                        "why": "Quedan menos de dos semanas para la fecha que te pusiste.",
                        "data": "Fecha límite y progreso registrados del objetivo.",
                        "recommendation": "Revisa si llegas o ajusta la fecha antes de que venza."})
        ev = list(db.scalars(select(CalendarEvent).where(CalendarEvent.start_at >= now,
                                                         CalendarEvent.start_at <= now + timedelta(hours=36))
                             .order_by(CalendarEvent.start_at).limit(3)))
        if ev:
            out.append({"id": f"upcoming:events:{'-'.join(str(e.id) for e in ev)}", "rule": "upcoming", "level": "info",
                        "module": "calendar", "link": "/calendar", "title": f"{len(ev)} evento(s) en las próximas 36 h",
                        "what": "; ".join(f"{e.title} ({e.start_at.replace(tzinfo=ZoneInfo('UTC')).astimezone(tz):%a %H:%M})"
                                          for e in ev),
                        "why": "Para que puedas prepararlos con tiempo.", "data": "Tu calendario sincronizado.",
                        "recommendation": "Revisa si necesitas preparar algo o bloquear tiempo antes."})

    if on["stalled_projects"]:
        for p in db.scalars(select(Project).where(Project.status == "active")):
            last = max(filter(None, [
                p.updated_at, p.created_at,
                db.scalar(select(func.max(Task.updated_at)).where(Task.project_id == p.id)),
                db.scalar(select(func.max(Memory.updated_at)).where(Memory.project_id == p.id)),
                db.scalar(select(func.max(Document.created_at)).where(Document.project_id == p.id)),
            ]))
            idle = (now - last).days
            if idle >= 14:
                open_t = db.scalar(select(func.count(Task.id)).where(Task.project_id == p.id, Task.status == "pending")) or 0
                out.append({"id": f"stalled_projects:{p.id}:{last.date()}", "rule": "stalled_projects", "level": "info",
                            "module": "projects", "link": f"/projects?id={p.id}", "title": f"«{p.name}» lleva {idle} días sin actividad",
                            "what": f"Sin cambios en tareas, notas ni documentos desde el {last:%d/%m}. Tareas abiertas: {open_t}.",
                            "why": "Un proyecto activo sin movimiento suele estar bloqueado o ya no ser prioritario.",
                            "data": "Última modificación de sus tareas, notas y documentos.",
                            "recommendation": "Define el siguiente paso concreto o márcalo como pausado."})

    if on["stalled_goals"]:
        for g in db.scalars(select(Goal).where(Goal.status == "active", Goal.auto_metric.is_(None))):
            last = db.scalar(select(func.max(GoalProgress.recorded_at)).where(GoalProgress.goal_id == g.id)) or g.created_at
            if (now - last).days >= 21:
                out.append({"id": f"stalled_goals:{g.id}:{last.date()}", "rule": "stalled_goals", "level": "info",
                            "module": "goals", "link": "/tasks", "title": f"Sin progreso en «{g.title}» desde hace {(now - last).days} días",
                            "what": f"Último registro: {last:%d/%m}.", "why": "Lo que no se mide no avanza.",
                            "data": "Historial de progreso del objetivo.",
                            "recommendation": "Registra dónde estás o crea una tarea pequeña que lo haga avanzar esta semana."})

    if on["unusual_spending"]:
        m0 = today.replace(day=1)
        prev = [(m0 - timedelta(days=1)).replace(day=1)]
        for _ in range(2):
            prev.append((prev[-1] - timedelta(days=1)).replace(day=1))

        def spent(start: date, end: date) -> dict:
            return dict(db.execute(select(Transaction.category, func.sum(Transaction.amount_cents)).where(
                Transaction.kind == "expense", Transaction.occurred_on >= start, Transaction.occurred_on < end)
                .group_by(Transaction.category)).all())
        cur = spent(m0, today + timedelta(days=1))
        hist = [spent(prev[i], prev[i - 1] if i else m0) for i in range(3)]
        for cat, c in cur.items():
            past = [h.get(cat, 0) or 0 for h in hist]
            months_with = [x for x in past if x]
            if len(months_with) < 2:
                continue  # sin historial suficiente no se compara
            avg = sum(past) / 3
            if c >= 2000 and c > 1.5 * avg:
                out.append({"id": f"unusual_spending:{cat}:{m0}:{c // 1000}", "rule": "unusual_spending", "level": "warning",
                            "module": "finance", "link": "/finance", "title": f"Gasto alto en {cat or 'otros'} este mes",
                            "what": f"Llevas {_eur(int(c))}; tu media de los 3 meses anteriores es {_eur(int(avg))}.",
                            "why": f"Es un {round(100 * (c / avg - 1)) if avg else 100} % más de lo habitual.",
                            "data": "Tus gastos registrados por categoría.",
                            "recommendation": "Revisa los movimientos de esta categoría o ponle un presupuesto."})

    if on["training_gap"] and db.scalar(select(func.count(Routine.id))):
        last = db.scalar(select(func.max(WorkoutSession.performed_on)))
        if last and (today - last).days >= 6:
            out.append({"id": f"training_gap:{last}", "rule": "training_gap", "level": "info", "module": "gym", "link": "/gym",
                        "title": f"{(today - last).days} días sin entrenar", "what": f"Último entreno registrado: {last:%d/%m}.",
                        "why": "Para ganar volumen necesitas constancia (tu rutina es de 4 días).",
                        "data": "Tus sesiones registradas en Gimnasio.",
                        "recommendation": "Mira qué te toca hoy y registra la sesión al terminar."})

    dismissed = prefs.get("insights_dismissed") or {}
    return [i for i in out if i["id"] not in dismissed]
