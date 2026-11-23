"""Agregación de datos REALES para el dashboard. Sin cifras inventadas:
si no hay registros, se devuelven ceros/listas vacías y el frontend muestra
un estado vacío."""

from datetime import date, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from atlas.models import (
    ActivityLog,
    CalendarEvent,
    Project,
    Task,
    Transaction,
    WorkoutSession,
)
from atlas.services.clock import (
    local_day_bounds_utc,
    local_to_utc_naive,
    now_local,
    part_of_day,
    utc_naive_to_local,
)

OPEN_STATUSES = ("pending", "in_progress")
PRIORITY_RANK = case(
    {"critical": 0, "high": 1, "medium": 2, "low": 3}, value=Task.priority, else_=4
)


def _iso_local(dt: datetime | None, tz: str) -> str | None:
    return utc_naive_to_local(dt, tz).isoformat() if dt else None


def _tasks(db: Session, tz: str, now_utc: datetime, today_end_utc: datetime) -> dict:
    open_q = select(Task).where(Task.status.in_(OPEN_STATUSES))
    pending = db.scalar(select(func.count()).select_from(open_q.subquery())) or 0
    overdue = db.scalar(
        select(func.count()).where(Task.status.in_(OPEN_STATUSES), Task.due_at < now_utc)
    ) or 0
    due_today = db.scalar(
        select(func.count()).where(
            Task.status.in_(OPEN_STATUSES),
            Task.due_at >= now_utc,
            Task.due_at < today_end_utc,
        )
    ) or 0
    top = db.scalars(
        open_q.order_by(
            PRIORITY_RANK,
            Task.due_at.is_(None),  # con fecha primero
            Task.due_at,
            Task.id,
        ).limit(6)
    ).all()
    return {
        "pending": pending,
        "overdue": overdue,
        "due_today": due_today,
        "items": [
            {
                "id": t.id,
                "title": t.title,
                "priority": t.priority,
                "status": t.status,
                "due_at": _iso_local(t.due_at, tz),
                "all_day": t.all_day,
                "overdue": bool(t.due_at and t.due_at < now_utc),
            }
            for t in top
        ],
    }


def _events(db: Session, tz: str, now_utc: datetime) -> dict:
    # Eventos en curso o futuros
    rows = db.scalars(
        select(CalendarEvent)
        .where(
            (CalendarEvent.start_at >= now_utc)
            | ((CalendarEvent.end_at.is_not(None)) & (CalendarEvent.end_at > now_utc))
        )
        .order_by(CalendarEvent.start_at)
        .limit(5)
    ).all()
    return {
        "items": [
            {
                "id": e.id,
                "title": e.title,
                "location": e.location,
                "start_at": _iso_local(e.start_at, tz),
                "end_at": _iso_local(e.end_at, tz),
                "in_progress": e.start_at <= now_utc,
            }
            for e in rows
        ]
    }


def _sum_cents(db: Session, kind: str, start: date | None = None, end: date | None = None) -> int:
    q = select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(Transaction.kind == kind)
    if start:
        q = q.where(Transaction.occurred_on >= start)
    if end:
        q = q.where(Transaction.occurred_on < end)
    return int(db.scalar(q) or 0)


def _trading(db: Session) -> dict:
    """Resumen del paper trading (SIMULADO) para el nodo del centro de control."""
    from atlas.models import PaperTrade
    from atlas.trading.service import pnl
    closed = list(db.scalars(select(PaperTrade).where(PaperTrade.closed_at.is_not(None))))
    return {"open": db.scalar(select(func.count(PaperTrade.id)).where(PaperTrade.closed_at.is_(None))) or 0,
            "closed": len(closed), "pnl": round(sum(pnl(t) for t in closed), 2)}


def _finance(db: Session, today: date, currency: str) -> dict:
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    income = _sum_cents(db, "income", month_start, next_month)
    expense = _sum_cents(db, "expense", month_start, next_month)
    total_balance = _sum_cents(db, "income") - _sum_cents(db, "expense")
    top_cat = db.execute(
        select(Transaction.category, func.sum(Transaction.amount_cents).label("t"))
        .where(
            Transaction.kind == "expense",
            Transaction.occurred_on >= month_start,
            Transaction.occurred_on < next_month,
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount_cents).desc())
        .limit(4)
    ).all()
    has_data = db.scalar(select(func.count(Transaction.id))) or 0
    # Neto acumulado día a día en el mes (para el gráfico); solo días con datos reales
    daily = db.execute(
        select(Transaction.occurred_on,
               func.sum(case((Transaction.kind == "income", Transaction.amount_cents), else_=-Transaction.amount_cents)))
        .where(Transaction.occurred_on >= month_start, Transaction.occurred_on <= today)
        .group_by(Transaction.occurred_on).order_by(Transaction.occurred_on)
    ).all()
    acc, series = 0, []
    for d, v in daily:
        acc += int(v)
        series.append({"date": d.isoformat(), "net_cents": acc})
    from atlas.finance.service import budget_status
    return {
        "budgets": budget_status(db, month_start, next_month),
        "series": series,
        "has_data": has_data > 0,
        "currency": currency,
        "month": month_start.isoformat()[:7],
        "income_cents": income,
        "expense_cents": expense,
        "net_cents": income - expense,
        "balance_cents": total_balance,
        "top_expense_categories": [
            {"category": c or "Sin categoría", "amount_cents": int(t)} for c, t in top_cat
        ],
    }


