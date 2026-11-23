"""Gimnasio: registro y análisis. Todas las cifras salen de las series registradas."""

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.gym.library import MUSCLE_ES
from atlas.gym.parse import ParsedExercise
from atlas.models import Exercise, Goal, Routine, RoutineExercise, WorkoutSession, WorkoutSet
from atlas.services.activity import log_activity

TEMPLATES = Path(__file__).parent / "templates"
DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
# Referencia general para hipertrofia (series efectivas por músculo y semana). Orientativo.
WEEKLY_SETS_MIN = 10
WEEKLY_SETS_MAX = 20
TRACKED_MUSCLES = ("pecho", "espalda", "hombros", "deltoide_posterior", "biceps", "triceps", "antebrazo", "trapecio",
                   "cuadriceps", "isquios", "gluteos", "gemelos", "abdomen")


def e1rm(weight: float, reps: int) -> float:
    """1RM estimado (Epley). Solo fiable hasta ~12 repeticiones."""
    if reps <= 0 or weight <= 0:
        return 0.0
    if reps == 1:
        return weight
    return round(weight * (1 + min(reps, 12) / 30), 1)


# ------------------------------------------------------------------ rutinas

def routine_dict(db: Session, r: Routine) -> dict:
    items = db.execute(
        select(RoutineExercise, Exercise).join(Exercise, Exercise.id == RoutineExercise.exercise_id)
        .where(RoutineExercise.routine_id == r.id).order_by(RoutineExercise.position, RoutineExercise.id)
    ).all()
    return {
        "id": r.id, "name": r.name, "weekday": r.weekday, "weekday_name": DAYS_ES[r.weekday] if r.weekday is not None else None,
        "notes": r.notes, "active": r.active,
        "exercises": [{"id": re_.id, "exercise_id": ex.id, "name": ex.name, "muscle": ex.muscle, "per_side": ex.per_side,
                       "position": re_.position, "warmup_sets": re_.warmup_sets, "sets": re_.sets, "reps_min": re_.reps_min,
                       "reps_max": re_.reps_max, "weight": re_.weight, "notes": re_.notes} for re_, ex in items],
    }


