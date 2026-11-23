"""Objetivos medibles: progreso, ritmo, necesidad semanal y proyección."""

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.models import Goal, GoalProgress, Task
from atlas.models.base import utcnow
from atlas.services.activity import log_activity
from atlas.services.clock import utc_naive_to_local

PACE_ES = {"ahead": "adelantado", "on_track": "en ritmo", "behind": "por detrás", "overdue": "fuera de plazo",
           "achieved": "conseguido", "no_deadline": "sin fecha límite", "not_started": "sin progreso aún"}


def _fmt(v: float) -> float:
    return round(v, 2)


def metrics(db: Session, g: Goal, today: date) -> dict:
    """Cálculos reales a partir de los valores registrados (sin estimaciones inventadas)."""
    if g.kind == "milestones":
        total = db.scalar(select(func.count()).select_from(Task).where(Task.goal_id == g.id)) or 0
        done = db.scalar(select(func.count()).select_from(Task).where(Task.goal_id == g.id, Task.status == "done")) or 0
        start, target, current = 0.0, float(total), float(done)
    else:
        start, target, current = g.start_value or 0.0, g.target_value, g.current_value or 0.0
    span = (target - start) if target is not None else None
    if span:
        pct = max(0.0, min(1.0, (current - start) / span))
    elif target is not None:
        pct = 1.0 if current == target and (g.kind != "milestones" or target > 0) else 0.0
    else:
        pct = None

    elapsed = max(0, (today - g.start_date).days)
    out: dict = {"progress": _fmt(pct) if pct is not None else None, "current": current, "target": target,
                 "start": start, "elapsed_days": elapsed}
    if g.status == "achieved" or (pct is not None and pct >= 1):
        out.update(pace="achieved")
        return out
    remaining = (target - current) if target is not None else None
    out["remaining"] = _fmt(remaining) if remaining is not None else None

    # Ritmo real: desde el inicio (valor inicial) hasta el último registro
    if g.kind == "numeric" and elapsed > 0 and current != start:
        rate = (current - start) / elapsed  # por día
        out["rate_per_week"] = _fmt(rate * 7)
        if remaining is not None and rate != 0 and (remaining / rate) > 0:
            out["projected_date"] = (today + timedelta(days=round(remaining / rate))).isoformat()
    elif g.kind == "milestones" and elapsed > 0 and current > 0 and remaining:
        rate = current / elapsed
        out["rate_per_week"] = _fmt(rate * 7)
        out["projected_date"] = (today + timedelta(days=round(remaining / rate))).isoformat()

    if not g.deadline:
        out["pace"] = "no_deadline" if pct else "not_started"
        return out
    days_left = (g.deadline - today).days
    out["days_left"] = days_left
    if days_left < 0:
        out["pace"] = "overdue"
        return out
    total_days = max(1, (g.deadline - g.start_date).days)
    expected = min(1.0, elapsed / total_days)
    out["expected_progress"] = _fmt(expected)
    if remaining is not None:
        out["required_per_week"] = _fmt(remaining / max(days_left / 7, 1 / 7))
    if pct is None:
        out["pace"] = "not_started"
    elif pct - expected > 0.05:
        out["pace"] = "ahead"
    elif expected - pct > 0.05:
        out["pace"] = "behind"
    else:
        out["pace"] = "on_track"
    return out


def to_dict(db: Session, g: Goal, today: date, tz: str) -> dict:
    tasks_total = db.scalar(select(func.count()).select_from(Task).where(Task.goal_id == g.id)) or 0
    tasks_done = db.scalar(select(func.count()).select_from(Task).where(Task.goal_id == g.id, Task.status == "done")) or 0
    return {
        "id": g.id, "title": g.title, "description": g.description, "area": g.area, "kind": g.kind, "unit": g.unit,
        "start_value": g.start_value, "target_value": g.target_value, "current_value": g.current_value,
        "start_date": g.start_date.isoformat(), "deadline": g.deadline.isoformat() if g.deadline else None,
        "status": g.status, "tasks_total": tasks_total, "tasks_done": tasks_done,
        "achieved_at": utc_naive_to_local(g.achieved_at, tz).isoformat() if g.achieved_at else None,
        "auto_metric": g.auto_metric, "auto_exercise_id": g.auto_exercise_id,
        "metrics": metrics(db, g, today),
    }


def history(db: Session, g: Goal, tz: str) -> list[dict]:
    rows = db.scalars(select(GoalProgress).where(GoalProgress.goal_id == g.id).order_by(GoalProgress.recorded_at))
    return [{"id": r.id, "value": r.value, "note": r.note,
             "recorded_at": utc_naive_to_local(r.recorded_at, tz).isoformat()} for r in rows]


def create_goal(db: Session, **fields) -> Goal:
    g = Goal(**fields)
    if g.current_value is None:
        g.current_value = g.start_value or 0
    db.add(g)
    db.flush()
    db.add(GoalProgress(goal_id=g.id, value=g.current_value, note="Inicio"))
    log_activity(db, "goals", "create", f"Objetivo creado: {g.title[:80]}")
    db.flush()
    return g


def record_progress(db: Session, g: Goal, value: float, note: str | None = None) -> Goal:
    g.current_value = value
    db.add(GoalProgress(goal_id=g.id, value=value, note=note))
    reached = g.target_value is not None and (
        (g.target_value >= g.start_value and value >= g.target_value)
        or (g.target_value < g.start_value and value <= g.target_value))
    if reached and g.status == "active":
        g.status, g.achieved_at = "achieved", utcnow()
        log_activity(db, "goals", "achieved", f"🎯 Objetivo conseguido: {g.title[:80]}")
    else:
        log_activity(db, "goals", "progress", f"Progreso en «{g.title[:60]}»: {value:g}{(' ' + g.unit) if g.unit else ''}")
    db.flush()
    return g


def active_goals(db: Session) -> list[Goal]:
    return list(db.scalars(select(Goal).where(Goal.status == "active").order_by(Goal.deadline.is_(None), Goal.deadline)))


def snapshot(db: Session, today: date) -> list[dict]:
    """Resumen compacto para el cerebro de ATLAS."""
    out = []
    for g in active_goals(db):
        m = metrics(db, g, today)
        unit = f" {g.unit}" if g.unit else ""
        item = {"objetivo": g.title, "area": g.area,
                "progreso": f"{round((m['progress'] or 0) * 100)}%" if m.get("progress") is not None else "sin medir",
                "ritmo": PACE_ES.get(m.get("pace", ""), m.get("pace"))}
        if g.kind == "numeric":
            item["actual"] = f"{g.current_value:g}{unit}"
            item["meta"] = f"{g.target_value:g}{unit}" if g.target_value is not None else None
        else:
            item["hitos"] = f"{int(m['current'])}/{int(m['target'] or 0)} tareas"
        if g.deadline:
            item["fecha_limite"] = g.deadline.isoformat()
            item["dias_restantes"] = m.get("days_left")
        if m.get("required_per_week") is not None:
            item["necesario_por_semana"] = f"{abs(m['required_per_week']):g}{unit}"
        if m.get("rate_per_week") is not None:
            item["ritmo_real_por_semana"] = f"{abs(m['rate_per_week']):g}{unit}"
        if m.get("projected_date"):
            item["fecha_proyectada_al_ritmo_actual"] = m["projected_date"]
        out.append(item)
    return out
