"""VISTAN: fotografías privadas (físico y comidas) y análisis generados por IA."""

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class BodyPhoto(Base):
    """Foto de progreso físico. El archivo vive en data/private/photos/physique (fuera de la web pública)."""

    __tablename__ = "body_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    taken_on: Mapped[date] = mapped_column(Date, index=True)
    pose: Mapped[str] = mapped_column(String(12), default="front")  # front | back | side | other
    note: Mapped[str | None] = mapped_column(Text)
    file: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MealPhoto(Base):
    """Foto de una comida con su análisis. Los registros de macros (MealEntry) se crean al confirmarlo."""

    __tablename__ = "meal_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eaten_at: Mapped[datetime] = mapped_column(DateTime, index=True)  # hora local
    meal: Mapped[str] = mapped_column(String(16))
    description: Mapped[str | None] = mapped_column(Text)
    file: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending | analyzed | logged | error
    analysis: Mapped[dict | None] = mapped_column(JSON)
    model: Mapped[str | None] = mapped_column(String(120))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Analysis(Base):
    """Resultado de un análisis de IA (físico, comparación, progreso, consejo nutricional) con su modelo."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)  # physique | compare | progress | nutrition
    refs: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    model: Mapped[str | None] = mapped_column(String(120))
    provider: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
