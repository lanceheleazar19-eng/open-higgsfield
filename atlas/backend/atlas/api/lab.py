"""VISTAN INNOVATION LAB — API. Reutiliza Research, Knowledge (RAG/grafo), Memory, Projects/Tasks, Workflows y el
registro de modelos. La ejecución de código solo ocurre en el sandbox, con confirmación explícita y registro."""

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, BeforeValidator, Field, model_validator
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.brain.base import ProviderError
from atlas.config import get_settings
from atlas.integrations.secrets import delete_secret, set_secret
from atlas.lab import ai, arena, sandbox
from atlas.lab import service as sv
from atlas.lab import sources as src
from atlas.models import (IxArenaRun, IxArenaSuite, IxDiscovery, IxExperiment, IxFile, IxIdea, IxLibraryItem, IxLink, IxPatent, IxProjectMeta,
                          IxPrototype, IxResearch, IxSandboxRun, IxScenario, IxTechnology, IxTrial, IxVersion, LfOpportunity, Project,
                          Research, Task)
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs

# Un campo numérico vacío del formulario llega como null: se guarda como 0 (horas/coste no registrados).
Zero = Annotated[float, BeforeValidator(lambda v: 0 if v is None or v == "" else v)]

router = APIRouter(prefix="/api/lab", tags=["innovation-lab"])
CATS = "^(" + "|".join(sv.CATEGORIES) + ")$"
MAT = "^(academic|prototype|commercial|speculative)$"


def _d(v: Any) -> Any:
    return v.isoformat() if isinstance(v, (date, datetime)) else v


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


def _set(o: Any, body: BaseModel, partial: bool = False) -> None:
    for k, v in body.model_dump(exclude_unset=partial).items():
        setattr(o, k, v.strip() if isinstance(v, str) else v)


def _crud(path: str, model: Any, In: type[BaseModel], Patch: type[BaseModel] | None = None, order: Any = None, label: str = "") -> None:
    """Registra listar/crear/editar/borrar para entidades sencillas."""
    def lst(db: DB) -> list[dict]:
        return [row(x) for x in db.scalars(select(model).order_by(order if order is not None else model.id.desc()).limit(1000))]

    def create(body: In, db: DB) -> dict:  # type: ignore[valid-type]
        o = model()
        _set(o, body)
        db.add(o)
        log_activity(db, "lab", "create", f"{label} creado: {getattr(o, 'name', None) or getattr(o, 'title', '')}"[:200])
        db.commit()
        return row(o)

    def patch(oid: int, body: Patch or In, db: DB) -> dict:  # type: ignore[valid-type]
        o = _get(db, model, oid)
        _set(o, body, partial=True)
        db.commit()
        return row(o)

    def delete(oid: int, db: DB) -> dict:
        db.delete(_get(db, model, oid))
        log_activity(db, "lab", "delete", f"{label} #{oid} eliminado")
        db.commit()
        return {"ok": True}
    router.add_api_route(path, lst, methods=["GET"])
    router.add_api_route(path, create, methods=["POST"], status_code=201)
    router.add_api_route(f"{path}/{{oid}}", patch, methods=["PATCH"])
    router.add_api_route(f"{path}/{{oid}}", delete, methods=["DELETE"])


# ───────── Centro de mando y analíticas ─────────

@router.get("/meta")
def meta() -> dict:
    return {"categories": sv.CATEGORIES, "maturity": sv.MATURITY, "states": sv.EXP_STATES, "sources": src.status(),
            "workflows": WORKFLOW_TEMPLATES}


@router.get("/command")
def command(db: DB) -> dict:
    return sv.command_center(db)


@router.get("/analytics")
def analytics(db: DB, start: date | None = None, end: date | None = None, category: str | None = None) -> dict:
    return sv.analytics(db, start, end, category)


# ───────── Technology Radar ─────────

class TechIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(pattern=CATS)
    description: str | None = Field(default=None, max_length=4000)
    maturity: str = Field(default="academic", pattern=MAT)
    watch: bool = True
    entities: list[str] = Field(default_factory=list, max_length=30)
    notes: str | None = Field(default=None, max_length=4000)


class TechPatch(TechIn):
    name: str | None = Field(default=None, min_length=2, max_length=120)  # type: ignore[assignment]
    category: str | None = Field(default=None, pattern=CATS)  # type: ignore[assignment]


_crud("/technologies", IxTechnology, TechIn, TechPatch, IxTechnology.name, "Tecnología")


@router.get("/technologies/{tid}/timeline")
def tech_timeline(tid: int, db: DB) -> dict:
    t = _get(db, IxTechnology, tid)
    ds = list(db.scalars(select(IxDiscovery).where(IxDiscovery.technology_id == tid).order_by(IxDiscovery.published_on.is_(None), IxDiscovery.published_on)))
    by_year: dict[str, dict] = {}
    for d in ds:
        y = str((d.published_on or d.created_at.date()).year)
        by_year.setdefault(y, {"year": y, "total": 0, **{m: 0 for m in sv.MATURITY}})
        by_year[y]["total"] += 1
        by_year[y][d.maturity] += 1
    return {"technology": row(t), "discoveries": [row(d) for d in reversed(ds)], "by_year": list(by_year.values())}


class DiscIn(BaseModel):
    title: str = Field(min_length=3, max_length=400)
    category: str = Field(pattern=CATS)
    technology_id: int | None = None
    kind: str = Field(default="news", pattern="^(paper|patent|news|product|report|note)$")
    maturity: str = Field(pattern=MAT)
    description: str | None = Field(default=None, max_length=8000)
    source_name: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=1000, pattern=r"^$|^https?://")
    published_on: date | None = None
    reliability: str | None = Field(default=None, pattern="^(alta|media|baja)$")

    @model_validator(mode="after")
    def _need_source(self) -> "DiscIn":
        if not (self.source_url or self.source_name):
            raise ValueError("Cada descubrimiento necesita una fuente (URL o nombre)")
        return self


