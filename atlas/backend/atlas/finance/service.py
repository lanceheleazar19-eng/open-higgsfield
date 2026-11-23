"""Finanzas personales (DINERO REAL). ATLAS solo registra y analiza: nunca mueve dinero."""

import re
import unicodedata
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.models import Budget, Transaction

EXPENSE_CATS = {
    "comida": ["comida", "comer", "restaurante", "cena", "almuerzo", "desayuno", "super", "supermercado", "mercadona",
               "mcdonalds", "burger", "kebab", "pizza", "cafe", "bar"],
    "transporte": ["transporte", "gasolina", "bus", "autobus", "metro", "tren", "taxi", "uber", "cabify", "moto", "parking"],
    "ocio": ["ocio", "cine", "fiesta", "salir", "juego", "juegos", "concierto", "discoteca", "viaje"],
    "ropa": ["ropa", "zapatillas", "camiseta", "pantalon", "zara", "nike"],
    "gimnasio": ["gimnasio", "gym", "suplementos", "proteina", "creatina"],
    "suscripciones": ["suscripcion", "suscripciones", "netflix", "spotify", "hbo", "disney", "icloud", "youtube"],
    "salud": ["salud", "farmacia", "medico", "dentista"],
    "estudios": ["estudios", "libros", "libro", "material", "academia", "matricula", "curso"],
    "tecnologia": ["tecnologia", "movil", "ordenador", "auriculares", "cascos"],
    "hogar": ["hogar", "casa", "alquiler", "luz", "agua", "internet"],
    "regalos": ["regalo", "regalos"],
}
INCOME_CATS = {
    "nómina": ["nomina", "sueldo", "salario", "trabajo"],
    "extra": ["extra", "propina", "propinas", "chapuza", "bonus"],
    "regalo": ["regalo", "paga", "cumpleanos"],
    "venta": ["venta", "vendido", "wallapop", "vinted"],
}


def _n(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def guess_category(text: str, kind: str) -> str:
    words = set(re.findall(r"[a-z0-9]+", _n(text)))
    for cat, keys in (EXPENSE_CATS if kind == "expense" else INCOME_CATS).items():
        if words & set(keys):
            return cat
    return "otros"


AMOUNT = r"(\d{1,7}(?:[.,]\d{1,2})?)\s*(?:€|euros?|eur|pavos)?"
EXP_RE = re.compile(rf"^(?:he\s+gastado|me\s+he\s+gastado|gaste|gasto(?:\s+de)?|he\s+pagado|pague|pago(?:\s+de)?)\s+{AMOUNT}\s*(?:(?:en|de|por|para)\s+)?(.*)$")
INC_RE = re.compile(rf"^(?:he\s+cobrado|cobre|cobro|ingreso(?:\s+de)?|me\s+han\s+pagado|me\s+han\s+dado|he\s+ganado|gane|he\s+recibido)\s+{AMOUNT}\s*(?:(?:de|por|en|del)\s+)?(.*)$")


def to_cents(s: str) -> int:
    return round(float(s.replace(",", ".")) * 100)


def parse_money_command(text: str) -> dict | None:
    """«he gastado 12,50 en comida» → gasto. «ingreso 300 nómina» → ingreso. Solo REGISTRA, no mueve dinero."""
    t = _n(text.strip()).rstrip(".!")
    for kind, rx in (("expense", EXP_RE), ("income", INC_RE)):
        m = rx.match(t)
        if m:
            cents = to_cents(m.group(1))
            if cents <= 0:
                return None
            desc = text.strip().rstrip(".!")
            rest = m.group(2).strip()
            return {"kind": kind, "amount_cents": cents, "category": guess_category(rest or t, kind),
                    "description": rest[:200] or None, "raw": desc}
    return None


def to_dict(t: Transaction) -> dict:
    return {"id": t.id, "kind": t.kind, "amount_cents": t.amount_cents, "currency": t.currency,
            "category": t.category, "description": t.description, "occurred_on": t.occurred_on.isoformat()}


def month_bounds(month: str | None, today: date) -> tuple[date, date]:
    start = date.fromisoformat(month + "-01") if month else today.replace(day=1)
    return start, (start + timedelta(days=32)).replace(day=1)


def _sum(db: Session, kind: str, start: date, end: date) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
        Transaction.kind == kind, Transaction.occurred_on >= start, Transaction.occurred_on < end)) or 0)


def budget_status(db: Session, start: date, end: date) -> list[dict]:
    spent = dict(db.execute(select(Transaction.category, func.sum(Transaction.amount_cents)).where(
        Transaction.kind == "expense", Transaction.occurred_on >= start, Transaction.occurred_on < end)
        .group_by(Transaction.category)).all())
    out = []
    for b in db.scalars(select(Budget).order_by(Budget.category)):
        s = int(spent.get(b.category) or 0)
        pct = round(100 * s / b.monthly_cents) if b.monthly_cents else 0
        out.append({"category": b.category, "monthly_cents": b.monthly_cents, "spent_cents": s, "pct": pct,
                    "status": "over" if s > b.monthly_cents else "warning" if pct >= 80 else "ok"})
    return out


def summary(db: Session, today: date, month: str | None = None) -> dict:
    start, end = month_bounds(month, today)
    income, expense = _sum(db, "income", start, end), _sum(db, "expense", start, end)
    cats = db.execute(select(Transaction.category, func.sum(Transaction.amount_cents)).where(
        Transaction.kind == "expense", Transaction.occurred_on >= start, Transaction.occurred_on < end)
        .group_by(Transaction.category).order_by(func.sum(Transaction.amount_cents).desc())).all()
    months, m = [], start
    for _ in range(6):  # últimos 6 meses (solo con datos registrados)
        e = (m + timedelta(days=32)).replace(day=1)
        i_, x_ = _sum(db, "income", m, e), _sum(db, "expense", m, e)
        months.append({"month": m.strftime("%Y-%m"), "income_cents": i_, "expense_cents": x_, "net_cents": i_ - x_})
        m = (m - timedelta(days=1)).replace(day=1)
    total = int(db.scalar(select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(Transaction.kind == "income")) or 0) \
        - int(db.scalar(select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(Transaction.kind == "expense")) or 0)
    return {
        "month": start.strftime("%Y-%m"), "income_cents": income, "expense_cents": expense, "net_cents": income - expense,
        "savings_rate": round(100 * (income - expense) / income) if income else None,
        "balance_cents": total, "by_category": [{"category": c or "otros", "cents": int(v)} for c, v in cats],
        "budgets": budget_status(db, start, end), "months": list(reversed(months)),
        "count": db.scalar(select(func.count(Transaction.id)).where(Transaction.occurred_on >= start, Transaction.occurred_on < end)) or 0,
    }
