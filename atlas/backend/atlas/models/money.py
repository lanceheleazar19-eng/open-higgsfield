"""Finanzas (dinero REAL: presupuestos) y trading (SIMULADO: capital virtual). Tablas separadas."""

from datetime import date, datetime

from sqlalchemy import JSON, CheckConstraint, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class Budget(Base):
    """Presupuesto mensual por categoría de gasto (dinero real)."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(64), unique=True)
    monthly_cents: Mapped[int] = mapped_column(Integer)


class PaperTrade(Base):
    """Operación de PAPER TRADING (simulada). Nunca se envía a ningún bróker."""

    __tablename__ = "paper_trades"
    __table_args__ = (
        CheckConstraint("side IN ('long', 'short')", name="side"),
        CheckConstraint("quantity > 0", name="qty"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(5))
    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    take_profit: Mapped[float | None] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    strategy: Mapped[str | None] = mapped_column(String(64), index=True)
    mistakes: Mapped[list] = mapped_column(JSON, default=list)  # etiquetas: «sin stop», «FOMO», …
    notes: Mapped[str | None] = mapped_column(Text)


class HealthDay(Base):
    """Datos diarios de Apple Salud enviados por el Atajo del iPhone."""

    __tablename__ = "health_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True)
    steps: Mapped[int | None] = mapped_column(Integer)
    sleep_hours: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    active_kcal: Mapped[float | None] = mapped_column(Float)
    distance_km: Mapped[float | None] = mapped_column(Float)
    resting_hr: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
