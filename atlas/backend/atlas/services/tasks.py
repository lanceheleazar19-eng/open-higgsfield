"""Gestor de tareas: consultas, resúmenes, plan semanal y recordatorios."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from atlas.models import Goal, Project, Task
from atlas.models.base import utcnow
from atlas.services.activity import log_activity
from atlas.services.clock import local_to_utc_naive, utc_naive_to_local

OPEN = ("pending", "in_progress")
RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def end_of_day_utc(d: date, tz: str) -> datetime:
    return local_to_utc_naive(datetime.combine(d, time(23, 59, 59), tzinfo=ZoneInfo(tz)))


def to_dict(t: Task, tz: str, now: datetime | None = None, names: dict | None = None) -> dict:
    now = now or utcnow()
    due_local = utc_naive_to_local(t.due_at, tz) if t.due_at else None
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "priority": t.priority,
        "status": t.status,
        "category": t.category,
        "due_at": due_local.isoformat() if due_local else None,
        "due_date": due_local.date().isoformat() if due_local else None,
        "all_day": t.all_day,
        "overdue": bool(t.due_at and t.status in OPEN and t.due_at < now),
        "reminder_at": utc_naive_to_local(t.reminder_at, tz).isoformat() if t.reminder_at else None,
        "goal_id": t.goal_id,
        "goal_title": (names or {}).get(("goal", t.goal_id)),
        "project_id": t.project_id,
        "project_name": (names or {}).get(("project", t.project_id)),
        "created_at": utc_naive_to_local(t.created_at, tz).isoformat(),
        "completed_at": utc_naive_to_local(t.completed_at, tz).isoformat() if t.completed_at else None,
    }


def names_for(db: Session, tasks: list[Task]) -> dict:
    out: dict = {}
    gids = {t.goal_id for t in tasks if t.goal_id}
    pids = {t.project_id for t in tasks if t.project_id}
    if gids:
        out.update({("goal", g.id): g.title for g in db.scalars(select(Goal).where(Goal.id.in_(gids)))})
    if pids:
        out.update({("project", p.id): p.name for p in db.scalars(select(Project).where(Project.id.in_(pids)))})
    return out


def list_tasks(db: Session, status: str = "open", q: str = "", goal_id: int | None = None,
               category: str | None = None, limit: int = 500) -> list[Task]:
    stmt = select(Task)
    if status == "open":
        stmt = stmt.where(Task.status.in_(OPEN))
    elif status == "done":
        stmt = stmt.where(Task.status == "done")
    if q.strip():
        stmt = stmt.where(or_(Task.title.ilike(f"%{q.strip()}%"), Task.description.ilike(f"%{q.strip()}%")))
    if goal_id:
        stmt = stmt.where(Task.goal_id == goal_id)
    if category:
        stmt = stmt.where(Task.category == category)
    if status == "done":
        stmt = stmt.order_by(Task.completed_at.desc())
    else:
        stmt = stmt.order_by(Task.due_at.is_(None), Task.due_at, Task.id)
    rows = list(db.scalars(stmt.limit(limit)))
    if status != "done":
        rows.sort(key=lambda t: (t.due_at is None, t.due_at or datetime.max, RANK.get(t.priority, 2), t.id))
    return rows


def create_task(db: Session, **fields) -> Task:
    t = Task(**fields)
    db.add(t)
    db.flush()
    log_activity(db, "tasks", "create", f"Tarea creada: {t.title[:80]}")
    return t


def set_done(db: Session, t: Task, done: bool) -> Task:
    if done and t.status != "done":
        t.status, t.completed_at = "done", utcnow()
        log_activity(db, "tasks", "complete", f"Tarea completada: {t.title[:80]}")
    elif not done and t.status == "done":
        t.status, t.completed_at = "pending", None
        log_activity(db, "tasks", "reopen", f"Tarea reabierta: {t.title[:80]}")
    db.flush()
    return t


def find_open_task(db: Session, text: str) -> Task | None:
    """Mejor coincidencia entre las tareas abiertas para «he terminado X»."""
    import difflib

    from atlas.services.memory import normalize
    target = normalize(text)
    best, score = None, 0.0
    for t in db.scalars(select(Task).where(Task.status.in_(OPEN))):
        n = normalize(t.title)
        s = difflib.SequenceMatcher(None, target, n).ratio()
        if target and (target in n or n in target):
            s = max(s, 0.9)
        if s > score:
            best, score = t, s
    return best if score >= 0.55 else None


# --------------------------------------------------------------- resúmenes

def summary(db: Session, tz: str, period: str = "day", now_local: datetime | None = None) -> dict:
    z = ZoneInfo(tz)
    now_local = now_local or datetime.now(z)
    today = now_local.date()
    start_day = today - timedelta(days=today.weekday()) if period == "week" else today
    end_day = start_day + timedelta(days=7 if period == "week" else 1)
    s = local_to_utc_naive(datetime.combine(start_day, time.min, tzinfo=z))
    e = local_to_utc_naive(datetime.combine(end_day, time.min, tzinfo=z))
    now = local_to_utc_naive(now_local)

    completed = list(db.scalars(select(Task).where(Task.completed_at >= s, Task.completed_at < e)))
    created = db.scalar(select(func.count()).select_from(Task).where(Task.created_at >= s, Task.created_at < e)) or 0
    due_open = list(db.scalars(select(Task).where(Task.status.in_(OPEN), Task.due_at >= s, Task.due_at < e)))
    due_total = db.scalar(select(func.count()).select_from(Task).where(Task.due_at >= s, Task.due_at < e)) or 0
    overdue = db.scalar(select(func.count()).select_from(Task).where(Task.status.in_(OPEN), Task.due_at < now)) or 0
    due_done = sum(1 for t in completed if t.due_at and s <= t.due_at < e)
    return {
        "period": period,
        "from": start_day.isoformat(),
        "to": (end_day - timedelta(days=1)).isoformat(),
        "completed": len(completed),
        "completed_titles": [t.title for t in completed][:10],
        "created": created,
        "due": due_total,
        "due_open": len(due_open),
        "overdue": overdue,
        "completion_rate": round(due_done / due_total, 2) if due_total else None,
    }


# --------------------------------------------------------------- plan semanal

def plan_week(db: Session, tz: str, per_day: int = 4, now_local: datetime | None = None) -> dict:
    """Reparte las tareas abiertas en los próximos 7 días.

    - Atrasadas → hoy. Con fecha en la semana → su día (fijas).
    - Sin fecha, de prioridad crítica/alta/media → huecos libres (máx. `per_day` por día), por prioridad.
    - Prioridad baja sin fecha → «si queda tiempo».
    """
    z = ZoneInfo(tz)
    now_local = now_local or datetime.now(z)
    today = now_local.date()
    days = [today + timedelta(days=i) for i in range(7)]
    end_utc = local_to_utc_naive(datetime.combine(days[-1] + timedelta(days=1), time.min, tzinfo=z))
    now = local_to_utc_naive(now_local)
    tasks = list(db.scalars(select(Task).where(Task.status.in_(OPEN))))
    slots: dict[date, list[dict]] = {d: [] for d in days}
    later, extra = [], []

    def item(t: Task, pinned: bool) -> dict:
        return {"id": t.id, "title": t.title, "priority": t.priority, "pinned": pinned,
                "overdue": bool(t.due_at and t.due_at < now), "all_day": t.all_day,
                "time": None if t.all_day or not t.due_at else utc_naive_to_local(t.due_at, tz).strftime("%H:%M")}

    for t in sorted(tasks, key=lambda t: (RANK.get(t.priority, 2), t.due_at or datetime.max)):
        if t.due_at and t.due_at < now:
            slots[today].append(item(t, True))
        elif t.due_at and t.due_at < end_utc:
            slots[utc_naive_to_local(t.due_at, tz).date()].append(item(t, True))
        elif t.due_at:
            later.append(item(t, True))
    undated = sorted((t for t in tasks if not t.due_at), key=lambda t: (RANK.get(t.priority, 2), t.id))
    for t in undated:
        if t.priority == "low":
            extra.append(item(t, False))
            continue
        free = next((d for d in days if len(slots[d]) < per_day), None)
        if free is None:
            extra.append(item(t, False))
        else:
            slots[free].append(item(t, False))
    return {
        "days": [{"date": d.isoformat(), "tasks": slots[d], "load": len(slots[d]), "over_capacity": len(slots[d]) > per_day}
                 for d in days],
        "if_time": extra,
        "later": later[:10],
        "per_day": per_day,
    }


def apply_plan(db: Session, tz: str, assignments: list[tuple[int, date]]) -> int:
    """Fija fecha (día completo) a tareas sin fecha según el plan. No toca las que ya tienen fecha."""
    n = 0
    for task_id, d in assignments:
        t = db.get(Task, task_id)
        if t and t.status in OPEN and t.due_at is None:
            t.due_at, t.all_day = end_of_day_utc(d, tz), True
            n += 1
    if n:
        log_activity(db, "tasks", "plan", f"Semana organizada: {n} tareas programadas")
    db.flush()
    return n


# --------------------------------------------------------------- recordatorios

def due_reminders(db: Session, mark: bool = True) -> list[Task]:
    now = utcnow()
    rows = list(db.scalars(select(Task).where(Task.status.in_(OPEN), Task.reminder_at.is_not(None),
                                              Task.reminder_at <= now, Task.reminded_at.is_(None))))
    if mark:
        for t in rows:
            t.reminded_at = now
        db.flush()
    return rows
