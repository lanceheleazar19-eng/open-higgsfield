"""Paper trading: SIMULACIÓN con capital virtual. Ninguna operación llega a un bróker real."""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.models import PaperTrade
from atlas.models.base import utcnow
from atlas.services.preferences import get_prefs, set_prefs
from atlas.trading import service as svc

router = APIRouter(prefix="/api/trading", tags=["trading"])


class TradeIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: str = Field(pattern="^(long|short)$")
    quantity: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    strategy: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)
    opened_at: datetime | None = None

    @model_validator(mode="after")
    def check(self):
        long = self.side == "long"
        if self.stop_loss is not None and (self.stop_loss >= self.entry_price if long else self.stop_loss <= self.entry_price):
            raise ValueError("El stop loss debe estar " + ("por debajo" if long else "por encima") + " de la entrada")
        if self.take_profit is not None and (self.take_profit <= self.entry_price if long else self.take_profit >= self.entry_price):
            raise ValueError("El take profit debe estar " + ("por encima" if long else "por debajo") + " de la entrada")
        return self


class CloseIn(BaseModel):
    exit_price: float = Field(gt=0)
    closed_at: datetime | None = None
    mistakes: list[str] = Field(default_factory=list, max_length=10)
    notes: str | None = Field(default=None, max_length=2000)


class CapitalIn(BaseModel):
    amount: float = Field(gt=0, le=10**9)


@router.get("/trades")
def list_trades(db: DB) -> list[dict]:
    return [svc.to_dict(t) for t in db.scalars(select(PaperTrade).order_by(PaperTrade.opened_at.desc(), PaperTrade.id.desc()))]


@router.post("/trades", status_code=201)
def open_trade(body: TradeIn, db: DB) -> dict:
    t = PaperTrade(**body.model_dump(exclude={"opened_at"}), opened_at=body.opened_at or utcnow(), mistakes=[])
    t.symbol = t.symbol.strip().upper()
    t.strategy = (t.strategy or "").strip() or None
    db.add(t)
    db.commit()
    return svc.to_dict(t)


def _trade(db, trade_id: int) -> PaperTrade:  # noqa: ANN001
    t = db.get(PaperTrade, trade_id)
    if not t:
        raise HTTPException(404, "Operación no encontrada")
    return t


@router.post("/trades/{trade_id}/close")
def close_trade(trade_id: int, body: CloseIn, db: DB) -> dict:
    t = _trade(db, trade_id)
    if t.closed_at:
        raise HTTPException(409, "La operación ya está cerrada")
    t.exit_price = body.exit_price
    t.closed_at = body.closed_at or utcnow()
    t.mistakes = sorted({m.strip().lower()[:40] for m in body.mistakes if m.strip()})
    if body.notes:
        t.notes = ((t.notes + "\n") if t.notes else "") + body.notes
    db.commit()
    return svc.to_dict(t)


@router.delete("/trades/{trade_id}", status_code=204)
def delete_trade(trade_id: int, db: DB) -> None:
    db.delete(_trade(db, trade_id))
    db.commit()


@router.get("/stats")
def get_stats(db: DB) -> dict:
    cap = get_prefs(db).get("paper_capital")
    return svc.stats(db, float(cap) if cap else None)


@router.put("/capital")
def put_capital(body: CapitalIn, db: DB) -> dict:
    set_prefs(db, {"paper_capital": body.amount})
    db.commit()
    return {"paper_capital": body.amount}
