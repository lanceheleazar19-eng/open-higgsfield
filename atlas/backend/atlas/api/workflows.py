from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.models import Workflow, WorkflowRun
from atlas.workflows import engine

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class StepIn(BaseModel):
    type: str
    params: dict = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def known(cls, v: str) -> str:
        if v not in engine.STEP_TYPES:
            raise ValueError(f"Paso desconocido: {v}")
        return v


class WorkflowIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    steps: list[StepIn] = Field(min_length=1, max_length=20)
    schedule: str | None = Field(default=None, pattern=r"^(daily \d{1,2}:\d{2}|weekly [0-6] \d{1,2}:\d{2})$")
    enabled: bool = True


@router.get("")
def list_workflows(db: DB) -> dict:
    return {"workflows": [engine.wf_dict(w) for w in db.scalars(select(Workflow).order_by(Workflow.builtin.desc(), Workflow.id))],
            "step_types": {k: {"level": v[0], "label": v[1], "params": v[2]} for k, v in engine.STEP_TYPES.items()}}


@router.post("", status_code=201)
def create(body: WorkflowIn, db: DB) -> dict:
    w = Workflow(name=body.name, description=body.description, steps=[s.model_dump() for s in body.steps],
                 schedule=body.schedule, enabled=body.enabled)
    db.add(w)
    db.commit()
    return engine.wf_dict(w)


def _wf(db, wid: int) -> Workflow:  # noqa: ANN001
    w = db.get(Workflow, wid)
    if not w:
        raise HTTPException(404, "Workflow no encontrado")
    return w


@router.put("/{wid}")
def update(wid: int, body: WorkflowIn, db: DB) -> dict:
    w = _wf(db, wid)
    if w.builtin:  # los predefinidos: solo horario y activación
        w.schedule, w.enabled = body.schedule, body.enabled
    else:
        w.name, w.description, w.steps = body.name, body.description, [s.model_dump() for s in body.steps]
        w.schedule, w.enabled = body.schedule, body.enabled
    db.commit()
    return engine.wf_dict(w)


@router.delete("/{wid}", status_code=204)
def delete(wid: int, db: DB) -> None:
    w = _wf(db, wid)
    if w.builtin:
        raise HTTPException(409, "Los workflows predefinidos no se borran (puedes desactivarlos)")
    db.delete(w)
    db.commit()


class RunIn(BaseModel):
    params: dict = Field(default_factory=dict)


@router.post("/{wid}/run")
def run(wid: int, body: RunIn, db: DB) -> dict:
    w = _wf(db, wid)
    missing = [p for p in engine.wf_dict(w)["needs"] if not body.params.get(p)]
    if missing:
        raise HTTPException(422, "Falta: " + ", ".join({"project_id": "proyecto", "question": "pregunta"}.get(m, m) for m in missing))
    r = engine.start(db, w, {k: v for k, v in body.params.items() if not k.startswith("_")})
    return engine.run_dict(r, w)


@router.get("/runs")
def runs(db: DB, workflow_id: int | None = None, limit: int = 30) -> list[dict]:
    q = select(WorkflowRun).order_by(WorkflowRun.id.desc()).limit(min(limit, 100))
    if workflow_id:
        q = q.where(WorkflowRun.workflow_id == workflow_id)
    names = {w.id: w for w in db.scalars(select(Workflow))}
    return [engine.run_dict(r, names.get(r.workflow_id)) for r in db.scalars(q)]


@router.get("/runs/{rid}")
def run_detail(rid: int, db: DB) -> dict:
    r = db.get(WorkflowRun, rid)
    if not r:
        raise HTTPException(404, "Ejecución no encontrada")
    return engine.run_dict(r, db.get(Workflow, r.workflow_id))
