"""Motor de PAPER BETTING: bankroll ficticio, registro de pronósticos (simples y combinados), liquidación según el
resultado real y estadísticas. No existe ninguna ruta para apostar dinero real ni para depositar o retirar."""

from __future__ import annotations

import math
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.bets import markets as mk
from atlas.bets import models as md
from atlas.bets import providers as pv
from atlas.models import BtBankroll, BtBet, BtEvent, BtLeg, BtPrediction
from atlas.models.base import utcnow

DEFAULT_BANKROLL = 10_000.0


class BetError(ValueError):
    pass


# ───────── Bankroll ─────────

def bankroll(db: Session) -> BtBankroll:
    b = db.scalar(select(BtBankroll).where(BtBankroll.active.is_(True)).order_by(BtBankroll.id.desc()))
    if not b:
        b = BtBankroll(name="BANKROLL VIRTUAL", initial=DEFAULT_BANKROLL, balance=DEFAULT_BANKROLL, currency="EUR")
        db.add(b)
        db.flush()
    return b


def new_bankroll(db: Session, initial: float, currency: str = "EUR", name: str | None = None) -> BtBankroll:
    if not 10 <= initial <= 100_000_000:
        raise BetError("Saldo inicial entre 10 y 100.000.000")
    old = bankroll(db)
    if db.scalar(select(BtBet.id).where(BtBet.bankroll_id == old.id, BtBet.status == "pending")):
        raise BetError("Hay pronósticos pendientes: espera a que se liquiden antes de empezar un bankroll nuevo")
    old.active = False
    b = BtBankroll(name=name or "BANKROLL VIRTUAL", initial=initial, balance=initial, currency=currency.upper())
    db.add(b)
    db.flush()
    return b


# ───────── Eventos ─────────

def upsert_event(db: Session, d: dict) -> BtEvent:
    ev = None
    if d.get("external_id") and d.get("provider"):
        ev = db.scalar(select(BtEvent).where(BtEvent.provider == d["provider"], BtEvent.external_id == d["external_id"]))
    name = d.get("name") or (f"{d['home']} – {d['away']}" if d.get("home") and d.get("away") else "Evento")
    if not ev:
        ev = BtEvent(sport=d["sport"], provider=d.get("provider", "manual"), external_id=d.get("external_id"), name=name,
                     home=d.get("home"), away=d.get("away"), starts_at=d["starts_at"], competition=d.get("competition"),
                     participants=d.get("participants") or [], meta=d.get("meta") or {}, status=d.get("status", "scheduled"))
        db.add(ev)
    else:
        ev.starts_at, ev.competition = d["starts_at"], d.get("competition") or ev.competition
        if d.get("meta"):
            ev.meta = {**(ev.meta or {}), **d["meta"]}
    if d.get("status") and ev.status != "finished":
        ev.status = d["status"]
    if d.get("result") and ev.result_source != "manual":
        ev.result, ev.result_source = d["result"], d.get("provider")
    db.flush()
    return ev


def set_result(db: Session, ev: BtEvent, status: str, result: dict | None) -> BtEvent:
    if status not in ("finished", "postponed", "cancelled"):
        raise BetError("Estado no válido")
    if status == "finished":
        if ev.starts_at > utcnow():
            raise BetError("El evento aún no ha empezado: no se puede registrar un resultado")
        _check_result(ev.sport, result)
    ev.status, ev.result, ev.result_source = status, ({**(ev.result or {}), **(result or {})} if result else ev.result), "manual"
    return ev


def _check_result(sport: str, r: dict | None) -> None:
    if not r:
        raise BetError("Falta el resultado")
    if sport == "f1":
        if not r.get("order") and not r.get("stats"):
            raise BetError("Para F1 indica el orden de llegada")
    elif sport == "tennis":
        if "sets" not in r and not ("home_sets" in r and "away_sets" in r) and not r.get("stats"):
            raise BetError("Para tenis indica los sets")
    elif not ("home" in r and "away" in r) and not r.get("stats"):
        raise BetError("Indica el marcador de local y visitante")


# ───────── Combinadas ─────────

def _compatible(legs: list[tuple[str, str, float | None]]) -> bool:
    """¿Existe algún marcador en el que ganen todas? (detecta selecciones contradictorias del mismo partido)."""
    for h in range(16):
        for a in range(16):
            if all(mk.settle_leg("football", m, p, ln, None, "finished", {"home": h, "away": a}) == "won" for m, p, ln in legs):
                return True
    return False


