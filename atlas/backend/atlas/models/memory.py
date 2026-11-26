"""Memoria persistente: recuerdos y conversaciones."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow

MEMORY_KINDS = ("preference", "goal", "decision", "fact", "note", "procedure", "episode")
# all: cualquier modelo/agente · local: nunca sale a modelos en la nube · private: nunca entra en el contexto de la IA
MEMORY_ACCESS = ("all", "local", "private")
MEMORY_SOURCES = ("manual", "chat", "suggested")


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(f"kind IN {MEMORY_KINDS}", name="kind"),
        CheckConstraint(f"source IN {MEMORY_SOURCES}", name="source"),
        CheckConstraint(f"access IN {MEMORY_ACCESS}", name="access"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16), default="fact", index=True)
    # Temporal si tiene fecha de caducidad; permanente si es NULL
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    # Alcance: global (NULL) o un proyecto concreto (memoria independiente por proyecto)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    content_key: Mapped[str] = mapped_column(String(64), index=True)  # huella normalizada (duplicados)
    access: Mapped[str] = mapped_column(String(8), default="all", server_default="all")
    # Si otro recuerdo lo actualiza (contradicción resuelta), este queda como histórico y no se usa como contexto
    superseded_by: Mapped[int | None] = mapped_column(ForeignKey("memories.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    mode: Mapped[str | None] = mapped_column(String(8))  # ai | local (solo respuestas)
    model: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
