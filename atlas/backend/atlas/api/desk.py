"""VISTAN Trading Desk — API de PAPER TRADING (dinero virtual). No existe ninguna ruta para operar con dinero real
ni para guardar credenciales de brókers: solo claves de proveedores de DATOS de mercado (en el llavero)."""

import base64
import binascii
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.config import get_settings
from atlas.desk import analytics, backtest, engine, news
from atlas.desk import market as mk
from atlas.integrations.secrets import delete_secret, set_secret
from atlas.models import (Research, TdAccount, TdBacktest, TdInstrument, TdJournal, TdOrder, TdPosition, TdWatch)
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/desk", tags=["trading-desk"])
SIM = "SIMULACIÓN · dinero virtual"


def _day_start(db) -> datetime:  # noqa: ANN001
    tz = ZoneInfo(str(get_prefs(db)["timezone"]))
    local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def _acc(db, account_id: int | None) -> TdAccount:  # noqa: ANN001
    accs = engine.ensure_accounts(db)
    db.commit()
    if account_id is None:
        return next(a for a in accs if a.kind == "safe")
    a = db.get(TdAccount, account_id)
    if not a:
        raise HTTPException(404, "Cuenta virtual no encontrada")
    return a


def _inst(db, symbol: str) -> mk.Instrument:  # noqa: ANN001
    i = mk.instruments(db).get(symbol)
    if not i:
        raise HTTPException(404, f"Activo desconocido: {symbol}")
    return i


def acc_dict(a: TdAccount) -> dict:
    return {"id": a.id, "kind": a.kind, "name": a.name, "currency": a.currency, "initial_capital": a.initial_capital,
            "slippage_bps": a.slippage_bps, "commission_fixed": a.commission_fixed, "commission_pct": a.commission_pct,
            "max_risk_pct": a.max_risk_pct, "max_daily_loss_pct": a.max_daily_loss_pct, "max_drawdown_pct": a.max_drawdown_pct,
            "max_exposure_pct": a.max_exposure_pct, "require_stop": a.require_stop, "enforce_limits": a.enforce_limits,
            "active": a.active, "simulated": True, "created_at": a.created_at.isoformat()}


def order_dict(o: TdOrder) -> dict:
    return {"id": o.id, "account_id": o.account_id, "symbol": o.symbol, "side": o.side, "type": o.type, "qty": o.qty,
            "limit_price": o.limit_price, "stop_price": o.stop_price, "sl": o.sl, "tp": o.tp, "status": o.status, "reason": o.reason,
            "fill_price": o.fill_price, "fees": o.fees, "ref_price": o.ref_price, "risk_money": o.risk_money, "risk_pct": o.risk_pct,
            "warnings": o.warnings or [], "data_kind": o.data_kind, "data_source": o.data_source, "strategy": o.strategy,
            "timeframe": o.timeframe, "position_id": o.position_id, "simulated": True, "created_at": o.created_at.isoformat(),
            "filled_at": o.filled_at.isoformat() if o.filled_at else None}


def pos_dict(p: TdPosition, val: dict | None = None) -> dict:
    d = {"id": p.id, "account_id": p.account_id, "symbol": p.symbol, "side": p.side, "qty": p.qty, "entry_price": p.entry_price,
         "sl": p.sl, "tp": p.tp, "status": p.status, "exit_price": p.exit_price, "realized_pnl": p.realized_pnl, "fees": round(p.fees, 2),
         "reserved": round(p.reserved, 2), "exit_reason": p.exit_reason, "risk_money": p.risk_money, "strategy": p.strategy,
         "timeframe": p.timeframe, "data_kind": p.data_kind, "simulated": True, "opened_at": p.opened_at.isoformat(),
         "closed_at": p.closed_at.isoformat() if p.closed_at else None}
    if val:
        d |= {"price": val.get("price"), "price_kind": val.get("kind"), "unrealized": val.get("unrealized")}
    return d


# ───────────── Cuentas ─────────────

@router.get("/accounts")
def accounts(db: DB) -> list[dict]:
    accs = engine.ensure_accounts(db)
    db.commit()
    archived = list(db.scalars(select(TdAccount).where(TdAccount.active.is_(False)).order_by(TdAccount.id.desc())))
    return [acc_dict(a) for a in accs] + [acc_dict(a) for a in archived]


