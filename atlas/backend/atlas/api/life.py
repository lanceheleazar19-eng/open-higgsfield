"""VISTAN LIFE OS — API. Reutiliza Goals, Tasks, Projects, Finanzas, Memory, Research y Workflows; aquí solo vive lo nuevo.
Ninguna ruta envía mensajes, pagos ni publica nada: todo es registro, análisis y aprendizaje."""

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.brain.base import ProviderError
from atlas.life import ai, lock
from atlas.life import service as sv
from atlas.models import (Goal, LfAsset, LfAssessment, LfCommitment, LfContact, LfDecision, LfFailure, LfHabit, LfHabitLog, LfInteraction,
                          LfLesson, LfMilestone, LfNetWorth, LfOpportunity, LfRadar, LfSimulation, LfSubject, LfVision, Project, Research,
                          Task, Workflow, WorkflowRun)
from atlas.models.base import utcnow
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs

public = APIRouter(prefix="/api/life", tags=["life-os"])
router = APIRouter(prefix="/api/life", tags=["life-os"], dependencies=[Depends(lock.require)])


def _today(db) -> date:  # noqa: ANN001
    return datetime.now(ZoneInfo(str(get_prefs(db)["timezone"]))).date()


def _d(v: Any) -> Any:
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def row(o: Any, skip: tuple = ()) -> dict:
    return {c.name: _d(getattr(o, c.name)) for c in o.__table__.columns if c.name not in skip}


def _get(db, model, oid: int):  # noqa: ANN001, ANN202
    o = db.get(model, oid)
    if not o:
        raise HTTPException(404, "No encontrado")
    return o


def _ai(fn, *a):  # noqa: ANN001, ANN002, ANN202
    try:
        return fn(*a)
    except ProviderError as exc:
        raise HTTPException(503, f"Esta función necesita la IA de VISTAN (Ollama o un modelo en la nube): {exc}") from exc


def _apply(o: Any, body: BaseModel, partial: bool) -> None:
    for k, v in body.model_dump(exclude_unset=partial).items():
        setattr(o, k, v.strip() if isinstance(v, str) else v)


def _remember(db, text: str, kind: str = "note") -> None:  # noqa: ANN001
    from atlas.services.memory import remember
    remember(db, text[:2000], kind=kind, source="manual")


# ───────── Bloqueo con PIN ─────────

class PinIn(BaseModel):
    pin: str = Field(min_length=4, max_length=12)
    current: str | None = None


@public.get("/lock")
def lock_status(request: Request) -> dict:
    return {"enabled": lock.enabled(), "unlocked": lock.unlocked(request)}


@public.post("/lock/unlock")
def unlock(body: PinIn, response: Response, db: DB) -> dict:
    if not lock.verify(body.pin):
        log_activity(db, "security", "life_lock", "Intento fallido de desbloquear LIFE OS")
        db.commit()
        raise HTTPException(401, "PIN incorrecto")
    response.set_cookie(lock.COOKIE, lock.new_session(), httponly=True, samesite="strict", max_age=lock.TTL)
    return {"unlocked": True}


@public.post("/lock/lock")
def relock(request: Request, response: Response) -> dict:
    lock.end_session(request.cookies.get(lock.COOKIE))
    response.delete_cookie(lock.COOKIE)
    return {"unlocked": not lock.enabled()}


@public.put("/lock/pin")
def set_pin(body: PinIn, request: Request, response: Response, db: DB) -> dict:
    if lock.enabled() and not (body.current and lock.verify(body.current)):
        raise HTTPException(401, "Introduce tu PIN actual")
    lock.set_pin(body.pin)
    response.set_cookie(lock.COOKIE, lock.new_session(), httponly=True, samesite="strict", max_age=lock.TTL)
    log_activity(db, "security", "life_lock", "PIN de LIFE OS configurado")
    db.commit()
    return {"enabled": True}


@public.delete("/lock/pin")
def del_pin(body: PinIn, db: DB) -> dict:
    if not lock.verify(body.pin):
        raise HTTPException(401, "PIN incorrecto")
    lock.remove_pin()
    log_activity(db, "security", "life_lock", "PIN de LIFE OS eliminado")
    db.commit()
    return {"enabled": False}


# ───────── Resumen ─────────

@router.get("/overview")
def overview(db: DB) -> dict:
    today = _today(db)
    sv.ensure_subjects(db)
    db.commit()
    due_dec = list(db.scalars(select(LfDecision).where(LfDecision.review_on <= today, LfDecision.outcome.is_(None))))
    fu = list(db.scalars(select(LfContact).where(LfContact.next_followup <= today)))
    disc = sv.discipline_report(db, today)
    return {"growth": sv.growth(db, today), "stalled_goals": sv.stalled_goals(db, today), "discipline_findings": disc["findings"],
            "habits_today": [{"id": h["id"], "name": h["name"], "done": h["done_today"]} for h in disc["habits"] if h["due_today"]],
            "decisions_to_review": [{"id": d.id, "title": d.title, "review_on": d.review_on.isoformat()} for d in due_dec],
            "followups_due": [{"id": c.id, "name": c.name, "date": c.next_followup.isoformat()} for c in fu],
            "overdue_commitments": disc["overdue_commitments"], "networth": sv.networth(db),
            "note": "Indicadores observables calculados con tus registros; ninguno mide tu valor como persona."}


# ───────── Emprendimiento ─────────

class OppIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=8000)
    market: str | None = Field(default=None, max_length=4000)
    customer: str | None = Field(default=None, max_length=4000)
    problem: str | None = Field(default=None, max_length=4000)
    solution: str | None = Field(default=None, max_length=4000)
    competition: str | None = Field(default=None, max_length=4000)
    suppliers: str | None = Field(default=None, max_length=4000)
    business_model: str | None = Field(default=None, max_length=4000)
    marketing: str | None = Field(default=None, max_length=4000)
    launch_plan: str | None = Field(default=None, max_length=4000)
    risks: str | None = Field(default=None, max_length=4000)
    resources: str | None = Field(default=None, max_length=4000)
    next_actions: str | None = Field(default=None, max_length=4000)
    status: str = Field(default="idea", pattern="^(idea|research|validating|building|launched|paused|discarded)$")
    economics: dict = Field(default_factory=dict)
    scores: dict = Field(default_factory=dict)
    swot: dict = Field(default_factory=dict)

    @field_validator("scores")
    @classmethod
    def _scores(cls, v: dict) -> dict:
        for k, x in v.items():
            if k not in sv.OPP_CRITERIA or x is not None and not (isinstance(x, (int, float)) and 1 <= x <= 5):
                raise ValueError("Puntuaciones de 1 a 5 en criterios conocidos")
        return v


class OppPatch(OppIn):
    name: str | None = Field(default=None, min_length=1, max_length=160)  # type: ignore[assignment]
    status: str | None = Field(default=None, pattern="^(idea|research|validating|building|launched|paused|discarded)$")  # type: ignore[assignment]


def opp_dict(o: LfOpportunity) -> dict:
    return row(o) | {"calc": sv.economics(o.economics or {}), "score": sv.opp_score(o.scores or {})}


@router.get("/opportunities")
def opps(db: DB) -> dict:
    return {"items": [opp_dict(o) for o in db.scalars(select(LfOpportunity).order_by(LfOpportunity.updated_at.desc()))],
            "criteria": {k: v[0] for k, v in sv.OPP_CRITERIA.items()}}


@router.post("/opportunities", status_code=201)
def opp_create(body: OppIn, db: DB) -> dict:
    o = LfOpportunity()
    _apply(o, body, False)
    db.add(o)
    log_activity(db, "life", "opportunity", f"Oportunidad registrada: {o.name}")
    db.commit()
    return opp_dict(o)


@router.patch("/opportunities/{oid}")
def opp_patch(oid: int, body: OppPatch, db: DB) -> dict:
    o = _get(db, LfOpportunity, oid)
    _apply(o, body, True)
    db.commit()
    return opp_dict(o)


@router.delete("/opportunities/{oid}")
def opp_del(oid: int, db: DB) -> dict:
    db.delete(_get(db, LfOpportunity, oid))
    db.commit()
    return {"ok": True}


@router.post("/opportunities/{oid}/research", status_code=201)
def opp_research(oid: int, db: DB) -> dict:
    from atlas.research import engine as rengine
    o = _get(db, LfOpportunity, oid)
    q = (f"Investigación de mercado para la idea de negocio «{o.name}»: {o.description or ''}. Mercado: {o.market or 'por definir'}. "
         f"Cliente: {o.customer or 'por definir'}. Busca tamaño de mercado, competidores, precios, tendencias y riesgos, con fuentes.")
    r = Research(question=q[:900], status="queued", state={})
    db.add(r)
    db.flush()
    o.research_id = r.id
    log_activity(db, "research", "start", f"Investigación de mercado: {o.name}")
    db.commit()
    rengine.start(r.id)
    return {"research_id": r.id}


@router.post("/opportunities/{oid}/analyze")
async def opp_analyze(oid: int, db: DB) -> dict:
    from atlas.research.engine import to_dict as rdict
    o = _get(db, LfOpportunity, oid)
    research = None
    if o.research_id:
        r = db.get(Research, o.research_id)
        if r and r.status == "done":
            research = rdict(r, full=True)
    rep = await run_in_threadpool(_ai, ai.business_report, get_prefs(db), opp_dict(o) | {"report": None}, research)
    o.report = rep | {"generated_at": utcnow().isoformat(), "used_research": bool(research)}
    db.commit()
    return opp_dict(o)


@router.post("/opportunities/{oid}/project", status_code=201)
def opp_project(oid: int, db: DB) -> dict:
    o = _get(db, LfOpportunity, oid)
    if o.project_id and db.get(Project, o.project_id):
        raise HTTPException(409, "Esta oportunidad ya tiene un proyecto")
    p = Project(name=o.name, description=(o.description or "") + "\n\nCreado desde LIFE OS · Entrepreneur Intelligence", status="active")
    db.add(p)
    db.flush()
    o.project_id = p.id
    for line in (o.next_actions or "").splitlines():
        if line.strip(" -•\t"):
            db.add(Task(title=line.strip(" -•\t")[:300], project_id=p.id, category="negocio"))
    db.commit()
    return {"project_id": p.id}


# ───────── Patrimonio ─────────

class AssetIn(BaseModel):
    side: str = Field(pattern="^(asset|liability)$")
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=40)
    scope: str = Field(default="personal", pattern="^(personal|business)$")
    basis: str = Field(default="real", pattern="^(real|estimated)$")
    value: float = Field(ge=0, le=1e12)
    currency: str = Field(default="EUR", pattern="^[A-Z]{3}$")
    notes: str | None = Field(default=None, max_length=2000)


