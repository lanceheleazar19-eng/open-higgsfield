"""API de VISTAN LEGAL. Protegida con el mismo PIN/sesión que LIFE OS (no hay un segundo sistema de autenticación)."""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from atlas.api.deps import DB
from atlas.brain.base import ProviderError
from atlas.legal import ai, compliance, contracts, drafts, reports, research, risks, sources, vault
from atlas.life import lock
from atlas.models import (AgentRun, LgAlert, LgAnalysis, LgCase, LgComment, LgComparison, LgCompliance, LgDeadline, LgDocument, LgDraft,
                          LgDraftVersion, LgEvent, LgQuery, LgResearch, LfOpportunity, Project)
from atlas.models.legal import CASE_STATES
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs, set_prefs

router = APIRouter(prefix="/api/legal", tags=["legal"], dependencies=[Depends(lock.require)])


def _get(db, model, oid: int):  # noqa: ANN001, ANN202
    o = db.get(model, oid)
    if not o:
        raise HTTPException(404, "No encontrado")
    return o


def ev(db, case_id: int | None, kind: str, summary: str) -> None:  # noqa: ANN001
    if case_id:
        db.add(LgEvent(case_id=case_id, kind=kind, summary=summary[:1000]))
    log_activity(db, "legal", kind, summary[:200])


def row(o) -> dict:  # noqa: ANN001
    out = {}
    for c in o.__table__.columns:
        v = getattr(o, c.name)
        out[c.name] = v.isoformat() if isinstance(v, (date, datetime)) else v
    return out


def doc_row(d: LgDocument) -> dict:
    r = row(d)
    r.pop("stored_path", None)
    r["has_original"] = bool(d.stored_path)
    return r


# ───────── meta y panel ─────────
@router.get("/meta")
def meta(db: DB) -> dict:
    return {"branches": sources.BRANCHES, "jurisdictions": sources.JURISDICTIONS, "states": CASE_STATES, "levels": contracts.LEVELS,
            "templates": {k: {"label": v[0], "fields": v[1]} for k, v in drafts.TEMPLATES.items()}, "profiles": compliance.PROFILES,
            "contract_types": {k: v[1] for k, v in contracts.TYPES.items()}, "sources": sources.status(), "settings": ai.conf(get_prefs(db)),
            "disclaimer": ai.DISCLAIMER, "formats": sorted(vault.EXT)}


@router.get("/dashboard")
def dashboard(db: DB) -> dict:
    today = date.today()
    active = list(db.scalars(select(LgCase).where(LgCase.status.notin_(("resuelto", "archivado"))).order_by(LgCase.updated_at.desc())))
    analyzed = {a for (a,) in db.execute(select(LgAnalysis.legal_doc_id).where(LgAnalysis.status == "done")).all()}
    pending = [d for d in db.scalars(select(LgDocument).where(LgDocument.kind.in_(("contract", "policy", "tos")), LgDocument.origin == "original"))
               if d.id not in analyzed]
    alerts = list(db.scalars(select(LgAlert).where(LgAlert.status == "abierta").order_by(LgAlert.detected_at.desc())))
    agent_runs = [r for r in db.scalars(select(AgentRun).order_by(AgentRun.id.desc()).limit(100)) if "legal" in (r.agents or [])][:6]
    return {
        "counts": {"active_cases": len(active), "documents": db.scalar(select(func.count(LgDocument.id))) or 0, "pending_review": len(pending),
                   "open_alerts": len(alerts), "research": db.scalar(select(func.count(LgResearch.id))) or 0,
                   "drafts": db.scalar(select(func.count(LgDraft.id))) or 0},
        "alerts_by_level": {lv: sum(1 for a in alerts if a.level == lv) for lv in contracts.LEVELS},
        "cases": [row(c) for c in active[:8]], "pending_review": [doc_row(d) for d in pending[:8]],
        "alerts": [risks.alert_dict(a) for a in alerts[:8]],
        "deadlines": [row(d) | {"days": (d.due_on - today).days} for d in db.scalars(select(LgDeadline).where(
            LgDeadline.status == "pendiente", LgDeadline.due_on <= today + timedelta(days=60)).order_by(LgDeadline.due_on).limit(10))],
        "research": [research.to_dict(r) for r in db.scalars(select(LgResearch).order_by(LgResearch.id.desc()).limit(6))],
        "recent_docs": [doc_row(d) for d in db.scalars(select(LgDocument).order_by(LgDocument.updated_at.desc()).limit(6))],
        "queries": [row(q) for q in db.scalars(select(LgQuery).order_by(LgQuery.id.desc()).limit(10))],
        "agent": [{"at": r.created_at.isoformat(), "request": r.request[:140], "agents": r.agents, "status": r.status} for r in agent_runs]}