@router.get("/discoveries")
def discoveries(db: DB, category: str | None = None, maturity: str | None = None, technology_id: int | None = None, q: str | None = None) -> list[dict]:
    qy = select(IxDiscovery)
    if category:
        qy = qy.where(IxDiscovery.category == category)
    if maturity:
        qy = qy.where(IxDiscovery.maturity == maturity)
    if technology_id:
        qy = qy.where(IxDiscovery.technology_id == technology_id)
    out = list(db.scalars(qy.order_by(IxDiscovery.id.desc()).limit(500)))
    if q:
        out = [d for d in out if q.lower() in f"{d.title} {d.description}".lower()]
    return [row(d) for d in out]


@router.post("/discoveries", status_code=201)
def add_discovery(body: DiscIn, db: DB) -> dict:
    d = IxDiscovery(**body.model_dump(exclude={"reliability"}), reliability=body.reliability or sv.reliability_for(body.source_url), origin="manual")
    db.add(d)
    db.commit()
    return row(d)


@router.delete("/discoveries/{did}")
def del_discovery(did: int, db: DB) -> dict:
    db.delete(_get(db, IxDiscovery, did))
    db.commit()
    return {"ok": True}


class PapersIn(BaseModel):
    query: str = Field(min_length=3, max_length=200)
    category: str = Field(pattern=CATS)
    technology_id: int | None = None
    sources: list[str] = Field(default_factory=lambda: ["arxiv", "openalex"])


@router.post("/discoveries/papers")
async def fetch_papers(body: PapersIn, db: DB) -> dict:
    res = await run_in_threadpool(sv.import_papers, db, body.query, body.category, body.technology_id,
                                  [s for s in body.sources if s in ("arxiv", "openalex")], 8)
    db.commit()
    return res


@router.get("/papers/search")
async def papers_search(q: str, source: str = "openalex") -> dict:
    try:
        items = await run_in_threadpool(src.arxiv if source == "arxiv" else src.openalex, q, 10)
    except src.SourceError as exc:
        return {"items": [], "error": str(exc)}
    return {"items": items, "error": None}


class CompareIn(BaseModel):
    technology_ids: list[int] = Field(min_length=2, max_length=6)


@router.post("/technologies/compare")
async def compare(body: CompareIn, db: DB) -> dict:
    data = []
    for tid in body.technology_ids:
        t = _get(db, IxTechnology, tid)
        ds = list(db.scalars(select(IxDiscovery).where(IxDiscovery.technology_id == tid).limit(15)))
        data.append({"tecnologia": t.name, "madurez_registrada": sv.MATURITY[t.maturity],
                     "descubrimientos": [{"titulo": d.title, "madurez": d.maturity, "fuente": d.source_url or d.source_name, "fiabilidad": d.reliability} for d in ds]})
    if not any(x["descubrimientos"] for x in data):
        raise HTTPException(422, "Registra descubrimientos de estas tecnologías antes de compararlas")
    out, model = await run_in_threadpool(_ai, ai.compare, get_prefs(db), data)
    return out | {"model": model}


# ───────── Research Lab (Research Engine + publicaciones científicas) ─────────

class ResearchIn(BaseModel):
    question: str = Field(min_length=6, max_length=900)
    category: str | None = Field(default=None, pattern=CATS)
    tags: list[str] = Field(default_factory=list, max_length=12)
    papers: bool = True


@router.get("/research")
def research_list(db: DB, tag: str | None = None, saved: bool | None = None) -> list[dict]:
    from atlas.research.engine import to_dict
    out = []
    for m in db.scalars(select(IxResearch).order_by(IxResearch.id.desc()).limit(200)):
        if tag and tag not in (m.tags or []):
            continue
        if saved is not None and m.saved != saved:
            continue
        r = db.get(Research, m.research_id)
        if r:
            out.append(row(m, ("papers",)) | {"papers_count": len(m.papers or []), "research": to_dict(r)})
    return out


@router.post("/research", status_code=201)
async def research_start(body: ResearchIn, db: DB) -> dict:
    from atlas.research import engine
    r = Research(question=body.question.strip(), status="queued", state={})
    db.add(r)
    db.flush()
    papers, err = [], None
    if body.papers:
        for fn in (src.openalex, src.arxiv):
            try:
                papers += await run_in_threadpool(fn, body.question, 5)
            except src.SourceError as exc:
                err = str(exc)
    m = IxResearch(research_id=r.id, category=body.category, tags=[t.strip()[:40] for t in body.tags if t.strip()], papers=papers)
    db.add(m)
    log_activity(db, "research", "start", f"Innovation Lab: {body.question[:150]}")
    db.commit()
    engine.start(r.id)
    return row(m) | {"papers_error": err}


@router.get("/research/{rid}")
def research_get(rid: int, db: DB) -> dict:
    from atlas.research.engine import to_dict
    m = db.scalar(select(IxResearch).where(IxResearch.research_id == rid))
    r = _get(db, Research, rid)
    return {"meta": row(m) if m else None, "research": to_dict(r, full=True)}


class ResearchPatch(BaseModel):
    tags: list[str] | None = Field(default=None, max_length=12)
    saved: bool | None = None
    category: str | None = Field(default=None, pattern=CATS)


@router.patch("/research/{rid}")
def research_patch(rid: int, body: ResearchPatch, db: DB) -> dict:
    m = db.scalar(select(IxResearch).where(IxResearch.research_id == rid)) or IxResearch(research_id=rid)
    _set(m, body, partial=True)
    db.add(m)
    db.commit()
    return row(m)


@router.post("/research/{rid}/resume")
def research_resume(rid: int, db: DB) -> dict:
    from atlas.research import engine
    r = _get(db, Research, rid)
    if r.status in ("done", "running"):
        raise HTTPException(409, "Esta investigación no necesita reanudarse")
    r.status = "queued"
    db.commit()
    engine.start(r.id)
    return {"ok": True}


class ToDiscIn(BaseModel):
    category: str = Field(pattern=CATS)
    technology_id: int | None = None


