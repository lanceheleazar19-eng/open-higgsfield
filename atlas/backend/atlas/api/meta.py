"""API de VISTAN META-BRAIN — THINK. COORDINATE. VERIFY. EXECUTE."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.agents.registry import AGENTS
from atlas.agents.tools import TOOLS
from atlas.api.deps import DB
from atlas.brain.base import ProviderError
from atlas.integrations.secrets import delete_secret, set_secret
from atlas.metabrain import bench, engine, evaluation, execution, llm, memory_intel, multimodal
from atlas.metabrain.complexity import analyze
from atlas.metabrain.governance import DEFAULT_META, agent_perms, meta_conf, needs_local
from atlas.models import ActivityLog, Approval, IxArenaRun, IxArenaSuite, MbRun, Memory, Workflow, WorkflowRun
from atlas.services import memory as mem
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs, set_prefs
from atlas.workflows import engine as wf_engine

router = APIRouter(prefix="/api/meta", tags=["meta-brain"])

INTERNAL = [
    {"id": "core", "name": "VISTAN CORE", "role": "Interpreta, detecta complejidad, formula el problema, coordina e integra la respuesta final.",
     "permissions": "Lectura de los datos que reúnen los agentes; no ejecuta acciones."},
    {"id": "critic", "name": "Critic Agent", "role": "Revisa de forma independiente: lógica, evidencia, contradicciones, cálculos, supuestos, "
     "desactualización, riesgos e instrucciones maliciosas. Puede pedir una investigación nueva.", "permissions": "Solo lectura del análisis y las evidencias."},
    {"id": "verifier", "name": "Verifier", "role": "Comprueba sin IA el soporte textual de cada hecho en la evidencia citada, los cálculos y las afirmaciones absolutas.",
     "permissions": "Solo lectura."},
    {"id": "planner", "name": "Execution Planner", "role": "Convierte objetivos en planes con pasos reales del motor de Automatizaciones.",
     "permissions": "Propone; ejecutar requiere que lances el plan y, según tu política, tu autorización por paso."},
]


def _run(db, rid: int) -> MbRun:  # noqa: ANN001
    r = db.get(MbRun, rid)
    if not r:
        raise HTTPException(404, "Ejecución no encontrada")
    return r


# ───────── estado general ─────────
@router.get("/overview")
def overview(db: DB) -> dict:
    prefs = get_prefs(db)
    inv = llm.inventory(prefs)
    runs = list(db.scalars(select(MbRun).order_by(MbRun.id.desc()).limit(8)))
    return {"kill": meta_conf(prefs)["kill"], "providers": [{k: p.get(k) for k in ("id", "label", "kind", "configured", "note")}
                                                           for p in inv["providers"]],
            "models_available": len(llm.candidates("chat", prefs)), "privacy": inv["privacy"],
            "active": [engine.run_dict(r) for r in db.scalars(select(MbRun).where(MbRun.status.in_(("queued", "running", "waiting"))))],
            "recent": [engine.run_dict(r) for r in runs], "pending_approvals": len(list(db.scalars(select(Approval.id).where(Approval.status == "pending")))),
            "eval": evaluation.evaluate(db, 30)["metrics"]}


class TextIn(BaseModel):
    text: str = Field(min_length=2, max_length=6000)


@router.post("/analyze")
def analyze_ep(body: TextIn, db: DB) -> dict:
    """Qué haría el META-BRAIN con esta petición, sin llamar a ningún modelo."""
    prefs = get_prefs(db)
    cx = analyze(body.text, prefs)
    local, why = needs_local(prefs, cx["agents"], cx["personal"])
    return {**cx, "agent_names": [AGENTS[a].name for a in cx["agents"]], "local_only": local, "local_reason": why,
            "phases": engine.PHASES[cx["mode"]], "route": {t: llm.candidates(t, prefs, local)[:3] for t in ("chat", "agents", "json")}}


# ───────── ejecuciones ─────────
class RunIn(BaseModel):
    text: str = Field(min_length=2, max_length=6000)
    mode: str = Field(default="auto", pattern="^(auto|direct|agents|council|research)$")


@router.post("/runs", status_code=201)
def create_run(body: RunIn, db: DB) -> dict:
    if meta_conf(get_prefs(db))["kill"]:
        raise HTTPException(423, "Kill switch activo: desactívalo en Gobierno para volver a ejecutar")
    r = engine.create(db, body.text, body.mode, "console")
    db.commit()
    engine.start(r.id)
    return engine.run_dict(r)


@router.get("/runs")
def list_runs(db: DB, status: str | None = None, limit: int = 40, include_bench: bool = False) -> list[dict]:
    """Las ejecuciones del Benchmark Center se ven desde sus resultados; aquí solo si se piden."""
    q = select(MbRun).order_by(MbRun.id.desc()).limit(min(limit, 200))
    if not include_bench:
        q = q.where(MbRun.source != "bench")
    if status:
        q = q.where(MbRun.status == status)
    return [engine.run_dict(r) for r in db.scalars(q)]


@router.get("/runs/{rid}")
def get_run(rid: int, db: DB) -> dict:
    return engine.run_dict(_run(db, rid), full=True)


@router.post("/runs/{rid}/cancel")
def cancel_run(rid: int, db: DB) -> dict:
    r = _run(db, rid)
    if r.status not in ("queued", "running", "waiting"):
        raise HTTPException(409, "La ejecución no está en curso")
    r.status, r.error, r.finished_at = "cancelled", "Cancelado por ti", datetime.utcnow()
    db.commit()
    return engine.run_dict(r)


@router.post("/runs/{rid}/resume")
def resume_run(rid: int, db: DB) -> dict:
    """Reanuda desde el último checkpoint: las fases ya completadas no se repiten (ni se vuelven a pagar)."""
    r = _run(db, rid)
    if r.status not in ("error", "cancelled"):
        raise HTTPException(409, "Solo se reanuda una ejecución con error o cancelada")
    if meta_conf(get_prefs(db))["kill"]:
        raise HTTPException(423, "Kill switch activo")
    r.status, r.error, r.finished_at = "queued", None, None
    db.commit()
    engine.start(r.id)
    return engine.run_dict(r)


class FeedbackIn(BaseModel):
    value: int = Field(ge=-1, le=1)
    note: str | None = Field(default=None, max_length=1000)


@router.post("/runs/{rid}/feedback")
def feedback(rid: int, body: FeedbackIn, db: DB) -> dict:
    r = _run(db, rid)
    r.feedback, r.feedback_note = (body.value or None), body.note
    db.commit()
    return engine.run_dict(r)


@router.post("/runs/{rid}/remember", status_code=201)
def remember_run(rid: int, db: DB) -> dict:
    """Guarda un EPISODIO (solo si tú lo pides): pregunta y conclusión, con su nivel de privacidad."""
    r = _run(db, rid)
    if r.status != "done" or not r.answer:
        raise HTTPException(409, "Solo se recuerdan ejecuciones terminadas")
    content = f"Episodio META-BRAIN ({r.created_at:%d/%m/%Y}): «{r.request[:200]}» → {r.answer[:600]}"
    m, created = mem.remember(db, content, kind="episode", source="manual")
    if r.local_only and created:
        mem.update_memory(db, m, reason="episodio con datos personales", access="local")
    db.commit()
    return {"memory_id": m.id, "created": created, "access": m.access}


@router.delete("/runs/{rid}", status_code=204)
def delete_run(rid: int, db: DB) -> None:
    r = _run(db, rid)
    if r.status in ("queued", "running", "waiting"):
        raise HTTPException(409, "Cancélala antes de eliminarla")
    db.delete(r)
    db.commit()


# ───────── router ─────────
@router.get("/router")
def router_info(db: DB, days: int = 30) -> dict:
    prefs = get_prefs(db)
    inv = llm.inventory(prefs)
    return {**inv, "stats": llm.stats(days), "chains": {t: llm.candidates(t, prefs) for t in ("chat", "agents", "json", "research")},
            "chains_local": llm.candidates("agents", prefs, local_only=True),
            "note": "Solo aparecen proveedores y modelos realmente accesibles. Coste: solo si configuras precios en Modelos."}


class CompatIn(BaseModel):
    base_url: str = Field(min_length=8, max_length=300)
    model: str = Field(min_length=1, max_length=160)
    label: str | None = Field(default=None, max_length=60)
    api_key: str | None = Field(default=None, max_length=400)


@router.put("/router/compat")
def set_compat(body: CompatIn, db: DB) -> dict:
    if not llm.valid_base_url(body.base_url):
        raise HTTPException(422, "La URL debe ser https:// (o http://localhost para servidores locales como LM Studio)")
    set_secret("compat_base_url", body.base_url.strip())
    set_secret("compat_model", body.model.strip())
    if body.label:
        set_secret("compat_label", body.label.strip())
    if body.api_key:
        set_secret("compat_api_key", body.api_key.strip())
    log_activity(db, "security", "compat_provider", f"Proveedor compatible configurado: {body.base_url}")
    db.commit()
    return {"configured": True}


@router.delete("/router/compat", status_code=204)
def delete_compat(db: DB) -> None:
    for k in ("compat_base_url", "compat_model", "compat_label", "compat_api_key"):
        delete_secret(k)
    log_activity(db, "security", "compat_provider", "Proveedor compatible eliminado")
    db.commit()


@router.post("/router/compat/test")
async def test_compat() -> dict:
    c = llm.compat_conf()
    if not c:
        raise HTTPException(404, "No hay proveedor compatible configurado")
    t0 = datetime.utcnow()
    try:
        text, usage = await run_in_threadpool(llm.raw_call, "compat", c["model"], [{"role": "user", "content": "Responde solo: ok"}])
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300]}
    return {"ok": True, "reply": text[:200], "ms": int((datetime.utcnow() - t0).total_seconds() * 1000), "usage": usage}


# ───────── agentes y gobierno ─────────
@router.get("/agents")
def agents(db: DB) -> dict:
    perms = agent_perms(get_prefs(db))
    return {"agents": [{"id": a.id, "name": a.name, "role": a.role, "limits": a.limits, "helpers": a.helpers,
                        "tools": [{"name": t, "level": TOOLS[t].level, "desc": TOOLS[t].description} for t in a.tools if t in TOOLS],
                        "actions": a.actions, "perms": perms[a.id]} for a in AGENTS.values()], "internal": INTERNAL}


class PermIn(BaseModel):
    enabled: bool | None = None
    memory: bool | None = None
    cloud: bool | None = None


@router.put("/agents/{aid}/perms")
def set_perms(aid: str, body: PermIn, db: DB) -> dict:
    if aid not in AGENTS:
        raise HTTPException(404, "Agente desconocido")
    prefs = get_prefs(db)
    saved = dict(prefs.get("agent_perms") or {})
    saved[aid] = {**agent_perms(prefs)[aid], **body.model_dump(exclude_none=True)}
    set_prefs(db, {"agent_perms": saved})
    log_activity(db, "security", "agent_perms", f"Permisos de {AGENTS[aid].name}: {saved[aid]}")
    db.commit()
    return saved[aid]


@router.get("/governance")
def governance(db: DB) -> dict:
    prefs = get_prefs(db)
    return {"meta": meta_conf(prefs), "defaults": DEFAULT_META, "policy": prefs.get("security_policy") or {},
            "backups": "/security", "credentials": "Las claves se guardan en el Llavero del sistema; nunca en la base de datos ni en el navegador."}


class LimitsIn(BaseModel):
    max_calls: int | None = Field(default=None, ge=1, le=60)
    max_seconds: int | None = Field(default=None, ge=30, le=3600)
    max_cost_usd: float | None = Field(default=None, ge=0, le=100)


class GovIn(BaseModel):
    limits: LimitsIn | None = None
    council_size: int | None = Field(default=None, ge=2, le=4)
    diverse_models: bool | None = None
    allow_cloud_personal: bool | None = None
    auto_research: bool | None = None
    clear_cost_limit: bool = False


@router.put("/governance")
def set_governance(body: GovIn, db: DB) -> dict:
    prefs = get_prefs(db)
    m = meta_conf(prefs)
    ch = body.model_dump(exclude_none=True, exclude={"limits", "clear_cost_limit"})
    m.update(ch)
    if body.limits:
        m["limits"] = {**m["limits"], **body.limits.model_dump(exclude_none=True)}
    if body.clear_cost_limit:
        m["limits"]["max_cost_usd"] = None
    set_prefs(db, {"meta": m})
    log_activity(db, "security", "meta_governance", f"Gobierno META-BRAIN actualizado: {ch or ''} {m['limits']}")
    db.commit()
    return m


class KillIn(BaseModel):
    on: bool


@router.post("/governance/kill")
def kill(body: KillIn, db: DB) -> dict:
    """Kill switch: detiene al momento el META-BRAIN, automatizaciones, Arena, investigaciones y sandbox."""
    prefs = get_prefs(db)
    m = meta_conf(prefs)
    m["kill"] = body.on
    set_prefs(db, {"meta": m})
    stopped = {"meta": 0, "workflows": 0, "arena": 0}
    if body.on:
        now = datetime.utcnow()
        for r in db.scalars(select(MbRun).where(MbRun.status.in_(("queued", "running", "waiting")))):
            r.status, r.error, r.finished_at = "cancelled", "Kill switch", now
            stopped["meta"] += 1
        for r in db.scalars(select(WorkflowRun).where(WorkflowRun.status.in_(("running", "awaiting_approval")))):
            r.status, r.output, r.finished_at = "cancelled", "Kill switch", now
            stopped["workflows"] += 1
        for r in db.scalars(select(IxArenaRun).where(IxArenaRun.status.in_(("queued", "running")))):
            r.status, r.error, r.finished_at = "error", "Kill switch", now
            stopped["arena"] += 1
    log_activity(db, "security", "kill_switch", ("ACTIVADO" if body.on else "desactivado") + f" · detenidos: {stopped}")
    db.commit()
    return {"kill": body.on, "stopped": stopped}


@router.get("/governance/audit")
def audit(db: DB, limit: int = 80) -> dict:
    mods = ("metabrain", "security", "memory", "workflows", "agents", "lab")
    log = [{"at": a.created_at.isoformat(), "module": a.module, "action": a.action, "summary": a.summary}
           for a in db.scalars(select(ActivityLog).where(ActivityLog.module.in_(mods)).order_by(ActivityLog.id.desc()).limit(min(limit, 300)))]
    inj = []
    for r in db.scalars(select(MbRun).order_by(MbRun.id.desc()).limit(200)):
        n = ((r.state or {}).get("context") or {}).get("injection_flags", 0)
        if n:
            inj.append({"run_id": r.id, "flags": n, "request": r.request[:120], "at": r.created_at.isoformat()})
    pend = [{"id": a.id, "level": a.level, "summary": a.summary, "at": a.created_at.isoformat()}
            for a in db.scalars(select(Approval).where(Approval.status == "pending").order_by(Approval.id.desc()))]
    return {"log": log, "injections": inj, "pending_approvals": pend}


# ───────── memoria ─────────
@router.get("/memory")
def memory_overview(db: DB) -> dict:
    return {**memory_intel.overview(db), **memory_intel.analyze_pairs(db)}


@router.get("/memory/{mid}/history")
def memory_history(mid: int, db: DB) -> list[dict]:
    if not db.get(Memory, mid):
        raise HTTPException(404, "Recuerdo no encontrado")
    return memory_intel.history(db, mid)


class PairIn(BaseModel):
    keep_id: int
    other_id: int


def _pair(db, body: PairIn) -> tuple[Memory, Memory]:  # noqa: ANN001
    a, b = db.get(Memory, body.keep_id), db.get(Memory, body.other_id)
    if not a or not b or a.id == b.id:
        raise HTTPException(404, "Recuerdos no válidos")
    return a, b


@router.post("/memory/resolve")
def memory_resolve(body: PairIn, db: DB) -> dict:
    keep, old = _pair(db, body)
    memory_intel.resolve(db, keep, old, f"reemplazado por #{keep.id} (contradicción resuelta)")
    db.commit()
    return {"kept": keep.id, "superseded": old.id}


@router.post("/memory/merge")
def memory_merge(body: PairIn, db: DB) -> dict:
    keep, drop = _pair(db, body)
    memory_intel.merge(db, keep, drop)
    db.commit()
    return {"kept": keep.id, "deleted": body.other_id}


class AccessIn(BaseModel):
    access: str = Field(pattern="^(all|local|private)$")


@router.put("/memory/{mid}/access")
def memory_access(mid: int, body: AccessIn, db: DB) -> dict:
    m = db.get(Memory, mid)
    if not m:
        raise HTTPException(404, "Recuerdo no encontrado")
    mem.update_memory(db, m, reason="control de acceso", access=body.access)
    db.commit()
    return mem.to_dict(m, str(get_prefs(db)["timezone"]))


@router.post("/memory/check")
async def memory_check(body: PairIn, db: DB) -> dict:
    """Confirma con un modelo LOCAL (la memoria es personal) si dos recuerdos se contradicen."""
    a, b = _pair(db, body)
    if "private" in (a.access, b.access):
        raise HTTPException(403, "Uno de los recuerdos es privado: no se envía a ningún modelo")
    prefs = get_prefs(db)
    msgs = [{"role": "system", "content": 'Compara dos recuerdos del usuario. JSON: {"contradiccion": bool, "explicacion": str, '
             '"vigente": "A"|"B"|"desconocido"}. «vigente» = cuál parece más actual SOLO si el texto lo indica.'},
            {"role": "user", "content": f"A ({a.updated_at:%Y-%m-%d}): {a.content}\nB ({b.updated_at:%Y-%m-%d}): {b.content}"}]
    try:
        res = await run_in_threadpool(lambda: llm.call("json", prefs, msgs, json_mode=True, local_only=True, tag="meta_memcheck"))
    except ProviderError as exc:
        raise HTTPException(503, f"Necesita un modelo local: {exc}") from exc
    return {**(res["data"] or {}), "model": res["model"]}


# ───────── evaluación, benchmarks, multimodal ─────────
@router.get("/eval")
def eval_ep(db: DB, days: int = 30) -> dict:
    return evaluation.evaluate(db, max(1, min(days, 365)))


@router.post("/bench/install")
def bench_install(db: DB) -> dict:
    s = bench.install(db)
    db.commit()
    return {"suite_id": s.id, "tests": len(s.tests)}


@router.get("/bench")
def bench_info(db: DB) -> dict:
    s = db.scalar(select(IxArenaSuite).where(IxArenaSuite.name == bench.SUITE_NAME))
    if not s:
        return {"installed": False, "categories": bench.CATEGORIES, "tests": len(bench.TESTS)}
    runs = [{"id": r.id, "model": r.model, "status": r.status, "summary": r.summary, "results": r.results, "error": r.error,
             "created_at": r.created_at.isoformat()} for r in db.scalars(select(IxArenaRun).where(IxArenaRun.suite_id == s.id).order_by(IxArenaRun.id.desc()).limit(30))]
    latest: dict[str, dict] = {}
    for r in runs:
        latest.setdefault(r["model"], r)
    return {"installed": True, "suite_id": s.id, "tests": s.tests, "runs": runs, "compare": bench.compare(list(latest.values()), s.tests),
            "conditions": "Mismas pruebas, mismo orden y misma comprobación automática para todos. Ollama a temperatura 0; "
                          "en la nube, la temperatura por defecto del proveedor. «Herramientas» mide el acceso a tus datos."}


@router.get("/multimodal")
def mm(db: DB) -> list[dict]:
    return multimodal.matrix(get_prefs(db))


# ───────── ejecución autónoma ─────────
class GoalIn(BaseModel):
    goal: str = Field(min_length=6, max_length=2000)


@router.get("/exec/catalog")
def exec_catalog() -> list[dict]:
    return execution.step_catalog()


@router.post("/exec/plan")
async def exec_plan(body: GoalIn, db: DB) -> dict:
    prefs = get_prefs(db)
    try:
        return await run_in_threadpool(execution.plan, prefs, body.goal)
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc


class ExecIn(BaseModel):
    goal: str = Field(min_length=6, max_length=2000)
    name: str = Field(min_length=2, max_length=120)
    steps: list[dict] = Field(min_length=1, max_length=execution.MAX_STEPS)


def _exec_thread(run_id: int) -> None:
    from atlas.db import session_scope
    with session_scope() as d:
        wf_engine.execute(d, d.get(WorkflowRun, run_id))


@router.post("/exec", status_code=201)
def exec_start(body: ExecIn, db: DB) -> dict:
    prefs = get_prefs(db)
    if meta_conf(prefs)["kill"]:
        raise HTTPException(423, "Kill switch activo")
    try:
        wf = execution.create(db, body.name, body.goal, body.steps, prefs)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    run = WorkflowRun(workflow_id=wf.id, params={}, trigger="manual", log=[])
    db.add(run)
    log_activity(db, "metabrain", "exec", f"Objetivo lanzado: {body.goal[:100]} ({len(wf.steps)} pasos)")
    db.commit()
    wf_engine.run_in_thread(_exec_thread, run.id)
    return {"workflow_id": wf.id, "run_id": run.id}


@router.get("/exec")
def exec_list(db: DB) -> list[dict]:
    out = []
    for wf in db.scalars(select(Workflow).where(Workflow.key.like("meta-%")).order_by(Workflow.id.desc()).limit(30)):
        runs = list(db.scalars(select(WorkflowRun).where(WorkflowRun.workflow_id == wf.id).order_by(WorkflowRun.id.desc()).limit(5)))
        out.append({**wf_engine.wf_dict(wf), "goal": (wf.description or "").replace("[META-BRAIN] Objetivo: ", ""),
                    "runs": [wf_engine.run_dict(r, wf) for r in runs]})
    return out