class AccountIn(BaseModel):
    kind: str = Field(pattern="^(safe|experimental)$")
    capital: float = Field(ge=100, le=1_000_000_000)
    currency: str = Field(default="EUR", pattern="^(EUR|USD)$")
    name: str | None = Field(default=None, max_length=80)


@router.post("/accounts", status_code=201)
def new_account(body: AccountIn, db: DB) -> dict:
    engine.ensure_accounts(db)
    try:
        a = engine.create_account(db, body.kind, body.capital, body.currency, body.name)
    except engine.OrderError as exc:
        raise HTTPException(409, str(exc)) from exc
    log_activity(db, "trading", "account", f"[SIMULADA] Nueva cuenta virtual {a.name}: {a.initial_capital:,.0f} {a.currency}")
    db.commit()
    return acc_dict(a)


class AccountPatch(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    slippage_bps: float | None = Field(default=None, ge=0, le=500)
    commission_fixed: float | None = Field(default=None, ge=0, le=1000)
    commission_pct: float | None = Field(default=None, ge=0, le=5)
    max_risk_pct: float | None = Field(default=None, ge=0, le=100)
    max_daily_loss_pct: float | None = Field(default=None, ge=0, le=100)
    max_drawdown_pct: float | None = Field(default=None, ge=0, le=100)
    max_exposure_pct: float | None = Field(default=None, ge=0, le=1000)
    require_stop: bool | None = None
    enforce_limits: bool | None = None


@router.patch("/accounts/{aid}")
def patch_account(aid: int, body: AccountPatch, db: DB) -> dict:
    a = _acc(db, aid)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    return acc_dict(a)


@router.get("/state")
def state(db: DB, account_id: int | None = None) -> dict:
    a = _acc(db, account_id)
    events = engine.process(db)
    db.commit()
    st = engine.account_state(db, a)
    ds = _day_start(db)
    base = engine.day_start_equity(db, a, ds)
    opens = list(db.scalars(select(TdPosition).where(TdPosition.account_id == a.id, TdPosition.status == "open").order_by(TdPosition.opened_at.desc())))
    pend = list(db.scalars(select(TdOrder).where(TdOrder.account_id == a.id, TdOrder.status == "pending").order_by(TdOrder.id.desc())))
    realized_today = sum(p.realized_pnl or 0 for p in db.scalars(select(TdPosition).where(
        TdPosition.account_id == a.id, TdPosition.status == "closed", TdPosition.closed_at >= ds)))
    exposure: dict[str, float] = {}
    for p in opens:
        exposure[p.symbol] = exposure.get(p.symbol, 0) + p.reserved
    open_risk = [p.risk_money for p in opens]
    return {"account": acc_dict(a), "label": SIM, **{k: v for k, v in st.items() if k != "values"},
            "day_pnl": round(st["equity"] - base, 2) if base is not None and not st["unpriced_positions"] else None,
            "day_realized": round(realized_today, 2), "drawdown": engine.drawdown(db, a, st["equity"]),
            "open_risk": round(sum(r for r in open_risk if r), 2) if opens else 0.0,
            "open_without_stop": sum(1 for r in open_risk if r is None),
            "exposure_by_symbol": [{"symbol": k, "amount": round(v, 2), "pct": round(v / st["equity"] * 100, 2) if st["equity"] > 0 else None}
                                   for k, v in sorted(exposure.items(), key=lambda x: -x[1])],
            "alerts": engine.check_limits(db, a, ds), "events": events,
            "positions": [pos_dict(p, st["values"].get(p.id)) for p in opens], "pending": [order_dict(o) for o in pend]}


# ───────────── Mercado ─────────────

@router.get("/instruments")
def list_instruments(db: DB) -> dict:
    ins = mk.instruments(db)
    return {"classes": mk.CLASSES, "timeframes": mk.TIMEFRAMES, "popular": mk.POPULAR,
            "instruments": [{"symbol": i.symbol, "name": i.name, "cls": i.cls, "ccy": i.ccy, "custom": i.custom,
                             "sources": [s for s in ("binance", "finnhub", "twelvedata", "stooq", "alphavantage")
                                         if getattr(i, {"twelvedata": "td", "alphavantage": "av"}.get(s, s))]} for i in ins.values()]}


class InstrumentIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9.\-/^]+$")
    name: str = Field(default="", max_length=80)
    cls: str = Field(pattern="^(stock|etf|crypto|forex|index|commodity)$")
    ccy: str = Field(default="USD", pattern="^[A-Za-z]{3}$")