@router.post("/research/{rid}/discoveries")
def research_to_discoveries(rid: int, body: ToDiscIn, db: DB) -> dict:
    r = _get(db, Research, rid)
    if r.status != "done":
        raise HTTPException(409, "La investigación aún no ha terminado")
    n = sv.discoveries_from_research(db, r, body.category, body.technology_id)
    m = db.scalar(select(IxResearch).where(IxResearch.research_id == rid))
    for p in (m.papers if m else []) or []:
        if p.get("external_id") and not db.scalar(select(IxDiscovery.id).where(IxDiscovery.external_id == p["external_id"])):
            db.add(IxDiscovery(title=p["title"][:400], category=body.category, technology_id=body.technology_id, kind="paper", maturity="academic",
                               description=(p.get("summary") or "")[:4000], source_name=p["source"], source_url=p["url"],
                               published_on=src.parse_date(p.get("published")), reliability=p["reliability"], origin="research",
                               external_id=p["external_id"], authors=p.get("authors") or []))
            n += 1
    db.commit()
    return {"added": n}


# ───────── Experimentation Engine ─────────

class ExpIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    objective: str | None = Field(default=None, max_length=4000)
    hypothesis: str | None = Field(default=None, max_length=4000)
    description: str | None = Field(default=None, max_length=8000)
    technology: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, pattern=CATS)
    resources: str | None = Field(default=None, max_length=4000)
    variables: str | None = Field(default=None, max_length=4000)
    methodology: str | None = Field(default=None, max_length=8000)
    expected: str | None = Field(default=None, max_length=4000)
    observed: str | None = Field(default=None, max_length=8000)
    evidence: str | None = Field(default=None, max_length=8000)
    conclusion: str | None = Field(default=None, max_length=4000)
    status: str = Field(default="IDEA", pattern="^(IDEA|PLANNED|RUNNING|PAUSED|COMPLETED|FAILED|ARCHIVED)$")
    verdict: str | None = Field(default=None, pattern="^(supported|refuted|inconclusive)$")
    started_on: date | None = None
    finished_on: date | None = None
    hours: Zero = Field(default=0, ge=0, le=100000)
    cost: Zero = Field(default=0, ge=0, le=1e9)


class ExpPatch(ExpIn):
    name: str | None = Field(default=None, min_length=2, max_length=200)  # type: ignore[assignment]
    status: str | None = Field(default=None, pattern="^(IDEA|PLANNED|RUNNING|PAUSED|COMPLETED|FAILED|ARCHIVED)$")  # type: ignore[assignment]


def _check_verdict(e: IxExperiment) -> None:
    """No se marca un experimento como exitoso sin resultados verificables."""
    if e.verdict in ("supported", "refuted") and not ((e.observed or "").strip() and (e.evidence or "").strip()):
        raise HTTPException(422, "Para dar un veredicto hacen falta resultados observados y evidencias registradas")
    if e.status == "COMPLETED" and e.verdict is None and not (e.observed or "").strip():
        raise HTTPException(422, "Un experimento completado necesita resultados observados (o márcalo como fallido)")


@router.get("/experiments")
def experiments(db: DB, status: str | None = None) -> list[dict]:
    q = select(IxExperiment)
    if status:
        q = q.where(IxExperiment.status == status)
    out = []
    for e in db.scalars(q.order_by(IxExperiment.updated_at.desc())):
        n = db.scalar(select(IxTrial.id).where(IxTrial.experiment_id == e.id).order_by(IxTrial.id.desc()).limit(1))
        out.append(row(e) | {"has_trials": bool(n)})
    return out


@router.post("/experiments", status_code=201)
def exp_create(body: ExpIn, db: DB) -> dict:
    e = IxExperiment()
    _set(e, body)
    _check_verdict(e)
    db.add(e)
    log_activity(db, "lab", "experiment", f"Experimento creado: {e.name}")
    db.commit()
    return row(e)


@router.patch("/experiments/{eid}")
def exp_patch(eid: int, body: ExpPatch, db: DB) -> dict:
    e = _get(db, IxExperiment, eid)
    _set(e, body, partial=True)
    if e.status == "RUNNING" and not e.started_on:
        e.started_on = date.today()
    if e.status in ("COMPLETED", "FAILED") and not e.finished_on:
        e.finished_on = date.today()
    _check_verdict(e)
    db.commit()
    return row(e)


@router.delete("/experiments/{eid}")
def exp_del(eid: int, db: DB) -> dict:
    db.delete(_get(db, IxExperiment, eid))
    db.commit()
    return {"ok": True}


class TrialIn(BaseModel):
    version: str = Field(min_length=1, max_length=40)
    params: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    observed: str | None = Field(default=None, max_length=8000)
    evidence: str | None = Field(default=None, max_length=8000)
    outcome: str = Field(default="inconclusive", pattern="^(pass|fail|inconclusive)$")

    @model_validator(mode="after")
    def _verifiable(self) -> "TrialIn":
        if self.outcome != "inconclusive" and not (self.metrics or (self.observed or "").strip()):
            raise ValueError("Un resultado pass/fail necesita métricas o una observación registrada")
        return self


@router.get("/experiments/{eid}/trials")
def trials(eid: int, db: DB) -> dict:
    e = _get(db, IxExperiment, eid)
    ts = list(db.scalars(select(IxTrial).where(IxTrial.experiment_id == eid).order_by(IxTrial.ran_at)))
    keys = sorted({k for t in ts for k in (t.metrics or {})})
    return {"experiment": row(e), "trials": [row(t) for t in ts], "metric_keys": keys,
            "comparison": [{"version": t.version, **{k: (t.metrics or {}).get(k) for k in keys}, "outcome": t.outcome} for t in ts]}


@router.post("/experiments/{eid}/trials", status_code=201)
def trial_add(eid: int, body: TrialIn, db: DB) -> dict:
    _get(db, IxExperiment, eid)
    t = IxTrial(experiment_id=eid, **body.model_dump())
    db.add(t)
    db.commit()
    return row(t)


