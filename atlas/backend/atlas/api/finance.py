"""Finanzas: DINERO REAL. Solo registro y análisis. VISTAN nunca hace transferencias ni pagos."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.finance import service as fin
from atlas.models import Budget, Transaction
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/finance", tags=["finance"])


def _today(db) -> date:  # noqa: ANN001
    return datetime.now(ZoneInfo(str(get_prefs(db)["timezone"]))).date()


class TxIn(BaseModel):
    kind: str = Field(pattern="^(income|expense)$")
    amount_cents: int = Field(gt=0, le=10**10)
    category: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    occurred_on: date | None = None


class TxPatch(BaseModel):
    kind: str | None = Field(default=None, pattern="^(income|expense)$")
    amount_cents: int | None = Field(default=None, gt=0, le=10**10)
    category: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    occurred_on: date | None = None


class BudgetIn(BaseModel):
    monthly_cents: int = Field(gt=0, le=10**10)


@router.get("/transactions")
def list_tx(db: DB, month: str | None = None) -> list[dict]:
    start, end = fin.month_bounds(month, _today(db))
    q = select(Transaction).where(Transaction.occurred_on >= start, Transaction.occurred_on < end)
    return [fin.to_dict(t) for t in db.scalars(q.order_by(Transaction.occurred_on.desc(), Transaction.id.desc()))]


@router.post("/transactions", status_code=201)
def create_tx(body: TxIn, db: DB) -> dict:
    cat = (body.category or "").strip().lower() or fin.guess_category(body.description or "", body.kind)
    t = Transaction(kind=body.kind, amount_cents=body.amount_cents, category=cat, description=body.description,
                    occurred_on=body.occurred_on or _today(db), currency=str(get_prefs(db)["currency"]))
    db.add(t)
    db.commit()
    return fin.to_dict(t)


def _tx(db, tx_id: int) -> Transaction:  # noqa: ANN001
    t = db.get(Transaction, tx_id)
    if not t:
        raise HTTPException(404, "Movimiento no encontrado")
    return t


@router.patch("/transactions/{tx_id}")
def patch_tx(tx_id: int, body: TxPatch, db: DB) -> dict:
    t = _tx(db, tx_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(t, k, v.strip().lower() if k == "category" else v)
    db.commit()
    return fin.to_dict(t)


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_tx(tx_id: int, db: DB) -> None:
    db.delete(_tx(db, tx_id))
    db.commit()


@router.get("/summary")
def get_summary(db: DB, month: str | None = None) -> dict:
    return fin.summary(db, _today(db), month)


@router.get("/categories")
def categories() -> dict:
    return {"expense": [*fin.EXPENSE_CATS, "otros"], "income": [*fin.INCOME_CATS, "otros"]}


@router.put("/budgets/{category}")
def put_budget(category: str, body: BudgetIn, db: DB) -> dict:
    cat = category.strip().lower()[:64]
    b = db.scalar(select(Budget).where(Budget.category == cat))
    if b:
        b.monthly_cents = body.monthly_cents
    else:
        db.add(Budget(category=cat, monthly_cents=body.monthly_cents))
    db.commit()
    return {"category": cat, "monthly_cents": body.monthly_cents}


@router.delete("/budgets/{category}", status_code=204)
def delete_budget(category: str, db: DB) -> None:
    b = db.scalar(select(Budget).where(Budget.category == category.strip().lower()))
    if not b:
        raise HTTPException(404, "Presupuesto no encontrado")
    db.delete(b)
    db.commit()
