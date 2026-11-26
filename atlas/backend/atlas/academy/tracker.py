"""Knowledge Tracker + Adaptive Learning + Gamification. Todo se calcula con actividad REAL registrada:
lecciones completadas, tiempo medido en la interfaz, evaluaciones corregidas y repasos.

Repetición espaciada (variante de SM-2): cada concepto evaluado tiene facilidad, intervalo y fecha de repaso.
Un concepto solo pasa a «consolidado» con ≥3 aciertos, dominio ≥ 80 y al menos 7 días entre el primer acierto y el último
(aprobar un único test nunca basta)."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.models import AcConcept, AcCourse, AcLab, AcSession, AcTutorMsg, LfAssessment, LfLesson, LfSubject

STATES = {"nuevo": "Sin evaluar", "aprendiendo": "Aprendiendo", "reciente": "Aprendido recientemente", "consolidado": "Consolidado"}


def ckey(name: str) -> str:
    t = unicodedata.normalize("NFKD", name.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()[:200]


def concept(db: Session, subject_id: int, name: str) -> AcConcept:
    k = ckey(name)
    c = db.scalar(select(AcConcept).where(AcConcept.subject_id == subject_id, AcConcept.key == k))
    if not c:
        c = AcConcept(subject_id=subject_id, name=name.strip()[:200], key=k, history=[], errors=[])
        db.add(c)
        db.flush()
    return c


def review(c: AcConcept, score: float, kind: str, question: str | None = None, today: date | None = None) -> None:
    """Actualiza el concepto con una respuesta corregida (score 0-100)."""
    today = today or date.today()
    now = datetime.utcnow()
    ok = score >= 60
    c.history = [*(c.history or []), {"at": now.isoformat(timespec="minutes"), "score": round(score, 1), "kind": kind}][-40:]
    c.mastery = round(score if not c.reps and not c.lapses else c.mastery * 0.6 + score * 0.4, 1)
    q = max(0, min(5, round(score / 20)))  # calidad 0-5
    c.ease = max(1.3, c.ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    if ok:
        c.correct += 1
        c.reps += 1
        c.first_ok_at = c.first_ok_at or now
        c.interval_days = 1 if c.reps == 1 else 3 if c.reps == 2 else max(4, round(c.interval_days * c.ease))
    else:
        c.wrong += 1
        c.lapses += 1
        c.reps = 0
        c.interval_days = 1
        if question:
            c.errors = [*(c.errors or []), {"at": now.isoformat(timespec="minutes"), "q": question[:300]}][-10:]
    c.due_on = today + timedelta(days=c.interval_days)
    c.last_seen_at = now
    span = (now - c.first_ok_at).days if c.first_ok_at else 0
    if c.correct >= 3 and c.mastery >= 80 and span >= 7 and c.reps >= 2:
        c.state = "consolidado"
    elif c.mastery >= 60 and c.correct >= 1:
        c.state = "reciente"
    else:
        c.state = "aprendiendo"


def error_pattern(c: AcConcept) -> bool:
    """Errores repetidos: 2 o más fallos entre los 3 últimos intentos."""
    last = (c.history or [])[-3:]
    return sum(1 for h in last if h["score"] < 60) >= 2


def apply_results(db: Session, a: LfAssessment, results: list[dict]) -> None:
    for i, r in enumerate(results):
        q = (a.questions or [])[i] if i < len(a.questions or []) else {}
        name = r.get("topic") or q.get("topic")
        if name:
            review(concept(db, a.subject_id, name), float(r.get("score") or 0), a.kind, q.get("q"))
    db.flush()


def concept_dict(c: AcConcept) -> dict:
    return {"id": c.id, "subject_id": c.subject_id, "name": c.name, "mastery": c.mastery, "state": c.state, "state_label": STATES[c.state],
            "due_on": c.due_on.isoformat() if c.due_on else None, "interval_days": c.interval_days, "reps": c.reps, "lapses": c.lapses,
            "correct": c.correct, "wrong": c.wrong, "error_pattern": error_pattern(c), "errors": c.errors or [], "history": (c.history or [])[-12:]}


# ───────── perfil del alumno (para que cada profesor adapte la clase) ─────────
def profile(db: Session, subject_id: int | None) -> dict:
    from atlas.life.service import mastery
    out: dict = {}
    if subject_id:
        m = mastery(db, subject_id)
        cs = list(db.scalars(select(AcConcept).where(AcConcept.subject_id == subject_id)))
        lessons = list(db.scalars(select(LfLesson).where(LfLesson.subject_id == subject_id, LfLesson.completed_at.is_not(None))))
        mins = [x.minutes for x in lessons if x.minutes]
        out = {"nivel": m.get("label"), "nivel_num": m.get("level"), "media_evaluaciones": m.get("avg"),
               "dominados": [c.name for c in cs if c.state == "consolidado"][:15],
               "recientes": [c.name for c in cs if c.state == "reciente"][:15],
               "pendientes_o_debiles": [c.name for c in sorted(cs, key=lambda c: c.mastery) if c.state in ("aprendiendo", "nuevo")][:12],
               "errores_frecuentes": [{"concepto": c.name, "fallos": c.lapses, "ejemplo": (c.errors or [{}])[-1].get("q")} for c in cs if c.lapses >= 2][:8],
               "lecciones_completadas": [x.topic for x in lessons][-12:],
               "ritmo": f"{round(sum(mins) / len(mins))} min por lección" if mins else "sin datos de ritmo todavía",
               "examenes": [{"nota": a.score, "tipo": a.kind, "fecha": a.graded_at.date().isoformat()} for a in db.scalars(
                   select(LfAssessment).where(LfAssessment.subject_id == subject_id, LfAssessment.score.is_not(None)).order_by(LfAssessment.id.desc()).limit(5))]}
    return out


# ───────── métricas ─────────
def activity_days(db: Session) -> set[date]:
    days = {d for (d,) in db.execute(select(AcSession.day)).all()}
    days |= {x.completed_at.date() for x in db.scalars(select(LfLesson).where(LfLesson.completed_at.is_not(None)))}
    days |= {a.graded_at.date() for a in db.scalars(select(LfAssessment).where(LfAssessment.graded_at.is_not(None)))}
    return days


def streak(days: set[date], today: date) -> int:
    d = today if today in days else today - timedelta(days=1)
    n = 0
    while d in days:
        n += 1
        d -= timedelta(days=1)
    return n


def stats(db: Session, today: date | None = None) -> dict:
    today = today or date.today()
    week = today - timedelta(days=6)
    sessions = list(db.scalars(select(AcSession)))
    minutes = sum(s.minutes for s in sessions)
    by_subject = defaultdict(float)
    for s in sessions:
        if s.subject_id:
            by_subject[s.subject_id] += s.minutes
    weekly = [{"day": (week + timedelta(days=i)).isoformat(), "minutes": round(sum(s.minutes for s in sessions if s.day == week + timedelta(days=i)), 1)}
              for i in range(7)]
    graded = list(db.scalars(select(LfAssessment).where(LfAssessment.score.is_not(None)).order_by(LfAssessment.graded_at)))
    concepts = list(db.scalars(select(AcConcept)))
    recent_reviews = [h for c in concepts for h in (c.history or []) if h["at"] >= (today - timedelta(days=30)).isoformat()]
    reviews_only = [h for h in recent_reviews if h["kind"] == "review"]
    retention = round(sum(1 for h in reviews_only if h["score"] >= 60) / len(reviews_only) * 100, 1) if reviews_only else None
    days = activity_days(db)
    names = {s.id: s.name for s in db.scalars(select(LfSubject))}
    return {
        "hours": round(minutes / 60, 1), "minutes_total": round(minutes, 1), "minutes_week": round(sum(w["minutes"] for w in weekly), 1), "weekly": weekly,
        "lessons_done": db.scalar(select(func.count(LfLesson.id)).where(LfLesson.completed_at.is_not(None))) or 0,
        "courses_active": db.scalar(select(func.count(AcCourse.id)).where(AcCourse.status == "active")) or 0,
        "courses_done": db.scalar(select(func.count(AcCourse.id)).where(AcCourse.status == "completed")) or 0,
        "exams": len(graded), "avg_score": round(sum(a.score for a in graded) / len(graded), 1) if graded else None,
        "retention_pct": retention, "retention_rule": "Aciertos en repasos espaciados de los últimos 30 días",
        "streak": streak(days, today), "active_days": len(days),
        "concepts": {k: sum(1 for c in concepts if c.state == k) for k in STATES},
        "due_reviews": sum(1 for c in concepts if c.due_on and c.due_on <= today),
        "time_by_subject": sorted([{"subject": names.get(k, "?"), "minutes": round(v, 1)} for k, v in by_subject.items()], key=lambda x: -x["minutes"]),
        "score_series": [{"at": a.graded_at.date().isoformat(), "score": a.score, "subject": names.get(a.subject_id), "kind": a.kind} for a in graded][-40:],
    }


def subject_progress(db: Session) -> list[dict]:
    from atlas.life.service import mastery
    out = []
    for s in db.scalars(select(LfSubject)):
        cs = list(db.scalars(select(AcConcept).where(AcConcept.subject_id == s.id)))
        mins = db.scalar(select(func.coalesce(func.sum(AcSession.minutes), 0)).where(AcSession.subject_id == s.id)) or 0
        lessons = db.scalar(select(func.count(LfLesson.id)).where(LfLesson.subject_id == s.id, LfLesson.completed_at.is_not(None))) or 0
        if not cs and not mins and not lessons:
            continue
        m = mastery(db, s.id)
        out.append({"subject_id": s.id, "subject": s.name, "category": s.category, "level": m["level"], "level_label": m["label"], "avg": m["avg"],
                    "minutes": round(mins, 1), "lessons": lessons, "consolidated": sum(1 for c in cs if c.state == "consolidado"),
                    "recent": sum(1 for c in cs if c.state == "reciente"), "learning": sum(1 for c in cs if c.state == "aprendiendo"),
                    "series": [{"at": a.graded_at.date().isoformat(), "score": a.score} for a in db.scalars(
                        select(LfAssessment).where(LfAssessment.subject_id == s.id, LfAssessment.score.is_not(None)).order_by(LfAssessment.graded_at))]})
    return sorted(out, key=lambda x: -x["minutes"])


# ───────── gamificación (opcional) ─────────
def gamification(db: Session, st: dict) -> dict:
    """XP que premia comprensión, retención y práctica, no solo horas (las horas aportan poco)."""
    graded = list(db.scalars(select(LfAssessment).where(LfAssessment.score.is_not(None))))
    concepts = list(db.scalars(select(AcConcept)))
    labs = db.scalar(select(func.count(AcLab.id)).where(AcLab.status == "done")) or 0
    review_ok = sum(1 for c in concepts for h in (c.history or []) if h["kind"] == "review" and h["score"] >= 60)
    parts = {"comprension (evaluaciones)": round(sum(a.score / 10 * (0.6 + 0.2 * a.difficulty) for a in graded)),
             "retencion (repasos acertados)": review_ok * 6, "consolidacion (conceptos)": sum(1 for c in concepts if c.state == "consolidado") * 25,
             "practica (laboratorios)": labs * 20, "lecciones": st["lessons_done"] * 8, "cursos completados": st["courses_done"] * 60,
             "tiempo (1 XP por cada 10 min)": int(st["hours"] * 6)}
    xp = sum(parts.values())
    level = int(math.sqrt(xp / 50)) + 1
    badges = [b for b, ok in [("Primera lección", st["lessons_done"] >= 1), ("Cinco lecciones", st["lessons_done"] >= 5),
                               ("Primer examen ≥ 80 %", any(a.score >= 80 for a in graded)), ("Tres conceptos consolidados", parts["consolidacion (conceptos)"] >= 75),
                               ("Racha de 7 días", st["streak"] >= 7), ("Curso completado", st["courses_done"] >= 1), ("Laboratorio superado", labs >= 1),
                               ("Retención ≥ 80 %", (st["retention_pct"] or 0) >= 80 and review_ok >= 10)] if ok]
    return {"xp": xp, "level": level, "next_level_xp": 50 * level ** 2, "breakdown": parts, "badges": badges}


def recommendations(db: Session, st: dict) -> list[dict]:
    today = date.today()
    out = []
    due = list(db.scalars(select(AcConcept).where(AcConcept.due_on <= today).order_by(AcConcept.due_on).limit(10)))
    if due:
        out.append({"kind": "review", "text": f"Tienes {len(due)} concepto(s) para repasar hoy ({', '.join(c.name for c in due[:3])}…)", "action": "reviews"})
    for c in db.scalars(select(AcConcept)):
        if error_pattern(c):
            out.append({"kind": "remediate", "text": f"Fallos repetidos en «{c.name}»: te lo explico de otra forma y volvemos a evaluarlo", "concept_id": c.id})
            break
    cur = db.scalar(select(AcCourse).where(AcCourse.status == "active").order_by(AcCourse.updated_at.desc()))
    if cur:
        out.append({"kind": "continue", "text": f"Continúa «{cur.title}»", "course_id": cur.id})
    if not st["exams"] and st["lessons_done"]:
        out.append({"kind": "exam", "text": "Has estudiado pero aún no te has evaluado: haz un test para medir tu nivel real"})
    if not out:
        out.append({"kind": "start", "text": "Empieza un curso: pide a la academia lo que quieres aprender"})
    return out


def tutor_history(db: Session, subject_id: int | None, lesson_id: int | None, n: int = 10) -> list[dict]:
    q = select(AcTutorMsg).order_by(AcTutorMsg.id.desc()).limit(n)
    if lesson_id:
        q = q.where(AcTutorMsg.lesson_id == lesson_id)
    elif subject_id:
        q = q.where(AcTutorMsg.subject_id == subject_id)
    return [{"role": m.role, "content": m.content} for m in reversed(list(db.scalars(q)))]


def frequent_topics(db: Session) -> list[str]:
    return [t for t, _ in Counter(m.teacher for m in db.scalars(select(AcTutorMsg)) if m.teacher).most_common(3)]
