"""Prediction Engine: modelos estadísticos transparentes sobre resultados REALES anteriores al evento.

- Fútbol: Poisson con fuerzas de ataque/defensa (local/visitante), decaimiento temporal y contracción hacia la media
  (evita sobreajustar con pocos partidos). Incertidumbre por bootstrap de los partidos usados.
- Baloncesto: modelo normal del margen y del total, con medias y desviaciones medidas en los partidos.
- F1: pesos por puntos recientes (modelo de Plackett-Luce simplificado). Muy incierto: se indica.
Si no hay datos suficientes, devuelve `insufficient` con el motivo: nunca rellena con números inventados."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime

from atlas.bets import markets as mk

MAX_GOALS = 10


@dataclass
class Match:
    date: datetime
    home: str
    away: str
    hg: int
    ag: int


def _pois(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def score_matrix(lh: float, la: float) -> list[list[float]]:
    m = [[_pois(h, lh) * _pois(a, la) for a in range(MAX_GOALS + 1)] for h in range(MAX_GOALS + 1)]
    s = sum(map(sum, m))
    return [[v / s for v in row] for row in m]


def fit_poisson(matches: list[Match], home: str, away: str, at: datetime, half_life_days: float = 180, prior: float = 4.0) -> dict | None:
    past = [m for m in matches if m.date < at]
    if len(past) < 20:
        return None
    w = [0.5 ** ((at - m.date).days / half_life_days) for m in past]
    W = sum(w)
    avg_h = sum(wi * m.hg for wi, m in zip(w, past)) / W
    avg_a = sum(wi * m.ag for wi, m in zip(w, past)) / W
    if avg_h <= 0 or avg_a <= 0:
        return None

    def strength(team: str, side: str) -> tuple[float, float, float]:
        """(ataque, defensa, partidos efectivos) con contracción bayesiana hacia 1."""
        gf = ga = ef = 0.0
        for wi, m in zip(w, past):
            if side == "home" and m.home == team:
                gf += wi * m.hg; ga += wi * m.ag; ef += wi
            elif side == "away" and m.away == team:
                gf += wi * m.ag; ga += wi * m.hg; ef += wi
        base_f, base_a = (avg_h, avg_a) if side == "home" else (avg_a, avg_h)
        att = (gf + prior * base_f) / ((ef + prior) * base_f)
        dfn = (ga + prior * base_a) / ((ef + prior) * base_a)
        return att, dfn, ef

    ah, dh, nh = strength(home, "home")
    aa, da, na = strength(away, "away")
    if nh < 0.5 and na < 0.5:
        return None
    lh, la = avg_h * ah * da, avg_a * aa * dh
    return {"lambda_home": lh, "lambda_away": la, "league_avg_home": avg_h, "league_avg_away": avg_a,
            "home_games": round(nh, 1), "away_games": round(na, 1), "matches_used": len(past)}


FOOTBALL_MARKETS = [("1x2", "home", None), ("1x2", "draw", None), ("1x2", "away", None), ("double_chance", "1X", None),
                    ("double_chance", "12", None), ("double_chance", "X2", None), ("total", "over", 1.5), ("total", "over", 2.5),
                    ("total", "under", 2.5), ("total", "over", 3.5), ("btts", "yes", None), ("btts", "no", None),
                    ("handicap", "home", -1.5), ("handicap", "away", 1.5)]


def market_key(m: str, p: str, line: float | None) -> str:
    return f"{m}:{p}" + (f":{line:g}" if line is not None else "")


def football(matches: list[Match], home: str, away: str, at: datetime, boot: int = 120, seed: int = 7) -> dict:
    fit = fit_poisson(matches, home, away, at)
    if not fit:
        return {"insufficient": "Hacen falta al menos 20 partidos previos de la competición con estos equipos"}
    mat = score_matrix(fit["lambda_home"], fit["lambda_away"])
    probs = {market_key(m, p, ln): mk.matrix_prob(mat, [(m, p, ln)]) for m, p, ln in FOOTBALL_MARKETS}
    # Incertidumbre: bootstrap de los partidos previos (re-muestreo con reemplazo)
    rnd = random.Random(seed)
    past = [m for m in matches if m.date < at]
    samples: dict[str, list[float]] = {k: [] for k in probs}
    for _ in range(boot):
        res = [past[rnd.randrange(len(past))] for _ in past]
        f = fit_poisson(res, home, away, at)
        if not f:
            continue
        bm = score_matrix(f["lambda_home"], f["lambda_away"])
        for m, p, ln in FOOTBALL_MARKETS:
            samples[market_key(m, p, ln)].append(mk.matrix_prob(bm, [(m, p, ln)]))
    intervals = {}
    for k, xs in samples.items():
        if len(xs) >= 20:
            xs.sort()
            intervals[k] = [round(xs[int(0.1 * len(xs))], 4), round(xs[int(0.9 * len(xs)) - 1], 4)]
    top = sorted(((h, a, mat[h][a]) for h in range(6) for a in range(6)), key=lambda x: -x[2])[:6]
    return {"model": "poisson_fuerzas_v1", "probs": {k: round(v, 4) for k, v in probs.items()}, "intervals_80": intervals,
            "expected_goals": {"home": round(fit["lambda_home"], 3), "away": round(fit["lambda_away"], 3)},
            "top_scores": [{"score": f"{h}-{a}", "p": round(p, 4)} for h, a, p in top], "fit": fit, "matrix": mat,
            "method": ("Poisson independiente por equipo: goles esperados = media de la liga × ataque × defensa rival, "
                       "estimados con partidos anteriores al evento (más peso a los recientes, vida media 180 días) y "
                       "contraídos hacia la media de la liga. Intervalos del 80 % por bootstrap de esos partidos. "
                       "Limitaciones: no conoce lesiones, alineaciones, motivación ni clima salvo que se aporten.")}


def form(matches: list[Match], team: str, at: datetime, n: int = 5) -> dict:
    past = sorted((m for m in matches if m.date < at and team in (m.home, m.away)), key=lambda m: m.date)
    last = past[-n:]
    seq, gf, ga = [], 0, 0
    for m in last:
        f, a = (m.hg, m.ag) if m.home == team else (m.ag, m.hg)
        gf += f; ga += a
        seq.append("V" if f > a else "E" if f == a else "D")
    home = [m for m in past if m.home == team]
    away = [m for m in past if m.away == team]

    def ppg(ms: list[Match], side: str) -> float | None:
        if not ms:
            return None
        pts = sum(3 if (m.hg > m.ag if side == "home" else m.ag > m.hg) else 1 if m.hg == m.ag else 0 for m in ms)
        return round(pts / len(ms), 2)
    rest = (at - past[-1].date).days if past else None
    return {"team": team, "last": seq, "goals_for": gf, "goals_against": ga, "games": len(last),
            "home_ppg": ppg(home, "home"), "home_games": len(home), "away_ppg": ppg(away, "away"), "away_games": len(away),
            "rest_days": rest, "last_match": past[-1].date.date().isoformat() if past else None}


def h2h(matches: list[Match], a: str, b: str, at: datetime, n: int = 6) -> list[dict]:
    ms = sorted((m for m in matches if m.date < at and {m.home, m.away} == {a, b}), key=lambda m: m.date)[-n:]
    return [{"date": m.date.date().isoformat(), "home": m.home, "away": m.away, "score": f"{m.hg}-{m.ag}"} for m in ms]


def _ncdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def basketball(matches: list[Match], home: str, away: str, at: datetime, lines: dict | None = None) -> dict:
    past = [m for m in matches if m.date < at]
    hm = [m for m in past if m.home == home]
    am = [m for m in past if m.away == away]
    if len(past) < 30 or len(hm) < 5 or len(am) < 5:
        return {"insufficient": "Hacen falta al menos 30 partidos de la liga y 5 como local/visitante de cada equipo"}
    exp_h = (sum(m.hg for m in hm) / len(hm) + sum(m.hg for m in am) / len(am)) / 2
    exp_a = (sum(m.ag for m in am) / len(am) + sum(m.ag for m in hm) / len(hm)) / 2
    margins = [m.hg - m.ag for m in past]
    totals = [m.hg + m.ag for m in past]

    def sd(xs: list[float]) -> float:
        mu = sum(xs) / len(xs)
        return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))
    s_m, s_t = sd(margins), sd(totals)
    mu_m, mu_t = exp_h - exp_a, exp_h + exp_a
    probs = {"moneyline:home": 1 - _ncdf((0 - mu_m) / s_m)}
    probs["moneyline:away"] = 1 - probs["moneyline:home"]
    for ln in (lines or {}).get("total", []):
        probs[f"total:over:{ln:g}"] = 1 - _ncdf((ln - mu_t) / s_t)
        probs[f"total:under:{ln:g}"] = 1 - probs[f"total:over:{ln:g}"]
    for ln in (lines or {}).get("handicap", []):
        probs[f"handicap:home:{ln:g}"] = 1 - _ncdf((-ln - mu_m) / s_m)
        probs[f"handicap:away:{ln:g}"] = 1 - probs[f"handicap:home:{ln:g}"]
    return {"model": "normal_margen_v1", "probs": {k: round(v, 4) for k, v in probs.items()},
            "expected_points": {"home": round(exp_h, 1), "away": round(exp_a, 1)}, "sd_margin": round(s_m, 2), "sd_total": round(s_t, 2),
            "games_used": len(past), "intervals_80": {},
            "method": ("Puntos esperados = media de anotación del local en casa y del visitante fuera, combinada con lo que "
                       "encaja cada rival; margen y total ~ Normal con la desviación medida en la liga. No incluye lesiones, "
                       "descanso entre partidos ni ritmo; incertidumbre alta con pocos partidos.")}


def f1(recent: list[dict], drivers: list[str]) -> dict:
    """recent: [{"round": n, "results": [{"driver": "Verstappen", "points": 25}, ...]}] de carreras ya disputadas."""
    if len(recent) < 3:
        return {"insufficient": "Hacen falta al menos 3 carreras disputadas esta temporada"}
    pts: dict[str, float] = {}
    for i, race in enumerate(sorted(recent, key=lambda r: r["round"])[-8:]):
        w = 0.8 ** (len(recent[-8:]) - 1 - i)
        for r in race["results"]:
            pts[r["driver"]] = pts.get(r["driver"], 0) + w * float(r["points"])
    pool = drivers or list(pts)
    strength = {d: pts.get(d, 0.0) + 0.5 for d in pool}  # +0.5: nadie tiene probabilidad cero
    total = sum(strength.values())
    win = {d: s / total for d, s in strength.items()}
    # podio por simulación de Plackett-Luce
    rnd = random.Random(11)
    pod = {d: 0 for d in pool}
    N = 4000
    for _ in range(N):
        rest = dict(strength)
        for _ in range(min(3, len(rest))):
            r = rnd.random() * sum(rest.values())
            acc = 0.0
            for d, s in rest.items():
                acc += s
                if acc >= r:
                    pod[d] += 1
                    del rest[d]
                    break
    probs = {f"winner:{d}": round(p, 4) for d, p in win.items()} | {f"podium:{d}": round(c / N, 4) for d, c in pod.items()}
    return {"model": "plackett_luce_puntos_v1", "probs": probs, "races_used": min(len(recent), 8), "intervals_80": {},
            "method": ("Fuerza de cada piloto = puntos de las últimas 8 carreras (más peso a las recientes); probabilidad de "
                       "victoria proporcional a la fuerza y podio por simulación (Plackett-Luce). No contempla clasificación, "
                       "parrilla, meteorología ni fiabilidad: tómalo como orientación muy incierta.")}


def brier(pairs: list[tuple[float, int]]) -> float | None:
    return round(sum((p - o) ** 2 for p, o in pairs) / len(pairs), 4) if pairs else None


def log_loss(pairs: list[tuple[float, int]]) -> float | None:
    if not pairs:
        return None
    eps = 1e-6
    return round(-sum(o * math.log(max(p, eps)) + (1 - o) * math.log(max(1 - p, eps)) for p, o in pairs) / len(pairs), 4)


def calibration(pairs: list[tuple[float, int]], bins: int = 5) -> list[dict]:
    out = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        xs = [(p, o) for p, o in pairs if lo <= p < hi or (i == bins - 1 and p == 1)]
        if xs:
            out.append({"bin": f"{int(lo * 100)}-{int(hi * 100)} %", "n": len(xs), "predicted": round(sum(p for p, _ in xs) / len(xs), 3),
                        "observed": round(sum(o for _, o in xs) / len(xs), 3)})
    return out
