from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.gym import service as gym
from atlas.gym.library import MUSCLE_ES
from atlas.gym.parse import parse_workout
from atlas.models import BodyMetric, Exercise, Routine, RoutineExercise, WorkoutSession, WorkoutSet
from atlas.models.gym import MUSCLES
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/gym", tags=["gym"])


def _today(db) -> date:  # noqa: ANN001
    return datetime.now(ZoneInfo(str(get_prefs(db)["timezone"]))).date()


def _exercise(db, exercise_id: int) -> Exercise:  # noqa: ANN001
    ex = db.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(404, "Ejercicio no encontrado")
    return ex


# ---------------------------------------------------------------- ejercicios

class ExerciseIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    muscle: str = Field(pattern="^(" + "|".join(MUSCLES) + ")$")
    secondary: list[str] = Field(default_factory=list)
    equipment: str | None = Field(default=None, max_length=32)
    per_side: bool = False
    aliases: list[str] = Field(default_factory=list, max_length=20)


class ExercisePatch(BaseModel):
    muscle: str | None = Field(default=None, pattern="^(" + "|".join(MUSCLES) + ")$")
    secondary: list[str] | None = None
    per_side: bool | None = None
    aliases: list[str] | None = Field(default=None, max_length=20)


@router.get("/exercises")
def exercises(db: DB) -> dict:
    rows = db.scalars(select(Exercise).order_by(Exercise.muscle, Exercise.name))
    return {"items": [{"id": e.id, "name": e.name, "muscle": e.muscle, "muscle_label": MUSCLE_ES[e.muscle],
                       "secondary": e.secondary, "equipment": e.equipment, "per_side": e.per_side,
                       "aliases": e.aliases, "custom": e.custom} for e in rows],
            "muscles": [{"id": m, "label": MUSCLE_ES[m]} for m in MUSCLES]}


@router.post("/exercises", status_code=201)
def create_exercise(body: ExerciseIn, db: DB) -> dict:
    if db.scalar(select(Exercise).where(Exercise.name == body.name.strip())):
        raise HTTPException(409, "Ya existe un ejercicio con ese nombre")
    bad = [m for m in body.secondary if m not in MUSCLES]
    if bad:
        raise HTTPException(422, f"Músculos desconocidos: {bad}")
    ex = Exercise(name=body.name.strip(), muscle=body.muscle, secondary=body.secondary, equipment=body.equipment,
                  per_side=body.per_side, aliases=[a.strip().lower() for a in body.aliases if a.strip()], custom=True)
    db.add(ex)
    db.commit()
    return {"id": ex.id, "name": ex.name}


