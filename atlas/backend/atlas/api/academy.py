"""API de VISTAN ACADEMY. Amplía la academia de LIFE OS (mismas asignaturas, lecciones y evaluaciones) y usa su mismo
control de acceso (PIN/sesión). Todo el progreso sale de actividad real registrada."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from atlas.academy import ai, catalog, grading, labs, teachers, tracker
from atlas.api.deps import DB
from atlas.brain.base import ProviderError
from atlas.life import lock
from atlas.models import (AcConcept, AcCourse, AcLab, AcPath, AcSession, AcTutorMsg, ActivityLog, Goal, LfAssessment, LfLesson, LfSubject,
                          Project, Research)
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs, set_prefs

router = APIRouter(prefix="/api/academy", tags=["academy"], dependencies=[Depends(lock.require)])
SETTINGS = {"gamification": True, "weekly_minutes": 180, "weekly_lessons": 3, "style": "equilibrado", "voice_autoplay": False}


def _get(db, model, oid: int):  # noqa: ANN001, ANN202
    o = db.get(model, oid)
    if not o:
        raise HTTPException(404, "No encontrado")
    return o


def row(o, skip: tuple = ()) -> dict:  # noqa: ANN001
    out = {}
    for c in o.__table__.columns:
        if c.name in skip:
            continue
        v = getattr(o, c.name)
        out[c.name] = v.isoformat() if isinstance(v, (date, datetime)) else v
    return out


def conf(prefs: dict) -> dict:
    return {**SETTINGS, **(prefs.get("academy") or {})}


def _ai(fn, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202
    try:
        return fn(*a, **k)
    except ProviderError as exc:
        raise HTTPException(503, f"Necesita la IA de VISTAN (Ollama o un modelo configurado): {exc}") from exc


def _project(db, pid: int | None) -> dict | None:  # noqa: ANN001
    p = db.get(Project, pid) if pid else None
    return {"nombre": p.name, "descripcion": (p.description or "")[:800]} if p else None


def _disclaimer(s: LfSubject | None) -> str | None:
    k = catalog.high_impact(s) if s else None
    return catalog.DISCLAIMERS.get(k) if k else None


def _public_q(q: dict) -> dict:
    return {k: v for k, v in q.items() if k not in ("answer", "explanation", "solution", "model_answer", "tolerance")} | (
        {"criteria": [{"criterio": c["criterio"], "puntos": c["puntos"]} for c in q.get("criteria", [])]} if q.get("criteria") else {})


# ───────── meta, panel y ajustes ─────────
@router.get("/meta")
def meta(db: DB) -> dict:
    catalog.ensure(db)
    db.commit()
    return {"categories": catalog.CATEGORIES, "teachers": [{"id": t.id, "name": t.name, "specialty": t.specialty, "tools": t.tools, "categories": t.categories}
                                                           for t in teachers.TEACHERS.values()], "coordinator": teachers.COORDINATOR,
            "question_types": list(ai.TYPES), "actions": ai.ACTIONS, "settings": conf(get_prefs(db)), "criteria_note": grading.CRITERIA_NOTE,
            "states": tracker.STATES}


class SettingsIn(BaseModel):
    gamification: bool | None = None
    weekly_minutes: int | None = Field(default=None, ge=0, le=6000)
    weekly_lessons: int | None = Field(default=None, ge=0, le=100)
    style: str | None = Field(default=None, pattern="^(equilibrado|practico|teorico|visual)$")
    voice_autoplay: bool | None = None


@router.put("/settings")
def settings(body: SettingsIn, db: DB) -> dict:
    c = conf(get_prefs(db)) | body.model_dump(exclude_none=True)
    set_prefs(db, {"academy": c})
    db.commit()
    return c


def _course_progress(db, c: AcCourse) -> dict:  # noqa: ANN001
    lessons = {(x.module_idx, x.lesson_idx): x for x in db.scalars(select(LfLesson).where(LfLesson.course_id == c.id))}
    total = sum(len(m["lessons"]) for m in c.modules)
    done = sum(1 for x in lessons.values() if x.completed_at)
    exams = {a.module_idx: a for a in db.scalars(select(LfAssessment).where(LfAssessment.course_id == c.id, LfAssessment.kind == "module",
                                                                           LfAssessment.score.is_not(None)).order_by(LfAssessment.score))}
    nxt = None
    for mi, m in enumerate(c.modules):
        for li, _ in enumerate(m["lessons"]):
            x = lessons.get((mi, li))
            if not x or not x.completed_at:
                nxt = {"module": mi, "lesson": li, "lesson_id": x.id if x else None, "title": m["lessons"][li]["title"]}
                break
        if nxt:
            break
        if mi not in exams or exams[mi].score < 70:
            nxt = {"module": mi, "exam": True, "title": f"Examen del módulo {mi + 1}: {m['title']}"}
            break
    final = db.scalar(select(LfAssessment).where(LfAssessment.course_id == c.id, LfAssessment.kind == "final", LfAssessment.score.is_not(None))
                      .order_by(LfAssessment.score.desc()))
    return {"total": total, "done": done, "pct": round(done / total * 100) if total else 0, "next": nxt,
            "module_exams": {str(k): v.score for k, v in exams.items()}, "final_score": final.score if final else None,
            "lessons": {f"{k[0]}-{k[1]}": {"id": v.id, "done": bool(v.completed_at), "minutes": v.minutes} for k, v in lessons.items()}}


@router.get("/dashboard")
def dashboard(db: DB) -> dict:
    catalog.ensure(db)
    prefs = get_prefs(db)
    c = conf(prefs)
    st = tracker.stats(db)
    subs = tracker.subject_progress(db)
    levels = [s["level"] for s in subs if s["level"]]
    courses = [row(x, ("modules",)) | {"progress": _course_progress(db, x)} for x in db.scalars(select(AcCourse).where(AcCourse.status == "active").order_by(AcCourse.updated_at.desc()))]
    upcoming = [{"course_id": x["id"], "course": x["title"], "title": x["progress"]["next"]["title"]} for x in courses if (x["progress"]["next"] or {}).get("exam")]
    goals = [{"id": g.id, "title": g.title, "deadline": g.deadline.isoformat() if g.deadline else None, "current": g.current_value, "target": g.target_value,
              "unit": g.unit, "status": g.status} for g in db.scalars(select(Goal).where(Goal.area == "aprendizaje").order_by(Goal.id.desc()).limit(8))]
    recent = [{"at": a.created_at.isoformat(), "summary": a.summary} for a in db.scalars(select(ActivityLog).where(ActivityLog.module == "academy")
                                                                                       .order_by(ActivityLog.id.desc()).limit(10))]
    cont = None
    if st["due_reviews"]:
        cont = {"kind": "reviews", "label": f"Repasar {st['due_reviews']} concepto(s) pendientes"}
    elif courses and courses[0]["progress"]["next"]:
        cont = {"kind": "course", "course_id": courses[0]["id"], "label": f"{courses[0]['title']} · {courses[0]['progress']['next']['title']}"}
    return {"greeting": prefs.get("user_name") or prefs.get("username") or "", "overall_level": round(sum(levels) / len(levels), 1) if levels else None,
            "stats": st, "courses": courses, "upcoming_exams": upcoming, "goals": goals, "weekly_target": {"minutes": c["weekly_minutes"], "lessons": c["weekly_lessons"]},
            "lessons_week": db.scalar(select(func.count(LfLesson.id)).where(LfLesson.completed_at >= datetime.utcnow() - timedelta(days=7))) or 0,
            "recommendations": tracker.recommendations(db, st), "recent": recent, "continue": cont,
            "gamification": tracker.gamification(db, st) if c["gamification"] else None, "subjects": subs[:8]}


# ───────── biblioteca ─────────
@router.get("/library")
def library(db: DB, category: str | None = None, q: str = "") -> list[dict]:
    catalog.ensure(db)
    db.commit()
    s = select(LfSubject).order_by(LfSubject.category, LfSubject.name)
    if category:
        s = s.where(LfSubject.category == category)
    if q:
        s = s.where(LfSubject.name.ilike(f"%{q}%"))
    counts = dict(db.execute(select(AcConcept.subject_id, func.count(AcConcept.id)).group_by(AcConcept.subject_id)).all())
    lessons = dict(db.execute(select(LfLesson.subject_id, func.count(LfLesson.id)).where(LfLesson.completed_at.is_not(None)).group_by(LfLesson.subject_id)).all())
    return [{"id": x.id, "key": x.key, "name": x.name, "category": x.category, "custom": x.custom, "description": x.description,
             "concepts": counts.get(x.id, 0), "lessons_done": lessons.get(x.id, 0), "high_impact": catalog.high_impact(x)} for x in db.scalars(s)]


class SubjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: str = Field(pattern="^(" + "|".join(catalog.CATEGORIES) + ")$")
    description: str | None = Field(default=None, max_length=2000)


@router.post("/library", status_code=201)
def add_subject(body: SubjectIn, db: DB) -> dict:
    key = catalog.slug(body.name)
    if db.scalar(select(LfSubject).where(LfSubject.key == key)):
        raise HTTPException(409, "Esa disciplina ya existe en la biblioteca")
    s = LfSubject(key=key, name=body.name.strip(), category=body.category, description=body.description, custom=True, syllabus=[])
    db.add(s)
    log_activity(db, "academy", "subject", f"Disciplina añadida a la biblioteca: {s.name}")
    db.commit()
    return row(s)


@router.delete("/library/{sid}", status_code=204)
def del_subject(sid: int, db: DB) -> None:
    s = _get(db, LfSubject, sid)
    if not s.custom:
        raise HTTPException(409, "Solo se pueden eliminar disciplinas añadidas por ti")
    if db.scalar(select(LfLesson.id).where(LfLesson.subject_id == sid).limit(1)) or db.scalar(select(LfAssessment.id).where(LfAssessment.subject_id == sid).limit(1)):
        raise HTTPException(409, "Tiene lecciones o evaluaciones: elimínalas antes desde Memoria educativa")
    db.delete(s)
    db.commit()


@router.get("/subjects/{sid}")
def subject(sid: int, db: DB) -> dict:
    from atlas.life.service import mastery
    s = _get(db, LfSubject, sid)
    return {"subject": row(s), "mastery": mastery(db, sid), "teachers": [t.name for t in teachers.choose(s.category, s.name)],
            "disclaimer": _disclaimer(s), "concepts": [tracker.concept_dict(c) for c in db.scalars(select(AcConcept).where(AcConcept.subject_id == sid).order_by(AcConcept.mastery))],
            "courses": [row(c, ("modules",)) for c in db.scalars(select(AcCourse).where(AcCourse.subject_id == sid))],
            "lessons": [row(x, ("content", "progress")) for x in db.scalars(select(LfLesson).where(LfLesson.subject_id == sid).order_by(LfLesson.id.desc()).limit(50))],
            "exams": [row(a, ("questions", "answers", "feedback", "criteria")) for a in db.scalars(select(LfAssessment).where(LfAssessment.subject_id == sid).order_by(LfAssessment.id.desc()).limit(30))]}


# ───────── cursos ─────────
class CourseIn(BaseModel):
    request: str = Field(min_length=6, max_length=2000)
    subject_id: int | None = None
    project_id: int | None = None
    path_id: int | None = None


def _subject_for(db, sid: int | None, text: str) -> LfSubject:  # noqa: ANN001
    if sid:
        return _get(db, LfSubject, sid)
    t = catalog.slug(text).replace("-", " ")
    for s in db.scalars(select(LfSubject)):
        if catalog.slug(s.name).replace("-", " ") in t:
            return s
    s = db.scalar(select(LfSubject).where(LfSubject.key == "pensamiento-critico")) or db.scalar(select(LfSubject))
    return s


@router.post("/courses", status_code=201)
async def create_course(body: CourseIn, db: DB) -> dict:
    catalog.ensure(db)
    s = _subject_for(db, body.subject_id, body.request)
    if body.project_id:
        _get(db, Project, body.project_id)
    prefs = get_prefs(db)
    d = await run_in_threadpool(_ai, ai.course, prefs, body.request, s.name, tracker.profile(db, s.id), _project(db, body.project_id))
    c = AcCourse(subject_id=s.id, title=d["title"], description=d["description"], request=body.request, level_start=d["level_start"], goals=d["goals"],
                 modules=d["modules"], est_hours=d["est_hours"], final_project=d["final_project"], criteria=d["criteria"], project_id=body.project_id,
                 path_id=body.path_id, model=d["model"])
    db.add(c)
    log_activity(db, "academy", "course", f"Curso creado: {c.title}")
    db.commit()
    return row(c) | {"progress": _course_progress(db, c)}


@router.get("/courses")
def list_courses(db: DB, status: str | None = None) -> list[dict]:
    s = select(AcCourse).order_by(AcCourse.updated_at.desc())
    if status:
        s = s.where(AcCourse.status == status)
    return [row(c, ("modules",)) | {"progress": _course_progress(db, c)} for c in db.scalars(s)]


@router.get("/courses/{cid}")
def get_course(cid: int, db: DB) -> dict:
    c = _get(db, AcCourse, cid)
    s = db.get(LfSubject, c.subject_id) if c.subject_id else None
    return row(c) | {"progress": _course_progress(db, c), "subject": s.name if s else None, "disclaimer": _disclaimer(s)}


class CoursePatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, pattern="^(active|paused|completed|archived)$")
    modules: list[dict] | None = None
    project_id: int | None = None


@router.patch("/courses/{cid}")
def patch_course(cid: int, body: CoursePatch, db: DB) -> dict:
    c = _get(db, AcCourse, cid)
    ch = body.model_dump(exclude_unset=True)
    if "modules" in ch:
        mods = []
        for m in ch["modules"] or []:
            ls = [{"title": str(x.get("title"))[:200], "objective": str(x.get("objective") or "")[:400], "minutes": int(x.get("minutes") or 30)}
                  for x in m.get("lessons") or [] if x.get("title")]
            if m.get("title") and ls:
                mods.append({"title": str(m["title"])[:200], "objective": str(m.get("objective") or "")[:400], "lessons": ls, "exam": True})
        if not mods:
            raise HTTPException(422, "El curso necesita al menos un módulo con una lección")
        old = {(lx.module_idx, lx.lesson_idx): lx for lx in db.scalars(select(LfLesson).where(LfLesson.course_id == cid))}
        titles = {lx.topic: lx for lx in old.values()}
        for mi, m in enumerate(mods):  # las lecciones ya generadas siguen a su título al reorganizar
            for li, x in enumerate(m["lessons"]):
                lx = titles.get(x["title"])
                if lx:
                    lx.module_idx, lx.lesson_idx = mi, li
        ch["modules"] = mods
    if ch.get("status") == "completed" and c.status != "completed":
        c.completed_at = datetime.utcnow()
    for k, v in ch.items():
        setattr(c, k, v)
    log_activity(db, "academy", "course", f"Curso «{c.title}» actualizado: {', '.join(ch)}")
    db.commit()
    return get_course(cid, db)


@router.delete("/courses/{cid}", status_code=204)
def delete_course(cid: int, db: DB) -> None:
    c = _get(db, AcCourse, cid)
    log_activity(db, "academy", "course", f"Curso eliminado: {c.title} (las lecciones y evaluaciones se conservan en la materia)")
    db.delete(c)
    db.commit()


@router.post("/courses/{cid}/lessons/{mi}/{li}")
async def course_lesson(cid: int, mi: int, li: int, db: DB) -> dict:
    c = _get(db, AcCourse, cid)
    if mi >= len(c.modules) or li >= len(c.modules[mi]["lessons"]):
        raise HTTPException(404, "Lección no encontrada en el curso")
    ex = db.scalar(select(LfLesson).where(LfLesson.course_id == cid, LfLesson.module_idx == mi, LfLesson.lesson_idx == li))
    if ex:
        return row(ex)
    s = _get(db, LfSubject, c.subject_id)
    item = c.modules[mi]["lessons"][li]
    prefs = get_prefs(db)
    level = max(c.level_start, min(5, c.level_start + mi // 2))
    g = await run_in_threadpool(_ai, ai.lesson, prefs, s.name, item["title"], item.get("objective") or "", level, tracker.profile(db, s.id),
                                teachers.choose(s.category, s.name, item["title"]), _project(db, c.project_id), "", _disclaimer(s))
    x = LfLesson(subject_id=s.id, topic=item["title"], level=level, content=g["content"], model=g["model"], course_id=cid, module_idx=mi, lesson_idx=li,
                 progress={"section": 0, "seen": []})
    db.add(x)
    c.updated_at = datetime.utcnow()
    db.commit()
    return row(x)


class LessonIn(BaseModel):
    subject_id: int
    topic: str = Field(min_length=2, max_length=200)
    level: int = Field(default=1, ge=1, le=5)
    doc_id: int | None = None


@router.post("/lessons", status_code=201)
async def standalone_lesson(body: LessonIn, db: DB) -> dict:
    """Lección suelta; opcionalmente basada en un documento de tu gestor documental (contenido tratado como dato)."""
    s = _get(db, LfSubject, body.subject_id)
    doc = ""
    if body.doc_id:
        from atlas.models import DocChunk, Document
        d = db.get(Document, body.doc_id)
        if not d or d.vault:
            raise HTTPException(404, "Documento no encontrado")
        doc = ai.clean_doc("\n".join(ch.text for ch in db.scalars(select(DocChunk).where(DocChunk.document_id == d.id).order_by(DocChunk.idx).limit(8))))
    g = await run_in_threadpool(_ai, ai.lesson, get_prefs(db), s.name, body.topic, "", body.level, tracker.profile(db, s.id),
                                teachers.choose(s.category, s.name, body.topic), None, doc, _disclaimer(s))
    x = LfLesson(subject_id=s.id, topic=body.topic, level=body.level, content=g["content"] | ({"source_document": body.doc_id} if body.doc_id else {}),
                 model=g["model"], progress={"section": 0, "seen": []})
    db.add(x)
    db.commit()
    return row(x)


@router.get("/lessons/{lid}")
def get_lesson(lid: int, db: DB) -> dict:
    x = _get(db, LfLesson, lid)
    s = db.get(LfSubject, x.subject_id)
    d = row(x)
    ev = (x.content or {}).get("evaluacion") or []
    checked = (x.progress or {}).get("check")
    if not checked:  # las respuestas de la evaluación no se muestran antes de contestar
        d["content"] = {**(x.content or {}), "evaluacion": [{k: v for k, v in q.items() if k not in ("answer", "explanation")} for q in ev]}
    return d | {"subject": s.name if s else None, "tutor": tracker.tutor_history(db, None, lid, 20)}


class ProgressIn(BaseModel):
    section: int = Field(ge=0, le=50)
    seen: list[str] = Field(default_factory=list, max_length=30)


@router.patch("/lessons/{lid}/progress")
def lesson_progress(lid: int, body: ProgressIn, db: DB) -> dict:
    x = _get(db, LfLesson, lid)
    x.progress = {**(x.progress or {}), "section": body.section, "seen": body.seen, "at": datetime.utcnow().isoformat(timespec="minutes")}
    db.commit()
    return {"progress": x.progress}


class CheckIn(BaseModel):
    answers: list[int | None] = Field(max_length=10)


@router.post("/lessons/{lid}/check")
def lesson_check(lid: int, body: CheckIn, db: DB) -> dict:
    """Evaluación de la lección (tipo test, corrección exacta). Actualiza el dominio de cada concepto."""
    x = _get(db, LfLesson, lid)
    ev = (x.content or {}).get("evaluacion") or []
    if len(body.answers) != len(ev):
        raise HTTPException(422, "Responde todas las preguntas")
    res = [{"correct": a == q["answer"], "answer": q["answer"], "explanation": q.get("explanation"), "topic": q.get("topic") or x.topic} for q, a in zip(ev, body.answers)]
    for r in res:
        tracker.review(tracker.concept(db, x.subject_id, r["topic"]), 100.0 if r["correct"] else 0.0, "lesson")
    score = round(sum(r["correct"] for r in res) / len(res) * 100, 1) if res else None
    x.progress = {**(x.progress or {}), "check": {"answers": body.answers, "score": score}}
    db.commit()
    return {"results": res, "score": score}


class CompleteIn(BaseModel):
    minutes: float = Field(default=0, ge=0, le=600)


@router.post("/lessons/{lid}/complete")
def lesson_complete(lid: int, body: CompleteIn, db: DB) -> dict:
    x = _get(db, LfLesson, lid)
    if not x.completed_at:
        x.completed_at = datetime.utcnow()
        log_activity(db, "academy", "lesson", f"Lección completada: {x.topic}")
    if body.minutes:
        x.minutes = (x.minutes or 0) + body.minutes
        db.add(AcSession(kind="lesson", subject_id=x.subject_id, course_id=x.course_id, ref_id=x.id, minutes=body.minutes, day=date.today()))
    if x.course_id:
        c = db.get(AcCourse, x.course_id)
        if c:
            c.updated_at = datetime.utcnow()
    db.commit()
    return row(x, ("content",))


class SessionIn(BaseModel):
    kind: str = Field(pattern="^(lesson|exam|review|tutor|lab|research)$")
    minutes: float = Field(gt=0, le=240)
    subject_id: int | None = None
    course_id: int | None = None
    ref_id: int | None = None


@router.post("/sessions", status_code=201)
def add_session(body: SessionIn, db: DB) -> dict:
    """Tiempo medido en la interfaz mientras estudias (no se estima ni se inventa)."""
    s = AcSession(**body.model_dump(), day=date.today())
    if s.kind == "lesson" and s.ref_id:
        x = db.get(LfLesson, s.ref_id)
        if x:
            x.minutes = (x.minutes or 0) + s.minutes
    db.add(s)
    db.commit()
    return row(s)


# ───────── profesor ─────────
class TutorIn(BaseModel):
    subject_id: int
    question: str | None = Field(default=None, max_length=4000)
    action: str | None = Field(default=None, pattern="^(" + "|".join(ai.ACTIONS) + ")$")
    lesson_id: int | None = None


@router.post("/tutor")
async def tutor(body: TutorIn, db: DB) -> dict:
    s = _get(db, LfSubject, body.subject_id)
    q = (ai.ACTIONS[body.action] + (f" Tema: {body.question}" if body.question else "")) if body.action else (body.question or "").strip()
    if not q:
        raise HTTPException(422, "Escribe una pregunta o elige una acción")
    lesson = db.get(LfLesson, body.lesson_id) if body.lesson_id else None
    lctx = {"tema": lesson.topic, "resumen": (lesson.content or {}).get("resumen"), "seccion_actual": (lesson.progress or {}).get("section")} if lesson else None
    team = teachers.choose(s.category, s.name, q)
    r = await run_in_threadpool(_ai, ai.tutor, get_prefs(db), s.name, team, tracker.profile(db, s.id),
                                tracker.tutor_history(db, s.id, body.lesson_id), q, lctx, _disclaimer(s))
    for role, text, model in (("user", q, None), ("assistant", r["answer"], r["model"])):
        db.add(AcTutorMsg(subject_id=s.id, lesson_id=body.lesson_id, teacher=team[0].name, role=role, content=text, model=model))
    db.commit()
    return {"answer": r["answer"], "model": r["model"], "teachers": [t.name for t in team], "coordinator": teachers.COORDINATOR}


@router.get("/tutor/history")
def tutor_hist(db: DB, subject_id: int | None = None, lesson_id: int | None = None) -> list[dict]:
    s = select(AcTutorMsg).order_by(AcTutorMsg.id.desc()).limit(100)
    if lesson_id:
        s = s.where(AcTutorMsg.lesson_id == lesson_id)
    elif subject_id:
        s = s.where(AcTutorMsg.subject_id == subject_id)
    return [row(m) for m in reversed(list(db.scalars(s)))]


@router.delete("/tutor/history", status_code=204)
def tutor_clear(db: DB, subject_id: int | None = None) -> None:
    s = select(AcTutorMsg)
    if subject_id:
        s = s.where(AcTutorMsg.subject_id == subject_id)
    for m in db.scalars(s):
        db.delete(m)
    log_activity(db, "academy", "memory", "Historial del profesor eliminado")
    db.commit()


# ───────── exámenes ─────────
class ExamIn(BaseModel):
    subject_id: int | None = None
    course_id: int | None = None
    module_idx: int | None = None
    kind: str = Field(default="quiz", pattern="^(quiz|exam|module|final|review|critical)$")
    topics: list[str] = Field(default_factory=list, max_length=20)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    types: list[str] = Field(default_factory=lambda: ["mcq", "tf", "numeric", "open"], max_length=6)
    n: int = Field(default=6, ge=2, le=15)


def _create_exam(db, prefs: dict, body: ExamIn) -> LfAssessment:  # noqa: ANN001
    from atlas.life.service import mastery
    c = _get(db, AcCourse, body.course_id) if body.course_id else None
    sid = body.subject_id or (c.subject_id if c else None)
    if not sid:
        raise HTTPException(422, "Indica la materia o el curso")
    s = _get(db, LfSubject, sid)
    topics = list(body.topics)
    if c and body.kind == "module":
        if body.module_idx is None or body.module_idx >= len(c.modules):
            raise HTTPException(422, "Módulo no válido")
        topics = [x["title"] for x in c.modules[body.module_idx]["lessons"]]
    elif c and body.kind == "final":
        topics = [x["title"] for m in c.modules for x in m["lessons"]]
    m = mastery(db, sid)
    diff = body.difficulty or max(1, min(5, (m["level"] or 1) + (1 if (m["avg"] or 0) >= 75 else 0)))
    types = [t for t in body.types if t in ai.TYPES] or ["mcq"]
    if s.category == "programacion" and "code" not in types and body.kind in ("exam", "module", "final"):
        types.append("code")
    g = _ai(ai.exam, prefs, s.name, topics or [s.name], diff, body.kind, tracker.profile(db, sid), types, body.n if body.kind not in ("final",) else max(body.n, 10))
    a = LfAssessment(subject_id=sid, kind=body.kind, topic=", ".join(topics)[:200] or None, difficulty=diff, questions=g["questions"], model=g["model"],
                     course_id=c.id if c else None, module_idx=body.module_idx, criteria={"note": grading.CRITERIA_NOTE,
                                                                                         "points": [q.get("points", 1) for q in g["questions"]]})
    db.add(a)
    db.flush()
    return a


@router.post("/exams", status_code=201)
async def create_exam(body: ExamIn, db: DB) -> dict:
    prefs = get_prefs(db)
    a = await run_in_threadpool(_create_exam, db, prefs, body)
    db.commit()
    return row(a, ("questions", "answers")) | {"questions": [_public_q(q) for q in a.questions]}


class SubmitIn(BaseModel):
    answers: list = Field(max_length=40)
    minutes: float = Field(default=0, ge=0, le=300)


@router.post("/exams/{aid}/submit")
async def submit_exam(aid: int, body: SubmitIn, db: DB) -> dict:
    a = _get(db, LfAssessment, aid)
    if a.score is not None:
        raise HTTPException(409, "Esta evaluación ya está corregida")
    if len(body.answers) != len(a.questions):
        raise HTTPException(422, "Responde todas las preguntas (puedes dejar en blanco las abiertas)")
    s = _get(db, LfSubject, a.subject_id)
    prev = db.scalar(select(LfAssessment).where(LfAssessment.subject_id == a.subject_id, LfAssessment.score.is_not(None), LfAssessment.id != aid)
                     .order_by(LfAssessment.graded_at.desc()))
    g = await run_in_threadpool(grading.grade, get_prefs(db), s.name, a.questions, body.answers)
    a.answers, a.score, a.graded_at = body.answers, g["score"], datetime.utcnow()
    a.feedback = {"results": g["results"], "weak_topics": g["weak_topics"], "mastered_topics": g["mastered_topics"], "grade_10": g["grade_10"],
                  "correct": g["correct"], "incorrect": g["incorrect"], "points": g["points"], "max_points": g["max_points"],
                  "pending_ai": g["pending_ai"], "previous": prev.score if prev else None}
    tracker.apply_results(db, a, g["results"])
    if body.minutes:
        db.add(AcSession(kind="review" if a.kind == "review" else "exam", subject_id=a.subject_id, course_id=a.course_id, ref_id=a.id, minutes=body.minutes, day=date.today()))
    log_activity(db, "academy", "exam", f"Evaluación de {s.name} ({a.kind}): {g['score']} %")
    if a.course_id:
        _maybe_complete(db, db.get(AcCourse, a.course_id))
    db.commit()
    return row(a) | {"evolution": None if not prev else round(g["score"] - prev.score, 1)}


def _maybe_complete(db, c: AcCourse | None) -> None:  # noqa: ANN001
    if not c or c.status == "completed":
        return
    p = _course_progress(db, c)
    if p["done"] == p["total"] and all((p["module_exams"].get(str(i)) or 0) >= 70 for i in range(len(c.modules))) and (p["final_score"] or 0) >= 70:
        c.status, c.completed_at = "completed", datetime.utcnow()
        log_activity(db, "academy", "course", f"Curso completado: {c.title}")


@router.get("/exams")
def list_exams(db: DB, subject_id: int | None = None, course_id: int | None = None) -> list[dict]:
    s = select(LfAssessment).order_by(LfAssessment.id.desc()).limit(100)
    if subject_id:
        s = s.where(LfAssessment.subject_id == subject_id)
    if course_id:
        s = s.where(LfAssessment.course_id == course_id)
    names = {x.id: x.name for x in db.scalars(select(LfSubject))}
    return [row(a, ("questions", "answers", "criteria")) | {"subject": names.get(a.subject_id), "n": len(a.questions)} for a in db.scalars(s)]


@router.get("/exams/{aid}")
def get_exam(aid: int, db: DB) -> dict:
    a = _get(db, LfAssessment, aid)
    d = row(a)
    if a.score is None:
        d["questions"] = [_public_q(q) for q in a.questions]
    return d


# ───────── repasos y aprendizaje adaptativo ─────────
@router.get("/reviews")
def reviews(db: DB) -> dict:
    today = date.today()
    cs = list(db.scalars(select(AcConcept).where(AcConcept.due_on.is_not(None)).order_by(AcConcept.due_on)))
    names = {x.id: x.name for x in db.scalars(select(LfSubject))}
    cal: dict[str, list] = {}
    for c in cs:
        if c.due_on <= today + timedelta(days=21):
            cal.setdefault(max(c.due_on, today).isoformat(), []).append({"id": c.id, "name": c.name, "subject": names.get(c.subject_id)})
    return {"due": [tracker.concept_dict(c) | {"subject": names.get(c.subject_id)} for c in cs if c.due_on <= today],
            "calendar": [{"day": k, "items": v} for k, v in sorted(cal.items())],
            "patterns": [tracker.concept_dict(c) | {"subject": names.get(c.subject_id)} for c in db.scalars(select(AcConcept)) if tracker.error_pattern(c)]}


@router.post("/reviews/start", status_code=201)
async def start_review(db: DB) -> dict:
    today = date.today()
    due = list(db.scalars(select(AcConcept).where(AcConcept.due_on <= today).order_by(AcConcept.due_on)))
    if not due:
        raise HTTPException(409, "No tienes repasos pendientes hoy")
    by: dict[int, list] = {}
    for c in due:
        by.setdefault(c.subject_id, []).append(c.name)
    sid = max(by, key=lambda k: len(by[k]))
    prefs = get_prefs(db)
    a = await run_in_threadpool(_create_exam, db, prefs, ExamIn(subject_id=sid, kind="review", topics=by[sid][:8], types=["mcq", "tf", "numeric"], n=min(10, max(3, len(by[sid]) * 2))))
    db.commit()
    return row(a, ("questions", "answers")) | {"questions": [_public_q(q) for q in a.questions]}


@router.post("/reviews/schedule")
def schedule_reviews(db: DB) -> dict:
    """Crea recordatorios en Tareas (y por tanto en el calendario de tareas) para los días con repasos."""
    from atlas.models import Task
    from atlas.services.tasks import create_task
    cal = reviews(db)["calendar"]
    made = 0
    for d in cal[:14]:
        title = f"Repaso VISTAN ACADEMY ({len(d['items'])} conceptos)"
        due = datetime.fromisoformat(d["day"]).replace(hour=18)
        if db.scalar(select(Task).where(Task.title == title, Task.due_at == due)):
            continue
        create_task(db, title=title, description=", ".join(x["name"] for x in d["items"])[:2000], priority="medium", due_at=due, category="academy")
        made += 1
    db.commit()
    return {"created": made}


@router.post("/concepts/{cid}/remediate", status_code=201)
async def remediate(cid: int, db: DB) -> dict:
    """Errores repetidos: patrón → explicación distinta → ejercicios adicionales → nueva evaluación del concepto."""
    c = _get(db, AcConcept, cid)
    s = _get(db, LfSubject, c.subject_id)
    prefs = get_prefs(db)
    r = await run_in_threadpool(_ai, ai.remediate, prefs, s.name, c.name, c.errors or [], tracker.profile(db, s.id))
    a = await run_in_threadpool(_create_exam, db, prefs, ExamIn(subject_id=s.id, kind="review", topics=[c.name], types=["mcq", "tf", "numeric"], n=4))
    db.add(AcTutorMsg(subject_id=s.id, teacher="Academy Coordinator", role="assistant", content=f"Patrón detectado en «{c.name}»: {r['pattern']}\n\n{r['explanation']}", model=r["model"]))
    db.commit()
    return {"remediation": r, "exam": row(a, ("questions", "answers")) | {"questions": [_public_q(q) for q in a.questions]}}


class ConceptPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    reset: bool = False


@router.patch("/concepts/{cid}")
def patch_concept(cid: int, body: ConceptPatch, db: DB) -> dict:
    c = _get(db, AcConcept, cid)
    if body.name:
        c.name, c.key = body.name, tracker.ckey(body.name)
    if body.reset:
        c.mastery, c.state, c.reps, c.lapses, c.correct, c.wrong, c.interval_days, c.due_on, c.history, c.errors, c.first_ok_at = 0, "nuevo", 0, 0, 0, 0, 0, None, [], [], None
    db.commit()
    return tracker.concept_dict(c)


@router.delete("/concepts/{cid}", status_code=204)
def del_concept(cid: int, db: DB) -> None:
    db.delete(_get(db, AcConcept, cid))
    db.commit()


# ───────── seguimiento ─────────
@router.get("/progress")
def progress(db: DB) -> dict:
    st = tracker.stats(db)
    cs = list(db.scalars(select(AcConcept).order_by(AcConcept.last_seen_at.desc())))
    return {"stats": st, "subjects": tracker.subject_progress(db),
            "recent": [tracker.concept_dict(c) for c in cs if c.state == "reciente"][:30],
            "consolidated": [tracker.concept_dict(c) for c in cs if c.state == "consolidado"][:30],
            "learning": [tracker.concept_dict(c) for c in cs if c.state == "aprendiendo"][:30],
            "gamification": tracker.gamification(db, st) if conf(get_prefs(db))["gamification"] else None}


# ───────── investigación ─────────
class ResearchIn(BaseModel):
    question: str = Field(min_length=6, max_length=900)
    subject_id: int | None = None
    course_id: int | None = None


@router.post("/research", status_code=201)
def academy_research(body: ResearchIn, db: DB) -> dict:
    from atlas.research import engine
    r = Research(question=body.question, status="queued", state={})
    db.add(r)
    db.flush()
    lab = AcLab(kind="research", title=body.question[:200], state={"research_id": r.id, "course_id": body.course_id}, subject_id=body.subject_id)
    db.add(lab)
    if body.course_id:
        c = _get(db, AcCourse, body.course_id)
        c.research_ids = [*(c.research_ids or []), r.id]
    log_activity(db, "academy", "research", f"Investigación para estudiar: {body.question[:120]}")
    db.commit()
    engine.start(r.id)
    return row(lab) | {"research": engine.to_dict(r)}


@router.get("/research")
def list_research(db: DB) -> list[dict]:
    from atlas.research import engine
    out = []
    for lab in db.scalars(select(AcLab).where(AcLab.kind == "research").order_by(AcLab.id.desc())):
        r = db.get(Research, lab.state.get("research_id"))
        out.append(row(lab) | {"research": engine.to_dict(r) if r else None})
    return out


@router.post("/research/{lid}/material")
async def research_material(lid: int, db: DB) -> dict:
    """Material de estudio SOLO desde una investigación terminada: lo verificado lleva sus fuentes; lo demás se etiqueta."""
    from atlas.research import engine
    lab = _get(db, AcLab, lid)
    r = db.get(Research, lab.state.get("research_id"))
    if not r or r.status != "done":
        raise HTTPException(409, "La investigación aún no ha terminado")
    full = engine.to_dict(r, full=True)
    s = db.get(LfSubject, lab.subject_id) if lab.subject_id else None
    m = await run_in_threadpool(_ai, ai.study_material, get_prefs(db), s.name if s else "general", full.get("report") or {}, full.get("sources") or [])
    lab.result, lab.status = m, "done"
    db.commit()
    return row(lab)


# ───────── itinerarios ─────────
class PathIn(BaseModel):
    goal: str = Field(min_length=6, max_length=1000)
    start_level: int = Field(default=1, ge=1, le=5)


@router.post("/paths", status_code=201)
async def create_path(body: PathIn, db: DB) -> dict:
    catalog.ensure(db)
    names = [s.name for s in db.scalars(select(LfSubject))]
    p = await run_in_threadpool(_ai, ai.path, get_prefs(db), body.goal, body.start_level, names, {})
    x = AcPath(title=p["title"], goal=body.goal, start_level=body.start_level, competencies=p["competencies"], steps=p["steps"], model=p["model"])
    db.add(x)
    log_activity(db, "academy", "path", f"Itinerario creado: {x.title}")
    db.commit()
    return _path_dict(db, x)


def _path_dict(db, p: AcPath) -> dict:  # noqa: ANN001
    steps = []
    prev_ok = True
    for st in p.steps:
        c = db.get(AcCourse, st.get("course_id")) if st.get("course_id") else None
        best = db.scalar(select(func.max(LfAssessment.score)).where(LfAssessment.course_id == c.id, LfAssessment.kind.in_(("final", "module")))) if c else None
        done = bool(c and c.status == "completed" and (best or 0) >= st.get("min_score", 70))
        steps.append({**st, "course_status": c.status if c else None, "best_score": best, "passed": done, "unlocked": prev_ok})
        prev_ok = done
    return row(p) | {"steps": steps}


@router.get("/paths")
def list_paths(db: DB) -> list[dict]:
    return [_path_dict(db, p) for p in db.scalars(select(AcPath).order_by(AcPath.id.desc()))]


class PathPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    steps: list[dict] | None = None
    status: str | None = Field(default=None, pattern="^(active|paused|archived)$")


@router.patch("/paths/{pid}")
def patch_path(pid: int, body: PathPatch, db: DB) -> dict:
    p = _get(db, AcPath, pid)
    ch = body.model_dump(exclude_unset=True)
    if "steps" in ch:
        ch["steps"] = [{"title": str(s.get("title"))[:200], "subject": str(s.get("subject") or "")[:80], "why": str(s.get("why") or "")[:500],
                        "evaluation": str(s.get("evaluation") or "")[:300], "project": str(s.get("project") or "")[:500],
                        "min_score": max(50, min(100, int(s.get("min_score") or 70))), "course_id": s.get("course_id")} for s in ch["steps"] or [] if s.get("title")]
    for k, v in ch.items():
        setattr(p, k, v)
    db.commit()
    return _path_dict(db, p)


@router.delete("/paths/{pid}", status_code=204)
def del_path(pid: int, db: DB) -> None:
    db.delete(_get(db, AcPath, pid))
    db.commit()


@router.post("/paths/{pid}/steps/{i}/course", status_code=201)
async def path_course(pid: int, i: int, db: DB) -> dict:
    p = _get(db, AcPath, pid)
    if i >= len(p.steps):
        raise HTTPException(404, "Paso no encontrado")
    st = p.steps[i]
    s = db.scalar(select(LfSubject).where(or_(LfSubject.name == st.get("subject"), LfSubject.key == catalog.slug(st.get("subject") or ""))))
    c = await create_course(CourseIn(request=f"{st['title']}. Objetivo del itinerario: {p.goal}", subject_id=s.id if s else None, path_id=p.id), db)
    steps = list(p.steps)
    steps[i] = {**st, "course_id": c["id"]}
    p.steps = steps
    db.commit()
    return c


# ───────── laboratorios ─────────
class CompoundIn(BaseModel):
    start: float = Field(ge=0, le=1e9)
    monthly: float = Field(ge=0, le=1e7)
    rate_pct: float = Field(ge=-20, le=40)
    years: int = Field(ge=1, le=60)
    inflation_pct: float = Field(default=0, ge=0, le=30)


@router.post("/labs/finance/compound")
def lab_compound(body: CompoundIn) -> dict:
    return labs.compound(**body.model_dump())


class BudgetIn(BaseModel):
    income: float = Field(gt=0, le=1e8)
    needs: float = Field(ge=0, le=1e8)
    wants: float = Field(ge=0, le=1e8)
    savings: float = Field(ge=0, le=1e8)


@router.post("/labs/finance/budget")
def lab_budget(body: BudgetIn) -> dict:
    return labs.budget(**body.model_dump())


class RiskIn(BaseModel):
    amount: float = Field(gt=0, le=1e9)
    mean_pct: float = Field(ge=-30, le=40)
    vol_pct: float = Field(ge=0, le=100)
    years: int = Field(ge=1, le=40)


@router.post("/labs/finance/risk")
def lab_risk(body: RiskIn) -> dict:
    return labs.risk_return(**body.model_dump())


class BizIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    model: str = Field(min_length=2, max_length=300)
    market_demand: float = Field(gt=0, le=1e7)
    competitor_price: float = Field(gt=0, le=1e7)
    elasticity: float = Field(default=1.5, ge=0.2, le=5)


@router.post("/labs/business", status_code=201)
def lab_business(body: BizIn, db: DB) -> dict:
    x = AcLab(kind="business", title=body.name, state=body.model_dump() | {"rounds": []})
    db.add(x)
    db.commit()
    return row(x)


class RoundIn(BaseModel):
    price: float = Field(gt=0, le=1e7)
    unit_cost: float = Field(ge=0, le=1e7)
    fixed_costs: float = Field(ge=0, le=1e8)
    marketing: float = Field(default=0, ge=0, le=1e8)
    decision: str | None = Field(default=None, max_length=600)


@router.post("/labs/{lid}/round")
def lab_round(lid: int, body: RoundIn, db: DB) -> dict:
    x = _get(db, AcLab, lid)
    if x.kind != "business" or x.status == "done":
        raise HTTPException(409, "Simulación no disponible")
    st = dict(x.state)
    res = labs.business_round({**st, **body.model_dump()})
    st["rounds"] = [*st.get("rounds", []), {"n": len(st.get("rounds", [])) + 1, "input": body.model_dump(), "result": res}]
    x.state = st
    db.commit()
    return row(x)


@router.post("/labs/{lid}/finish")
def lab_finish(lid: int, db: DB) -> dict:
    x = _get(db, AcLab, lid)
    if x.kind == "business":
        ev = labs.business_eval(x.state.get("rounds", []))
        if not ev:
            raise HTTPException(409, "Juega al menos una ronda")
        x.result, x.score = ev, ev["score"]
    x.status = "done"
    log_activity(db, "academy", "lab", f"Laboratorio completado: {x.title}")
    db.commit()
    return row(x)


class BacktestIn(BaseModel):
    symbol: str | None = Field(default=None, max_length=30)
    closes: list[float] | None = Field(default=None, max_length=5000)
    strategy: str = Field(default="sma", pattern="^(sma|rsi)$")
    fast: int = Field(default=10, ge=2, le=100)
    slow: int = Field(default=30, ge=3, le=300)
    capital: float = Field(default=10000, gt=0, le=1e9)
    allocation_pct: float = Field(default=100, ge=1, le=100)


@router.post("/labs/trading/backtest", status_code=201)
async def lab_backtest(body: BacktestIn, db: DB) -> dict:
    closes, source = body.closes, "precios introducidos por ti"
    if not closes and body.symbol:
        from atlas.desk import market
        inst = market.instruments(db).get(body.symbol.upper())
        if not inst:
            raise HTTPException(404, f"«{body.symbol}» no está en los instrumentos del Trading Desk; añádelo allí o pega la serie de precios")
        try:
            data = await run_in_threadpool(market.candles, inst, "1d", 500)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(503, f"No se pudieron descargar datos históricos de {body.symbol}: {exc}") from exc
        closes = [float(c["close"]) for c in (data or {}).get("candles", []) if c.get("close") is not None]
        source = f"{body.symbol} · {(data or {}).get('source', 'proveedor de mercado')}"
    if not closes:
        raise HTTPException(422, "Indica un símbolo con datos disponibles o pega una serie de precios de cierre")
    try:
        res = labs.backtest(closes, body.strategy, body.fast, body.slow, body.capital, body.allocation_pct)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    x = AcLab(kind="trading", title=f"Backtest {body.strategy.upper()} · {body.symbol or 'serie propia'}", state=body.model_dump(exclude={"closes"}) | {"source": source, "n": len(closes)},
              result=res, status="done")
    db.add(x)
    log_activity(db, "academy", "lab", f"Backtest educativo ({body.strategy}) sobre {source}")
    db.commit()
    return row(x)


class CodeLabIn(BaseModel):
    level: int = Field(default=1, ge=1, le=5)
    topic: str = Field(default="funciones", min_length=2, max_length=120)
    project_id: int | None = None


@router.post("/labs/programming", status_code=201)
async def lab_code(body: CodeLabIn, db: DB) -> dict:
    e = await run_in_threadpool(_ai, ai.code_exercise, get_prefs(db), body.level, body.topic, _project(db, body.project_id))
    prog = db.scalar(select(LfSubject).where(LfSubject.key == "python"))
    x = AcLab(kind="programming", title=e["title"], state=e | {"level": body.level, "topic": body.topic, "attempts": []}, subject_id=prog.id if prog else None)
    db.add(x)
    db.commit()
    return _lab_public(x)


def _lab_public(x: AcLab) -> dict:
    d = row(x)
    if x.kind == "programming" and x.status != "done":
        d["state"] = {k: v for k, v in x.state.items() if k != "solution"}
    return d


class CodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=20000)


@router.post("/labs/{lid}/submit")
def lab_submit(lid: int, body: CodeIn, db: DB) -> dict:
    x = _get(db, AcLab, lid)
    if x.kind != "programming":
        raise HTTPException(409, "No es un ejercicio de programación")
    sc, why = grading._code(body.code, x.state["tests"])
    st = dict(x.state)
    st["attempts"] = [*st.get("attempts", []), {"at": datetime.utcnow().isoformat(timespec="minutes"), "score": sc, "feedback": why}][-20:]
    x.state, x.score = st, max(x.score or 0, round(sc, 1))
    if sc == 100:
        x.status = "done"
        log_activity(db, "academy", "lab", f"Reto de programación superado: {x.title}")
        if x.subject_id:
            tracker.review(tracker.concept(db, x.subject_id, x.state.get("topic") or x.title), 100.0, "lab")
    db.commit()
    return _lab_public(x) | {"last": {"score": round(sc, 1), "feedback": why}}


@router.post("/labs/critical", status_code=201)
async def lab_critical(db: DB, level: int = 2) -> dict:
    catalog.ensure(db)
    s = db.scalar(select(LfSubject).where(LfSubject.key == "pensamiento-critico"))
    g = await run_in_threadpool(_ai, ai.critical_set, get_prefs(db), level)
    if not g["questions"]:
        raise HTTPException(503, "El modelo no devolvió desafíos válidos")
    a = LfAssessment(subject_id=s.id, kind="critical", topic="Pensamiento crítico", difficulty=level, questions=g["questions"], model=g["model"],
                     criteria={"note": grading.CRITERIA_NOTE})
    db.add(a)
    db.commit()
    return row(a, ("questions", "answers")) | {"questions": [_public_q(q) for q in a.questions]}


@router.get("/labs")
def list_labs(db: DB, kind: str | None = None) -> list[dict]:
    s = select(AcLab).where(AcLab.kind != "research").order_by(AcLab.id.desc()).limit(60)
    if kind:
        s = s.where(AcLab.kind == kind)
    return [_lab_public(x) for x in db.scalars(s)]


@router.get("/labs/{lid}")
def get_lab(lid: int, db: DB) -> dict:
    return _lab_public(_get(db, AcLab, lid))


# ───────── objetivos (sobre los Objetivos de VISTAN) ─────────
class GoalIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    target_hours: float | None = Field(default=None, gt=0, le=10000)
    deadline: date | None = None


@router.post("/goals", status_code=201)
def add_goal(body: GoalIn, db: DB) -> dict:
    from atlas.services.goals import create_goal
    g = create_goal(db, title=body.title, area="aprendizaje", kind="numeric", unit="h", target_value=body.target_hours, start_value=0,
                    start_date=date.today(), deadline=body.deadline)
    db.commit()
    return {"id": g.id, "title": g.title}


# ───────── memoria educativa (consultar, exportar, borrar) ─────────
@router.get("/memory")
def memory(db: DB) -> dict:
    c = lambda m: db.scalar(select(func.count(m.id))) or 0  # noqa: E731
    return {"courses": c(AcCourse), "lessons": c(LfLesson), "exams": c(LfAssessment), "concepts": c(AcConcept), "tutor_messages": c(AcTutorMsg),
            "sessions": c(AcSession), "labs": c(AcLab), "paths": c(AcPath), "settings": conf(get_prefs(db)),
            "note": "Tus datos educativos viven en tu base de datos local (copias en Seguridad). No se guardan grabaciones de voz."}


@router.get("/export")
def export(db: DB) -> Response:
    data = {"courses": [row(x) for x in db.scalars(select(AcCourse))], "lessons": [row(x) for x in db.scalars(select(LfLesson))],
            "exams": [row(x) for x in db.scalars(select(LfAssessment))], "concepts": [row(x) for x in db.scalars(select(AcConcept))],
            "tutor": [row(x) for x in db.scalars(select(AcTutorMsg))], "sessions": [row(x) for x in db.scalars(select(AcSession))],
            "labs": [row(x) for x in db.scalars(select(AcLab))], "paths": [row(x) for x in db.scalars(select(AcPath))]}
    return Response(json.dumps(data, ensure_ascii=False, indent=1, default=str), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="vistan-academy.json"'})


@router.delete("/memory/{kind}/{oid}", status_code=204)
def forget(kind: str, oid: int, db: DB) -> None:
    model = {"lesson": LfLesson, "exam": LfAssessment, "lab": AcLab, "session": AcSession}.get(kind)
    if not model:
        raise HTTPException(422, "Tipo no válido")
    db.delete(_get(db, model, oid))
    log_activity(db, "academy", "memory", f"Dato educativo eliminado ({kind} #{oid})")
    db.commit()
