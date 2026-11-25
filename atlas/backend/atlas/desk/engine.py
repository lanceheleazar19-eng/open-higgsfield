"""Motor de PAPER TRADING. Dinero VIRTUAL: no existe ninguna ruta de código que envíe órdenes a un bróker.

Modelo de cuenta (sin apalancamiento): abrir una posición (larga o corta) compromete su nominal en la divisa de la
cuenta (`reserved`) más los costes. Equity = efectivo + capital comprometido + P&L no realizado.

Ejecución:
- Market: último precio disponible ± deslizamiento (bps) en contra. Sin precio → orden rechazada.
- Limit: compra si precio ≤ límite (al precio, nunca peor que el límite); venta si precio ≥ límite.
- Stop: compra si precio ≥ stop; venta si precio ≤ stop (al precio ± deslizamiento).
- Stop Loss / Take Profit de las posiciones: se comprueban con cada precio nuevo.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.desk import market as mk
from atlas.models import TdAccount, TdEquity, TdOrder, TdPosition
from atlas.models.base import utcnow

DEFAULT_ACCOUNTS = {
    "safe": {"name": "SAFE ACCOUNT", "initial_capital": 100_000.0, "max_risk_pct": 1.0, "max_daily_loss_pct": 3.0,
             "max_drawdown_pct": 10.0, "max_exposure_pct": 60.0, "require_stop": True, "enforce_limits": True},
    "experimental": {"name": "EXPERIMENTAL ACCOUNT", "initial_capital": 100_000.0, "max_risk_pct": 5.0, "max_daily_loss_pct": 10.0,
                     "max_drawdown_pct": 35.0, "max_exposure_pct": 100.0, "require_stop": False, "enforce_limits": False},
}


class OrderError(ValueError):
    pass


class RiskBlocked(ValueError):
    def __init__(self, warnings: list[dict]):
        super().__init__("La orden supera los límites de riesgo de la cuenta")
        self.warnings = warnings


def ensure_accounts(db: Session) -> list[TdAccount]:
    accs = list(db.scalars(select(TdAccount).where(TdAccount.active.is_(True)).order_by(TdAccount.id)))
    for kind, cfg in DEFAULT_ACCOUNTS.items():
        if not any(a.kind == kind for a in accs):
            a = TdAccount(kind=kind, cash=cfg["initial_capital"], currency="EUR", **cfg)
            db.add(a)
            db.flush()
            db.add(TdEquity(account_id=a.id, equity=a.cash, cash=a.cash, used=0.0, event="apertura"))
            accs.append(a)
    db.flush()
    return accs


def create_account(db: Session, kind: str, capital: float, currency: str = "EUR", name: str | None = None) -> TdAccount:
    """Nueva cuenta virtual del mismo tipo. La anterior se archiva (su historial se conserva)."""
    if kind not in DEFAULT_ACCOUNTS:
        raise OrderError("Tipo de cuenta no válido")
    if not 100 <= capital <= 1_000_000_000:
        raise OrderError("Capital inicial entre 100 y 1.000.000.000")
    for old in db.scalars(select(TdAccount).where(TdAccount.kind == kind, TdAccount.active.is_(True))):
        if db.scalar(select(TdPosition.id).where(TdPosition.account_id == old.id, TdPosition.status == "open")):
            raise OrderError("Cierra las posiciones abiertas antes de crear una cuenta nueva")
        for o in db.scalars(select(TdOrder).where(TdOrder.account_id == old.id, TdOrder.status == "pending")):
            o.status, o.reason = "cancelled", "Cuenta archivada"
        old.active = False
    cfg = {**DEFAULT_ACCOUNTS[kind], "initial_capital": capital}
    if name:
        cfg["name"] = name
    a = TdAccount(kind=kind, cash=capital, currency=currency.upper(), **cfg)
    db.add(a)
    db.flush()
    db.add(TdEquity(account_id=a.id, equity=capital, cash=capital, used=0.0, event="apertura"))
    return a


# ───────────── Valoración ─────────────

def _dir(side: str) -> int:
    return 1 if side in ("long", "buy") else -1


def fees_for(acc: TdAccount, notional_acc: float) -> float:
    return round(acc.commission_fixed + notional_acc * acc.commission_pct / 100, 4)


def position_value(db: Session, acc: TdAccount, p: TdPosition, price: float | None = None) -> dict:
    inst = mk.instruments(db).get(p.symbol)
    q = mk.quote(inst) if inst and price is None else {"price": price, "kind": "historical", "source": None}
    px = q.get("price")
    fx = p.entry_fx
    if inst and inst.ccy != acc.currency:
        r, _ = mk.fx_rate(inst.ccy, acc.currency, db)
        fx = r or p.entry_fx
    upnl = (px - p.entry_price) * p.qty * _dir(p.side) * fx if px is not None else None
    return {"price": px, "kind": q.get("kind"), "source": q.get("source"), "ts": q.get("ts"), "fx": fx,
            "unrealized": round(upnl, 2) if upnl is not None else None}


def account_state(db: Session, acc: TdAccount, with_quotes: bool = True) -> dict:
    opens = list(db.scalars(select(TdPosition).where(TdPosition.account_id == acc.id, TdPosition.status == "open")))
    used = sum(p.reserved for p in opens)
    unreal = 0.0
    missing = 0
    vals = {}
    for p in opens:
        v = position_value(db, acc, p) if with_quotes else {"unrealized": None}
        vals[p.id] = v
        if v["unrealized"] is None:
            missing += 1
        else:
            unreal += v["unrealized"]
    equity = acc.cash + used + unreal
    realized = sum(p.realized_pnl or 0 for p in db.scalars(select(TdPosition).where(TdPosition.account_id == acc.id, TdPosition.status == "closed")))
    return {"equity": round(equity, 2), "cash": round(acc.cash, 2), "used": round(used, 2), "unrealized": round(unreal, 2),
            "realized": round(realized, 2), "total_pnl": round(equity - acc.initial_capital, 2),
            "return_pct": round((equity / acc.initial_capital - 1) * 100, 3), "open_positions": len(opens),
            "exposure_pct": round(used / equity * 100, 2) if equity > 0 else None,
            "unpriced_positions": missing, "values": vals}


def snapshot(db: Session, acc: TdAccount, event: str | None = None) -> None:
    st = account_state(db, acc)
    if st["unpriced_positions"]:
        return  # sin precio no se registra una equity inventada
    db.add(TdEquity(account_id=acc.id, equity=st["equity"], cash=st["cash"], used=st["used"], event=event))


def day_start_equity(db: Session, acc: TdAccount, day_start_utc: datetime) -> float | None:
    e = db.scalar(select(TdEquity).where(TdEquity.account_id == acc.id, TdEquity.ts < day_start_utc).order_by(TdEquity.ts.desc()).limit(1))
    if e is None:
        e = db.scalar(select(TdEquity).where(TdEquity.account_id == acc.id).order_by(TdEquity.ts).limit(1))
    return e.equity if e else None


def drawdown(db: Session, acc: TdAccount, current: float | None = None) -> dict:
    eqs = [e.equity for e in db.scalars(select(TdEquity).where(TdEquity.account_id == acc.id).order_by(TdEquity.ts))]
    if current is not None:
        eqs.append(current)
    peak, max_dd, cur_dd = None, 0.0, 0.0
    for v in eqs:
        peak = v if peak is None or v > peak else peak
        dd = (peak - v) / peak * 100 if peak else 0
        max_dd = max(max_dd, dd)
        cur_dd = dd
    return {"current_pct": round(cur_dd, 2), "max_pct": round(max_dd, 2), "peak": peak, "points": len(eqs)}


# ───────────── Riesgo ─────────────

def risk_preview(db: Session, acc: TdAccount, symbol: str, side: str, qty: float, otype: str = "market",
                 limit_price: float | None = None, stop_price: float | None = None, sl: float | None = None,
                 tp: float | None = None, day_start_utc: datetime | None = None) -> dict:
    inst = mk.instruments(db).get(symbol)
    if not inst:
        raise OrderError(f"Activo desconocido: {symbol}")
    q = mk.quote(inst)
    last = q.get("price")
    entry = limit_price if otype == "limit" else stop_price if otype == "stop" else last
    fx, fx_note = mk.fx_rate(inst.ccy, acc.currency, db)
    st = account_state(db, acc)
    eq = st["equity"]
    out: dict = {"symbol": symbol, "price": last, "kind": q.get("kind"), "source": q.get("source"), "ts": q.get("ts"),
                 "entry": entry, "fx": fx, "fx_note": fx_note, "quote_ccy": inst.ccy, "account_ccy": acc.currency,
                 "equity": eq, "notional": None, "fees": None, "risk_money": None, "risk_pct": None, "rr": None,
                 "reward_money": None, "suggested_qty": None, "warnings": [], "blocking": False}
    w = out["warnings"]
    if entry is None:
        w.append({"code": "no_price", "level": "block", "text": "Sin precio de mercado: no se puede valorar ni ejecutar la orden"})
        out["blocking"] = True
        return out
    if fx is None:
        w.append({"code": "no_fx", "level": "block", "text": f"Sin tipo de cambio {inst.ccy}→{acc.currency}"})
        out["blocking"] = True
        return out
    d = _dir(side)
    notional = entry * qty * fx
    out["notional"] = round(notional, 2)
    out["fees"] = round(fees_for(acc, notional) * 2, 2)  # entrada + salida estimada
    if sl is not None:
        if (d == 1 and sl >= entry) or (d == -1 and sl <= entry):
            w.append({"code": "bad_sl", "level": "block", "text": "El stop loss debe quedar por debajo de la entrada en compras y por encima en ventas"})
        rm = abs(entry - sl) * qty * fx + out["fees"]
        out["risk_money"] = round(rm, 2)
        out["risk_pct"] = round(rm / eq * 100, 3) if eq > 0 else None
        if acc.max_risk_pct and abs(entry - sl) > 0:
            out["suggested_qty"] = round(max(eq * acc.max_risk_pct / 100 - out["fees"], 0) / (abs(entry - sl) * fx), 6)
    if tp is not None:
        if (d == 1 and tp <= entry) or (d == -1 and tp >= entry):
            w.append({"code": "bad_tp", "level": "block", "text": "El take profit debe quedar por encima de la entrada en compras y por debajo en ventas"})
        out["reward_money"] = round(abs(tp - entry) * qty * fx - out["fees"], 2)
        if sl is not None and abs(entry - sl) > 0:
            out["rr"] = round(abs(tp - entry) / abs(entry - sl), 2)
    lvl = "block" if acc.enforce_limits else "warn"
    if sl is None and acc.require_stop:
        w.append({"code": "no_stop", "level": lvl, "text": "Esta cuenta exige stop loss en cada operación"})
    elif sl is None:
        w.append({"code": "no_stop", "level": "warn", "text": "Sin stop loss: el riesgo de la operación no está limitado"})
    if out["risk_pct"] is not None and acc.max_risk_pct and out["risk_pct"] > acc.max_risk_pct:
        w.append({"code": "risk", "level": lvl, "text": f"Riesgo {out['risk_pct']:.2f}% > máximo de la cuenta {acc.max_risk_pct}%"})
    if out["rr"] is not None and out["rr"] < 1:
        w.append({"code": "rr", "level": "warn", "text": f"Relación riesgo/beneficio {out['rr']}: ganas menos de lo que arriesgas"})
    if notional + out["fees"] / 2 > acc.cash:
        w.append({"code": "cash", "level": "block", "text": "Saldo virtual disponible insuficiente"})
    if acc.max_exposure_pct and eq > 0 and (st["used"] + notional) / eq * 100 > acc.max_exposure_pct:
        w.append({"code": "exposure", "level": lvl, "text": f"Exposición total {(st['used'] + notional) / eq * 100:.1f}% > límite {acc.max_exposure_pct}%"})
    if day_start_utc is not None and acc.max_daily_loss_pct:
        base = day_start_equity(db, acc, day_start_utc)
        if base and (base - eq) / base * 100 >= acc.max_daily_loss_pct:
            w.append({"code": "daily_loss", "level": lvl, "text": f"Pérdida diaria {(base - eq) / base * 100:.2f}% ≥ límite {acc.max_daily_loss_pct}%"})
    if acc.max_drawdown_pct:
        dd = drawdown(db, acc, eq)
        if dd["current_pct"] >= acc.max_drawdown_pct:
            w.append({"code": "drawdown", "level": lvl, "text": f"Drawdown {dd['current_pct']}% ≥ límite {acc.max_drawdown_pct}%"})
    if q.get("kind") == "delayed":
        w.append({"code": "delayed", "level": "info", "text": "Precio con retraso: la ejecución simulada usa el último dato disponible"})
    out["blocking"] = any(x["level"] == "block" for x in w)
    return out


# ───────────── Órdenes ─────────────

def _fill(db: Session, acc: TdAccount, o: TdOrder, price: float, kind: str | None, source: str | None) -> TdPosition | None:
    inst = mk.instruments(db).get(o.symbol)
    fx, _ = mk.fx_rate(inst.ccy, acc.currency, db) if inst else (None, None)
    if fx is None:
        o.status, o.reason = "rejected", "Sin tipo de cambio para valorar la orden"
        return None
    notional = price * o.qty * fx
    fee = fees_for(acc, notional)
    if notional + fee > acc.cash + 1e-9:
        o.status, o.reason = "rejected", f"Saldo virtual insuficiente al ejecutar ({notional + fee:,.2f} > {acc.cash:,.2f})"
        return None
    acc.cash -= notional + fee
    p = TdPosition(account_id=acc.id, symbol=o.symbol, side="long" if o.side == "buy" else "short", qty=o.qty, entry_price=price,
                   entry_fx=fx, reserved=notional, fees=fee, sl=o.sl, tp=o.tp, status="open", strategy=o.strategy,
                   timeframe=o.timeframe, data_kind=kind,
                   risk_money=round(abs(price - o.sl) * o.qty * fx, 2) if o.sl is not None else None)
    db.add(p)
    db.flush()
    o.status, o.fill_price, o.fees, o.fx, o.filled_at, o.position_id = "filled", price, fee, fx, utcnow(), p.id
    o.data_kind, o.data_source = kind, source
    return p


def _slip(acc: TdAccount, price: float, side_dir: int) -> float:
    return price * (1 + side_dir * acc.slippage_bps / 10_000)


def place_order(db: Session, acc: TdAccount, *, symbol: str, side: str, otype: str, qty: float,
                limit_price: float | None = None, stop_price: float | None = None, sl: float | None = None,
                tp: float | None = None, strategy: str | None = None, timeframe: str | None = None,
                note: str | None = None, acknowledge_risk: bool = False, day_start_utc: datetime | None = None) -> TdOrder:
    """1) valida 2) comprueba saldo 3) reglas de ejecución 4) registra 5) cartera 6) P&L 7) estadísticas (equity)."""
    if not acc.active:
        raise OrderError("Esta cuenta está archivada")
    if side not in ("buy", "sell") or otype not in ("market", "limit", "stop"):
        raise OrderError("Orden no válida")
    if not qty or qty <= 0:
        raise OrderError("La cantidad debe ser mayor que 0")
    if otype == "limit" and not limit_price:
        raise OrderError("Indica el precio límite")
    if otype == "stop" and not stop_price:
        raise OrderError("Indica el precio de activación (stop)")
    pre = risk_preview(db, acc, symbol, side, qty, otype, limit_price, stop_price, sl, tp, day_start_utc)
    hard = [w for w in pre["warnings"] if w["level"] == "block" and w["code"] in ("no_price", "no_fx", "bad_sl", "bad_tp", "cash")]
    o = TdOrder(account_id=acc.id, symbol=symbol, side=side, type=otype, qty=qty, limit_price=limit_price, stop_price=stop_price,
                sl=sl, tp=tp, strategy=strategy, timeframe=timeframe, note=note, ref_price=pre["price"],
                risk_money=pre["risk_money"], risk_pct=pre["risk_pct"], warnings=pre["warnings"],
                data_kind=pre["kind"], data_source=pre["source"], status="pending")
    if hard and not (otype != "market" and [w["code"] for w in hard] == ["cash"]):
        o.status, o.reason = "rejected", "; ".join(w["text"] for w in hard)
    elif pre["blocking"] and acc.enforce_limits:
        o.status, o.reason = "rejected", "Bloqueada por los límites de la cuenta: " + "; ".join(w["text"] for w in pre["warnings"] if w["level"] == "block")
    elif any(w["level"] in ("warn", "block") and w["code"] in ("risk", "exposure", "daily_loss", "drawdown", "no_stop") for w in pre["warnings"]) and not acknowledge_risk:
        raise RiskBlocked(pre["warnings"])
    db.add(o)
    db.flush()
    if o.status == "pending" and otype == "market":
        _fill(db, acc, o, _slip(acc, pre["price"], _dir(side)), pre["kind"], pre["source"])
        snapshot(db, acc, "orden")
    return o


def cancel_order(db: Session, o: TdOrder) -> TdOrder:
    if o.status != "pending":
        raise OrderError("Solo se pueden cancelar órdenes pendientes")
    o.status, o.reason = "cancelled", "Cancelada por ti"
    return o


def close_position(db: Session, acc: TdAccount, p: TdPosition, price: float | None = None, reason: str = "manual",
                   qty: float | None = None, kind: str | None = None) -> TdPosition:
    if p.status != "open":
        raise OrderError("La posición ya está cerrada")
    inst = mk.instruments(db).get(p.symbol)
    if price is None:
        q = mk.quote(inst) if inst else {}
        if q.get("price") is None:
            raise OrderError("Sin precio de mercado: no se puede cerrar ahora (no se inventa un precio)")
        price = _slip(acc, q["price"], -_dir(p.side))
        kind = q.get("kind")
    fx = p.entry_fx
    if inst and inst.ccy != acc.currency:
        r, _ = mk.fx_rate(inst.ccy, acc.currency, db)
        fx = r or p.entry_fx
    target = p
    if qty is not None and 0 < qty < p.qty:  # cierre parcial: la parte cerrada pasa a una posición cerrada propia
        frac = qty / p.qty
        target = TdPosition(account_id=p.account_id, symbol=p.symbol, side=p.side, qty=qty, entry_price=p.entry_price,
                            entry_fx=p.entry_fx, reserved=p.reserved * frac, fees=p.fees * frac, sl=p.sl, tp=p.tp, status="open",
                            strategy=p.strategy, timeframe=p.timeframe, data_kind=p.data_kind, parent_id=p.id,
                            risk_money=p.risk_money * frac if p.risk_money else None, opened_at=p.opened_at)
        p.qty -= qty
        p.reserved -= target.reserved
        p.fees -= target.fees
        if p.risk_money:
            p.risk_money -= target.risk_money or 0
        db.add(target)
        db.flush()
    gross = (price - target.entry_price) * target.qty * _dir(target.side) * fx
    exit_fee = fees_for(acc, price * target.qty * fx)
    acc.cash += target.reserved + gross - exit_fee
    target.fees += exit_fee
    target.realized_pnl = round(gross - target.fees, 2)
    target.exit_price, target.exit_fx, target.exit_reason = price, fx, reason
    target.status, target.closed_at = "closed", utcnow()
    return target


def modify_position(p: TdPosition, sl: float | None, tp: float | None, price: float | None) -> TdPosition:
    if p.status != "open":
        raise OrderError("La posición está cerrada")
    d = _dir(p.side)
    ref = price if price is not None else p.entry_price
    if sl is not None and ((d == 1 and sl >= ref) or (d == -1 and sl <= ref)):
        raise OrderError("Stop loss en el lado equivocado del precio actual")
    if tp is not None and ((d == 1 and tp <= ref) or (d == -1 and tp >= ref)):
        raise OrderError("Take profit en el lado equivocado del precio actual")
    p.sl, p.tp = sl, tp
    return p


def process(db: Session, prices: dict[str, dict] | None = None) -> list[dict]:
    """Revisa órdenes pendientes y SL/TP con el último precio disponible. Devuelve los eventos ocurridos."""
    from atlas.security.policy import notify
    events: list[dict] = []
    accs = {a.id: a for a in db.scalars(select(TdAccount).where(TdAccount.active.is_(True)))}
    pend = [o for o in db.scalars(select(TdOrder).where(TdOrder.status == "pending")) if o.account_id in accs]
    opens = [p for p in db.scalars(select(TdPosition).where(TdPosition.status == "open")) if p.account_id in accs and (p.sl or p.tp)]
    syms = {o.symbol for o in pend} | {p.symbol for p in opens}
    if not syms:
        return events
    insts = mk.instruments(db)
    if prices is None:
        prices = mk.quotes([insts[s] for s in syms if s in insts])
    touched: set[int] = set()
    for o in pend:
        q = prices.get(o.symbol) or {}
        px = q.get("price")
        if px is None:
            continue
        acc = accs[o.account_id]
        d = _dir(o.side)
        fill = None
        if o.type == "limit" and ((d == 1 and px <= o.limit_price) or (d == -1 and px >= o.limit_price)):
            fill = min(px, o.limit_price) if d == 1 else max(px, o.limit_price)
        elif o.type == "stop" and ((d == 1 and px >= o.stop_price) or (d == -1 and px <= o.stop_price)):
            fill = _slip(acc, px, d)
        if fill is None:
            continue
        p = _fill(db, acc, o, fill, q.get("kind"), q.get("source"))
        touched.add(acc.id)
        txt = (f"[SIMULADA] {o.type.upper()} {o.side.upper()} {o.qty:g} {o.symbol} ejecutada a {fill:,.4f}" if p
               else f"[SIMULADA] Orden {o.type} {o.symbol} rechazada: {o.reason}")
        events.append({"type": "fill" if p else "reject", "order_id": o.id, "text": txt})
        notify(db, txt, f"Cuenta {acc.name} (dinero virtual)", "info" if p else "warning", "/trading")
    for p in opens:
        q = prices.get(p.symbol) or {}
        px = q.get("price")
        if px is None or p.status != "open":
            continue
        d = _dir(p.side)
        hit = None
        if p.sl is not None and ((d == 1 and px <= p.sl) or (d == -1 and px >= p.sl)):
            hit = "stop_loss"
        elif p.tp is not None and ((d == 1 and px >= p.tp) or (d == -1 and px <= p.tp)):
            hit = "take_profit"
        if not hit:
            continue
        acc = accs[p.account_id]
        exit_px = _slip(acc, px, -d) if hit == "stop_loss" else px
        close_position(db, acc, p, exit_px, hit, kind=q.get("kind"))
        touched.add(acc.id)
        txt = f"[SIMULADA] {'Stop loss' if hit == 'stop_loss' else 'Take profit'} en {p.symbol}: {p.realized_pnl:+,.2f} {acc.currency}"
        events.append({"type": hit, "position_id": p.id, "text": txt})
        notify(db, txt, f"Cuenta {acc.name} (dinero virtual)", "info", "/trading")
    for aid in touched:
        snapshot(db, accs[aid], "ejecución")
    return events


def check_limits(db: Session, acc: TdAccount, day_start_utc: datetime) -> list[str]:
    """Alertas de límites superados (para notificaciones)."""
    st = account_state(db, acc)
    if st["unpriced_positions"]:
        return []
    out = []
    base = day_start_equity(db, acc, day_start_utc)
    if base and acc.max_daily_loss_pct and (base - st["equity"]) / base * 100 >= acc.max_daily_loss_pct:
        out.append(f"Pérdida diaria ≥ {acc.max_daily_loss_pct}%")
    dd = drawdown(db, acc, st["equity"])
    if acc.max_drawdown_pct and dd["current_pct"] >= acc.max_drawdown_pct:
        out.append(f"Drawdown ≥ {acc.max_drawdown_pct}%")
    if acc.max_exposure_pct and st["exposure_pct"] and st["exposure_pct"] > acc.max_exposure_pct:
        out.append(f"Exposición > {acc.max_exposure_pct}%")
    return out


def periodic(db: Session, every: timedelta = timedelta(minutes=15)) -> None:
    """Bucle del servidor: ejecuta órdenes/SL/TP y guarda la equity de las cuentas con posiciones abiertas."""
    process(db)
    for acc in db.scalars(select(TdAccount).where(TdAccount.active.is_(True))):
        if not db.scalar(select(TdPosition.id).where(TdPosition.account_id == acc.id, TdPosition.status == "open")):
            continue
        last = db.scalar(select(TdEquity.ts).where(TdEquity.account_id == acc.id).order_by(TdEquity.ts.desc()).limit(1))
        if not last or utcnow() - last >= every:
            snapshot(db, acc, "periódica")
