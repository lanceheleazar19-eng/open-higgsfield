"""Correos recibidos (solo cabeceras y un extracto) y su clasificación de importancia."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[str] = mapped_column(String(300), unique=True)
    sender: Mapped[str] = mapped_column(String(300))
    subject: Mapped[str] = mapped_column(String(500))
    received_at: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC
    snippet: Mapped[str] = mapped_column(Text, default="")
    important: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), index=True)
    reason: Mapped[str | None] = mapped_column(String(300))
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