@router.patch("/exercises/{exercise_id}")
def patch_exercise(exercise_id: int, body: ExercisePatch, db: DB) -> dict:
    ex = _exercise(db, exercise_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(ex, k, v)
    db.commit()
    return {"id": ex.id, "per_side": ex.per_side, "muscle": ex.muscle}


# ---------------------------------------------------------------- rutinas

class RoutineItemIn(BaseModel):
    exercise_id: int
    warmup_sets: int = Field(default=0, ge=0, le=10)
    sets: int = Field(default=3, ge=1, le=20)
    reps_min: int = Field(default=8, ge=1, le=100)
    reps_max: int | None = Field(default=None, ge=1, le=100)
    weight: float | None = Field(default=None, ge=0, le=1000)
    notes: str | None = Field(default=None, max_length=200)


class RoutineIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    weekday: int | None = Field(default=None, ge=0, le=6)
    notes: str | None = Field(default=None, max_length=1000)
    exercises: list[RoutineItemIn] = Field(default_factory=list, max_length=40)


@router.get("/routines")
def routines(db: DB) -> dict:
    rows = db.scalars(select(Routine).order_by(Routine.weekday.is_(None), Routine.weekday, Routine.id))
    return {"items": [gym.routine_dict(db, r) for r in rows], "templates": gym.list_templates()}


def _save_items(db, routine: Routine, items: list[RoutineItemIn]) -> None:  # noqa: ANN001
    for it in db.scalars(select(RoutineExercise).where(RoutineExercise.routine_id == routine.id)):
        db.delete(it)
    for i, it in enumerate(items):
        _exercise(db, it.exercise_id)
        db.add(RoutineExercise(routine_id=routine.id, position=i, **it.model_dump()))


@router.post("/routines", status_code=201)
def create_routine(body: RoutineIn, db: DB) -> dict:
    r = Routine(name=body.name, weekday=body.weekday, notes=body.notes)
    db.add(r)
    db.flush()
    _save_items(db, r, body.exercises)
    log_activity(db, "gym", "routine", f"Rutina creada: {r.name}")
    db.commit()
    return gym.routine_dict(db, r)


@router.put("/routines/{routine_id}")
def update_routine(routine_id: int, body: RoutineIn, db: DB) -> dict:
    r = db.get(Routine, routine_id)
    if not r:
        raise HTTPException(404, "Rutina no encontrada")
    r.name, r.weekday, r.notes = body.name, body.weekday, body.notes
    _save_items(db, r, body.exercises)
    db.commit()
    return gym.routine_dict(db, r)


@router.delete("/routines/{routine_id}", status_code=204)
def delete_routine(routine_id: int, db: DB) -> None:
    r = db.get(Routine, routine_id)
    if not r:
        raise HTTPException(404, "Rutina no encontrada")
    log_activity(db, "gym", "routine", f"Rutina eliminada: {r.name}")
    db.delete(r)
    db.commit()


@router.post("/routines/import/{template_id}", status_code=201)
def import_template(template_id: str, db: DB) -> dict:
    try:
        created = gym.import_template(db, template_id)
    except KeyError as exc:
        raise HTTPException(404, "Plantilla no encontrada") from exc
    db.commit()
    return {"items": [gym.routine_dict(db, r) for r in created]}


# ---------------------------------------------------------------- hoy y registro

@router.get("/today")
def today(db: DB) -> dict:
    t = _today(db)
    plan = gym.today_plan(db, t)
    if plan["session_id"]:
        plan["session"] = gym.session_dict(db, db.get(WorkoutSession, plan["session_id"]))
    return plan


class SetIn(BaseModel):
    exercise_id: int
    reps: int = Field(ge=0, le=200)
    weight: float = Field(default=0, ge=0, le=1000)
    rir: int | None = Field(default=None, ge=0, le=10)
    warmup: bool = False
    day: date | None = None
    routine_id: int | None = None  # entrenar otra rutina en un día distinto al suyo


def _routine(db, routine_id: int | None) -> Routine | None:  # noqa: ANN001
    if routine_id is None:
        return None
    r = db.get(Routine, routine_id)
    if not r:
        raise HTTPException(404, "Rutina no encontrada")
    return r


@router.post("/sets", status_code=201)
def add_set(body: SetIn, db: DB) -> dict:
    _exercise(db, body.exercise_id)
    ws = gym.add_set(db, body.day or _today(db), body.exercise_id, body.reps, body.weight, body.rir, body.warmup,
                     _routine(db, body.routine_id))
    db.commit()
    return {"id": ws.id, "session_id": ws.session_id, "e1rm": gym.e1rm(ws.weight, ws.reps)}


@router.delete("/sets/{set_id}", status_code=204)
def delete_set(set_id: int, db: DB) -> None:
    ws = db.get(WorkoutSet, set_id)
    if not ws:
        raise HTTPException(404, "Serie no encontrada")
    db.delete(ws)
    db.flush()
    gym.sync_goals(db)
    db.commit()


class LogTextIn(BaseModel):
    text: str = Field(min_length=3, max_length=4000)
    day: date | None = None
    preview: bool = False
    routine_id: int | None = None


@router.post("/log-text")
def log_text(body: LogTextIn, db: DB) -> dict:
    """Registra (o previsualiza) un entrenamiento escrito en lenguaje natural."""
    parsed = parse_workout(body.text, list(db.scalars(select(Exercise))))
    items = [{"exercise_id": p.exercise_id, "name": p.exercise_name, "reps": p.reps, "weight": p.weight, "rir": p.rir,
              "warmup_sets": p.warmup_sets, "per_side": p.per_side, "notes": p.notes} for p in parsed]
    if body.preview or not parsed:
        return {"parsed": items, "session": None}
    s, _ = gym.log_parsed(db, parsed, body.day or _today(db), _routine(db, body.routine_id))
    db.commit()
    return {"parsed": items, "session": gym.session_dict(db, s)}


# ---------------------------------------------------------------- historial y análisis

@router.get("/sessions")
def sessions(db: DB, limit: int = 30) -> dict:
    rows = db.scalars(select(WorkoutSession).order_by(WorkoutSession.performed_on.desc(), WorkoutSession.id.desc()).limit(limit))
    return {"items": [gym.session_dict(db, s) for s in rows]}


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, db: DB) -> None:
    s = db.get(WorkoutSession, session_id)
    if not s:
        raise HTTPException(404, "Sesión no encontrada")
    log_activity(db, "gym", "delete", f"Sesión eliminada: {s.routine_name or ''} {s.performed_on}")
    db.delete(s)
    db.flush()
    gym.sync_goals(db)
    db.commit()