@router.post("/experiments/{eid}/trials/{tid}/repeat", status_code=201)
def trial_repeat(eid: int, tid: int, db: DB) -> dict:
    """Prepara una repetición con los mismos parámetros (los resultados se registran al ejecutarla)."""
    t = _get(db, IxTrial, tid)
    n = IxTrial(experiment_id=eid, version=f"{t.version}-rep", params=dict(t.params or {}), metrics={}, outcome="inconclusive",
                observed=None, evidence=None)
    db.add(n)
    db.commit()
    return row(n)


@router.delete("/experiments/{eid}/trials/{tid}")
def trial_del(eid: int, tid: int, db: DB) -> dict:
    db.delete(_get(db, IxTrial, tid))
    db.commit()
    return {"ok": True}


@router.post("/experiments/{eid}/design")
async def exp_design(eid: int, db: DB) -> dict:
    e = _get(db, IxExperiment, eid)
    out, model = await run_in_threadpool(_ai, ai.design_experiment, get_prefs(db), row(e))
    return out | {"model": model, "note": "Propuesta del Innovation Agent: revísala antes de aplicarla"}


@router.post("/experiments/{eid}/evaluate")
async def exp_evaluate(eid: int, db: DB) -> dict:
    e = _get(db, IxExperiment, eid)
    ts = [row(t) for t in db.scalars(select(IxTrial).where(IxTrial.experiment_id == eid))]
    out, model = await run_in_threadpool(_ai, ai.evaluate_experiment, get_prefs(db), row(e), ts)
    if not ts and not (e.observed or "").strip():
        out["veredicto_sugerido"] = "inconclusive"
    return out | {"model": model, "note": "Sugerencia: el veredicto lo decides tú y exige resultados registrados"}


# ───────── AI Research Lab: Model Testing Arena ─────────

@router.get("/arena/models")
def arena_models(db: DB) -> list[dict]:
    return arena.available_models(get_prefs(db))


class SuiteIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    tests: list[dict] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _tests(self) -> "SuiteIn":
        for t in self.tests:
            if not str(t.get("prompt") or "").strip():
                raise ValueError("Cada prueba necesita un prompt")
            if t.get("check", "none") not in ("exact", "contains", "regex", "judge", "none"):
                raise ValueError("Comprobación no válida")
            if t.get("check") in ("exact", "contains", "regex") and not str(t.get("expected") or "").strip():
                raise ValueError("Las comprobaciones exacta/contiene/regex necesitan el resultado esperado")
        return self


_crud("/arena/suites", IxArenaSuite, SuiteIn, None, None, "Batería de pruebas")


class ArenaRunIn(BaseModel):
    suite_id: int
    models: list[str] = Field(min_length=1, max_length=8)
    judge: str | None = None


@router.post("/arena/runs", status_code=201)
def arena_run(body: ArenaRunIn, db: DB) -> list[dict]:
    _get(db, IxArenaSuite, body.suite_id)
    avail = {m["id"] for m in arena.available_models(get_prefs(db))}
    bad = [m for m in body.models + ([body.judge] if body.judge else []) if m not in avail]
    if bad:
        raise HTTPException(422, f"Modelos no configurados o no accesibles: {', '.join(bad)}")
    runs = []
    for m in body.models:
        r = IxArenaRun(suite_id=body.suite_id, model=m, judge=body.judge)
        db.add(r)
        db.flush()
        runs.append(r)
    log_activity(db, "lab", "arena", f"Arena: {len(runs)} modelo(s)")
    db.commit()
    for r in runs:
        arena.start(r.id)
    return [row(r) for r in runs]


@router.get("/arena/runs")
def arena_runs(db: DB, suite_id: int | None = None) -> list[dict]:
    q = select(IxArenaRun)
    if suite_id:
        q = q.where(IxArenaRun.suite_id == suite_id)
    return [row(r) for r in db.scalars(q.order_by(IxArenaRun.id.desc()).limit(100))]


# ───────── Prototype Studio + sandbox ─────────

class ProtoIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    kind: str = Field(default="app", pattern="^(app|tool|web|automation|agent|saas|ui|analytics|software)$")
    description: str | None = Field(default=None, max_length=8000)
    problem: str | None = Field(default=None, max_length=4000)
    goal: str | None = Field(default=None, max_length=4000)
    tech: str | None = Field(default=None, max_length=4000)
    architecture: str | None = Field(default=None, max_length=8000)
    tests: str | None = Field(default=None, max_length=8000)
    results: str | None = Field(default=None, max_length=8000)
    status: str = Field(default="concept", pattern="^(concept|building|testing|done|abandoned)$")
    hours: Zero = Field(default=0, ge=0, le=100000)
    cost: Zero = Field(default=0, ge=0, le=1e9)


class ProtoPatch(ProtoIn):
    name: str | None = Field(default=None, min_length=2, max_length=160)  # type: ignore[assignment]
    kind: str | None = Field(default=None, pattern="^(app|tool|web|automation|agent|saas|ui|analytics|software)$")  # type: ignore[assignment]
    status: str | None = Field(default=None, pattern="^(concept|building|testing|done|abandoned)$")  # type: ignore[assignment]


_crud("/prototypes", IxPrototype, ProtoIn, ProtoPatch, IxPrototype.updated_at.desc(), "Prototipo")


@router.get("/prototypes/{pid}/detail")
def proto_detail(pid: int, db: DB) -> dict:
    p = _get(db, IxPrototype, pid)
    return {"prototype": row(p), "versions": [row(v) for v in db.scalars(select(IxVersion).where(IxVersion.prototype_id == pid).order_by(IxVersion.id.desc()))],
            "files": [row(f) for f in db.scalars(select(IxFile).where(IxFile.prototype_id == pid).order_by(IxFile.id.desc()))],
            "runs": [row(r) for r in db.scalars(select(IxSandboxRun).where(IxSandboxRun.prototype_id == pid).order_by(IxSandboxRun.id.desc()).limit(20))]}


class VersionIn(BaseModel):
    version: str = Field(min_length=1, max_length=40)
    notes: str | None = Field(default=None, max_length=8000)


