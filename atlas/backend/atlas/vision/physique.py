"""Análisis visual del físico. Reglas: solo lo visible, sin % de grasa ni medidas, sin diagnósticos médicos,
y advirtiendo cuando luz, distancia, postura o ángulo hacen la comparación poco fiable."""

import re
from datetime import date

SYSTEM = """Eres un entrenador personal experto en hipertrofia que analiza fotos de progreso físico de tu cliente
(un adolescente de 17 años que entrena 4 días por semana para ganar volumen). Analiza SOLO lo que se ve.
Reglas estrictas:
- NO estimes porcentaje de grasa corporal, peso, ni medidas (cm, kg, %). Nunca des números sobre el cuerpo.
- NO hagas diagnósticos médicos ni comentarios sobre salud; si algo te preocupa, sugiere consultar a un profesional.
- Si comparas fotos, evalúa primero si son comparables: iluminación, distancia, postura, ángulo, bombeo, ropa.
  Si no lo son, dilo y baja la fiabilidad; no confundas diferencias de foto con cambios reales.
- Lenguaje respetuoso, motivador y concreto. Español.
- Usa los DATOS DE ENTRENAMIENTO dados para que las recomendaciones encajen con su rutina real.
Responde SOLO JSON con estas claves:
{"fiabilidad": "alta|media|baja", "motivos_fiabilidad": ["..."], "observaciones": ["..."], "mas_desarrollados": ["..."],
 "a_trabajar": ["..."], "simetria": "...", "cambios": ["... (solo si comparas)"], "recomendaciones_entrenamiento": ["..."],
 "habitos": ["..."], "relacion_con_datos": "cómo encaja con su entrenamiento registrado"}"""

NUM_BODY = re.compile(r"\d+([.,]\d+)?\s?(%|por ?ciento|cm|kg|kilos?)", re.I)
MEDICAL = re.compile(r"diagn[oó]stic|enfermedad|patolog|escoliosis|ginecomastia|hernia", re.I)
LISTS = ("motivos_fiabilidad", "observaciones", "mas_desarrollados", "a_trabajar", "cambios", "recomendaciones_entrenamiento", "habitos")


def clean(data: dict, compare: bool) -> dict:
    """Aplica las reglas aunque el modelo se las salte: fuera cifras corporales y comentarios médicos."""
    removed = 0

    def ok(t: str) -> bool:
        nonlocal removed
        bad = bool(NUM_BODY.search(t) or MEDICAL.search(t))
        removed += bad
        return not bad
    out = {k: [str(x)[:400] for x in (data.get(k) or []) if isinstance(x, (str, int, float)) and ok(str(x))][:8] for k in LISTS}
    if not compare:
        out["cambios"] = []
    for k in ("simetria", "relacion_con_datos"):
        v = str(data.get(k) or "")[:600]
        out[k] = v if ok(v) else ""
    out["fiabilidad"] = data.get("fiabilidad") if data.get("fiabilidad") in ("alta", "media", "baja") else "media"
    out["omitidos"] = removed
    out["aviso"] = ("Observaciones visuales orientativas: no son medidas ni un diagnóstico. La luz, la postura y el ángulo "
                    "influyen mucho; para comparar, haz las fotos en el mismo sitio, a la misma hora y con la misma pose.")
    return out


def training_context(db, today: date) -> dict:  # noqa: ANN001
    from atlas.gym import service as g
    from atlas.services.goals import snapshot
    snap = g.snapshot(db, today)
    return {"entrenamiento": snap, "objetivos": [x for x in snapshot(db, today) if x.get("area") in (None, "salud", "fitness", "gimnasio")][:6]}


def prompt_text(photos: list, ctx: dict, compare: bool, weights: dict) -> str:  # noqa: ANN001
    import json
    desc = [f"Foto {i + 1}: {p.taken_on:%d/%m/%Y}, pose {p.pose}" + (f", nota: {p.note}" if p.note else "") for i, p in enumerate(photos)]
    head = ("Compara estas fotos (de la más antigua a la más reciente) y describe los cambios VISIBLES."
            if compare else "Analiza esta foto de progreso físico.")
    return (head + "\n" + "\n".join(desc) + "\nPeso registrado en esas fechas (si existe): " + json.dumps(weights, ensure_ascii=False)
            + "\nDATOS DE ENTRENAMIENTO Y OBJETIVOS (reales):\n" + json.dumps(ctx, ensure_ascii=False, default=str)[:6000])
