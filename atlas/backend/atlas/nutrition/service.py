"""Nutrición: base de alimentos, interpretación de comidas en texto, fotos (modelo de visión),
objetivos (Mifflin-St Jeor) y recomendaciones. Las cifras salen de la base de alimentos."""

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.models import BodyMetric, Food, MealEntry
from atlas.services.activity import log_activity
from atlas.services.memory import normalize

FOODS_FILE = Path(__file__).parent / "foods.json"
MEALS = ("desayuno", "comida", "merienda", "cena", "snack")
NUM_WORDS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "medio": 0.5, "media": 0.5}
UNIT_WORDS = r"racion|raciones|plato|platos|vaso|vasos|taza|tazas|rebanada|rebanadas|cucharada|cucharadas|cucharadita|lata|latas|punado|punados|unidad|unidades|filete|filetes|bol|loncha|lonchas|pieza|piezas|cacito|cacitos|porcion|porciones|bola|bolas|pincho|tarrina"


def ensure_foods(db: Session) -> int:
    existing = set(db.scalars(select(Food.name)))
    added = 0
    for n, aliases, k, p, c, f, unit, grams in json.loads(FOODS_FILE.read_text(encoding="utf-8")):
        if n not in existing:
            db.add(Food(name=n, aliases=aliases, kcal=k, protein=p, carbs=c, fat=f, unit_name=unit, unit_grams=grams))
            added += 1
    db.commit()
    return added


def macros(food: Food, grams: float) -> dict:
    k = grams / 100
    return {"kcal": round(food.kcal * k, 1), "protein": round(food.protein * k, 1),
            "carbs": round(food.carbs * k, 1), "fat": round(food.fat * k, 1)}


def match_food(text: str, foods: list[Food]) -> Food | None:
    n = " " + normalize(text) + " "
    best, best_len = None, 0
    for f in foods:
        for a in [f.name, *(f.aliases or [])]:
            na = normalize(a)
            if na and f" {na} " in n and len(na) > best_len:
                best, best_len = f, len(na)
    return best


def parse_meal_text(text: str, foods: list[Food]) -> list[dict]:
    """«2 huevos, una tostada y un café con leche» → [{food, grams, name}] (sin match: food None)."""
    items = []
    for seg in re.split(r",|;|\+|\s+y\s+|\s+mas\s+|\n", text, flags=re.IGNORECASE):
        seg = seg.strip(" .")
        if not seg:
            continue
        n = normalize(seg)
        food = match_food(seg, foods)
        grams = None
        if m := re.search(r"(\d+(?:[.,]\d+)?)\s*(g|gr|gramos|ml|kg)\b", seg.lower()):
            v = float(m.group(1).replace(",", "."))
            grams = v * 1000 if m.group(2) == "kg" else v
        else:
            qty = 1.0
            if m := re.search(r"\b(\d+(?:[.,]\d+)?)\b", n):
                qty = float(m.group(1).replace(",", "."))
            elif m := re.search(r"\b(" + "|".join(NUM_WORDS) + r")\b", n):
                qty = NUM_WORDS[m.group(1)]
            if food:
                grams = qty * food.unit_grams
        if food is None:
            # descartar palabras sueltas de relleno («he desayunado», «para comer»)
            words = [w for w in n.split() if w not in ("he", "desayunado", "comido", "cenado", "merendado", "tomado", "de", "para", "hoy")]
            if words:
                items.append({"food": None, "grams": grams, "name": seg})
            continue
        items.append({"food": food, "grams": round(grams or food.unit_grams, 1), "name": food.name})
    return items


MEAL_TRIGGER = re.compile(
    r"^(?:atlas[,:\s]+)?(?:hoy\s+)?(?:he\s+(?P<verb>desayunado|comido|almorzado|merendado|cenado|tomado|picado)|"
    r"(?P<label>desayuno|comida|almuerzo|merienda|cena|snack)\s*:)\s*(?P<body>.+)$", re.IGNORECASE | re.DOTALL)
VERB_MEAL = {"desayunado": "desayuno", "comido": "comida", "almorzado": "comida", "merendado": "merienda",
             "cenado": "cena", "tomado": None, "picado": "snack"}


def meal_for_time(now: datetime) -> str:
    h = now.hour + now.minute / 60
    return "desayuno" if h < 11.5 else "comida" if h < 16.5 else "merienda" if h < 19.5 else "cena"


def parse_meal_command(text: str, now: datetime) -> tuple[str, str] | None:
    m = MEAL_TRIGGER.match(text.strip())
    if not m:
        return None
    meal = VERB_MEAL.get((m.group("verb") or "").lower()) if m.group("verb") else m.group("label").lower().replace("almuerzo", "comida")
    return meal or meal_for_time(now), m.group("body")


def add_entries(db: Session, day: date, meal: str, items: list[tuple[Food, float]], source: str) -> list[MealEntry]:
    out = []
    for food, grams in items:
        e = MealEntry(eaten_on=day, meal=meal, food_id=food.id, name=food.name, grams=grams, source=source, **macros(food, grams))
        db.add(e)
        out.append(e)
    db.flush()
    if out:
        log_activity(db, "nutrition", "log", f"Comida registrada ({meal}): " + ", ".join(e.name for e in out)[:90])
    return out


