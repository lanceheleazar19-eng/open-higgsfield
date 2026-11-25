"""Indicadores técnicos sobre velas reales (listas alineadas con las velas; None donde aún no hay datos)."""

from __future__ import annotations


def sma(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = []
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        out.append(s / n if i >= n - 1 else None)
    return out


def ema(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = []
    k = 2 / (n + 1)
    prev = None
    for i, v in enumerate(values):
        if i < n - 1:
            out.append(None)
            continue
        if prev is None:
            prev = sum(values[i - n + 1:i + 1]) / n
        else:
            prev = v * k + prev * (1 - k)
        out.append(prev)
    return out


def rsi(values: list[float], n: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = values[i] - values[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    ag, al = gains / n, losses / n
    out[n] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(n + 1, len(values)):
        d = values[i] - values[i - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ef, es = ema(values, fast), ema(values, slow)
    line = [a - b if a is not None and b is not None else None for a, b in zip(ef, es)]
    start = next((i for i, v in enumerate(line) if v is not None), None)
    sig: list[float | None] = [None] * len(values)
    if start is not None:
        sub = ema([v for v in line[start:]], signal)  # type: ignore[misc]
        sig[start:] = sub
    hist = [a - b if a is not None and b is not None else None for a, b in zip(line, sig)]
    return {"macd": line, "signal": sig, "hist": hist}


def bollinger(values: list[float], n: int = 20, k: float = 2.0) -> dict:
    mid = sma(values, n)
    up: list[float | None] = []
    lo: list[float | None] = []
    for i, m in enumerate(mid):
        if m is None:
            up.append(None)
            lo.append(None)
            continue
        w = values[i - n + 1:i + 1]
        sd = (sum((x - m) ** 2 for x in w) / n) ** 0.5
        up.append(m + k * sd)
        lo.append(m - k * sd)
    return {"middle": mid, "upper": up, "lower": lo}


def atr(c: list[dict], n: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(c)
    trs = []
    for i, x in enumerate(c):
        pc = c[i - 1]["close"] if i else x["close"]
        trs.append(max(x["high"] - x["low"], abs(x["high"] - pc), abs(x["low"] - pc)))
    if len(c) < n:
        return out
    a = sum(trs[:n]) / n
    out[n - 1] = a
    for i in range(n, len(c)):
        a = (a * (n - 1) + trs[i]) / n
        out[i] = a
    return out


def vwap(c: list[dict]) -> list[float | None]:
    """VWAP acumulado que se reinicia cada día UTC."""
    out: list[float | None] = []
    pv = vol = 0.0
    day = None
    for x in c:
        d = x["time"] // 86400
        if d != day:
            pv = vol = 0.0
            day = d
        tp = (x["high"] + x["low"] + x["close"]) / 3
        pv += tp * (x.get("volume") or 0)
        vol += x.get("volume") or 0
        out.append(pv / vol if vol else None)
    return out


def snapshot(c: list[dict]) -> dict:
    """Lectura de los indicadores en la última vela (para el tutor). Solo números calculados."""
    if len(c) < 2:
        return {"velas": len(c)}
    closes = [x["close"] for x in c]
    last = lambda xs: next((v for v in reversed(xs) if v is not None), None)  # noqa: E731
    m = macd(closes)
    bb = bollinger(closes)
    r = {"velas": len(c), "ultimo_cierre": closes[-1], "cambio_pct_periodo": round((closes[-1] / closes[0] - 1) * 100, 2),
         "maximo_periodo": max(x["high"] for x in c), "minimo_periodo": min(x["low"] for x in c),
         "sma20": last(sma(closes, 20)), "sma50": last(sma(closes, 50)), "sma200": last(sma(closes, 200)),
         "ema20": last(ema(closes, 20)), "rsi14": last(rsi(closes)), "macd": last(m["macd"]), "macd_senal": last(m["signal"]),
         "bollinger_sup": last(bb["upper"]), "bollinger_inf": last(bb["lower"]), "atr14": last(atr(c))}
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()}