@router.get("/wealth")
def wealth(db: DB) -> dict:
    from atlas.models import BtBankroll, TdAccount
    today = _today(db)
    virtual = [{"name": a.name, "kind": "Trading Desk (virtual)", "value": a.cash} for a in db.scalars(select(TdAccount).where(TdAccount.active.is_(True)))]
    virtual += [{"name": b.name, "kind": "Paper Betting (ficticio)", "value": b.balance} for b in db.scalars(select(BtBankroll).where(BtBankroll.active.is_(True)))]
    return {"networth": sv.networth(db), "items": [row(a) for a in db.scalars(select(LfAsset).order_by(LfAsset.side, LfAsset.value.desc()))],
            "history": [row(n) for n in db.scalars(select(LfNetWorth).order_by(LfNetWorth.day))], "savings": sv.savings_stats(db, today),
            "virtual": virtual, "labels": {"real": "Dinero real registrado", "estimated": "Valor estimado", "virtual": "Dinero virtual (simulaciones)",
                                           "business": "Capital de negocios", "simulation": "Simulación de inversión"}}


@router.post("/wealth/items", status_code=201)
def asset_add(body: AssetIn, db: DB) -> dict:
    a = LfAsset()
    _apply(a, body, False)
    db.add(a)
    db.flush()
    sv.snapshot_networth(db, _today(db))
    db.commit()
    return row(a)


@router.patch("/wealth/items/{aid}")
def asset_patch(aid: int, body: AssetIn, db: DB) -> dict:
    a = _get(db, LfAsset, aid)
    _apply(a, body, False)
    sv.snapshot_networth(db, _today(db))
    db.commit()
    return row(a)


@router.delete("/wealth/items/{aid}")
def asset_del(aid: int, db: DB) -> dict:
    db.delete(_get(db, LfAsset, aid))
    db.flush()
    sv.snapshot_networth(db, _today(db))
    db.commit()
    return {"ok": True}


class SimIn(BaseModel):
    start: float = Field(ge=0, le=1e10)
    monthly: float = Field(ge=-1e8, le=1e8)
    annual_return_pct: float = Field(ge=-50, le=50)
    years: int = Field(ge=1, le=60)
    inflation_pct: float = Field(default=0, ge=-5, le=30)


@router.post("/wealth/simulate")
def wealth_sim(body: SimIn) -> dict:
    return sv.simulate(body.start, body.monthly, body.annual_return_pct, body.years, body.inflation_pct)


# ───────── Academia ─────────

@router.get("/academy")
def academy(db: DB) -> list[dict]:
    subs = sv.ensure_subjects(db)
    db.commit()
    return [{"id": s.id, "key": s.key, "name": s.name, "topics": len(s.syllabus or []), "mastery": sv.mastery(db, s.id)} for s in subs]


@router.get("/academy/{sid}")
def subject(sid: int, db: DB) -> dict:
    s = _get(db, LfSubject, sid)
    return {"subject": row(s), "mastery": sv.mastery(db, sid),
            "lessons": [row(x, ("content",)) | {"has_content": True} for x in db.scalars(select(LfLesson).where(LfLesson.subject_id == sid).order_by(LfLesson.id.desc()))],
            "assessments": [row(a, ("questions", "answers")) | {"n": len(a.questions)} for a in db.scalars(select(LfAssessment).where(LfAssessment.subject_id == sid).order_by(LfAssessment.id.desc()))]}


@router.post("/academy/{sid}/syllabus")
async def gen_syllabus(sid: int, db: DB) -> dict:
    s = _get(db, LfSubject, sid)
    temas, model = await run_in_threadpool(_ai, ai.syllabus, get_prefs(db), s.name)
    if not temas:
        raise HTTPException(502, "La IA no devolvió un temario válido; inténtalo de nuevo")
    s.syllabus, s.syllabus_source = temas, f"IA ({model})"
    db.commit()
    return row(s)