@router.post("/prototypes/{pid}/versions", status_code=201)
def proto_version(pid: int, body: VersionIn, db: DB) -> dict:
    _get(db, IxPrototype, pid)
    v = IxVersion(prototype_id=pid, **body.model_dump())
    db.add(v)
    db.commit()
    return row(v)


def _lab_dir():  # noqa: ANN202
    d = get_settings().resolved_data_dir / "private" / "lab"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


ALLOWED = {"image/png", "image/jpeg", "image/webp", "text/plain", "text/markdown", "text/csv", "application/json", "application/pdf",
           "text/x-python", "application/x-python-code", "text/javascript", "application/javascript", "text/html", "text/css", "application/zip"}


@router.post("/prototypes/{pid}/files", status_code=201)
async def proto_file(pid: int, db: DB, file: UploadFile = File(...), version_id: int | None = Form(default=None)) -> dict:
    import secrets
    _get(db, IxPrototype, pid)
    data = await file.read()
    if len(data) > 15_000_000:
        raise HTTPException(413, "Máximo 15 MB por archivo")
    mime = (file.content_type or "application/octet-stream").split(";")[0]
    name = (file.filename or "archivo")[:200]
    if mime not in ALLOWED and not name.endswith((".py", ".md", ".txt", ".json", ".csv", ".ts", ".tsx", ".js", ".html", ".css")):
        raise HTTPException(415, "Tipo de archivo no admitido")
    stored = secrets.token_hex(12)
    path = _lab_dir() / stored
    path.write_bytes(data)
    path.chmod(0o600)
    f = IxFile(prototype_id=pid, version_id=version_id, name=name, stored=stored, mime=mime, size=len(data), is_image=mime.startswith("image/"))
    db.add(f)
    db.commit()
    return row(f)


@router.get("/files/{fid}")
def get_file(fid: int, db: DB) -> FileResponse:
    f = _get(db, IxFile, fid)
    # Siempre como descarga/imagen: nunca se interpreta HTML/JS del prototipo en el origen de VISTAN
    media = f.mime if f.is_image else "application/octet-stream"
    return FileResponse(_lab_dir() / f.stored, media_type=media, filename=f.name,
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})


@router.delete("/files/{fid}")
def del_file(fid: int, db: DB) -> dict:
    f = _get(db, IxFile, fid)
    (_lab_dir() / f.stored).unlink(missing_ok=True)
    db.delete(f)
    db.commit()
    return {"ok": True}


class SandboxIn(BaseModel):
    code: str = Field(min_length=1, max_length=sandbox.MAX_CODE)
    prototype_id: int | None = None
    confirm: bool = False


@router.post("/sandbox/run")
async def sandbox_run(body: SandboxIn, db: DB) -> dict:
    if not body.confirm:
        raise HTTPException(428, "Confirma la ejecución: el código se ejecutará en el sandbox aislado (sin red, sin tus archivos, 10 s)")
    res = await run_in_threadpool(sandbox.run_python, body.code)
    r = IxSandboxRun(prototype_id=body.prototype_id, code=body.code, **res)
    db.add(r)
    log_activity(db, "lab", "sandbox", f"Código ejecutado en el sandbox ({res['status']}, {res['duration_ms']} ms)")
    db.commit()
    return row(r)


# ───────── Biblioteca científica ─────────

class LibIn(BaseModel):
    kind: str = Field(pattern="^(paper|article|patent|report|docs|book|publication|experiment|note|discovery|link)$")
    title: str = Field(min_length=2, max_length=400)
    authors: list[str] = Field(default_factory=list, max_length=40)
    url: str | None = Field(default=None, max_length=1000, pattern=r"^$|^https?://")
    published_on: date | None = None
    origin: str = Field(default="external", pattern="^(own|external)$")
    category: str | None = Field(default=None, pattern=CATS)
    tags: list[str] = Field(default_factory=list, max_length=20)
    summary: str | None = Field(default=None, max_length=8000)
    notes: str | None = Field(default=None, max_length=20000)


class LibPatch(LibIn):
    kind: str | None = Field(default=None, pattern="^(paper|article|patent|report|docs|book|publication|experiment|note|discovery|link)$")  # type: ignore[assignment]
    title: str | None = Field(default=None, min_length=2, max_length=400)  # type: ignore[assignment]


@router.get("/library")
def library(db: DB, q: str | None = None, kind: str | None = None, tag: str | None = None, category: str | None = None) -> list[dict]:
    qy = select(IxLibraryItem)
    if kind:
        qy = qy.where(IxLibraryItem.kind == kind)
    if category:
        qy = qy.where(IxLibraryItem.category == category)
    items = list(db.scalars(qy.order_by(IxLibraryItem.id.desc()).limit(1000)))
    if tag:
        items = [i for i in items if tag in (i.tags or [])]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in f"{i.title} {i.summary} {i.notes} {' '.join(i.concepts or [])} {' '.join(i.authors or [])}".lower()]
    return [row(i) for i in items]


@router.post("/library", status_code=201)
def lib_add(body: LibIn, db: DB) -> dict:
    i = IxLibraryItem()
    _set(i, body)
    db.add(i)
    db.commit()
    return row(i)


@router.patch("/library/{iid}")
def lib_patch(iid: int, body: LibPatch, db: DB) -> dict:
    i = _get(db, IxLibraryItem, iid)
    _set(i, body, partial=True)
    db.commit()
    return row(i)


@router.delete("/library/{iid}")
def lib_del(iid: int, db: DB) -> dict:
    db.delete(_get(db, IxLibraryItem, iid))
    db.commit()
    return {"ok": True}


@router.post("/library/{iid}/index")
def lib_index(iid: int, db: DB) -> dict:
    """Añade el elemento a la base de conocimiento (RAG + grafo) de VISTAN, indicando su origen."""
    from atlas.knowledge.service import ingest
    i = _get(db, IxLibraryItem, iid)
    text = f"{i.title}\n{'Autores: ' + ', '.join(i.authors) if i.authors else ''}\nOrigen: {'propio' if i.origin == 'own' else 'fuente externa'} {i.url or ''}\n\n{i.summary or ''}\n\n{i.notes or ''}"
    if len(text.strip()) < 40:
        raise HTTPException(422, "Añade un resumen o notas antes de indexarlo")
    doc = ingest(db, title=f"[Lab] {i.title}", kind="text", text_=text, url=i.url, prefs=get_prefs(db))
    i.document_id = doc.id
    db.commit()
    return {"document_id": doc.id}


