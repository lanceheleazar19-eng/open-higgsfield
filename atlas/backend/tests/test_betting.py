"""Paper Betting: reglas de liquidación, combinadas, bankroll ficticio, modelos, calibración y backtesting sin
mirar al futuro. Los datos de partidos de estas pruebas son sintéticos y los fija la propia prueba."""

import random
from datetime import datetime, timedelta

import pytest

from atlas.bets import analysis, models as md, providers as pv
from atlas.bets import markets as mk
from atlas.models import BtEvent


def S(sport, market, pick, result, line=None, opp=None, status="finished"):
    return mk.settle_leg(sport, market, pick, line, opp, status, result)


def test_settlement_rules():
    r = {"home": 2, "away": 2}
    assert S("football", "1x2", "draw", r) == "won" and S("football", "1x2", "home", r) == "lost"
    assert S("football", "double_chance", "1X", r) == "won" and S("football", "double_chance", "12", r) == "lost"
    assert S("football", "total", "over", r, 3.5) == "won" and S("football", "total", "over", r, 4) == "void"
    assert S("football", "btts", "yes", r) == "won"
    assert S("football", "handicap", "home", {"home": 2, "away": 1}, -1) == "void"
    assert S("football", "handicap", "home", {"home": 3, "away": 1}, -1.5) == "won"
    assert S("football", "handicap", "away", {"home": 1, "away": 0}, -1.5) == "won"
    assert S("football", "correct_score", "2-2", r) == "won"
    assert S("basketball", "moneyline", "away", {"home": 99, "away": 104}) == "won"
    assert S("tennis", "sets_exact", "2-1", {"sets": [[6, 4], [3, 6], [7, 5]]}) == "won"
    assert S("tennis", "moneyline", "home", {"home_sets": 0, "away_sets": 2}) == "lost"
    assert S("tennis", "sets_total", "over", {"sets": [[6, 4], [6, 4]]}, 2.5) == "lost"
    order = {"order": ["Norris", "Verstappen", "Leclerc", "Hamilton"]}
    assert S("f1", "winner", "Norris", order) == "won" and S("f1", "podium", "Hamilton", order) == "lost"
    assert S("f1", "h2h", "Leclerc", order, opp="Hamilton") == "won"
    assert S("f1", "h2h", "Sainz", order, opp="Hamilton") == "lost"  # Sainz no terminó (no está en el orden)
    assert S("football", "player_stat", "Haaland goles:over", {"home": 1, "away": 0, "stats": {"Haaland goles": 2}}, 1.5) == "won"
    assert S("football", "player_stat", "Pedri asistencias:over", {"home": 1, "away": 0}, 0.5) is None  # sin dato → no se supone
    assert S("football", "1x2", "home", None, status="scheduled") is None
    assert S("football", "1x2", "home", None, status="cancelled") == "void"
    with pytest.raises(mk.MarketError):
        mk.validate("football", "total", "over", 2.25, None)  # líneas de cuarto no admitidas
    with pytest.raises(mk.MarketError):
        mk.validate("tennis", "btts", "yes", None, None)


def test_combo_payout_odds_math():
    assert mk.bet_outcome(["won", "won"], [2.0, 1.5], 10) == ("won", 30.0)
    assert mk.bet_outcome(["won", "void"], [2.0, 1.5], 10) == ("won", 20.0)  # nula = cuota 1
    assert mk.bet_outcome(["won", "lost"], [2.0, 1.5], 10) == ("lost", 0.0)
    assert mk.bet_outcome(["won", "pending"], [2.0, 1.5], 10) == ("pending", None)
    assert mk.bet_outcome(["void"], [2.0], 10) == ("void", 10.0)
    ov = mk.overround([2.0, 3.4, 4.0])
    assert ov["margin_pct"] == pytest.approx((0.5 + 1 / 3.4 + 0.25 - 1) * 100, abs=0.01)
    assert sum(ov["fair_probs"]) == pytest.approx(1, abs=1e-5)
    e = mk.edge(0.55, 2.0)
    assert e["ev_per_unit"] == pytest.approx(0.1) and e["kelly_fraction"] == pytest.approx(0.1)


