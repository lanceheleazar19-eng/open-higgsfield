"""META-BRAIN: ejecuciones trazables del cerebro central e historial de cambios de la memoria."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class MbRun(Base):
    """Una petición resuelta por el META-BRAIN: análisis, plan, traza de cada fase, evidencias, crítica,
    verificación, modelos usados, coste y resultado. Reanudable desde su último checkpoint."""

    __tablename__ = "mb_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(12), default="auto")  # direct | agents | council | research
    requested_mode: Mapped[str] = mapped_column(String(12), default="auto")
    source: Mapped[str] = mapped_column(String(12), default="console")  # console | chat | workflow | bench
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued running waiting done error cancelled
    phase: Mapped[str | None] = mapped_column(String(20))
    complexity: Mapped[dict] = mapped_column(JSON, default=dict)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[dict] = mapped_column(JSON, default=dict)  # resultados por fase (checkpoint para reanudar)
    trace: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    critique: Mapped[dict] = mapped_column(JSON, default=dict)
    verification: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    answer: Mapped[str | None] = mapped_column(Text)
    models: Mapped[list] = mapped_column(JSON, default=list)
    local_only: Mapped[bool] = mapped_column(Boolean, default=False)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    research_id: Mapped[int | None] = mapped_column(ForeignKey("research.id", ondelete="SET NULL"))
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"))
    error: Mapped[str | None] = mapped_column(Text)
    feedback: Mapped[int | None] = mapped_column(Integer)  # 1 útil | -1 no útil
    feedback_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class MemoryRevision(Base):
    """Historial temporal de un recuerdo: qué cambió, cuándo y por qué."""

    __tablename__ = "memory_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    memory_id: Mapped[int] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(20))
    before: Mapped[str | None] = mapped_column(Text)
    after: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
