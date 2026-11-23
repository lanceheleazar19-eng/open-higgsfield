from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.brain.orchestrator import suggest_memories
from atlas.models import Conversation, ConversationMessage, Memory
from atlas.models.base import utcnow
from atlas.models.memory import MEMORY_KINDS
from atlas.services import conversations as convs
from atlas.services import memory as mem
from atlas.services.preferences import get_prefs

router = APIRouter(tags=["memory"])
KIND_PATTERN = "^(" + "|".join(MEMORY_KINDS) + ")$"


def _tz(db) -> str:  # noqa: ANN001
    return str(get_prefs(db)["timezone"])


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        raise HTTPException(422, "La fecha de caducidad debe incluir zona horaria")
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


class MemoryIn(BaseModel):
    content: str = Field(min_length=2, max_length=2000)
    kind: str = Field(default="fact", pattern=KIND_PATTERN)
    expires_at: datetime | None = None
    project_id: int | None = None
    source: str = Field(default="manual", pattern="^(manual|suggested)$")


class MemoryPatch(BaseModel):
    content: str | None = Field(default=None, min_length=2, max_length=2000)
    kind: str | None = Field(default=None, pattern=KIND_PATTERN)
    expires_at: datetime | None = None
    permanent: bool | None = None  # True => quita la caducidad


@router.get("/api/memory")
def list_memories(db: DB, q: str = "", kind: str | None = None, include_expired: bool = False,
                  limit: int = Query(200, le=1000)) -> dict:
    tz = _tz(db)
    if q.strip():
        items = mem.search_memories(db, q, limit=limit, include_expired=include_expired)
    else:
        stmt = select(Memory).order_by(Memory.updated_at.desc()).limit(limit)
        if not include_expired:
            stmt = stmt.where(mem._active_clause(utcnow()))
        items = list(db.scalars(stmt))
    if kind:
        items = [m for m in items if m.kind == kind]
    return {"items": [mem.to_dict(m, tz) for m in items], **mem.counts(db)}


@router.post("/api/memory", status_code=201)
def create_memory(body: MemoryIn, db: DB) -> JSONResponse:
    m, created = mem.remember(db, body.content, kind=body.kind, expires_at=_to_utc(body.expires_at),
                              source=body.source, project_id=body.project_id)
    db.commit()
    return JSONResponse({"memory": mem.to_dict(m, _tz(db)), "created": created}, status_code=201 if created else 200)


@router.patch("/api/memory/{memory_id}")
def patch_memory(memory_id: int, body: MemoryPatch, db: DB) -> dict:
    m = db.get(Memory, memory_id)
    if not m:
        raise HTTPException(404, "Recuerdo no encontrado")
    changes = body.model_dump(exclude_unset=True, exclude={"permanent", "expires_at"})
    if body.permanent:
        changes["expires_at"] = None
    elif "expires_at" in body.model_fields_set:
        changes["expires_at"] = _to_utc(body.expires_at)
    if "content" in changes:
        dup = mem.find_duplicate(db, changes["content"], m.project_id)
        if dup and dup.id != m.id:
            raise HTTPException(409, f"Ya existe un recuerdo igual: «{dup.content}»")
    mem.update_memory(db, m, **changes)
    db.commit()
    return mem.to_dict(m, _tz(db))


@router.delete("/api/memory/{memory_id}", status_code=204)
def delete_memory(memory_id: int, db: DB) -> None:
    m = db.get(Memory, memory_id)
    if not m:
        raise HTTPException(404, "Recuerdo no encontrado")
    mem.forget(db, m)
    db.commit()


@router.post("/api/memory/purge-expired")
def purge(db: DB) -> dict:
    n = mem.purge_expired(db)
    db.commit()
    return {"deleted": n}


class SuggestIn(BaseModel):
    conversation_id: int


@router.post("/api/memory/suggest")
def suggest(body: SuggestIn, db: DB) -> dict:
    """Propone recuerdos a partir del último intercambio. No guarda nada."""
    last = db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id == body.conversation_id)
                      .order_by(ConversationMessage.id.desc()).limit(2)).all()
    if len(last) < 2 or last[1].role != "user" or last[0].role != "assistant":
        return {"suggestions": []}
    existing = [m.content for m in db.scalars(select(Memory).order_by(Memory.updated_at.desc()).limit(30))]
    out = []
    for s in suggest_memories(get_prefs(db), last[1].content, last[0].content, existing):
        if not mem.find_duplicate(db, s["content"]):
            out.append(s)  # {content, kind, temporary}: el usuario decide si lo guarda
    return {"suggestions": out}


@router.get("/api/conversations")
def list_conversations(db: DB, q: str = "") -> dict:
    tz = _tz(db)
    if q.strip():
        hits = mem.search_messages(db, q, limit=30)
        return {"hits": [convs.message_dict(m, tz) for m in hits]}
    return {"items": convs.list_conversations(db, tz)}


@router.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: int, db: DB) -> dict:
    c = db.get(Conversation, conversation_id)
    if not c:
        raise HTTPException(404, "Conversación no encontrada")
    return convs.conversation_detail(db, c, _tz(db))


@router.delete("/api/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: DB) -> None:
    c = db.get(Conversation, conversation_id)
    if not c:
        raise HTTPException(404, "Conversación no encontrada")
    db.delete(c)
    db.commit()


@router.get("/api/memory/export")
def export(db: DB) -> JSONResponse:
    """Exporta toda la memoria y las conversaciones (JSON descargable)."""
    tz = _tz(db)
    data = {
        "atlas_export": "memoria",
        "generado": datetime.now(timezone.utc).isoformat(),
        "recuerdos": [mem.to_dict(m, tz) for m in db.scalars(select(Memory).order_by(Memory.id))],
        "conversaciones": [convs.conversation_detail(db, c, tz)
                           for c in db.scalars(select(Conversation).order_by(Conversation.id))],
    }
    fname = f"atlas-memoria-{datetime.now():%Y%m%d-%H%M}.json"
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="{fname}"'})
