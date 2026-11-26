"""Practical Lab: simuladores DETERMINISTAS con fórmulas visibles. Todo el dinero es VIRTUAL (nunca real) y ningún ejercicio
ejecuta operaciones reales: el trading educativo solo hace backtesting sobre datos históricos."""

from __future__ import annotations

import math
import random
import statistics

VIRTUAL = "Dinero VIRTUAL de práctica: no es dinero real ni se mueve ninguna cuenta."


# ───────── Finanzas ─────────
def compound(start: float, monthly: float, rate_pct: float, years: int, inflation_pct: float = 0) -> dict:
    r = rate_pct / 100 / 12
    bal, contributed, rows = start, start, []
    for m in range(1, years * 12 + 1):
        bal = bal * (1 + r) + monthly
        contributed += monthly
        if m % 12 == 0:
            real = bal / ((1 + inflation_pct / 100) ** (m / 12))
            rows.append({"year": m // 12, "balance": round(bal, 2), "contributed": round(contributed, 2), "interest": round(bal - contributed, 2), "real": round(real, 2)})
    return {"rows": rows, "final": rows[-1] if rows else None, "formula": "Saldo(mes) = Saldo(mes-1) × (1 + r/12) + aportación", "note": VIRTUAL}


def budget(income: float, needs: float, wants: float, savings: float) -> dict:
    tot = needs + wants + savings
    pct = {k: round(v / income * 100, 1) if income else None for k, v in (("necesidades", needs), ("deseos", wants), ("ahorro", savings))}
    ref = {"necesidades": 50, "deseos": 30, "ahorro": 20}
    return {"percent": pct, "reference_50_30_20": ref, "unassigned": round(income - tot, 2),
            "observations": [f"{k}: {v} % frente al {ref[k]} % de referencia" for k, v in pct.items() if v is not None and abs(v - ref[k]) >= 10],
            "note": "La regla 50/30/20 es una heurística orientativa, no una norma. " + VIRTUAL}


def risk_return(amount: float, mean_pct: float, vol_pct: float, years: int, runs: int = 1000, seed: int = 7) -> dict:
    """Monte Carlo con rentabilidades anuales normales (modelo didáctico simplificado; los mercados reales no son normales)."""
    rnd = random.Random(seed)
    finals = []
    for _ in range(runs):
        v = amount
        for _y in range(years):
            v *= max(0.0, 1 + rnd.gauss(mean_pct / 100, vol_pct / 100))
        finals.append(v)
    finals.sort()
    q = lambda p: round(finals[int(p * (runs - 1))], 2)  # noqa: E731
    return {"p5": q(0.05), "p25": q(0.25), "median": q(0.5), "p75": q(0.75), "p95": q(0.95), "loss_prob_pct": round(sum(1 for f in finals if f < amount) / runs * 100, 1),
            "runs": runs, "seed": seed, "model": "Rentabilidad anual ~ Normal(media, volatilidad), independiente cada año", "note": VIRTUAL}


# ───────── Empresa ─────────
def business_round(s: dict) -> dict:
    """Demanda didáctica: base × (precio_competencia/precio)^elasticidad × (1 + ln(1 + marketing/1000) × 0,15). Fórmula visible."""
    price, cost, fixed = float(s["price"]), float(s["unit_cost"]), float(s["fixed_costs"])
    mkt, base, comp, el = float(s.get("marketing", 0)), float(s["market_demand"]), float(s["competitor_price"]), float(s.get("elasticity", 1.5))
    units = max(0.0, base * (comp / price) ** el * (1 + math.log1p(mkt / 1000) * 0.15)) if price > 0 else 0.0
    units = math.floor(units)
    revenue, var = units * price, units * cost
    margin_u = price - cost
    profit = revenue - var - fixed - mkt
    be = math.ceil((fixed + mkt) / margin_u) if margin_u > 0 else None
    return {"units": units, "revenue": round(revenue, 2), "variable_costs": round(var, 2), "gross_margin_pct": round(margin_u / price * 100, 1) if price else None,
            "profit": round(profit, 2), "break_even_units": be, "price_vs_competitor_pct": round((price / comp - 1) * 100, 1) if comp else None,
            "formula": "Unidades = demanda base × (precio competencia / tu precio)^elasticidad × (1 + 0,15·ln(1 + marketing/1000))",
            "note": "Modelo didáctico simplificado, no una predicción real. " + VIRTUAL}


def business_eval(rounds: list[dict]) -> dict:
    if not rounds:
        return {}
    profits = [r["result"]["profit"] for r in rounds]
    trend = "mejora" if len(profits) > 1 and profits[-1] > profits[0] else "empeora" if len(profits) > 1 and profits[-1] < profits[0] else "estable"
    score = max(0, min(100, 50 + (sum(1 for p in profits if p > 0) / len(profits)) * 40 + (10 if trend == "mejora" else 0)))
    return {"total_profit": round(sum(profits), 2), "profitable_rounds": sum(1 for p in profits if p > 0), "trend": trend, "score": round(score, 1),
            "rule": "50 base + 40 × proporción de rondas con beneficio + 10 si el beneficio mejora de la primera a la última ronda"}


# ───────── Trading (solo backtesting educativo) ─────────
def sma(xs: list[float], n: int) -> list[float | None]:
    return [None if i + 1 < n else sum(xs[i + 1 - n:i + 1]) / n for i in range(len(xs))]


def rsi(xs: list[float], n: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(xs)
    for i in range(n, len(xs)):
        g = [max(0, xs[j] - xs[j - 1]) for j in range(i - n + 1, i + 1)]
        lo = [max(0, xs[j - 1] - xs[j]) for j in range(i - n + 1, i + 1)]
        ag, al = sum(g) / n, sum(lo) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def backtest(closes: list[float], strategy: str, fast: int = 10, slow: int = 30, capital: float = 10000, risk_pct: float = 100) -> dict:
    if len(closes) < max(slow, 15) + 5:
        raise ValueError(f"Se necesitan al menos {max(slow, 15) + 5} precios de cierre")
    sig: list[int] = []
    if strategy == "sma":
        f, s = sma(closes, fast), sma(closes, slow)
        sig = [1 if (f[i] is not None and s[i] is not None and f[i] > s[i]) else 0 for i in range(len(closes))]
    else:
        r = rsi(closes)
        pos = 0
        for v in r:
            if v is not None and v < 30:
                pos = 1
            elif v is not None and v > 70:
                pos = 0
            sig.append(pos)
    cash, units, equity, trades, entry = capital, 0.0, [], [], None
    alloc = max(1.0, min(100.0, risk_pct)) / 100
    for i, p in enumerate(closes):
        want = sig[i - 1] if i else 0  # se opera con la señal del cierre ANTERIOR (sin mirar el futuro)
        if want and not units:
            units = (cash * alloc) / p
            cash -= units * p
            entry = p
        elif not want and units:
            cash += units * p
            trades.append({"entry": round(entry, 4), "exit": round(p, 4), "ret_pct": round((p / entry - 1) * 100, 2)})
            units = 0.0
        equity.append(cash + units * p)
    peak, mdd = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak * 100)
    rets = [t["ret_pct"] for t in trades]
    return {"strategy": strategy, "final_equity": round(equity[-1], 2), "return_pct": round((equity[-1] / capital - 1) * 100, 2),
            "buy_hold_pct": round((closes[-1] / closes[0] - 1) * 100, 2), "max_drawdown_pct": round(mdd, 2), "trades": len(trades),
            "win_rate_pct": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1) if rets else None,
            "avg_trade_pct": round(statistics.mean(rets), 2) if rets else None, "equity": [round(v, 2) for v in equity][-300:], "trade_list": trades[-30:],
            "note": "Backtesting educativo: resultados pasados no predicen resultados futuros; sin comisiones ni deslizamiento. " + VIRTUAL
                    + " Nunca se ejecutan órdenes reales desde la academia."}
