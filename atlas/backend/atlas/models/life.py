"""VISTAN LIFE OS: desarrollo personal y empresarial. Reutiliza Goals, Tasks, Projects, Transactions, Memory y Research;
estas tablas (lf_*) cubren solo lo que no existía. Los datos empresariales (oportunidades, capital de negocio) están
separados de los personales (hábitos, contactos personales, decisiones, errores)."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class LfOpportunity(Base):
    __tablename__ = "lf_opportunities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    market: Mapped[str | None] = mapped_column(Text)
    customer: Mapped[str | None] = mapped_column(Text)
    problem: Mapped[str | None] = mapped_column(Text)
    solution: Mapped[str | None] = mapped_column(Text)
    competition: Mapped[str | None] = mapped_column(Text)
    suppliers: Mapped[str | None] = mapped_column(Text)
    business_model: Mapped[str | None] = mapped_column(Text)
    marketing: Mapped[str | None] = mapped_column(Text)
    launch_plan: Mapped[str | None] = mapped_column(Text)
    risks: Mapped[str | None] = mapped_column(Text)
    resources: Mapped[str | None] = mapped_column(Text)
    next_actions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="idea", index=True)  # idea | research | validating | building | launched | paused | discarded
    economics: Mapped[dict] = mapped_column(JSON, default=dict)  # supuestos ESTIMADOS del usuario (precio, costes, unidades…)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)  # criterios 1-5 que puntúas tú
    swot: Mapped[dict] = mapped_column(JSON, default=dict)
    report: Mapped[dict | None] = mapped_column(JSON)  # último informe del Business Agent (marcado como estimación)
    research_id: Mapped[int | None] = mapped_column(Integer)
    project_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LfAsset(Base):
    """Activos y pasivos. `basis`: real (comprobado) | estimated (valor estimado). Separado por ámbito."""
    __tablename__ = "lf_assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    side: Mapped[str] = mapped_column(String(10))  # asset | liability
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))  # efectivo, cuenta, inversión, inmueble, vehículo, negocio, préstamo…
    scope: Mapped[str] = mapped_column(String(10), default="personal")  # personal | business
    basis: Mapped[str] = mapped_column(String(10), default="real")  # real | estimated
    value: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LfNetWorth(Base):
    __tablename__ = "lf_networth"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True)
    assets: Mapped[float] = mapped_column(Float)
    liabilities: Mapped[float] = mapped_column(Float)
    net: Mapped[float] = mapped_column(Float)
    estimated_share: Mapped[float] = mapped_column(Float, default=0)  # parte del patrimonio basada en estimaciones


class LfSubject(Base):
    __tablename__ = "lf_subjects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    syllabus: Mapped[list] = mapped_column(JSON, default=list)  # [{"topic": str, "level": 1-5}]
    syllabus_source: Mapped[str | None] = mapped_column(String(80))
    category: Mapped[str | None] = mapped_column(String(16), index=True)  # biblioteca de VISTAN ACADEMY
    description: Mapped[str | None] = mapped_column(Text)
    custom: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class LfLesson(Base):
    __tablename__ = "lf_lessons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("lf_subjects.id"), index=True)
    topic: Mapped[str] = mapped_column(String(200))
    level: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[dict] = mapped_column(JSON)  # explicación, ejemplos, caso práctico, ejercicios
    model: Mapped[str | None] = mapped_column(String(80))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("ac_courses.id", ondelete="SET NULL"), index=True)
    module_idx: Mapped[int | None] = mapped_column(Integer)
    lesson_idx: Mapped[int | None] = mapped_column(Integer)
    progress: Mapped[dict | None] = mapped_column(JSON)  # dónde te quedaste, secciones vistas, respuestas de comprensión
    minutes: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class LfAssessment(Base):
    __tablename__ = "lf_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("lf_subjects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # quiz | exam | exercise
    topic: Mapped[str | None] = mapped_column(String(200))
    difficulty: Mapped[int] = mapped_column(Integer, default=2)  # 1-5
    questions: Mapped[list] = mapped_column(JSON)
    answers: Mapped[list | None] = mapped_column(JSON)
    score: Mapped[float | None] = mapped_column(Float)  # 0-100, solo tras corregir
    feedback: Mapped[dict | None] = mapped_column(JSON)
    model: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("ac_courses.id", ondelete="SET NULL"), index=True)
    module_idx: Mapped[int | None] = mapped_column(Integer)
    criteria: Mapped[dict | None] = mapped_column(JSON)  # criterios de evaluación explícitos (puntos por pregunta y rúbricas)


class LfSimulation(Base):
    __tablename__ = "lf_simulations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    area: Mapped[str] = mapped_column(String(16), index=True)  # leadership | communication
    scenario: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(160))
    transcript: Mapped[list] = mapped_column(JSON, default=list)
    debrief: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10), default="active")  # active | finished
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class LfHabit(Base):
    __tablename__ = "lf_habits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(16), default="custom")  # reading | training | sleep | work | study | distraction | custom
    kind: Mapped[str] = mapped_column(String(8), default="check")  # check | amount
    target: Mapped[float | None] = mapped_column(Float)  # objetivo diario (amount)
    unit: Mapped[str | None] = mapped_column(String(16))
    limit: Mapped[bool] = mapped_column(Boolean, default=False)  # True: el objetivo es NO superar (p. ej. distracciones)
    days: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4, 5, 6])  # 0=lunes
    remind_at: Mapped[str | None] = mapped_column(String(5))  # HH:MM
    reminded_on: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LfHabitLog(Base):
    __tablename__ = "lf_habit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("lf_habits.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[float] = mapped_column(Float, default=1)
    note: Mapped[str | None] = mapped_column(String(300))


class LfCommitment(Base):
    """Objetivos semanales / mensuales concretos (compromisos verificables)."""
    __tablename__ = "lf_commitments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period: Mapped[str] = mapped_column(String(8))  # week | month
    title: Mapped[str] = mapped_column(String(200))
    due: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(8), default="open", index=True)  # open | done | missed | dropped
    goal_id: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)


class LfContact(Base):
    __tablename__ = "lf_contacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(40))
    company: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str | None] = mapped_column(String(120))
    relation: Mapped[str | None] = mapped_column(String(60))
    scope: Mapped[str] = mapped_column(String(12), default="professional")  # professional | personal
    interests: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    opportunities: Mapped[str | None] = mapped_column(Text)
    last_interaction: Mapped[date | None] = mapped_column(Date)
    next_followup: Mapped[date | None] = mapped_column(Date, index=True)
    followup_notified: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LfInteraction(Base):
    __tablename__ = "lf_interactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("lf_contacts.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    channel: Mapped[str | None] = mapped_column(String(30))
    summary: Mapped[str] = mapped_column(Text)


class LfDecision(Base):
    __tablename__ = "lf_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    day: Mapped[date] = mapped_column(Date, index=True)
    area: Mapped[str | None] = mapped_column(String(32))
    context: Mapped[str | None] = mapped_column(Text)
    problem: Mapped[str | None] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON, default=list)
    decision: Mapped[str] = mapped_column(Text)
    reasons: Mapped[str | None] = mapped_column(Text)
    expectations: Mapped[str | None] = mapped_column(Text)
    risks: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer, default=60)  # 0-100
    expected_result: Mapped[str | None] = mapped_column(Text)
    review_on: Mapped[date | None] = mapped_column(Date, index=True)
    actual_result: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(String(10))  # better | as_expected | worse
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    analysis: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LfFailure(Base):
    __tablename__ = "lf_failures"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16))  # project | decision | business | goal | personal
    day: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    causes: Mapped[str | None] = mapped_column(Text)
    consequences: Mapped[str | None] = mapped_column(Text)
    lessons: Mapped[str | None] = mapped_column(Text)
    actions: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    decision_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LfVision(Base):
    __tablename__ = "lf_vision"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section: Mapped[str] = mapped_column(String(32), unique=True)
    content: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LfMilestone(Base):
    """Línea temporal de la visión (hitos personales, años)."""
    __tablename__ = "lf_timeline"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(200))
    area: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(10), default="planned")  # planned | achieved | dropped
    goal_id: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)


class LfRadar(Base):
    __tablename__ = "lf_radar"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(String(300))
    lens: Mapped[str] = mapped_column(String(24))  # trends | problems | digital | models | markets | advantages
    research_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