@router.post("/library/{iid}/extract")
async def lib_extract(iid: int, db: DB) -> dict:
    i = _get(db, IxLibraryItem, iid)
    text = f"{i.summary or ''}\n{i.notes or ''}"
    if len(text.strip()) < 80:
        raise HTTPException(422, "Hace falta el texto (resumen o notas) para extraer conceptos: no se inventa el contenido")
    out, model = await run_in_threadpool(_ai, ai.extract, get_prefs(db), {"titulo": i.title, "tipo": i.kind}, text)
    i.concepts = [str(c)[:80] for c in out.get("conceptos", [])][:12]
    if not i.summary and out.get("resumen"):
        i.summary = out["resumen"]
    db.commit()
    return row(i) | {"extraction": out, "model": model}


@router.get("/library/search/rag")
def lib_rag(q: str, db: DB) -> dict:
    from atlas.knowledge.service import search
    hits = search(db, q, k=8)
    return {"hits": hits, "note": "Fragmentos de tu base de conocimiento: [Lab] = elementos del laboratorio; el resto, tus documentos."}


# ───────── Referencias cruzadas ─────────

class LinkIn(BaseModel):
    a_type: str = Field(pattern="^(discovery|experiment|prototype|idea|library|research|patent|scenario|technology|project|opportunity)$")
    a_id: int
    b_type: str = Field(pattern="^(discovery|experiment|prototype|idea|library|research|patent|scenario|technology|project|opportunity)$")
    b_id: int
    note: str | None = Field(default=None, max_length=300)


@router.post("/links", status_code=201)
def link_add(body: LinkIn, db: DB) -> dict:
    lk = IxLink(**body.model_dump())
    db.add(lk)
    db.commit()
    return row(lk)


@router.get("/links")
def links(db: DB, type: str, id: int) -> list[dict]:  # noqa: A002
    out = []
    for lk in db.scalars(select(IxLink)):
        if (lk.a_type, lk.a_id) == (type, id):
            out.append(row(lk) | {"other_type": lk.b_type, "other_id": lk.b_id})
        elif (lk.b_type, lk.b_id) == (type, id):
            out.append(row(lk) | {"other_type": lk.a_type, "other_id": lk.a_id})
    return out


@router.delete("/links/{lid}")
def link_del(lid: int, db: DB) -> dict:
    db.delete(_get(db, IxLink, lid))
    db.commit()
    return {"ok": True}


# ───────── Idea Generator ─────────

class IdeaIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    concept: str | None = Field(default=None, max_length=4000)
    problem: str | None = Field(default=None, max_length=4000)
    solution: str | None = Field(default=None, max_length=4000)
    tech: str | None = Field(default=None, max_length=4000)
    feasibility: str | None = Field(default=None, max_length=4000)
    difficulty: str | None = Field(default=None, pattern="^(baja|media|alta)$")
    cost: str | None = Field(default=None, max_length=120)
    applications: str | None = Field(default=None, max_length=4000)
    risks: str | None = Field(default=None, max_length=4000)
    customers: str | None = Field(default=None, max_length=4000)
    next_experiment: str | None = Field(default=None, max_length=4000)
    category: str | None = Field(default=None, pattern=CATS)
    status: str = Field(default="new", pattern="^(new|exploring|converted|discarded)$")


class IdeaPatch(IdeaIn):
    name: str | None = Field(default=None, min_length=2, max_length=200)  # type: ignore[assignment]
    status: str | None = Field(default=None, pattern="^(new|exploring|converted|discarded)$")  # type: ignore[assignment]


_crud("/ideas", IxIdea, IdeaIn, IdeaPatch, IxIdea.id.desc(), "Idea")

SOURCES = {"daily": "problema cotidiano", "business": "necesidad empresarial", "advance": "avance tecnológico", "material": "nuevo material",
           "emerging": "tecnología emergente", "combo": "combinación de tecnologías", "market": "oportunidad de mercado", "science": "investigación científica"}


class GenIn(BaseModel):
    source: str = Field(pattern="^(" + "|".join(SOURCES) + ")$")
    text: str = Field(min_length=5, max_length=3000)
    category: str | None = Field(default=None, pattern=CATS)
    n: int = Field(default=3, ge=1, le=5)


@router.post("/ideas/generate", status_code=201)
async def ideas_generate(body: GenIn, db: DB) -> list[dict]:
    ctx = {"tecnologias_seguidas": [t.name for t in db.scalars(select(IxTechnology).limit(20))],
           "descubrimientos_recientes": [d.title for d in db.scalars(select(IxDiscovery).order_by(IxDiscovery.id.desc()).limit(10))]}
    items, model = await run_in_threadpool(_ai, ai.ideas, get_prefs(db), SOURCES[body.source], body.text, ctx, body.n)
    if not items:
        raise HTTPException(502, "La IA no devolvió ideas válidas; inténtalo de nuevo")
    out = []
    for it in items:
        i = IxIdea(**it, category=body.category, origin="generated", source_input=f"{SOURCES[body.source]}: {body.text}"[:4000])
        db.add(i)
        out.append(i)
    log_activity(db, "lab", "ideas", f"{len(out)} ideas generadas ({SOURCES[body.source]}) con {model}")
    db.commit()
    return [row(i) | {"label": "Propuesta generada por IA: hipótesis sin validar"} for i in out]


class ConvertIn(BaseModel):
    to: str = Field(pattern="^(experiment|prototype|opportunity|project)$")


