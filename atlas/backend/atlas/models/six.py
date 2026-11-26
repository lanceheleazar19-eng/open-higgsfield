"""VISTAN SIX: seis agentes que operan de forma autónoma SOLO a través del motor de Paper Trading del Trading Desk.
Aquí solo se guarda su configuración, su registro de decisiones y las validaciones históricas; las órdenes y posiciones
son las del propio Trading Desk (td_orders/td_positions), identificadas por el id de estrategia «SIX:…»."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class SxAgent(Base):
    __tablename__ = "sx_agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(40))
    account_kind: Mapped[str] = mapped_column(String(16))  # safe | experimental
    family: Mapped[str] = mapped_column(String(24))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    symbols: Mapped[list] = mapped_column(JSON, default=list)
    variants: Mapped[list] = mapped_column(JSON, default=list)  # [{id, timeframe, params}]
    variant_idx: Mapped[int] = mapped_column(Integer, default=0)
    allocation_pct: Mapped[float] = mapped_column(Float)  # % del capital inicial de su cuenta (asignación virtual propia)
    risk_pct: Mapped[float] = mapped_column(Float)  # riesgo por operación sobre su asignación
    max_positions: Mapped[int] = mapped_column(Integer, default=2)
    max_dd_pct: Mapped[float] = mapped_column(Float)  # freno de emergencia (drawdown de su asignación)
    max_daily_loss_pct: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="idle")  # idle running paused halted
    halt_reason: Mapped[str | None] = mapped_column(Text)
    state: Mapped[dict] = mapped_column(JSON, default=dict)  # última vela evaluada por activo, rotaciones, análisis en curso
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SxDecision(Base):
    """Cada decisión: ejecutada, descartada (y por qué), rechazada por el motor o error. Nunca se borra."""
    __tablename__ = "sx_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent: Mapped[str] = mapped_column(String(16), index=True)
    strategy: Mapped[str | None] = mapped_column(String(64), index=True)
    symbol: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(16))  # analyze open_long open_short close modify cancel skip rotate halt
    status: Mapped[str] = mapped_column(String(10), index=True)  # executed skipped rejected error info
    reason: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON, default=dict)  # precio, fuente, tipo de dato, vela, indicadores, avisos
    order_id: Mapped[int | None] = mapped_column(Integer)
    position_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SxValidation(Base):
    """Backtest de la MISMA lógica sobre velas históricas reales, dividido en tramo de ajuste y tramo fuera de muestra."""
    __tablename__ = "sx_validations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent: Mapped[str] = mapped_column(String(16), index=True)
    strategy: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(8))
    source: Mapped[str | None] = mapped_column(String(24))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
