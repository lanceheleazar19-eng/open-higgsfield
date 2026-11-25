"""Estadísticas calculadas SOLO con operaciones cerradas registradas. Sin operaciones → valores None."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.models import TdAccount, TdEquity, TdJournal, TdPosition


def _block(pnls: list[float]) -> dict:
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gw, gl = sum(wins), -sum(losses)
    return {"trades": n, "wins": len(wins), "losses": len(losses),
            "win_rate": round(len(wins) / n * 100, 2) if n else None,
            "net": round(sum(pnls), 2) if n else None, "gross_profit": round(gw, 2) if n else None,
            "gross_loss": round(gl, 2) if n else None,
            "profit_factor": round(gw / gl, 2) if gl > 0 else (None if not wins else "∞"),
            "avg_win": round(gw / len(wins), 2) if wins else None, "avg_loss": round(-gl / len(losses), 2) if losses else None,
            "best": round(max(pnls), 2) if n else None, "worst": round(min(pnls), 2) if n else None,
            "expectancy": round(sum(pnls) / n, 2) if n else None}


def closed_positions(db: Session, account_id: int | None = None, symbol: str | None = None,
                     start: datetime | None = None, end: datetime | None = None, strategy: str | None = None) -> list[TdPosition]:
    q = select(TdPosition).where(TdPosition.status == "closed")
    if account_id:
        q = q.where(TdPosition.account_id == account_id)
    if symbol:
        q = q.where(TdPosition.symbol == symbol)
    if strategy:
        q = q.where(TdPosition.strategy == strategy)
    if start:
        q = q.where(TdPosition.closed_at >= start)
    if end:
        q = q.where(TdPosition.closed_at <= end)
    return list(db.scalars(q.order_by(TdPosition.closed_at)))


def stats(db: Session, acc: TdAccount, **filters) -> dict:
    ps = closed_positions(db, acc.id, **filters)
    pnls = [p.realized_pnl or 0.0 for p in ps]
    out = _block(pnls)
    # Curva de capital por operaciones cerradas y drawdown máximo sobre esa curva
    curve, eq, peak, mdd = [], acc.initial_capital, acc.initial_capital, 0.0
    for p in ps:
        eq += p.realized_pnl or 0
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak * 100 if peak else 0)
        curve.append({"t": p.closed_at.isoformat(), "equity": round(eq, 2), "symbol": p.symbol, "pnl": p.realized_pnl})
    out["max_drawdown_pct"] = round(mdd, 2) if ps else None
    out["curve"] = curve
    out["equity_series"] = [{"t": e.ts.isoformat(), "equity": e.equity, "event": e.event}
                            for e in db.scalars(select(TdEquity).where(TdEquity.account_id == acc.id).order_by(TdEquity.ts))]
    rs = [p.realized_pnl / p.risk_money for p in ps if p.risk_money]
    out["avg_r"] = round(sum(rs) / len(rs), 2) if rs else None
    for key, attr in (("by_symbol", "symbol"), ("by_strategy", "strategy"), ("by_timeframe", "timeframe"), ("by_exit", "exit_reason")):
        groups: dict[str, list[float]] = defaultdict(list)
        for p in ps:
            groups[getattr(p, attr) or "sin indicar"].append(p.realized_pnl or 0)
        out[key] = sorted(({"key": k, **_block(v)} for k, v in groups.items()), key=lambda x: -(x["net"] or 0))
    durs = [(p.closed_at - p.opened_at).total_seconds() / 3600 for p in ps if p.closed_at]
    out["avg_hours"] = round(sum(durs) / len(durs), 2) if durs else None
    return out


def journal_patterns(db: Session, acc: TdAccount) -> dict:
    """Patrones de comportamiento a partir del diario y de las operaciones (solo hechos contados)."""
    ps = closed_positions(db, acc.id)
    by_id = {p.id: p for p in ps}
    js = [j for j in db.scalars(select(TdJournal)) if j.position_id in by_id]
    mistakes = Counter(m for j in js for m in (j.mistakes or []))
    emo: dict[str, list[float]] = defaultdict(list)
    for j in js:
        if j.emotion:
            emo[j.emotion].append(by_id[j.position_id].realized_pnl or 0)
    mistake_pnl: dict[str, list[float]] = defaultdict(list)
    for j in js:
        for m in j.mistakes or []:
            mistake_pnl[m].append(by_id[j.position_id].realized_pnl or 0)
    no_stop = [p for p in ps if p.risk_money is None]
    over_risk = [p for p in ps if p.risk_money and acc.max_risk_pct and p.risk_money / acc.initial_capital * 100 > acc.max_risk_pct]
    # rachas: ¿se opera más tamaño tras una pérdida? (posible «revenge trading»)
    after_loss = [b for a, b in zip(ps, ps[1:]) if (a.realized_pnl or 0) < 0 and b.reserved > a.reserved * 1.5]
    findings = []
    if mistakes:
        m, n = mistakes.most_common(1)[0]
        findings.append(f"Error más repetido en tu diario: «{m}» ({n} veces)")
    if no_stop:
        findings.append(f"{len(no_stop)} de {len(ps)} operaciones cerradas no tenían stop loss")
    if over_risk:
        findings.append(f"{len(over_risk)} operaciones superaron tu riesgo máximo por operación")
    if after_loss:
        findings.append(f"{len(after_loss)} veces aumentaste mucho el tamaño justo después de una pérdida (posible revancha)")
    neg_emo = [(k, sum(v) / len(v), len(v)) for k, v in emo.items() if len(v) >= 2 and sum(v) < 0]
    for k, avg, n in sorted(neg_emo, key=lambda x: x[1])[:2]:
        findings.append(f"Cuando operas con «{k}» tu resultado medio es {avg:+.2f} ({n} operaciones)")
    return {"closed": len(ps), "journaled": len(js), "mistakes": mistakes.most_common(10),
            "mistake_pnl": {k: round(sum(v), 2) for k, v in mistake_pnl.items()},
            "emotions": {k: {"trades": len(v), "net": round(sum(v), 2)} for k, v in emo.items()},
            "no_stop": len(no_stop), "over_risk": len(over_risk), "size_up_after_loss": len(after_loss), "findings": findings}