def _league(n_rounds=30, seed=3, start=datetime(2025, 8, 1)):
    rnd = random.Random(seed)
    teams = [f"T{i}" for i in range(10)]
    power = {t: 0.6 + i * 0.12 for i, t in enumerate(teams)}
    ms, d = [], start
    for _ in range(n_rounds):
        rnd.shuffle(teams)
        for h, a in zip(teams[::2], teams[1::2]):
            lh, la = 1.3 * power[h] / power[a], 1.0 * power[a] / power[h]
            hg = sum(1 for _ in range(10) if rnd.random() < lh / 10)
            ag = sum(1 for _ in range(10) if rnd.random() < la / 10)
            ms.append(md.Match(d, h, a, hg, ag))
        d += timedelta(days=7)
    return ms, d


def test_poisson_model_probabilities_uncertainty_and_joint():
    ms, end = _league()
    assert "insufficient" in md.football(ms[:10], "T9", "T0", end)
    r = md.football(ms, "T9", "T0", end, boot=40)
    p = r["probs"]
    assert p["1x2:home"] + p["1x2:draw"] + p["1x2:away"] == pytest.approx(1, abs=1e-6)
    assert p["1x2:home"] > p["1x2:away"]  # el equipo más fuerte en casa
    lo, hi = r["intervals_80"]["1x2:home"]
    assert lo <= p["1x2:home"] <= hi and hi - lo > 0
    joint = mk.matrix_prob(r["matrix"], [("1x2", "home", None), ("total", "over", 2.5)])
    assert joint != pytest.approx(p["1x2:home"] * p["total:over:2.5"], abs=1e-4)  # correlación: no es el producto
    assert mk.matrix_prob(r["matrix"], [("1x2", "home", None), ("1x2", "away", None)]) == 0
    f = md.form(ms, "T9", end)
    assert len(f["last"]) == 5 and f["rest_days"] == 7


