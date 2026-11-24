"""Nutrición: alimentos (base local) y comidas registradas."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class Food(Base):
    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    kcal: Mapped[float] = mapped_column(Float)  # por 100 g
    protein: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    unit_name: Mapped[str] = mapped_column(String(32), default="ración")
    unit_grams: Mapped[float] = mapped_column(Float, default=100)
    custom: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class MealEntry(Base):
    __tablename__ = "meal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eaten_on: Mapped[date] = mapped_column(Date, index=True)  # día local
    meal: Mapped[str] = mapped_column(String(16))  # desayuno | comida | merienda | cena | snack
    food_id: Mapped[int | None] = mapped_column(ForeignKey("foods.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120))
    grams: Mapped[float] = mapped_column(Float)
    kcal: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(8), default="manual")  # manual | text | photo
    photo_id: Mapped[int | None] = mapped_column(ForeignKey("meal_photos.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