SCORE_MARKETS = {"1x2", "double_chance", "total", "btts", "handicap", "correct_score", "moneyline"}


def latest_prediction(db: Session, event_id: int) -> BtPrediction | None:
    return db.scalar(select(BtPrediction).where(BtPrediction.event_id == event_id).order_by(BtPrediction.id.desc()).limit(1))


def analyze_slip(db: Session, legs: list[dict], stake: float | None = None) -> dict:
    """Cuota combinada, retorno potencial, probabilidad conjunta del modelo (sin suponer independencia
    entre selecciones del mismo evento) y avisos."""
    if not legs:
        raise BetError("Añade al menos una selección")
    warnings: list[str] = []
    evs: dict[int, BtEvent] = {}
    for leg in legs:
        ev = db.get(BtEvent, leg["event_id"])
        if not ev:
            raise BetError("Evento no encontrado")
        evs[ev.id] = ev
        mk.validate(ev.sport, leg["market"], leg["pick"], leg.get("line"), leg.get("opponent"))
        if not 1.01 <= float(leg["odds"]) <= 1000:
            raise BetError("Las cuotas decimales deben estar entre 1,01 y 1000")
    keys = [(l["event_id"], l["market"], l["pick"], l.get("line"), l.get("opponent")) for l in legs]
    if len(set(keys)) != len(keys):
        raise BetError("Hay una selección repetida")
    groups: dict[int, list[dict]] = defaultdict(list)
    for leg in legs:
        groups[leg["event_id"]].append(leg)
    joint: float | None = 1.0
    for eid, ls in groups.items():
        ev = evs[eid]
        if len(ls) > 1:
            warnings.append(f"{ev.name}: {len(ls)} selecciones del mismo evento están CORRELACIONADAS; su probabilidad conjunta "
                            "no es el producto de las individuales (y las casas reales suelen ajustar o no aceptar estas combinadas).")
            if ev.sport in ("football", "basketball", "other") and all(l["market"] in SCORE_MARKETS for l in ls):
                if not _compatible([(l["market"], l["pick"], l.get("line")) for l in ls]):
                    raise BetError(f"{ev.name}: las selecciones son incompatibles entre sí (no pueden ganar a la vez)")
        pred = latest_prediction(db, eid)
        if len(ls) == 1:
            p = ls[0].get("model_prob")
            if p is None and pred:
                p = pred.probs.get(md.market_key(ls[0]["market"], ls[0]["pick"], ls[0].get("line")))
            ls[0]["model_prob"] = p
            joint = joint * p if joint is not None and p is not None else None
        else:
            mat = (pred.inputs or {}).get("matrix") if pred else None
            if ev.sport == "football" and mat and all(l["market"] in SCORE_MARKETS for l in ls):
                pj = mk.matrix_prob(mat, [(l["market"], l["pick"], l.get("line")) for l in ls])
                for l in ls:
                    l["model_prob"] = l.get("model_prob") or mk.matrix_prob(mat, [(l["market"], l["pick"], l.get("line"))])
                joint = joint * pj if joint is not None else None
            else:
                joint = None
                warnings.append(f"{ev.name}: sin un modelo conjunto del partido no se calcula la probabilidad combinada de estas selecciones.")
    if len(groups) > 1 and joint is not None:
        warnings.append("Entre eventos distintos se asume independencia (aproximación razonable, no exacta).")
    odds = math.prod(float(l["odds"]) for l in legs)
    out = {"legs": len(legs), "odds": round(odds, 4), "implied_prob": round(1 / odds, 6), "model_prob": round(joint, 6) if joint is not None else None,
           "fair_odds": round(1 / joint, 3) if joint else None, "warnings": warnings,
           "conditions": [f"{evs[l['event_id']].name}: {leg_label(evs[l['event_id']], l)}" for l in legs]}
    if joint is not None:
        out |= {"edge": mk.edge(joint, odds)}
    if stake:
        out |= {"stake": stake, "potential_return": round(stake * odds, 2), "potential_profit": round(stake * (odds - 1), 2),
                "expected_profit": round(stake * (joint * odds - 1), 2) if joint is not None else None}
    return out