class LessonIn(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    level: int = Field(default=1, ge=1, le=5)


@router.post("/academy/{sid}/lessons", status_code=201)
async def gen_lesson(sid: int, body: LessonIn, db: DB) -> dict:
    s = _get(db, LfSubject, sid)
    weak = sv.mastery(db, sid).get("weak_topics", [])
    content, model = await run_in_threadpool(_ai, ai.lesson, get_prefs(db), s.name, body.topic, body.level, weak)
    if not content.get("explicacion"):
        raise HTTPException(502, "La IA no devolvió una lección válida; inténtalo de nuevo")
    lesson = LfLesson(subject_id=sid, topic=body.topic, level=body.level, content=content, model=model)
    db.add(lesson)
    db.commit()
    return row(lesson)


@router.get("/lessons/{lid}")
def get_lesson(lid: int, db: DB) -> dict:
    return row(_get(db, LfLesson, lid))


@router.post("/lessons/{lid}/complete")
def complete_lesson(lid: int, db: DB) -> dict:
    x = _get(db, LfLesson, lid)
    x.completed_at = x.completed_at or utcnow()
    db.commit()
    return row(x, ("content",))


class AssessIn(BaseModel):
    kind: str = Field(default="quiz", pattern="^(quiz|exam|exercise)$")
    topic: str | None = Field(default=None, max_length=200)
    difficulty: int | None = Field(default=None, ge=1, le=5)


@router.post("/academy/{sid}/assessments", status_code=201)
async def gen_assessment(sid: int, body: AssessIn, db: DB) -> dict:
    s = _get(db, LfSubject, sid)
    m = sv.mastery(db, sid)
    diff = body.difficulty or max(1, min(5, (m["level"] or 1) + (1 if (m["avg"] or 0) >= 75 else 0)))  # dificultad adaptativa
    qs, model = await run_in_threadpool(_ai, ai.quiz, get_prefs(db), s.name, body.topic, diff, body.kind, m.get("weak_topics", []))
    if not qs:
        raise HTTPException(502, "La IA no devolvió preguntas válidas; inténtalo de nuevo")
    a = LfAssessment(subject_id=sid, kind=body.kind, topic=body.topic, difficulty=diff, questions=qs, model=model)
    db.add(a)
    db.commit()
    return row(a) | {"questions": [{k: v for k, v in q.items() if k not in ("answer", "explanation", "rubric")} for q in qs]}


class SubmitIn(BaseModel):
    answers: list[Any] = Field(max_length=30)


@router.post("/assessments/{aid}/submit")
async def submit(aid: int, body: SubmitIn, db: DB) -> dict:
    a = _get(db, LfAssessment, aid)
    if a.score is not None:
        raise HTTPException(409, "Esta evaluación ya está corregida")
    if len(body.answers) != len(a.questions):
        raise HTTPException(422, "Responde todas las preguntas (puedes dejar en blanco las abiertas)")
    s = db.get(LfSubject, a.subject_id)
    results: list[dict] = []
    opens = [(i, q) for i, q in enumerate(a.questions) if q["type"] == "open"]
    graded: list[dict] = []
    if opens:
        items = [{"pregunta": q["q"], "rubrica": q.get("rubric"), "respuesta": str(body.answers[i] or "")} for i, q in opens]
        graded, _ = await run_in_threadpool(_ai, ai.grade_open, get_prefs(db), s.name, items)
    gi = iter(graded)
    for i, q in enumerate(a.questions):
        ans = body.answers[i]
        if q["type"] == "mcq":
            ok = isinstance(ans, int) and ans == q["answer"]
            results.append({"score": 100 if ok else 0, "correct": ok, "answer": q["answer"], "explanation": q.get("explanation"), "topic": q.get("topic")})
        else:
            g = next(gi, {}) or {}
            sc = float(g.get("score") or 0) if str(ans or "").strip() else 0.0
            results.append({"score": max(0, min(100, sc)), "feedback": g.get("feedback"), "model_answer": g.get("mejor_respuesta"), "topic": q.get("topic")})
    score = round(sum(r["score"] for r in results) / len(results), 1)
    weak = sorted({r["topic"] for r in results if r["score"] < 60 and r.get("topic")})
    a.answers, a.score, a.graded_at = body.answers, score, utcnow()
    a.feedback = {"results": results, "weak_topics": weak}
    log_activity(db, "life", "assessment", f"Evaluación de {s.name}: {score:.0f} %")
    db.commit()
    return row(a) | {"mastery": sv.mastery(db, a.subject_id)}


@router.get("/assessments/{aid}")
def get_assessment(aid: int, db: DB) -> dict:
    a = _get(db, LfAssessment, aid)
    d = row(a)
    if a.score is None:  # no se revelan las respuestas antes de corregir
        d["questions"] = [{k: v for k, v in q.items() if k not in ("answer", "explanation", "rubric")} for q in a.questions]
    return d


# ───────── Simulador (liderazgo y comunicación) ─────────

@router.get("/scenarios")
def scenarios() -> dict:
    return ai.SCENARIOS


class SimStart(BaseModel):
    scenario: str


@router.post("/sims", status_code=201)
async def sim_start(body: SimStart, db: DB) -> dict:
    sc = ai.SCENARIOS.get(body.scenario)
    if not sc:
        raise HTTPException(404, "Escenario desconocido")
    first, _ = await run_in_threadpool(_ai, ai.sim_reply, get_prefs(db), sc, [])
    s = LfSimulation(area=sc["area"], scenario=body.scenario, title=sc["title"], transcript=[{"role": "counterpart", "content": first}])
    db.add(s)
    db.commit()
    return row(s) | {"brief": sc["brief"], "role": sc["role"]}


class SayIn(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


@router.post("/sims/{sid}/say")
async def sim_say(sid: int, body: SayIn, db: DB) -> dict:
    s = _get(db, LfSimulation, sid)
    if s.status != "active":
        raise HTTPException(409, "La simulación ya terminó")
    tr = [*s.transcript, {"role": "user", "content": body.text.strip()}]
    reply, _ = await run_in_threadpool(_ai, ai.sim_reply, get_prefs(db), ai.SCENARIOS[s.scenario], tr)
    s.transcript = [*tr, {"role": "counterpart", "content": reply}]
    db.commit()
    return row(s)


@router.post("/sims/{sid}/finish")
async def sim_finish(sid: int, db: DB) -> dict:
    s = _get(db, LfSimulation, sid)
    if not any(m["role"] == "user" for m in s.transcript):
        raise HTTPException(422, "Interviene al menos una vez antes de terminar")
    deb, model = await run_in_threadpool(_ai, ai.sim_debrief, get_prefs(db), ai.SCENARIOS[s.scenario], s.transcript)
    s.debrief, s.status, s.finished_at = deb | {"model": model}, "finished", utcnow()
    log_activity(db, "life", "simulation", f"Simulación terminada: {s.title}")
    db.commit()
    return row(s)


@router.get("/sims")
def sims(db: DB, area: str | None = None) -> list[dict]:
    q = select(LfSimulation)
    if area:
        q = q.where(LfSimulation.area == area)
    return [row(s, ("transcript",)) for s in db.scalars(q.order_by(LfSimulation.id.desc()).limit(100))]


@router.get("/sims/{sid}")
def sim_get(sid: int, db: DB) -> dict:
    s = _get(db, LfSimulation, sid)
    sc = ai.SCENARIOS.get(s.scenario, {})
    return row(s) | {"brief": sc.get("brief"), "role": sc.get("role")}


# ───────── Disciplina ─────────

class HabitIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="custom", pattern="^(reading|training|sleep|work|study|distraction|custom)$")
    kind: str = Field(default="check", pattern="^(check|amount)$")
    target: float | None = Field(default=None, ge=0, le=100000)
    unit: str | None = Field(default=None, max_length=16)
    limit: bool = False
    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], min_length=1, max_length=7)
    remind_at: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    active: bool = True


