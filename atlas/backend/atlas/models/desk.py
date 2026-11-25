"""VISTAN Trading Desk: PAPER TRADING (dinero VIRTUAL). Ninguna tabla guarda credenciales de brókers ni
órdenes reales: todo lo que hay aquí es simulación y se marca como tal (`simulated`)."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, utcnow


class TdAccount(Base):
    __tablename__ = "td_accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # safe | experimental
    name: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    initial_capital: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)  # saldo virtual disponible
    slippage_bps: Mapped[float] = mapped_column(Float, default=2.0)
    commission_fixed: Mapped[float] = mapped_column(Float, default=1.0)
    commission_pct: Mapped[float] = mapped_column(Float, default=0.05)  # % del nominal por lado
    max_risk_pct: Mapped[float | None] = mapped_column(Float)  # riesgo máximo por operación (% equity)
    max_daily_loss_pct: Mapped[float | None] = mapped_column(Float)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float)
    max_exposure_pct: Mapped[float | None] = mapped_column(Float)
    require_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    enforce_limits: Mapped[bool] = mapped_column(Boolean, default=False)  # True: bloquea; False: solo avisa
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TdOrder(Base):
    __tablename__ = "td_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("td_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(4))  # buy | sell
    type: Mapped[str] = mapped_column(String(8))  # market | limit | stop
    qty: Mapped[float] = mapped_column(Float)
    limit_price: Mapped[float | None] = mapped_column(Float)
    stop_price: Mapped[float | None] = mapped_column(Float)
    sl: Mapped[float | None] = mapped_column(Float)
    tp: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), index=True)  # pending | filled | cancelled | rejected
    reason: Mapped[str | None] = mapped_column(Text)
    fill_price: Mapped[float | None] = mapped_column(Float)
    fees: Mapped[float | None] = mapped_column(Float)
    fx: Mapped[float | None] = mapped_column(Float)
    ref_price: Mapped[float | None] = mapped_column(Float)  # último precio al enviar la orden
    risk_money: Mapped[float | None] = mapped_column(Float)
    risk_pct: Mapped[float | None] = mapped_column(Float)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    data_kind: Mapped[str | None] = mapped_column(String(16))  # realtime | delayed | historical
    data_source: Mapped[str | None] = mapped_column(String(24))
    strategy: Mapped[str | None] = mapped_column(String(64), index=True)
    timeframe: Mapped[str | None] = mapped_column(String(8))
    note: Mapped[str | None] = mapped_column(Text)
    position_id: Mapped[int | None] = mapped_column(Integer, index=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime)


class TdPosition(Base):
    __tablename__ = "td_positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("td_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(5))  # long | short
    qty: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    entry_fx: Mapped[float] = mapped_column(Float, default=1.0)  # divisa del activo → divisa de la cuenta
    reserved: Mapped[float] = mapped_column(Float)  # capital virtual comprometido (divisa de la cuenta)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    sl: Mapped[float | None] = mapped_column(Float)
    tp: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(8), index=True)  # open | closed
    exit_price: Mapped[float | None] = mapped_column(Float)
    exit_fx: Mapped[float | None] = mapped_column(Float)
    realized_pnl: Mapped[float | None] = mapped_column(Float)  # neto de costes, divisa de la cuenta
    exit_reason: Mapped[str | None] = mapped_column(String(16))  # manual | stop_loss | take_profit | agent
    risk_money: Mapped[float | None] = mapped_column(Float)
    strategy: Mapped[str | None] = mapped_column(String(64), index=True)
    timeframe: Mapped[str | None] = mapped_column(String(8), index=True)
    data_kind: Mapped[str | None] = mapped_column(String(16))
    parent_id: Mapped[int | None] = mapped_column(Integer)  # cierre parcial
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)


class TdJournal(Base):
    __tablename__ = "td_journal"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("td_positions.id"), unique=True)
    entry_reason: Mapped[str | None] = mapped_column(Text)
    strategy: Mapped[str | None] = mapped_column(String(64))
    analysis: Mapped[str | None] = mapped_column(Text)
    emotion: Mapped[str | None] = mapped_column(String(40))
    exit_reason: Mapped[str | None] = mapped_column(Text)
    mistakes: Mapped[list] = mapped_column(JSON, default=list)
    lessons: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    image: Mapped[str | None] = mapped_column(String(80))  # captura del gráfico (archivo privado)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class TdEquity(Base):
    __tablename__ = "td_equity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("td_accounts.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    equity: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    used: Mapped[float] = mapped_column(Float)
    event: Mapped[str | None] = mapped_column(String(24))


class TdWatch(Base):
    __tablename__ = "td_watchlist"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class TdInstrument(Base):
    """Activos añadidos por ti (además del catálogo)."""
    __tablename__ = "td_instruments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    cls: Mapped[str] = mapped_column(String(12))
    ccy: Mapped[str] = mapped_column(String(3), default="USD")


class TdBacktest(Base):
    __tablename__ = "td_backtests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    params: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
