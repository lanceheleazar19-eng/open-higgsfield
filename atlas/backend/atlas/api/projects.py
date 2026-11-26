"""Workspaces: cada proyecto con su información, tareas, notas, documentos, investigaciones,
entidades, informes e historial. La IA usa el contexto del proyecto sin mezclarlo con lo demás."""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from atlas.api.deps import DB
from atlas.knowledge.service import doc_dict
from atlas.models import ActivityLog, Document, Entity, Memory, Project, Research, Task
from atlas.research.engine import to_dict as research_dict
from atlas.services import memory as mem
from atlas.services import tasks as tasks_svc
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: str = Field(default="active", pattern="^(active|paused|done|archived)$")


def _counts(db, p: Project) -> dict:  # noqa: ANN001
    now = datetime.utcnow()
    q = lambda *w: db.scalar(select(func.count(Task.id)).where(Task.project_id == p.id, *w)) or 0  # noqa: E731
    total, done = q(), q(Task.status == "done")
    return {"tasks_total": total, "tasks_done": done, "tasks_open": total - done,
            "tasks_overdue": q(Task.status == "pending", Task.due_at < now),
            "progress": round(100 * done / total) if total else None,
            "notes": db.scalar(select(func.count(Memory.id)).where(Memory.project_id == p.id)) or 0,
            "documents": db.scalar(select(func.count(Document.id)).where(Document.project_id == p.id)) or 0,
            "research": db.scalar(select(func.count(Research.id)).where(Research.project_id == p.id)) or 0}


def pdict(db, p: Project) -> dict:  # noqa: ANN001
    return {"id": p.id, "name": p.name, "description": p.description, "status": p.status,
            "created_at": p.created_at.isoformat(), "updated_at": p.updated_at.isoformat() if p.updated_at else None} | _counts(db, p)


@router.get("")
def list_projects(db: DB) -> list[dict]:
    return [pdict(db, p) for p in db.scalars(select(Project).order_by(Project.status, Project.updated_at.desc()))]


@router.post("", status_code=201)
def create(body: ProjectIn, db: DB) -> dict:
    p = Project(**body.model_dump())
    db.add(p)
    db.flush()
    log_activity(db, "projects", "create", f"Proyecto «{p.name}»")
    db.commit()
    return pdict(db, p)


def _p(db, pid: int) -> Project:  # noqa: ANN001
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "Proyecto no encontrado")
    return p


@router.get("/{pid}")
def detail(pid: int, db: DB) -> dict:
    p = _p(db, pid)
    tz = str(get_prefs(db)["timezone"])
    tasks = list(db.scalars(select(Task).where(Task.project_id == pid).order_by(Task.status, Task.due_at)))
    names = tasks_svc.names_for(db, tasks)
    words = [w for w in p.name.lower().split() if len(w) > 3]
    history = [{"module": a.module, "summary": a.summary, "created_at": a.created_at.isoformat()}
               for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id.desc()).limit(400))
               if p.name.lower() in a.summary.lower() or (words and all(w in a.summary.lower() for w in words))][:30]
    return pdict(db, p) | {
        "tasks": [tasks_svc.to_dict(t, tz, names=names) for t in tasks],
        "notes": [mem.to_dict(m, tz) for m in db.scalars(select(Memory).where(Memory.project_id == pid).order_by(Memory.updated_at.desc()))],
        "documents": [doc_dict(d) for d in db.scalars(select(Document).where(Document.project_id == pid, Document.vault.is_(None)).order_by(Document.created_at.desc()))],
        "research": [research_dict(r) for r in db.scalars(select(Research).where(Research.project_id == pid).order_by(Research.created_at.desc()))],
        "entities": [{"id": e.id, "name": e.name, "kind": e.kind} for e in db.scalars(select(Entity).where(Entity.project_id == pid))],
        "history": history,
    }


@router.put("/{pid}")
def update(pid: int, body: ProjectIn, db: DB) -> dict:
    p = _p(db, pid)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    log_activity(db, "projects", "update", f"Proyecto «{p.name}» actualizado ({p.status})")
    db.commit()
    return pdict(db, p)


@router.delete("/{pid}", status_code=204)
def delete(pid: int, db: DB) -> None:
    p = _p(db, pid)
    log_activity(db, "projects", "delete", f"Proyecto «{p.name}» eliminado")
    db.delete(p)  # tareas/documentos quedan sin proyecto; las notas del proyecto se borran con él
    db.commit()


class NoteIn(BaseModel):
    content: str = Field(min_length=2, max_length=4000)
    kind: str = Field(default="note", pattern="^(note|decision|goal|preference|fact)$")


@router.post("/{pid}/notes", status_code=201)
def add_note(pid: int, body: NoteIn, db: DB) -> dict:
    p = _p(db, pid)
    m, created = mem.remember(db, body.content, kind=body.kind, source="manual", project_id=p.id)
    p.updated_at = datetime.utcnow()
    db.commit()
    return {"id": m.id, "created": created}


class TaskIn(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")


@router.post("/{pid}/tasks", status_code=201)
def add_task(pid: int, body: TaskIn, db: DB) -> dict:
    p = _p(db, pid)
    t = tasks_svc.create_task(db, title=body.title, priority=body.priority, project_id=p.id)
    p.updated_at = datetime.utcnow()
    db.commit()
    return tasks_svc.to_dict(t, str(get_prefs(db)["timezone"]))


@router.post("/{pid}/analysis")
def analysis(pid: int, db: DB) -> dict:
    from atlas.workflows.engine import project_analysis
    _p(db, pid)
    return {"report": project_analysis(db, pid, get_prefs(db))}