# ───────── expedientes ─────────
class CaseIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    category: str | None = Field(default=None, max_length=32)
    description: str | None = Field(default=None, max_length=8000)
    jurisdiction: str = Field(default="es", max_length=16)
    parties: list[dict] = Field(default_factory=list, max_length=20)
    status: str = Field(default="nuevo", pattern="^(" + "|".join(CASE_STATES) + ")$")
    priority: str = Field(default="media", pattern="^(baja|media|alta|urgente)$")
    opened_on: date | None = None
    project_id: int | None = None
    opportunity_id: int | None = None
    notes: str | None = Field(default=None, max_length=20000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class CasePatch(CaseIn):
    name: str | None = Field(default=None, min_length=2, max_length=200)  # type: ignore[assignment]
    status: str | None = Field(default=None, pattern="^(" + "|".join(CASE_STATES) + ")$")  # type: ignore[assignment]
    priority: str | None = Field(default=None, pattern="^(baja|media|alta|urgente)$")  # type: ignore[assignment]
    jurisdiction: str | None = Field(default=None, max_length=16)  # type: ignore[assignment]


def _links(db, b: CaseIn | CasePatch) -> None:  # noqa: ANN001
    if b.project_id and not db.get(Project, b.project_id):
        raise HTTPException(422, "Proyecto no encontrado")
    if b.opportunity_id and not db.get(LfOpportunity, b.opportunity_id):
        raise HTTPException(422, "Empresa/oportunidad de LIFE OS no encontrada")


@router.get("/cases")
def list_cases(db: DB, q: str = "", status: str | None = None, category: str | None = None) -> list[dict]:
    s = select(LgCase).order_by(LgCase.updated_at.desc())
    if q:
        s = s.where(or_(LgCase.name.ilike(f"%{q}%"), LgCase.ref.ilike(f"%{q}%"), LgCase.description.ilike(f"%{q}%")))
    if status:
        s = s.where(LgCase.status == status)
    if category:
        s = s.where(LgCase.category == category)
    out = []
    for c in db.scalars(s):
        out.append(row(c) | {"documents": db.scalar(select(func.count(LgDocument.id)).where(LgDocument.case_id == c.id)) or 0,
                             "open_alerts": db.scalar(select(func.count(LgAlert.id)).where(LgAlert.case_id == c.id, LgAlert.status == "abierta")) or 0})
    return out


@router.post("/cases", status_code=201)
def create_case(body: CaseIn, db: DB) -> dict:
    _links(db, body)
    year = date.today().year
    n = (db.scalar(select(func.count(LgCase.id)).where(LgCase.ref.like(f"EXP-{year}-%"))) or 0) + 1
    c = LgCase(**body.model_dump(exclude={"opened_on"}), opened_on=body.opened_on or date.today(), ref=f"EXP-{year}-{n:04d}")
    db.add(c)
    db.flush()
    ev(db, c.id, "created", f"Expediente {c.ref} abierto: {c.name}")
    db.commit()
    return row(c)


@router.get("/cases/{cid}")
def get_case(cid: int, db: DB) -> dict:
    c = _get(db, LgCase, cid)
    return row(c) | {
        "documents": [doc_row(d) for d in db.scalars(select(LgDocument).where(LgDocument.case_id == cid).order_by(LgDocument.updated_at.desc()))],
        "research": [research.to_dict(r) for r in db.scalars(select(LgResearch).where(LgResearch.case_id == cid).order_by(LgResearch.id.desc()))],
        "drafts": [row(d) | {"content": None} for d in db.scalars(select(LgDraft).where(LgDraft.case_id == cid))],
        "deadlines": [row(d) for d in db.scalars(select(LgDeadline).where(LgDeadline.case_id == cid).order_by(LgDeadline.due_on))],
        "alerts": [risks.alert_dict(a) for a in db.scalars(select(LgAlert).where(LgAlert.case_id == cid).order_by(LgAlert.detected_at.desc()))],
        "comments": [row(x) for x in db.scalars(select(LgComment).where(LgComment.target == "case", LgComment.target_id == cid).order_by(LgComment.id.desc()))],
        "timeline": [row(e) for e in db.scalars(select(LgEvent).where(LgEvent.case_id == cid).order_by(LgEvent.id.desc()).limit(200))],
        "project": (lambda p: {"id": p.id, "name": p.name} if p else None)(db.get(Project, c.project_id) if c.project_id else None),
        "opportunity": (lambda o: {"id": o.id, "name": o.name} if o else None)(db.get(LfOpportunity, c.opportunity_id) if c.opportunity_id else None)}


@router.patch("/cases/{cid}")
def patch_case(cid: int, body: CasePatch, db: DB) -> dict:
    c = _get(db, LgCase, cid)
    _links(db, body)
    ch = body.model_dump(exclude_unset=True)
    if "status" in ch and ch["status"] != c.status:
        ev(db, cid, "status", f"Estado: {c.status} → {ch['status']}")
    for k, v in ch.items():
        setattr(c, k, v)
    ev(db, cid, "edit", "Expediente editado: " + ", ".join(k for k in ch if k != "status"))
    db.commit()
    return row(c)


@router.delete("/cases/{cid}", status_code=204)
def delete_case(cid: int, db: DB, confirm: str = "") -> None:
    """Eliminación controlada: hay que escribir el número del expediente. Borra también sus documentos cifrados."""
    c = _get(db, LgCase, cid)
    if confirm != c.ref:
        raise HTTPException(428, f"Para eliminar escribe el número del expediente ({c.ref}). Considera archivarlo en su lugar.")
    for d in db.scalars(select(LgDocument).where(LgDocument.case_id == cid)):
        vault.delete(db, d)
    log_activity(db, "legal", "delete", f"Expediente {c.ref} eliminado")
    db.delete(c)
    db.commit()


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


@router.post("/comments", status_code=201)
def add_comment(target: str, target_id: int, body: NoteIn, db: DB) -> dict:
    if target not in ("case", "draft", "doc"):
        raise HTTPException(422, "Destino no válido")
    _get(db, {"case": LgCase, "draft": LgDraft, "doc": LgDocument}[target], target_id)
    c = LgComment(target=target, target_id=target_id, text=body.text)
    db.add(c)
    if target == "case":
        ev(db, target_id, "comment", f"Comentario: {body.text[:200]}")
    db.commit()
    return row(c)


@router.get("/comments")
def list_comments(target: str, target_id: int, db: DB) -> list[dict]:
    return [row(c) for c in db.scalars(select(LgComment).where(LgComment.target == target, LgComment.target_id == target_id).order_by(LgComment.id.desc()))]


class TaskIn(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    due_at: datetime | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")


@router.post("/cases/{cid}/tasks", status_code=201)
def case_task(cid: int, body: TaskIn, db: DB) -> dict:
    from atlas.services.tasks import create_task
    c = _get(db, LgCase, cid)
    t = create_task(db, title=f"[{c.ref}] {body.title}", priority=body.priority, due_at=body.due_at, category="legal", project_id=c.project_id)
    ev(db, cid, "task", f"Tarea creada en Tareas: {body.title}")
    db.commit()
    return {"task_id": t.id, "title": t.title}


# ───────── documentos ─────────
@router.post("/documents", status_code=201)
async def upload(db: DB, file: UploadFile = File(...), case_id: int | None = Form(None), kind: str = Form("contract"),
                 title: str | None = Form(None)) -> dict:
    if case_id:
        _get(db, LgCase, case_id)
    data = await file.read()
    if not vault.kind_for(file.filename or ""):
        raise HTTPException(415, "Formato no admitido: PDF, DOCX, DOC, TXT, RTF, ODT o imagen (OCR local)")
    prefs = get_prefs(db)
    try:
        lg, created = await run_in_threadpool(vault.add, db, title=title or file.filename or "Documento", kind=kind[:20], case_id=case_id,
                                              prefs=prefs, data=data, filename=file.filename)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if created:
        ev(db, case_id, "doc", f"Documento añadido: {lg.title} ({lg.extraction}, {lg.chars} caracteres)")
    db.commit()
    return doc_row(lg) | {"created": created}


class TextDocIn(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    text: str = Field(min_length=10, max_length=400000)
    case_id: int | None = None
    kind: str = Field(default="note", max_length=20)


@router.post("/documents/text", status_code=201)
def add_text(body: TextDocIn, db: DB) -> dict:
    if body.case_id:
        _get(db, LgCase, body.case_id)
    lg, created = vault.add(db, title=body.title, kind=body.kind, case_id=body.case_id, prefs=get_prefs(db), text=body.text,
                            origin="nota" if body.kind == "note" else "original")
    if created:
        ev(db, body.case_id, "doc", f"Texto añadido: {lg.title}")
    db.commit()
    return doc_row(lg) | {"created": created}


@router.get("/documents")
def list_docs(db: DB, case_id: int | None = None, kind: str | None = None, origin: str | None = None) -> list[dict]:
    s = select(LgDocument).order_by(LgDocument.updated_at.desc())
    if case_id is not None:
        s = s.where(LgDocument.case_id == case_id)
    if kind:
        s = s.where(LgDocument.kind == kind)
    if origin:
        s = s.where(LgDocument.origin == origin)
    return [doc_row(d) for d in db.scalars(s.limit(300))]


@router.get("/documents/{did}")
def get_doc(did: int, db: DB) -> dict:
    d = _get(db, LgDocument, did)
    text = vault.text_of(db, d)
    return doc_row(d) | {"text": text[:200000], "analyses": [row(a) for a in db.scalars(select(LgAnalysis).where(LgAnalysis.legal_doc_id == did).order_by(LgAnalysis.id.desc()))],
                         "comments": list_comments("doc", did, db)}


@router.get("/documents/{did}/download")
def download(did: int, db: DB) -> Response:
    d = _get(db, LgDocument, did)
    if not d.stored_path:
        raise HTTPException(404, "Este documento no tiene archivo original (es texto)")
    log_activity(db, "legal", "download", f"Original descargado: {d.title[:80]}")
    db.commit()
    return Response(vault.load(d.stored_path), media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{(d.filename or "documento").replace(chr(34), "")}"',
                             "Content-Security-Policy": "sandbox", "X-Content-Type-Options": "nosniff"})


class DocPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    kind: str | None = Field(default=None, max_length=20)
    case_id: int | None = None


@router.patch("/documents/{did}")
def patch_doc(did: int, body: DocPatch, db: DB) -> dict:
    d = _get(db, LgDocument, did)
    ch = body.model_dump(exclude_unset=True)
    if "case_id" in ch and ch["case_id"] != d.case_id:
        if ch["case_id"]:
            _get(db, LgCase, ch["case_id"])
        ev(db, d.case_id, "doc", f"Documento «{d.title}» retirado del expediente")
        ev(db, ch["case_id"], "doc", f"Documento «{d.title}» asociado al expediente")
    for k, v in ch.items():
        setattr(d, k, v)
    db.commit()
    return doc_row(d)


@router.delete("/documents/{did}", status_code=204)
def delete_doc(did: int, db: DB, confirm: bool = False) -> None:
    d = _get(db, LgDocument, did)
    if not confirm:
        raise HTTPException(428, "Confirma la eliminación: se borra el original cifrado y su texto")
    ev(db, d.case_id, "doc", f"Documento eliminado: {d.title}")
    vault.delete(db, d)
    db.commit()


# ───────── análisis y comparación ─────────
def _analyze_thread(aid: int) -> None:
    from atlas.db import session_scope
    with session_scope() as db:
        a = db.get(LgAnalysis, aid)
        lg = db.get(LgDocument, a.legal_doc_id)
        a.status = "running"
        db.commit()
        try:
            res = contracts.analyze(vault.text_of(db, lg), get_prefs(db))
            a.result, a.contract_type, a.model, a.status = res, res["type"], res["model"], "done"
            ev(db, lg.case_id, "analysis", f"Análisis de «{lg.title}»: " + ", ".join(f"{v} {k}" for k, v in res["counts"].items() if v))
            risks.scan(db)
        except Exception as exc:  # noqa: BLE001
            a.status, a.error = "error", str(exc)[:500]
        a.finished_at = datetime.utcnow()
        db.commit()


@router.post("/documents/{did}/analyze", status_code=202)
def analyze_doc(did: int, db: DB) -> dict:
    _get(db, LgDocument, did)
    a = LgAnalysis(legal_doc_id=did, status="queued")
    db.add(a)
    db.commit()
    threading.Thread(target=_analyze_thread, args=(a.id,), daemon=True).start()
    return row(a)


@router.get("/analyses/{aid}")
def get_analysis(aid: int, db: DB) -> dict:
    return row(_get(db, LgAnalysis, aid))


class CompareIn(BaseModel):
    a_id: int
    b_id: int


@router.post("/compare", status_code=201)
def compare(body: CompareIn, db: DB) -> dict:
    a, b = _get(db, LgDocument, body.a_id), _get(db, LgDocument, body.b_id)
    if a.case_id != b.case_id:
        raise HTTPException(422, "Solo se comparan documentos del mismo expediente (separación de expedientes)")
    c = LgComparison(a_id=a.id, b_id=b.id, result=contracts.compare(vault.text_of(db, a), vault.text_of(db, b)))
    db.add(c)
    ev(db, a.case_id, "compare", f"Comparación «{a.title}» ↔ «{b.title}»: {c.result['counts']}")
    db.commit()
    return row(c) | {"a_title": a.title, "b_title": b.title}


@router.get("/comparisons/{cid}")
def get_comparison(cid: int, db: DB) -> dict:
    c = _get(db, LgComparison, cid)
    return row(c) | {"a_title": db.get(LgDocument, c.a_id).title, "b_title": db.get(LgDocument, c.b_id).title}


# ───────── investigación ─────────
class PrecheckIn(BaseModel):
    question: str = Field(min_length=8, max_length=3000)
    facts: str | None = Field(default=None, max_length=6000)


@router.post("/research/precheck")
def precheck(body: PrecheckIn) -> dict:
    return sources.classify(body.question, body.facts or "")


class ResearchIn(PrecheckIn):
    jurisdiction: str = Field(default="auto", pattern="^(auto|es|es-ct|eu)$")
    case_id: int | None = None


@router.post("/research", status_code=201)
def start_research(body: ResearchIn, db: DB) -> dict:
    from atlas.metabrain.governance import killed
    if killed(get_prefs(db)):
        raise HTTPException(423, "Kill switch activo")
    if body.case_id:
        _get(db, LgCase, body.case_id)
    r = LgResearch(question=body.question, facts=body.facts, jurisdiction=body.jurisdiction, case_id=body.case_id, state={})
    db.add(r)
    db.add(LgQuery(kind="research", question=body.question, case_id=body.case_id))
    db.flush()
    ev(db, body.case_id, "research", f"Investigación jurídica iniciada: {body.question[:200]}")
    db.commit()
    research.start(r.id)
    return research.to_dict(r)


@router.get("/research")
def list_research(db: DB, case_id: int | None = None) -> list[dict]:
    s = select(LgResearch).order_by(LgResearch.id.desc()).limit(100)
    if case_id:
        s = s.where(LgResearch.case_id == case_id)
    return [research.to_dict(r) for r in db.scalars(s)]


@router.get("/research/{rid}")
def get_research(rid: int, db: DB) -> dict:
    return research.to_dict(_get(db, LgResearch, rid), full=True)


@router.post("/research/{rid}/resume")
def resume_research(rid: int, db: DB) -> dict:
    r = _get(db, LgResearch, rid)
    if r.status not in ("error",):
        raise HTTPException(409, "Solo se reanuda una investigación con error")
    r.status, r.error = "queued", None
    db.commit()
    research.start(rid)
    return research.to_dict(r)


@router.post("/research/{rid}/save", status_code=201)
def save_research(rid: int, db: DB) -> dict:
    """Guarda el informe en la base de conocimiento jurídica como CONCLUSIÓN DE IA (separada de los originales)."""
    r = _get(db, LgResearch, rid)
    if r.status != "done":
        raise HTTPException(409, "La investigación no ha terminado")
    rp = r.report
    text = "\n\n".join([f"Pregunta: {r.question}", rp.get("resumen", ""), rp.get("interpretacion", ""), rp.get("aplicacion", ""),
                        "Conclusión: " + rp.get("conclusion", ""), "Fuentes: " + "; ".join(f"{s['titulo']} ({s['url']})" for s in rp.get("fuentes", []))])
    lg, created = vault.add(db, title=f"Investigación: {r.question[:120]}", kind="report", case_id=r.case_id, prefs=get_prefs(db), text=text,
                            origin="ia", meta={"research_id": r.id, "generated": r.updated_at.isoformat() if r.updated_at else None})
    db.commit()
    return doc_row(lg) | {"created": created}


# ───────── Document Studio ─────────
class GenIn(BaseModel):
    doc_type: str = Field(pattern="^(" + "|".join(drafts.TEMPLATES) + ")$")
    jurisdiction: str = Field(default="es", pattern="^(es|es-ct|eu)$")
    inputs: dict = Field(default_factory=dict)
    request: str = Field(min_length=4, max_length=4000)
    case_id: int | None = None
    research_id: int | None = None


@router.post("/drafts/generate", status_code=201)
async def generate(body: GenIn, db: DB) -> dict:
    if body.case_id:
        _get(db, LgCase, body.case_id)
    notes = ""
    if body.research_id:
        rr = _get(db, LgResearch, body.research_id)
        notes = "; ".join(f"{x.get('norma')} {', '.join(x.get('articulos_encontrados') or [])} ({x.get('url')})"
                          for x in (rr.report or {}).get("legislacion", []) if x.get("verificada_en_fuente") and x.get("vigencia") != "derogada")
    prefs = get_prefs(db)
    try:
        g = await run_in_threadpool(drafts.generate, prefs, body.doc_type, sources.JURISDICTIONS.get(body.jurisdiction, body.jurisdiction),
                                    body.inputs, body.request, notes)
    except (ProviderError, ValueError) as exc:
        raise HTTPException(503, f"No se pudo generar el borrador: {exc}") from exc
    d = LgDraft(case_id=body.case_id, title=g["title"], doc_type=body.doc_type, jurisdiction=body.jurisdiction, content=g["content"],
                inputs=body.inputs, pending=g["pending"], review=g["review"], model=g["model"])
    db.add(d)
    db.flush()
    db.add(LgDraftVersion(draft_id=d.id, content=d.content, note="Generado por IA"))
    ev(db, body.case_id, "draft", f"Borrador generado: {d.title}")
    db.commit()
    return row(d) | {"missing_inputs": g["missing_inputs"], "scrubbed": g["scrubbed"]}


class DraftIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    doc_type: str = Field(default="interno", max_length=32)
    content: str = Field(default="", max_length=400000)
    case_id: int | None = None
    tags: list[str] = Field(default_factory=list)


@router.post("/drafts", status_code=201)
def create_draft(body: DraftIn, db: DB) -> dict:
    content = body.content if body.content.startswith("BORRADOR") else f"{drafts.HEADER}\n\n{body.content}"
    d = LgDraft(title=body.title, doc_type=body.doc_type, content=content, case_id=body.case_id, tags=body.tags, pending=drafts.pending(content))
    db.add(d)
    db.flush()
    db.add(LgDraftVersion(draft_id=d.id, content=content, note="Creado"))
    db.commit()
    return row(d)


@router.get("/drafts")
def list_drafts(db: DB, case_id: int | None = None, tag: str | None = None) -> list[dict]:
    s = select(LgDraft).order_by(LgDraft.updated_at.desc())
    if case_id:
        s = s.where(LgDraft.case_id == case_id)
    out = [row(d) | {"content": None, "chars": len(d.content)} for d in db.scalars(s)]
    return [d for d in out if not tag or tag in (d["tags"] or [])]


@router.get("/drafts/{did}")
def get_draft(did: int, db: DB) -> dict:
    d = _get(db, LgDraft, did)
    return row(d) | {"versions": [row(v) | {"content": None} for v in db.scalars(select(LgDraftVersion).where(LgDraftVersion.draft_id == did).order_by(LgDraftVersion.id.desc()))],
                     "comments": list_comments("draft", did, db)}


class DraftPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    content: str | None = Field(default=None, max_length=400000)
    tags: list[str] | None = None
    case_id: int | None = None


@router.patch("/drafts/{did}")
def patch_draft(did: int, body: DraftPatch, db: DB) -> dict:
    """Guardado automático: actualiza el texto actual (las versiones se crean al pulsar «Guardar versión»)."""
    d = _get(db, LgDraft, did)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    d.pending = drafts.pending(d.content)
    db.commit()
    return row(d) | {"content": None, "saved_at": datetime.utcnow().isoformat()}


class VersionIn(BaseModel):
    note: str | None = Field(default=None, max_length=200)


@router.post("/drafts/{did}/versions", status_code=201)
def save_version(did: int, body: VersionIn, db: DB) -> dict:
    d = _get(db, LgDraft, did)
    v = LgDraftVersion(draft_id=did, content=d.content, note=body.note or "Versión manual")
    db.add(v)
    db.commit()
    return row(v) | {"content": None}


@router.get("/drafts/{did}/versions/{vid}")
def get_version(did: int, vid: int, db: DB) -> dict:
    v = _get(db, LgDraftVersion, vid)
    if v.draft_id != did:
        raise HTTPException(404, "Versión no encontrada")
    d = _get(db, LgDraft, did)
    return row(v) | {"compare": contracts.compare(v.content, d.content)}


@router.post("/drafts/{did}/restore/{vid}")
def restore(did: int, vid: int, db: DB) -> dict:
    d, v = _get(db, LgDraft, did), _get(db, LgDraftVersion, vid)
    if v.draft_id != did:
        raise HTTPException(404, "Versión no encontrada")
    db.add(LgDraftVersion(draft_id=did, content=d.content, note="Antes de restaurar"))
    d.content, d.pending = v.content, drafts.pending(v.content)
    db.commit()
    return row(d)


@router.post("/drafts/{did}/duplicate", status_code=201)
def duplicate(did: int, db: DB) -> dict:
    d = _get(db, LgDraft, did)
    n = LgDraft(title=f"{d.title} (copia)"[:200], doc_type=d.doc_type, jurisdiction=d.jurisdiction, content=d.content, inputs=d.inputs,
                pending=d.pending, review=d.review, tags=d.tags, case_id=d.case_id)
    db.add(n)
    db.flush()
    db.add(LgDraftVersion(draft_id=n.id, content=n.content, note=f"Duplicado de #{d.id}"))
    db.commit()
    return row(n)


@router.delete("/drafts/{did}", status_code=204)
def delete_draft(did: int, db: DB) -> None:
    d = _get(db, LgDraft, did)
    ev(db, d.case_id, "draft", f"Borrador eliminado: {d.title}")
    db.delete(d)
    db.commit()


def _file(data: bytes, name: str, fmt: str) -> Response:
    media = "application/pdf" if fmt == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)[:80] or "informe"
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{safe}.{fmt}"'})


@router.get("/drafts/{did}/export")
def export_draft(did: int, db: DB, fmt: str = "docx") -> Response:
    if fmt not in ("pdf", "docx"):
        raise HTTPException(422, "Formato: pdf o docx")
    d = _get(db, LgDraft, did)
    return _file(reports.text_doc(d.title, d.content, fmt), d.title, fmt)


# ───────── plazos y alertas ─────────
class DeadlineIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    due_on: date
    kind: str = Field(default="otro", pattern="^(procesal|administrativo|contractual|fiscal|otro)$")
    verified: bool = False
    basis: str | None = Field(default=None, max_length=4000)
    case_id: int | None = None
    notes: str | None = Field(default=None, max_length=4000)
    remind: bool = True


@router.post("/deadlines", status_code=201)
def add_deadline(body: DeadlineIn, db: DB) -> dict:
    """VISTAN no calcula plazos: registra el que tú indiques. Los procesales/administrativos sin verificar se señalan."""
    if body.case_id:
        _get(db, LgCase, body.case_id)
    if body.verified and not (body.basis or "").strip():
        raise HTTPException(422, "Para marcarlo como verificado indica la regla o fuente aplicada (y si hay interrupciones o suspensiones)")
    d = LgDeadline(**body.model_dump(exclude={"remind"}))
    db.add(d)
    db.flush()
    if body.remind:
        from atlas.services.tasks import create_task
        t = create_task(db, title=f"Plazo jurídico: {body.title}" + ("" if body.verified else " (SIN VERIFICAR)"), priority="high",
                        due_at=datetime.combine(body.due_on, datetime.min.time()).replace(hour=9), category="legal")
        d.task_id = t.id
    ev(db, body.case_id, "deadline", f"Plazo registrado: {body.title} ({body.due_on.isoformat()}){'' if body.verified else ' — sin verificar'}")
    risks.scan(db)
    db.commit()
    return row(d) | {"warning": None if body.verified or body.kind not in ("procesal", "administrativo") else
                     "Plazo procesal/administrativo sin verificar: compruébalo con prioridad (cómputo, días hábiles, suspensiones)."}


@router.get("/deadlines")
def list_deadlines(db: DB, case_id: int | None = None) -> list[dict]:
    s = select(LgDeadline).order_by(LgDeadline.due_on)
    if case_id:
        s = s.where(LgDeadline.case_id == case_id)
    today = date.today()
    return [row(d) | {"days": (d.due_on - today).days} for d in db.scalars(s)]


class DeadlinePatch(BaseModel):
    status: str | None = Field(default=None, pattern="^(pendiente|cumplido|descartado)$")
    verified: bool | None = None
    basis: str | None = Field(default=None, max_length=4000)


@router.patch("/deadlines/{did}")
def patch_deadline(did: int, body: DeadlinePatch, db: DB) -> dict:
    d = _get(db, LgDeadline, did)
    ch = body.model_dump(exclude_unset=True)
    if ch.get("verified") and not (ch.get("basis") or d.basis or "").strip():
        raise HTTPException(422, "Indica la regla o fuente aplicada para marcarlo como verificado")
    for k, v in ch.items():
        setattr(d, k, v)
    ev(db, d.case_id, "deadline", f"Plazo «{d.title}» actualizado: {ch}")
    db.commit()
    return row(d)


@router.delete("/deadlines/{did}", status_code=204)
def delete_deadline(did: int, db: DB) -> None:
    db.delete(_get(db, LgDeadline, did))
    db.commit()


@router.get("/alerts")
def list_alerts(db: DB, status: str = "abierta", case_id: int | None = None) -> list[dict]:
    s = select(LgAlert).where(LgAlert.status == status).order_by(LgAlert.detected_at.desc())
    if case_id:
        s = s.where(LgAlert.case_id == case_id)
    return [risks.alert_dict(a) for a in db.scalars(s)]


class AlertPatch(BaseModel):
    status: str = Field(pattern="^(abierta|resuelta|descartada)$")


@router.patch("/alerts/{aid}")
def patch_alert(aid: int, body: AlertPatch, db: DB) -> dict:
    a = _get(db, LgAlert, aid)
    a.status = body.status
    ev(db, a.case_id, "alert", f"Alerta «{a.title[:80]}» → {body.status}")
    db.commit()
    return risks.alert_dict(a)


@router.post("/alerts/scan")
def scan(db: DB) -> dict:
    n = risks.scan(db)
    db.commit()
    return {"new": n}


# ───────── cumplimiento ─────────
class ComplianceGen(BaseModel):
    profile: str = Field(pattern="^(" + "|".join(compliance.PROFILES) + ")$")
    case_id: int | None = None
    opportunity_id: int | None = None


@router.post("/compliance/generate", status_code=201)
def gen_compliance(body: ComplianceGen, db: DB) -> list[dict]:
    if body.opportunity_id and not db.get(LfOpportunity, body.opportunity_id):
        raise HTTPException(422, "Empresa/oportunidad de LIFE OS no encontrada")
    have = {(c.obligation, c.case_id, c.opportunity_id) for c in db.scalars(select(LgCompliance).where(LgCompliance.profile == body.profile))}
    out = []
    for it in compliance.items(body.profile):
        if (it["obligation"], body.case_id, body.opportunity_id) in have:
            continue
        c = LgCompliance(profile=body.profile, case_id=body.case_id, opportunity_id=body.opportunity_id, **it)
        db.add(c)
        out.append(c)
    ev(db, body.case_id, "compliance", f"Lista de cumplimiento «{compliance.PROFILES[body.profile]}»: {len(out)} obligaciones")
    db.commit()
    return [row(c) for c in out]


@router.get("/compliance")
def list_compliance(db: DB, profile: str | None = None, case_id: int | None = None) -> list[dict]:
    s = select(LgCompliance).order_by(LgCompliance.id)
    if profile:
        s = s.where(LgCompliance.profile == profile)
    if case_id:
        s = s.where(LgCompliance.case_id == case_id)
    return [row(c) for c in db.scalars(s)]


class CompliancePatch(BaseModel):
    status: str | None = Field(default=None, pattern="^(pendiente|en_curso|cumplida|no_aplica)$")
    applicability: str | None = Field(default=None, pattern="^(confirmada|potencial|asesoramiento)$")
    owner: str | None = Field(default=None, max_length=120)
    due_on: date | None = None
    evidence: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)