def entry_dict(e: MealEntry) -> dict:
    return {"id": e.id, "date": e.eaten_on.isoformat(), "meal": e.meal, "food_id": e.food_id, "name": e.name, "grams": e.grams,
            "kcal": e.kcal, "protein": e.protein, "carbs": e.carbs, "fat": e.fat, "source": e.source}


# ---------------------------------------------------------------- objetivos

def latest_weight(db: Session) -> float | None:
    return db.scalar(select(BodyMetric.weight_kg).where(BodyMetric.weight_kg.is_not(None))
                     .order_by(BodyMetric.measured_on.desc(), BodyMetric.id.desc()).limit(1))


def compute_targets(cfg: dict, weight: float | None) -> dict | None:
    """Mifflin-St Jeor × actividad + ajuste por objetivo. None si faltan datos."""
    w = weight or cfg.get("weight_kg")
    if not all([w, cfg.get("height_cm"), cfg.get("age"), cfg.get("sex")]):
        return None
    bmr = 10 * w + 6.25 * cfg["height_cm"] - 5 * cfg["age"] + (5 if cfg["sex"] == "male" else -161)
    tdee = bmr * cfg.get("activity", 1.55)
    adj = {"bulk": 300, "cut": -400, "maintain": 0}[cfg.get("goal", "maintain")]
    kcal = round(tdee + adj)
    protein = round(w * cfg.get("protein_per_kg", 1.8))
    fat = round(w * 0.9)
    carbs = max(0, round((kcal - protein * 4 - fat * 9) / 4))
    return {"bmr": round(bmr), "tdee": round(tdee), "kcal": kcal, "protein": protein, "carbs": carbs, "fat": fat, "weight_used": w}


def day_totals(db: Session, day: date) -> dict:
    row = db.execute(select(func.coalesce(func.sum(MealEntry.kcal), 0), func.coalesce(func.sum(MealEntry.protein), 0),
                            func.coalesce(func.sum(MealEntry.carbs), 0), func.coalesce(func.sum(MealEntry.fat), 0))
                     .where(MealEntry.eaten_on == day)).one()
    return {"kcal": round(row[0]), "protein": round(row[1], 1), "carbs": round(row[2], 1), "fat": round(row[3], 1)}


PROTEIN_SOURCES = ["Pechuga de pollo", "Atún en lata", "Yogur proteico", "Queso batido", "Huevo", "Batido de proteína", "Pavo"]


def recommendations(db: Session, totals: dict, targets: dict | None, now: datetime, training_today: bool) -> list[str]:
    if not targets:
        return ["Completa tu perfil nutricional (edad, altura, sexo, objetivo) para calcular tus objetivos."]
    tips = []
    kcal_left = targets["kcal"] - totals["kcal"]
    prot_left = round(targets["protein"] - totals["protein"])
    if prot_left > 15:
        foods = {f.name: f for f in db.scalars(select(Food).where(Food.name.in_(PROTEIN_SOURCES)))}
        opts = []
        for n in PROTEIN_SOURCES[:4]:
            f = foods.get(n)
            if f and f.protein:
                g = min(400, round(prot_left / 2 / f.protein * 100 / 10) * 10)  # media del déficit con este alimento
                opts.append(f"{g} g de {f.name.lower()} (+{round(f.protein * g / 100)} g)")
        tips.append(f"Te faltan {prot_left} g de proteína. Opciones: " + "; ".join(opts[:3]) + ".")
    if kcal_left > 500 and now.hour >= 18:
        tips.append(f"Te quedan {kcal_left} kcal para tu objetivo. Para ganar volumen, no te saltes la cena y añade hidratos (arroz, pasta, patata).")
    elif kcal_left < -300:
        tips.append(f"Hoy vas {-kcal_left} kcal por encima del objetivo. Si se repite a menudo, ganarás más grasa de la necesaria.")
    if training_today and totals["carbs"] < targets["carbs"] * 0.4 and now.hour < 18:
        tips.append("Hoy entrenas: toma hidratos 1-2 h antes (avena, arroz, plátano) para rendir mejor.")
    return tips


def week_series(db: Session, today: date) -> list[dict]:
    out = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        out.append({"date": d.isoformat(), **day_totals(db, d)})
    return out


# ---------------------------------------------------------------- fotos (modelo de visión local)

VISION_HINTS = ("vl", "vision", "llava", "moondream", "minicpm-v", "bakllava")

PHOTO_PROMPT = """Eres un analista de nutrición. Identifica cada alimento visible en la foto del plato y estima su
peso en gramos. Usa nombres comunes en español (p. ej. «arroz blanco», «pechuga de pollo», «ensalada»).
Responde SOLO con JSON: {"alimentos": [{"nombre": "...", "gramos": 150}]}. Si no es comida, {"alimentos": []}."""


def pick_vision_model(models: list) -> str | None:
    for m in models:
        n = m.name.lower()
        if any(h in n for h in VISION_HINTS):
            return m.name
    return None
