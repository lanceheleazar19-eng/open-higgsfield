"""VISTAN Paper Betting — API. Simulación con dinero FICTICIO: sin depósitos, sin retiradas, sin casas de apuestas
conectadas para apostar. Tablas bt_* separadas de la Trading Desk."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.bets import analysis, engine
from atlas.bets import markets as mk
from atlas.bets import providers as pv
from atlas.integrations.secrets import delete_secret, set_secret
from atlas.models import BtBacktest, BtBet, BtEvent, BtPrediction
from atlas.models.base import utcnow
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/betting", tags=["paper-betting"])
SPORTS = {"football": "Fútbol", "basketball": "Baloncesto", "tennis": "Tenis", "f1": "Fórmula 1", "other": "Otros"}


def event_dict(e: BtEvent) -> dict:
    return {"id": e.id, "sport": e.sport, "competition": e.competition, "name": e.name, "home": e.home, "away": e.away,
            "participants": e.participants or [], "starts_at": e.starts_at.isoformat(), "status": e.status, "result": e.result,
            "result_source": e.result_source, "provider": e.provider, "meta": {k: v for k, v in (e.meta or {}).items() if k != "matrix"}}


def br_dict(b) -> dict:  # noqa: ANN001
    return {"id": b.id, "name": b.name, "currency": b.currency, "initial": b.initial, "balance": b.balance, "active": b.active,
            "simulated": True, "created_at": b.created_at.isoformat()}


@router.get("/meta")
def meta() -> dict:
    return {"sports": SPORTS, "markets": mk.MARKETS, "pick_labels": mk.PICK_LABEL, "competitions": pv.FOOTBALL_COMPETITIONS,
            "csv_leagues": list(pv.CSV_LEAGUES), "strategies": analysis.STRATEGIES,
            "notice": "Simulación educativa con dinero ficticio. No hay depósitos, retiradas ni apuestas reales."}


@router.get("/bankroll")
def get_bankroll(db: DB) -> dict:
    b = engine.bankroll(db)
    db.commit()
    pending = sum(x.stake for x in db.scalars(select(BtBet).where(BtBet.bankroll_id == b.id, BtBet.status == "pending")))
    return br_dict(b) | {"pending_stake": round(pending, 2), "label": "DINERO FICTICIO"}


class BankrollIn(BaseModel):
    initial: float = Field(ge=10, le=100_000_000)
    currency: str = Field(default="EUR", pattern="^(EUR|USD)$")


@router.post("/bankroll", status_code=201)
def reset_bankroll(body: BankrollIn, db: DB) -> dict:
    try:
        b = engine.new_bankroll(db, body.initial, body.currency)
    except engine.BetError as exc:
        raise HTTPException(409, str(exc)) from exc
    log_activity(db, "betting", "bankroll", f"[SIMULACIÓN] Nuevo bankroll ficticio: {b.initial:,.0f} {b.currency}")
    db.commit()
    return br_dict(b)


# ───────── Eventos ─────────

@router.get("/events")
def events(db: DB, sport: str | None = None, status: str | None = None, q: str | None = None, days: int = 14) -> list[dict]:
    qry = select(BtEvent)
    if sport:
        qry = qry.where(BtEvent.sport == sport)
    if status:
        qry = qry.where(BtEvent.status == status)
    else:
        qry = qry.where(BtEvent.starts_at >= utcnow() - timedelta(days=days))
    evs = list(db.scalars(qry.order_by(BtEvent.starts_at).limit(500)))
    if q:
        evs = [e for e in evs if q.lower() in f"{e.name} {e.competition}".lower()]
    return [event_dict(e) for e in evs]


class EventIn(BaseModel):
    sport: str = Field(pattern="^(football|basketball|tennis|f1|other)$")
    competition: str | None = Field(default=None, max_length=120)
    home: str | None = Field(default=None, max_length=120)
    away: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, max_length=200)
    participants: list[str] = Field(default_factory=list, max_length=40)
    starts_at: datetime
    notes: str | None = Field(default=None, max_length=4000)


@router.post("/events", status_code=201)
def create_event(body: EventIn, db: DB) -> dict:
    if body.sport != "f1" and not (body.home and body.away):
        raise HTTPException(422, "Indica los dos equipos o jugadores")
    start = body.starts_at.astimezone(timezone.utc).replace(tzinfo=None) if body.starts_at.tzinfo else body.starts_at
    ev = engine.upsert_event(db, {"sport": body.sport, "competition": body.competition, "home": body.home, "away": body.away,
                                  "name": body.name, "participants": body.participants, "starts_at": start, "provider": "manual",
                                  "meta": {"notes": body.notes} if body.notes else {}})
    db.commit()
    return event_dict(ev)


class NotesIn(BaseModel):
    notes: str = Field(max_length=4000)


@router.put("/events/{eid}/notes")
def event_notes(eid: int, body: NotesIn, db: DB) -> dict:
    ev = db.get(BtEvent, eid)
    if not ev:
        raise HTTPException(404, "Evento no encontrado")
    ev.meta = {**(ev.meta or {}), "notes": body.notes.strip() or None}
    db.commit()
    return event_dict(ev)


class ResultIn(BaseModel):
    status: str = Field(pattern="^(finished|postponed|cancelled)$")
    result: dict | None = None


@router.put("/events/{eid}/result")
def event_result(eid: int, body: ResultIn, db: DB) -> dict:
    ev = db.get(BtEvent, eid)
    if not ev:
        raise HTTPException(404, "Evento no encontrado")
    try:
        engine.set_result(db, ev, body.status, body.result)
        out = engine.settle(db, fetch=False)
    except engine.BetError as exc:
        raise HTTPException(422, str(exc)) from exc
    log_activity(db, "betting", "result", f"Resultado registrado a mano: {ev.name} ({body.status})")
    db.commit()
    return event_dict(ev) | {"settled": out["settled"]}


class SyncIn(BaseModel):
    football: list[str] = Field(default_factory=list)
    f1: bool = False
    nba: bool = False
    odds_sport: str | None = Field(default=None, max_length=80)
    days: int = Field(default=10, ge=1, le=30)


@router.post("/sync")
async def sync(body: SyncIn, db: DB) -> dict:
    """Importa próximos eventos REALES de los proveedores elegidos."""
    errors, added = [], 0

    def run() -> None:
        nonlocal added
        f, t = pv.upcoming_window(body.days)
        rows: list[dict] = []
        for code in body.football:
            try:
                rows += [r | {"meta": {"code": code, "matchday": r.get("matchday")}} for r in pv.fd_matches(code, f, t)]
            except pv.DataError as exc:
                errors.append(str(exc))
        if body.f1:
            try:
                now = utcnow()
                rows += [r for r in pv.f1_schedule() if now - timedelta(days=1) <= r["starts_at"] <= now + timedelta(days=body.days + 20)]
            except pv.DataError as exc:
                errors.append(str(exc))
        if body.nba:
            try:
                rows += pv.tsdb_next("4387")
            except pv.DataError as exc:
                errors.append(str(exc))
        if body.odds_sport:
            try:
                for e in pv.odds_for(body.odds_sport):
                    sport = ("football" if e["sport_key"].startswith("soccer") else "basketball" if e["sport_key"].startswith("basketball")
                             else "tennis" if e["sport_key"].startswith("tennis") else "other")
                    rows.append({"external_id": e["id"], "provider": "theoddsapi", "sport": sport, "competition": e["sport_key"],
                                 "home": e["home"], "away": e["away"], "starts_at": e["starts_at"], "status": "scheduled",
                                 "meta": {"sport_key": e["sport_key"]}})
            except pv.DataError as exc:
                errors.append(str(exc))
        for r in rows:
            engine.upsert_event(db, {k: v for k, v in r.items() if k not in ("code", "matchday")})
            added += 1
    await run_in_threadpool(run)
    db.commit()
    return {"imported": added, "errors": errors}


# ───────── Prediction engine y cuotas ─────────

@router.post("/events/{eid}/predict")
async def predict(eid: int, db: DB, explain: bool = True) -> dict:
    ev = db.get(BtEvent, eid)
    if not ev:
        raise HTTPException(404, "Evento no encontrado")
    out = await run_in_threadpool(analysis.predict, db, get_prefs(db), ev, explain)
    db.commit()
    return out


@router.get("/events/{eid}/prediction")
def last_prediction(eid: int, db: DB) -> dict | None:
    p = db.scalar(select(BtPrediction).where(BtPrediction.event_id == eid).order_by(BtPrediction.id.desc()).limit(1))
    if not p:
        return None
    return {"id": p.id, "model": p.model, "probs": p.probs, "intervals_80": (p.inputs or {}).get("intervals_80"),
            "method": (p.inputs or {}).get("method"), "explanation": p.explanation, "created_at": p.created_at.isoformat()}


@router.get("/events/{eid}/odds")
async def event_odds(eid: int, db: DB) -> dict:
    ev = db.get(BtEvent, eid)
    if not ev:
        raise HTTPException(404, "Evento no encontrado")
    return await run_in_threadpool(analysis.odds_table, db, ev)


class OddsIn(BaseModel):
    odds: list[float] = Field(min_length=1, max_length=40)
    probs: list[float | None] = Field(default_factory=list)
    stake: float | None = Field(default=None, gt=0)


@router.post("/odds/analyze")
def analyze_odds(body: OddsIn) -> dict:
    """Odds Analyzer: probabilidad implícita, margen (si el mercado está completo), diferencia con tu modelo y retornos."""
    if any(o <= 1 for o in body.odds):
        raise HTTPException(422, "Las cuotas decimales deben ser mayores que 1")
    out: dict = {"implied": [round(1 / o, 6) for o in body.odds]}
    if len(body.odds) >= 2:
        out["market"] = mk.overround(body.odds)
    out["selections"] = []
    for i, o in enumerate(body.odds):
        p = body.probs[i] if i < len(body.probs) else None
        s = {"odds": o, "implied": round(1 / o, 6), "edge": mk.edge(p, o) if p else None}
        if body.stake:
            s |= {"return_if_win": round(body.stake * o, 2), "profit_if_win": round(body.stake * (o - 1), 2), "loss_if_lose": -body.stake,
                  "expected_profit": round(body.stake * (p * o - 1), 2) if p else None}
        out["selections"].append(s)
    return out


# ───────── Pronósticos ─────────

class LegIn(BaseModel):
    event_id: int
    market: str
    pick: str = Field(max_length=120)
    line: float | None = None
    opponent: str | None = Field(default=None, max_length=120)
    odds: float = Field(gt=1)
    odds_source: str | None = Field(default="manual", max_length=80)
    model_prob: float | None = Field(default=None, ge=0, le=1)


class SlipIn(BaseModel):
    legs: list[LegIn] = Field(min_length=1, max_length=20)
    stake: float | None = Field(default=None, gt=0)
    reasoning: str | None = Field(default=None, max_length=8000)
    strategy: str | None = Field(default=None, max_length=64)
    user_prob: float | None = Field(default=None, gt=0, lt=1)


@router.post("/slip/analyze")
def slip_analyze(body: SlipIn, db: DB) -> dict:
    try:
        return engine.analyze_slip(db, [leg.model_dump() for leg in body.legs], body.stake)
    except (engine.BetError, mk.MarketError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/bets", status_code=201)
def place(body: SlipIn, db: DB) -> dict:
    try:
        b = engine.place(db, [leg.model_dump() for leg in body.legs], body.stake or 0, body.reasoning, body.strategy, body.user_prob)
    except (engine.BetError, mk.MarketError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    log_activity(db, "betting", "bet", f"[SIMULACIÓN] Pronóstico {'combinado' if b.kind == 'combo' else 'simple'} #{b.id}: {b.stake:,.2f} ficticios a cuota {b.odds:.2f}")
    db.commit()
    return engine.bet_dict(db, b)


@router.get("/bets")
def bets(db: DB, status: str | None = None, kind: str | None = None, limit: int = 300) -> list[dict]:
    br = engine.bankroll(db)
    q = select(BtBet).where(BtBet.bankroll_id == br.id)
    if status:
        q = q.where(BtBet.status == status)
    if kind:
        q = q.where(BtBet.kind == kind)
    return [engine.bet_dict(db, b) for b in db.scalars(q.order_by(BtBet.id.desc()).limit(min(limit, 2000)))]


@router.post("/settle")
async def settle(db: DB) -> dict:
    out = await run_in_threadpool(engine.settle, db, True)
    db.commit()
    return out


@router.get("/analytics")
def get_analytics(db: DB) -> dict:
    out = engine.analytics(db)
    db.commit()
    return out | {"label": "SIMULACIÓN · dinero ficticio"}


# ───────── Backtesting ─────────

class BacktestIn(BaseModel):
    league: str = Field(max_length=8)
    seasons: list[int] = Field(min_length=1, max_length=4)
    strategies: list[str] = Field(min_length=1, max_length=5)
    threshold: float = Field(default=0.05, ge=0, le=1)
    stake_mode: str = Field(default="flat", pattern="^(flat|kelly)$")
    stake: float = Field(default=100, gt=0)
    kelly_frac: float = Field(default=0.25, gt=0, le=1)
    bankroll: float = Field(default=10_000, ge=100)


@router.post("/backtest")
async def backtest(body: BacktestIn, db: DB) -> dict:
    if any(s not in analysis.STRATEGIES for s in body.strategies):
        raise HTTPException(422, "Estrategia desconocida")
    try:
        res = await run_in_threadpool(analysis.backtest, body.league, body.seasons, body.strategies, body.threshold,
                                      body.stake_mode, body.stake, body.kelly_frac, body.bankroll)
    except (pv.DataError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    db.add(BtBacktest(params=body.model_dump(), result={k: v for k, v in res.items() if k != "results"} |
                      {"results": [{k: v for k, v in r.items() if k not in ("curve", "sample")} for r in res["results"]]}))
    log_activity(db, "betting", "backtest", f"Backtest de apuestas {body.league} {body.seasons}: {', '.join(body.strategies)}")
    db.commit()
    return res


@router.get("/backtests")
def backtests(db: DB) -> list[dict]:
    return [{"id": b.id, "created_at": b.created_at.isoformat(), "params": b.params, "result": b.result}
            for b in db.scalars(select(BtBacktest).order_by(BtBacktest.id.desc()).limit(20))]


# ───────── Agente ─────────

class TutorIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    event_id: int | None = None
    history: list[dict] = Field(default_factory=list, max_length=12)


@router.post("/agent")
async def agent(body: TutorIn, db: DB) -> dict:
    from atlas.brain.base import ProviderError
    try:
        return await run_in_threadpool(analysis.tutor, db, get_prefs(db), body.question, body.event_id, body.history)
    except ProviderError as exc:
        raise HTTPException(503, f"El agente necesita la IA de VISTAN: {exc}") from exc


# ───────── Proveedores ─────────

@router.get("/providers")
def providers() -> list[dict]:
    return pv.status()


@router.get("/odds-sports")
async def odds_sports() -> dict:
    try:
        return {"sports": await run_in_threadpool(pv.odds_sports), "error": None}
    except pv.DataError as exc:
        return {"sports": [], "error": str(exc)}


class KeyIn(BaseModel):
    key: str = Field(min_length=3, max_length=200)


@router.put("/providers/{pid}/key")
def set_key(pid: str, body: KeyIn, db: DB) -> dict:
    p = pv.PROVIDERS.get(pid)
    if not p or not p["key"]:
        raise HTTPException(404, "Proveedor sin clave configurable")
    where = set_secret(p["key"], body.key.strip())
    pv.clear_cache()
    log_activity(db, "security", "credential", f"API key de datos deportivos guardada: {p['name']}")
    db.commit()
    return {"ok": True, "stored_in": where}


@router.delete("/providers/{pid}/key")
def del_key(pid: str, db: DB) -> dict:
    p = pv.PROVIDERS.get(pid)
    if not p or not p["key"]:
        raise HTTPException(404, "Proveedor sin clave configurable")
    delete_secret(p["key"])
    pv.clear_cache()
    db.commit()
    return {"ok": True}