@router.get("/discipline")
def discipline(db: DB) -> dict:
    today = _today(db)
    rep = sv.discipline_report(db, today)
    return rep | {"habit_defs": [row(h) for h in db.scalars(select(LfHabit).order_by(LfHabit.id))],
                  "commitments": [row(c) for c in db.scalars(select(LfCommitment).order_by(LfCommitment.due.desc()).limit(200))],
                  "today": today.isoformat()}


@router.post("/habits", status_code=201)
def habit_add(body: HabitIn, db: DB) -> dict:
    if any(d < 0 or d > 6 for d in body.days):
        raise HTTPException(422, "Días de 0 (lunes) a 6 (domingo)")
    h = LfHabit()
    _apply(h, body, False)
    db.add(h)
    db.commit()
    return row(h)


@router.patch("/habits/{hid}")
def habit_patch(hid: int, body: HabitIn, db: DB) -> dict:
    h = _get(db, LfHabit, hid)
    _apply(h, body, False)
    db.commit()
    return row(h)


@router.delete("/habits/{hid}")
def habit_del(hid: int, db: DB) -> dict:
    db.delete(_get(db, LfHabit, hid))
    db.commit()
    return {"ok": True}


class LogIn(BaseModel):
    day: date
    value: float = Field(default=1, ge=0, le=100000)
    note: str | None = Field(default=None, max_length=300)


@router.put("/habits/{hid}/log")
def habit_log(hid: int, body: LogIn, db: DB) -> dict:
    h = _get(db, LfHabit, hid)
    if body.day > _today(db):
        raise HTTPException(422, "No se pueden registrar días futuros")
    lg = db.scalar(select(LfHabitLog).where(LfHabitLog.habit_id == hid, LfHabitLog.day == body.day)) or LfHabitLog(habit_id=hid, day=body.day)
    lg.value, lg.note = body.value, body.note
    db.add(lg)
    db.commit()
    return sv.habit_stats(db, h, _today(db))


@router.delete("/habits/{hid}/log")
def habit_unlog(hid: int, day: date, db: DB) -> dict:
    h = _get(db, LfHabit, hid)
    lg = db.scalar(select(LfHabitLog).where(LfHabitLog.habit_id == hid, LfHabitLog.day == day))
    if lg:
        db.delete(lg)
        db.commit()
    return sv.habit_stats(db, h, _today(db))


class CommitIn(BaseModel):
    period: str = Field(pattern="^(week|month)$")
    title: str = Field(min_length=1, max_length=200)
    due: date
    goal_id: int | None = None
    note: str | None = Field(default=None, max_length=2000)


class CommitPatch(BaseModel):
    status: str = Field(pattern="^(open|done|missed|dropped)$")
    note: str | None = Field(default=None, max_length=2000)


@router.post("/commitments", status_code=201)
def commit_add(body: CommitIn, db: DB) -> dict:
    c = LfCommitment()
    _apply(c, body, False)
    db.add(c)
    db.commit()
    return row(c)


@router.patch("/commitments/{cid}")
def commit_patch(cid: int, body: CommitPatch, db: DB) -> dict:
    c = _get(db, LfCommitment, cid)
    c.status = body.status
    if body.note is not None:
        c.note = body.note
    c.closed_at = utcnow() if body.status != "open" else None
    db.commit()
    return row(c)


@router.delete("/commitments/{cid}")
def commit_del(cid: int, db: DB) -> dict:
    db.delete(_get(db, LfCommitment, cid))
    db.commit()
    return {"ok": True}


# ───────── CRM ─────────

class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=160, pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=40)
    company: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=120)
    relation: str | None = Field(default=None, max_length=60)
    scope: str = Field(default="professional", pattern="^(professional|personal)$")
    interests: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=8000)
    opportunities: str | None = Field(default=None, max_length=4000)
    last_interaction: date | None = None
    next_followup: date | None = None


@router.get("/contacts")
def contacts(db: DB, q: str | None = None) -> list[dict]:
    cs = list(db.scalars(select(LfContact).order_by(LfContact.next_followup.is_(None), LfContact.next_followup, LfContact.name)))
    if q:
        cs = [c for c in cs if q.lower() in f"{c.name} {c.company} {c.role} {c.interests}".lower()]
    return [row(c) for c in cs]


@router.post("/contacts", status_code=201)
def contact_add(body: ContactIn, db: DB) -> dict:
    c = LfContact()
    _apply(c, body, False)
    db.add(c)
    db.commit()
    return row(c)


@router.patch("/contacts/{cid}")
def contact_patch(cid: int, body: ContactIn, db: DB) -> dict:
    c = _get(db, LfContact, cid)
    _apply(c, body, False)
    db.commit()
    return row(c)


@router.delete("/contacts/{cid}")
def contact_del(cid: int, db: DB) -> dict:
    db.delete(_get(db, LfContact, cid))
    log_activity(db, "life", "contact", "Contacto eliminado del CRM")
    db.commit()
    return {"ok": True}


class InteractionIn(BaseModel):
    day: date
    channel: str | None = Field(default=None, max_length=30)
    summary: str = Field(min_length=1, max_length=4000)
    next_followup: date | None = None