@router.post("/ideas/{iid}/convert", status_code=201)
def idea_convert(iid: int, body: ConvertIn, db: DB) -> dict:
    i = _get(db, IxIdea, iid)
    ref: dict
    if body.to == "experiment":
        e = IxExperiment(name=f"Validar: {i.name}"[:200], objective=i.concept, hypothesis=i.solution, description=i.problem, technology=(i.tech or "")[:200],
                         category=i.category, methodology=i.next_experiment, status="IDEA", idea_id=i.id)
        db.add(e)
        db.flush()
        i.experiment_id, ref = e.id, {"experiment_id": e.id}
    elif body.to == "prototype":
        p = IxPrototype(name=i.name[:160], description=i.concept, problem=i.problem, goal=i.solution, tech=i.tech, idea_id=i.id)
        db.add(p)
        db.flush()
        i.prototype_id, ref = p.id, {"prototype_id": p.id}
    elif body.to == "opportunity":
        o = LfOpportunity(name=i.name[:160], description=i.concept, problem=i.problem, solution=i.solution, customer=i.customers, risks=i.risks,
                          next_actions=i.next_experiment, status="idea", economics={}, scores={}, swot={})
        db.add(o)
        db.flush()
        i.opportunity_id, ref = o.id, {"opportunity_id": o.id}
    else:
        pr = _make_project(db, i.name, i.concept, "idea", i.id, [i.next_experiment] if i.next_experiment else [])
        i.project_id, ref = pr.id, {"project_id": pr.id}
    i.status = "converted"
    log_activity(db, "lab", "convert", f"Idea «{i.name}» convertida en {body.to}")
    db.commit()
    return ref


# ───────── Future Technology Simulator ─────────

class ScenarioIn(BaseModel):
    question: str = Field(min_length=8, max_length=1000)
    horizon: str = Field(default="5 años", pattern="^(1 año|3 años|5 años|10 años|20 años)$")
    research_id: int | None = None


@router.get("/scenarios")
def scenarios(db: DB) -> list[dict]:
    return [row(s) for s in db.scalars(select(IxScenario).order_by(IxScenario.id.desc()).limit(100))]


@router.post("/scenarios", status_code=201)
async def scenario(body: ScenarioIn, db: DB) -> dict:
    research = None
    if body.research_id:
        from atlas.research.engine import to_dict
        r = _get(db, Research, body.research_id)
        if r.status != "done":
            raise HTTPException(409, "La investigación de apoyo aún no ha terminado")
        full = to_dict(r, full=True)
        research = {"resumen": (full.get("report") or {}).get("summary"), "fuentes": [{"url": s.get("url"), "titulo": s.get("title"), "extracto": s.get("excerpt")} for s in full.get("sources", [])[:12]]}
    out, model = await run_in_threadpool(_ai, ai.scenario, get_prefs(db), body.question, body.horizon, research)
    if not research:
        out["hechos"] = []  # sin investigación de apoyo no se presentan hechos
    s = IxScenario(question=body.question, horizon=body.horizon, research_id=body.research_id, result=out, model=model)
    db.add(s)
    db.commit()
    return row(s) | {"grounded": bool(research)}


@router.delete("/scenarios/{sid}")
def scenario_del(sid: int, db: DB) -> dict:
    db.delete(_get(db, IxScenario, sid))
    db.commit()
    return {"ok": True}


# ───────── Patentes ─────────

class PatentIn(BaseModel):
    kind: str = Field(default="external", pattern="^(external|own)$")
    title: str = Field(min_length=3, max_length=400)
    number: str | None = Field(default=None, max_length=60)
    office: str | None = Field(default=None, max_length=20)
    applicants: list[str] = Field(default_factory=list, max_length=20)
    abstract: str | None = Field(default=None, max_length=8000)
    url: str | None = Field(default=None, max_length=1000, pattern=r"^$|^https?://")
    published_on: date | None = None
    technology: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=8000)
    status: str | None = Field(default=None, pattern="^(idea|drafting|consulted|filed)$")


class PatentPatch(PatentIn):
    title: str | None = Field(default=None, min_length=3, max_length=400)  # type: ignore[assignment]
    kind: str | None = Field(default=None, pattern="^(external|own)$")  # type: ignore[assignment]


_crud("/patents", IxPatent, PatentIn, PatentPatch, IxPatent.id.desc(), "Patente")


@router.get("/patents/search")
async def patent_search(q: str) -> dict:
    links_ = src.patent_links(q)
    if not src.epo_configured():
        return {"items": [], "links": links_, "error": "Espacenet (EPO OPS) no configurado: usa los enlaces oficiales o añade tus credenciales gratuitas"}
    try:
        items = await run_in_threadpool(src.epo_search, q, 15)
    except src.SourceError as exc:
        return {"items": [], "links": links_, "error": str(exc)}
    return {"items": items, "links": links_, "error": None,
            "legal": "Una búsqueda no demuestra que una idea sea patentable ni que esté libre de derechos: consulta a un agente de la propiedad industrial."}


class EpoKeys(BaseModel):
    key: str = Field(min_length=4, max_length=200)
    secret: str = Field(min_length=4, max_length=200)


@router.put("/sources/epo")
def epo_keys(body: EpoKeys, db: DB) -> dict:
    set_secret("epo_ops_key", body.key.strip())
    set_secret("epo_ops_secret", body.secret.strip())
    src._token.update(value=None, exp=0)
    log_activity(db, "security", "credential", "Credenciales de Espacenet (EPO OPS) guardadas en el llavero")
    db.commit()
    return {"ok": True}


@router.delete("/sources/epo")
def epo_del(db: DB) -> dict:
    delete_secret("epo_ops_key")
    delete_secret("epo_ops_secret")
    src._token.update(value=None, exp=0)
    db.commit()
    return {"ok": True}


# ───────── Innovation Project Manager (sobre Projects/Tasks) ─────────

def _make_project(db, name: str, desc: str | None, origin_type: str, origin_id: int, steps: list[str]) -> Project:  # noqa: ANN001
    p = Project(name=name[:200], description=(desc or "") + "\n\nCreado desde VISTAN INNOVATION LAB", status="active")
    db.add(p)
    db.flush()
    db.add(IxProjectMeta(project_id=p.id, origin_type=origin_type, origin_id=origin_id, agents=["innovation"], next_steps="\n".join(steps)))
    for s in steps:
        if s and s.strip():
            db.add(Task(title=s.strip()[:300], project_id=p.id, category="innovación"))
    return p