def leg_label(ev: BtEvent, l: dict) -> str:
    m, p, ln = l["market"], l["pick"], l.get("line")
    side = {"home": ev.home or "Local", "away": ev.away or "Visitante"}.get(p, mk.PICK_LABEL.get(p, p))
    if m == "1x2":
        return "Empate" if p == "draw" else f"Gana {side}"
    if m == "moneyline":
        return f"Gana {side}"
    if m == "double_chance":
        return {"1X": f"{ev.home} o empate", "12": "No hay empate", "X2": f"Empate o {ev.away}"}[p]
    if m in ("total", "sets_total"):
        return f"{'Más' if p == 'over' else 'Menos'} de {ln:g} {'sets' if m == 'sets_total' else 'goles/puntos'}"
    if m == "btts":
        return "Ambos marcan" if p == "yes" else "No marcan ambos"
    if m == "handicap":
        return f"{side} con hándicap {ln:+g}" if p == "home" else f"{side} con hándicap {-ln:+g}"
    if m in ("correct_score", "sets_exact"):
        return f"Resultado {p}"
    if m == "winner":
        return f"{p} gana la carrera"
    if m == "podium":
        return f"{p} en el podio"
    if m == "h2h":
        return f"{p} termina por delante de {l.get('opponent')}"
    if m == "player_stat":
        name, s = p.rsplit(":", 1)
        return f"{name}: {'más' if s == 'over' else 'menos'} de {ln:g}"
    return f"{m} {p}"


def place(db: Session, legs: list[dict], stake: float, reasoning: str | None, strategy: str | None, user_prob: float | None) -> BtBet:
    b = bankroll(db)
    if not stake or stake <= 0:
        raise BetError("El importe ficticio debe ser mayor que 0")
    if stake > b.balance + 1e-9:
        raise BetError(f"Saldo virtual insuficiente ({b.balance:,.2f} {b.currency})")
    now = utcnow()
    for l in legs:
        ev = db.get(BtEvent, l["event_id"])
        if ev and (ev.starts_at <= now or ev.status != "scheduled"):
            raise BetError(f"{ev.name} ya ha empezado o no está programado: solo se registran pronósticos antes del inicio")
    a = analyze_slip(db, legs, stake)
    if user_prob is not None and not 0 < user_prob < 1:
        raise BetError("Tu probabilidad debe estar entre 0 y 1")
    bet = BtBet(bankroll_id=b.id, kind="single" if len(legs) == 1 else "combo", stake=round(stake, 2), odds=a["odds"],
                potential_return=a["potential_return"], model_prob=a["model_prob"], user_prob=user_prob,
                reasoning=(reasoning or "").strip() or None, strategy=(strategy or "").strip() or None, warnings=a["warnings"])
    db.add(bet)
    db.flush()
    for l in legs:
        db.add(BtLeg(bet_id=bet.id, event_id=l["event_id"], market=l["market"], pick=l["pick"], line=l.get("line"),
                     opponent=l.get("opponent"), odds=float(l["odds"]), odds_source=l.get("odds_source") or "manual",
                     model_prob=l.get("model_prob")))
    b.balance = round(b.balance - stake, 2)
    db.flush()
    return bet


# ───────── Liquidación ─────────

def refresh_results(db: Session, events: list[BtEvent]) -> list[str]:
    """Consulta los resultados reales de los eventos ya empezados. Devuelve errores de proveedores (si los hay)."""
    errors: list[str] = []
    now = utcnow()
    odds_sports: set[str] = set()
    for ev in events:
        if ev.status in ("finished", "cancelled") or ev.starts_at > now or ev.result_source == "manual":
            continue
        try:
            if ev.provider == "football-data":
                m = pv._fd(f"/matches/{ev.external_id}")
                ft = (m.get("score") or {}).get("fullTime") or {}
                ev.status = pv.FD_STATUS.get(m.get("status"), ev.status)
                if ev.status == "finished" and ft.get("home") is not None:
                    ev.result, ev.result_source = {"home": ft["home"], "away": ft["away"]}, "football-data"
            elif ev.provider == "jolpica":
                season, rnd = ev.external_id.split("-")
                res = pv.f1_results(season, rnd)
                if res:
                    ev.status, ev.result_source = "finished", "jolpica"
                    ev.result = {"order": [r["driver"] for r in sorted(res, key=lambda x: x["position"])]}
            elif ev.provider == "thesportsdb":
                d = pv.tsdb_event(ev.external_id)
                if d and d["status"] != "scheduled":
                    ev.status, ev.result, ev.result_source = d["status"], d["result"], "thesportsdb"
            elif ev.provider == "theoddsapi" and ev.meta.get("sport_key"):
                odds_sports.add(ev.meta["sport_key"])
        except pv.DataError as exc:
            errors.append(str(exc))
    for sk in odds_sports:
        try:
            scores = {s["id"]: s for s in pv.odds_scores(sk)}
        except pv.DataError as exc:
            errors.append(str(exc))
            continue
        for ev in events:
            s = scores.get(ev.external_id or "") if ev.provider == "theoddsapi" else None
            if s and s["completed"] and s["result"]:
                ev.status, ev.result, ev.result_source = "finished", s["result"], "theoddsapi"
    db.flush()
    return sorted(set(errors))


