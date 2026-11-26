"""VISTAN LEGAL: expedientes, documentos jurídicos (sobre el gestor documental de VISTAN), análisis de contratos,
investigaciones jurídicas, borradores, alertas, plazos y cumplimiento normativo."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow

CASE_STATES = ("nuevo", "investigacion", "pendiente_doc", "revision", "pendiente_respuesta", "resuelto", "archivado")
RISK_LEVELS = ("critico", "alto", "medio", "bajo")


class LgCase(Base):
    __tablename__ = "lg_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(24), unique=True)  # número interno EXP-2026-0001
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(32))  # rama del derecho
    description: Mapped[str | None] = mapped_column(Text)
    jurisdiction: Mapped[str] = mapped_column(String(16), default="es")  # es | es-ct | eu | otra
    parties: Mapped[list] = mapped_column(JSON, default=list)  # [{name, role, notes}]
    status: Mapped[str] = mapped_column(String(20), default="nuevo", index=True)
    priority: Mapped[str] = mapped_column(String(10), default="media")
    opened_on: Mapped[date] = mapped_column(Date)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("lf_opportunities.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, index=True)


class LgEvent(Base):
    """Cronología y registro de actividad de cada expediente."""
    __tablename__ = "lg_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("lg_cases.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class LgDocument(Base):
    """Documento jurídico. El texto y la búsqueda semántica viven en el gestor documental de VISTAN (documents/doc_chunks,
    marcado como bóveda «legal»); el archivo original se guarda cifrado. origin: original | ia | nota."""
    __tablename__ = "lg_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("lg_cases.id", ondelete="SET NULL"), index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20), default="other")  # contract policy tos report draft note other
    origin: Mapped[str] = mapped_column(String(10), default="original")
    filename: Mapped[str | None] = mapped_column(String(300))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    text_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    stored_path: Mapped[str | None] = mapped_column(String(300))  # archivo cifrado (Fernet)
    extraction: Mapped[str | None] = mapped_column(String(40))  # método: pypdf, docx, ocr-visión-local…
    chars: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("lg_documents.id", ondelete="SET NULL"))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="ready")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, index=True)


class LgAnalysis(Base):
    __tablename__ = "lg_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legal_doc_id: Mapped[int] = mapped_column(ForeignKey("lg_documents.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="queued")
    contract_type: Mapped[str | None] = mapped_column(String(40))
    result: Mapped[dict] = mapped_column(JSON, default=dict)  # partes, fechas, importes, cláusulas, obligaciones, riesgos…
    model: Mapped[str | None] = mapped_column(String(120))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class LgComparison(Base):
    __tablename__ = "lg_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    a_id: Mapped[int] = mapped_column(ForeignKey("lg_documents.id", ondelete="CASCADE"))
    b_id: Mapped[int] = mapped_column(ForeignKey("lg_documents.id", ondelete="CASCADE"))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LgResearch(Base):
    __tablename__ = "lg_research"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("lg_cases.id", ondelete="SET NULL"), index=True)
    question: Mapped[str] = mapped_column(Text)
    jurisdiction: Mapped[str] = mapped_column(String(16), default="es")
    branch: Mapped[str | None] = mapped_column(String(32))
    facts: Mapped[str | None] = mapped_column(Text)  # datos que aportas (lugar, fechas, tipo de relación…)
    status: Mapped[str] = mapped_column(String(10), default="queued", index=True)
    step: Mapped[str | None] = mapped_column(String(20))
    state: Mapped[dict] = mapped_column(JSON, default=dict)  # fuentes, vigencia, análisis por fuente (reanudable)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    verification: Mapped[dict] = mapped_column(JSON, default=dict)
    model: Mapped[str | None] = mapped_column(String(120))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LgDraft(Base):
    __tablename__ = "lg_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("lg_cases.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    doc_type: Mapped[str] = mapped_column(String(32))
    jurisdiction: Mapped[str] = mapped_column(String(16), default="es")
    content: Mapped[str] = mapped_column(Text, default="")
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)  # datos que TÚ diste (lo único que puede aparecer como dato real)
    pending: Mapped[list] = mapped_column(JSON, default=list)  # campos [[PENDIENTE: …]]
    review: Mapped[list] = mapped_column(JSON, default=list)  # cláusulas que requieren revisión
    tags: Mapped[list] = mapped_column(JSON, default=list)
    model: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, index=True)


class LgDraftVersion(Base):
    __tablename__ = "lg_draft_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("lg_drafts.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LgComment(Base):
    __tablename__ = "lg_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target: Mapped[str] = mapped_column(String(10))  # draft | doc | case
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LgDeadline(Base):
    """Plazo o vencimiento. VISTAN nunca lo calcula: lo registras tú con su regla/fuente y lo marcas como verificado."""
    __tablename__ = "lg_deadlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("lg_cases.id", ondelete="CASCADE"), index=True)
    legal_doc_id: Mapped[int | None] = mapped_column(ForeignKey("lg_documents.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    due_on: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="otro")  # procesal administrativo contractual fiscal otro
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    basis: Mapped[str | None] = mapped_column(Text)  # regla aplicada, fuente, interrupciones/suspensiones consideradas
    status: Mapped[str] = mapped_column(String(10), default="pendiente")
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LgAlert(Base):
    __tablename__ = "lg_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)  # evita duplicados al reescanear
    case_id: Mapped[int | None] = mapped_column(ForeignKey("lg_cases.id", ondelete="CASCADE"), index=True)
    legal_doc_id: Mapped[int | None] = mapped_column(ForeignKey("lg_documents.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String(8), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(300))
    consequence: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="abierta", index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class LgCompliance(Base):
    __tablename__ = "lg_compliance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile: Mapped[str] = mapped_column(String(24))
    case_id: Mapped[int | None] = mapped_column(ForeignKey("lg_cases.id", ondelete="SET NULL"), index=True)
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("lf_opportunities.id", ondelete="SET NULL"))
    area: Mapped[str] = mapped_column(String(24))
    obligation: Mapped[str] = mapped_column(Text)
    norm: Mapped[str | None] = mapped_column(String(200))
    article: Mapped[str | None] = mapped_column(String(80))
    source_url: Mapped[str | None] = mapped_column(String(400))
    applicability: Mapped[str] = mapped_column(String(14), default="potencial")  # confirmada potencial asesoramiento
    status: Mapped[str] = mapped_column(String(12), default="pendiente")  # pendiente en_curso cumplida no_aplica
    owner: Mapped[str | None] = mapped_column(String(120))
    due_on: Mapped[date | None] = mapped_column(Date)
    evidence: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LgQuery(Base):
    """Historial de consultas jurídicas (buscador central y Legal Agent)."""
    __tablename__ = "lg_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(12))  # agent | search | research
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(120))
    case_id: Mapped[int | None] = mapped_column(ForeignKey("lg_cases.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
