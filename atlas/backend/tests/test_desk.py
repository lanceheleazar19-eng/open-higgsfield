"""Trading Desk (PAPER TRADING): motor de órdenes, cuentas independientes, riesgo, estadísticas y diario.
Los precios de estas pruebas los fija la propia prueba (mercado simulado controlado)."""

import pytest

from atlas.desk import backtest, indicators
from atlas.desk import market as mk


@pytest.fixture()
def market(client, monkeypatch):
    prices: dict[str, float | None] = {"BTC/USDT": 50_000.0, "AAPL": 200.0, "EUR/USD": 1.25}

    def quote(inst, ttl=None):
        p = prices.get(inst.symbol)
        return {"symbol": inst.symbol, "price": p, "change_pct": 0.0, "volume": None, "ts": 1,
                "source": "test" if p is not None else None, "kind": "realtime" if p is not None else "none"}

    monkeypatch.setattr(mk, "quote", quote)
    monkeypatch.setattr(mk, "quotes", lambda insts: {i.symbol: quote(i) for i in insts})
    return prices


def accounts(client):
    accs = client.get("/api/desk/accounts").json()
    return {a["kind"]: a for a in accs if a["active"]}


def order(client, acc, **kw):
    body = {"account_id": acc["id"], "symbol": "BTC/USDT", "side": "buy", "type": "market", "qty": 0.1} | kw
    return client.post("/api/desk/orders", json=body)


def state(client, acc):
    return client.get("/api/desk/state", params={"account_id": acc["id"]}).json()


def test_two_independent_accounts_with_virtual_capital(client, market):
    a = accounts(client)
    assert set(a) == {"safe", "experimental"}
    assert a["safe"]["initial_capital"] == 100_000 and a["safe"]["simulated"] is True
    assert a["safe"]["enforce_limits"] is True and a["experimental"]["enforce_limits"] is False
    r = order(client, a["experimental"], acknowledge_risk=True)
    assert r.status_code == 201 and r.json()["status"] == "filled"
    s_safe, s_exp = state(client, a["safe"]), state(client, a["experimental"])
    assert s_safe["cash"] == 100_000 and s_safe["open_positions"] == 0
    assert s_exp["open_positions"] == 1 and s_exp["cash"] < 100_000
    assert s_exp["label"].startswith("SIMULACIÓN")


def test_market_order_fills_with_slippage_fees_and_fx(client, market):
    a = accounts(client)["experimental"]
    r = order(client, a, symbol="AAPL", qty=10, sl=190, tp=230)
    assert r.status_code == 201
    o = r.json()
    # deslizamiento de 2 bps en contra: 200 * 1.0002
    assert o["fill_price"] == pytest.approx(200.04)
    st = state(client, a)
    # nominal en EUR: 200.04 * 10 / 1.25 = 1600.32; comisión 1 + 0.05%
    notional = 200.04 * 10 / 1.25
    fee = 1 + notional * 0.0005
    assert st["cash"] == pytest.approx(100_000 - notional - fee, abs=0.01)
    assert st["used"] == pytest.approx(notional, abs=0.01)
    pos = st["positions"][0]
    assert pos["side"] == "long" and pos["sl"] == 190 and pos["tp"] == 230
    # P&L no realizado a precio actual 200 (en EUR)
    assert pos["unrealized"] == pytest.approx((200 - 200.04) * 10 / 1.25, abs=0.01)


def test_no_price_means_rejected_not_invented(client, market):
    market["BTC/USDT"] = None
    a = accounts(client)["experimental"]
    o = order(client, a, acknowledge_risk=True).json()
    assert o["status"] == "rejected" and "Sin precio" in o["reason"]
    assert state(client, a)["cash"] == 100_000


def test_limit_and_stop_wait_for_price(client, market):
    a = accounts(client)["experimental"]
    lim = order(client, a, type="limit", limit_price=48_000, sl=47_000, acknowledge_risk=True).json()
    stp = order(client, a, type="stop", stop_price=52_000, sl=51_000, acknowledge_risk=True).json()
    assert lim["status"] == "pending" and stp["status"] == "pending"
    client.post("/api/desk/process")
    assert len(state(client, a)["pending"]) == 2  # 50.000: ninguna condición cumplida
    market["BTC/USDT"] = 47_900.0
    ev = client.post("/api/desk/process").json()["events"]
    assert [e["type"] for e in ev] == ["fill"]
    filled = [o for o in client.get("/api/desk/orders", params={"account_id": a["id"], "status": "filled"}).json()]
    assert filled[0]["fill_price"] == 47_900.0  # al precio (mejor que el límite)
    market["BTC/USDT"] = 52_100.0
    client.post("/api/desk/process")
    st = state(client, a)
    assert st["pending"] == [] and st["open_positions"] == 2
    stop_fill = client.get("/api/desk/orders", params={"account_id": a["id"], "status": "filled"}).json()[0]
    assert stop_fill["fill_price"] == pytest.approx(52_100 * 1.0002)