def _event(client, session, **kw):
    body = {"sport": "football", "competition": "Liga test", "home": "Rojo", "away": "Azul",
            "starts_at": (datetime.utcnow() + timedelta(hours=3)).isoformat() + "Z"} | kw
    r = client.post("/api/betting/events", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _start(session, eid):
    ev = session.get(BtEvent, eid)
    ev.starts_at = datetime.utcnow() - timedelta(hours=2)
    session.commit()


def test_bankroll_singles_combos_and_settlement(client, session):
    br = client.get("/api/betting/bankroll").json()
    assert br["initial"] == 10_000 and br["balance"] == 10_000 and br["simulated"] is True
    e1, e2 = _event(client, session), _event(client, session, home="Verde", away="Negro")
    single = client.post("/api/betting/bets", json={"legs": [{"event_id": e1["id"], "market": "1x2", "pick": "home", "odds": 2.1}],
                                                    "stake": 100, "reasoning": "Mejor forma en casa", "user_prob": 0.5}).json()
    assert single["kind"] == "single" and single["potential_return"] == 210
    combo_an = client.post("/api/betting/slip/analyze", json={"legs": [
        {"event_id": e1["id"], "market": "total", "pick": "over", "line": 2.5, "odds": 1.9},
        {"event_id": e2["id"], "market": "btts", "pick": "yes", "odds": 1.8}], "stake": 50}).json()
    assert combo_an["odds"] == pytest.approx(3.42) and combo_an["potential_return"] == pytest.approx(171)
    combo = client.post("/api/betting/bets", json={"legs": [
        {"event_id": e1["id"], "market": "total", "pick": "over", "line": 2.5, "odds": 1.9},
        {"event_id": e2["id"], "market": "btts", "pick": "yes", "odds": 1.8}], "stake": 50}).json()
    assert combo["kind"] == "combo"
    # Correlación en el mismo partido: aviso; contradicción: rechazo
    corr = client.post("/api/betting/slip/analyze", json={"legs": [
        {"event_id": e1["id"], "market": "1x2", "pick": "home", "odds": 2.1},
        {"event_id": e1["id"], "market": "total", "pick": "over", "line": 2.5, "odds": 1.9}]}).json()
    assert any("CORRELACIONADAS" in w for w in corr["warnings"])
    bad = client.post("/api/betting/slip/analyze", json={"legs": [
        {"event_id": e1["id"], "market": "1x2", "pick": "home", "odds": 2.1},
        {"event_id": e1["id"], "market": "1x2", "pick": "away", "odds": 3.5}]})
    assert bad.status_code == 422 and "incompatibles" in bad.json()["detail"]
    assert client.get("/api/betting/bankroll").json()["balance"] == 9_850
    assert client.post("/api/betting/bets", json={"legs": [{"event_id": e1["id"], "market": "1x2", "pick": "home", "odds": 2}], "stake": 20_000}).status_code == 422
    # Resultados: no antes de empezar; después, liquidación automática
    assert client.put(f"/api/betting/events/{e1['id']}/result", json={"status": "finished", "result": {"home": 2, "away": 1}}).status_code == 422
    _start(session, e1["id"])
    assert client.post("/api/betting/bets", json={"legs": [{"event_id": e1["id"], "market": "1x2", "pick": "away", "odds": 3}], "stake": 10}).status_code == 422
    r = client.put(f"/api/betting/events/{e1['id']}/result", json={"status": "finished", "result": {"home": 2, "away": 1}}).json()
    assert single["id"] in r["settled"] and combo["id"] not in r["settled"]  # la combinada espera al otro partido
    assert client.get("/api/betting/bankroll").json()["balance"] == 9_850 + 210
    _start(session, e2["id"])
    client.put(f"/api/betting/events/{e2['id']}/result", json={"status": "cancelled"})
    bets = {b["id"]: b for b in client.get("/api/betting/bets").json()}
    assert bets[combo["id"]]["status"] == "won" and bets[combo["id"]]["returned"] == pytest.approx(95)  # 50 × 1,9 (la nula cuenta como 1)
    a = client.get("/api/betting/analytics").json()
    assert a["won"] == 2 and a["lost"] == 0 and a["hit_rate"] == 100.0
    assert a["profit"] == pytest.approx(110 + 45) and a["roi"] == pytest.approx(155 / 150 * 100, abs=0.01)
    assert a["calibration"]["user"]["n"] == 1 and a["calibration"]["user"]["brier"] == pytest.approx(0.25)
    assert {x["key"] for x in a["by_kind"]} == {"Simples", "Combinadas"} and len(a["curve"]) == 2
    assert client.post("/api/betting/bankroll", json={"initial": 5000}).status_code == 201
    assert client.get("/api/betting/bankroll").json()["balance"] == 5000


def test_backtest_respects_time_order(monkeypatch):
    ms, _ = _league(n_rounds=36, seed=5)
    rows = [{"date": m.date, "home": m.home, "away": m.away, "hg": m.hg, "ag": m.ag,
             "odds": {"home": 2.3, "draw": 3.3, "away": 3.1, "over25": 1.95, "under25": 1.9}} for m in ms]
    monkeypatch.setattr(pv, "csv_season", lambda league, s: [dict(r) for r in rows])
    r1 = analysis.backtest("PL", [2025], ["model_value_1x2", "home", "favourite"], threshold=0.0)
    assert r1["evaluated"] > 0 and r1["model_brier_1x2"] is not None and any("NO garantizan" in w for w in r1["warnings"])
    res = {x["strategy"]: x for x in r1["results"]}
    assert res["home"]["bets"] == len(rows) - r1["warmup"]
    # Sin mirar al futuro: cambiar el último partido no altera ninguna decisión anterior
    rows[-1] = rows[-1] | {"hg": 9, "ag": 0}
    r2 = analysis.backtest("PL", [2025], ["model_value_1x2"], threshold=0.0)
    a = [(x["match"], x["pick"]) for x in res["model_value_1x2"]["sample"][:-1]]
    b = [(x["match"], x["pick"]) for x in r2["results"][0]["sample"][:-1]]
    assert a == b


class _R:
    def __init__(self, js=None, text="", status=200, headers=None):
        self._js, self.text, self.status_code, self.headers = js, text, status, headers or {}
        self.content = text.encode("latin-1")

    def json(self):
        return self._js


def test_provider_formats(client, monkeypatch):
    def fake(url, params=None, headers=None, timeout=None):
        if "football-data.org/v4/competitions/PL/matches" in url:
            return _R({"matches": [{"id": 1, "utcDate": "2026-12-01T20:00:00Z", "status": "TIMED", "competition": {"name": "Premier League"},
                                    "homeTeam": {"name": "Arsenal FC"}, "awayTeam": {"name": "Chelsea FC"}, "score": {"fullTime": {"home": None, "away": None}}}]})
        if "the-odds-api.com/v4/sports/soccer_epl/odds" in url:
            return _R([{"id": "abc", "sport_key": "soccer_epl", "commence_time": "2026-12-01T20:00:00Z", "home_team": "Arsenal", "away_team": "Chelsea",
                        "bookmakers": [{"key": "b1", "title": "Casa 1", "last_update": "2026-11-30T10:00:00Z",
                                        "markets": [{"key": "h2h", "outcomes": [{"name": "Arsenal", "price": 2.0}, {"name": "Chelsea", "price": 3.6}, {"name": "Draw", "price": 3.5}]}]}]}],
                      headers={"x-requests-remaining": "480"})
        if "jolpi.ca/ergast/f1/2026/5/results.json" in url:
            return _R({"MRData": {"RaceTable": {"Races": [{"Results": [
                {"position": "2", "Driver": {"familyName": "Verstappen", "code": "VER"}, "Constructor": {"name": "Red Bull"}, "points": "18", "status": "Finished"},
                {"position": "1", "Driver": {"familyName": "Norris", "code": "NOR"}, "Constructor": {"name": "McLaren"}, "points": "25", "status": "Finished"}]}]}}})
        if "football-data.co.uk" in url:
            return _R(text="Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,AvgH,AvgD,AvgA,Avg>2.5,Avg<2.5\nE0,16/08/2024,20:00,Man United,Fulham,1,0,1.6,4.2,5.5,1.9,1.95\n")
        return _R({}, status=404)
    monkeypatch.setattr(pv.httpx, "get", fake)
    from atlas.integrations.secrets import set_secret
    set_secret("footballdata_api_key", "k1")
    set_secret("theoddsapi_api_key", "k2")
    pv.clear_cache()
    m = pv.fd_matches("PL", "2026-11-25", "2026-12-05")[0]
    assert m["home"] == "Arsenal FC" and m["status"] == "scheduled" and m["result"] is None
    o = pv.odds_for("soccer_epl")[0]
    assert o["bookmakers"][0]["markets"]["h2h"][0]["price"] == 2.0
    assert {p["id"]: p for p in pv.status()}["theoddsapi"]["remaining"] == "480"
    res = pv.f1_results("2026", 5)
    assert sorted(res, key=lambda x: x["position"])[0]["driver"] == "Norris"
    rows = pv.csv_season("PL", 2024)
    assert rows[0]["odds"] == {"home": 1.6, "draw": 4.2, "away": 5.5, "over25": 1.9, "under25": 1.95} and rows[0]["hg"] == 1
    r = client.post("/api/betting/sync", json={"football": ["PL"], "odds_sport": "soccer_epl"}).json()
    assert r["imported"] == 2 and r["errors"] == []
    evs = client.get("/api/betting/events").json()
    odds_ev = next(e for e in evs if e["provider"] == "theoddsapi")
    t = client.get(f"/api/betting/events/{odds_ev['id']}/odds").json()
    sel = t["markets"][0]
    assert sel["margin_pct"] == pytest.approx((0.5 + 1 / 3.6 + 1 / 3.5 - 1) * 100, abs=0.01)
    assert [s["pick"] for s in sel["selections"]] == ["home", "away", "draw"]


def test_no_data_means_insufficient_and_agent_rules(client, session, ollama):
    e = _event(client, session, sport="tennis", home="Jugador A", away="Jugador B", competition=None)
    p = client.post(f"/api/betting/events/{e['id']}/predict").json()
    assert "insufficient" in p["model"] and any("Lesiones" in m for m in p["data"]["missing"])
    ollama.reply_chunks = ["No hay datos suficientes ", "para estimar."]
    r = client.post("/api/betting/agent", json={"question": "¿Cuánto debo apostar para recuperar lo perdido?", "event_id": e["id"]})
    assert r.status_code == 200
    sys = " ".join(m["content"] for m in ollama.requests[-1]["messages"] if m["role"] == "system")
    assert "perseguir pérdidas" in sys and "Nunca inventes estadísticas" in sys and "Jugador A" in sys
    an = client.post("/api/betting/odds/analyze", json={"odds": [1.9, 1.9], "probs": [0.55, None], "stake": 10}).json()
    assert an["market"]["margin_pct"] == pytest.approx(5.263, abs=0.01)
    assert an["selections"][0]["expected_profit"] == pytest.approx(0.45) and an["selections"][1]["edge"] is None
