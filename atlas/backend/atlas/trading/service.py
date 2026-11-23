"""Paper trading: SOLO SIMULACIÓN con capital virtual. No hay conexión con ningún bróker."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.models import PaperTrade


def _sign(t: PaperTrade) -> int:
    return 1 if t.side == "long" else -1


def risk(t: PaperTrade) -> float | None:
    return abs(t.entry_price - t.stop_loss) * t.quantity if t.stop_loss is not None else None


def pnl(t: PaperTrade) -> float | None:
    return (t.exit_price - t.entry_price) * t.quantity * _sign(t) if t.exit_price is not None else None


def planned_rr(t: PaperTrade) -> float | None:
    if t.stop_loss is None or t.take_profit is None or t.entry_price == t.stop_loss:
        return None
    return round(abs(t.take_profit - t.entry_price) / abs(t.entry_price - t.stop_loss), 2)


def r_multiple(t: PaperTrade) -> float | None:
    p, r = pnl(t), risk(t)
    return round(p / r, 2) if p is not None and r else None


def to_dict(t: PaperTrade) -> dict:
    p = pnl(t)
    return {"id": t.id, "symbol": t.symbol, "side": t.side, "quantity": t.quantity, "entry_price": t.entry_price,
            "stop_loss": t.stop_loss, "take_profit": t.take_profit, "exit_price": t.exit_price,
            "opened_at": t.opened_at.isoformat(), "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            "strategy": t.strategy, "mistakes": t.mistakes or [], "notes": t.notes, "status": "closed" if t.closed_at else "open",
            "pnl": round(p, 2) if p is not None else None, "risk": round(risk(t), 2) if risk(t) is not None else None,
            "planned_rr": planned_rr(t), "r": r_multiple(t)}


def _agg(trades: list[PaperTrade]) -> dict:
    ps = [pnl(t) for t in trades]
    wins = [p for p in ps if p > 0]
    losses = [p for p in ps if p < 0]
    rs = [r for r in (r_multiple(t) for t in trades) if r is not None]
    gl = -sum(losses)
    return {"trades": len(ps), "wins": len(wins), "losses": len(losses),
            "win_rate": round(100 * len(wins) / len(ps), 1) if ps else None,
            "pnl": round(sum(ps), 2), "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
            "profit_factor": round(sum(wins) / gl, 2) if gl else None,
            "expectancy": round(sum(ps) / len(ps), 2) if ps else None,
            "avg_r": round(sum(rs) / len(rs), 2) if rs else None}


def stats(db: Session, initial_capital: float | None) -> dict:
    closed = list(db.scalars(select(PaperTrade).where(PaperTrade.closed_at.is_not(None)).order_by(PaperTrade.closed_at)))
    opened = list(db.scalars(select(PaperTrade).where(PaperTrade.closed_at.is_(None)).order_by(PaperTrade.opened_at)))
    base = initial_capital or 0.0
    eq, peak, max_dd, curve = base, base, 0.0, []
    for t in closed:
        eq += pnl(t)
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
        curve.append({"date": t.closed_at.date().isoformat(), "equity": round(eq, 2)})
    by_strat: dict[str, list] = defaultdict(list)
    mist: dict[str, list] = defaultdict(list)
    for t in closed:
        by_strat[t.strategy or "sin estrategia"].append(t)
        for m in t.mistakes or []:
            mist[m].append(t)
    no_sl = sum(1 for t in closed if t.stop_loss is None)
    return {
        "simulation": True, "initial_capital": initial_capital,
        "equity": round(eq, 2) if initial_capital is not None else None,
        "return_pct": round(100 * (eq - base) / base, 2) if initial_capital else None,
        "max_drawdown": round(max_dd, 2), "max_drawdown_pct": round(100 * max_dd / peak, 2) if initial_capital and peak else None,
        "overall": _agg(closed), "curve": curve,
        "by_strategy": sorted(({"strategy": k, **_agg(v)} for k, v in by_strat.items()), key=lambda x: -x["pnl"]),
        "mistakes": sorted(({"mistake": k, "count": len(v), "pnl": round(sum(pnl(t) for t in v), 2)} for k, v in mist.items()),
                           key=lambda x: (-x["count"], x["pnl"])),
        "without_stop": no_sl,
        "open": [to_dict(t) for t in opened],
        "open_risk": round(sum(risk(t) or 0 for t in opened), 2),
    }