def test_stop_loss_and_take_profit_close_automatically(client, market):
    a = accounts(client)["experimental"]
    order(client, a, qty=0.2, sl=49_000, tp=53_000)
    order(client, a, side="sell", qty=0.1, sl=51_000, tp=48_000)
    market["BTC/USDT"] = 53_500.0  # TP de la larga y SL de la corta
    ev = client.post("/api/desk/process").json()["events"]
    assert sorted(e["type"] for e in ev) == ["stop_loss", "take_profit"]
    closed = client.get("/api/desk/positions", params={"account_id": a["id"]}).json()
    by = {p["side"]: p for p in closed}
    assert by["long"]["realized_pnl"] > 0 and by["long"]["exit_reason"] == "take_profit"
    assert by["short"]["realized_pnl"] < 0 and by["short"]["exit_reason"] == "stop_loss"
    st = state(client, a)
    assert st["open_positions"] == 0
    assert st["cash"] == pytest.approx(100_000 + by["long"]["realized_pnl"] + by["short"]["realized_pnl"], abs=0.02)


def test_risk_rules_safe_blocks_experimental_warns(client, market):
    a = accounts(client)
    # SAFE: exige stop loss → rechazada y registrada
    o = order(client, a["safe"], qty=0.1).json()
    assert o["status"] == "rejected" and "stop loss" in o["reason"]
    # SAFE: riesgo 1 BTC con stop a 5.000 (≈4% del capital) > 1% → rechazada
    o = order(client, a["safe"], qty=1, sl=45_000).json()
    assert o["status"] == "rejected" and "Riesgo" in o["reason"]
    # SAFE: dentro de los límites → ejecutada
    pre = client.post("/api/desk/orders/preview", json={"account_id": a["safe"]["id"], "symbol": "BTC/USDT", "side": "buy",
                                                         "type": "market", "qty": 0.1, "sl": 49_000, "tp": 52_000}).json()
    assert pre["rr"] == 2.0 and pre["risk_pct"] < 1 and pre["suggested_qty"] > 0 and not pre["blocking"]
    assert order(client, a["safe"], qty=0.1, sl=49_000, tp=52_000).json()["status"] == "filled"
    # EXPERIMENTAL: sin stop → pide confirmación (409) y no registra nada hasta confirmar
    r = order(client, a["experimental"], qty=0.1)
    assert r.status_code == 409 and r.json()["detail"]["needs_ack"] is True
    assert client.get("/api/desk/orders", params={"account_id": a["experimental"]["id"]}).json() == []
    assert order(client, a["experimental"], qty=0.1, acknowledge_risk=True).json()["status"] == "filled"
    # Saldo insuficiente → rechazada
    o = order(client, a["experimental"], qty=100, acknowledge_risk=True).json()
    assert o["status"] == "rejected" and "insuficiente" in o["reason"]
    # SL en el lado equivocado → rechazada
    o = order(client, a["experimental"], qty=0.1, sl=55_000, acknowledge_risk=True).json()
    assert o["status"] == "rejected" and "stop loss" in o["reason"]


def test_partial_close_modify_and_analytics(client, market):
    a = accounts(client)["experimental"]
    empty = client.get("/api/desk/analytics", params={"account_id": a["id"]}).json()
    assert empty["trades"] == 0 and empty["win_rate"] is None and empty["profit_factor"] is None
    pid = order(client, a, qty=0.4, sl=48_000).json()["position_id"]
    assert client.patch(f"/api/desk/positions/{pid}", json={"sl": 49_500, "tp": 60_000}).status_code == 200
    assert client.patch(f"/api/desk/positions/{pid}", json={"sl": 51_000}).status_code == 422
    market["BTC/USDT"] = 51_000.0
    part = client.post(f"/api/desk/positions/{pid}/close", json={"qty": 0.1}).json()
    assert part["qty"] == 0.1 and part["status"] == "closed" and part["realized_pnl"] > 0
    market["BTC/USDT"] = 49_800.0
    rest = client.post(f"/api/desk/positions/{pid}/close", json={}).json()
    assert rest["qty"] == pytest.approx(0.3) and rest["realized_pnl"] < 0
    st = client.get("/api/desk/analytics", params={"account_id": a["id"]}).json()
    assert st["trades"] == 2 and st["wins"] == 1 and st["losses"] == 1 and st["win_rate"] == 50.0
    assert st["net"] == pytest.approx(part["realized_pnl"] + rest["realized_pnl"], abs=0.01)
    assert st["profit_factor"] == pytest.approx(part["realized_pnl"] / -rest["realized_pnl"], abs=0.01)
    assert st["by_symbol"][0]["key"] == "BTC/USDT" and len(st["curve"]) == 2
    assert client.get("/api/desk/positions", params={"account_id": a["id"], "result": "win"}).json()[0]["id"] == part["id"]


