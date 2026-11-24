"""ATLAS 4.0: base de conocimiento (RAG), grafo, investigación, agentes, workflows, aprobaciones,
notificaciones y uso de modelos. Todo persistente en la base de datos local."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class Document(Base):
    """Documento importado a la base de conocimiento (archivo, enlace o nota)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str | None] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(16))  # pdf, docx, txt, md, csv, xlsx, image, url, note
    source_url: Mapped[str | None] = mapped_column(String(1000))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    chars: Mapped[int] = mapped_column(Integer, default=0)
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    embedded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    status: Mapped[str] = mapped_column(String(16), default="ready")  # ready | error
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class DocChunk(Base):
    __tablename__ = "doc_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSON)


class Entity(Base):
    """Nodo propio del grafo: persona, organización, lugar, concepto o idea."""

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="concept")  # person, org, place, concept, idea
    notes: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Relation(Base):
    """Arista explícita del grafo entre dos elementos (tipo + id)."""

    __tablename__ = "relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    src_type: Mapped[str] = mapped_column(String(16), index=True)
    src_id: Mapped[int] = mapped_column(Integer, index=True)
    dst_type: Mapped[str] = mapped_column(String(16), index=True)
    dst_id: Mapped[int] = mapped_column(Integer, index=True)
    label: Mapped[str] = mapped_column(String(64), default="relacionado")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Research(Base):
    """Investigación (reanudable). `state` guarda el avance para poder continuar."""

    __tablename__ = "research"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)  # queued running done error interrupted
    step: Mapped[str | None] = mapped_column(String(32))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    report: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[str | None] = mapped_column(String(8))
    model: Mapped[str | None] = mapped_column(String(120))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AgentRun(Base):
    """Ejecución de ATLAS CORE: agentes elegidos, herramientas usadas (con nivel) y resultado."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request: Mapped[str] = mapped_column(Text)
    agents: Mapped[list] = mapped_column(JSON, default=list)
    intent: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(120))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(16), default="chat")  # chat | workflow | manual
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Approval(Base):
    """Acción sensible en espera de tu autorización."""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(8))
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    workflow_run_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)  # pending approved rejected done
    result: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str | None] = mapped_column(String(40), unique=True)  # predefinidos
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    schedule: Mapped[str | None] = mapped_column(String(40))  # "daily 08:00" | "weekly 6 20:00" | None
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=false())
    builtin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)  # running done error awaiting_approval
    trigger: Mapped[str] = mapped_column(String(12), default="manual")  # manual | schedule
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    next_step: Mapped[int] = mapped_column(Integer, default=0)
    log: Mapped[list] = mapped_column(JSON, default=list)
    output: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(8), default="info")
    link: Mapped[str | None] = mapped_column(String(200))
    read: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ModelCall(Base):
    """Registro de cada llamada a un modelo: proveedor, tiempo, errores y coste si se puede calcular."""

    __tablename__ = "model_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(16), index=True)
    model: Mapped[str] = mapped_column(String(120))
    task: Mapped[str] = mapped_column(String(16))
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
