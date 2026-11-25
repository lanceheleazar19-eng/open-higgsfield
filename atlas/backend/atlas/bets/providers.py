"""Fuentes de datos deportivos (solo lectura de datos; ninguna permite apostar):

- football-data.org (clave gratuita): calendario, resultados y temporadas de las grandes ligas de fútbol.
- Jolpica F1 (sin clave, sucesor de Ergast): calendario y resultados de Fórmula 1.
- TheSportsDB (clave pública gratuita «123»): eventos y resultados de NBA y otras ligas.
- The Odds API (clave gratuita, 500 créditos/mes): cuotas de casas autorizadas y marcadores recientes.
- football-data.co.uk (sin clave): resultados y cuotas históricas de fútbol para backtesting.
Las claves se guardan en el llavero (nunca en la base de datos)."""

from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timedelta, timezone

import httpx

from atlas.integrations.secrets import get_secret

PROVIDERS = {
    "football-data": {"name": "football-data.org", "key": "footballdata_api_key", "url": "https://www.football-data.org/client/register",
                      "covers": "Fútbol: calendario, resultados y temporadas (Premier, LaLiga, Bundesliga, Serie A, Ligue 1, Champions…)",
                      "limits": "Gratis: 10 peticiones/minuto; resultados al terminar el partido"},
    "jolpica": {"name": "Jolpica F1", "key": None, "url": "https://github.com/jolpica/jolpica-f1",
                "covers": "Fórmula 1: calendario, resultados y clasificación de cada carrera", "limits": "Público, sin clave"},
    "thesportsdb": {"name": "TheSportsDB", "key": "thesportsdb_api_key", "default_key": "123", "url": "https://www.thesportsdb.com/api.php",
                    "covers": "Baloncesto (NBA) y otras ligas: próximos partidos y resultados", "limits": "Clave pública «123» con límites; premium opcional"},
    "theoddsapi": {"name": "The Odds API", "key": "theoddsapi_api_key", "url": "https://the-odds-api.com",
                   "covers": "Cuotas de casas autorizadas (1X2, hándicaps, totales) de fútbol, baloncesto, tenis… y marcadores recientes",
                   "limits": "Gratis: 500 créditos/mes (cada consulta de cuotas gasta créditos)"},
    "football-data.co.uk": {"name": "football-data.co.uk", "key": None, "url": "https://www.football-data.co.uk",
                            "covers": "Fútbol: resultados y cuotas históricas por temporada (para backtesting)", "limits": "Público, sin clave"},
}

FOOTBALL_COMPETITIONS = {"PL": "Premier League", "PD": "LaLiga", "BL1": "Bundesliga", "SA": "Serie A", "FL1": "Ligue 1",
                         "CL": "Champions League", "DED": "Eredivisie", "PPL": "Primeira Liga", "ELC": "Championship"}
# Códigos de football-data.co.uk para backtesting (liga → archivo)
CSV_LEAGUES = {"PL": "E0", "PD": "SP1", "BL1": "D1", "SA": "I1", "FL1": "F1", "DED": "N1", "PPL": "P1", "ELC": "E1"}
TSDB_LEAGUES = {"4387": "NBA"}

_stats: dict[str, dict] = {p: {"ok": 0, "errors": 0, "last_error": None, "last_ms": None, "last_at": None, "remaining": None} for p in PROVIDERS}
_cache: dict[tuple, tuple[float, object]] = {}


class DataError(RuntimeError):
    pass


def key(pid: str) -> str | None:
    p = PROVIDERS[pid]
    if not p["key"]:
        return ""
    return get_secret(p["key"]) or p.get("default_key")


def configured(pid: str) -> bool:
    return key(pid) is not None