@router.get("/contacts/{cid}/interactions")
def interactions(cid: int, db: DB) -> list[dict]:
    return [row(i) for i in db.scalars(select(LfInteraction).where(LfInteraction.contact_id == cid).order_by(LfInteraction.day.desc()))]


@router.post("/contacts/{cid}/interactions", status_code=201)
def interaction_add(cid: int, body: InteractionIn, db: DB) -> dict:
    c = _get(db, LfContact, cid)
    i = LfInteraction(contact_id=cid, day=body.day, channel=body.channel, summary=body.summary.strip())
    db.add(i)
    if not c.last_interaction or body.day >= c.last_interaction:
        c.last_interaction = body.day
    if body.next_followup:
        c.next_followup, c.followup_notified = body.next_followup, None
    db.commit()
    return row(i)


@router.post("/contacts/{cid}/task", status_code=201)
def contact_task(cid: int, db: DB) -> dict:
    """Crea una tarea-recordatorio de seguimiento (no envía nada al contacto)."""
    c = _get(db, LfContact, cid)
    if not c.next_followup:
        raise HTTPException(422, "Pon antes una fecha de próximo seguimiento")
    t = Task(title=f"Seguimiento con {c.name}" + (f" ({c.company})" if c.company else ""), category="relaciones",
             due_at=datetime.combine(c.next_followup, datetime.min.time()).replace(hour=10), all_day=False,
             reminder_at=datetime.combine(c.next_followup, datetime.min.time()).replace(hour=9))
    db.add(t)
    db.commit()
    return {"task_id": t.id}


# ───────── Decisiones ─────────

class DecisionIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    day: date
    area: str | None = Field(default=None, max_length=32)
    context: str | None = Field(default=None, max_length=8000)
    problem: str | None = Field(default=None, max_length=4000)
    options: list[str] = Field(default_factory=list, max_length=12)
    decision: str = Field(min_length=1, max_length=4000)
    reasons: str | None = Field(default=None, max_length=4000)
    expectations: str | None = Field(default=None, max_length=4000)
    risks: str | None = Field(default=None, max_length=4000)
    confidence: int = Field(default=60, ge=0, le=100)
    expected_result: str | None = Field(default=None, max_length=4000)
    review_on: date | None = None
    remember: bool = False


class ReviewIn(BaseModel):
    actual_result: str = Field(min_length=1, max_length=8000)
    outcome: str = Field(pattern="^(better|as_expected|worse)$")
    analyze: bool = True


@router.get("/decisions")
def decisions(db: DB) -> dict:
    today = _today(db)
    ds = list(db.scalars(select(LfDecision).order_by(LfDecision.day.desc(), LfDecision.id.desc())))
    return {"items": [row(d) for d in ds], "due": [d.id for d in ds if d.review_on and d.review_on <= today and not d.outcome],
            "calibration": sv.decision_calibration(db)}


@router.post("/decisions", status_code=201)
def decision_add(body: DecisionIn, db: DB) -> dict:
    d = LfDecision(**body.model_dump(exclude={"remember"}))
    db.add(d)
    if body.remember:
        _remember(db, f"Decisión ({body.day}): {body.title} → {body.decision}", "decision")
    db.commit()
    return row(d)


@router.patch("/decisions/{did}")
def decision_patch(did: int, body: DecisionIn, db: DB) -> dict:
    d = _get(db, LfDecision, did)
    for k, v in body.model_dump(exclude={"remember"}).items():
        setattr(d, k, v)
    db.commit()
    return row(d)


@router.delete("/decisions/{did}")
def decision_del(did: int, db: DB) -> dict:
    db.delete(_get(db, LfDecision, did))
    db.commit()
    return {"ok": True}


@router.post("/decisions/{did}/review")
async def decision_review(did: int, body: ReviewIn, db: DB) -> dict:
    d = _get(db, LfDecision, did)
    d.actual_result, d.outcome, d.reviewed_at = body.actual_result.strip(), body.outcome, utcnow()
    db.commit()
    if body.analyze:
        hist = [row(x, ("analysis",)) for x in db.scalars(select(LfDecision).where(LfDecision.id != did, LfDecision.outcome.is_not(None))
                                                          .order_by(LfDecision.day.desc()).limit(10))]
        data, model = await run_in_threadpool(_ai, ai.decision_review, get_prefs(db), row(d, ("analysis",)), hist)
        d.analysis = data | {"model": model}
        db.commit()
    return row(d) | {"calibration": sv.decision_calibration(db)}


# ───────── Errores ─────────

class FailureIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern="^(project|decision|business|goal|personal)$")
    day: date
    description: str | None = Field(default=None, max_length=8000)
    causes: str | None = Field(default=None, max_length=4000)
    consequences: str | None = Field(default=None, max_length=4000)
    lessons: str | None = Field(default=None, max_length=4000)
    actions: str | None = Field(default=None, max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=12)
    decision_id: int | None = None
    remember: bool = False


@router.get("/failures")
def failures(db: DB) -> dict:
    return {"items": [row(f) for f in db.scalars(select(LfFailure).order_by(LfFailure.day.desc()))], "patterns": sv.failure_patterns(db)}


@router.post("/failures", status_code=201)
def failure_add(body: FailureIn, db: DB) -> dict:
    f = LfFailure(**body.model_dump(exclude={"remember"}) | {"tags": [t.strip()[:40] for t in body.tags if t.strip()]})
    db.add(f)
    if body.remember and body.lessons:
        _remember(db, f"Lección de un error ({body.title}): {body.lessons}")
    db.commit()
    return row(f)


