"""Apple Salud vía Atajo del iPhone. El Atajo envía un POST con la clave en la cabecera X-Atlas-Token.
ATLAS no accede a HealthKit directamente: solo recibe lo que tu Atajo decide enviar."""

import secrets as pysecrets
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.integrations.secrets import get_secret, set_secret
from atlas.models import BodyMetric, HealthDay
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/health", tags=["health"])
FIELDS = ("steps", "sleep_hours", "weight_kg", "active_kcal", "distance_km", "resting_hr")
SUM_FIELDS = {"steps", "sleep_hours", "active_kcal", "distance_km"}
LIMITS = {"steps": 200000, "sleep_hours": 24, "weight_kg": 400, "active_kcal": 20000, "distance_km": 300, "resting_hr": 250}


def _num(v):  # noqa: ANN001, ANN202
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().split()[0].replace(",", ".")  # «8.432 pasos», «75,4 kg», «7,5»
    if s.count(".") > 1:  # separador de miles: 8.432.100
        s = s.replace(".", "")
    return float(s)


class HealthIn(BaseModel):
    day: date | None = None
    steps: float | None = None
    sleep_hours: float | None = None
    sleep_minutes: float | None = None
    weight_kg: float | None = None
    active_kcal: float | None = None
    distance_km: float | None = None
    resting_hr: float | None = None

    @field_validator("steps", "sleep_hours", "sleep_minutes", "weight_kg", "active_kcal", "distance_km", "resting_hr",
                     mode="before")
    @classmethod
    def lenient(cls, v, info):  # noqa: ANN001, ANN206
        """El Atajo puede mandar números como texto o listas de muestras (las suma o toma la última)."""
        if isinstance(v, str) and "\n" in v:
            v = [x for x in v.splitlines() if x.strip()]
        if isinstance(v, list):
            nums = [n for n in (_num(x) for x in v) if n is not None]
            if not nums:
                return None
            return sum(nums) if info.field_name in SUM_FIELDS | {"sleep_minutes"} else nums[-1]
        try:
            return _num(v)
        except ValueError as e:
            raise ValueError("Número no válido") from e


def _token() -> str:
    t = get_secret("health_token")
    if not t:
        t = pysecrets.token_urlsafe(24)
        set_secret("health_token", t)
    return t


def day_dict(h: HealthDay) -> dict:
    return {"day": h.day.isoformat(), **{f: getattr(h, f) for f in FIELDS}}


@router.post("/ingest")
def ingest(body: HealthIn, db: DB, x_atlas_token: str | None = Header(default=None)) -> dict:
    expected = get_secret("health_token")
    if not expected or not x_atlas_token or not pysecrets.compare_digest(x_atlas_token, expected):
        raise HTTPException(401, "Clave de ATLAS incorrecta")
    data = body.model_dump()
    if data.get("sleep_minutes") is not None and data.get("sleep_hours") is None:
        data["sleep_hours"] = data["sleep_minutes"] / 60
    vals = {f: data[f] for f in FIELDS if data.get(f) is not None}
    for f, v in vals.items():
        if not 0 <= v <= LIMITS[f]:
            raise HTTPException(422, f"Valor fuera de rango: {f}")
    if not vals:
        raise HTTPException(422, "No llegó ningún dato")
    if "steps" in vals:
        vals["steps"] = int(round(vals["steps"]))
    for f in ("sleep_hours", "distance_km", "weight_kg"):
        if f in vals:
            vals[f] = round(vals[f], 2)
    day = body.day or datetime.now(ZoneInfo(str(get_prefs(db)["timezone"]))).date()
    h = db.scalar(select(HealthDay).where(HealthDay.day == day)) or HealthDay(day=day)
    for f, v in vals.items():
        setattr(h, f, v)
    db.add(h)
    if "weight_kg" in vals:  # el peso también alimenta Gimnasio y Nutrición
        bm = db.scalar(select(BodyMetric).where(BodyMetric.measured_on == day, BodyMetric.notes == "Apple Salud"))
        if bm:
            bm.weight_kg = vals["weight_kg"]
        else:
            db.add(BodyMetric(measured_on=day, weight_kg=vals["weight_kg"], notes="Apple Salud"))
    db.commit()
    return {"ok": True, "day": day.isoformat(), "saved": sorted(vals)}


@router.get("/days")
def days(db: DB, n: int = 30) -> list[dict]:
    since = datetime.now(ZoneInfo(str(get_prefs(db)["timezone"]))).date() - timedelta(days=max(1, min(n, 365)) - 1)
    return [day_dict(h) for h in db.scalars(select(HealthDay).where(HealthDay.day >= since).order_by(HealthDay.day))]


@router.get("/setup")
def setup() -> dict:
    return {"token": _token(), "path": "/api/health/ingest", "header": "X-Atlas-Token", "fields": [*FIELDS, "sleep_minutes", "day"]}


@router.post("/token")
def rotate() -> dict:
    t = pysecrets.token_urlsafe(24)
    set_secret("health_token", t)
    return {"token": t}


def snapshot(db, today: date) -> dict:  # noqa: ANN001
    """Últimos 7 días registrados por el Atajo (para la IA). Solo datos reales."""
    rows = list(db.scalars(select(HealthDay).where(HealthDay.day > today - timedelta(days=7)).order_by(HealthDay.day)))
    def avg(f):  # noqa: ANN001, ANN202
        v = [getattr(r, f) for r in rows if getattr(r, f) is not None]
        return round(sum(v) / len(v), 1) if v else None
    return {"dias_registrados": len(rows), "media_pasos": avg("steps"), "media_sueno_h": avg("sleep_hours"),
            "media_kcal_activas": avg("active_kcal"), "dias": [day_dict(r) for r in rows]} if rows else {"dias_registrados": 0}
