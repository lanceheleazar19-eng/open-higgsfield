"""Estrategias de VISTAN SIX. La MISMA función de decisión se usa en vivo (agente) y en la validación histórica, para que el
backtest mida exactamente lo que el agente hace. Solo se evalúan velas CERRADAS. Todas admiten LONG y SHORT."""

from __future__ import annotations

import math
import statistics

from atlas.desk import indicators as ind

FAMILIES = {
    "ema_trend": "Seguimiento de tendencia (cruce EMA + filtro de tendencia)",
    "meanrev": "Reversión a la media (Bollinger + RSI, entrada limitada)",
    "rsi_macd": "Combinada RSI + MACD",
    "breakout": "Breakout (canal de Donchian)",
    "momentum": "Momentum (ROC + MACD, salida por tiempo)",
    "ma_cross": "Cruce de medias simples (experimentación de parámetros y temporalidades)",
}


def warmup(family: str, p: dict) -> int:
    return int(max(p.get("slow", 0), p.get("n", 0), p.get("period", 0), 35)) + 20


def prepare(c: list[dict], family: str, p: dict) -> dict:
    cl = [x["close"] for x in c]
    a: dict = {"close": cl, "high": [x["high"] for x in c], "low": [x["low"] for x in c], "atr": ind.atr(c, 14)}
    if family == "ema_trend":
        a["f"], a["s"] = ind.ema(cl, p["fast"]), ind.ema(cl, p["slow"])
    elif family == "ma_cross":
        a["f"], a["s"] = ind.sma(cl, p["fast"]), ind.sma(cl, p["slow"])
    elif family == "meanrev":
        a["bb"], a["rsi"] = ind.bollinger(cl, p["period"], p["k"]), ind.rsi(cl, 14)
    elif family in ("rsi_macd", "momentum"):
        a["macd"], a["rsi"] = ind.macd(cl), ind.rsi(cl, 14)
    return a


def _cross(f: list, s: list, i: int) -> int:
    if i < 1 or None in (f[i], s[i], f[i - 1], s[i - 1]):
        return 0
    if f[i - 1] <= s[i - 1] and f[i] > s[i]:
        return 1
    if f[i - 1] >= s[i - 1] and f[i] < s[i]:
        return -1
    return 0


def decide(a: dict, i: int, family: str, p: dict) -> dict:
    """Decisión al CIERRE de la vela i. entry: long|short|None · exit_long/exit_short · order: market|limit."""
    cl, atr = a["close"], a["atr"][i]
    out = {"entry": None, "exit_long": False, "exit_short": False, "order": "market", "limit": None, "values": {"close": cl[i], "atr": atr}, "reason": ""}
    if atr is None:
        out["reason"] = "ATR aún no disponible"
        return out
    if family in ("ema_trend", "ma_cross"):
        f, s = a["f"], a["s"]
        x = _cross(f, s, i)
        out["values"].update(fast=f[i], slow=s[i])
        if x == 1 and (family == "ma_cross" or cl[i] > s[i]):
            out["entry"], out["reason"] = "long", f"Media rápida cruza por encima de la lenta ({f[i]:.4g} > {s[i]:.4g})"
        elif x == -1 and (family == "ma_cross" or cl[i] < s[i]):
            out["entry"], out["reason"] = "short", f"Media rápida cruza por debajo de la lenta ({f[i]:.4g} < {s[i]:.4g})"
        if f[i] is not None and s[i] is not None:
            out["exit_long"], out["exit_short"] = f[i] < s[i], f[i] > s[i]
    elif family == "meanrev":
        bb, r = a["bb"], a["rsi"][i]
        lo, mid, up = bb["lower"][i], bb["middle"][i], bb["upper"][i]
        out["values"].update(lower=lo, middle=mid, upper=up, rsi=r)
        if None not in (lo, up, r):
            if cl[i] < lo and r < p["rsi_low"]:
                out.update(entry="long", order="limit", limit=cl[i] - 0.1 * atr, reason=f"Cierre bajo la banda inferior y RSI {r:.1f} < {p['rsi_low']}")
            elif cl[i] > up and r > p["rsi_high"]:
                out.update(entry="short", order="limit", limit=cl[i] + 0.1 * atr, reason=f"Cierre sobre la banda superior y RSI {r:.1f} > {p['rsi_high']}")
            out["exit_long"], out["exit_short"] = cl[i] >= mid, cl[i] <= mid
            out["target"] = mid
    elif family == "rsi_macd":
        h, r = a["macd"]["hist"], a["rsi"][i]
        out["values"].update(macd_hist=h[i], rsi=r)
        if i >= 1 and None not in (h[i], h[i - 1], r):
            if h[i - 1] <= 0 < h[i] and 45 <= r <= 70:
                out["entry"], out["reason"] = "long", f"Histograma MACD pasa a positivo con RSI {r:.1f}"
            elif h[i - 1] >= 0 > h[i] and 30 <= r <= 55:
                out["entry"], out["reason"] = "short", f"Histograma MACD pasa a negativo con RSI {r:.1f}"
            out["exit_long"], out["exit_short"] = h[i] < 0, h[i] > 0
    elif family == "breakout":
        n, m = p["n"], p["exit_n"]
        if i >= n:
            hi, lo = max(a["high"][i - n:i]), min(a["low"][i - n:i])
            xlo, xhi = min(a["low"][i - m:i]), max(a["high"][i - m:i])
            out["values"].update(channel_high=hi, channel_low=lo)
            if cl[i] > hi:
                out["entry"], out["reason"] = "long", f"Ruptura del máximo de {n} velas ({hi:.4g})"
            elif cl[i] < lo:
                out["entry"], out["reason"] = "short", f"Ruptura del mínimo de {n} velas ({lo:.4g})"
            out["exit_long"], out["exit_short"] = cl[i] < xlo, cl[i] > xhi
    elif family == "momentum":
        n = p["n"]
        mc = a["macd"]
        if i >= n and None not in (mc["macd"][i], mc["signal"][i]):
            roc = (cl[i] / cl[i - n] - 1) * 100
            out["values"].update(roc_pct=roc, macd=mc["macd"][i], signal=mc["signal"][i])
            if roc > p["thr"] and mc["macd"][i] > mc["signal"][i]:
                out["entry"], out["reason"] = "long", f"Momentum {roc:.2f}% en {n} velas y MACD sobre su señal"
            elif roc < -p["thr"] and mc["macd"][i] < mc["signal"][i]:
                out["entry"], out["reason"] = "short", f"Momentum {roc:.2f}% en {n} velas y MACD bajo su señal"
            out["exit_long"], out["exit_short"] = roc < 0, roc > 0
    if out["entry"] is None and not out["reason"]:
        out["reason"] = "Sin señal en la última vela cerrada"
    return out


