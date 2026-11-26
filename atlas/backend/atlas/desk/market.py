"""Datos de mercado para la Trading Desk. Nunca se inventan cotizaciones: si ningún proveedor responde,
el precio es None y la interfaz muestra N/D. Cada dato indica su fuente y su tipo:

- realtime   → tiempo real (Binance para cripto; Finnhub para acciones de EE. UU. en su plan gratuito)
- delayed    → con retraso (Stooq ~15-20 min o cierre; Alpha Vantage: último día de negociación)
- plan       → tiempo real o con retraso según tu plan (Twelve Data)
- historical → velas históricas

Las claves de API se guardan en el llavero del sistema (nunca en la base de datos ni en el código)."""

from __future__ import annotations

import csv
import io
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from atlas.integrations.secrets import get_secret

TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]
TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800, "1M": 2592000}
CLASSES = {"index": "Índices", "stock": "Acciones", "forex": "Forex", "crypto": "Cripto", "commodity": "Materias primas", "etf": "ETFs"}
KIND_LABEL = {"realtime": "Tiempo real", "delayed": "Con retraso", "plan": "Tiempo real o retraso (según plan)",
              "historical": "Histórico", "none": "Sin datos"}


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    cls: str
    ccy: str  # divisa de cotización
    binance: str | None = None
    stooq: str | None = None
    td: str | None = None  # Twelve Data
    finnhub: str | None = None
    av: str | None = None  # Alpha Vantage
    custom: bool = False


def _stock(sym: str, name: str, cls: str = "stock") -> Instrument:
    return Instrument(sym, name, cls, "USD", stooq=f"{sym.lower()}.us", td=sym, finnhub=sym, av=sym)


def _crypto(base: str, name: str) -> Instrument:
    return Instrument(f"{base}/USDT", name, "crypto", "USD", binance=f"{base}USDT", td=f"{base}/USD")


def _fx(a: str, b: str) -> Instrument:
    return Instrument(f"{a}/{b}", f"{a}/{b}", "forex", b, stooq=f"{a}{b}".lower(), td=f"{a}/{b}")


CATALOG: list[Instrument] = [
    Instrument("SPX", "S&P 500", "index", "USD", stooq="^spx"),
    Instrument("NDX", "Nasdaq 100", "index", "USD", stooq="^ndx"),
    Instrument("DJI", "Dow Jones", "index", "USD", stooq="^dji"),
    Instrument("DAX", "DAX 40", "index", "EUR", stooq="^dax"),
    Instrument("N225", "Nikkei 225", "index", "JPY", stooq="^nkx"),
    _stock("AAPL", "Apple"), _stock("MSFT", "Microsoft"), _stock("NVDA", "NVIDIA"), _stock("TSLA", "Tesla"),
    _stock("AMZN", "Amazon"), _stock("GOOGL", "Alphabet"), _stock("META", "Meta Platforms"),
    _fx("EUR", "USD"), _fx("GBP", "USD"), _fx("USD", "JPY"), _fx("EUR", "GBP"), _fx("USD", "CHF"),
    _crypto("BTC", "Bitcoin"), _crypto("ETH", "Ethereum"), _crypto("SOL", "Solana"), _crypto("BNB", "BNB"), _crypto("XRP", "XRP"),
    Instrument("XAU/USD", "Oro", "commodity", "USD", stooq="xauusd", td="XAU/USD"),
    Instrument("XAG/USD", "Plata", "commodity", "USD", stooq="xagusd", td="XAG/USD"),
    Instrument("WTI", "Petróleo WTI (futuro)", "commodity", "USD", stooq="cl.f"),
    Instrument("NG", "Gas natural (futuro)", "commodity", "USD", stooq="ng.f"),
    _stock("SPY", "SPDR S&P 500 ETF", "etf"), _stock("QQQ", "Invesco QQQ", "etf"), _stock("GLD", "SPDR Gold", "etf"),
    _stock("IWM", "iShares Russell 2000", "etf"), _stock("VTI", "Vanguard Total Market", "etf"),
]
POPULAR = ["BTC/USDT", "NVDA", "SPY", "EUR/USD", "XAU/USD", "TSLA"]