@router.patch("/failures/{fid}")
def failure_patch(fid: int, body: FailureIn, db: DB) -> dict:
    f = _get(db, LfFailure, fid)
    for k, v in body.model_dump(exclude={"remember"}).items():
        setattr(f, k, v)
    db.commit()
    return row(f)


@router.delete("/failures/{fid}")
def failure_del(fid: int, db: DB) -> dict:
    db.delete(_get(db, LfFailure, fid))
    db.commit()
    return {"ok": True}


@router.post("/failures/analyze")
async def failures_analyze(db: DB) -> dict:
    fs = [row(f) for f in db.scalars(select(LfFailure).order_by(LfFailure.day))]
    if len(fs) < 2:
        raise HTTPException(422, "Registra al menos 2 errores para buscar patrones entre ellos")
    data, model = await run_in_threadpool(_ai, ai.failure_analysis, get_prefs(db), fs)
    return data | {"model": model, "patterns": sv.failure_patterns(db)}


# ───────── Objetivos (reutiliza Goals y Tasks) ─────────

@router.get("/goals")
def goals(db: DB) -> dict:
    from atlas.services.goals import metrics
    today = _today(db)
    items = []
    for g in db.scalars(select(Goal).where(Goal.status == "active").order_by(Goal.deadline.is_(None), Goal.deadline)):
        tasks = list(db.scalars(select(Task).where(Task.goal_id == g.id)))
        items.append({"id": g.id, "title": g.title, "area": g.area, "deadline": _d(g.deadline), "horizon": sv.horizon(g),
                      "metrics": metrics(db, g, today), "tasks": len(tasks), "tasks_done": sum(t.status == "done" for t in tasks)})
    return {"items": items, "stalled": sv.stalled_goals(db, today)}


@router.post("/goals/{gid}/plan")
async def goal_plan(gid: int, db: DB) -> dict:
    g = _get(db, Goal, gid)
    today = _today(db)
    data, model = await run_in_threadpool(_ai, ai.goal_plan, get_prefs(db), {"objetivo": g.title, "descripcion": g.description, "area": g.area,
                                                                               "hoy": today.isoformat(), "fecha_limite": _d(g.deadline),
                                                                               "horizonte": sv.horizon(g)})
    return data | {"model": model, "note": "Propuesta: revisa y aplica solo lo que te sirva"}


class PlanApply(BaseModel):
    tasks: list[dict] = Field(max_length=20)


@router.post("/goals/{gid}/plan/apply", status_code=201)
def goal_plan_apply(gid: int, body: PlanApply, db: DB) -> dict:
    g = _get(db, Goal, gid)
    made = 0
    for t in body.tasks:
        title = str(t.get("titulo") or t.get("title") or "").strip()
        if not title:
            continue
        due = None
        try:
            due = datetime.fromisoformat(str(t.get("fecha"))).replace(hour=18) if t.get("fecha") else None
        except ValueError:
            due = None
        pr = t.get("prioridad") if t.get("prioridad") in ("high", "medium", "low") else "medium"
        db.add(Task(title=title[:300], goal_id=g.id, due_at=due, priority=pr, category="hito" if t.get("milestone") else "objetivo"))
        made += 1
    if g.kind == "numeric" and made and not g.target_value:
        g.kind = "milestones"
    log_activity(db, "life", "goal_plan", f"Plan aplicado a «{g.title}»: {made} tareas")
    db.commit()
    return {"created": made}


@router.post("/goals/stalled/advice")
async def stalled_advice(db: DB) -> dict:
    items = sv.stalled_goals(db, _today(db))
    if not items:
        return {"acciones": [], "note": "No hay objetivos estancados"}
    data, model = await run_in_threadpool(_ai, ai.stalled_advice, get_prefs(db), items)
    return data | {"model": model}


# ───────── Radar de oportunidades (usa el motor de investigación) ─────────

LENSES = {"trends": "Tendencias actuales verificables (con datos y fecha) en", "problems": "Problemas y quejas frecuentes de consumidores que podrían convertirse en negocios en",
          "digital": "Oportunidades de negocio digitales (software, contenido, e-commerce) en", "models": "Modelos de negocio emergentes en",
          "markets": "Comparación de mercados (tamaño, crecimiento, competencia, barreras) de", "advantages": "Posibles ventajas competitivas sostenibles para un nuevo entrante en"}