def test_journal_remember_and_patterns(client, market):
    a = accounts(client)["experimental"]
    pid = order(client, a, qty=0.1, acknowledge_risk=True).json()["position_id"]
    market["BTC/USDT"] = 49_000.0
    client.post(f"/api/desk/positions/{pid}/close", json={})
    r = client.put(f"/api/desk/journal/{pid}", json={"entry_reason": "Ruptura", "strategy": "breakout", "emotion": "ansiedad",
                                                     "mistakes": ["sin stop", "FOMO"], "lessons": "Poner siempre stop", "remember": True})
    assert r.status_code == 200 and r.json()["remembered"] is True
    mem = client.get("/api/memory").json()
    assert any("Poner siempre stop" in m["content"] for m in (mem if isinstance(mem, list) else mem.get("items", [])))
    pat = client.get("/api/desk/patterns", params={"account_id": a["id"]}).json()
    assert pat["closed"] == 1 and pat["journaled"] == 1 and pat["no_stop"] == 1
    assert any("sin stop" in f or "stop loss" in f for f in pat["findings"])
    png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    assert client.post(f"/api/desk/journal/{pid}/image", json={"data_url": png}).status_code == 200
    assert client.get(f"/api/desk/journal/{pid}/image").content.startswith(b"\x89PNG")
    assert client.post(f"/api/desk/journal/{pid}/image", json={"data_url": "data:text/html;base64,PGI+"}).status_code == 422


def test_new_account_with_custom_capital_archives_old(client, market):
    a = accounts(client)["experimental"]
    order(client, a, qty=0.1, acknowledge_risk=True)
    assert client.post("/api/desk/accounts", json={"kind": "experimental", "capital": 25_000}).status_code == 409
    pid = state(client, a)["positions"][0]["id"]
    client.post(f"/api/desk/positions/{pid}/close", json={})
    r = client.post("/api/desk/accounts", json={"kind": "experimental", "capital": 25_000})
    assert r.status_code == 201
    new = accounts(client)["experimental"]
    assert new["initial_capital"] == 25_000 and new["id"] != a["id"]
    assert state(client, new)["cash"] == 25_000
    old = [x for x in client.get("/api/desk/accounts").json() if x["id"] == a["id"]][0]
    assert old["active"] is False  # historial conservado
    assert len(client.get("/api/desk/positions", params={"account_id": a["id"]}).json()) == 1


def test_providers_without_keys_and_no_market_data(client):
    prov = {p["id"]: p for p in client.get("/api/desk/providers").json()}
    assert prov["twelvedata"]["state"] == "sin clave" and prov["binance"]["needs_key"] is False
    assert client.put("/api/desk/providers/twelvedata/key", json={"key": "demo-key-123"}).status_code == 200
    assert {p["id"]: p for p in client.get("/api/desk/providers").json()}["twelvedata"]["configured"] is True
    assert client.delete("/api/desk/providers/twelvedata/key").status_code == 200
    assert client.get("/api/desk/news").json()["note"]
    assert client.get("/api/desk/macro").json()["series"] == []


