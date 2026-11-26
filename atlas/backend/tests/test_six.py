"""VISTAN SIX: agentes autónomos de PAPER TRADING sobre el motor existente del Trading Desk.
El mercado de estas pruebas lo fija la propia prueba (velas y precios controlados con el formato real del Trading Desk)."""

import math
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from atlas.desk import market as mk
from atlas.models import SxAgent, SxDecision, TdOrder, TdPosition
from atlas.six import runner, strategies


def make_candles(tf: str, n: int = 300, base: float = 100.0, wave: float = 0.0, now: float | None = None, stale_s: int = 0) -> list[dict]:
    step = mk.TF_SECONDS[tf]
    now = now or datetime.now(timezone.utc).timestamp()
    cur = int(now // step) * step - stale_s  # vela en formación (se descarta)
    out = []
    for k in range(n, -1, -1):
        t = cur - k * step
        c = base * (1 + wave * math.sin(k / 7) + wave * 0.6 * math.sin(k / 31) + wave * 0.3 * math.sin(k / 3.3))
        out.append({"time": t, "open": c, "high": c * 1.004, "low": c * 0.996, "close": c, "volume": 10})
    return out


@pytest.fixture()
def six(client, monkeypatch):
    m = {"bases": {"BTC/USDT": 50_000.0, "ETH/USDT": 3_000.0, "SOL/USDT": 150.0}, "n": 300, "stale_s": 0, "price": {}, "signal": {}, "calls": 0}

    def candles(inst, tf, limit=300):
        m["calls"] += 1
        return {"candles": make_candles(tf, m["n"], m["bases"][inst.symbol], stale_s=m["stale_s"]), "source": "test", "kind": "historical"}

    def quote(inst, ttl=None):
        p = m["price"].get(inst.symbol, m["bases"].get(inst.symbol))
        return {"symbol": inst.symbol, "price": p, "change_pct": 0, "volume": None, "ts": 1, "source": "test" if p else None,
                "kind": "realtime" if p else "none"}

    real_decide = strategies.decide

    def decide(a, i, family, p):
        d = real_decide(a, i, family, p)
        s = m["signal"]
        if s:
            d |= {"entry": s.get("entry"), "exit_long": s.get("exit_long", False), "exit_short": s.get("exit_short", False),
                  "order": s.get("order", "market"), "limit": s.get("limit"), "reason": "señal de prueba"}
            d["values"] = {**d["values"], "atr": s.get("atr", d["values"].get("atr") or 1.0)}
        return d

    monkeypatch.setattr(mk, "candles", candles)
    monkeypatch.setattr(mk, "quote", quote)
    monkeypatch.setattr(mk, "quotes", lambda insts: {i.symbol: quote(i) for i in insts})
    monkeypatch.setattr(runner.st, "decide", decide)
    monkeypatch.setattr(mk, "fx_rate", lambda frm, to, db=None: (1.0, "test") if frm != to or True else (1.0, ""))
    return m


def only(client, *keys):
    for a in client.get("/api/six/status").json()["agents"]:
        client.patch(f"/api/six/agents/{a['key']}", json={"enabled": a["key"] in keys, "symbols": ["BTC/USDT"]})


def activate(client):
    return client.post("/api/six/autonomy", json={"on": True, "confirm": "ACTIVAR"})


def six_positions(session, status=None):
    q = select(TdPosition).where(TdPosition.strategy.like("SIX:%"))
    if status:
        q = q.where(TdPosition.status == status)
    session.expire_all()
    return list(session.scalars(q))


def test_status_six_agents_two_accounts_and_rules(client, six):
    s = client.get("/api/six/status").json()
    assert len(s["agents"]) == 6
    assert {a["account"] for a in s["agents"]} == {"safe", "experimental"}
    assert s["accounts"]["safe"]["initial_capital"] == 100_000 and s["accounts"]["experimental"]["initial_capital"] == 100_000
    assert s["config"]["autonomous"] is False
    a = s["agents"][0]
    assert a["ledger"]["allocation"] == 30_000 and a["metrics"]["verdict"] == "sin_datos"
    # la suma de asignaciones por cuenta nunca supera el 100 %
    for kind in ("safe", "experimental"):
        assert sum(x["allocation_pct"] for x in s["agents"] if x["account"] == kind) <= 100


def test_autonomy_requires_explicit_confirmation_and_off_means_no_trades(client, six, session):
    six["signal"] = {"entry": "long"}
    assert client.post("/api/six/autonomy", json={"on": True}).status_code == 428
    r = runner.tick(session)
    assert r["ran"] is False and six_positions(session) == []
    assert activate(client).json()["autonomous"] is True


def test_entry_goes_through_paper_engine_with_costs(client, six, session):
    only(client, "orion")
    activate(client)
    six["signal"] = {"entry": "long", "atr": 500.0}
    r = client.post("/api/six/tick").json()
    assert r["ran"] is True
    ps = six_positions(session, "open")
    assert len(ps) == 1, [(d["symbol"], d["status"], d["reason"]) for d in client.get("/api/six/decisions").json()]
    p = ps[0]
    assert p.strategy.startswith("SIX:orion:ema_trend:1h") and p.side == "long" and p.data_kind == "realtime"
    assert p.entry_price > 50_000  # deslizamiento aplicado por el motor (compra más cara)
    assert p.fees > 0 and p.sl < p.entry_price and p.tp > p.entry_price
    o = session.scalar(select(TdOrder).where(TdOrder.position_id == p.id))
    assert "[VISTAN SIX" in o.note
    # riesgo: 0,5 % de la equity de su asignación (30 000 €) → ~150 € de riesgo hasta el stop
    assert 100 < p.qty * (p.entry_price - p.sl) <= 160
    d = client.get("/api/six/decisions", params={"agent": "orion", "status": "executed"}).json()
    assert d and d[0]["action"] == "open_long" and d[0]["data"]["source"] == "test"


def test_no_duplicate_orders_same_bar_or_same_symbol(client, six, session):
    only(client, "orion")
    activate(client)
    six["signal"] = {"entry": "long", "atr": 500.0}
    client.post("/api/six/tick")
    client.post("/api/six/tick")  # misma vela: no se reevalúa la entrada
    assert len(six_positions(session, "open")) == 1
    a = session.scalar(select(SxAgent).where(SxAgent.key == "orion"))
    a.state = {**a.state, "last_bar": {}}  # nueva vela simulada con la posición aún abierta
    session.commit()
    client.post("/api/six/tick")
    assert len(six_positions(session, "open")) == 1
    skipped = client.get("/api/six/decisions", params={"status": "skipped"}).json()
    assert any("sin duplicados" in d["reason"] for d in skipped)


def test_short_and_exit_by_signal_keeps_losing_trade(client, six, session):
    only(client, "nova")
    activate(client)
    six["signal"] = {"entry": "short", "atr": 500.0}
    client.post("/api/six/tick")
    p = six_positions(session, "open")[0]
    assert p.side == "short" and p.sl > p.entry_price
    six["price"]["BTC/USDT"] = 50_400.0  # el precio sube: el corto pierde
    six["signal"] = {"entry": None, "exit_short": True}
    client.post("/api/six/tick")
    closed = six_positions(session, "closed")
    assert len(closed) == 1 and closed[0].realized_pnl < 0 and closed[0].exit_reason == "agent"
    tr = client.get("/api/six/trades", params={"agent": "nova", "status": "closed"}).json()
    assert len(tr) == 1 and tr[0]["realized"] < 0  # las operaciones perdedoras se conservan
    s = client.get("/api/six/status").json()
    nova = next(x for x in s["agents"] if x["key"] == "nova")
    assert nova["metrics"]["trades"] == 1 and nova["metrics"]["net"] < 0
    assert any(x["strategy"].startswith("SIX:nova:") for x in s["strategies"])


def test_stop_loss_executed_by_engine(client, six, session):
    only(client, "orion")
    activate(client)
    six["signal"] = {"entry": "long", "atr": 500.0}
    client.post("/api/six/tick")
    p = six_positions(session, "open")[0]
    six["price"]["BTC/USDT"] = p.sl - 10
    six["signal"] = {"entry": None}
    client.post("/api/six/tick")
    c = six_positions(session, "closed")
    assert len(c) == 1 and c[0].exit_reason == "stop_loss" and c[0].realized_pnl < 0


def test_trailing_stop_only_moves_in_favour(client, six, session):
    only(client, "orion")  # trail_atr 2.5
    activate(client)
    six["signal"] = {"entry": "long", "atr": 500.0}
    client.post("/api/six/tick")
    p = six_positions(session, "open")[0]
    sl0 = p.sl
    six["signal"] = {"entry": None, "atr": 500.0}
    six["price"]["BTC/USDT"] = 51_800.0  # sube (sin tocar el TP de 4 ATR): el stop sube
    client.post("/api/six/tick")
    p = six_positions(session, "open")[0]
    assert p.sl > sl0
    sl1 = p.sl
    six["price"]["BTC/USDT"] = 51_300.0  # retrocede: el stop no baja
    client.post("/api/six/tick")
    assert six_positions(session, "open")[0].sl == sl1


def test_limit_orders_expire(client, six, session):
    only(client, "vega")
    activate(client)
    six["signal"] = {"entry": "long", "order": "limit", "limit": 49_000.0, "atr": 500.0}
    client.post("/api/six/tick")
    o = session.scalar(select(TdOrder).where(TdOrder.strategy.like("SIX:vega:%")))
    assert o.status == "pending" and o.type == "limit"
    o.created_at = datetime.utcnow() - timedelta(hours=4)
    session.commit()
    six["signal"] = {"entry": None}
    client.post("/api/six/tick")
    session.expire_all()
    o = session.get(TdOrder, o.id)
    assert o.status == "cancelled" and "Caducada" in o.reason


def test_insufficient_stale_and_anomalous_data_block_trading(client, six, session):
    only(client, "orion")
    activate(client)
    six["signal"] = {"entry": "long", "atr": 500.0}
    six["n"] = 30
    client.post("/api/six/tick")
    six["n"], six["stale_s"] = 300, 6 * 3600
    a = session.scalar(select(SxAgent).where(SxAgent.key == "orion"))
    client.post("/api/six/tick")
    six["stale_s"] = 0
    six["price"] = {"BTC/USDT": 70_000.0, "ETH/USDT": 9_000.0}
    client.post("/api/six/tick")
    six["price"] = {"BTC/USDT": None, "ETH/USDT": None}
    client.post("/api/six/tick")
    assert six_positions(session) == []
    reasons = " | ".join(d["reason"] for d in client.get("/api/six/decisions", params={"status": "skipped"}).json())
    assert "insuficientes" in reasons and "desactualizados" in reasons and "anómalo" in reasons and "Sin precio" in reasons
    session.refresh(a)
    assert a.state["analyzing"]["BTC/USDT"]["error"]


def test_kill_switch_and_emergency_stop(client, six, session):
    only(client, "orion")
    activate(client)
    client.post("/api/meta/governance/kill", json={"on": True})
    six["signal"] = {"entry": "long", "atr": 500.0}
    assert client.post("/api/six/tick").json()["ran"] is False
    client.post("/api/meta/governance/kill", json={"on": False})
    client.post("/api/six/tick")
    assert len(six_positions(session, "open")) == 1
    r = client.post("/api/six/emergency", json={"close_positions": True}).json()
    assert r["autonomous"] is False and r["closed"] == 1
    s = client.get("/api/six/status").json()
    assert all(a["status"] == "paused" for a in s["agents"])
    assert len(six_positions(session, "closed")) == 1  # se cierra, no se borra
    client.post("/api/six/agents/orion/resume")
    assert next(a for a in client.get("/api/six/status").json()["agents"] if a["key"] == "orion")["status"] == "idle"


def test_drawdown_halts_agent(client, six, session):
    only(client, "orion")
    activate(client)
    a = session.scalar(select(SxAgent).where(SxAgent.key == "orion"))
    a.max_dd_pct = 0.1  # umbral diminuto para provocar el freno
    session.commit()
    six["signal"] = {"entry": "long", "atr": 500.0}
    client.post("/api/six/tick")
    six["price"]["BTC/USDT"] = 49_800.0
    six["signal"] = {"entry": None}
    client.post("/api/six/tick")
    session.refresh(a)
    assert a.status == "halted" and "Drawdown" in a.halt_reason
    assert client.post("/api/six/tick").json()["agents"] == []  # detenido hasta que lo reactives


def test_safe_agents_limited_risk_and_symbols_validated(client, six):
    assert client.patch("/api/six/agents/orion", json={"risk_pct": 3}).status_code == 422
    assert client.patch("/api/six/agents/orion", json={"symbols": ["NOEXISTE/USDT"]}).status_code == 422
    assert client.patch("/api/six/agents/nova", json={"risk_pct": 3}).status_code == 200


def test_metrics_and_verdicts_need_sample():
    assert strategies.metrics([], 0, 30_000, [])["verdict"] == "sin_datos"
    assert strategies.metrics([10.0] * 12, 1, 30_000, [5] * 12)["verdict"] == "insuficiente"
    pn = [30.0, -10.0] * 30
    m = strategies.metrics(pn, 5, 30_000, [10] * 60)
    assert m["trades"] == 60 and m["win_rate"] == 50 and m["profit_factor"] == 3 and m["verdict"] == "ventaja"
    bad = strategies.metrics([10.0, -12.0] * 30, 5, 30_000, [10] * 60)
    assert bad["verdict"] == "sin_ventaja" and bad["expectancy"] < 0


def test_rotation_only_after_enough_trades(client, six, session):
    runner.ensure_agents(session)
    from atlas.desk import engine
    engine.ensure_accounts(session)
    a = session.scalar(select(SxAgent).where(SxAgent.key == "altair"))
    acc = runner.account_for(session, a)
    sid0 = runner.sid(a)

    def add(n):
        for _ in range(n):
            session.add(TdPosition(account_id=acc.id, symbol="BTC/USDT", side="long", qty=0.01, entry_price=100, status="closed",
                                   strategy=sid0, realized_pnl=-5.0, fees=1.0, reserved=0, risk_money=10, exit_reason="sl", closed_at=datetime.utcnow()))
        session.flush()

    add(5)
    runner.maybe_rotate(session, a, acc)
    assert runner.sid(a) == sid0  # pocas operaciones negativas: no se cambia
    add(15)
    runner.maybe_rotate(session, a, acc)
    assert runner.sid(a) != sid0 and a.state["rotations"][-1]["evidence"]["trades"] == 20
    assert session.scalar(select(SxDecision).where(SxDecision.action == "rotate"))
    # los agentes SAFE nunca rotan
    o = session.scalar(select(SxAgent).where(SxAgent.key == "orion"))
    runner.maybe_rotate(session, o, runner.account_for(session, o))
    assert o.variant_idx == 0


def test_validation_in_and_out_of_sample(client, six):
    six["signal"] = {}
    six["n"] = 800
    r = client.post("/api/six/agents/altair/validate", json={"symbol": "BTC/USDT"})
    assert r.status_code == 201
    v = r.json()["result"]
    assert v["bars"] == 800 and v["split_bar"] == 560 and v["source"] == "test"
    assert "in_sample" in v and "out_of_sample" in v and v["costs"]["slippage_bps"] == 2
    six["n"] = 100
    assert client.post("/api/six/agents/altair/validate", json={"symbol": "BTC/USDT"}).status_code == 422
    assert len(client.get("/api/six/validations").json()) == 1


def test_simulate_all_families_with_costs():
    cs = make_candles("1h", 1200, 100, wave=0.06)
    for fam, p in [("ema_trend", {"fast": 20, "slow": 50, "sl_atr": 2, "tp_atr": 4}), ("meanrev", {"period": 20, "k": 2, "rsi_low": 30, "rsi_high": 70, "sl_atr": 1.5}),
                   ("rsi_macd", {"sl_atr": 2, "tp_atr": 3}), ("breakout", {"n": 20, "exit_n": 10, "sl_atr": 2}),
                   ("momentum", {"n": 12, "thr": 1, "sl_atr": 2, "tp_atr": 3, "max_bars": 20}), ("ma_cross", {"fast": 10, "slow": 30, "sl_atr": 2, "tp_atr": 4})]:
        free = strategies.simulate(cs, fam, p, 0, 0, 0, 10_000, 1)
        cost = strategies.simulate(cs, fam, p, 0.05, 1, 2, 10_000, 1)
        assert len(free) == len(cost) > 0, fam
        assert sum(t["pnl"] for t in cost) < sum(t["pnl"] for t in free), fam  # los costes siempre restan


def test_autonomous_loop_due(client, six, session):
    assert runner.due(session) is False
    activate(client)
    session.expire_all()
    assert runner.due(session) is True
    client.put("/api/six/config", json={"interval_min": 30})
    client.post("/api/six/tick")
    session.expire_all()
    assert runner.due(session) is False