def _get(pid: str, url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 12.0) -> httpx.Response:
    st = _stats[pid]
    t0 = time.perf_counter()
    try:
        r = httpx.get(url, params=params, headers={"User-Agent": "VISTAN-PaperBetting/1.0", **(headers or {})}, timeout=timeout)
    except httpx.HTTPError as exc:
        st.update(errors=st["errors"] + 1, last_error=f"sin conexión ({type(exc).__name__})", last_at=time.time())
        raise DataError(f"{PROVIDERS[pid]['name']}: sin conexión") from exc
    ms = round((time.perf_counter() - t0) * 1000)
    if "x-requests-remaining" in r.headers:
        st["remaining"] = r.headers["x-requests-remaining"]
    if r.status_code >= 400:
        msg = {401: "clave no válida", 403: "acceso denegado (clave o plan)", 404: "no encontrado", 429: "límite de uso alcanzado"}.get(r.status_code, f"HTTP {r.status_code}")
        st.update(errors=st["errors"] + 1, last_error=msg, last_ms=ms, last_at=time.time())
        raise DataError(f"{PROVIDERS[pid]['name']}: {msg}")
    st.update(ok=st["ok"] + 1, last_ms=ms, last_at=time.time(), last_error=None)
    return r


def _cached(k: tuple, ttl: float, fn):
    hit = _cache.get(k)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    v = fn()
    _cache[k] = (time.time(), v)
    return v


def clear_cache() -> None:
    _cache.clear()


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)


# ── football-data.org ──
FD_STATUS = {"FINISHED": "finished", "AWARDED": "finished", "POSTPONED": "postponed", "CANCELLED": "cancelled", "SUSPENDED": "postponed",
             "IN_PLAY": "live", "PAUSED": "live", "LIVE": "live"}


def _fd(path: str, params: dict | None = None) -> dict:
    k = key("football-data")
    if not k:
        raise DataError("football-data.org: falta la API key (gratuita)")
    return _get("football-data", f"https://api.football-data.org/v4{path}", params, {"X-Auth-Token": k}).json()


def fd_matches(code: str, date_from: str | None = None, date_to: str | None = None, season: int | None = None) -> list[dict]:
    params: dict = {}
    if date_from:
        params |= {"dateFrom": date_from, "dateTo": date_to}
    if season:
        params["season"] = season
    data = _cached(("fd", code, date_from, date_to, season), 600, lambda: _fd(f"/competitions/{code}/matches", params))
    out = []
    for m in data.get("matches", []):
        ft = (m.get("score") or {}).get("fullTime") or {}
        out.append({"external_id": str(m["id"]), "provider": "football-data", "sport": "football",
                    "competition": (m.get("competition") or {}).get("name") or FOOTBALL_COMPETITIONS.get(code, code), "code": code,
                    "home": (m.get("homeTeam") or {}).get("name"), "away": (m.get("awayTeam") or {}).get("name"),
                    "starts_at": _dt(m["utcDate"]), "status": FD_STATUS.get(m.get("status"), "scheduled"),
                    "result": {"home": ft["home"], "away": ft["away"]} if ft.get("home") is not None and ft.get("away") is not None else None,
                    "matchday": m.get("matchday")})
    return out


def fd_history(code: str, at: datetime) -> list[dict]:
    """Temporada en curso + anterior (solo partidos terminados), para el modelo."""
    season = at.year if at.month >= 7 else at.year - 1
    rows = []
    for s in (season - 1, season):
        try:
            rows += [m for m in fd_matches(code, season=s) if m["status"] == "finished" and m["result"]]
        except DataError:
            if s == season:
                raise
    return rows


# ── Jolpica F1 ──
def _jol(path: str, params: dict | None = None) -> dict:
    return _get("jolpica", f"https://api.jolpi.ca/ergast/f1{path}", params).json()["MRData"]


def f1_schedule(season: str = "current") -> list[dict]:
    races = _cached(("f1s", season), 3600, lambda: _jol(f"/{season}.json", {"limit": 100}))["RaceTable"]["Races"]
    out = []
    for r in races:
        t = r.get("time", "12:00:00Z")
        out.append({"external_id": f"{r['season']}-{r['round']}", "provider": "jolpica", "sport": "f1", "competition": f"Fórmula 1 {r['season']}",
                    "name": r["raceName"], "starts_at": _dt(f"{r['date']}T{t}"), "status": "scheduled", "result": None,
                    "meta": {"circuit": r["Circuit"]["circuitName"], "country": r["Circuit"]["Location"]["country"], "round": int(r["round"])}})
    return out


