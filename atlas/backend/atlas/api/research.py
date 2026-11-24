from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.models import Relation, Research
from atlas.research import engine
from atlas.services import memory as mem
from atlas.services.activity import log_activity

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchIn(BaseModel):
    question: str = Field(min_length=4, max_length=1000)
    project_id: int | None = None


@router.get("")
def list_research(db: DB) -> list[dict]:
    return [engine.to_dict(r) for r in db.scalars(select(Research).order_by(Research.created_at.desc()).limit(100))]


@router.post("", status_code=201)
def create(body: ResearchIn, db: DB) -> dict:
    r = Research(question=body.question.strip(), project_id=body.project_id, status="queued", state={})
    db.add(r)
    log_activity(db, "research", "start", body.question[:150])
    db.commit()
    engine.start(r.id)
    return engine.to_dict(r)


def _get(db, rid: int) -> Research:  # noqa: ANN001
    r = db.get(Research, rid)
    if not r:
        raise HTTPException(404, "Investigación no encontrada")
    return r


@router.get("/{rid}")
def get_one(rid: int, db: DB) -> dict:
    return engine.to_dict(_get(db, rid), full=True)


@router.post("/{rid}/resume")
def resume(rid: int, db: DB) -> dict:
    r = _get(db, rid)
    if r.status in ("done", "running"):
        raise HTTPException(409, "Esta investigación no necesita reanudarse")
    r.status = "queued"
    db.commit()
    engine.start(r.id)
    return engine.to_dict(r)


@router.post("/{rid}/save")
def save_to_memory(rid: int, db: DB) -> dict:
    r = _get(db, rid)
    if r.status != "done" or not r.report:
        raise HTTPException(409, "Guarda la investigación cuando haya terminado")
    concl = "; ".join(c["text"] for c in r.report.get("conclusions", [])[:4])
    content = f"Investigación «{r.question}»: {r.report.get('summary', '')}" + (f" Conclusiones: {concl}" if concl else "")
    m, created = mem.remember(db, content[:3000], kind="note", source="manual", project_id=r.project_id)
    if created:
        db.add(Relation(src_type="memory", src_id=m.id, dst_type="research", dst_id=r.id, label="resume"))
    db.commit()
    return {"memory_id": m.id, "created": created}


@router.delete("/{rid}", status_code=204)
def delete(rid: int, db: DB) -> None:
    db.delete(_get(db, rid))
    db.commit()
