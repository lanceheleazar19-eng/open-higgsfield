"""Historial de conversaciones con ATLAS."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.models import Conversation, ConversationMessage
from atlas.models.base import utcnow
from atlas.services.clock import utc_naive_to_local


def get_or_create(db: Session, conversation_id: int | None, first_text: str) -> Conversation:
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if conv:
            return conv
    title = first_text.strip().replace("\n", " ")
    conv = Conversation(title=title[:80] + ("…" if len(title) > 80 else ""))
    db.add(conv)
    db.flush()
    return conv


def add_message(db: Session, conv: Conversation, role: str, content: str,
                mode: str | None = None, model: str | None = None) -> ConversationMessage:
    msg = ConversationMessage(conversation_id=conv.id, role=role, content=content, mode=mode, model=model)
    db.add(msg)
    conv.updated_at = utcnow()
    db.flush()
    return msg


def history(db: Session, conv: Conversation, limit: int = 12) -> list[dict]:
    rows = db.scalars(
        select(ConversationMessage).where(ConversationMessage.conversation_id == conv.id)
        .order_by(ConversationMessage.id.desc()).limit(limit)
    ).all()
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]


def message_dict(m: ConversationMessage, tz: str) -> dict:
    return {"id": m.id, "conversation_id": m.conversation_id, "role": m.role, "content": m.content,
            "mode": m.mode, "model": m.model, "created_at": utc_naive_to_local(m.created_at, tz).isoformat()}


def list_conversations(db: Session, tz: str, limit: int = 50) -> list[dict]:
    n = (select(ConversationMessage.conversation_id, func.count().label("n"))
         .group_by(ConversationMessage.conversation_id).subquery())
    rows = db.execute(
        select(Conversation, func.coalesce(n.c.n, 0)).outerjoin(n, n.c.conversation_id == Conversation.id)
        .order_by(Conversation.updated_at.desc()).limit(limit)
    ).all()
    return [{"id": c.id, "title": c.title, "messages": int(k),
             "created_at": utc_naive_to_local(c.created_at, tz).isoformat(),
             "updated_at": utc_naive_to_local(c.updated_at, tz).isoformat()} for c, k in rows]


def conversation_detail(db: Session, conv: Conversation, tz: str) -> dict:
    msgs = db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id == conv.id)
                      .order_by(ConversationMessage.id)).all()
    return {"id": conv.id, "title": conv.title,
            "created_at": utc_naive_to_local(conv.created_at, tz).isoformat(),
            "messages": [message_dict(m, tz) for m in msgs]}