def f1_results(season: str, rnd: int | str) -> list[dict] | None:
    races = _jol(f"/{season}/{rnd}/results.json")["RaceTable"]["Races"]
    if not races:
        return None
    return [{"position": int(x["position"]), "driver": x["Driver"]["familyName"], "code": x["Driver"].get("code"),
             "team": x["Constructor"]["name"], "points": float(x["points"]), "status": x["status"]} for x in races[0]["Results"]]


def f1_season_results(season: str = "current") -> list[dict]:
    data = _cached(("f1r", season), 1800, lambda: _jol(f"/{season}/results.json", {"limit": 1000}))
    out = []
    for r in data["RaceTable"]["Races"]:
        out.append({"round": int(r["round"]), "race": r["raceName"],
                    "results": [{"driver": x["Driver"]["familyName"], "points": float(x["points"]), "position": int(x["position"])} for x in r["Results"]]})
    return out


# ── TheSportsDB ──
def _tsdb(path: str, params: dict) -> dict:
    return _get("thesportsdb", f"https://www.thesportsdb.com/api/v1/json/{key('thesportsdb')}/{path}", params).json() or {}


def _tsdb_event(e: dict) -> dict:
    ts = e.get("strTimestamp") or f"{e.get('dateEvent')}T{e.get('strTime') or '00:00:00'}"
    hs, as_ = e.get("intHomeScore"), e.get("intAwayScore")
    finished = hs not in (None, "") and as_ not in (None, "") and (e.get("strStatus") in (None, "", "FT", "AOT", "Match Finished", "Finished"))
    st = (e.get("strStatus") or "").lower()
    return {"external_id": str(e["idEvent"]), "provider": "thesportsdb", "sport": "basketball" if e.get("strSport") == "Basketball" else "other",
            "competition": e.get("strLeague"), "home": e.get("strHomeTeam"), "away": e.get("strAwayTeam"),
            "starts_at": _dt(ts if "+" in ts or ts.endswith("Z") else ts + "Z"),
            "status": "finished" if finished else "postponed" if "postp" in st else "cancelled" if "cancel" in st else "scheduled",
            "result": {"home": int(hs), "away": int(as_)} if finished else None}


def tsdb_next(league: str) -> list[dict]:
    return [_tsdb_event(e) for e in (_cached(("tn", league), 900, lambda: _tsdb("eventsnextleague.php", {"id": league})).get("events") or [])]


def tsdb_past(league: str) -> list[dict]:
    return [_tsdb_event(e) for e in (_cached(("tp", league), 900, lambda: _tsdb("eventspastleague.php", {"id": league})).get("events") or [])]


def tsdb_event(eid: str) -> dict | None:
    ev = (_tsdb("lookupevent.php", {"id": eid}).get("events") or [])
    return _tsdb_event(ev[0]) if ev else None


# ── The Odds API ──
def _odds(path: str, params: dict | None = None) -> object:
    k = key("theoddsapi")
    if not k:
        raise DataError("The Odds API: falta la API key (gratuita)")
    return _get("theoddsapi", f"https://api.the-odds-api.com/v4{path}", {**(params or {}), "apiKey": k}).json()


def odds_sports() -> list[dict]:
    return [s for s in _cached(("osports",), 6 * 3600, lambda: _odds("/sports")) if s.get("active") and not s.get("has_outrights")]


