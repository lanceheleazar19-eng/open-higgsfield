"""VISTAN Paper Betting: simulación de apuestas deportivas con dinero FICTICIO. Tablas propias (bt_*),
totalmente separadas de la Trading Desk (td_*) y de las finanzas reales. No hay depósitos, retiradas,
credenciales de casas de apuestas ni ninguna forma de apostar dinero real."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class BtBankroll(Base):
    __tablename__ = "bt_bankrolls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    initial: Mapped[float] = mapped_column(Float)
    balance: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BtEvent(Base):
    __tablename__ = "bt_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport: Mapped[str] = mapped_column(String(16), index=True)  # football | basketball | tennis | f1 | other
    competition: Mapped[str | None] = mapped_column(String(120))
    home: Mapped[str | None] = mapped_column(String(120))  # local / jugador 1
    away: Mapped[str | None] = mapped_column(String(120))  # visitante / jugador 2
    name: Mapped[str] = mapped_column(String(200))
    participants: Mapped[list] = mapped_column(JSON, default=list)  # F1 u otros con varios participantes
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(12), default="scheduled", index=True)  # scheduled | live | finished | postponed | cancelled
    result: Mapped[dict | None] = mapped_column(JSON)
    result_source: Mapped[str | None] = mapped_column(String(40))  # proveedor o «manual»
    provider: Mapped[str | None] = mapped_column(String(24), index=True)  # football-data | theoddsapi | jolpica | thesportsdb | manual
    external_id: Mapped[str | None] = mapped_column(String(64), index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class BtBet(Base):
    """Pronóstico simulado (simple o combinada)."""
    __tablename__ = "bt_bets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bankroll_id: Mapped[int] = mapped_column(ForeignKey("bt_bankrolls.id"), index=True)
    kind: Mapped[str] = mapped_column(String(8))  # single | combo
    stake: Mapped[float] = mapped_column(Float)
    odds: Mapped[float] = mapped_column(Float)  # cuota decimal total en el momento del registro
    potential_return: Mapped[float] = mapped_column(Float)
    model_prob: Mapped[float | None] = mapped_column(Float)  # probabilidad del modelo (combinada: conjunta)
    user_prob: Mapped[float | None] = mapped_column(Float)  # tu propia estimación
    status: Mapped[str] = mapped_column(String(8), default="pending", index=True)  # pending | won | lost | void
    returned: Mapped[float | None] = mapped_column(Float)
    profit: Mapped[float | None] = mapped_column(Float)
    reasoning: Mapped[str | None] = mapped_column(Text)
    strategy: Mapped[str | None] = mapped_column(String(64), index=True)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)


class BtLeg(Base):
    __tablename__ = "bt_legs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bet_id: Mapped[int] = mapped_column(ForeignKey("bt_bets.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("bt_events.id"), index=True)
    market: Mapped[str] = mapped_column(String(20))
    pick: Mapped[str] = mapped_column(String(120))
    line: Mapped[float | None] = mapped_column(Float)
    opponent: Mapped[str | None] = mapped_column(String(120))  # duelo (F1 h2h)
    odds: Mapped[float] = mapped_column(Float)
    odds_source: Mapped[str] = mapped_column(String(80), default="manual")
    model_prob: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(8), default="pending")  # pending | won | lost | void


class BtPrediction(Base):
    """Análisis del Prediction Engine guardado (para revisar su precisión después)."""
    __tablename__ = "bt_predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("bt_events.id"), index=True)
    model: Mapped[str] = mapped_column(String(40))
    probs: Mapped[dict] = mapped_column(JSON)
    inputs: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class BtBacktest(Base):
    __tablename__ = "bt_backtests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    params: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