def levels(side: str, entry: float, atr: float, p: dict, target: float | None = None) -> tuple[float, float | None]:
    d = 1 if side == "long" else -1
    sl = entry - d * p.get("sl_atr", 2.0) * atr
    tp = None
    if target is not None and (target - entry) * d > 0.5 * atr:
        tp = target
    elif p.get("tp_atr"):
        tp = entry + d * p["tp_atr"] * atr
    return sl, tp


# ───────── métricas comunes (vivo y backtest) ─────────
def metrics(pnls: list[float], fees: float = 0.0, base: float | None = None, risks: list[float | None] | None = None) -> dict:
    n = len(pnls)
    if not n:
        return {"trades": 0, "verdict": "sin_datos", "verdict_text": "Sin operaciones cerradas todavía"}
    wins, losses = [x for x in pnls if x > 0], [x for x in pnls if x < 0]
    mean = sum(pnls) / n
    sd = statistics.stdev(pnls) if n > 1 else None
    t = mean / (sd / math.sqrt(n)) if sd else None
    cum, peak, mdd = 0.0, 0.0, 0.0
    for x in pnls:
        cum += x
        peak = max(peak, cum)
        mdd = max(mdd, peak - cum)
    half = n // 2
    h1 = sum(pnls[:half]) / half if half else None
    h2 = sum(pnls[half:]) / (n - half) if n - half else None
    pf = sum(wins) / -sum(losses) if losses else None
    rr = [x / r for x, r in zip(pnls, risks or []) if r]
    out = {"trades": n, "wins": len(wins), "losses": len(losses), "win_rate": round(len(wins) / n * 100, 1), "net": round(sum(pnls), 2),
           "profit_factor": round(pf, 2) if pf is not None else None, "expectancy": round(mean, 2), "expectancy_r": round(sum(rr) / len(rr), 3) if rr else None,
           "avg_win": round(sum(wins) / len(wins), 2) if wins else None, "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
           "std": round(sd, 2) if sd else None, "t_stat": round(t, 2) if t is not None else None, "max_dd": round(mdd, 2),
           "max_dd_pct": round(mdd / base * 100, 2) if base else None, "return_pct": round(sum(pnls) / base * 100, 3) if base else None,
           "costs": round(fees, 2), "first_half_exp": round(h1, 2) if h1 is not None else None, "second_half_exp": round(h2, 2) if h2 is not None else None}
    if n < 10:
        v, txt = "sin_datos", f"Solo {n} operaciones: sin base estadística"
    elif n < 30:
        v, txt = "insuficiente", f"{n} operaciones: muestra insuficiente (mínimo 30) para afirmar nada"
    elif mean <= 0 or (pf is not None and pf < 1):
        v, txt = "sin_ventaja", "Expectativa negativa o nula después de costes"
    elif (t or 0) < 2 or (pf or 0) < 1.2 or (h1 or 0) <= 0 or (h2 or 0) <= 0:
        v, txt = "no_significativa", "Expectativa positiva pero no significativa o inestable entre mitades"
    else:
        v, txt = "ventaja", f"Ventaja estadística después de costes (t = {t:.2f}, PF = {pf:.2f}, ambas mitades positivas)"
    return {**out, "verdict": v, "verdict_text": txt}