@router.post("/instruments", status_code=201)
def add_instrument(body: InstrumentIn, db: DB) -> dict:
    inst = mk.custom_instrument(body.symbol, body.name, body.cls, body.ccy)
    if inst.symbol in mk.instruments(db):
        raise HTTPException(409, "Ese activo ya está en la lista")
    db.add(TdInstrument(symbol=inst.symbol, name=inst.name, cls=inst.cls, ccy=inst.ccy))
    db.commit()
    return {"symbol": inst.symbol}


@router.get("/overview")
async def overview(db: DB) -> dict:
    ins = mk.instruments(db)
    q = await run_in_threadpool(mk.quotes, list(ins.values()))
    watch = [w.symbol for w in db.scalars(select(TdWatch).order_by(TdWatch.sort, TdWatch.id))]
    rows = [{"symbol": i.symbol, "name": i.name, "cls": i.cls, "ccy": i.ccy, **{k: v for k, v in q[i.symbol].items() if k != "symbol"},
             "kind_label": mk.KIND_LABEL.get(q[i.symbol].get("kind") or "none")} for i in ins.values()]
    live = sum(1 for r in rows if r["price"] is not None)
    return {"rows": rows, "watchlist": watch, "classes": mk.CLASSES, "priced": live, "total": len(rows),
            "generated_at": datetime.utcnow().isoformat()}


@router.get("/quote")
async def get_quote(symbol: str, db: DB) -> dict:
    inst = _inst(db, symbol)
    q = await run_in_threadpool(mk.quote, inst)
    return q | {"kind_label": mk.KIND_LABEL.get(q.get("kind") or "none"), "name": inst.name, "cls": inst.cls, "ccy": inst.ccy}


@router.get("/candles")
async def get_candles(symbol: str, db: DB, tf: str = "1d", limit: int = 500) -> dict:
    inst = _inst(db, symbol)
    try:
        d = await run_in_threadpool(mk.candles, inst, tf, max(50, min(limit, 1500)))
    except mk.DataError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"symbol": symbol, "tf": tf, **d, "kind_label": mk.KIND_LABEL.get(d.get("kind") or "none")}


class WatchIn(BaseModel):
    symbol: str = Field(max_length=32)


@router.post("/watchlist", status_code=201)
def watch_add(body: WatchIn, db: DB) -> list[str]:
    _inst(db, body.symbol)
    if not db.scalar(select(TdWatch).where(TdWatch.symbol == body.symbol)):
        n = len(list(db.scalars(select(TdWatch))))
        db.add(TdWatch(symbol=body.symbol, sort=n))
        db.commit()
    return [w.symbol for w in db.scalars(select(TdWatch).order_by(TdWatch.sort, TdWatch.id))]


@router.delete("/watchlist")
def watch_del(symbol: str, db: DB) -> list[str]:
    w = db.scalar(select(TdWatch).where(TdWatch.symbol == symbol))
    if w:
        db.delete(w)
        db.commit()
    return [w.symbol for w in db.scalars(select(TdWatch).order_by(TdWatch.sort, TdWatch.id))]


class WatchOrder(BaseModel):
    symbols: list[str]


@router.put("/watchlist")
def watch_order(body: WatchOrder, db: DB) -> list[str]:
    pos = {s: i for i, s in enumerate(body.symbols)}
    for w in db.scalars(select(TdWatch)):
        w.sort = pos.get(w.symbol, 999)
    db.commit()
    return [w.symbol for w in db.scalars(select(TdWatch).order_by(TdWatch.sort, TdWatch.id))]


# ───────────── Órdenes y posiciones ─────────────

