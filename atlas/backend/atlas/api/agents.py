"""Sistema multiagente: catálogo, ejecuciones con su traza y aprobaciones."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.agents.core import answer, run_dict
from atlas.agents.registry import AGENTS
from atlas.agents.tools import ACTIONS, TOOLS
from atlas.api.deps import DB
from atlas.models import AgentRun, Approval
from atlas.security.policy import LEVELS, decide, policy
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
def catalog(db: DB) -> dict:
    prefs = get_prefs(db)
    runs = list(db.scalars(select(AgentRun).order_by(AgentRun.id.desc()).limit(300)))
    stats = {a: {"runs": 0, "last": None} for a in AGENTS}
    for r in runs:
        for a in r.agents:
            if a in stats:
                stats[a]["runs"] += 1
                stats[a]["last"] = stats[a]["last"] or r.created_at.isoformat()
    return {
        "core": {"name": "ATLAS CORE", "role": "Recibe cada petición, elige agentes y herramientas, consulta la memoria, "
                                               "ejecuta lo autorizado y redacta la respuesta."},
        "agents": [{"id": a.id, "name": a.name, "role": a.role, "limits": a.limits,
                    "tools": [{"name": t, "level": TOOLS[t].level, "description": TOOLS[t].description} for t in a.tools],
                    "actions": [{"name": x, "level": ACTIONS[x][0], "description": ACTIONS[x][1]} for x in a.actions],
                    **stats[a.id]} for a in AGENTS.values()],
        "levels": LEVELS, "policy": policy(prefs),
    }


class RunIn(BaseModel):
    text: str = Field(min_length=2, max_length=4000)
    agents: list[str] | None = None


@router.post("/run")
def run_agents(body: RunIn, db: DB) -> dict:
    prefs = get_prefs(db)
    r = answer(db, body.text, prefs, str(prefs["timezone"]), body.agents, source="manual")
    db.commit()
    return r


@router.get("/runs")
def runs(db: DB, limit: int = 50) -> list[dict]:
    return [run_dict(r) for r in db.scalars(select(AgentRun).order_by(AgentRun.id.desc()).limit(min(limit, 200)))]


@router.get("/runs/{rid}")
def run_detail(rid: int, db: DB) -> dict:
    r = db.get(AgentRun, rid)
    if not r:
        raise HTTPException(404, "Ejecución no encontrada")
    return run_dict(r)


def approval_dict(a: Approval) -> dict:
    return {"id": a.id, "action": a.action, "level": a.level, "summary": a.summary, "payload": a.payload,
            "status": a.status, "result": a.result, "workflow_run_id": a.workflow_run_id,
            "created_at": a.created_at.isoformat(), "decided_at": a.decided_at.isoformat() if a.decided_at else None}


@router.get("/approvals")
def approvals(db: DB, status: str = "pending") -> list[dict]:
    q = select(Approval).order_by(Approval.id.desc()).limit(100)
    if status != "all":
        q = q.where(Approval.status == status)
    return [approval_dict(a) for a in db.scalars(q)]


class DecideIn(BaseModel):
    approve: bool


@router.post("/approvals/{aid}")
def decide_approval(aid: int, body: DecideIn, db: DB) -> dict:
    a = db.get(Approval, aid)
    if not a:
        raise HTTPException(404, "Solicitud no encontrada")
    if a.status != "pending":
        raise HTTPException(409, "Esta solicitud ya se decidió")
    decide(db, a, body.approve)
    db.commit()
    if a.workflow_run_id:
        from atlas.workflows.engine import resume_after_approval
        resume_after_approval(db, a)
    return approval_dict(a)