def custom_instrument(symbol: str, name: str, cls: str, ccy: str) -> Instrument:
    s = symbol.upper().strip()
    if cls == "crypto":
        base = s.split("/")[0]
        return Instrument(f"{base}/USDT", name or base, "crypto", "USD", binance=f"{base}USDT", td=f"{base}/USD", custom=True)
    if cls == "forex" and "/" in s:
        a, b = s.split("/", 1)
        return Instrument(s, name or s, "forex", b, stooq=f"{a}{b}".lower(), td=s, custom=True)
    return Instrument(s, name or s, cls, ccy.upper(), stooq=f"{s.lower()}.us" if ccy.upper() == "USD" else None,
                      td=s, finnhub=s, av=s, custom=True)


def instruments(db=None) -> dict[str, Instrument]:
    out = {i.symbol: i for i in CATALOG}
    if db is not None:
        from sqlalchemy import select

        from atlas.models import TdInstrument
        for c in db.scalars(select(TdInstrument)):
            inst = custom_instrument(c.symbol, c.name, c.cls, c.ccy)
            out.setdefault(inst.symbol, inst)
    return out


# ───────────────────────── Proveedores ─────────────────────────

class DataError(RuntimeError):
    pass


PROVIDERS = {
    "binance": {"name": "Binance (cripto)", "key": None, "kind": "realtime", "url": "https://api.binance.com",
                "covers": "Criptomonedas: precio, volumen y velas en todas las temporalidades", "limits": "Público, sin clave (límite por IP muy amplio)"},
    "finnhub": {"name": "Finnhub", "key": "finnhub_api_key", "kind": "realtime", "url": "https://finnhub.io",
                "covers": "Cotización de acciones y ETF de EE. UU., noticias financieras, calendario económico (según plan)",
                "limits": "Gratis: 60 peticiones/minuto. Velas y calendario económico requieren plan de pago"},
    "twelvedata": {"name": "Twelve Data", "key": "twelvedata_api_key", "kind": "plan", "url": "https://twelvedata.com",
                   "covers": "Acciones, ETF, forex, cripto y metales: cotizaciones y velas en todas las temporalidades",
                   "limits": "Gratis: 8 peticiones/minuto y 800/día"},
    "alphavantage": {"name": "Alpha Vantage", "key": "alphavantage_api_key", "kind": "delayed", "url": "https://www.alphavantage.co",
                     "covers": "Cotización diaria de acciones, velas diarias, noticias con sentimiento e indicadores macro (IPC, tipos, empleo)",
                     "limits": "Gratis: 25 peticiones/día"},
    "stooq": {"name": "Stooq", "key": None, "kind": "delayed", "url": "https://stooq.com",
              "covers": "Índices, acciones, ETF, forex y materias primas con retraso; velas diarias/semanales/mensuales",
              "limits": "Público, sin clave; datos con retraso o al cierre"},
}

_stats: dict[str, dict] = {p: {"ok": 0, "errors": 0, "last_error": None, "last_ms": None, "last_at": None} for p in PROVIDERS}
_cache: dict[tuple, tuple[float, object]] = {}


def has_key(provider: str) -> bool:
    k = PROVIDERS[provider]["key"]
    return k is None or bool(get_secret(k))


def _key(provider: str) -> str:
    k = get_secret(PROVIDERS[provider]["key"]) if PROVIDERS[provider]["key"] else None
    if PROVIDERS[provider]["key"] and not k:
        raise DataError(f"{PROVIDERS[provider]['name']}: falta la API key")
    return k or ""


def _get(provider: str, url: str, params: dict | None = None, timeout: float = 8.0, headers: dict | None = None) -> httpx.Response:
    t0 = time.perf_counter()
    st = _stats[provider]
    try:
        r = httpx.get(url, params=params, timeout=timeout, headers={"User-Agent": "VISTAN-TradingDesk/1.0", **(headers or {})})
    except httpx.HTTPError as exc:
        st.update(errors=st["errors"] + 1, last_error=f"sin conexión ({type(exc).__name__})", last_at=time.time())
        raise DataError(f"{PROVIDERS[provider]['name']}: sin conexión") from exc
    ms = round((time.perf_counter() - t0) * 1000)
    if r.status_code == 429:
        st.update(errors=st["errors"] + 1, last_error="límite de uso alcanzado (429)", last_ms=ms, last_at=time.time())
        raise DataError(f"{PROVIDERS[provider]['name']}: límite de uso alcanzado")
    if r.status_code in (401, 403):
        st.update(errors=st["errors"] + 1, last_error=f"acceso denegado ({r.status_code}): clave o plan", last_ms=ms, last_at=time.time())
        raise DataError(f"{PROVIDERS[provider]['name']}: acceso denegado (clave inválida o función de pago)")
    if r.status_code >= 400:
        st.update(errors=st["errors"] + 1, last_error=f"HTTP {r.status_code}", last_ms=ms, last_at=time.time())
        raise DataError(f"{PROVIDERS[provider]['name']}: error {r.status_code}")
    st.update(ok=st["ok"] + 1, last_ms=ms, last_at=time.time(), last_error=None)
    return r


