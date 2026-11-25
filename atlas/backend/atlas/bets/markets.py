"""Mercados, reglas de liquidación y matemática de cuotas. Todo determinista y verificable.

Resultados (BtEvent.result):
- football / basketball / other:  {"home": int, "away": int}
- tennis: {"sets": [[6, 4], [3, 6], [6, 2]]}  o  {"home_sets": 2, "away_sets": 1}
- f1: {"order": ["Verstappen", "Norris", ...]}  (orden de llegada; DNF al final o ausente)
- estadísticas individuales: {"stats": {"Haaland goles": 2}}  (añadidas al resultado del evento)
"""

from __future__ import annotations

import math

MARKETS: dict[str, dict] = {
    "1x2": {"name": "Ganador (1X2)", "sports": ["football", "other"], "picks": ["home", "draw", "away"]},
    "double_chance": {"name": "Doble oportunidad", "sports": ["football"], "picks": ["1X", "12", "X2"]},
    "moneyline": {"name": "Ganador (sin empate)", "sports": ["basketball", "tennis", "other"], "picks": ["home", "away"]},
    "total": {"name": "Más/menos goles o puntos", "sports": ["football", "basketball", "other"], "picks": ["over", "under"], "line": True},
    "btts": {"name": "Ambos equipos marcan", "sports": ["football"], "picks": ["yes", "no"]},
    "handicap": {"name": "Hándicap (sobre el local)", "sports": ["football", "basketball", "other"], "picks": ["home", "away"], "line": True},
    "correct_score": {"name": "Resultado exacto", "sports": ["football"], "picks": None},
    "sets_exact": {"name": "Resultado por sets", "sports": ["tennis"], "picks": None},
    "sets_total": {"name": "Total de sets", "sports": ["tennis"], "picks": ["over", "under"], "line": True},
    "winner": {"name": "Ganador de la carrera", "sports": ["f1"], "picks": None},
    "podium": {"name": "Podio (top 3)", "sports": ["f1"], "picks": None},
    "h2h": {"name": "Duelo entre pilotos", "sports": ["f1"], "picks": None},
    "player_stat": {"name": "Estadística individual (más/menos)", "sports": ["football", "basketball", "tennis", "f1", "other"], "picks": None, "line": True},
}
PICK_LABEL = {"home": "Local", "draw": "Empate", "away": "Visitante", "over": "Más de", "under": "Menos de", "yes": "Sí", "no": "No"}


class MarketError(ValueError):
    pass


def validate(sport: str, market: str, pick: str, line: float | None, opponent: str | None) -> None:
    m = MARKETS.get(market)
    if not m:
        raise MarketError("Mercado desconocido")
    if sport not in m["sports"]:
        raise MarketError(f"El mercado «{m['name']}» no se aplica a este deporte")
    if m["picks"] and pick not in m["picks"]:
        raise MarketError(f"Selección no válida para «{m['name']}»")
    if m.get("line") and line is None:
        raise MarketError("Este mercado necesita una línea (p. ej. 2.5)")
    if line is not None and abs(line * 2 - round(line * 2)) > 1e-9:
        raise MarketError("Solo líneas enteras o de medio punto (las líneas asiáticas de cuarto no se admiten)")
    if market == "correct_score" or market == "sets_exact":
        parts = pick.split("-")
        if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
            raise MarketError("Formato del resultado: 2-1")
    if market == "h2h" and not opponent:
        raise MarketError("Indica el piloto rival del duelo")
    if market == "player_stat" and pick.split(":")[-1] not in ("over", "under"):
        raise MarketError("Formato: «Nombre estadística:over» o «:under»")


def _ou(value: float, line: float, side: str) -> str:
    if value == line:
        return "void"
    return "won" if (value > line) == (side == "over") else "lost"


def _sets(result: dict) -> tuple[int, int] | None:
    if "home_sets" in result and "away_sets" in result:
        return int(result["home_sets"]), int(result["away_sets"])
    if result.get("sets"):
        h = sum(1 for a, b in result["sets"] if a > b)
        return h, len(result["sets"]) - h
    return None