@router.patch("/compliance/{cid}")
def patch_compliance(cid: int, body: CompliancePatch, db: DB) -> dict:
    c = _get(db, LgCompliance, cid)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    return row(c)


@router.delete("/compliance/{cid}", status_code=204)
def delete_compliance(cid: int, db: DB) -> None:
    db.delete(_get(db, LgCompliance, cid))
    db.commit()


@router.post("/compliance/vigencia")
async def compliance_vigencia(db: DB) -> dict:
    """Comprueba en la API del BOE / EUR-Lex la vigencia de las normas de la lista (requiere internet)."""
    urls = sorted({c.source_url for c in db.scalars(select(LgCompliance)) if c.source_url})
    return await run_in_threadpool(sources.check_vigencia, [(u, "") for u in urls])


# ───────── base de conocimiento y agente ─────────
@router.get("/kb/search")
def kb_search(db: DB, q: str, case_id: int | None = None, all_cases: bool = False) -> list[dict]:
    if len(q.strip()) < 2:
        return []
    return vault.search(db, q, case_id=case_id, k=10, all_cases=all_cases)


class AgentIn(BaseModel):
    question: str = Field(min_length=3, max_length=3000)
    case_id: int | None = None


@router.post("/agent")
async def agent(body: AgentIn, db: DB) -> dict:
    """VISTAN LEGAL AGENT: responde con los datos del expediente (y solo de ese expediente) y la base de conocimiento jurídica."""
    case = _get(db, LgCase, body.case_id) if body.case_id else None
    hits = vault.search(db, body.question, case_id=body.case_id, k=6)
    ctx = {"expediente": {k: getattr(case, k) for k in ("ref", "name", "category", "jurisdiction", "status", "description")} if case else None,
           "fragmentos": [{"id": f"D{i + 1}", "titulo": h["title"], "origen": "documento original" if h["origin"] == "original" else "conclusión de IA",
                           "texto": h["text"][:1200]} for i, h in enumerate(hits)],
           "alertas": [a.title for a in db.scalars(select(LgAlert).where(LgAlert.status == "abierta", LgAlert.case_id == body.case_id).limit(10))] if case else [],
           "plazos": [f"{d.title} {d.due_on} ({'verificado' if d.verified else 'SIN VERIFICAR'})" for d in db.scalars(select(LgDeadline).where(LgDeadline.case_id == body.case_id))] if case else []}
    prefs = get_prefs(db)
    try:
        res = await run_in_threadpool(ai.call, prefs, [
            {"role": "system", "content": ai.RULES + "\nEres VISTAN LEGAL AGENT. Responde usando SOLO el CONTEXTO (cita D# cuando uses un fragmento). "
             "Si hace falta investigar normativa, dilo y propón la investigación. Termina con «Siguiente paso recomendado»."},
            {"role": "user", "content": f"CONTEXTO: {ctx}\n\nPREGUNTA: {body.question}"}], "agent", False, 1)
    except ProviderError as exc:
        raise HTTPException(503, f"Necesita un modelo local disponible: {exc}") from exc
    answer = f"{res['text'].strip()}\n\n— {ai.DISCLAIMER}"
    db.add(LgQuery(kind="agent", question=body.question, answer=answer[:8000], model=res["model"], case_id=body.case_id))
    ev(db, body.case_id, "agent", f"Consulta al Legal Agent: {body.question[:160]}")
    db.commit()
    return {"answer": answer, "model": res["model"], "fragments": [{"id": f"D{i + 1}", "title": h["title"], "origin": h["origin"]} for i, h in enumerate(hits)]}