def settle(db: Session, fetch: bool = True) -> dict:
    from atlas.security.policy import notify
    pending = list(db.scalars(select(BtBet).where(BtBet.status == "pending")))
    if not pending:
        return {"settled": [], "errors": []}
    legs = list(db.scalars(select(BtLeg).where(BtLeg.bet_id.in_([b.id for b in pending]))))
    evs = {e.id: e for e in db.scalars(select(BtEvent).where(BtEvent.id.in_({l.event_id for l in legs})))}
    errors = refresh_results(db, list(evs.values())) if fetch else []
    for l in legs:
        if l.status != "pending":
            continue
        ev = evs[l.event_id]
        r = mk.settle_leg(ev.sport, l.market, l.pick, l.line, l.opponent, ev.status, ev.result, ev.home, ev.away)
        if r:
            l.status = r
    by_bet: dict[int, list[BtLeg]] = defaultdict(list)
    for l in legs:
        by_bet[l.bet_id].append(l)
    settled = []
    for b in pending:
        ls = by_bet[b.id]
        st, ret = mk.bet_outcome([l.status for l in ls], [l.odds for l in ls], b.stake)
        if st == "pending":
            continue
        b.status, b.returned, b.profit, b.settled_at = st, ret, round((ret or 0) - b.stake, 2), utcnow()
        br = db.get(BtBankroll, b.bankroll_id)
        br.balance = round(br.balance + (ret or 0), 2)
        settled.append(b.id)
        txt = {"won": "acertado", "lost": "fallado", "void": "anulado (se devuelve el importe)"}[st]
        notify(db, f"[SIMULACIÓN] Pronóstico #{b.id} {txt}: {b.profit:+,.2f} {br.currency} ficticios", "Paper Betting · dinero ficticio", "info", "/betting")
    db.flush()
    return {"settled": settled, "errors": errors}


# ───────── Estadísticas ─────────

def _sport_of(db: Session, b: BtBet, legs: list[BtLeg], evs: dict[int, BtEvent]) -> str:
    return "combinada" if b.kind == "combo" else evs[legs[0].event_id].sport


