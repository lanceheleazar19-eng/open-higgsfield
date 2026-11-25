"""VISTAN INNOVATION LAB. Reutiliza Research (investigación profunda), Document/DocChunk/Entity (RAG y grafo),
Memory, Project/Task, Workflow y ModelCall. Las tablas ix_* cubren solo lo que no existía."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class IxTechnology(Base):
    """Tecnología seguida en el radar."""
    __tablename__ = "ix_technologies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(24), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    maturity: Mapped[str] = mapped_column(String(16), default="academic")  # academic | prototype | commercial | speculative
    watch: Mapped[bool] = mapped_column(Boolean, default=True)
    entities: Mapped[list] = mapped_column(JSON, default=list)  # empresas y laboratorios que sigues
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IxDiscovery(Base):
    __tablename__ = "ix_discoveries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(400))
    category: Mapped[str] = mapped_column(String(24), index=True)
    technology_id: Mapped[int | None] = mapped_column(ForeignKey("ix_technologies.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(12), default="news")  # paper | patent | news | product | report | note
    maturity: Mapped[str] = mapped_column(String(16))  # academic | prototype | commercial | speculative
    description: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    published_on: Mapped[date | None] = mapped_column(Date, index=True)
    reliability: Mapped[str] = mapped_column(String(8), default="media")  # alta | media | baja
    origin: Mapped[str] = mapped_column(String(16), default="manual")  # manual | arxiv | openalex | research | epo
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    authors: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class IxResearch(Base):
    """Metadatos de laboratorio sobre una investigación del Research Engine (etiquetas, categoría, guardada)."""
    __tablename__ = "ix_research"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_id: Mapped[int] = mapped_column(Integer, unique=True)
    category: Mapped[str | None] = mapped_column(String(24))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    saved: Mapped[bool] = mapped_column(Boolean, default=False)
    papers: Mapped[list] = mapped_column(JSON, default=list)  # publicaciones científicas consultadas (arXiv/OpenAlex)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IxExperiment(Base):
    __tablename__ = "ix_experiments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str | None] = mapped_column(Text)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    technology: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(24), index=True)
    resources: Mapped[str | None] = mapped_column(Text)
    variables: Mapped[str | None] = mapped_column(Text)
    methodology: Mapped[str | None] = mapped_column(Text)
    expected: Mapped[str | None] = mapped_column(Text)
    observed: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="IDEA", index=True)  # IDEA PLANNED RUNNING PAUSED COMPLETED FAILED ARCHIVED
    verdict: Mapped[str | None] = mapped_column(String(12))  # supported | refuted | inconclusive (solo con resultados)
    started_on: Mapped[date | None] = mapped_column(Date)
    finished_on: Mapped[date | None] = mapped_column(Date)
    hours: Mapped[float] = mapped_column(Float, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0)
    idea_id: Mapped[int | None] = mapped_column(Integer)
    project_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class IxTrial(Base):
    """Registro de pruebas de un experimento (versiones repetibles y comparables)."""
    __tablename__ = "ix_trials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("ix_experiments.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(40))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    observed: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(12), default="inconclusive")  # pass | fail | inconclusive
    ran_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class IxArenaSuite(Base):
    __tablename__ = "ix_arena_suites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    tests: Mapped[list] = mapped_column(JSON)  # [{"prompt", "check": exact|contains|regex|judge|none, "expected", "system", "rag"}]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IxArenaRun(Base):
    __tablename__ = "ix_arena_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    suite_id: Mapped[int] = mapped_column(ForeignKey("ix_arena_suites.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(160))  # proveedor:modelo
    status: Mapped[str] = mapped_column(String(10), default="queued")  # queued | running | done | error
    results: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    judge: Mapped[str | None] = mapped_column(String(160))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class IxPrototype(Base):
    __tablename__ = "ix_prototypes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(16), default="app")  # app | tool | web | automation | agent | saas | ui | analytics | software
    description: Mapped[str | None] = mapped_column(Text)
    problem: Mapped[str | None] = mapped_column(Text)
    goal: Mapped[str | None] = mapped_column(Text)
    tech: Mapped[str | None] = mapped_column(Text)
    architecture: Mapped[str | None] = mapped_column(Text)
    tests: Mapped[str | None] = mapped_column(Text)
    results: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="concept", index=True)  # concept | building | testing | done | abandoned
    hours: Mapped[float] = mapped_column(Float, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0)
    idea_id: Mapped[int | None] = mapped_column(Integer)
    project_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class IxVersion(Base):
    __tablename__ = "ix_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prototype_id: Mapped[int] = mapped_column(ForeignKey("ix_prototypes.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IxFile(Base):
    """Archivo o captura de un prototipo (guardado en data/private/lab, nunca se ejecuta automáticamente)."""
    __tablename__ = "ix_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prototype_id: Mapped[int] = mapped_column(ForeignKey("ix_prototypes.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    stored: Mapped[str] = mapped_column(String(80))
    mime: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    is_image: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IxSandboxRun(Base):
    __tablename__ = "ix_sandbox_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prototype_id: Mapped[int | None] = mapped_column(Integer, index=True)
    language: Mapped[str] = mapped_column(String(10), default="python")
    code: Mapped[str] = mapped_column(Text)
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12))  # ok | error | timeout | blocked
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class IxLibraryItem(Base):
    __tablename__ = "ix_library"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(14), index=True)  # paper | article | patent | report | docs | book | publication | experiment | note | discovery | link
    title: Mapped[str] = mapped_column(String(400))
    authors: Mapped[list] = mapped_column(JSON, default=list)
    url: Mapped[str | None] = mapped_column(String(1000))
    published_on: Mapped[date | None] = mapped_column(Date)
    origin: Mapped[str] = mapped_column(String(10), default="external")  # own | external
    category: Mapped[str | None] = mapped_column(String(24), index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    concepts: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(Integer)  # Documento de Knowledge (RAG) si se ha importado
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class IxLink(Base):
    """Referencias cruzadas entre elementos del laboratorio (y con proyectos/oportunidades)."""
    __tablename__ = "ix_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    a_type: Mapped[str] = mapped_column(String(16))
    a_id: Mapped[int] = mapped_column(Integer)
    b_type: Mapped[str] = mapped_column(String(16))
    b_id: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IxIdea(Base):
    __tablename__ = "ix_ideas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    concept: Mapped[str | None] = mapped_column(Text)
    problem: Mapped[str | None] = mapped_column(Text)
    solution: Mapped[str | None] = mapped_column(Text)
    tech: Mapped[str | None] = mapped_column(Text)
    feasibility: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str | None] = mapped_column(String(10))  # baja | media | alta
    cost: Mapped[str | None] = mapped_column(String(120))
    applications: Mapped[str | None] = mapped_column(Text)
    risks: Mapped[str | None] = mapped_column(Text)
    customers: Mapped[str | None] = mapped_column(Text)
    next_experiment: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(24), index=True)
    origin: Mapped[str] = mapped_column(String(10), default="manual")  # manual | generated
    source_input: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="new", index=True)  # new | exploring | converted | discarded
    experiment_id: Mapped[int | None] = mapped_column(Integer)
    prototype_id: Mapped[int | None] = mapped_column(Integer)
    opportunity_id: Mapped[int | None] = mapped_column(Integer)
    project_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class IxScenario(Base):
    __tablename__ = "ix_scenarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    horizon: Mapped[str] = mapped_column(String(16), default="5 años")
    research_id: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[dict | None] = mapped_column(JSON)
    model: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class IxPatent(Base):
    __tablename__ = "ix_patents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), default="external")  # external | own
    title: Mapped[str] = mapped_column(String(400))
    number: Mapped[str | None] = mapped_column(String(60), index=True)
    office: Mapped[str | None] = mapped_column(String(20))
    applicants: Mapped[list] = mapped_column(JSON, default=list)
    abstract: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1000))
    published_on: Mapped[date | None] = mapped_column(Date)
    technology: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(16))  # propias: idea | drafting | consulted | filed
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual | epo
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class IxProjectMeta(Base):
    """Datos de innovación de un Project existente (presupuesto, recursos, agentes y origen)."""
    __tablename__ = "ix_project_meta"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, unique=True)
    budget: Mapped[float | None] = mapped_column(Float)
    spent: Mapped[float] = mapped_column(Float, default=0)
    owner: Mapped[str | None] = mapped_column(String(120))
    agents: Mapped[list] = mapped_column(JSON, default=list)
    resources: Mapped[str | None] = mapped_column(Text)
    results: Mapped[str | None] = mapped_column(Text)
    next_steps: Mapped[str | None] = mapped_column(Text)
    origin_type: Mapped[str | None] = mapped_column(String(16))
    origin_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