def list_templates() -> list[dict]:
    out = []
    for f in sorted(TEMPLATES.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        out.append({"id": f.stem, "name": data["name"], "description": data.get("description"),
                    "days": [{"name": r["name"], "weekday": r.get("weekday")} for r in data["routines"]]})
    return out


def import_template(db: Session, template_id: str) -> list[Routine]:
    path = TEMPLATES / f"{template_id}.json"
    if not path.is_file() or path.parent != TEMPLATES:
        raise KeyError(template_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    by_name = {e.name: e for e in db.scalars(select(Exercise))}
    created = []
    for r in data["routines"]:
        routine = Routine(name=r["name"], weekday=r.get("weekday"), notes=r.get("notes"))
        db.add(routine)
        db.flush()
        for i, item in enumerate(r["exercises"]):
            ex = by_name[item["exercise"]]
            db.add(RoutineExercise(routine_id=routine.id, exercise_id=ex.id, position=i,
                                   warmup_sets=item.get("warmup_sets", 0), sets=item.get("sets", 3),
                                   reps_min=item.get("reps_min", 8), reps_max=item.get("reps_max"),
                                   weight=item.get("weight"), notes=item.get("notes")))
        created.append(routine)
    log_activity(db, "gym", "import", f"Rutina importada: {data['name']}")
    db.flush()
    return created


def routine_for_day(db: Session, day: date) -> Routine | None:
    return db.scalars(select(Routine).where(Routine.active.is_(True), Routine.weekday == day.weekday())
                      .order_by(Routine.id)).first()


def today_plan(db: Session, today: date) -> dict:
    r = routine_for_day(db, today)
    session = db.scalars(select(WorkoutSession).where(WorkoutSession.performed_on == today)
                         .order_by(WorkoutSession.id.desc())).first()
    done_ids = set()
    if session:
        done_ids = set(db.scalars(select(WorkoutSet.exercise_id).where(WorkoutSet.session_id == session.id)))
    nxt = None
    for i in range(1, 8):
        rr = routine_for_day(db, today + timedelta(days=i))
        if rr:
            nxt = {"name": rr.name, "date": (today + timedelta(days=i)).isoformat(), "weekday_name": DAYS_ES[(today + timedelta(days=i)).weekday()]}
            break
    out = {"date": today.isoformat(), "weekday_name": DAYS_ES[today.weekday()], "rest_day": r is None,
           "routine": None, "session_id": session.id if session else None, "next": nxt}
    if r:
        rd = routine_dict(db, r)
        for item in rd["exercises"]:
            item["done"] = item["exercise_id"] in done_ids
            item["last"] = last_performance(db, item["exercise_id"], before=today)
        out["routine"] = rd
    return out


# ------------------------------------------------------------------ registro

def get_or_create_session(db: Session, day: date, routine: Routine | None = None) -> WorkoutSession:
    s = db.scalars(select(WorkoutSession).where(WorkoutSession.performed_on == day).order_by(WorkoutSession.id.desc())).first()
    if s:
        return s
    routine = routine or routine_for_day(db, day)
    s = WorkoutSession(performed_on=day, routine_id=routine.id if routine else None,
                       routine_name=routine.name if routine else "Entreno libre")
    db.add(s)
    db.flush()
    return s


def log_parsed(db: Session, parsed: list[ParsedExercise], day: date,
               routine: Routine | None = None) -> tuple[WorkoutSession, list[WorkoutSet]]:
    s = get_or_create_session(db, day, routine)
    created: list[WorkoutSet] = []
    for p in parsed:
        n = db.scalar(select(func.coalesce(func.max(WorkoutSet.set_number), 0))
                      .where(WorkoutSet.session_id == s.id, WorkoutSet.exercise_id == p.exercise_id)) or 0
        if p.warmup_sets:  # el peso del calentamiento no se conoce: se anota sin inventar cifras
            note = f"{p.warmup_sets} series de calentamiento en {p.exercise_name}"
            s.notes = f"{s.notes}; {note}" if s.notes else note
        for reps in p.reps:
            n += 1
            created.append(WorkoutSet(session_id=s.id, exercise_id=p.exercise_id, set_number=n, reps=reps,
                                      weight=p.weight or 0, rir=p.rir))
    db.add_all(created)
    db.flush()
    names = ", ".join(p.exercise_name for p in parsed)
    log_activity(db, "gym", "log", f"Entreno registrado: {names[:90]}")
    sync_goals(db)
    return s, created


def add_set(db: Session, day: date, exercise_id: int, reps: int, weight: float, rir: int | None, warmup: bool,
            routine: Routine | None = None) -> WorkoutSet:
    s = get_or_create_session(db, day, routine)
    n = db.scalar(select(func.coalesce(func.max(WorkoutSet.set_number), 0))
                  .where(WorkoutSet.session_id == s.id, WorkoutSet.exercise_id == exercise_id)) or 0
    ws = WorkoutSet(session_id=s.id, exercise_id=exercise_id, set_number=n + 1, reps=reps, weight=weight, rir=rir, warmup=warmup)
    db.add(ws)
    db.flush()
    sync_goals(db)
    return ws


def session_dict(db: Session, s: WorkoutSession) -> dict:
    rows = db.execute(select(WorkoutSet, Exercise).join(Exercise, Exercise.id == WorkoutSet.exercise_id)
                      .where(WorkoutSet.session_id == s.id).order_by(WorkoutSet.id)).all()
    by_ex: dict[int, dict] = {}
    for ws, ex in rows:
        d = by_ex.setdefault(ex.id, {"exercise_id": ex.id, "name": ex.name, "muscle": ex.muscle, "per_side": ex.per_side, "sets": []})
        d["sets"].append({"id": ws.id, "set_number": ws.set_number, "reps": ws.reps, "weight": ws.weight,
                          "rir": ws.rir, "warmup": ws.warmup, "e1rm": None if ws.warmup else e1rm(ws.weight, ws.reps)})
    work = [ws for ws, _ in rows if not ws.warmup]
    return {"id": s.id, "date": s.performed_on.isoformat(), "routine_name": s.routine_name, "routine_id": s.routine_id,
            "duration_min": s.duration_min, "notes": s.notes, "exercises": list(by_ex.values()),
            "working_sets": len(work), "tonnage": round(sum(ws.weight * ws.reps for ws in work), 1)}


# ------------------------------------------------------------------ análisis

def _work_sets(db: Session, since: date | None = None, until: date | None = None, exercise_id: int | None = None):
    q = (select(WorkoutSet, WorkoutSession.performed_on, Exercise)
         .join(WorkoutSession, WorkoutSession.id == WorkoutSet.session_id)
         .join(Exercise, Exercise.id == WorkoutSet.exercise_id)
         .where(WorkoutSet.warmup.is_(False)))
    if since:
        q = q.where(WorkoutSession.performed_on >= since)
    if until:
        q = q.where(WorkoutSession.performed_on <= until)
    if exercise_id:
        q = q.where(WorkoutSet.exercise_id == exercise_id)
    return db.execute(q.order_by(WorkoutSession.performed_on, WorkoutSet.id)).all()


def last_performance(db: Session, exercise_id: int, before: date | None = None) -> dict | None:
    q = (select(WorkoutSession.performed_on).join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
         .where(WorkoutSet.exercise_id == exercise_id, WorkoutSet.warmup.is_(False)))
    if before:
        q = q.where(WorkoutSession.performed_on < before)
    day = db.scalar(q.order_by(WorkoutSession.performed_on.desc()).limit(1))
    if not day:
        return None
    sets = [ws for ws, _, _ in _work_sets(db, since=day, until=day, exercise_id=exercise_id)]
    top = max(sets, key=lambda s: (s.weight, s.reps))
    return {"date": day.isoformat(), "sets": [{"reps": s.reps, "weight": s.weight, "rir": s.rir} for s in sets],
            "top": {"reps": top.reps, "weight": top.weight}}


def progression(db: Session, exercise_id: int, weeks: int = 26, today: date | None = None) -> dict:
    today = today or date.today()
    rows = _work_sets(db, since=today - timedelta(weeks=weeks), exercise_id=exercise_id)
    by_day: dict[date, list[WorkoutSet]] = defaultdict(list)
    for ws, d, _ in rows:
        by_day[d].append(ws)
    points = []
    for d in sorted(by_day):
        sets = by_day[d]
        top = max(sets, key=lambda s: (s.weight, s.reps))
        points.append({"date": d.isoformat(), "e1rm": max(e1rm(s.weight, s.reps) for s in sets),
                       "top_weight": top.weight, "top_reps": top.reps, "sets": len(sets),
                       "volume": round(sum(s.weight * s.reps for s in sets), 1)})
    out: dict = {"points": points, "sessions": len(points)}
    if len(points) >= 2:
        first, last = points[0], points[-1]
        out["change_e1rm"] = round(last["e1rm"] - first["e1rm"], 1)
        out["change_pct"] = round((last["e1rm"] / first["e1rm"] - 1) * 100, 1) if first["e1rm"] else None
        out["change_top_weight"] = round(last["top_weight"] - first["top_weight"], 1)
        out["since"] = first["date"]
    out["best"] = max(points, key=lambda p: p["e1rm"]) if points else None
    out["stagnant"] = is_stagnant(points)
    return out


def is_stagnant(points: list[dict]) -> bool:
    """Estancado: ≥4 sesiones y las 3 últimas no superan (+1 %) el mejor 1RM estimado anterior."""
    if len(points) < 4:
        return False
    prev_best = max(p["e1rm"] for p in points[:-3])
    recent_best = max(p["e1rm"] for p in points[-3:])
    return recent_best <= prev_best * 1.01


def weekly_volume(db: Session, today: date | None = None, days: int = 7) -> dict:
    """Series efectivas por músculo (principal = 1, secundario = 0,5) en los últimos `days` días."""
    today = today or date.today()
    since = today - timedelta(days=days - 1)
    sets: dict[str, float] = defaultdict(float)
    sessions_by_muscle: dict[str, set] = defaultdict(set)
    for ws, d, ex in _work_sets(db, since=since, until=today):
        sets[ex.muscle] += 1
        sessions_by_muscle[ex.muscle].add(d)
        for m in ex.secondary or []:
            sets[m] += 0.5
    rows = []
    for m in TRACKED_MUSCLES:
        n = sets.get(m, 0.0)
        status = "sin trabajar" if n == 0 else "bajo" if n < WEEKLY_SETS_MIN else "alto" if n > WEEKLY_SETS_MAX else "óptimo"
        rows.append({"muscle": m, "label": MUSCLE_ES[m], "sets": n, "frequency": len(sessions_by_muscle.get(m, ())),
                     "status": status})
    return {"from": since.isoformat(), "to": today.isoformat(), "muscles": rows,
            "reference": {"min": WEEKLY_SETS_MIN, "max": WEEKLY_SETS_MAX}}


def stagnations(db: Session, today: date | None = None) -> list[dict]:
    today = today or date.today()
    ids = set(db.scalars(select(WorkoutSet.exercise_id).join(WorkoutSession, WorkoutSession.id == WorkoutSet.session_id)
                         .where(WorkoutSession.performed_on >= today - timedelta(weeks=8))))
    out = []
    for ex in db.scalars(select(Exercise).where(Exercise.id.in_(ids))) if ids else []:
        p = progression(db, ex.id, weeks=8, today=today)
        if p["stagnant"]:
            out.append({"exercise_id": ex.id, "name": ex.name, "sessions": p["sessions"],
                        "best_e1rm": p["best"]["e1rm"] if p["best"] else None})
    return out


def compare_last(db: Session, routine_id: int) -> dict | None:
    """Compara las dos últimas sesiones de una rutina, ejercicio a ejercicio."""
    ss = list(db.scalars(select(WorkoutSession).where(WorkoutSession.routine_id == routine_id)
                         .order_by(WorkoutSession.performed_on.desc()).limit(2)))
    if len(ss) < 2:
        return None
    cur, prev = session_dict(db, ss[0]), session_dict(db, ss[1])

    def tops(sd):
        return {e["exercise_id"]: max((s for s in e["sets"] if not s["warmup"]), key=lambda s: (s["weight"], s["reps"]), default=None)
                for e in sd["exercises"]}
    tc, tp = tops(cur), tops(prev)
    rows = []
    for e in cur["exercises"]:
        a, b = tc.get(e["exercise_id"]), tp.get(e["exercise_id"])
        if a and b:
            rows.append({"name": e["name"], "now": a, "before": b,
                         "delta_e1rm": round(e1rm(a["weight"], a["reps"]) - e1rm(b["weight"], b["reps"]), 1)})
    return {"current": cur["date"], "previous": prev["date"], "exercises": rows,
            "tonnage_delta": round(cur["tonnage"] - prev["tonnage"], 1)}


# ------------------------------------------------------------------ objetivos automáticos

AUTO_METRICS = ("exercise_weight", "exercise_e1rm", "exercise_reps", "workout_count")


def goal_auto_value(db: Session, g: Goal) -> float | None:
    if g.auto_metric == "workout_count":
        return float(db.scalar(select(func.count()).select_from(WorkoutSession)
                               .where(WorkoutSession.performed_on >= g.start_date)) or 0)
    if not g.auto_exercise_id:
        return None
    rows = _work_sets(db, since=g.start_date, exercise_id=g.auto_exercise_id)
    if not rows:
        return None
    sets = [ws for ws, _, _ in rows]
    if g.auto_metric == "exercise_weight":
        return max(s.weight for s in sets)
    if g.auto_metric == "exercise_e1rm":
        return max(e1rm(s.weight, s.reps) for s in sets)
    if g.auto_metric == "exercise_reps":
        return float(max(s.reps for s in sets))
    return None


def sync_goals(db: Session) -> list[Goal]:
    """Actualiza los objetivos enlazados al gimnasio con los datos registrados."""
    from atlas.services.goals import record_progress
    changed = []
    for g in db.scalars(select(Goal).where(Goal.status == "active", Goal.auto_metric.is_not(None))):
        v = goal_auto_value(db, g)
        if v is not None and v != g.current_value:
            record_progress(db, g, v, note="Automático (gimnasio)")
            changed.append(g)
    return changed


# ------------------------------------------------------------------ contexto para la IA

def snapshot(db: Session, today: date) -> dict:
    tp = today_plan(db, today)
    vol = weekly_volume(db, today)
    ex_ids = set(db.scalars(select(RoutineExercise.exercise_id)))
    ex_ids |= set(db.scalars(select(WorkoutSet.exercise_id).join(WorkoutSession, WorkoutSession.id == WorkoutSet.session_id)
                             .where(WorkoutSession.performed_on >= today - timedelta(weeks=12))))
    progress = []
    for ex in db.scalars(select(Exercise).where(Exercise.id.in_(ex_ids))) if ex_ids else []:
        p = progression(db, ex.id, weeks=12, today=today)
        if not p["points"]:
            continue
        last = p["points"][-1]
        item = {"ejercicio": ex.name, "ultima_sesion": last["date"], "mejor_serie": f"{last['top_weight']:g} kg x {last['top_reps']}",
                "1rm_estimado": last["e1rm"], "sesiones_12_semanas": p["sessions"]}
        if ex.per_side:
            item["peso_por_lado"] = True
        if "change_pct" in p:
            item["cambio_1rm_desde"] = f"{p['change_pct']:+g}% desde {p['since']}"
        if p["stagnant"]:
            item["estancado"] = True
        progress.append(item)
    return {
        "hoy": ("descanso" if tp["rest_day"] else tp["routine"]["name"]) + f" ({tp['weekday_name']})",
        "proximo_entreno": tp["next"],
        "rutina_semanal": [f"{DAYS_ES[r.weekday]}: {r.name}" for r in db.scalars(select(Routine).where(Routine.active.is_(True))
                           .order_by(Routine.weekday)) if r.weekday is not None],
        "progresion_por_ejercicio": progress,
        "volumen_semanal_series_por_musculo": {m["label"]: m["sets"] for m in vol["muscles"] if m["sets"] or m["muscle"] in
                                               ("pecho", "espalda", "hombros", "biceps", "triceps", "cuadriceps", "isquios", "gluteos")},
        "musculos_por_debajo_de_10_series": [m["label"] for m in vol["muscles"] if m["status"] in ("bajo", "sin trabajar")],
        "nota": "1RM estimado con la fórmula de Epley. En ejercicios «por lado» el peso es por lado.",
    }