def odds_for(sport_key: str, markets: str = "h2h,totals,spreads") -> list[dict]:
    """Cuotas decimales por casa (región UE). Cada consulta gasta créditos: se guarda en caché 10 minutos."""
    data = _cached(("odds", sport_key, markets), 600, lambda: _odds(f"/sports/{sport_key}/odds", {"regions": "eu", "markets": markets, "oddsFormat": "decimal"}))
    out = []
    for e in data:
        books = []
        for b in e.get("bookmakers", []):
            mk = {}
            for m in b.get("markets", []):
                mk[m["key"]] = [{"name": o["name"], "price": o["price"], "point": o.get("point")} for o in m.get("outcomes", [])]
            books.append({"key": b["key"], "title": b["title"], "last_update": b.get("last_update"), "markets": mk})
        out.append({"id": e["id"], "sport_key": e["sport_key"], "home": e.get("home_team"), "away": e.get("away_team"),
                    "starts_at": _dt(e["commence_time"]), "bookmakers": books})
    return out


def odds_scores(sport_key: str, days_from: int = 3) -> list[dict]:
    data = _cached(("oscores", sport_key), 300, lambda: _odds(f"/sports/{sport_key}/scores", {"daysFrom": days_from}))
    out = []
    for e in data:
        sc = {s["name"]: s["score"] for s in (e.get("scores") or [])}
        res = None
        if e.get("completed") and e.get("home_team") in sc and e.get("away_team") in sc:
            try:
                res = {"home": int(float(sc[e["home_team"]])), "away": int(float(sc[e["away_team"]]))}
            except (TypeError, ValueError):
                res = None
        out.append({"id": e["id"], "completed": bool(e.get("completed")), "result": res})
    return out


# ── football-data.co.uk (histórico con cuotas) ──
def csv_season(league_code: str, season_start: int) -> list[dict]:
    code = CSV_LEAGUES.get(league_code, league_code)
    yy = f"{season_start % 100:02d}{(season_start + 1) % 100:02d}"
    url = f"https://www.football-data.co.uk/mmz4281/{yy}/{code}.csv"
    text = _cached(("csv", code, yy), 24 * 3600, lambda: _get("football-data.co.uk", url, timeout=20).content.decode("latin-1"))
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            d = r["Date"]
            fmt = "%d/%m/%Y" if len(d.split("/")[-1]) == 4 else "%d/%m/%y"
            when = datetime.strptime(f"{d} {r.get('Time') or '15:00'}", f"{fmt} %H:%M")
            row = {"date": when, "home": r["HomeTeam"], "away": r["AwayTeam"], "hg": int(r["FTHG"]), "ag": int(r["FTAG"]), "odds": {}}
        except (KeyError, ValueError):
            continue
        for k_out, cols in {"home": ("AvgH", "B365H", "PSH"), "draw": ("AvgD", "B365D", "PSD"), "away": ("AvgA", "B365A", "PSA"),
                            "over25": ("Avg>2.5", "B365>2.5", "P>2.5"), "under25": ("Avg<2.5", "B365<2.5", "P<2.5")}.items():
            for c in cols:
                try:
                    v = float(r.get(c) or "")
                    if v > 1:
                        row["odds"][k_out] = v
                        break
                except ValueError:
                    continue
        rows.append(row)
    if not rows:
        raise DataError("football-data.co.uk: temporada sin datos")
    return sorted(rows, key=lambda x: x["date"])


def status() -> list[dict]:
    out = []
    for pid, p in PROVIDERS.items():
        s = _stats[pid]
        has = configured(pid)
        uses_default = bool(p["key"]) and not get_secret(p["key"]) and bool(p.get("default_key"))
        out.append({"id": pid, "name": p["name"], "needs_key": bool(p["key"]) and not p.get("default_key"), "configured": has,
                    "default_key": uses_default, "covers": p["covers"], "limits": p["limits"], "url": p["url"],
                    "state": "sin clave" if not has else "error" if s["last_error"] else "conectado" if s["ok"] else "sin probar",
                    "latency_ms": s["last_ms"], "ok": s["ok"], "errors": s["errors"], "last_error": s["last_error"], "remaining": s["remaining"],
                    "last_at": datetime.fromtimestamp(s["last_at"], timezone.utc).isoformat() if s["last_at"] else None})
    return out


def upcoming_window(days: int = 10) -> tuple[str, str]:
    now = datetime.now(timezone.utc).date()
    return now.isoformat(), (now + timedelta(days=days)).isoformat()