class OrderIn(BaseModel):
    account_id: int
    symbol: str = Field(max_length=32)
    side: str = Field(pattern="^(buy|sell)$")
    type: str = Field(pattern="^(market|limit|stop)$")
    qty: float = Field(gt=0)
    limit_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)
    sl: float | None = Field(default=None, gt=0)
    tp: float | None = Field(default=None, gt=0)
    strategy: str | None = Field(default=None, max_length=64)
    timeframe: str | None = Field(default=None, max_length=8)
    note: str | None = Field(default=None, max_length=2000)
    acknowledge_risk: bool = False


@router.post("/orders/preview")
async def preview(body: OrderIn, db: DB) -> dict:
    a = _acc(db, body.account_id)
    try:
        return await run_in_threadpool(engine.risk_preview, db, a, body.symbol, body.side, body.qty, body.type,
                                       body.limit_price, body.stop_price, body.sl, body.tp, _day_start(db))
    except engine.OrderError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/orders", status_code=201)
def place(body: OrderIn, db: DB) -> dict:
    a = _acc(db, body.account_id)
    try:
        o = engine.place_order(db, a, symbol=body.symbol, side=body.side, otype=body.type, qty=body.qty,
                               limit_price=body.limit_price, stop_price=body.stop_price, sl=body.sl, tp=body.tp,
                               strategy=(body.strategy or "").strip() or None, timeframe=body.timeframe, note=body.note,
                               acknowledge_risk=body.acknowledge_risk, day_start_utc=_day_start(db))
    except engine.RiskBlocked as exc:
        db.rollback()
        raise HTTPException(409, {"message": str(exc), "warnings": exc.warnings, "needs_ack": True}) from exc
    except engine.OrderError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    verb = {"filled": "ejecutada", "pending": "pendiente", "rejected": "rechazada"}.get(o.status, o.status)
    log_activity(db, "trading", "order", f"[SIMULADA] {o.type} {o.side} {o.qty:g} {o.symbol} {verb} · {a.name}")
    db.commit()
    return order_dict(o)


@router.post("/orders/{oid}/cancel")
def cancel(oid: int, db: DB) -> dict:
    o = db.get(TdOrder, oid)
    if not o:
        raise HTTPException(404, "Orden no encontrada")
    try:
        engine.cancel_order(db, o)
    except engine.OrderError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    return order_dict(o)


def _range(start: str | None, end: str | None) -> tuple[datetime | None, datetime | None]:
    s = datetime.fromisoformat(start) if start else None
    e = datetime.fromisoformat(end) + timedelta(days=1) if end else None
    return s, e


@router.get("/orders")
def orders(db: DB, account_id: int | None = None, status: str | None = None, symbol: str | None = None,
           start: str | None = None, end: str | None = None, limit: int = 300) -> list[dict]:
    q = select(TdOrder)
    if account_id:
        q = q.where(TdOrder.account_id == account_id)
    if status:
        q = q.where(TdOrder.status == status)
    if symbol:
        q = q.where(TdOrder.symbol == symbol)
    s, e = _range(start, end)
    if s:
        q = q.where(TdOrder.created_at >= s)
    if e:
        q = q.where(TdOrder.created_at < e)
    return [order_dict(o) for o in db.scalars(q.order_by(TdOrder.id.desc()).limit(min(limit, 2000)))]


@router.get("/positions")
def positions(db: DB, account_id: int | None = None, status: str = "closed", symbol: str | None = None,
              start: str | None = None, end: str | None = None, result: str | None = None, strategy: str | None = None) -> list[dict]:
    q = select(TdPosition).where(TdPosition.status == status)
    if account_id:
        q = q.where(TdPosition.account_id == account_id)
    if symbol:
        q = q.where(TdPosition.symbol == symbol)
    if strategy:
        q = q.where(TdPosition.strategy == strategy)
    s, e = _range(start, end)
    col = TdPosition.closed_at if status == "closed" else TdPosition.opened_at
    if s:
        q = q.where(col >= s)
    if e:
        q = q.where(col < e)
    ps = list(db.scalars(q.order_by(col.desc()).limit(1000)))
    if result == "win":
        ps = [p for p in ps if (p.realized_pnl or 0) > 0]
    elif result == "loss":
        ps = [p for p in ps if (p.realized_pnl or 0) < 0]
    journaled = {j.position_id for j in db.scalars(select(TdJournal))}
    return [pos_dict(p) | {"journaled": p.id in journaled} for p in ps]


