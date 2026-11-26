"""API de VISTAN SIX · LIVE EXPERIMENTATION (paper trading autónomo con el motor del Trading Desk)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.desk import engine
from atlas.desk import market as mk
from atlas.models import SxAgent, SxDecision, SxValidation, TdOrder, TdPosition
from atlas.six import runner, strategies
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs, set_prefs

router = APIRouter(prefix="/api/six", tags=["six"])
CONFIRM = "ACTIVAR"


def conf(db) -> dict:  # noqa: ANN001
    return {"autonomous": False, "interval_min": 5, "authorized_at": None, **(get_prefs(db).get("six") or {})}


def _agent(db, key: str) -> SxAgent:  # noqa: ANN001
    runner.ensure_agents(db)
    a = db.scalar(select(SxAgent).where(SxAgent.key == key))
    if not a:
        raise HTTPException(404, "Agente no encontrado")
    return a


def pos_dict(db, p: TdPosition, acc) -> dict:  # noqa: ANN001
    d = {"id": p.id, "symbol": p.symbol, "side": p.side, "qty": p.qty, "entry": p.entry_price, "sl": p.sl, "tp": p.tp, "status": p.status,
         "strategy": p.strategy, "timeframe": p.timeframe, "fees": round(p.fees, 2), "realized": p.realized_pnl, "exit": p.exit_price,
         "exit_reason": p.exit_reason, "opened_at": p.opened_at.isoformat(), "closed_at": p.closed_at.isoformat() if p.closed_at else None,
         "data_kind": p.data_kind, "account": acc.kind if acc else None}
    if p.status == "open" and acc:
        v = engine.position_value(db, acc, p)
        d |= {"price": v["price"], "unrealized": v["unrealized"]}
    return d


def _next_bar(a: SxAgent) -> int | None:
    """Cuándo cierra la próxima vela que evaluará (las entradas solo se deciden con velas cerradas)."""
    times = [v.get("bar_time") for v in ((a.state or {}).get("analyzing") or {}).values() if v.get("bar_time")]
    tf = mk.TF_SECONDS.get(a.variants[a.variant_idx]["timeframe"])
    return int(max(times) + 2 * tf) if times and tf else None


def agent_dict(db, a: SxAgent) -> dict:  # noqa: ANN001
    acc = runner.account_for(db, a)
    lg = runner.ledger(db, a, acc) if acc else None
    return {"key": a.key, "name": a.name, "account": a.account_kind, "family": a.family, "family_label": strategies.FAMILIES[a.family],
            "enabled": a.enabled, "status": a.status, "halt_reason": a.halt_reason, "symbols": a.symbols, "strategy": runner.sid(a),
            "variant": a.variants[a.variant_idx], "variants": [{"id": runner.sid_for(a, i), **v} for i, v in enumerate(a.variants)],
            "allocation_pct": a.allocation_pct, "risk_pct": a.risk_pct, "max_positions": a.max_positions, "max_dd_pct": a.max_dd_pct,
            "max_daily_loss_pct": a.max_daily_loss_pct, "ledger": lg, "analyzing": (a.state or {}).get("analyzing", {}),
            "rotations": (a.state or {}).get("rotations", []), "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
            "last_error": a.last_error, "metrics": runner.evaluate(db, a, acc) if acc else None,
            "last_decision": (lambda d: dec_dict(d) if d else None)(db.scalar(select(SxDecision).where(SxDecision.agent == a.key, SxDecision.action != "config").order_by(SxDecision.id.desc()).limit(1))),
            "next_bar_at": _next_bar(a),
            "metrics_current": runner.evaluate(db, a, acc, runner.sid(a)) if acc else None,
            "open": [pos_dict(db, p, acc) for p in runner.agent_positions(db, a, acc, "open")] if acc else []}


@router.get("/status")
def status(db: DB) -> dict:
    from atlas.metabrain.governance import killed
    engine.ensure_accounts(db)
    agents = runner.ensure_agents(db)
    db.commit()
    ag = [agent_dict(db, a) for a in agents]
    accounts = {}
    for kind in ("safe", "experimental"):
        acc = next((runner.account_for(db, a) for a in agents if a.account_kind == kind), None)
        if acc:
            stt = engine.account_state(db, acc)
            accounts[kind] = {"id": acc.id, "name": acc.name, "initial_capital": acc.initial_capital, "equity": stt["equity"], "cash": stt["cash"],
                              "return_pct": stt["return_pct"], "open_positions": stt["open_positions"], "commission_pct": acc.commission_pct,
                              "commission_fixed": acc.commission_fixed, "slippage_bps": acc.slippage_bps, "enforce_limits": acc.enforce_limits,
                              "max_risk_pct": acc.max_risk_pct, "max_exposure_pct": acc.max_exposure_pct}
    # rendimiento por estrategia (id independiente), sin mezclar agentes ni cuentas
    by_strategy: dict[str, list[TdPosition]] = defaultdict(list)
    for p in db.scalars(select(TdPosition).where(TdPosition.strategy.like("SIX:%"), TdPosition.status == "closed")):
        by_strategy[p.strategy].append(p)
    strat = []
    for sid_, ps in sorted(by_strategy.items()):
        key = sid_.split(":")[1]
        a = next((x for x in agents if x.key == key), None)
        acc = runner.account_for(db, a) if a else None
        strat.append({"strategy": sid_, "agent": key, **strategies.metrics([p.realized_pnl or 0 for p in ps], sum(p.fees for p in ps),
                                                                       acc.initial_capital * a.allocation_pct / 100 if a and acc else None, [p.risk_money for p in ps])})
    return {"config": conf(db), "kill": killed(get_prefs(db)), "agents": ag, "accounts": accounts, "strategies": strat,
            "leaderboard": sorted([{"key": x["key"], "name": x["name"], "account": x["account"], **(x["metrics"] or {}),
                                    "equity": (x["ledger"] or {}).get("equity"), "allocation": (x["ledger"] or {}).get("allocation")} for x in ag],
                                  key=lambda r: (-(r.get("net") or 0))),
            "recent": [dec_dict(d) for d in db.scalars(select(SxDecision).order_by(SxDecision.id.desc()).limit(40))],
            "rules": ["Todas las órdenes pasan por el motor de Paper Trading del Trading Desk (sin simulador paralelo ni bróker real).",
                      "Comisiones y deslizamiento: los configurados en cada cuenta.", "Solo velas cerradas reales; datos insuficientes, desactualizados o anómalos → no se opera.",
                      "Una posición u orden por agente y activo; cada vela se evalúa una vez.", "Las operaciones perdedoras nunca se borran.",
                      f"Una variante solo se cambia tras ≥ {runner.MIN_TRADES_ROTATE} operaciones con expectativa negativa."]}


def dec_dict(d: SxDecision) -> dict:
    return {"id": d.id, "agent": d.agent, "strategy": d.strategy, "symbol": d.symbol, "action": d.action, "status": d.status, "reason": d.reason,
            "data": d.data, "order_id": d.order_id, "position_id": d.position_id, "at": d.created_at.isoformat()}


class AutonomyIn(BaseModel):
    on: bool
    confirm: str | None = None


@router.post("/autonomy")
def autonomy(body: AutonomyIn, db: DB) -> dict:
    """Activación única: a partir de aquí los agentes operan en PAPER TRADING sin pedir permiso por cada operación simulada."""
    c = conf(db)
    if body.on and (body.confirm or "").strip().upper() != CONFIRM:
        raise HTTPException(428, f"Para activar el modo autónomo escribe {CONFIRM}. Solo opera con dinero virtual en el Trading Desk.")
    c["autonomous"] = body.on
    if body.on:
        c["authorized_at"] = datetime.utcnow().isoformat(timespec="seconds")
    set_prefs(db, {"six": c})
    log_activity(db, "trading", "six", "[SIMULADA] VISTAN SIX: modo autónomo " + ("ACTIVADO" if body.on else "desactivado"))
    db.commit()
    return c


class ConfigIn(BaseModel):
    interval_min: int = Field(ge=1, le=240)


@router.put("/config")
def config(body: ConfigIn, db: DB) -> dict:
    c = conf(db) | {"interval_min": body.interval_min}
    set_prefs(db, {"six": c})
    db.commit()
    return c


@router.post("/tick")
async def tick_now(db: DB) -> dict:
    """Ejecuta un ciclo ahora (lo pides tú). Respeta el kill switch."""
    r = await run_in_threadpool(runner.tick, db, True)
    db.commit()
    return r


class EmergencyIn(BaseModel):
    close_positions: bool = False


@router.post("/emergency")
def emergency(body: EmergencyIn, db: DB) -> dict:
    """Parada de emergencia: desactiva la autonomía y pausa a los seis; opcionalmente cancela sus órdenes y cierra sus posiciones."""
    c = conf(db) | {"autonomous": False}
    set_prefs(db, {"six": c})
    closed, cancelled, errors = 0, 0, []
    for a in runner.ensure_agents(db):
        a.status, a.halt_reason = "paused", "Parada de emergencia"
        acc = runner.account_for(db, a)
        if not acc or not body.close_positions:
            continue
        for o in db.scalars(select(TdOrder).where(TdOrder.account_id == acc.id, TdOrder.status == "pending", TdOrder.strategy.like(f"SIX:{a.key}:%"))):
            engine.cancel_order(db, o)
            o.reason = "Parada de emergencia de VISTAN SIX"
            cancelled += 1
        for p in runner.agent_positions(db, a, acc, "open"):
            try:
                engine.close_position(db, acc, p, reason="emergency")
                closed += 1
            except engine.OrderError as exc:
                errors.append(f"{p.symbol}: {exc}")
        runner.log(db, a, "halt", "info", f"Parada de emergencia: {closed} posiciones cerradas, {cancelled} órdenes canceladas")
    log_activity(db, "trading", "six", f"[SIMULADA] VISTAN SIX: parada de emergencia ({closed} cerradas, {cancelled} canceladas)")
    db.commit()
    return {"autonomous": False, "closed": closed, "cancelled": cancelled, "errors": errors}


class AgentPatch(BaseModel):
    enabled: bool | None = None
    symbols: list[str] | None = Field(default=None, max_length=10)
    risk_pct: float | None = Field(default=None, gt=0, le=5)
    max_positions: int | None = Field(default=None, ge=1, le=10)


@router.patch("/agents/{key}")
def patch_agent(key: str, body: AgentPatch, db: DB) -> dict:
    a = _agent(db, key)
    ch = body.model_dump(exclude_unset=True)
    if "symbols" in ch:
        insts = mk.instruments(db)
        bad = [s for s in ch["symbols"] if s not in insts]
        if bad or not ch["symbols"]:
            raise HTTPException(422, f"Activos no disponibles en el Trading Desk: {', '.join(bad) or '(ninguno)'}")
    if a.account_kind == "safe" and ch.get("risk_pct", 0) > 1:
        raise HTTPException(422, "Los agentes de la SAFE ACCOUNT no pueden arriesgar más de un 1 % por operación")
    for k, v in ch.items():
        setattr(a, k, v)
    runner.log(db, a, "config", "info", f"Configuración cambiada por ti: {ch}")
    db.commit()
    return agent_dict(db, a)


@router.post("/agents/{key}/resume")
def resume(key: str, db: DB) -> dict:
    a = _agent(db, key)
    a.status, a.halt_reason = "idle", None
    runner.log(db, a, "config", "info", "Reactivado por ti")
    db.commit()
    return agent_dict(db, a)


@router.post("/agents/{key}/pause")
def pause(key: str, db: DB) -> dict:
    a = _agent(db, key)
    a.status, a.halt_reason = "paused", "Pausado por ti"
    db.commit()
    return agent_dict(db, a)


@router.get("/decisions")
def decisions(db: DB, agent: str | None = None, status: str | None = None, limit: int = 200) -> list[dict]:
    q = select(SxDecision).order_by(SxDecision.id.desc()).limit(min(limit, 1000))
    if agent:
        q = q.where(SxDecision.agent == agent)
    if status:
        q = q.where(SxDecision.status == status)
    return [dec_dict(d) for d in db.scalars(q)]


@router.get("/trades")
def trades(db: DB, agent: str | None = None, strategy: str | None = None, status: str | None = None) -> list[dict]:
    q = select(TdPosition).where(TdPosition.strategy.like(f"SIX:{agent}:%" if agent else "SIX:%")).order_by(TdPosition.id.desc()).limit(500)
    if strategy:
        q = q.where(TdPosition.strategy == strategy)
    if status:
        q = q.where(TdPosition.status == status)
    accs = {a.account_kind: runner.account_for(db, a) for a in runner.ensure_agents(db)}
    by_id = {x.id: x for x in accs.values() if x}
    return [pos_dict(db, p, by_id.get(p.account_id)) for p in db.scalars(q)]


class ValidateIn(BaseModel):
    symbol: str = Field(min_length=2, max_length=32)
    variant_idx: int | None = Field(default=None, ge=0, le=10)


@router.post("/agents/{key}/validate", status_code=201)
async def validate(key: str, body: ValidateIn, db: DB) -> dict:
    engine.ensure_accounts(db)
    a = _agent(db, key)
    try:
        v = await run_in_threadpool(runner.validate, db, a, body.symbol, body.variant_idx)
    except (ValueError, mk.DataError) as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return {"id": v.id, "agent": v.agent, "strategy": v.strategy, "symbol": v.symbol, "timeframe": v.timeframe, "result": v.result, "at": v.created_at.isoformat()}


@router.get("/validations")
def validations(db: DB, agent: str | None = None) -> list[dict]:
    q = select(SxValidation).order_by(SxValidation.id.desc()).limit(100)
    if agent:
        q = q.where(SxValidation.agent == agent)
    return [{"id": v.id, "agent": v.agent, "strategy": v.strategy, "symbol": v.symbol, "timeframe": v.timeframe, "result": v.result,
             "at": v.created_at.isoformat()} for v in db.scalars(q)]


@router.get("/agents/{key}/insights")
def insights(key: str, db: DB) -> dict:
    """Análisis de sus propios resultados (reglas sobre operaciones reales del simulador; sin conclusiones con muestras pequeñas)."""
    a = _agent(db, key)
    acc = runner.account_for(db, a)
    closed = runner.agent_positions(db, a, acc, "closed") if acc else []
    groups = {}
    for label, fn in (("lado", lambda p: p.side), ("activo", lambda p: p.symbol), ("salida", lambda p: p.exit_reason or "?"), ("estrategia", lambda p: p.strategy)):
        g: dict[str, list[float]] = defaultdict(list)
        for p in closed:
            g[fn(p)].append(p.realized_pnl or 0)
        groups[label] = {k: {"trades": len(v), "net": round(sum(v), 2), "expectancy": round(sum(v) / len(v), 2)} for k, v in g.items()}
    notes = []
    for label, g in groups.items():
        for k, m in g.items():
            if m["trades"] >= 15 and m["expectancy"] < 0:
                notes.append(f"{label} «{k}»: expectativa negativa ({m['expectancy']}) en {m['trades']} operaciones")
    hold = [(p.closed_at - p.opened_at).total_seconds() / 3600 for p in closed if p.closed_at]
    if not notes:
        notes.append("Sin patrones con muestra suficiente (≥ 15 operaciones por grupo) todavía." if len(closed) < 60 else "Ningún grupo con expectativa negativa significativa.")
    return {"groups": groups, "avg_hold_h": round(sum(hold) / len(hold), 2) if hold else None, "notes": notes, "trades": len(closed)}
