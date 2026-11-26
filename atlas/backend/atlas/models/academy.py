"""VISTAN ACADEMY: amplía la academia de LIFE OS (lf_subjects, lf_lessons, lf_assessments) con cursos, conceptos con
repetición espaciada, tiempo de estudio real, itinerarios, laboratorios e historial del profesor."""

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class AcCourse(Base):
    __tablename__ = "ac_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("lf_subjects.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    request: Mapped[str | None] = mapped_column(Text)
    level_start: Mapped[int] = mapped_column(Integer, default=1)
    goals: Mapped[list] = mapped_column(JSON, default=list)
    modules: Mapped[list] = mapped_column(JSON, default=list)  # [{title, objective, lessons: [{title, objective, minutes}], exam: bool}]
    est_hours: Mapped[float | None] = mapped_column(Float)
    final_project: Mapped[str | None] = mapped_column(Text)
    criteria: Mapped[list] = mapped_column(JSON, default=list)  # criterios de evaluación y aprobado
    status: Mapped[str] = mapped_column(String(10), default="active", index=True)  # active paused completed archived
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    path_id: Mapped[int | None] = mapped_column(ForeignKey("ac_paths.id", ondelete="SET NULL"))
    research_ids: Mapped[list] = mapped_column(JSON, default=list)
    final_submission: Mapped[dict | None] = mapped_column(JSON)
    model: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class AcPath(Base):
    __tablename__ = "ac_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(Text)
    start_level: Mapped[int] = mapped_column(Integer, default=1)
    competencies: Mapped[list] = mapped_column(JSON, default=list)
    steps: Mapped[list] = mapped_column(JSON, default=list)  # [{title, subject, why, course_id, advance: {min_score, needs_project}, project}]
    status: Mapped[str] = mapped_column(String(10), default="active")
    model: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AcConcept(Base):
    """Concepto evaluado. Dominio y repetición espaciada calculados SOLO con respuestas corregidas."""
    __tablename__ = "ac_concepts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("lf_subjects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(200), index=True)
    mastery: Mapped[float] = mapped_column(Float, default=0)  # 0-100
    state: Mapped[str] = mapped_column(String(12), default="nuevo")  # nuevo aprendiendo reciente consolidado
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    due_on: Mapped[date | None] = mapped_column(Date, index=True)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    wrong: Mapped[int] = mapped_column(Integer, default=0)
    first_ok_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    history: Mapped[list] = mapped_column(JSON, default=list)  # [{at, score, kind}]
    errors: Mapped[list] = mapped_column(JSON, default=list)  # últimas preguntas falladas (para detectar patrones)


class AcSession(Base):
    """Tiempo de estudio REAL (medido en la interfaz mientras estudias)."""
    __tablename__ = "ac_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))  # lesson exam review tutor lab research
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("lf_subjects.id", ondelete="SET NULL"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("ac_courses.id", ondelete="SET NULL"))
    ref_id: Mapped[int | None] = mapped_column(Integer)
    minutes: Mapped[float] = mapped_column(Float)
    day: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AcTutorMsg(Base):
    __tablename__ = "ac_tutor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("lf_subjects.id", ondelete="SET NULL"), index=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lf_lessons.id", ondelete="SET NULL"), index=True)
    teacher: Mapped[str | None] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AcLab(Base):
    __tablename__ = "ac_labs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(14), index=True)  # business finance trading programming
    title: Mapped[str] = mapped_column(String(200))
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON)
    score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="open")
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("lf_subjects.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
