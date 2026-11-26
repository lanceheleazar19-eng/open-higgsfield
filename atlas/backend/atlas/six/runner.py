"""VISTAN SIX: seis agentes que operan de forma autónoma con el motor de PAPER TRADING existente (atlas.desk.engine).

- Toda orden pasa por engine.place_order / close_position / modify_position / cancel_order: mismas comisiones, deslizamiento,
  límites de riesgo de la cuenta y registro. No hay simulador paralelo ni ninguna ruta hacia un bróker real.
- Cada agente tiene una ASIGNACIÓN virtual dentro de su cuenta (SAFE o EXPERIMENTAL) y solo opera con ella: su rendimiento se
  mide con sus propias posiciones (id de estrategia «SIX:…»), sin mezclar balances con otros agentes.
- Datos: solo velas CERRADAS reales del proveedor del Trading Desk; si faltan, están desactualizadas o el precio actual se
  desvía de forma anómala, no se opera (y se registra por qué).
- Sin duplicados: una posición u orden pendiente por agente y activo, y cada vela se evalúa para entradas una sola vez.
- Frenos: kill switch de VISTAN, parada de emergencia de SIX, pérdida diaria y drawdown máximo por agente.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.desk import engine
from atlas.desk import market as mk
from atlas.models import SxAgent, SxDecision, TdAccount, TdJournal, TdOrder, TdPosition
from atlas.six import strategies as st

TF_S = mk.TF_SECONDS
AGENTS = [
    # key, name, cuenta, familia, símbolos, variantes, asignación %, riesgo %, máx. posiciones, DD máx %, pérdida diaria %
    ("orion", "ORION · Tendencia", "safe", "ema_trend", ["BTC/USDT", "ETH/USDT"],
     [{"timeframe": "1h", "params": {"fast": 20, "slow": 50, "sl_atr": 2.0, "tp_atr": 4.0, "trail_atr": 2.5}}], 30, 0.5, 2, 8, 2),
    ("vega", "VEGA · Reversión a la media", "safe", "meanrev", ["BTC/USDT", "ETH/USDT"],
     [{"timeframe": "1h", "params": {"period": 20, "k": 2.0, "rsi_low": 30, "rsi_high": 70, "sl_atr": 1.5}}], 30, 0.5, 2, 8, 2),
    ("lyra", "LYRA · RSI + MACD", "safe", "rsi_macd", ["BTC/USDT", "SOL/USDT"],
     [{"timeframe": "4h", "params": {"sl_atr": 2.0, "tp_atr": 3.0}}], 30, 0.5, 2, 8, 2),
    ("nova", "NOVA · Breakout", "experimental", "breakout", ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
     [{"timeframe": "1h", "params": {"n": 20, "exit_n": 10, "sl_atr": 2.0, "trail_atr": 3.0}},
      {"timeframe": "4h", "params": {"n": 55, "exit_n": 20, "sl_atr": 2.5, "trail_atr": 3.5}}], 30, 1.5, 3, 25, 6),
    ("rigel", "RIGEL · Momentum", "experimental", "momentum", ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
     [{"timeframe": "1h", "params": {"n": 12, "thr": 1.0, "sl_atr": 2.0, "tp_atr": 3.0, "max_bars": 20}},
      {"timeframe": "15m", "params": {"n": 24, "thr": 0.8, "sl_atr": 1.5, "tp_atr": 2.5, "max_bars": 32}}], 30, 1.5, 3, 25, 6),
    ("altair", "ALTAIR · Cruce de medias (experimentos)", "experimental", "ma_cross", ["BTC/USDT", "ETH/USDT"],
     [{"timeframe": "1h", "params": {"fast": 10, "slow": 30, "sl_atr": 2.0, "tp_atr": 4.0}},
      {"timeframe": "4h", "params": {"fast": 20, "slow": 50, "sl_atr": 2.0, "tp_atr": 4.0}},
      {"timeframe": "15m", "params": {"fast": 5, "slow": 20, "sl_atr": 1.5, "tp_atr": 3.0}}], 30, 1.5, 3, 25, 6),
]
MIN_TRADES_ROTATE = 20  # no se cambia de variante por unas pocas operaciones negativas
LIMIT_EXPIRY_BARS = 3
MAX_DEVIATION = 0.08  # precio actual vs último cierre: más de un 8 % se considera dato anómalo


def sid_for(a: SxAgent, idx: int) -> str:
    return f"SIX:{a.key}:{a.family}:{a.variants[idx]['timeframe']}:v{idx + 1}"[:64]


def sid(a: SxAgent) -> str:
    return sid_for(a, a.variant_idx)


def ensure_agents(db: Session) -> list[SxAgent]:
    have = {a.key for a in db.scalars(select(SxAgent))}
    for key, name, kind, fam, syms, variants, alloc, risk, maxp, dd, daily in AGENTS:
        if key not in have:
            db.add(SxAgent(key=key, name=name, account_kind=kind, family=fam, symbols=syms, variants=variants, allocation_pct=alloc,
                           risk_pct=risk, max_positions=maxp, max_dd_pct=dd, max_daily_loss_pct=daily, state={}))
    db.flush()
    return list(db.scalars(select(SxAgent).order_by(SxAgent.id)))


def account_for(db: Session, a: SxAgent) -> TdAccount | None:
    return db.scalar(select(TdAccount).where(TdAccount.kind == a.account_kind, TdAccount.active.is_(True)))


def log(db: Session, a: SxAgent, action: str, status: str, reason: str, symbol: str | None = None, data: dict | None = None,
        order_id: int | None = None, position_id: int | None = None) -> SxDecision:
    d = SxDecision(agent=a.key, strategy=sid(a), symbol=symbol, action=action, status=status, reason=reason[:2000], data=data or {},
                   order_id=order_id, position_id=position_id)
    db.add(d)
    return d


# ───────── contabilidad del agente (sobre las posiciones del Trading Desk) ─────────
def agent_positions(db: Session, a: SxAgent, acc: TdAccount, status: str | None = None) -> list[TdPosition]:
    q = select(TdPosition).where(TdPosition.account_id == acc.id, TdPosition.strategy.like(f"SIX:{a.key}:%"))
    if status:
        q = q.where(TdPosition.status == status)
    return list(db.scalars(q.order_by(TdPosition.id)))


def ledger(db: Session, a: SxAgent, acc: TdAccount, with_quotes: bool = True) -> dict:
    alloc = acc.initial_capital * a.allocation_pct / 100
    closed = agent_positions(db, a, acc, "closed")
    opens = agent_positions(db, a, acc, "open")
    realized = sum(p.realized_pnl or 0 for p in closed)
    unreal, unpriced = 0.0, 0
    for p in opens:
        v = engine.position_value(db, acc, p) if with_quotes else {"unrealized": None}
        if v["unrealized"] is None:
            unpriced += 1
        else:
            unreal += v["unrealized"] - p.fees  # neto de la comisión de entrada ya pagada
    reserved = sum(p.reserved for p in opens)
    equity = alloc + realized + unreal
    return {"allocation": round(alloc, 2), "realized": round(realized, 2), "unrealized": round(unreal, 2), "equity": round(equity, 2),
            "reserved": round(reserved, 2), "available": round(max(0.0, alloc + realized - reserved - sum(p.fees for p in opens)), 2), "open": len(opens), "unpriced": unpriced,
            "fees": round(sum(p.fees for p in closed + opens), 2)}


# ───────── datos ─────────
def market_data(db: Session, symbol: str, tf: str, need: int) -> tuple[list[dict] | None, dict]:
    inst = mk.instruments(db).get(symbol)
    if not inst:
        return None, {"error": f"{symbol} no está en los instrumentos del Trading Desk"}
    try:
        res = mk.candles(inst, tf, max(need + 10, 200))
    except Exception as exc:  # noqa: BLE001
        return None, {"error": f"Error de datos: {exc}"}
    cs = res.get("candles") or []
    info = {"source": res.get("source"), "kind": res.get("kind"), "bars": len(cs)}
    if not cs:
        return None, info | {"error": res.get("error") or "Sin velas"}
    now = datetime.now(timezone.utc).timestamp()
    if cs[-1]["time"] + TF_S[tf] > now:  # la última vela aún se está formando: solo se usan velas cerradas
        cs = cs[:-1]
    if len(cs) < need:
        return None, info | {"error": f"Datos insuficientes: {len(cs)} velas cerradas de {need} necesarias"}
    age = now - (cs[-1]["time"] + TF_S[tf])
    info |= {"bar_time": cs[-1]["time"], "age_s": round(age)}
    if age > 2 * TF_S[tf] + 120:
        return None, info | {"error": f"Datos desactualizados: la última vela cerrada tiene {round(age / 60)} min de antigüedad"}
    q = mk.quote(inst)
    px = q.get("price")
    info |= {"price": px, "quote_kind": q.get("kind"), "quote_source": q.get("source")}
    if px is None:
        return None, info | {"error": "Sin precio actual: no se opera"}
    if abs(px / cs[-1]["close"] - 1) > MAX_DEVIATION:
        return None, info | {"error": f"Precio actual {px} se desvía más de un {MAX_DEVIATION * 100:.0f}% del último cierre {cs[-1]['close']}: dato anómalo"}
    return cs, info


# ───────── ciclo de un agente ─────────
def run_agent(db: Session, a: SxAgent, day_start_utc: datetime) -> None:
    acc = account_for(db, a)
    if not acc:
        log(db, a, "analyze", "error", f"No hay cuenta {a.account_kind} activa en el Trading Desk")
        return
    if a.status == "halted":
        return
    lg = ledger(db, a, acc)
    # freno de emergencia por agente
    if lg["unpriced"] == 0 and lg["allocation"] and (lg["allocation"] - lg["equity"]) / lg["allocation"] * 100 >= a.max_dd_pct:
        a.status, a.halt_reason = "halted", f"Drawdown de su asignación ≥ {a.max_dd_pct}%: detenido hasta que lo reactives"
        log(db, a, "halt", "info", a.halt_reason, data=lg)
        return
    st_ = dict(a.state or {})
    day = day_start_utc.date().isoformat()
    if st_.get("day") != day:
        st_["day"], st_["day_start_equity"] = day, lg["equity"]
    daily_loss = (st_["day_start_equity"] - lg["equity"]) / lg["allocation"] * 100 if lg["allocation"] else 0
    paused_today = daily_loss >= a.max_daily_loss_pct
    v = a.variants[a.variant_idx]
    tf, p = v["timeframe"], v["params"]
    need = st.warmup(a.family, p) + 2
    st_.setdefault("analyzing", {})
    for sym in a.symbols:
        cs, info = market_data(db, sym, tf, need)
        st_["analyzing"][sym] = {"at": datetime.utcnow().isoformat(timespec="seconds"), "timeframe": tf, **{k: info.get(k) for k in ("price", "source", "kind", "bar_time", "error")}}
        if cs is None:
            log(db, a, "analyze", "skipped", info["error"], sym, info)
            continue
        arr = st.prepare(cs, a.family, p)
        i = len(cs) - 1
        dec = st.decide(arr, i, a.family, p)
        vals = {k: (round(x, 6) if isinstance(x, float) else x) for k, x in dec["values"].items()}
        st_["analyzing"][sym]["signal"] = dec["entry"] or "ninguna"
        st_["analyzing"][sym]["values"] = vals
        _manage_open(db, a, acc, sym, dec, info, cs, p)
        _expire_limits(db, a, acc, sym, cs, tf)
        last_bar = (st_.get("last_bar") or {}).get(sym)
        if last_bar == info["bar_time"]:
            continue  # esta vela ya se evaluó para entradas: nunca dos entradas por la misma señal
        st_.setdefault("last_bar", {})[sym] = info["bar_time"]
        if not dec["entry"]:
            continue
        if paused_today:
            log(db, a, "skip", "skipped", f"Señal {dec['entry']} descartada: pérdida diaria del agente {daily_loss:.2f}% ≥ {a.max_daily_loss_pct}%", sym, {"values": vals})
            continue
        _enter(db, a, acc, sym, dec, info, vals, p, tf, day_start_utc)
    a.state = st_
    a.last_run_at = datetime.utcnow()


def _has_exposure(db: Session, a: SxAgent, acc: TdAccount, sym: str) -> bool:
    if db.scalar(select(TdPosition.id).where(TdPosition.account_id == acc.id, TdPosition.symbol == sym, TdPosition.status == "open",
                                              TdPosition.strategy.like(f"SIX:{a.key}:%"))):
        return True
    return bool(db.scalar(select(TdOrder.id).where(TdOrder.account_id == acc.id, TdOrder.symbol == sym, TdOrder.status == "pending",
                                                   TdOrder.strategy.like(f"SIX:{a.key}:%"))))


def _enter(db: Session, a: SxAgent, acc: TdAccount, sym: str, dec: dict, info: dict, vals: dict, p: dict, tf: str, day_start_utc: datetime) -> None:
    side = dec["entry"]
    if _has_exposure(db, a, acc, sym):
        log(db, a, "skip", "skipped", f"Señal {side} descartada: ya hay una posición u orden de {a.name} en {sym} (sin duplicados)", sym, {"values": vals})
        return
    lg = ledger(db, a, acc)
    if lg["open"] >= a.max_positions:
        log(db, a, "skip", "skipped", f"Señal {side} descartada: máximo de {a.max_positions} posiciones abiertas del agente", sym, {"values": vals})
        return
    entry = dec["limit"] if dec["order"] == "limit" else info["price"]
    atr = vals.get("atr")
    if not atr or atr <= 0:
        log(db, a, "skip", "skipped", "ATR no disponible: sin stop calculable", sym, {"values": vals})
        return
    sl, tp = st.levels(side, entry, atr, p, dec.get("target"))
    inst = mk.instruments(db).get(sym)
    fx, _ = mk.fx_rate(inst.ccy, acc.currency, db)
    if fx is None:
        log(db, a, "skip", "skipped", f"Sin tipo de cambio {inst.ccy}→{acc.currency}", sym)
        return
    risk_money = lg["equity"] * a.risk_pct / 100
    qty = risk_money / (abs(entry - sl) * fx)
    qty = min(qty, lg["available"] * 0.95 / (entry * fx), lg["allocation"] * 0.5 / (entry * fx))
    qty = math.floor(qty * 1e6) / 1e6
    if qty <= 0 or qty * entry * fx < 10:
        log(db, a, "skip", "skipped", f"Señal {side} descartada: capital disponible del agente insuficiente ({lg['available']:.2f} {acc.currency})", sym, {"ledger": lg})
        return
    data = {"values": vals, "price": info["price"], "source": info.get("source"), "kind": info.get("kind"), "bar_time": info.get("bar_time"),
            "entry": round(entry, 6), "sl": round(sl, 6), "tp": round(tp, 6) if tp else None, "qty": qty, "risk_money": round(risk_money, 2)}
    try:
        o = engine.place_order(db, acc, symbol=sym, side="buy" if side == "long" else "sell", otype=dec["order"], qty=qty,
                               limit_price=entry if dec["order"] == "limit" else None, sl=sl, tp=tp, strategy=sid(a), timeframe=tf,
                               note=f"[VISTAN SIX · {a.name}] {dec['reason']}", acknowledge_risk=True, day_start_utc=day_start_utc)
    except (engine.OrderError, engine.RiskBlocked) as exc:
        log(db, a, f"open_{side}", "rejected", f"El motor de paper trading rechazó la orden: {exc}", sym, data)
        return
    data["warnings"] = [w["text"] for w in o.warnings or [] if w.get("level") in ("warn", "block")]
    if o.status == "rejected":
        log(db, a, f"open_{side}", "rejected", f"Rechazada por el motor: {o.reason}", sym, data, order_id=o.id)
        return
    if o.position_id:
        db.add(TdJournal(position_id=o.position_id, entry_reason=dec["reason"], strategy=sid(a), analysis=f"Agente {a.name} · {tf} · valores {vals}"))
    log(db, a, f"open_{side}", "executed", f"{'Orden limitada' if o.status == 'pending' else 'Abierta'} {side.upper()} {qty:g} {sym}: {dec['reason']}", sym, data,
        order_id=o.id, position_id=o.position_id)


def _manage_open(db: Session, a: SxAgent, acc: TdAccount, sym: str, dec: dict, info: dict, cs: list[dict], p: dict) -> None:
    for pos in [x for x in agent_positions(db, a, acc, "open") if x.symbol == sym]:
        d = 1 if pos.side == "long" else -1
        opened_bars = sum(1 for c in cs if c["time"] >= pos.opened_at.replace(tzinfo=timezone.utc).timestamp())
        exit_sig = dec["exit_long"] if d == 1 else dec["exit_short"]
        if exit_sig or (p.get("max_bars") and opened_bars >= p["max_bars"]):
            why = "señal de salida de la estrategia" if exit_sig else f"salida por tiempo ({opened_bars} velas)"
            try:
                engine.close_position(db, acc, pos, reason="agent")
                log(db, a, "close", "executed", f"Cerrada {pos.side.upper()} {sym} por {why}: {pos.realized_pnl:+.2f} {acc.currency}", sym,
                    {"exit_price": pos.exit_price, "pnl": pos.realized_pnl}, position_id=pos.id)
                j = db.scalar(select(TdJournal).where(TdJournal.position_id == pos.id))
                if j:
                    j.exit_reason = why
            except engine.OrderError as exc:
                log(db, a, "close", "error", f"No se pudo cerrar: {exc}", sym, position_id=pos.id)
            continue
        trail = p.get("trail_atr")
        atr = dec["values"].get("atr")
        if trail and atr and info.get("price"):
            new_sl = info["price"] - d * trail * atr
            if pos.sl is None or (new_sl - pos.sl) * d > 0.25 * atr:  # solo se mueve a favor (nunca se aleja el stop)
                try:
                    old = pos.sl
                    engine.modify_position(pos, new_sl, pos.tp, info["price"])
                    log(db, a, "modify", "executed", f"Stop dinámico {sym}: {(f'{old:.6g}' if old is not None else '—')} → {new_sl:.6g}", sym, {"atr": atr}, position_id=pos.id)
                except engine.OrderError as exc:
                    log(db, a, "modify", "skipped", f"Stop no movido: {exc}", sym, position_id=pos.id)


def _expire_limits(db: Session, a: SxAgent, acc: TdAccount, sym: str, cs: list[dict], tf: str) -> None:
    for o in db.scalars(select(TdOrder).where(TdOrder.account_id == acc.id, TdOrder.symbol == sym, TdOrder.status == "pending",
                                              TdOrder.strategy.like(f"SIX:{a.key}:%"))):
        age_bars = (datetime.utcnow() - o.created_at).total_seconds() / TF_S[tf]
        if age_bars >= LIMIT_EXPIRY_BARS:
            engine.cancel_order(db, o)
            o.reason = f"Caducada tras {LIMIT_EXPIRY_BARS} velas sin ejecutarse (VISTAN SIX)"
            log(db, a, "cancel", "executed", o.reason, sym, order_id=o.id)


# ───────── evaluación y rotación (solo con evidencia) ─────────
def evaluate(db: Session, a: SxAgent, acc: TdAccount, strategy: str | None = None) -> dict:
    closed = [x for x in agent_positions(db, a, acc, "closed") if strategy is None or x.strategy == strategy]
    pnls = [x.realized_pnl or 0 for x in closed]
    return st.metrics(pnls, sum(x.fees for x in closed), acc.initial_capital * a.allocation_pct / 100, [x.risk_money for x in closed])


def maybe_rotate(db: Session, a: SxAgent, acc: TdAccount) -> None:
    """Solo agentes EXPERIMENTALES con varias variantes. Se rota únicamente si la variante actual acumula ≥ MIN_TRADES_ROTATE
    operaciones y su expectativa después de costes es negativa; se elige la siguiente variante sin evaluar o la mejor evaluada."""
    if a.account_kind != "experimental" or len(a.variants) < 2:
        return
    m = evaluate(db, a, acc, sid(a))
    if m["trades"] < MIN_TRADES_ROTATE or m["expectancy"] > 0:
        return
    if db.scalar(select(TdPosition.id).where(TdPosition.account_id == acc.id, TdPosition.status == "open", TdPosition.strategy == sid(a))):
        return  # no se cambia con posiciones abiertas de la variante actual
    old = sid(a)
    scores = []
    for i in range(len(a.variants)):
        if i == a.variant_idx:
            continue
        mi = evaluate(db, a, acc, sid_for(a, i))
        scores.append((mi["trades"] == 0, mi.get("expectancy") or 0, i))
    if not scores:
        return
    scores.sort(reverse=True)
    a.variant_idx = scores[0][2]
    st_ = dict(a.state or {})
    st_["rotations"] = [*st_.get("rotations", []), {"at": datetime.utcnow().isoformat(timespec="seconds"), "from": old, "to": sid(a),
                                                     "evidence": {k: m.get(k) for k in ("trades", "expectancy", "profit_factor", "t_stat")}}][-20:]
    st_["last_bar"] = {}
    a.state = st_
    log(db, a, "rotate", "info", f"Variante {old} retirada tras {m['trades']} operaciones con expectativa {m['expectancy']} después de costes; ahora {sid(a)}",
        data={"evidence": m})


def tick(db: Session, force: bool = False) -> dict:
    """Un ciclo de los seis agentes. Solo si el modo autónomo está activo (o forzado por ti) y sin kill switch."""
    from atlas.metabrain.governance import killed
    from atlas.services.preferences import get_prefs
    prefs = get_prefs(db)
    conf = {"autonomous": False, **(prefs.get("six") or {})}
    if killed(prefs):
        return {"ran": False, "reason": "Kill switch de VISTAN activo"}
    if not conf["autonomous"] and not force:
        return {"ran": False, "reason": "Modo autónomo desactivado"}
    engine.ensure_accounts(db)
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    ran = []
    for a in ensure_agents(db):
        if not a.enabled or a.status in ("halted", "paused"):
            continue
        a.status = "running"
        try:
            run_agent(db, a, day_start)
            acc = account_for(db, a)
            if acc:
                maybe_rotate(db, a, acc)
            a.last_error = None
        except Exception as exc:  # noqa: BLE001 - un agente con error no tumba a los demás
            a.last_error = f"{type(exc).__name__}: {exc}"[:500]
            log(db, a, "analyze", "error", a.last_error)
        if a.status == "running":
            a.status = "idle"
        db.flush()
        ran.append(a.key)
    engine.process(db)
    return {"ran": True, "agents": ran}


def due(db: Session) -> bool:
    from atlas.services.preferences import get_prefs
    conf = {"autonomous": False, "interval_min": 5, **(get_prefs(db).get("six") or {})}
    if not conf["autonomous"]:
        return False
    last = db.scalar(select(SxAgent.last_run_at).order_by(SxAgent.last_run_at.desc()).limit(1))
    return not last or datetime.utcnow() - last >= timedelta(minutes=max(1, int(conf["interval_min"])))


# ───────── validación histórica (dentro / fuera de muestra) ─────────
def validate(db: Session, a: SxAgent, symbol: str, variant_idx: int | None = None, bars: int = 1000):
    """Ejecuta la MISMA lógica sobre velas históricas reales del Trading Desk con los costes de su cuenta.
    70 % inicial = tramo de ajuste (in-sample); 30 % final = fuera de muestra. Los parámetros NO se optimizan aquí."""
    from atlas.models import SxValidation
    acc = account_for(db, a)
    idx = a.variant_idx if variant_idx is None else variant_idx
    v = a.variants[idx]
    inst = mk.instruments(db).get(symbol)
    if not inst:
        raise ValueError(f"{symbol} no está en el Trading Desk")
    res = mk.candles(inst, v["timeframe"], bars)
    cs = res.get("candles") or []
    now = datetime.now(timezone.utc).timestamp()
    if cs and cs[-1]["time"] + TF_S[v["timeframe"]] > now:
        cs = cs[:-1]
    if len(cs) < 300:
        raise ValueError(f"Datos históricos insuficientes: {len(cs)} velas (mínimo 300). {res.get('error') or ''}".strip())
    split = int(len(cs) * 0.7)
    trades = st.simulate(cs, a.family, v["params"], acc.commission_pct, acc.commission_fixed, acc.slippage_bps, 10_000.0, a.risk_pct)
    ins_t, oos_t = [t for t in trades if t["bar"] < split], [t for t in trades if t["bar"] >= split]
    m = lambda ts: st.metrics([t["pnl"] for t in ts], sum(t["fees"] for t in ts), 10_000.0, [t["risk"] for t in ts])  # noqa: E731
    out = {"in_sample": m(ins_t), "out_of_sample": m(oos_t), "bars": len(cs), "split_bar": split,
           "from": cs[0]["time"], "split_at": cs[split]["time"], "to": cs[-1]["time"], "source": res.get("source"), "kind": res.get("kind"),
           "costs": {"commission_pct": acc.commission_pct, "commission_fixed": acc.commission_fixed, "slippage_bps": acc.slippage_bps},
           "note": "Validación sobre datos históricos reales con la misma lógica y costes del agente. Fuera de muestra = último 30 % del "
                   "histórico, no usado para elegir parámetros. Resultados pasados no garantizan resultados futuros."}
    val = SxValidation(agent=a.key, strategy=sid_for(a, idx), symbol=symbol, timeframe=v["timeframe"], source=res.get("source"), result=out)
    db.add(val)
    log(db, a, "validate", "info", f"Validación {symbol} {v['timeframe']}: fuera de muestra {out['out_of_sample'].get('trades', 0)} operaciones, "
        f"veredicto {out['out_of_sample']['verdict']}", symbol, {"in": out["in_sample"].get("expectancy"), "oos": out["out_of_sample"].get("expectancy")})
    return val