class ToProject(BaseModel):
    kind: str = Field(pattern="^(experiment|research|prototype)$")
    id: int


@router.post("/projects", status_code=201)
def to_project(body: ToProject, db: DB) -> dict:
    if body.kind == "experiment":
        e = _get(db, IxExperiment, body.id)
        p = _make_project(db, e.name, e.objective, "experiment", e.id, [x for x in (e.methodology or "").splitlines()[:8]])
        e.project_id = p.id
    elif body.kind == "prototype":
        x = _get(db, IxPrototype, body.id)
        p = _make_project(db, x.name, x.description, "prototype", x.id, [])
        x.project_id = p.id
    else:
        r = _get(db, Research, body.id)
        nxt = ((r.report or {}).get("unconfirmed") or [])[:6]
        p = _make_project(db, r.question[:120], (r.report or {}).get("summary"), "research", r.id, [f"Resolver: {q}" for q in nxt if isinstance(q, str)])
    log_activity(db, "projects", "create", f"Proyecto de innovación creado: {p.name}")
    db.commit()
    return {"project_id": p.id}


@router.get("/projects")
def lab_projects(db: DB) -> list[dict]:
    out = []
    for m in db.scalars(select(IxProjectMeta).order_by(IxProjectMeta.id.desc())):
        p = db.get(Project, m.project_id)
        if not p:
            continue
        tasks = list(db.scalars(select(Task).where(Task.project_id == p.id)))
        out.append(row(m) | {"name": p.name, "status": p.status, "tasks": len(tasks), "tasks_done": sum(t.status == "done" for t in tasks),
                             "next": [t.title for t in tasks if t.status != "done"][:5]})
    return out


class MetaPatch(BaseModel):
    budget: float | None = Field(default=None, ge=0, le=1e10)
    spent: float | None = Field(default=None, ge=0, le=1e10)
    owner: str | None = Field(default=None, max_length=120)
    agents: list[str] | None = Field(default=None, max_length=12)
    resources: str | None = Field(default=None, max_length=8000)
    results: str | None = Field(default=None, max_length=8000)
    next_steps: str | None = Field(default=None, max_length=8000)


@router.patch("/projects/{pid}")
def lab_project_patch(pid: int, body: MetaPatch, db: DB) -> dict:
    m = db.scalar(select(IxProjectMeta).where(IxProjectMeta.project_id == pid))
    if not m:
        raise HTTPException(404, "No es un proyecto del laboratorio")
    _set(m, body, partial=True)
    db.commit()
    return row(m)


# ───────── Automatizaciones del laboratorio (motor de Workflows existente) ─────────

WORKFLOW_TEMPLATES = {
    "lab_weekly_research": {"name": "Investigación tecnológica semanal", "schedule": "weekly 0 09:00", "steps": [{"type": "lab_tech_watch"}, {"type": "notify", "params": {"title": "Seguimiento tecnológico"}}]},
    "lab_papers": {"name": "Nuevas publicaciones científicas", "schedule": "daily 07:30", "steps": [{"type": "lab_tech_watch"}]},
    "lab_model_compare": {"name": "Comparación periódica de modelos de IA", "schedule": "weekly 5 18:00", "steps": [{"type": "lab_arena"}]},
    "lab_experiments": {"name": "Evaluación de experimentos", "schedule": "weekly 4 19:00", "steps": [{"type": "lab_experiments_review"}, {"type": "notify", "params": {"title": "Experimentos"}}]},
    "lab_report": {"name": "Informe del laboratorio", "schedule": "weekly 6 19:30", "steps": [{"type": "lab_report"}, {"type": "notify", "params": {"title": "Informe del laboratorio"}}]},
    "lab_patents": {"name": "Seguimiento de patentes", "schedule": "weekly 2 08:30", "steps": [{"type": "lab_patent_watch"}]},
}


@router.post("/workflows/{key}", status_code=201)
def wf_install(key: str, db: DB) -> dict:
    from atlas.models import Workflow
    from atlas.workflows import engine as wf
    t = WORKFLOW_TEMPLATES.get(key)
    if not t:
        raise HTTPException(404, "Plantilla desconocida")
    w = db.scalar(select(Workflow).where(Workflow.key == key))
    if w:
        raise HTTPException(409, "Esta automatización ya está creada: gestiónala en Automatizaciones")
    w = Workflow(key=key, name=t["name"], description="Automatización del Innovation Lab", schedule=t["schedule"], enabled=False, steps=t["steps"])
    db.add(w)
    db.commit()
    return wf.wf_dict(w)


# ───────── Innovation Agent ─────────

class AgentIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=12)


@router.post("/agent")
async def agent(body: AgentIn, db: DB) -> dict:
    from atlas.agents.tools import TOOLS, Ctx
    prefs = get_prefs(db)
    c = Ctx(db=db, prefs=prefs, text=body.question, tz=str(prefs["timezone"]))
    tools = ["lab.overview", "lab.experiments", "lab.discoveries", "lab.ideas", "research.recent", "projects.list", "memory.search"]
    ctx = {}
    for t in tools:
        try:
            ctx[t] = TOOLS[t].fn(c)
        except Exception as exc:  # noqa: BLE001
            ctx[t] = {"error": str(exc)[:200]}
    text, model = await run_in_threadpool(_ai, ai.agent, prefs, body.question, ctx, body.history)
    log_activity(db, "agents", "innovation", f"Innovation Agent: {body.question[:120]}")
    db.commit()
    return {"answer": text, "model": model, "used": tools}


class RememberIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    ref: str | None = Field(default=None, max_length=200)


@router.post("/remember", status_code=201)
def remember(body: RememberIn, db: DB) -> dict:
    from atlas.services.memory import remember as rem
    rem(db, f"[Innovation Lab{' · ' + body.ref if body.ref else ''}] {body.text}"[:2000], kind="note", source="manual")
    db.commit()
    return {"ok": True}
