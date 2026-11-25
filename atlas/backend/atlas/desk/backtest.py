"""Backtesting sobre velas históricas reales. Ejecución en la apertura de la vela siguiente a la señal,
con comisión y deslizamiento. Solo largo (las estrategias cortas se pueden añadir con el mismo motor).
Los resultados históricos NO garantizan resultados futuros."""

from __future__ import annotations

from atlas.desk import indicators as ind

STRATEGIES = {
    "sma_cross": {"name": "Cruce de medias simples", "params": {"fast": 20, "slow": 50},
                  "help": "Compra cuando la media rápida cruza por encima de la lenta; vende cuando cruza por debajo."},
    "ema_cross": {"name": "Cruce de medias exponenciales", "params": {"fast": 12, "slow": 26},
                  "help": "Como el cruce de medias, pero las EMA reaccionan antes a los cambios de precio."},
    "rsi_reversion": {"name": "Reversión con RSI", "params": {"period": 14, "low": 30, "high": 55},
                      "help": "Compra cuando el RSI cae por debajo de «low» (sobreventa) y vende cuando supera «high»."},
    "bollinger": {"name": "Rebote en Bandas de Bollinger", "params": {"period": 20, "k": 2.0},
                  "help": "Compra al cerrar por debajo de la banda inferior y vende al volver a la media."},
    "breakout": {"name": "Ruptura de máximos (Donchian)", "params": {"entry": 20, "exit": 10},
                 "help": "Compra al superar el máximo de N velas y vende al perder el mínimo de M velas."},
    "buy_hold": {"name": "Comprar y mantener (referencia)", "params": {},
                 "help": "Compra en la primera vela y mantiene: sirve para comparar."},
}


def _signals(c: list[dict], strategy: str, p: dict) -> list[int]:
    """+1 entrar, -1 salir, 0 nada (señal al cierre de cada vela)."""
    cl = [x["close"] for x in c]
    n = len(c)
    s = [0] * n
    if strategy in ("sma_cross", "ema_cross"):
        f = (ind.sma if strategy == "sma_cross" else ind.ema)(cl, int(p["fast"]))
        sl = (ind.sma if strategy == "sma_cross" else ind.ema)(cl, int(p["slow"]))
        for i in range(1, n):
            if None in (f[i], sl[i], f[i - 1], sl[i - 1]):
                continue
            if f[i - 1] <= sl[i - 1] and f[i] > sl[i]:
                s[i] = 1
            elif f[i - 1] >= sl[i - 1] and f[i] < sl[i]:
                s[i] = -1
    elif strategy == "rsi_reversion":
        r = ind.rsi(cl, int(p["period"]))
        for i in range(n):
            if r[i] is None:
                continue
            if r[i] < float(p["low"]):
                s[i] = 1
            elif r[i] > float(p["high"]):
                s[i] = -1
    elif strategy == "bollinger":
        b = ind.bollinger(cl, int(p["period"]), float(p["k"]))
        for i in range(n):
            if b["lower"][i] is None:
                continue
            if cl[i] < b["lower"][i]:
                s[i] = 1
            elif cl[i] >= b["middle"][i]:
                s[i] = -1
    elif strategy == "breakout":
        e, x = int(p["entry"]), int(p["exit"])
        for i in range(max(e, x), n):
            if c[i]["close"] > max(k["high"] for k in c[i - e:i]):
                s[i] = 1
            elif c[i]["close"] < min(k["low"] for k in c[i - x:i]):
                s[i] = -1
    elif strategy == "buy_hold":
        s[0] = 1
    else:
        raise ValueError("Estrategia desconocida")
    return s


def run(c: list[dict], strategy: str, params: dict | None = None, capital: float = 10_000.0, commission_pct: float = 0.1,
        slippage_bps: float = 5.0, position_pct: float = 100.0) -> dict:
    if len(c) < 30:
        raise ValueError("Hacen falta al menos 30 velas históricas para un backtest")
    p = {**STRATEGIES[strategy]["params"], **(params or {})}
    sig = _signals(c, strategy, p)
    cash, qty, entry, entry_t = capital, 0.0, 0.0, None
    trades, curve = [], []
    peak, mdd = capital, 0.0
    for i in range(len(c)):
        # la señal de la vela i-1 se ejecuta en la apertura de la vela i
        if i > 0 and sig[i - 1] == 1 and qty == 0:
            px = c[i]["open"] * (1 + slippage_bps / 10_000)
            budget = cash * position_pct / 100
            qty = budget / (px * (1 + commission_pct / 100))
            fee = qty * px * commission_pct / 100
            cash -= qty * px + fee
            entry, entry_t = px, c[i]["time"]
            entry_fee = fee
        elif i > 0 and sig[i - 1] == -1 and qty > 0:
            px = c[i]["open"] * (1 - slippage_bps / 10_000)
            fee = qty * px * commission_pct / 100
            cash += qty * px - fee
            trades.append({"entry_t": entry_t, "exit_t": c[i]["time"], "entry": round(entry, 6), "exit": round(px, 6),
                           "pnl": round((px - entry) * qty - fee - entry_fee, 2), "ret_pct": round((px / entry - 1) * 100, 3)})
            qty = 0.0
        eq = cash + qty * c[i]["close"]
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak * 100 if peak else 0)
        curve.append({"time": c[i]["time"], "equity": round(eq, 2)})
    final = curve[-1]["equity"]
    pnls = [t["pnl"] for t in trades]
    wins, losses = [x for x in pnls if x > 0], [x for x in pnls if x < 0]
    bh = (c[-1]["close"] / c[0]["open"] - 1) * 100
    return {"strategy": strategy, "strategy_name": STRATEGIES[strategy]["name"], "params": p, "capital": capital,
            "final_equity": final, "return_pct": round((final / capital - 1) * 100, 2), "max_drawdown_pct": round(mdd, 2),
            "trades": len(trades), "win_rate": round(len(wins) / len(trades) * 100, 2) if trades else None,
            "profit_factor": round(sum(wins) / -sum(losses), 2) if losses else (None if not wins else "∞"),
            "open_at_end": qty > 0, "buy_hold_pct": round(bh, 2), "bars": len(c),
            "from": c[0]["time"], "to": c[-1]["time"], "curve": curve[:: max(1, len(curve) // 600)], "trade_list": trades[-200:],
            "warning": "Resultados sobre datos históricos: NO garantizan resultados futuros. Incluye costes simulados, "
                       "pero no el impacto real en el mercado, huecos de precio ni cambios de liquidez."}
