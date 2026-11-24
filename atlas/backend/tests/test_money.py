import json

from atlas.finance.service import parse_money_command


def _events(r):
    return [json.loads(line) for line in r.text.splitlines() if line.strip()]


def test_parse_money():
    p = parse_money_command("He gastado 12,50 en comida")
    assert p["kind"] == "expense" and p["amount_cents"] == 1250 and p["category"] == "comida"
    p = parse_money_command("he cobrado 300€ de la nómina")
    assert p["kind"] == "income" and p["amount_cents"] == 30000 and p["category"] == "nómina"
    assert parse_money_command("he pagado 9.99 de spotify")["category"] == "suscripciones"
    assert parse_money_command("gasto 20 en algo raro")["category"] == "otros"
    assert parse_money_command("he comido arroz") is None
    assert parse_money_command("apúntame pagar la luz") is None


def test_finance_crud_summary_budget_alerts(client):
    r = client.post("/api/finance/transactions", json={"kind": "income", "amount_cents": 50000, "description": "nómina"})
    assert r.status_code == 201 and r.json()["category"] == "nómina"
    client.put("/api/finance/budgets/ocio", json={"monthly_cents": 5000})
    ev = _events(client.post("/api/assistant/chat", json={"text": "he gastado 45 en el cine"}))
    tx = next(e for e in ev if e["type"] == "finance")["transaction"]
    assert tx["amount_cents"] == 4500 and tx["category"] == "ocio"
    reply = "".join(e["text"] for e in ev if e["type"] == "delta")
    assert "90 %" in reply
    s = client.get("/api/finance/summary").json()
    assert s["income_cents"] == 50000 and s["expense_cents"] == 4500 and s["savings_rate"] == 91
    assert s["budgets"][0]["status"] == "warning" and s["by_category"][0]["category"] == "ocio"
    alerts = client.get("/api/dashboard").json()["alerts"]
    assert any("90 %" in a["text"] for a in alerts)
    # deshacer
    assert client.delete(f"/api/finance/transactions/{tx['id']}").status_code == 204
    assert client.get("/api/finance/summary").json()["expense_cents"] == 0
    assert client.post("/api/finance/transactions", json={"kind": "expense", "amount_cents": 0}).status_code == 422


def test_paper_trading_stats(client):
    assert client.get("/api/trading/stats").json()["overall"]["trades"] == 0
    bad = client.post("/api/trading/trades", json={"symbol": "eurusd", "side": "long", "quantity": 1, "entry_price": 100, "stop_loss": 105})
    assert bad.status_code == 422
    client.put("/api/trading/capital", json={"amount": 10000})
    a = client.post("/api/trading/trades", json={"symbol": "btc", "side": "long", "quantity": 2, "entry_price": 100,
                                                 "stop_loss": 95, "take_profit": 115, "strategy": "breakout"}).json()
    assert a["symbol"] == "BTC" and a["planned_rr"] == 3.0 and a["risk"] == 10
    b = client.post("/api/trading/trades", json={"symbol": "eth", "side": "short", "quantity": 1, "entry_price": 50,
                                                 "stop_loss": 55, "strategy": "reversal"}).json()
    c = client.post(f"/api/trading/trades/{a['id']}/close", json={"exit_price": 115}).json()
    assert c["pnl"] == 30 and c["r"] == 3.0
    d = client.post(f"/api/trading/trades/{b['id']}/close", json={"exit_price": 60, "mistakes": ["FOMO", " movi el stop "]}).json()
    assert d["pnl"] == -10 and d["r"] == -2.0
    assert client.post(f"/api/trading/trades/{b['id']}/close", json={"exit_price": 60}).status_code == 409
    s = client.get("/api/trading/stats").json()
    assert s["simulation"] is True and s["equity"] == 10020 and s["return_pct"] == 0.2
    o = s["overall"]
    assert o["win_rate"] == 50.0 and o["profit_factor"] == 3.0 and o["expectancy"] == 10 and o["avg_r"] == 0.5
    assert s["max_drawdown"] == 10 and [x["mistake"] for x in s["mistakes"]] == ["fomo", "movi el stop"]
    assert s["by_strategy"][0]["strategy"] == "breakout"
    # el trading simulado NO toca el dinero real
    assert client.get("/api/finance/summary").json()["balance_cents"] == 0


def test_health_ingest(client):
    tok = client.get("/api/health/setup").json()["token"]
    assert client.post("/api/health/ingest", json={"steps": 100}).status_code == 401
    assert client.post("/api/health/ingest", json={"steps": 100}, headers={"X-Vistan-Token": "mal"}).status_code == 401
    h = {"X-Vistan-Token": tok}
    r = client.post("/api/health/ingest", headers=h, json={"day": "2026-11-20", "steps": "8.432", "sleep_minutes": [200, 250],
                                                          "weight_kg": "75,6", "active_kcal": "512,4\n100"})
    assert r.status_code == 200, r.text
    assert set(r.json()["saved"]) == {"steps", "sleep_hours", "weight_kg", "active_kcal"}
    client.post("/api/health/ingest", headers=h, json={"day": "2026-11-20", "steps": 9000})
    days = client.get("/api/health/days?n=365").json()
    d = next(x for x in days if x["day"] == "2026-11-20")
    assert d["steps"] == 9000 and d["sleep_hours"] == 7.5 and d["weight_kg"] == 75.6 and d["active_kcal"] == 612.4
    assert client.post("/api/health/ingest", headers=h, json={"steps": -5}).status_code == 422
    assert client.post("/api/health/ingest", headers=h, json={}).status_code == 422
    # el peso pasa a las medidas corporales (Gimnasio/Nutrición)
    from atlas.db import session_scope
    from atlas.nutrition.service import latest_weight
    with session_scope() as db:
        assert latest_weight(db) == 75.6
    new = client.post("/api/health/token").json()["token"]
    assert new != tok and client.post("/api/health/ingest", headers=h, json={"steps": 1}).status_code == 401