class PosPatch(BaseModel):
    sl: float | None = Field(default=None, gt=0)
    tp: float | None = Field(default=None, gt=0)


@router.patch("/positions/{pid}")
def modify(pid: int, body: PosPatch, db: DB) -> dict:
    p = db.get(TdPosition, pid)
    if not p:
        raise HTTPException(404, "Posición no encontrada")
    a = db.get(TdAccount, p.account_id)
    inst = mk.instruments(db).get(p.symbol)
    price = mk.quote(inst).get("price") if inst else None
    try:
        engine.modify_position(p, body.sl, body.tp, price)
    except engine.OrderError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return pos_dict(p, engine.position_value(db, a, p))


class CloseIn(BaseModel):
    qty: float | None = Field(default=None, gt=0)


@router.post("/positions/{pid}/close")
def close(pid: int, body: CloseIn, db: DB) -> dict:
    p = db.get(TdPosition, pid)
    if not p:
        raise HTTPException(404, "Posición no encontrada")
    a = db.get(TdAccount, p.account_id)
    try:
        closed = engine.close_position(db, a, p, qty=body.qty)
    except engine.OrderError as exc:
        raise HTTPException(409, str(exc)) from exc
    engine.snapshot(db, a, "cierre")
    log_activity(db, "trading", "close", f"[SIMULADA] Cierre {closed.symbol} {closed.realized_pnl:+,.2f} {a.currency} · {a.name}")
    db.commit()
    return pos_dict(closed)


@router.post("/process")
def process_now(db: DB) -> dict:
    ev = engine.process(db)
    db.commit()
    return {"events": ev}


# ───────────── Analytics, diario y patrones ─────────────

@router.get("/analytics")
def get_analytics(db: DB, account_id: int | None = None, symbol: str | None = None, strategy: str | None = None,
                  start: str | None = None, end: str | None = None) -> dict:
    a = _acc(db, account_id)
    s, e = _range(start, end)
    return {"account": acc_dict(a), "label": SIM, **analytics.stats(db, a, symbol=symbol, strategy=strategy, start=s, end=e)}


@router.get("/patterns")
def patterns(db: DB, account_id: int | None = None) -> dict:
    return analytics.journal_patterns(db, _acc(db, account_id))


def journal_dict(j: TdJournal | None, pid: int) -> dict:
    if not j:
        return {"position_id": pid, "entry_reason": None, "strategy": None, "analysis": None, "emotion": None, "exit_reason": None,
                "mistakes": [], "lessons": None, "notes": None, "image": False, "updated_at": None}
    return {"position_id": pid, "entry_reason": j.entry_reason, "strategy": j.strategy, "analysis": j.analysis, "emotion": j.emotion,
            "exit_reason": j.exit_reason, "mistakes": j.mistakes or [], "lessons": j.lessons, "notes": j.notes,
            "image": bool(j.image), "updated_at": j.updated_at.isoformat()}


@router.get("/journal/{pid}")
def get_journal(pid: int, db: DB) -> dict:
    p = db.get(TdPosition, pid)
    if not p:
        raise HTTPException(404, "Operación no encontrada")
    return {"position": pos_dict(p), "journal": journal_dict(db.scalar(select(TdJournal).where(TdJournal.position_id == pid)), pid)}


class JournalIn(BaseModel):
    entry_reason: str | None = Field(default=None, max_length=4000)
    strategy: str | None = Field(default=None, max_length=64)
    analysis: str | None = Field(default=None, max_length=8000)
    emotion: str | None = Field(default=None, max_length=40)
    exit_reason: str | None = Field(default=None, max_length=4000)
    mistakes: list[str] = Field(default_factory=list, max_length=20)
    lessons: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=8000)
    remember: bool = False  # guardar la lección en la memoria de VISTAN