def _fitness(db: Session, today: date) -> dict:
    week_ago = today - timedelta(days=6)
    rows = db.scalars(
        select(WorkoutSession)
        .where(WorkoutSession.performed_on >= week_ago, WorkoutSession.performed_on <= today)
        .order_by(WorkoutSession.performed_on)
    ).all()
    days = []
    for i in range(7):
        d = week_ago + timedelta(days=i)
        days.append({"date": d.isoformat(), "sessions": sum(1 for r in rows if r.performed_on == d)})
    last = db.scalars(
        select(WorkoutSession).order_by(WorkoutSession.performed_on.desc(), WorkoutSession.id.desc()).limit(1)
    ).first()
    from atlas.gym.service import routine_for_day
    r = routine_for_day(db, today)
    return {
        "today_routine": r.name if r else None,
        "sessions_7d": len(rows),
        "minutes_7d": sum(r.duration_min or 0 for r in rows),
        "days": days,
        "last_session": (
            {"date": last.performed_on.isoformat(), "routine": last.routine_name,
             "duration_min": last.duration_min}
            if last else None
        ),
    }


def _projects(db: Session) -> dict:
    open_tasks = (
        select(Task.project_id, func.count(Task.id).label("n"))
        .where(Task.status.in_(OPEN_STATUSES), Task.project_id.is_not(None))
        .group_by(Task.project_id)
        .subquery()
    )
    rows = db.execute(
        select(Project, func.coalesce(open_tasks.c.n, 0))
        .outerjoin(open_tasks, open_tasks.c.project_id == Project.id)
        .where(Project.status == "active")
        .order_by(Project.updated_at.desc())
        .limit(6)
    ).all()
    active = db.scalar(select(func.count()).where(Project.status == "active")) or 0
    return {
        "active": active,
        "items": [
            {"id": p.id, "name": p.name, "description": p.description, "open_tasks": int(n)}
            for p, n in rows
        ],
    }


def _activity(db: Session, tz: str) -> dict:
    rows = db.scalars(select(ActivityLog).order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(8)).all()
    return {
        "items": [
            {"id": a.id, "module": a.module, "action": a.action, "summary": a.summary,
             "created_at": _iso_local(a.created_at, tz)}
            for a in rows
        ]
    }


def build_dashboard(db: Session, prefs: dict, now: datetime | None = None) -> dict:
    tz = str(prefs["timezone"])
    local_now = now_local(tz) if now is None else now
    now_utc = local_to_utc_naive(local_now)
    today = local_now.date()
    _, today_end_utc = local_day_bounds_utc(today, tz)

    tasks = _tasks(db, tz, now_utc, today_end_utc)
    events = _events(db, tz, now_utc)
    fitness = _fitness(db, today)
    projects = _projects(db)

    return {
        "generated_at": local_now.isoformat(),
        "greeting": {
            "name": prefs.get("user_name") or "",
            "part_of_day": part_of_day(local_now.hour),
            "timezone": tz,
        },
        "summary": {
            "pending_tasks": tasks["pending"],
            "overdue_tasks": tasks["overdue"],
            "upcoming_events": len(events["items"]),
            "active_projects": projects["active"],
            "sessions_7d": fitness["sessions_7d"],
        },
        "tasks": tasks,
        "events": events,
        "finance": _finance(db, today, str(prefs.get("currency") or "EUR")),
        "trading": _trading(db),
        "fitness": fitness,
        "projects": projects,
        "activity": _activity(db, tz),
        "goals": _goals(db, today),
    }


def _goals(db: Session, today: date) -> dict:
    from atlas.services.goals import active_goals, metrics
    items = []
    for g in active_goals(db)[:6]:
        m = metrics(db, g, today)
        items.append({"id": g.id, "title": g.title, "unit": g.unit, "kind": g.kind, "progress": m.get("progress"),
                      "pace": m.get("pace"), "deadline": g.deadline.isoformat() if g.deadline else None,
                      "current": m.get("current"), "target": m.get("target"),
                      "required_per_week": m.get("required_per_week")})
    return {"items": items}
