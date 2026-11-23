"""Entidades base de cada módulo.

Se definen en la Fase 1 para que el dashboard lea datos reales desde el
principio. Cada fase posterior las amplía mediante migraciones de Alembic
(nunca recreando la base de datos).

Todas las fechas/horas se guardan en UTC naive. El dinero en céntimos (int)
para evitar errores de coma flotante.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import false
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow

TASK_PRIORITIES = ("low", "medium", "high", "critical")
TASK_STATUSES = ("pending", "in_progress", "done", "cancelled")
PROJECT_STATUSES = ("active", "paused", "done", "archived")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(f"status IN {PROJECT_STATUSES}", name="status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(f"priority IN {TASK_PRIORITIES}", name="priority"),
        CheckConstraint(f"status IN {TASK_STATUSES}", name="status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    category: Mapped[str | None] = mapped_column(String(64))
    due_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("goals.id", ondelete="SET NULL"), index=True)
    # Fecha sin hora: due_at = final del día local (no cuenta como atrasada hasta que acaba el día)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Recordatorio: momento en que avisar; reminded_at marca que ya se avisó
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(300))
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(32), default="local")  # local | google
    external_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Transaction(Base):
    """Movimiento de DINERO REAL. El capital virtual de trading va en otra tabla (Fase 6)."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("kind IN ('income', 'expense')", name="kind"),
        CheckConstraint("amount_cents >= 0", name="amount_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(8))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WorkoutSession(Base):
    """Sesión de entrenamiento. Ejercicios/series/RIR se añaden en la Fase 5."""

    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    performed_on: Mapped[date] = mapped_column(Date, index=True)
    routine_name: Mapped[str | None] = mapped_column(String(120))
    duration_min: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


GOAL_STATUSES = ("active", "achieved", "paused", "abandoned")


class Goal(Base):
    """Objetivo medible. Numérico (de start_value a target_value, p. ej. ahorrar o bajar de peso)
    o por hitos (progreso = tareas vinculadas completadas)."""

    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint(f"status IN {GOAL_STATUSES}", name="status"),
        CheckConstraint("kind IN ('numeric', 'milestones')", name="kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    area: Mapped[str | None] = mapped_column(String(32))  # finanzas, salud, negocio, aprendizaje…
    kind: Mapped[str] = mapped_column(String(12), default="numeric")
    unit: Mapped[str | None] = mapped_column(String(16))
    start_value: Mapped[float] = mapped_column(Float, default=0)
    target_value: Mapped[float | None] = mapped_column(Float)
    current_value: Mapped[float] = mapped_column(Float, default=0)
    start_date: Mapped[date] = mapped_column(Date)
    deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime)


class GoalProgress(Base):
    """Historial de valores de un objetivo (permite calcular el ritmo real)."""

    __tablename__ = "goal_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    value: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(String(300))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