def test_indicators_and_backtest_math():
    assert indicators.sma([1, 2, 3, 4], 2) == [None, 1.5, 2.5, 3.5]
    assert indicators.rsi([float(i) for i in range(30)])[-1] == 100.0
    e = indicators.ema([1.0] * 10, 3)
    assert e[2] == 1.0 and e[-1] == 1.0
    bb = indicators.bollinger([2.0] * 25, 20)
    assert bb["upper"][-1] == bb["lower"][-1] == 2.0
    c = [{"time": i * 86400, "open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100.5 + i, "volume": 10} for i in range(60)]
    r = backtest.run(c, "buy_hold", capital=1000, commission_pct=0, slippage_bps=0)
    assert r["open_at_end"] is True and r["return_pct"] == pytest.approx((159.5 / 101 - 1) * 100, abs=0.1)
    assert "NO garantizan" in r["warning"]
    with pytest.raises(ValueError):
        backtest.run(c[:10], "sma_cross")


class _Resp:
    def __init__(self, status=200, js=None, text=""):
        self.status_code, self._js, self.text = status, js, text

    def json(self):
        return self._js


def test_provider_parsers_with_real_formats(client, monkeypatch):
    """Formatos reales de respuesta de Binance, Stooq y Twelve Data (sin red)."""
    calls = []

    def fake_get(url, params=None, timeout=None, headers=None):
        calls.append(url)
        if url.endswith("/api/v3/ticker/24hr"):
            return _Resp(js=[{"symbol": "BTCUSDT", "lastPrice": "64000.5", "priceChangePercent": "-1.25", "quoteVolume": "123.4", "closeTime": 1700000000000}])
        if url.endswith("/api/v3/klines"):
            return _Resp(js=[[1700000000000, "1", "2", "0.5", "1.5", "10", 0], [1700000060000, "1.5", "2.5", "1", "2", "11", 0]])
        if "stooq.com/q/l/" in url:
            return _Resp(text="Symbol,Date,Time,Open,High,Low,Close,Volume\nAAPL.US,2026-11-24,22:00:09,190,195,189,194,1000\n^SPX,N/D,N/D,N/D,N/D,N/D,N/D,N/D\n")
        if "twelvedata.com/time_series" in url:
            return _Resp(js={"status": "ok", "values": [{"datetime": "2026-11-24 10:05:00", "open": "2", "high": "3", "low": "1", "close": "2.5", "volume": "5"},
                                                        {"datetime": "2026-11-24 10:00:00", "open": "1", "high": "2", "low": "1", "close": "2", "volume": "4"}]})
        if "twelvedata.com/quote" in url:
            return _Resp(js={"status": "error", "code": 429, "message": "You have run out of API credits"})
        return _Resp(status=404, js={})

    monkeypatch.setattr(mk.httpx, "get", fake_get)
    mk.clear_cache()
    ins = mk.instruments()
    q = mk.quotes([ins["BTC/USDT"], ins["AAPL"], ins["SPX"]])
    assert q["BTC/USDT"]["price"] == 64000.5 and q["BTC/USDT"]["kind"] == "realtime" and q["BTC/USDT"]["source"] == "binance"
    assert q["AAPL"]["price"] == 194.0 and q["AAPL"]["kind"] == "delayed" and q["AAPL"]["change_pct"] == pytest.approx(2.105, abs=0.01)
    assert q["SPX"]["price"] is None and q["SPX"]["kind"] == "none"  # N/D: no se inventa
    c = mk.candles(ins["BTC/USDT"], "1m", 100)
    assert c["source"] == "binance" and [k["close"] for k in c["candles"]] == [1.5, 2.0]
    nd = mk.candles(ins["AAPL"], "5m", 100)
    assert nd["candles"] == [] and "Twelve Data" in nd["error"]
    from atlas.integrations.secrets import set_secret
    set_secret("twelvedata_api_key", "k")
    mk.clear_cache()
    td = mk.candles(ins["AAPL"], "5m", 100)
    assert td["source"] == "twelvedata" and [k["close"] for k in td["candles"]] == [2.0, 2.5]  # orden cronológico
    with pytest.raises(mk.DataError, match="credits"):
        mk.td_quote("AAPL")
    st = {p["id"]: p for p in mk.provider_status()}
    assert st["twelvedata"]["last_error"] and st["binance"]["state"] == "conectado"


def test_tutor_uses_real_context_and_never_trades(client, market, ollama):
    a = accounts(client)["experimental"]
    order(client, a, qty=0.1, sl=49_000, tp=52_000)
    ollama.reply_chunks = ["Tu operación ", "arriesga un 0,1 %."]
    r = client.post("/api/desk/tutor", json={"question": "¿Estoy respetando mi gestión del riesgo?", "account_id": a["id"], "symbol": "BTC/USDT"})
    assert r.status_code == 200 and r.json()["answer"] == "Tu operación arriesga un 0,1 %."
    req = ollama.requests[-1]
    sys = " ".join(m["content"] for m in req["messages"] if m["role"] == "system")
    assert "PAPER TRADING" in sys and "posiciones_abiertas" in sys and "49000" in sys and "NUNCA presentes una predicción" in sys
    assert state(client, a)["open_positions"] == 1  # el tutor no opera