@router.put("/journal/{pid}")
def save_journal(pid: int, body: JournalIn, db: DB) -> dict:
    p = db.get(TdPosition, pid)
    if not p:
        raise HTTPException(404, "Operación no encontrada")
    j = db.scalar(select(TdJournal).where(TdJournal.position_id == pid)) or TdJournal(position_id=pid)
    for k, v in body.model_dump(exclude={"remember"}).items():
        setattr(j, k, [m.strip()[:40] for m in v if m.strip()] if k == "mistakes" else (v.strip() or None) if isinstance(v, str) else v)
    if j.strategy and not p.strategy:
        p.strategy = j.strategy
    db.add(j)
    remembered = False
    if body.remember and (j.lessons or j.mistakes):
        txt = f"Trading (simulación) · {p.symbol}: " + "; ".join(x for x in [
            f"lección: {j.lessons}" if j.lessons else "", f"errores: {', '.join(j.mistakes)}" if j.mistakes else "",
            f"estrategia: {j.strategy}" if j.strategy else ""] if x)
        from atlas.services.memory import remember
        remember(db, txt[:2000], kind="note", source="manual")
        remembered = True
    db.commit()
    return {"journal": journal_dict(j, pid), "remembered": remembered}


class ImageIn(BaseModel):
    data_url: str = Field(max_length=8_000_000)


def _img_dir():  # noqa: ANN202
    d = get_settings().resolved_data_dir / "private" / "trading"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


@router.post("/journal/{pid}/image")
def journal_image(pid: int, body: ImageIn, db: DB) -> dict:
    if not db.get(TdPosition, pid):
        raise HTTPException(404, "Operación no encontrada")
    head, _, b64 = body.data_url.partition(",")
    if head not in ("data:image/png;base64", "data:image/jpeg;base64"):
        raise HTTPException(422, "Solo imágenes PNG o JPEG")
    try:
        raw = base64.b64decode(b64, validate=True)
    except binascii.Error as exc:
        raise HTTPException(422, "Imagen no válida") from exc
    if not (raw.startswith(b"\x89PNG") or raw.startswith(b"\xff\xd8")):
        raise HTTPException(422, "Imagen no válida")
    name = f"chart_{pid}.{'png' if raw.startswith(b'\x89PNG') else 'jpg'}"
    path = _img_dir() / name
    path.write_bytes(raw)
    path.chmod(0o600)
    j = db.scalar(select(TdJournal).where(TdJournal.position_id == pid)) or TdJournal(position_id=pid)
    j.image = name
    db.add(j)
    db.commit()
    return {"ok": True}


@router.get("/journal/{pid}/image")
def journal_image_get(pid: int, db: DB) -> FileResponse:
    j = db.scalar(select(TdJournal).where(TdJournal.position_id == pid))
    if not j or not j.image:
        raise HTTPException(404, "Sin captura")
    return FileResponse(_img_dir() / j.image, headers={"Cache-Control": "no-store"})


# ───────────── Tutor (Trading Agent) ─────────────

class TutorIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    account_id: int | None = None
    symbol: str | None = Field(default=None, max_length=32)
    timeframe: str | None = Field(default=None, max_length=4)
    history: list[dict] = Field(default_factory=list, max_length=12)


@router.post("/tutor")
async def tutor(body: TutorIn, db: DB) -> dict:
    from atlas.brain.base import ProviderError
    from atlas.desk import tutor as t
    a = _acc(db, body.account_id)
    try:
        return await run_in_threadpool(t.ask, db, get_prefs(db), a, body.question, body.symbol, body.timeframe, _day_start(db), body.history)
    except ProviderError as exc:
        raise HTTPException(503, f"El tutor necesita la IA de VISTAN: {exc}") from exc


# ───────────── Noticias y macro ─────────────

@router.get("/news")
async def get_news() -> dict:
    return await run_in_threadpool(news.news)


@router.get("/macro")
async def get_macro() -> dict:
    return await run_in_threadpool(news.macro)


@router.get("/calendar")
async def get_calendar() -> dict:
    return await run_in_threadpool(news.calendar)


# ───────────── Proveedores de datos ─────────────

@router.get("/providers")
async def providers(test: bool = False) -> list[dict]:
    return await run_in_threadpool(mk.provider_status, test)


class KeyIn(BaseModel):
    key: str = Field(min_length=4, max_length=200)


