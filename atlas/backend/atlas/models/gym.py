"""Gimnasio: ejercicios, rutinas, series registradas y medidas corporales."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, String, Text, false, true
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow

MUSCLES = ("pecho", "espalda", "hombros", "deltoide_posterior", "biceps", "triceps", "antebrazo", "trapecio",
           "cuadriceps", "isquios", "gluteos", "gemelos", "abdomen")


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)  # nombres alternativos para el registro por texto/voz
    muscle: Mapped[str] = mapped_column(String(32), index=True)  # músculo principal
    secondary: Mapped[list] = mapped_column(JSON, default=list)  # cuentan como media serie
    equipment: Mapped[str | None] = mapped_column(String(32))
    per_side: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())  # peso por lado/mano
    custom: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Routine(Base):
    __tablename__ = "routines"
    __table_args__ = (CheckConstraint("weekday IS NULL OR (weekday >= 0 AND weekday <= 6)", name="weekday"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    weekday: Mapped[int | None] = mapped_column(Integer, index=True)  # 0=lunes … 6=domingo
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RoutineExercise(Base):
    __tablename__ = "routine_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    warmup_sets: Mapped[int] = mapped_column(Integer, default=0)
    sets: Mapped[int] = mapped_column(Integer, default=3)
    reps_min: Mapped[int] = mapped_column(Integer, default=8)
    reps_max: Mapped[int | None] = mapped_column(Integer)
    weight: Mapped[float | None] = mapped_column(Float)  # kg (por lado si per_side)
    notes: Mapped[str | None] = mapped_column(String(200))


class WorkoutSet(Base):
    __tablename__ = "workout_sets"
    __table_args__ = (
        CheckConstraint("reps >= 0", name="reps"),
        CheckConstraint("rir IS NULL OR (rir >= 0 AND rir <= 10)", name="rir"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), index=True)
    set_number: Mapped[int] = mapped_column(Integer, default=1)
    reps: Mapped[int] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Float, default=0)  # kg (por lado si el ejercicio es por lado)
    rir: Mapped[int | None] = mapped_column(Integer)
    warmup: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BodyMetric(Base):
    __tablename__ = "body_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    measured_on: Mapped[date] = mapped_column(Date, index=True)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    body_fat_pct: Mapped[float | None] = mapped_column(Float)
    waist_cm: Mapped[float | None] = mapped_column(Float)
    chest_cm: Mapped[float | None] = mapped_column(Float)
    arm_cm: Mapped[float | None] = mapped_column(Float)
    thigh_cm: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
