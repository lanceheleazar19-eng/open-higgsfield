"""Prediction Engine (datos + modelo + explicación de la IA), Odds Analyzer sobre cuotas reales, backtesting
cronológico y agente tutor. La IA solo explica lo calculado: nunca crea estadísticas ni probabilidades."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.bets import markets as mk
from atlas.bets import models as md
from atlas.bets import providers as pv
from atlas.models import BtBet, BtEvent, BtPrediction


def _matches(rows: list[dict]) -> list[md.Match]:
    return [md.Match(r["starts_at"], r["home"], r["away"], int(r["result"]["home"]), int(r["result"]["away"]))
            for r in rows if r.get("result") and r.get("home") and r.get("away")]


def gather(db: Session, ev: BtEvent) -> dict:
    """Datos reales disponibles ANTES del evento y lo que falta (para no inventar)."""
    out: dict = {"event": {"name": ev.name, "sport": ev.sport, "competition": ev.competition, "starts_at": ev.starts_at.isoformat(),
                           "home": ev.home, "away": ev.away, **({"circuit": ev.meta.get("circuit")} if ev.meta.get("circuit") else {})},
                 "missing": [], "sources": []}
    notes = (ev.meta or {}).get("notes")
    if notes:
        out["user_notes"] = notes  # lesiones/bajas/contexto aportado por ti
    else:
        out["missing"].append("Lesiones y bajas confirmadas: ningún proveedor conectado las ofrece; puedes añadirlas como nota del evento")
    out["missing"].append("Condiciones del evento (clima, estado del campo): sin fuente conectada")
    try:
        if ev.sport == "football" and ev.provider == "football-data" and ev.meta.get("code"):
            hist = pv.fd_history(ev.meta["code"], ev.starts_at)
            ms = _matches(hist)
            out["sources"].append(f"football-data.org · {len(ms)} partidos terminados de {ev.competition}")
            out["form_home"] = md.form(ms, ev.home, ev.starts_at)
            out["form_away"] = md.form(ms, ev.away, ev.starts_at)
            out["h2h"] = md.h2h(ms, ev.home, ev.away, ev.starts_at)
            if not out["h2h"]:
                out["missing"].append("Enfrentamientos directos: no hay en las dos últimas temporadas de esta competición")
            res = md.football(ms, ev.home, ev.away, ev.starts_at)
            out["model"] = res
        elif ev.sport == "basketball" and ev.provider == "thesportsdb":
            past = [r for r in pv.tsdb_past(next(iter(pv.TSDB_LEAGUES))) if r["result"]]
            ms = _matches(past)
            out["sources"].append(f"TheSportsDB · {len(ms)} partidos recientes (el plan gratuito devuelve pocos)")
            out["form_home"] = md.form(ms, ev.home, ev.starts_at)
            out["form_away"] = md.form(ms, ev.away, ev.starts_at)
            out["model"] = md.basketball(ms, ev.home, ev.away, ev.starts_at)
        elif ev.sport == "f1":
            season = ev.external_id.split("-")[0] if ev.external_id else "current"
            races = [r for r in pv.f1_season_results(season) if r["round"] < int(ev.meta.get("round", 99))]
            drivers = sorted({x["driver"] for r in races for x in r["results"]})
            out["sources"].append(f"Jolpica F1 · {len(races)} carreras disputadas")
            out["standings_recent"] = [{"race": r["race"], "top5": [x["driver"] for x in sorted(r["results"], key=lambda y: y["position"])[:5]]} for r in races[-5:]]
            out["model"] = md.f1(races, drivers)
        else:
            out["model"] = {"insufficient": "No hay un proveedor de datos históricos conectado para este deporte o evento manual"}
    except pv.DataError as exc:
        out["model"] = {"insufficient": str(exc)}
        out["missing"].append(str(exc))
    if "insufficient" in out.get("model", {}):
        out["missing"].append(f"Modelo: {out['model']['insufficient']}")
    return out


SYSTEM = """Eres el VISTAN Betting Agent, analista deportivo y profesor de probabilidad dentro de un SIMULADOR con dinero
FICTICIO. Reglas estrictas:
- Usa SOLO los datos del bloque DATOS. Si algo no está (lesiones, alineaciones, clima…), di explícitamente que no hay datos.
- Nunca inventes estadísticas, cuotas, resultados ni probabilidades. Las probabilidades vienen del modelo; puedes comentarlas.
- Muestra la incertidumbre (intervalos, tamaño de muestra) y nunca presentes un pronóstico como seguro.
- No prometas ganancias. No recomiendes subir importes para recuperar pérdidas (perseguir pérdidas). No animes a apostar
  dinero real: esto es un laboratorio educativo.