@router.put("/providers/{pid}/key")
def set_key(pid: str, body: KeyIn, db: DB) -> dict:
    p = mk.PROVIDERS.get(pid)
    if not p or not p["key"]:
        raise HTTPException(404, "Proveedor sin clave configurable")
    where = set_secret(p["key"], body.key.strip())
    mk.clear_cache()
    log_activity(db, "security", "credential", f"API key de datos de mercado guardada: {p['name']}")
    db.commit()
    return {"ok": True, "stored_in": where}


@router.delete("/providers/{pid}/key")
def del_key(pid: str, db: DB) -> dict:
    p = mk.PROVIDERS.get(pid)
    if not p or not p["key"]:
        raise HTTPException(404, "Proveedor sin clave configurable")
    delete_secret(p["key"])
    mk.clear_cache()
    log_activity(db, "security", "credential", f"API key de datos de mercado eliminada: {p['name']}")
    db.commit()
    return {"ok": True}


# ───────────── Backtesting ─────────────

@router.get("/backtest/strategies")
def strategies() -> dict:
    return backtest.STRATEGIES


class BacktestIn(BaseModel):
    symbol: str = Field(max_length=32)
    tf: str = Field(default="1d", pattern="^(1m|5m|15m|30m|1h|4h|1d|1w|1M)$")
    start: str
    end: str
    strategy: str
    params: dict = Field(default_factory=dict)
    capital: float = Field(default=10_000, ge=100, le=1_000_000_000)
    commission_pct: float = Field(default=0.1, ge=0, le=5)
    slippage_bps: float = Field(default=5, ge=0, le=500)
    position_pct: float = Field(default=100, gt=0, le=100)


@router.post("/backtest")
async def run_backtest(body: BacktestIn, db: DB) -> dict:
    if body.strategy not in backtest.STRATEGIES:
        raise HTTPException(422, "Estrategia desconocida")
    inst = _inst(db, body.symbol)
    try:
        s = int(datetime.fromisoformat(body.start).replace(tzinfo=ZoneInfo("UTC")).timestamp())
        e = int((datetime.fromisoformat(body.end) + timedelta(days=1)).replace(tzinfo=ZoneInfo("UTC")).timestamp())
    except ValueError as exc:
        raise HTTPException(422, "Fechas no válidas") from exc
    if e <= s:
        raise HTTPException(422, "El periodo no es válido")
    try:
        h = await run_in_threadpool(mk.history, inst, body.tf, s, e)
        res = backtest.run(h["candles"], body.strategy, body.params, body.capital, body.commission_pct, body.slippage_bps, body.position_pct)
    except (mk.DataError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    res |= {"symbol": body.symbol, "tf": body.tf, "source": h["source"], "data_kind": "historical"}
    bt = TdBacktest(params=body.model_dump(), result={k: v for k, v in res.items() if k != "curve"} | {"curve": res["curve"]})
    db.add(bt)
    log_activity(db, "trading", "backtest", f"Backtest {res['strategy_name']} en {body.symbol} {body.tf}: {res['return_pct']:+.2f}%")
    db.commit()
    return res | {"id": bt.id}


@router.get("/backtests")
def backtests(db: DB) -> list[dict]:
    return [{"id": b.id, "created_at": b.created_at.isoformat(), "params": b.params,
             "summary": {k: b.result.get(k) for k in ("strategy_name", "return_pct", "max_drawdown_pct", "trades", "win_rate", "profit_factor", "buy_hold_pct", "source")}}
            for b in db.scalars(select(TdBacktest).order_by(TdBacktest.id.desc()).limit(30))]


# ───────────── Integración con Research ─────────────

class ResearchIn(BaseModel):
    symbol: str = Field(max_length=32)


@router.post("/research", status_code=201)
def research_asset(body: ResearchIn, db: DB) -> dict:
    from atlas.research import engine as rengine
    inst = _inst(db, body.symbol)
    r = Research(question=f"Análisis educativo de {inst.name} ({inst.symbol}): situación reciente, factores que mueven su precio y riesgos principales",
                 status="queued", state={})
    db.add(r)
    log_activity(db, "research", "start", f"Investigación desde Trading Desk: {inst.symbol}")
    db.commit()
    rengine.start(r.id)
    return {"id": r.id}