def _fail(provider: str, msg: str) -> DataError:
    _stats[provider].update(errors=_stats[provider]["errors"] + 1, last_error=msg[:160], last_at=time.time())
    return DataError(f"{PROVIDERS[provider]['name']}: {msg}")


def _cached(key: tuple, ttl: float, fn):
    hit = _cache.get(key)
    now = time.time()
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


def clear_cache() -> None:
    _cache.clear()


def _f(v) -> float | None:
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


# ── Binance ──
BINANCE_HOSTS = ["https://api.binance.com", "https://data-api.binance.vision"]
BINANCE_TF = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w", "1M": "1M"}


def _binance_get(path: str, params: dict) -> httpx.Response:
    last: DataError | None = None
    for host in BINANCE_HOSTS:
        try:
            return _get("binance", f"{host}{path}", params)
        except DataError as exc:
            last = exc
    raise last or DataError("Binance: sin conexión")


def binance_quotes(syms: list[str]) -> dict[str, dict]:
    import json as _json
    r = _binance_get("/api/v3/ticker/24hr", {"symbols": _json.dumps(syms, separators=(",", ":"))})
    out = {}
    for d in r.json():
        out[d["symbol"]] = {"price": _f(d.get("lastPrice")), "change_pct": _f(d.get("priceChangePercent")),
                            "volume": _f(d.get("quoteVolume")), "volume_unit": "USDT",
                            "ts": int(d.get("closeTime", 0)) // 1000 or None, "open": True}
    return out


def binance_candles(sym: str, tf: str, limit: int = 500, start: int | None = None, end: int | None = None) -> list[dict]:
    params: dict = {"symbol": sym, "interval": BINANCE_TF[tf], "limit": min(limit, 1000)}
    if start:
        params["startTime"] = start * 1000
    if end:
        params["endTime"] = end * 1000
    rows = _binance_get("/api/v3/klines", params).json()
    return [{"time": int(k[0]) // 1000, "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
             "close": float(k[4]), "volume": float(k[5])} for k in rows]


# ── Stooq ──
def stooq_quotes(syms: list[str]) -> dict[str, dict]:
    r = _get("stooq", "https://stooq.com/q/l/", {"s": " ".join(syms), "f": "sd2t2ohlcv", "h": "", "e": "csv"})
    out = {}
    for row in csv.DictReader(io.StringIO(r.text)):
        sym = (row.get("Symbol") or "").lower()
        close = _f(row.get("Close"))
        if not sym or close is None:
            continue
        ts = None
        try:
            ts = int(datetime.strptime(f"{row['Date']} {row['Time']}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
        except (KeyError, ValueError):
            pass
        op = _f(row.get("Open"))
        out[sym] = {"price": close, "change_pct": round((close - op) / op * 100, 3) if op else None,
                    "change_basis": "desde la apertura", "volume": _f(row.get("Volume")), "ts": ts}
    return out


STOOQ_TF = {"1d": "d", "1w": "w", "1M": "m"}


def stooq_candles(sym: str, tf: str) -> list[dict]:
    if tf not in STOOQ_TF:
        raise DataError("Stooq solo ofrece velas diarias, semanales y mensuales")
    r = _get("stooq", "https://stooq.com/q/d/l/", {"s": sym, "i": STOOQ_TF[tf]})
    rows = []
    for row in csv.DictReader(io.StringIO(r.text)):
        try:
            t = int(datetime.strptime(row["Date"], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
            rows.append({"time": t, "open": float(row["Open"]), "high": float(row["High"]), "low": float(row["Low"]),
                         "close": float(row["Close"]), "volume": _f(row.get("Volume")) or 0.0})
        except (KeyError, ValueError):
            continue
    if not rows:
        raise _fail("stooq", "sin datos para este símbolo (o Stooq ha pedido verificación)")
    return rows


# ── Twelve Data ──
TD_TF = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day", "1w": "1week", "1M": "1month"}


def _td_check(d: dict) -> dict:
    if isinstance(d, dict) and d.get("status") == "error":
        raise _fail("twelvedata", str(d.get("message") or "error")[:160])
    return d


def td_quote(sym: str) -> dict:
    d = _td_check(_get("twelvedata", "https://api.twelvedata.com/quote", {"symbol": sym, "apikey": _key("twelvedata")}).json())
    return {"price": _f(d.get("close")), "change_pct": _f(d.get("percent_change")), "volume": _f(d.get("volume")),
            "ts": int(d["timestamp"]) if d.get("timestamp") else None, "open": d.get("is_market_open")}


def td_candles(sym: str, tf: str, limit: int = 500, start: str | None = None, end: str | None = None) -> list[dict]:
    params = {"symbol": sym, "interval": TD_TF[tf], "outputsize": min(limit, 5000), "timezone": "UTC", "apikey": _key("twelvedata")}
    if start:
        params["start_date"] = start
    if end:
        params["end_date"] = end
    d = _td_check(_get("twelvedata", "https://api.twelvedata.com/time_series", params, timeout=15).json())
    out = []
    for v in reversed(d.get("values") or []):
        fmt = "%Y-%m-%d %H:%M:%S" if " " in v["datetime"] else "%Y-%m-%d"
        t = int(datetime.strptime(v["datetime"], fmt).replace(tzinfo=timezone.utc).timestamp())
        out.append({"time": t, "open": float(v["open"]), "high": float(v["high"]), "low": float(v["low"]),
                    "close": float(v["close"]), "volume": _f(v.get("volume")) or 0.0})
    return out


# ── Finnhub ──
def finnhub_quote(sym: str) -> dict:
    d = _get("finnhub", "https://finnhub.io/api/v1/quote", {"symbol": sym}, headers={"X-Finnhub-Token": _key("finnhub")}).json()
    if not d or not d.get("c"):
        raise _fail("finnhub", f"sin cotización para {sym}")
    return {"price": _f(d["c"]), "change_pct": _f(d.get("dp")), "volume": None, "ts": int(d["t"]) if d.get("t") else None}


# ── Alpha Vantage ──
def _av(params: dict, timeout: float = 15.0) -> dict:
    d = _get("alphavantage", "https://www.alphavantage.co/query", {**params, "apikey": _key("alphavantage")}, timeout=timeout).json()
    for k in ("Note", "Information", "Error Message"):
        if isinstance(d, dict) and k in d:
            raise _fail("alphavantage", str(d[k])[:160])
    return d


def av_quote(sym: str) -> dict:
    q = _av({"function": "GLOBAL_QUOTE", "symbol": sym}).get("Global Quote") or {}
    if not q.get("05. price"):
        raise _fail("alphavantage", f"sin cotización para {sym}")
    pct = (q.get("10. change percent") or "").rstrip("%")
    day = q.get("07. latest trading day")
    ts = int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) if day else None
    return {"price": _f(q["05. price"]), "change_pct": _f(pct), "volume": _f(q.get("06. volume")), "ts": ts}


def av_candles_daily(sym: str) -> list[dict]:
    d = _av({"function": "TIME_SERIES_DAILY", "symbol": sym, "outputsize": "compact"})
    series = d.get("Time Series (Daily)") or {}
    out = []
    for day, v in sorted(series.items()):
        t = int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        out.append({"time": t, "open": float(v["1. open"]), "high": float(v["2. high"]), "low": float(v["3. low"]),
                    "close": float(v["4. close"]), "volume": _f(v.get("5. volume")) or 0.0})
    return out


# ───────────────────────── API de alto nivel ─────────────────────────

def _quote_one(inst: Instrument) -> dict:
    """Mejor fuente disponible para un activo (la más actual primero)."""
    errors = []
    attempts: list = []
    if inst.binance:
        attempts.append(("binance", lambda: binance_quotes([inst.binance])[inst.binance]))
    if inst.finnhub and has_key("finnhub"):
        attempts.append(("finnhub", lambda: finnhub_quote(inst.finnhub)))
    if inst.td and has_key("twelvedata"):
        attempts.append(("twelvedata", lambda: td_quote(inst.td)))
    if inst.stooq:
        attempts.append(("stooq", lambda: stooq_quotes([inst.stooq])[inst.stooq]))
    if inst.av and has_key("alphavantage"):
        attempts.append(("alphavantage", lambda: av_quote(inst.av)))
    for prov, fn in attempts:
        try:
            q = fn()
            if q.get("price") is not None:
                return {**q, "source": prov, "kind": PROVIDERS[prov]["kind"]}
        except (DataError, KeyError) as exc:
            errors.append(str(exc) if isinstance(exc, DataError) else f"{PROVIDERS[prov]['name']}: sin datos")
    return {"price": None, "change_pct": None, "volume": None, "ts": None, "source": None, "kind": "none",
            "error": "; ".join(errors) if errors else "Ningún proveedor conectado cubre este activo"}


def quote(inst: Instrument, ttl: float | None = None) -> dict:
    t = ttl if ttl is not None else (10 if inst.binance else 30)
    q = _cached(("q", inst.symbol), t, lambda: _quote_one(inst))
    return {"symbol": inst.symbol, **q}


def quotes(insts: list[Instrument]) -> dict[str, dict]:
    """Cotizaciones en lote: una petición para toda la cripto (Binance) y otra para el resto (Stooq);
    lo que falte se completa activo a activo con los proveedores con clave."""
    out: dict[str, dict] = {}
    now = time.time()
    pending = []
    for i in insts:
        hit = _cache.get(("q", i.symbol))
        if hit and now - hit[0] < (10 if i.binance else 30):
            out[i.symbol] = {"symbol": i.symbol, **hit[1]}
        else:
            pending.append(i)
    bn = [i for i in pending if i.binance]
    if bn:
        try:
            res = binance_quotes([i.binance for i in bn])
            for i in bn:
                if i.binance in res:
                    q = {**res[i.binance], "source": "binance", "kind": "realtime"}
                    _cache[("q", i.symbol)] = (now, q)
                    out[i.symbol] = {"symbol": i.symbol, **q}
        except DataError:
            pass
    st = [i for i in pending if i.symbol not in out and i.stooq]
    if st:
        try:
            res = stooq_quotes([i.stooq for i in st])
            for i in st:
                if i.stooq in res:
                    q = {**res[i.stooq], "source": "stooq", "kind": "delayed"}
                    _cache[("q", i.symbol)] = (now, q)
                    out[i.symbol] = {"symbol": i.symbol, **q}
        except DataError:
            pass
    for i in pending:
        if i.symbol not in out:
            if i.finnhub and has_key("finnhub"):
                out[i.symbol] = quote(i)
            else:
                out[i.symbol] = {"symbol": i.symbol, "price": None, "change_pct": None, "volume": None, "ts": None,
                                 "source": None, "kind": "none", "error": "Sin datos: ningún proveedor ha respondido"}
    return out


def candles(inst: Instrument, tf: str, limit: int = 500) -> dict:
    if tf not in TF_SECONDS:
        raise DataError("Temporalidad no válida")
    errors = []

    def attempt(prov: str, fn):
        try:
            rows = fn()
            if rows:
                return {"candles": rows, "source": prov, "kind": PROVIDERS[prov]["kind"]}
            errors.append(f"{PROVIDERS[prov]['name']}: sin velas")
        except DataError as exc:
            errors.append(str(exc))
        return None

    def load():
        if inst.binance:
            r = attempt("binance", lambda: binance_candles(inst.binance, tf, limit))
            if r:
                return r
        if inst.td and has_key("twelvedata"):
            r = attempt("twelvedata", lambda: td_candles(inst.td, tf, limit))
            if r:
                return r
        if inst.stooq and tf in STOOQ_TF:
            r = attempt("stooq", lambda: stooq_candles(inst.stooq, tf)[-limit:])
            if r:
                return r
        if inst.av and tf == "1d" and has_key("alphavantage"):
            r = attempt("alphavantage", lambda: av_candles_daily(inst.av))
            if r:
                return r
        if tf not in STOOQ_TF and not inst.binance and not has_key("twelvedata"):
            errors.append("Las velas intradía de este activo necesitan Twelve Data (clave gratuita)")
        return {"candles": [], "source": None, "kind": "none", "error": "; ".join(errors) or "Ningún proveedor disponible"}

    ttl = max(15, min(TF_SECONDS[tf] // 4, 600))
    return _cached(("c", inst.symbol, tf, limit), ttl, load)


def history(inst: Instrument, tf: str, start: int, end: int) -> dict:
    """Velas históricas de un periodo (backtesting)."""
    if inst.binance:
        rows: list[dict] = []
        cur = start
        for _ in range(40):  # hasta 40.000 velas
            chunk = binance_candles(inst.binance, tf, 1000, cur, end)
            if not chunk:
                break
            rows += chunk
            if len(chunk) < 1000 or chunk[-1]["time"] >= end:
                break
            cur = chunk[-1]["time"] + TF_SECONDS[tf]
        return {"candles": [r for r in rows if start <= r["time"] <= end], "source": "binance", "kind": "historical"}
    if inst.td and has_key("twelvedata"):
        s = datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        e = datetime.fromtimestamp(end, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        return {"candles": td_candles(inst.td, tf, 5000, s, e), "source": "twelvedata", "kind": "historical"}
    if inst.stooq and tf in STOOQ_TF:
        return {"candles": [r for r in stooq_candles(inst.stooq, tf) if start <= r["time"] <= end], "source": "stooq", "kind": "historical"}
    raise DataError("No hay un proveedor con histórico para este activo y temporalidad")


def fx_rate(frm: str, to: str, db=None) -> tuple[float | None, str | None]:
    """Tipo de cambio real (divisa del activo → divisa de la cuenta). None si no hay datos."""
    frm, to = frm.upper(), to.upper()
    if frm == to:
        return 1.0, None
    insts = instruments(db)

    def px(a: str, b: str) -> float | None:
        if f"{a}/{b}" in insts:
            p = quote(insts[f"{a}/{b}"], ttl=120).get("price")
            return p
        if f"{b}/{a}" in insts:
            p = quote(insts[f"{b}/{a}"], ttl=120).get("price")
            return 1 / p if p else None
        return None
    direct = px(frm, to)
    if direct:
        return direct, "directo"
    a, b = px(frm, "USD"), px("USD", to)
    a = a or (1.0 if frm == "USD" else None)
    b = b or (1.0 if to == "USD" else None)
    note = "vía USD"
    # Respaldo con datos reales de Binance si el proveedor de divisas no responde: EURUSDT, GBPUSDT… (USDT ≈ USD)
    if not a and frm != "USD":
        r = _binance_fx(frm)
        a, note = (r, f"vía Binance {frm}USDT (USDT≈USD)") if r else (None, note)
    if not b and to != "USD":
        r = _binance_fx(to)
        b, note = (1 / r, f"vía Binance {to}USDT (USDT≈USD)") if r else (None, note)
    if a and b:
        return a * b, note
    return None, None


_FX_CACHE: dict[str, tuple[float, float]] = {}


def _binance_fx(ccy: str) -> float | None:
    """Precio real de 1 unidad de `ccy` en USDT según Binance (solo divisas con par en Binance). Caché de 2 min."""
    import time as _t
    hit = _FX_CACHE.get(ccy)
    if hit and _t.time() - hit[1] < 120:
        return hit[0]
    try:
        p = binance_quotes([f"{ccy}USDT"]).get(f"{ccy}USDT", {}).get("price")
    except Exception:  # noqa: BLE001 - sin par o sin conexión: no hay tipo de cambio (nunca se inventa)
        p = None
    if p:
        _FX_CACHE[ccy] = (p, _t.time())
    return p


def provider_status(test: bool = False) -> list[dict]:
    out = []
    for pid, p in PROVIDERS.items():
        configured = has_key(pid)
        if test and configured:
            try:
                if pid == "binance":
                    binance_quotes(["BTCUSDT"])
                elif pid == "stooq":
                    stooq_quotes(["aapl.us"])
                elif pid == "finnhub":
                    finnhub_quote("AAPL")
                elif pid == "twelvedata":
                    td_quote("AAPL")
                elif pid == "alphavantage":
                    av_quote("IBM")
            except DataError:
                pass
        s = _stats[pid]
        state = ("sin clave" if not configured else "error" if s["last_error"] else "conectado" if s["ok"] else "sin probar")
        out.append({"id": pid, "name": p["name"], "needs_key": bool(p["key"]), "configured": configured, "kind": p["kind"],
                    "kind_label": KIND_LABEL[p["kind"]], "covers": p["covers"], "limits": p["limits"], "url": p["url"],
                    "state": state, "latency_ms": s["last_ms"], "ok": s["ok"], "errors": s["errors"], "last_error": s["last_error"],
                    "last_at": datetime.fromtimestamp(s["last_at"], timezone.utc).isoformat() if s["last_at"] else None})
    return out
