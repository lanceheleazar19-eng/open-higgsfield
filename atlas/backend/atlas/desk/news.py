"""Noticias financieras e indicadores macro de proveedores con clave. Cada elemento lleva fuente, proveedor
y fecha; VISTAN no verifica el contenido de las noticias (lo indica la interfaz)."""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone

from atlas.config import get_settings
from atlas.desk import market as mk

MACRO = {
    "FEDERAL_FUNDS_RATE": {"name": "Tipo de interés de la Fed", "params": {"interval": "monthly"}, "unit": "%"},
    "INFLATION": {"name": "Inflación EE. UU. (anual)", "params": {}, "unit": "%"},
    "CPI": {"name": "IPC EE. UU. (índice)", "params": {"interval": "monthly"}, "unit": "índice"},
    "UNEMPLOYMENT": {"name": "Desempleo EE. UU.", "params": {}, "unit": "%"},
    "NONFARM_PAYROLL": {"name": "Nóminas no agrícolas EE. UU.", "params": {}, "unit": "miles"},
    "TREASURY_YIELD": {"name": "Bono EE. UU. 10 años", "params": {"interval": "monthly", "maturity": "10year"}, "unit": "%"},
}


def _disk_cache(name: str, ttl: float, fn):
    path = get_settings().resolved_data_dir / "cache" / f"desk_{name}.json"
    try:
        d = json.loads(path.read_text())
        if time.time() - d["at"] < ttl:
            return d["value"]
    except (OSError, ValueError, KeyError):
        pass
    value = fn()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"at": time.time(), "value": value}))
    return value


def news(limit: int = 40) -> dict:
    items, errors, providers = [], [], []
    if mk.has_key("finnhub"):
        providers.append("finnhub")
        try:
            rows = mk._cached(("news", "finnhub"), 600, lambda: mk._get(
                "finnhub", "https://finnhub.io/api/v1/news", {"category": "general"},
                headers={"X-Finnhub-Token": mk._key("finnhub")}).json())
            for r in rows[:limit]:
                items.append({"title": r.get("headline"), "summary": r.get("summary"), "url": r.get("url"), "source": r.get("source"),
                              "provider": "Finnhub", "published": datetime.fromtimestamp(r["datetime"], timezone.utc).isoformat() if r.get("datetime") else None,
                              "sentiment": None, "tickers": [t for t in (r.get("related") or "").split(",") if t]})
        except mk.DataError as exc:
            errors.append(str(exc))
    if mk.has_key("alphavantage"):
        providers.append("alphavantage")
        try:
            d = _disk_cache("av_news", 3 * 3600, lambda: mk._av({"function": "NEWS_SENTIMENT", "topics": "financial_markets,economy_macro", "limit": "50"}))
            for r in (d.get("feed") or [])[:limit]:
                pub = r.get("time_published")
                items.append({"title": r.get("title"), "summary": r.get("summary"), "url": r.get("url"), "source": r.get("source"),
                              "provider": "Alpha Vantage",
                              "published": datetime.strptime(pub, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc).isoformat() if pub else None,
                              "sentiment": r.get("overall_sentiment_label"),
                              "tickers": [t.get("ticker") for t in r.get("ticker_sentiment") or []][:6]})
        except mk.DataError as exc:
            errors.append(str(exc))
    items.sort(key=lambda x: x["published"] or "", reverse=True)
    note = None if providers else "Conecta Finnhub o Alpha Vantage (claves gratuitas) para ver noticias."
    return {"items": items, "errors": errors, "providers": providers, "note": note}


def macro() -> dict:
    if not mk.has_key("alphavantage"):
        return {"series": [], "note": "Los indicadores macro (tipos, inflación, empleo) necesitan una clave gratuita de Alpha Vantage."}

    def load():
        out = []
        for fn, cfg in MACRO.items():
            try:
                d = mk._av({"function": fn, **cfg["params"]})
                data = [{"date": x["date"], "value": float(x["value"])} for x in (d.get("data") or [])[:24] if x.get("value") not in (None, ".")]
                out.append({"id": fn, "name": cfg["name"], "unit": cfg["unit"], "data": data, "error": None})
            except mk.DataError as exc:
                out.append({"id": fn, "name": cfg["name"], "unit": cfg["unit"], "data": [], "error": str(exc)})
        return out
    series = _disk_cache("av_macro", 12 * 3600, load)
    return {"series": series, "source": "Alpha Vantage (datos oficiales de EE. UU.: Fed, BLS, Tesoro)", "kind": "Datos publicados (no en tiempo real)", "note": None}


def calendar(days: int = 14) -> dict:
    if not mk.has_key("finnhub"):
        return {"events": [], "note": "El calendario económico necesita Finnhub (su plan gratuito puede no incluirlo)."}
    start, end = date.today(), date.today() + timedelta(days=days)
    try:
        d = mk._cached(("cal", start.isoformat()), 3600, lambda: mk._get(
            "finnhub", "https://finnhub.io/api/v1/calendar/economic", {"from": start.isoformat(), "to": end.isoformat()},
            headers={"X-Finnhub-Token": mk._key("finnhub")}).json())
    except mk.DataError as exc:
        return {"events": [], "note": f"{exc}. El calendario económico de Finnhub suele requerir un plan de pago."}
    ev = [{"time": e.get("time"), "country": e.get("country"), "event": e.get("event"), "impact": e.get("impact"),
           "actual": e.get("actual"), "estimate": e.get("estimate"), "prev": e.get("prev"), "unit": e.get("unit")}
          for e in (d.get("economicCalendar") or [])]
    return {"events": sorted(ev, key=lambda x: x["time"] or ""), "source": "Finnhub", "note": None}