def analytics(db: Session, bankroll_id: int | None = None) -> dict:
    br = db.get(BtBankroll, bankroll_id) if bankroll_id else bankroll(db)
    bets = list(db.scalars(select(BtBet).where(BtBet.bankroll_id == br.id).order_by(BtBet.created_at)))
    legs = list(db.scalars(select(BtLeg).where(BtLeg.bet_id.in_([b.id for b in bets])))) if bets else []
    by_bet: dict[int, list[BtLeg]] = defaultdict(list)
    for l in legs:
        by_bet[l.bet_id].append(l)
    evs = {e.id: e for e in db.scalars(select(BtEvent).where(BtEvent.id.in_({l.event_id for l in legs})))} if legs else {}
    settled = [b for b in bets if b.status in ("won", "lost", "void")]
    decided = [b for b in settled if b.status in ("won", "lost")]

    def block(bs: list[BtBet]) -> dict:
        st = [b for b in bs if b.status in ("won", "lost", "void")]
        dec = [b for b in st if b.status != "void"]
        staked = sum(b.stake for b in st)
        profit = sum(b.profit or 0 for b in st)
        return {"bets": len(bs), "won": sum(b.status == "won" for b in bs), "lost": sum(b.status == "lost" for b in bs),
                "void": sum(b.status == "void" for b in bs), "pending": sum(b.status == "pending" for b in bs),
                "hit_rate": round(sum(b.status == "won" for b in dec) / len(dec) * 100, 2) if dec else None,
                "staked": round(staked, 2), "profit": round(profit, 2) if st else None,
                "roi": round(profit / staked * 100, 2) if staked else None,
                "avg_odds": round(sum(b.odds for b in bs) / len(bs), 3) if bs else None}
    out = {"bankroll": {"id": br.id, "name": br.name, "initial": br.initial, "balance": br.balance, "currency": br.currency},
           **block(bets), "pending_stake": round(sum(b.stake for b in bets if b.status == "pending"), 2)}
    groups: dict[str, dict[str, list[BtBet]]] = {"by_sport": defaultdict(list), "by_market": defaultdict(list), "by_kind": defaultdict(list), "by_strategy": defaultdict(list)}
    for b in bets:
        ls = by_bet[b.id]
        groups["by_sport"][_sport_of(db, b, ls, evs)].append(b)
        groups["by_market"]["combinada" if b.kind == "combo" else mk.MARKETS[ls[0].market]["name"]].append(b)
        groups["by_kind"]["Simples" if b.kind == "single" else "Combinadas"].append(b)
        groups["by_strategy"][b.strategy or "sin estrategia"].append(b)
    for k, g in groups.items():
        out[k] = sorted(({"key": kk, **block(v)} for kk, v in g.items()), key=lambda x: -x["bets"])
    curve, bal = [], br.initial
    for b in sorted(settled, key=lambda x: x.settled_at or x.created_at):
        bal += b.profit or 0
        curve.append({"t": (b.settled_at or b.created_at).isoformat(), "bankroll": round(bal, 2)})
    out["curve"] = curve
    peak, mdd = br.initial, 0.0
    for c in curve:
        peak = max(peak, c["bankroll"])
        mdd = max(mdd, (peak - c["bankroll"]) / peak * 100 if peak else 0)
    out["max_drawdown_pct"] = round(mdd, 2) if curve else None
    # Calibración: selecciones decididas con probabilidad del modelo; y tus propias probabilidades (simples)
    mp = [(l.model_prob, 1 if l.status == "won" else 0) for l in legs if l.model_prob is not None and l.status in ("won", "lost")]
    up = [(b.user_prob, 1 if b.status == "won" else 0) for b in decided if b.user_prob is not None]
    imp = [(1 / l.odds, 1 if l.status == "won" else 0) for l in legs if l.status in ("won", "lost")]
    out["calibration"] = {
        "model": {"n": len(mp), "brier": md.brier(mp), "log_loss": md.log_loss(mp), "bins": md.calibration(mp)},
        "user": {"n": len(up), "brier": md.brier(up), "log_loss": md.log_loss(up), "bins": md.calibration(up)},
        "market": {"n": len(imp), "brier": md.brier(imp), "log_loss": md.log_loss(imp), "bins": md.calibration(imp),
                   "note": "Probabilidad implícita de la cuota (incluye el margen de la casa)"},
        "help": "Brier Score: 0 = perfecto, 0,25 = como lanzar una moneda en eventos 50/50. Menor es mejor.",
    }
    return out


def bet_dict(db: Session, b: BtBet) -> dict:
    legs = list(db.scalars(select(BtLeg).where(BtLeg.bet_id == b.id)))
    evs = {e.id: e for e in db.scalars(select(BtEvent).where(BtEvent.id.in_({l.event_id for l in legs})))}
    return {"id": b.id, "kind": b.kind, "stake": b.stake, "odds": b.odds, "potential_return": b.potential_return, "model_prob": b.model_prob,
            "user_prob": b.user_prob, "status": b.status, "returned": b.returned, "profit": b.profit, "reasoning": b.reasoning,
            "strategy": b.strategy, "warnings": b.warnings or [], "simulated": True, "created_at": b.created_at.isoformat(),
            "settled_at": b.settled_at.isoformat() if b.settled_at else None,
            "legs": [{"id": l.id, "event_id": l.event_id, "event": evs[l.event_id].name, "sport": evs[l.event_id].sport,
                      "starts_at": evs[l.event_id].starts_at.isoformat(), "market": l.market, "market_name": mk.MARKETS[l.market]["name"],
                      "pick": l.pick, "line": l.line, "opponent": l.opponent, "label": leg_label(evs[l.event_id], {"market": l.market, "pick": l.pick, "line": l.line, "opponent": l.opponent}),
                      "odds": l.odds, "odds_source": l.odds_source, "model_prob": l.model_prob, "status": l.status,
                      "result": evs[l.event_id].result, "event_status": evs[l.event_id].status} for l in legs]}