def settle_leg(sport: str, market: str, pick: str, line: float | None, opponent: str | None,
               status: str, result: dict | None, home: str | None = None, away: str | None = None) -> str | None:
    """won | lost | void, o None si aún no hay datos suficientes para liquidar (nunca se supone)."""
    if status in ("cancelled", "postponed"):
        return "void"
    if status != "finished" or not result:
        return None
    if market == "player_stat":
        name, side = pick.rsplit(":", 1)
        v = (result.get("stats") or {}).get(name)
        return None if v is None else _ou(float(v), float(line), side)
    if sport == "f1" or market in ("winner", "podium", "h2h"):
        order = [x.lower() for x in result.get("order") or []]
        if not order:
            return None
        pos = order.index(pick.lower()) if pick.lower() in order else None
        if market == "winner":
            return "won" if pos == 0 else "lost"
        if market == "podium":
            return "won" if pos is not None and pos < 3 else "lost"
        opp = order.index(opponent.lower()) if opponent and opponent.lower() in order else None
        if pos is None and opp is None:
            return "void"
        return "won" if opp is None or (pos is not None and pos < opp) else "lost"
    if market in ("sets_exact", "sets_total") or (sport == "tennis" and market == "moneyline"):
        s = _sets(result)
        if not s:
            return None
        if market == "sets_exact":
            a, b = (int(x) for x in pick.split("-"))
            return "won" if (a, b) == s else "lost"
        if market == "sets_total":
            return _ou(sum(s), float(line), pick)
        return "won" if (s[0] > s[1]) == (pick == "home") else "lost"
    if "home" not in result or "away" not in result:
        return None
    h, a = float(result["home"]), float(result["away"])
    if market == "1x2":
        out = "home" if h > a else "away" if a > h else "draw"
        return "won" if pick == out else "lost"
    if market == "double_chance":
        out = "1" if h > a else "2" if a > h else "X"
        return "won" if out in pick else "lost"
    if market == "moneyline":
        if h == a:
            return "void"
        return "won" if (h > a) == (pick == "home") else "lost"
    if market == "total":
        return _ou(h + a, float(line), pick)
    if market == "btts":
        both = h > 0 and a > 0
        return "won" if both == (pick == "yes") else "lost"
    if market == "handicap":
        adj = h + float(line) - a
        if adj == 0:
            return "void"
        return "won" if (adj > 0) == (pick == "home") else "lost"
    if market == "correct_score":
        x, y = (int(v) for v in pick.split("-"))
        return "won" if (x, y) == (int(h), int(a)) else "lost"
    raise MarketError("Mercado sin reglas de liquidación")


def bet_outcome(leg_status: list[str], leg_odds: list[float], stake: float) -> tuple[str, float | None]:
    """Liquidación de la apuesta: (estado, retorno). Las selecciones nulas cuentan como cuota 1."""
    if any(s == "lost" for s in leg_status):
        return "lost", 0.0
    if any(s == "pending" for s in leg_status):
        return "pending", None
    if all(s == "void" for s in leg_status):
        return "void", round(stake, 2)
    mult = math.prod(o for s, o in zip(leg_status, leg_odds) if s == "won")
    return "won", round(stake * mult, 2)


# ───────── Cuotas ─────────

def implied(odds: float) -> float:
    return 1 / odds


def overround(odds_list: list[float]) -> dict:
    """Margen de la casa en un mercado completo y probabilidades «justas» (normalización proporcional)."""
    if len(odds_list) < 2 or any(o <= 1 for o in odds_list):
        raise MarketError("Introduce todas las cuotas del mercado (todas > 1)")
    imp = [1 / o for o in odds_list]
    s = sum(imp)
    fair = [p / s for p in imp]
    return {"implied": [round(p, 6) for p in imp], "booksum": round(s, 6), "margin_pct": round((s - 1) * 100, 3),
            "fair_probs": [round(p, 6) for p in fair], "fair_odds": [round(1 / p, 4) for p in fair]}


def edge(prob: float, odds: float) -> dict:
    """Valor esperado por unidad apostada y fracción de Kelly (educativa)."""
    ev = prob * odds - 1
    b = odds - 1
    kelly = (prob * b - (1 - prob)) / b if b > 0 else None
    return {"ev_per_unit": round(ev, 4), "edge_pct": round((prob - 1 / odds) * 100, 3), "fair_odds": round(1 / prob, 4) if prob > 0 else None,
            "kelly_fraction": round(max(kelly, 0), 4) if kelly is not None else None}


# ───────── Probabilidades a partir de una matriz de marcadores (fútbol) ─────────

def leg_wins_on_score(market: str, pick: str, line: float | None, h: int, a: int) -> bool:
    r = settle_leg("football", market, pick, line, None, "finished", {"home": h, "away": a})
    return r == "won"


def matrix_prob(matrix: list[list[float]], legs: list[tuple[str, str, float | None]]) -> float:
    """Probabilidad de que TODAS las selecciones (mismo partido) ganen a la vez: suma exacta sobre la matriz,
    sin suponer independencia entre mercados correlacionados."""
    p = 0.0
    for h, row in enumerate(matrix):
        for a, v in enumerate(row):
            if all(leg_wins_on_score(m, pk, ln, h, a) for m, pk, ln in legs):
                p += v
    return p
