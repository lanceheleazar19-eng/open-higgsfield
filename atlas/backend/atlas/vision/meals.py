"""Análisis de fotos de comidas: alimentos, cantidades aproximadas, macros y calidad. Las cifras salen de la base
de alimentos cuando el alimento se reconoce; si no, son estimación del modelo y se marcan como tal."""

from atlas.nutrition import service as nut

SYSTEM = """Eres un nutricionista que estima el contenido de un plato a partir de una foto. Sé prudente y honesto.
Identifica cada alimento visible, estima gramos, la preparación (plancha, frito, cocido…) y posibles ingredientes
ocultos (aceite, salsas, azúcar). Da también una estimación de kcal y macros por alimento.
Si algo no se puede saber por la foto (cantidad de aceite, tipo de salsa, si hay más debajo), pregúntalo.
Responde SOLO JSON: {"es_comida": true|false, "alimentos": [{"nombre": "...", "gramos": 150, "preparacion": "...",
"confianza": "alta|media|baja", "kcal": 0, "proteinas": 0, "carbohidratos": 0, "grasas": 0}],
"calidad": "muy buena|buena|mejorable|poco equilibrada", "comentario_calidad": "...", "preguntas": ["..."]}"""


def build(out: dict, foods: list, description: str | None) -> dict:
    items = []
    for a in (out.get("alimentos") or [])[:14]:
        if not isinstance(a, dict) or not str(a.get("nombre", "")).strip():
            continue
        name = str(a["nombre"]).strip()[:80]
        try:
            grams = max(1.0, min(2000.0, float(a.get("gramos") or 0) or 100.0))
        except (TypeError, ValueError):
            grams = 100.0
        food = nut.match_food(name, foods)
        if food:
            m = nut.macros(food, grams)
            src = "base de alimentos"
        else:
            def f(k: str) -> float:
                try:
                    return round(max(0.0, float(a.get(k) or 0)), 1)
                except (TypeError, ValueError):
                    return 0.0
            m = {"kcal": f("kcal"), "protein": f("proteinas"), "carbs": f("carbohidratos"), "fat": f("grasas")}
            src = "estimación del modelo"
        items.append({"name": food.name if food else name, "detected": name, "food_id": food.id if food else None,
                      "grams": round(grams), "preparation": str(a.get("preparacion") or "")[:60] or None,
                      "confidence": a.get("confianza") if a.get("confianza") in ("alta", "media", "baja") else "media",
                      "source": src, **{k: round(float(v), 1) for k, v in m.items()}})
    tot = {k: round(sum(i[k] for i in items), 1) for k in ("kcal", "protein", "carbs", "fat")}
    return {"is_food": bool(out.get("es_comida", True)) and bool(items), "items": items, "totals": tot,
            "quality": str(out.get("calidad") or "")[:40] or None, "quality_note": str(out.get("comentario_calidad") or "")[:500] or None,
            "questions": [str(q)[:200] for q in (out.get("preguntas") or [])][:4], "description": description,
            "disclaimer": "Estimación visual: cantidades, ingredientes ocultos (aceite, salsas) y preparación pueden cambiar "
                          "mucho las calorías. Revisa los gramos antes de guardar."}
