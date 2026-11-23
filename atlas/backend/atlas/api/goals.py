from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from atlas.api.deps import DB
from atlas.models import Goal
from atlas.services import goals as svc
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/goals", tags=["goals"])


def _ctx(db) -> tuple[str, date]:  # noqa: ANN001
    tz = str(get_prefs(db)["timezone"])
    return tz, datetime.now(ZoneInfo(tz)).date()


class GoalIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    area: str | None = Field(default=None, max_length=32)
    kind: str = Field(default="numeric", pattern="^(numeric|milestones)$")
    unit: str | None = Field(default=None, max_length=16)
    start_value: float = 0
    target_value: float | None = None
    current_value: float | None = None
    start_date: date | None = None
    deadline: date | None = None

    @model_validator(mode="after")
    def check(self):
        if self.kind == "numeric":
            if self.target_value is None:
                raise ValueError("Un objetivo numérico necesita un valor meta")
            if self.target_value == self.start_value:
                raise ValueError("La meta debe ser distinta del valor inicial")
        if self.deadline and self.start_date and self.deadline <= self.start_date:
            raise ValueError("La fecha límite debe ser posterior al inicio")
        return self


class GoalPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    area: str | None = Field(default=None, max_length=32)
    unit: str | None = Field(default=None, max_length=16)
    target_value: float | None = None
    deadline: date | None = None
    status: str | None = Field(default=None, pattern="^(active|achieved|paused|abandoned)$")


class ProgressIn(BaseModel):
    value: float | None = None  # nuevo valor absoluto
    delta: float | None = None  # o incremento
    note: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def one(self):
        if (self.value is None) == (self.delta is None):
            raise ValueError("Indica value o delta (solo uno)")
        return self


def _get(db, goal_id: int) -> Goal:  # noqa: ANN001
    g = db.get(Goal, goal_id)
    if not g:
        raise HTTPException(404, "Objetivo no encontrado")
    return g


@router.get("")
def list_goals(db: DB, status: str = "active") -> dict:
    tz, today = _ctx(db)
    from sqlalchemy import select
    stmt = select(Goal).order_by(Goal.status != "active", Goal.deadline.is_(None), Goal.deadline, Goal.id)
    if status != "all":
        stmt = stmt.where(Goal.status == status)
    return {"items": [svc.to_dict(db, g, today, tz) for g in db.scalars(stmt)]}


@router.post("", status_code=201)
def create(body: GoalIn, db: DB) -> dict:
    tz, today = _ctx(db)
    data = body.model_dump()
    data["start_date"] = data["start_date"] or today
    if data["current_value"] is None:
        data["current_value"] = data["start_value"]
    g = svc.create_goal(db, **data)
    db.commit()
    return svc.to_dict(db, g, today, tz)


@router.get("/{goal_id}")
def detail(goal_id: int, db: DB) -> dict:
    tz, today = _ctx(db)
    g = _get(db, goal_id)
    return {**svc.to_dict(db, g, today, tz), "history": svc.history(db, g, tz)}


@router.patch("/{goal_id}")
def patch(goal_id: int, body: GoalPatch, db: DB) -> dict:
    tz, today = _ctx(db)
    g = _get(db, goal_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(g, k, v)
    log_activity(db, "goals", "update", f"Objetivo editado: {g.title[:80]}")
    db.commit()
    return svc.to_dict(db, g, today, tz)


@router.post("/{goal_id}/progress")
def progress(goal_id: int, body: ProgressIn, db: DB) -> dict:
    tz, today = _ctx(db)
    g = _get(db, goal_id)
    if g.kind != "numeric":
        raise HTTPException(422, "El progreso de este objetivo se mide con sus tareas")
    value = body.value if body.value is not None else (g.current_value or 0) + body.delta
    svc.record_progress(db, g, value, body.note)
    db.commit()
    return {**svc.to_dict(db, g, today, tz), "history": svc.history(db, g, tz)}


@router.delete("/{goal_id}", status_code=204)
def delete(goal_id: int, db: DB) -> None:
    g = _get(db, goal_id)
    log_activity(db, "goals", "delete", f"Objetivo eliminado: {g.title[:80]}")
    db.delete(g)
    db.commit()