class RadarIn(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    lens: str = Field(pattern="^(trends|problems|digital|models|markets|advantages)$")


@router.post("/radar", status_code=201)
def radar_start(body: RadarIn, db: DB) -> dict:
    from atlas.research import engine as rengine
    r = Research(question=f"{LENSES[body.lens]} {body.query}. Indica fuentes y fechas; no presentes ninguna oportunidad como segura.", status="queued", state={})
    db.add(r)
    db.flush()
    rd = LfRadar(query=body.query, lens=body.lens, research_id=r.id)
    db.add(rd)
    log_activity(db, "research", "start", f"Radar de oportunidades: {body.query}")
    db.commit()
    rengine.start(r.id)
    return row(rd)


@router.get("/radar")
def radar(db: DB) -> list[dict]:
    from atlas.research.engine import to_dict as rdict
    out = []
    for rd in db.scalars(select(LfRadar).order_by(LfRadar.id.desc()).limit(50)):
        r = db.get(Research, rd.research_id)
        out.append(row(rd) | {"research": rdict(r, full=True) if r else None})
    return out


# ───────── Legado / visión ─────────

VISION = {"person": "Qué clase de persona quiero ser", "companies": "Qué empresas quiero construir", "knowledge": "Qué conocimientos quiero adquirir",
          "skills": "Qué habilidades quiero dominar", "wealth": "Qué patrimonio quiero construir", "experiences": "Qué experiencias quiero vivir",
          "relationships": "Qué relaciones quiero cuidar", "impact": "Qué impacto quiero generar", "principles": "Qué principios quiero mantener"}


@router.get("/vision")
def vision(db: DB) -> dict:
    have = {v.section: v for v in db.scalars(select(LfVision))}
    return {"sections": [{"key": k, "label": lbl, "content": have[k].content if k in have else "", "updated_at": _d(have[k].updated_at) if k in have else None}
                         for k, lbl in VISION.items()],
            "timeline": [row(m) for m in db.scalars(select(LfMilestone).order_by(LfMilestone.year, LfMilestone.id))]}


class VisionIn(BaseModel):
    content: str = Field(max_length=8000)
    remember: bool = False


@router.put("/vision/{key}")
def vision_put(key: str, body: VisionIn, db: DB) -> dict:
    if key not in VISION:
        raise HTTPException(404, "Sección desconocida")
    v = db.scalar(select(LfVision).where(LfVision.section == key)) or LfVision(section=key)
    v.content = body.content.strip()
    db.add(v)
    if body.remember and v.content:
        _remember(db, f"Visión de vida · {VISION[key]}: {v.content}", "goal")
    db.commit()
    return {"key": key, "content": v.content}


class MilestoneIn(BaseModel):
    year: int = Field(ge=2000, le=2150)
    title: str = Field(min_length=1, max_length=200)
    area: str | None = Field(default=None, max_length=32)
    status: str = Field(default="planned", pattern="^(planned|achieved|dropped)$")
    goal_id: int | None = None
    notes: str | None = Field(default=None, max_length=4000)


@router.post("/timeline", status_code=201)
def ms_add(body: MilestoneIn, db: DB) -> dict:
    m = LfMilestone(**body.model_dump())
    db.add(m)
    db.commit()
    return row(m)


@router.patch("/timeline/{mid}")
def ms_patch(mid: int, body: MilestoneIn, db: DB) -> dict:
    m = _get(db, LfMilestone, mid)
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    db.commit()
    return row(m)


@router.delete("/timeline/{mid}")
def ms_del(mid: int, db: DB) -> dict:
    db.delete(_get(db, LfMilestone, mid))
    db.commit()
    return {"ok": True}


# ───────── Briefing y revisiones (Workflows existentes) ─────────

@router.get("/reviews")
def reviews(db: DB) -> dict:
    from atlas.workflows import engine as wf
    out = {}
    for key in ("daily_briefing", "weekly_review"):
        w = db.scalar(select(Workflow).where(Workflow.key == key))
        runs = list(db.scalars(select(WorkflowRun).where(WorkflowRun.workflow_id == w.id).order_by(WorkflowRun.id.desc()).limit(26))) if w else []
        out[key] = {"workflow_id": w.id if w else None, "schedule": w.schedule if w else None,
                    "runs": [wf.run_dict(r, w) for r in runs]}
    return out


@router.post("/reviews/{key}/now")
def review_now(key: str, db: DB) -> dict:
    from atlas.workflows import engine as wf
    if key not in ("daily_briefing", "weekly_review"):
        raise HTTPException(404, "Revisión desconocida")
    wf.ensure_builtins(db)
    w = db.scalar(select(Workflow).where(Workflow.key == key))
    run = wf.start(db, w, trigger="manual")
    db.commit()
    return wf.run_dict(run, w)


# ───────── Coach por área ─────────

class CoachIn(BaseModel):
    area: str = Field(pattern="^(entrepreneur|wealth|learning|leadership|discipline|communication|opportunity|decision|planning)$")
    question: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=12)


@router.post("/coach")
async def coach(body: CoachIn, db: DB) -> dict:
    from atlas.agents.tools import TOOLS, Ctx
    tools = {"entrepreneur": ["life.opportunities", "projects.list"], "wealth": ["life.wealth", "finance.summary"],
             "learning": ["life.learning"], "leadership": ["life.simulations"], "communication": ["life.simulations", "life.contacts"],
             "discipline": ["life.discipline", "gym.snapshot"], "opportunity": ["life.radar", "life.opportunities"],
             "decision": ["life.decisions", "life.failures"], "planning": ["life.goals", "tasks.overview", "goals.snapshot"]}[body.area]
    prefs = get_prefs(db)
    c = Ctx(db=db, prefs=prefs, text=body.question, tz=str(prefs["timezone"]))
    ctx = {}
    for t in tools:
        try:
            ctx[t] = TOOLS[t].fn(c)
        except Exception as exc:  # noqa: BLE001 - una herramienta sin datos no debe impedir responder
            ctx[t] = {"error": str(exc)[:200]}
    names = {"entrepreneur": "emprendimiento", "wealth": "patrimonio", "learning": "aprendizaje", "leadership": "liderazgo",
             "communication": "comunicación", "discipline": "disciplina", "opportunity": "oportunidades", "decision": "decisiones", "planning": "planificación"}
    text, model = await run_in_threadpool(_ai, ai.coach, prefs, names[body.area], body.question, ctx, body.history)
    return {"answer": text, "model": model, "used": tools}


# ───────── Memoria ─────────

class RememberIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    kind: str = Field(default="note", pattern="^(preference|goal|decision|fact|note)$")


@router.post("/remember", status_code=201)
def remember_ep(body: RememberIn, db: DB) -> dict:
    _remember(db, body.text, body.kind)
    db.commit()
    return {"ok": True}