class ObligationsIn(BaseModel):
    business: str = Field(min_length=4, max_length=2000)
    profile: str = Field(default="ecommerce", pattern="^(" + "|".join(compliance.PROFILES) + ")$")
    research: bool = False


@router.post("/agent/obligations")
def obligations(body: ObligationsIn, db: DB) -> dict:
    """Punto de integración entre agentes (p. ej. VISTAN SHOPIFY → LEGAL AGENT): obligaciones de partida con su norma y fuente
    oficial, documentación necesaria, riesgos y lo que requiere revisión profesional. Con research=true lanza además una
    investigación jurídica real sobre el negocio concreto."""
    its = compliance.items(body.profile)
    rid = None
    if body.research:
        r = LgResearch(question=f"Obligaciones jurídicas para: {body.business}", facts=body.business, jurisdiction="auto", state={})
        db.add(r)
        db.flush()
        rid = r.id
        db.commit()
        research.start(r.id)
    db.add(LgQuery(kind="agent", question=f"[obligaciones] {body.business[:300]}", answer=f"{len(its)} obligaciones de partida"))
    db.commit()
    return {"profile": compliance.PROFILES[body.profile],
            "obligations": [i for i in its if i["applicability"] == "confirmada"],
            "potential": [i for i in its if i["applicability"] == "potencial"],
            "professional_review": [i for i in its if i["applicability"] == "asesoramiento"],
            "documents_needed": ["Aviso legal (LSSI-CE)", "Política de privacidad", "Política de cookies y banner de consentimiento",
                                 "Condiciones generales de contratación"] + (["Formulario de desistimiento"] if body.profile == "ecommerce" else []),
            "verified_sources": sorted({i["source_url"] for i in its if i["source_url"]}), "research_id": rid,
            "note": "Referencias de partida con fuente oficial; comprueba su vigencia (botón en Cumplimiento) y la aplicación a tu caso concreto. " + ai.DISCLAIMER}