# ───────── simulación histórica de la misma lógica ─────────
def simulate(c: list[dict], family: str, p: dict, commission_pct: float, commission_fixed: float, slippage_bps: float,
             capital: float = 10_000.0, risk_pct: float = 1.0) -> list[dict]:
    """Recorre velas reales: decisión al cierre, ejecución en la apertura siguiente (o límite), SL/TP intravela
    (si SL y TP caen en la misma vela, se asume primero el SL: supuesto conservador) y costes por lado."""
    a = prepare(c, family, p)
    trades, pos, pend = [], None, None
    slip = slippage_bps / 10_000

    def fee(notional: float) -> float:
        return commission_fixed + notional * commission_pct / 100

    for i in range(warmup(family, p), len(c) - 1):
        nxt = c[i + 1]
        dec = decide(a, i, family, p)
        hit, px = None, None
        if pos:
            d = 1 if pos["side"] == "long" else -1
            bars = i - pos["i"]
            # 1) señal de salida al cierre de i → se ejecuta en la apertura de i+1 (antes de lo que ocurra dentro de esa vela)
            if (d == 1 and dec["exit_long"]) or (d == -1 and dec["exit_short"]) or (p.get("max_bars") and bars >= p["max_bars"]):
                hit, px = "signal", nxt["open"] * (1 - d * slip)
            # 2) si no, SL/TP dentro de la vela i+1 (SL primero si caen ambos: supuesto conservador)
            elif (d == 1 and nxt["low"] <= pos["sl"]) or (d == -1 and nxt["high"] >= pos["sl"]):
                hit, px = "stop_loss", pos["sl"] * (1 - d * slip)
            elif pos["tp"] is not None and ((d == 1 and nxt["high"] >= pos["tp"]) or (d == -1 and nxt["low"] <= pos["tp"])):
                hit, px = "take_profit", pos["tp"]
        if pos and hit:
            d = 1 if pos["side"] == "long" else -1
            gross = (px - pos["entry"]) * pos["qty"] * d
            f = pos["fee"] + fee(px * pos["qty"])
            trades.append({"side": pos["side"], "entry": pos["entry"], "exit": px, "pnl": gross - f, "fees": f, "risk": pos["risk"], "reason": hit, "bar": i + 1})
            pos = None
            continue
        if pend:  # orden limitada pendiente
            d = 1 if pend["side"] == "long" else -1
            if (d == 1 and nxt["low"] <= pend["limit"]) or (d == -1 and nxt["high"] >= pend["limit"]):
                pos = _open(pend["side"], pend["limit"], pend, i, capital + sum(t["pnl"] for t in trades), risk_pct, fee)
                pend = None
            elif i - pend["i"] >= 3:
                pend = None
            continue
        if not pos and dec["entry"] and dec["values"].get("atr"):
            sl, tp = levels(dec["entry"], dec["limit"] or nxt["open"], dec["values"]["atr"], p, dec.get("target"))
            plan = {"side": dec["entry"], "sl": sl, "tp": tp, "i": i, "limit": dec["limit"]}
            if dec["order"] == "limit":
                pend = plan
            else:
                d = 1 if dec["entry"] == "long" else -1
                pos = _open(dec["entry"], nxt["open"] * (1 + d * slip), plan, i, capital + sum(t["pnl"] for t in trades), risk_pct, fee)
    return trades


def _open(side: str, px: float, plan: dict, i: int, equity: float, risk_pct: float, fee) -> dict:  # noqa: ANN001
    risk_money = equity * risk_pct / 100
    dist = abs(px - plan["sl"]) or px * 0.01
    qty = risk_money / dist
    qty = min(qty, equity * 0.5 / px)
    return {"side": side, "entry": px, "qty": qty, "sl": plan["sl"], "tp": plan["tp"], "i": i, "fee": fee(px * qty), "risk": dist * qty}
