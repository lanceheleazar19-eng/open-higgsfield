from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from atlas.api.deps import DB
from atlas.models import Goal, Task
from atlas.models.domain import TASK_PRIORITIES
from atlas.services import tasks as svc
from atlas.services.clock import local_to_utc_naive
from atlas.services.nlp import parse_task_text
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
PRIO = "^(" + "|".join(TASK_PRIORITIES) + ")$"


def _tz(db) -> str:  # noqa: ANN001
    return str(get_prefs(db)["timezone"])


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        raise HTTPException(422, "Las fechas deben incluir zona horaria")
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    priority: str = Field(default="medium", pattern=PRIO)
    category: str | None = Field(default=None, max_length=64)
    due_at: datetime | None = None  # con hora
    due_date: date | None = None  # día completo
    reminder_at: datetime | None = None
    goal_id: int | None = None
    project_id: int | None = None

    @field_validator("title", "category")
    @classmethod
    def strip(cls, v: str | None) -> str | None:
        return v.strip() or None if v is not None else v


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    priority: str | None = Field(default=None, pattern=PRIO)
    category: str | None = Field(default=None, max_length=64)
    due_at: datetime | None = None
    due_date: date | None = None
    reminder_at: datetime | None = None
    goal_id: int | None = None
    project_id: int | None = None


def _due(db, due_at: datetime | None, due_date: date | None) -> tuple[datetime | None, bool]:  # noqa: ANN001
    if due_date:
        return svc.end_of_day_utc(due_date, _tz(db)), True
    return _utc(due_at), False


def _check_goal(db, goal_id: int | None) -> None:  # noqa: ANN001
    if goal_id and not db.get(Goal, goal_id):
        raise HTTPException(422, "Objetivo inexistente")


def _out(db, t: Task) -> dict:  # noqa: ANN001
    return svc.to_dict(t, _tz(db), names=svc.names_for(db, [t]))


@router.get("")
def list_tasks(db: DB, status: str = "open", q: str = "", goal_id: int | None = None, category: str | None = None) -> dict:
    rows = svc.list_tasks(db, status=status, q=q, goal_id=goal_id, category=category)
    names = svc.names_for(db, rows)
    tz = _tz(db)
    cats = sorted({c for c in (t.category for t in svc.list_tasks(db, status="all")) if c})
    return {"items": [svc.to_dict(t, tz, names=names) for t in rows], "categories": cats}


@router.post("", status_code=201)
def create(body: TaskIn, db: DB) -> dict:
    _check_goal(db, body.goal_id)
    due, all_day = _due(db, body.due_at, body.due_date)
    t = svc.create_task(db, title=body.title, description=body.description, priority=body.priority,
                        category=body.category, due_at=due, all_day=all_day, reminder_at=_utc(body.reminder_at),
                        goal_id=body.goal_id, project_id=body.project_id)
    db.commit()
    return _out(db, t)


class QuickIn(BaseModel):
    text: str = Field(min_length=2, max_length=500)


def _parsed(db, text: str) -> dict:  # noqa: ANN001
    tz = _tz(db)
    now_local = datetime.now(ZoneInfo(tz)).replace(tzinfo=None)
    p = parse_task_text(text, now_local)
    due_utc = local_to_utc_naive(p.due.replace(tzinfo=ZoneInfo(tz))) if p.due else None
    return {"title": p.title, "priority": p.priority, "category": p.category, "all_day": p.all_day,
            "due_local": p.due.isoformat() if p.due else None, "_due_utc": due_utc}


@router.post("/parse")
def parse(body: QuickIn, db: DB) -> dict:
    """Vista previa de cómo se interpretará una tarea escrita en lenguaje natural."""
    out = _parsed(db, body.text)
    out.pop("_due_utc")
    return out


@router.post("/quick", status_code=201)
def quick(body: QuickIn, db: DB) -> dict:
    p = _parsed(db, body.text)
    t = svc.create_task(db, title=p["title"], priority=p["priority"], category=p["category"],
                        due_at=p["_due_utc"], all_day=p["all_day"],
                        reminder_at=p["_due_utc"] if p["_due_utc"] and not p["all_day"] else None)
    db.commit()
    return _out(db, t)


@router.patch("/{task_id}")
def patch(task_id: int, body: TaskPatch, db: DB) -> dict:
    t = db.get(Task, task_id)
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    data = body.model_dump(exclude_unset=True)
    if "goal_id" in data:
        _check_goal(db, data["goal_id"])
    if "due_date" in data or "due_at" in data:
        t.due_at, t.all_day = _due(db, data.pop("due_at", None), data.pop("due_date", None))
    if "reminder_at" in data:
        t.reminder_at, t.reminded_at = _utc(data.pop("reminder_at")), None
    for k, v in data.items():
        setattr(t, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    return _out(db, t)


@router.post("/{task_id}/complete")
def complete(task_id: int, db: DB) -> dict:
    t = db.get(Task, task_id)
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    svc.set_done(db, t, True)
    db.commit()
    return _out(db, t)


@router.post("/{task_id}/reopen")
def reopen(task_id: int, db: DB) -> dict:
    t = db.get(Task, task_id)
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    svc.set_done(db, t, False)
    db.commit()
    return _out(db, t)


@router.delete("/{task_id}", status_code=204)
def delete(task_id: int, db: DB) -> None:
    t = db.get(Task, task_id)
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    from atlas.services.activity import log_activity
    log_activity(db, "tasks", "delete", f"Tarea eliminada: {t.title[:80]}")
    db.delete(t)
    db.commit()


@router.get("/summary")
def get_summary(db: DB, period: str = "day") -> dict:
    if period not in ("day", "week"):
        raise HTTPException(422, "period debe ser day o week")
    return svc.summary(db, _tz(db), period)


@router.get("/plan")
def get_plan(db: DB, per_day: int = 4) -> dict:
    return svc.plan_week(db, _tz(db), per_day=max(1, min(per_day, 12)))


class Assignment(BaseModel):
    task_id: int
    date: date


class ApplyIn(BaseModel):
    assignments: list[Assignment] = Field(max_length=200)


@router.post("/plan/apply")
def apply(body: ApplyIn, db: DB) -> dict:
    n = svc.apply_plan(db, _tz(db), [(a.task_id, a.date) for a in body.assignments])
    db.commit()
    return {"scheduled": n}


@router.get("/reminders/due")
def reminders(db: DB) -> dict:
    """Recordatorios vencidos aún no avisados; los marca como avisados."""
    rows = svc.due_reminders(db)
    db.commit()
    tz = _tz(db)
    return {"items": [svc.to_dict(t, tz) for t in rows]}
