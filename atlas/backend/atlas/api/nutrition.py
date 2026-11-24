import base64
import io
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.brain.base import ProviderError
from atlas.brain.orchestrator import brain_status, get_provider
from atlas.gym.service import routine_for_day
from atlas.models import Food, MealEntry
from atlas.nutrition import service as nut
from atlas.services.preferences import get_prefs, set_prefs

try:  # fotos HEIC del iPhone
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])
MEAL_RX = "^(" + "|".join(nut.MEALS) + ")$"


def _now(db) -> datetime:  # noqa: ANN001
    return datetime.now(ZoneInfo(str(get_prefs(db)["timezone"]))).replace(tzinfo=None)


def _cfg(db) -> dict:  # noqa: ANN001
    return get_prefs(db).get("nutrition_profile") or {}


def _food(f: Food) -> dict:
    return {"id": f.id, "name": f.name, "kcal": f.kcal, "protein": f.protein, "carbs": f.carbs, "fat": f.fat,
            "unit_name": f.unit_name, "unit_grams": f.unit_grams, "custom": f.custom}


# ---------------------------------------------------------------- perfil y objetivos

class ProfileIn(BaseModel):
    sex: str = Field(pattern="^(male|female)$")
    age: int = Field(ge=12, le=100)
    height_cm: float = Field(ge=120, le=230)
    weight_kg: float | None = Field(default=None, ge=30, le=300)
    activity: float = Field(default=1.55, ge=1.2, le=1.9)
    goal: str = Field(default="maintain", pattern="^(bulk|cut|maintain)$")
    target_weight_kg: float | None = Field(default=None, ge=30, le=300)
    protein_per_kg: float = Field(default=1.8, ge=1.0, le=2.5)


@router.get("/profile")
def profile(db: DB) -> dict:
    cfg = _cfg(db)
    return {"profile": cfg or None, "targets": nut.compute_targets(cfg, nut.latest_weight(db)) if cfg else None,
            "latest_weight": nut.latest_weight(db)}


@router.put("/profile")
def save_profile(body: ProfileIn, db: DB) -> dict:
    set_prefs(db, {"nutrition_profile": body.model_dump()})
    db.commit()
    return profile(db)


# ---------------------------------------------------------------- día

@router.get("/day")
def day(db: DB, on: date | None = None) -> dict:
    now = _now(db)
    d = on or now.date()
    entries = list(db.scalars(select(MealEntry).where(MealEntry.eaten_on == d).order_by(MealEntry.id)))
    totals = nut.day_totals(db, d)
    cfg = _cfg(db)
    targets = nut.compute_targets(cfg, nut.latest_weight(db)) if cfg else None
    tips = nut.recommendations(db, totals, targets, now, routine_for_day(db, d) is not None) if d == now.date() else []
    return {"date": d.isoformat(), "entries": [nut.entry_dict(e) for e in entries], "totals": totals, "targets": targets,
            "tips": tips, "suggested_meal": nut.meal_for_time(now)}


@router.get("/week")
def week(db: DB) -> dict:
    return {"days": nut.week_series(db, _now(db).date())}


# ---------------------------------------------------------------- alimentos

@router.get("/foods")
def foods(db: DB, q: str = "") -> dict:
    rows = list(db.scalars(select(Food).order_by(Food.name)))
    if q.strip():
        n = nut.normalize(q)
        rows = [f for f in rows if n in nut.normalize(f.name) or any(n in nut.normalize(a) for a in f.aliases or [])]
    return {"items": [_food(f) for f in rows[:300]]}


class FoodIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    kcal: float = Field(ge=0, le=950)
    protein: float = Field(ge=0, le=100)
    carbs: float = Field(ge=0, le=100)
    fat: float = Field(ge=0, le=100)
    unit_name: str = Field(default="ración", max_length=32)
    unit_grams: float = Field(default=100, gt=0, le=2000)
    aliases: list[str] = Field(default_factory=list, max_length=10)


@router.post("/foods", status_code=201)
def add_food(body: FoodIn, db: DB) -> dict:
    if db.scalar(select(Food).where(Food.name == body.name.strip())):
        raise HTTPException(409, "Ya existe un alimento con ese nombre")
    f = Food(**{**body.model_dump(), "name": body.name.strip()}, custom=True)
    db.add(f)
    db.commit()
    return _food(f)


# ---------------------------------------------------------------- registro

class Item(BaseModel):
    food_id: int
    grams: float = Field(gt=0, le=3000)


class EntriesIn(BaseModel):
    meal: str = Field(pattern=MEAL_RX)
    items: list[Item] = Field(min_length=1, max_length=30)
    on: date | None = None
    source: str = Field(default="manual", pattern="^(manual|text|photo)$")


@router.post("/entries", status_code=201)
def add_entries(body: EntriesIn, db: DB) -> dict:
    pairs = []
    for it in body.items:
        f = db.get(Food, it.food_id)
        if not f:
            raise HTTPException(422, f"Alimento {it.food_id} inexistente")
        pairs.append((f, it.grams))  # macros calculadas en el servidor con la base de alimentos
    out = nut.add_entries(db, body.on or _now(db).date(), body.meal, pairs, body.source)
    db.commit()
    return {"items": [nut.entry_dict(e) for e in out]}


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: DB) -> None:
    e = db.get(MealEntry, entry_id)
    if not e:
        raise HTTPException(404, "Registro no encontrado")
    db.delete(e)
    db.commit()


class TextIn(BaseModel):
    text: str = Field(min_length=2, max_length=1000)


def _proposal(items: list[dict]) -> list[dict]:
    return [{"food": _food(i["food"]) if i["food"] else None, "grams": i["grams"], "text": i["name"],
             **(nut.macros(i["food"], i["grams"]) if i["food"] and i["grams"] else {})} for i in items]


@router.post("/parse")
def parse(body: TextIn, db: DB) -> dict:
    """Interpreta texto («2 huevos y una tostada») sin guardar."""
    return {"items": _proposal(nut.parse_meal_text(body.text, list(db.scalars(select(Food)))))}


@router.post("/photo")
async def photo(db: DB, file: UploadFile = File(...)) -> dict:
    """Analiza una foto con el modelo de visión local y PROPONE alimentos y gramos (no guarda nada).
    La foto no se almacena: se procesa en memoria y se descarta."""
    data = await file.read(15 * 1024 * 1024 + 1)
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "La foto supera 15 MB")
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(415, "El archivo no es una imagen válida") from exc
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    provider = get_provider()
    st = provider.status()
    model = nut.pick_vision_model(st.models) if st.reachable else None
    if not model:
        raise HTTPException(503, "No hay modelo de visión en Ollama. Instálalo con: ollama pull qwen2.5vl:7b"
                            if st.reachable else "Ollama no está disponible")
    try:
        out = provider.complete_json(model, [{"role": "user", "content": nut.PHOTO_PROMPT,
                                              "images": [base64.b64encode(buf.getvalue()).decode()]}])
    except ProviderError as exc:
        raise HTTPException(502, str(exc)) from exc
    foods_ = list(db.scalars(select(Food)))
    items = []
    for a in (out.get("alimentos") or [])[:12] if isinstance(out, dict) else []:
        name = str(a.get("nombre") or "").strip()
        try:
            grams = max(1.0, min(1500.0, float(a.get("gramos") or 0)))
        except (TypeError, ValueError):
            grams = None
        if name:
            items.append({"food": nut.match_food(name, foods_), "grams": grams, "name": name})
    return {"model": model, "items": _proposal(items), "note": "Estimación por foto: revisa los gramos antes de guardar."}