@router.get("/progress/{exercise_id}")
def progress(exercise_id: int, db: DB, weeks: int = 26) -> dict:
    ex = _exercise(db, exercise_id)
    return {"exercise": {"id": ex.id, "name": ex.name, "per_side": ex.per_side},
            **gym.progression(db, exercise_id, weeks=max(1, min(weeks, 260)), today=_today(db))}


@router.get("/volume")
def volume(db: DB, days: int = 7) -> dict:
    return gym.weekly_volume(db, _today(db), days=max(1, min(days, 60)))


@router.get("/insights")
def insights(db: DB) -> dict:
    t = _today(db)
    vol = gym.weekly_volume(db, t)
    last = db.scalars(select(WorkoutSession).where(WorkoutSession.routine_id.is_not(None))
                      .order_by(WorkoutSession.performed_on.desc())).first()
    return {"stagnations": gym.stagnations(db, t),
            "undertrained": [m for m in vol["muscles"] if m["status"] in ("bajo", "sin trabajar")],
            "compare": gym.compare_last(db, last.routine_id) if last else None}


# ---------------------------------------------------------------- cuerpo

class BodyIn(BaseModel):
    measured_on: date | None = None
    weight_kg: float | None = Field(default=None, gt=20, lt=400)
    body_fat_pct: float | None = Field(default=None, gt=2, lt=70)
    waist_cm: float | None = Field(default=None, gt=30, lt=250)
    chest_cm: float | None = Field(default=None, gt=30, lt=250)
    arm_cm: float | None = Field(default=None, gt=10, lt=100)
    thigh_cm: float | None = Field(default=None, gt=20, lt=150)
    notes: str | None = Field(default=None, max_length=300)


def _body(b: BodyMetric) -> dict:
    return {k: getattr(b, k) for k in ("id", "weight_kg", "body_fat_pct", "waist_cm", "chest_cm", "arm_cm", "thigh_cm", "notes")} | {
        "measured_on": b.measured_on.isoformat()}


@router.get("/body")
def body_list(db: DB) -> dict:
    return {"items": [_body(b) for b in db.scalars(select(BodyMetric).order_by(BodyMetric.measured_on))]}


@router.post("/body", status_code=201)
def body_add(body: BodyIn, db: DB) -> dict:
    data = body.model_dump()
    if all(v is None for k, v in data.items() if k not in ("measured_on", "notes")):
        raise HTTPException(422, "Indica al menos una medida")
    data["measured_on"] = data["measured_on"] or _today(db)
    b = BodyMetric(**data)
    db.add(b)
    log_activity(db, "gym", "body", "Medidas corporales registradas" + (f": {b.weight_kg:g} kg" if b.weight_kg else ""))
    db.commit()
    return _body(b)


@router.delete("/body/{body_id}", status_code=204)
def body_delete(body_id: int, db: DB) -> None:
    b = db.get(BodyMetric, body_id)
    if not b:
        raise HTTPException(404, "Registro no encontrado")
    db.delete(b)
    db.commit()