# ───────── informes ─────────
@router.get("/reports/{kind}/{oid}")
def report(kind: str, oid: int, db: DB, fmt: str = "pdf") -> Response:
    if fmt not in ("pdf", "docx"):
        raise HTTPException(422, "Formato: pdf o docx")
    if kind == "research":
        r = _get(db, LgResearch, oid)
        rp = r.report or {}
        rep = reports.build("Investigación jurídica", r.question[:150], f"LG-R-{r.id}", rp.get("resumen", ""), [
            {"title": "Problema jurídico", "paragraphs": [rp.get("problema", ""), f"Jurisdicción: {rp.get('jurisdiccion')}. Ramas: {', '.join(rp.get('ramas') or [])}"]},
            {"title": "Legislación aplicable", "bullets": [f"{x.get('norma')} · arts. {', '.join(x.get('articulos') or []) or '—'} · vigencia: {x.get('vigencia')}"
                                                          + ("" if x.get("verificada_en_fuente") and not x.get("articulos_no_encontrados") else " · NO VERIFICADA EN LA FUENTE")
                                                          for x in rp.get("legislacion", [])]},
            {"title": "Jurisprudencia relevante", "bullets": [f"{x.get('resolucion')}: {x.get('criterio')}" + ("" if x.get("verificada_en_fuente") else " · NO VERIFICADA")
                                                             for x in rp.get("jurisprudencia", [])] or ["No se localizó jurisprudencia en las fuentes leídas."]},
            {"title": "Interpretación jurídica", "paragraphs": [rp.get("interpretacion", "")]},
            {"title": "Aplicación al caso", "paragraphs": [rp.get("aplicacion", "")]},
            {"title": "Riesgos e incertidumbres", "bullets": rp.get("riesgos", []) + rp.get("incertidumbres", [])}],
            sources=[{"id": s["id"], "title": f"{s['organismo']} · {s['titulo']}", "url": s["url"], "accessed": s.get("consultada")} for s in rp.get("fuentes", [])],
            conclusions=[rp.get("conclusion", "")] + (["La complejidad o las consecuencias aconsejan consultar con un abogado."] if rp.get("requiere_abogado") else []))
    elif kind == "analysis":
        a = _get(db, LgAnalysis, oid)
        lg = _get(db, LgDocument, a.legal_doc_id)
        x = a.result or {}
        rep = reports.build("Análisis contractual", lg.title, f"LG-A-{a.id}", x.get("summary") or f"{x.get('type_label')}: {x.get('counts')}", [
            {"title": "Identificación", "bullets": [f"Tipo: {x.get('type_label')}", f"Partes: {', '.join(x.get('entities', {}).get('parties') or x.get('parties_ai') or []) or '—'}",
                                                     f"Fechas: {', '.join(x.get('entities', {}).get('dates') or []) or '—'}", f"Importes: {', '.join(x.get('entities', {}).get('amounts') or []) or '—'}"]},
            {"title": "Riesgos detectados", "bullets": [f"[{r['nivel'].upper()}] {r.get('clausula')}: {r.get('problema')} — «{(r.get('fragmento') or '')[:200]}» → {r.get('recomendacion') or ''}"
                                                       + (f" Redacción alternativa: {r['redaccion_alternativa']}" if r.get("redaccion_alternativa") else "") for r in x.get("risks", [])]},
            {"title": "Posibles contradicciones", "bullets": [c["detalle"] for c in x.get("contradictions", [])] or ["Ninguna detectada por las reglas."]},
            {"title": "Información ausente", "bullets": x.get("missing") or ["—"]},
            {"title": "Obligaciones", "bullets": [f"{o.get('parte')}: {o.get('obligacion')} {o.get('plazo') or ''}" for o in x.get("obligations", [])] or ["—"]}],
            evidence=[r.get("fragmento", "")[:300] for r in x.get("risks", [])[:20]], limitations=[x.get("note", "")])
    elif kind == "comparison":
        c = _get(db, LgComparison, oid)
        x = c.result
        rep = reports.build("Comparación de contratos", f"{db.get(LgDocument, c.a_id).title} ↔ {db.get(LgDocument, c.b_id).title}", f"LG-C-{c.id}",
                            f"Cambios: {x['counts']}. Por categoría: {x['summary']}. Similitud: {x.get('similarity')} %",
                            [{"title": f"{ch['kind'].upper()}: {ch['clause']}", "paragraphs": [f"Antes: {ch['before'] or '—'}", f"Después: {ch['after'] or '—'}"],
                              "bullets": [f"Categorías: {', '.join(ch['categories']) or '—'}"]} for ch in x["changes"]])
    elif kind == "case":
        c = get_case(oid, db)
        rep = reports.build("Resumen de expediente", f"{c['ref']} · {c['name']}", c["ref"], c.get("description") or "", [
            {"title": "Datos", "bullets": [f"Estado: {c['status']}", f"Prioridad: {c['priority']}", f"Categoría: {c.get('category') or '—'}",
                                           f"Jurisdicción: {c['jurisdiction']}", f"Apertura: {c['opened_on']}",
                                           "Partes: " + (", ".join(f"{p.get('name')} ({p.get('role')})" for p in c["parties"]) or "—")]},
            {"title": "Plazos", "bullets": [f"{d['due_on']} · {d['title']} · {'verificado' if d['verified'] else 'SIN VERIFICAR'}" for d in c["deadlines"]] or ["—"]},
            {"title": "Alertas", "bullets": [f"[{a['level_label']}] {a['title']}" for a in c["alerts"]] or ["—"]},
            {"title": "Documentos", "bullets": [f"{d['title']} ({d['kind']}, {d['origin']}, v{d['version']})" for d in c["documents"]] or ["—"]},
            {"title": "Investigaciones", "bullets": [f"{r['question']} — {r['status']}" for r in c["research"]] or ["—"]},
            {"title": "Cronología", "bullets": [f"{e['created_at'][:16]} · {e['summary']}" for e in c["timeline"][:60]]}])
        ev(db, oid, "export", f"Expediente exportado ({fmt})")
        db.commit()
    elif kind in ("compliance", "risks"):
        if kind == "compliance":
            items = list_compliance(db, case_id=oid or None)
            sec = [{"title": lbl, "bullets": [f"{i['obligation']} — {i['norm']} {i['article'] or ''} · estado: {i['status']}" + (f" · responsable: {i['owner']}" if i["owner"] else "")
                                               for i in items if i["applicability"] == k]} for k, lbl in (("confirmada", "Obligaciones confirmadas"),
                                                                                                    ("potencial", "Potencialmente aplicables"), ("asesoramiento", "Requieren asesoramiento profesional"))]
            rep = reports.build("Informe de cumplimiento", "Cumplimiento normativo", f"LG-CMP-{oid}", f"{len(items)} obligaciones registradas", sec,
                                sources=[{"id": i, "title": u, "url": u} for i, u in enumerate(sorted({x["source_url"] for x in items if x["source_url"]}), 1)])
        else:
            al = list_alerts(db, case_id=oid or None)
            rep = reports.build("Informe de riesgos", "Riesgos jurídicos abiertos", f"LG-RSK-{oid}", f"{len(al)} alertas abiertas",
                                [{"title": f"[{a['level_label']}] {a['title']}", "paragraphs": [a["description"], f"Evidencia: {a['evidence'] or '—'}",
                                                                                                  f"Consecuencia posible: {a['consequence'] or '—'}", f"Acción: {a['action'] or '—'}"]} for a in al])
    else:
        raise HTTPException(404, "Tipo de informe desconocido")
    data = reports.pdf(rep) if fmt == "pdf" else reports.docx(rep)
    return _file(data, rep["title"], fmt)


# ───────── ajustes de seguridad ─────────
class SettingsIn(BaseModel):
    allow_cloud: bool


@router.put("/settings")
def settings(body: SettingsIn, db: DB) -> dict:
    set_prefs(db, {"legal": {"allow_cloud": body.allow_cloud}})
    log_activity(db, "security", "legal_cloud", "VISTAN LEGAL: " + ("AUTORIZADO el uso de modelos en la nube" if body.allow_cloud else "solo modelos locales"))
    db.commit()
    return ai.conf(get_prefs(db))