- Detecta errores de razonamiento (falacia del jugador, sesgo de confirmación, ignorar el margen de la casa, muestras pequeñas,
  tratar selecciones correlacionadas como independientes).
- Explica conceptos (probabilidad implícita, valor esperado, margen, calibración, Brier) con ejemplos sencillos.
- Responde en español, en Markdown sencillo y sin pasar de ~350 palabras salvo que te pidan más."""


def predict(db: Session, prefs: dict, ev: BtEvent, explain: bool = True) -> dict:
    data = gather(db, ev)
    model = data.get("model") or {}
    pred_out = {"event_id": ev.id, "data": {k: v for k, v in data.items() if k != "model"},
                "model": {k: v for k, v in model.items() if k not in ("matrix",)}, "explanation": None, "explanation_model": None}
    if "probs" in model:
        p = BtPrediction(event_id=ev.id, model=model["model"], probs=model["probs"],
                         inputs={"matrix": model.get("matrix"), "intervals_80": model.get("intervals_80"), "method": model.get("method")})
        db.add(p)
        db.flush()
        pred_out["prediction_id"] = p.id
    if explain:
        from atlas.brain import router
        from atlas.brain.base import ProviderError
        ctx = {k: v for k, v in data.items() if k != "model"} | {"modelo": pred_out["model"]}
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "system", "content": "DATOS:\n" + json.dumps(ctx, ensure_ascii=False, default=str)[:14000]},
                {"role": "user", "content": "Analiza este evento: forma reciente, enfrentamientos directos, local/visitante, descanso y "
                                            "calendario, lo que falta, la metodología del modelo y su incertidumbre. Termina con los escenarios "
                                            "principales y qué información cambiaría el análisis."}]
        try:
            text, model_name = router.complete_text("chat", prefs, msgs)
            pred_out["explanation"], pred_out["explanation_model"] = text.strip(), model_name
            if pred_out.get("prediction_id"):
                db.get(BtPrediction, pred_out["prediction_id"]).explanation = text.strip()
        except ProviderError as exc:
            pred_out["explanation_error"] = f"Sin IA disponible: {exc}"
    return pred_out


def odds_table(db: Session, ev: BtEvent) -> dict:
    """Cuotas reales (The Odds API) para el evento, con margen, probabilidades justas y diferencia frente al modelo."""
    if ev.provider != "theoddsapi" and not ev.meta.get("odds_event_id"):
        return {"markets": [], "note": "Este evento no está enlazado a un proveedor de cuotas: introduce las cuotas manualmente."}
    sk = ev.meta.get("sport_key")
    oid = ev.external_id if ev.provider == "theoddsapi" else ev.meta.get("odds_event_id")
    try:
        data = next((e for e in pv.odds_for(sk) if e["id"] == oid), None)
    except pv.DataError as exc:
        return {"markets": [], "note": str(exc)}
    if not data:
        return {"markets": [], "note": "El proveedor ya no ofrece cuotas para este evento"}
    pred = db.scalar(select(BtPrediction).where(BtPrediction.event_id == ev.id).order_by(BtPrediction.id.desc()).limit(1))
    rows = []
    for b in data["bookmakers"]:
        h2h = b["markets"].get("h2h")
        if h2h and len(h2h) >= 2:
            prices = [o["price"] for o in h2h]
            ov = mk.overround(prices)
            sel = []
            for o, fp in zip(h2h, ov["fair_probs"]):
                pick = "home" if o["name"] == ev.home else "away" if o["name"] == ev.away else "draw"
                market = "1x2" if len(h2h) == 3 else "moneyline"
                mp = pred.probs.get(md.market_key(market, pick, None)) if pred else None
                sel.append({"name": o["name"], "market": market, "pick": pick, "odds": o["price"], "implied": round(1 / o["price"], 4),
                            "fair_prob": fp, "model_prob": mp, "edge": mk.edge(mp, o["price"]) if mp else None})
            rows.append({"bookmaker": b["title"], "updated": b["last_update"], "market": "h2h", "margin_pct": ov["margin_pct"], "selections": sel})
        tot = b["markets"].get("totals")
        if tot and len(tot) == 2:
            ov = mk.overround([o["price"] for o in tot])
            sel = []
            for o, fp in zip(tot, ov["fair_probs"]):
                pick = "over" if o["name"].lower() == "over" else "under"
                mp = pred.probs.get(md.market_key("total", pick, o.get("point"))) if pred and o.get("point") is not None else None
                sel.append({"name": f"{o['name']} {o.get('point')}", "market": "total", "pick": pick, "line": o.get("point"), "odds": o["price"],
                            "implied": round(1 / o["price"], 4), "fair_prob": fp, "model_prob": mp, "edge": mk.edge(mp, o["price"]) if mp else None})
            rows.append({"bookmaker": b["title"], "updated": b["last_update"], "market": "totals", "margin_pct": ov["margin_pct"], "selections": sel})
    return {"markets": rows, "source": "The Odds API", "note": None}


# ───────── Backtesting cronológico (fútbol, cuotas históricas reales) ─────────

STRATEGIES = {
    "model_value_1x2": "Modelo Poisson: apostar al resultado 1X2 con mayor valor esperado si supera el umbral",
    "model_value_ou25": "Modelo Poisson: más/menos 2,5 goles cuando el valor esperado supera el umbral",
    "favourite": "Apostar siempre al favorito de las cuotas (referencia)",
    "home": "Apostar siempre al local (referencia)",
    "draw": "Apostar siempre al empate (referencia)",
}


def _probs_fast(lh: float, la: float) -> dict:
    mat = md.score_matrix(lh, la)
    ph = sum(mat[h][a] for h in range(len(mat)) for a in range(len(mat)) if h > a)
    pd = sum(mat[i][i] for i in range(len(mat)))
    po = sum(mat[h][a] for h in range(len(mat)) for a in range(len(mat)) if h + a > 2)
    return {"home": ph, "draw": pd, "away": 1 - ph - pd, "over25": po, "under25": 1 - po}


def backtest(league: str, seasons: list[int], strategies: list[str], threshold: float = 0.05, stake_mode: str = "flat",
             stake: float = 100.0, kelly_frac: float = 0.25, bankroll: float = 10_000.0, warmup: int = 60) -> dict:
    rows: list[dict] = []
    for s in sorted(seasons):
        rows += pv.csv_season(league, s)
    rows.sort(key=lambda r: r["date"])
    if len(rows) < warmup + 30:
        raise ValueError("Pocos partidos históricos para un backtest fiable")
    hist: list[md.Match] = []
    picks: dict[str, list[dict]] = {s: [] for s in strategies}
    brier_pairs: list[tuple[float, int]] = []
    evaluated = 0
    for i, r in enumerate(rows):
        # SOLO información anterior al partido: el modelo se ajusta con `hist`, que aún no incluye este partido
        if i >= warmup and {"home", "draw", "away"} <= r["odds"].keys():
            fit = md.fit_poisson(hist, r["home"], r["away"], r["date"])
            p = _probs_fast(fit["lambda_home"], fit["lambda_away"]) if fit else None
            out1x2 = "home" if r["hg"] > r["ag"] else "away" if r["ag"] > r["hg"] else "draw"
            if p:
                evaluated += 1
                for k in ("home", "draw", "away"):
                    brier_pairs.append((p[k], 1 if k == out1x2 else 0))
            for s in strategies:
                pick = prob = odds = None
                if s in ("model_value_1x2", "model_value_ou25") and p:
                    cands = [("home", "draw", "away")] if s == "model_value_1x2" else [("over25", "under25")]
                    best = max(((k, p[k] * r["odds"][k] - 1) for k in cands[0] if k in r["odds"]), key=lambda x: x[1], default=None)
                    if best and best[1] > threshold:
                        pick, prob, odds = best[0], p[best[0]], r["odds"][best[0]]
                elif s == "favourite":
                    pick = min(("home", "draw", "away"), key=lambda k: r["odds"][k])
                    odds = r["odds"][pick]
                elif s in ("home", "draw"):
                    pick, odds = s, r["odds"][s]
                if pick:
                    won = (pick == out1x2) if pick in ("home", "draw", "away") else ((r["hg"] + r["ag"] > 2) == (pick == "over25"))
                    picks[s].append({"date": r["date"].isoformat(), "match": f"{r['home']} – {r['away']}", "pick": pick, "odds": odds,
                                     "prob": prob, "won": won, "score": f"{r['hg']}-{r['ag']}"})
        hist.append(md.Match(r["date"], r["home"], r["away"], r["hg"], r["ag"]))
    results = []
    for s, ps in picks.items():
        bal, peak, mdd, curve, staked = bankroll, bankroll, 0.0, [], 0.0
        for x in ps:
            if stake_mode == "kelly" and x["prob"]:
                f = max((x["prob"] * (x["odds"] - 1) - (1 - x["prob"])) / (x["odds"] - 1), 0) * kelly_frac
                st = round(bal * min(f, 0.05), 2)  # nunca más del 5 % del bankroll por pronóstico
            else:
                st = min(stake, bal)
            if st <= 0:
                continue
            staked += st
            bal += st * (x["odds"] - 1) if x["won"] else -st
            peak = max(peak, bal)
            mdd = max(mdd, (peak - bal) / peak * 100 if peak else 0)
            curve.append({"date": x["date"], "bankroll": round(bal, 2)})
        half = len(ps) // 2

        def roi(xs: list[dict]) -> float | None:
            return round(sum((x["odds"] - 1) if x["won"] else -1 for x in xs) / len(xs) * 100, 2) if xs else None
        results.append({"strategy": s, "name": STRATEGIES[s], "bets": len(ps), "hit_rate": round(sum(x["won"] for x in ps) / len(ps) * 100, 2) if ps else None,
                        "profit": round(bal - bankroll, 2), "staked": round(staked, 2), "roi_flat": roi(ps),
                        "roi_first_half": roi(ps[:half]), "roi_second_half": roi(ps[half:]), "max_drawdown_pct": round(mdd, 2),
                        "avg_odds": round(sum(x["odds"] for x in ps) / len(ps), 3) if ps else None,
                        "curve": curve[:: max(1, len(curve) // 300)], "sample": ps[-30:]})
    return {"league": league, "seasons": seasons, "matches": len(rows), "warmup": warmup, "evaluated": evaluated,
            "model_brier_1x2": md.brier(brier_pairs), "results": results, "source": "football-data.co.uk (resultados y cuotas medias históricas)",
            "warnings": [
                "Los resultados históricos NO garantizan resultados futuros.",
                "Orden temporal respetado: cada pronóstico usa solo partidos anteriores a su fecha.",
                "Sobreajuste: si pruebas muchos umbrales o estrategias y eliges la mejor, el resultado está sesgado al alza. "
                "Compara la primera y la segunda mitad: si cambian mucho, el «edge» probablemente no es real.",
                "Las cuotas son medias de cierre de varias casas: en la práctica podrían no haber estado disponibles a ese precio.",
                "Muestras pequeñas (pocas apuestas) producen ROI muy volátiles: no son concluyentes."]}


def tutor(db: Session, prefs: dict, question: str, event_id: int | None, history: list[dict]) -> dict:
    from atlas.bets import engine
    from atlas.brain import router
    stats = engine.analytics(db)
    recent = [engine.bet_dict(db, b) for b in db.scalars(select(BtBet).order_by(BtBet.id.desc()).limit(12))]
    ctx: dict = {"aviso": "SIMULACIÓN con dinero ficticio", "estadisticas": {k: v for k, v in stats.items() if k != "curve"},
                 "ultimos_pronosticos": recent}
    if event_id:
        ev = db.get(BtEvent, event_id)
        if ev:
            pred = db.scalar(select(BtPrediction).where(BtPrediction.event_id == ev.id).order_by(BtPrediction.id.desc()).limit(1))
            ctx["evento"] = {"nombre": ev.name, "deporte": ev.sport, "competicion": ev.competition, "inicio": ev.starts_at.isoformat(),
                             "estado": ev.status, "resultado": ev.result, "notas": (ev.meta or {}).get("notes"),
                             "prediccion": {"modelo": pred.model, "probabilidades": pred.probs, "intervalos_80": (pred.inputs or {}).get("intervals_80")} if pred else None}
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "system", "content": "DATOS:\n" + json.dumps(ctx, ensure_ascii=False, default=str)[:14000]}]
    for h in history[-6:]:
        if h.get("role") in ("user", "assistant"):
            msgs.append({"role": h["role"], "content": str(h.get("content", ""))[:2000]})
    msgs.append({"role": "user", "content": question})
    text, model = router.complete_text("chat", prefs, msgs)
    return {"answer": text.strip(), "model": model}

