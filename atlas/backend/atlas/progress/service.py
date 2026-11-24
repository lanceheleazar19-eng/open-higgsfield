"""PROGRESS: reúne peso, entrenamiento, nutrición, objetivos y fotos, y detecta TENDENCIAS de verdad
(regresión con suficientes puntos y días, comparada con el ruido) sin confundirlas con variaciones puntuales."""

import math
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.models import BodyMetric, BodyPhoto, MealEntry, WorkoutSession, WorkoutSet


def trend(points: list[tuple[date, float]], min_points: int = 4, min_days: int = 14, unit: str = "") -> dict:
    """Pendiente por semana y si es una tendencia real: cambio previsto > 2 × error típico de la pendiente."""
    pts = sorted(points)
    if len(pts) < min_points or (pts[-1][0] - pts[0][0]).days < min_days:
        return {"status": "insuficiente", "points": len(pts), "reason": f"Hacen falta al menos {min_points} registros en {min_days} días."}
    t0 = pts[0][0]
    xs = [(d - t0).days for d, _ in pts]
    ys = [v for _, v in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return {"status": "insuficiente", "points": n, "reason": "Todos los registros son del mismo día."}
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    resid = [y - (my + slope * (x - mx)) for x, y in zip(xs, ys)]
    sd = math.sqrt(sum(r * r for r in resid) / max(1, n - 2))
    se = sd / math.sqrt(sxx) if sxx else 0
    span = xs[-1] - xs[0]
    change = slope * span
    significant = abs(slope) > 2 * se and abs(change) > 0.5 * sd if se > 0 else abs(change) > 0
    status = ("subiendo" if slope > 0 else "bajando") if significant else "estable"
    return {"status": status, "points": n, "days": span, "per_week": round(slope * 7, 3), "change": round(change, 2),
            "noise": round(sd, 2), "first": ys[0], "last": ys[-1], "unit": unit,
            "max_jump": round(max((abs(ys[i] - ys[i - 1]) for i in range(1, n)), default=0), 2)}


def gather(db: Session, today: date, prefs: dict) -> dict:
    from atlas.nutrition import service as nut
    from atlas.services.goals import snapshot
    since = today - timedelta(days=180)
    weights = [(d, float(w)) for d, w in db.execute(
        select(BodyMetric.measured_on, func.avg(BodyMetric.weight_kg)).where(BodyMetric.weight_kg.is_not(None), BodyMetric.measured_on >= since)
        .group_by(BodyMetric.measured_on).order_by(BodyMetric.measured_on)).all()]
    monday = today - timedelta(days=today.weekday())
    weeks = []
    for i in range(11, -1, -1):
        a = monday - timedelta(weeks=i)
        b = a + timedelta(days=7)
        s = db.scalar(select(func.count(WorkoutSession.id)).where(WorkoutSession.performed_on >= a, WorkoutSession.performed_on < b)) or 0
        vol = db.scalar(select(func.coalesce(func.sum(WorkoutSet.reps * WorkoutSet.weight), 0)).join(
            WorkoutSession, WorkoutSet.session_id == WorkoutSession.id).where(
            WorkoutSession.performed_on >= a, WorkoutSession.performed_on < b, WorkoutSet.warmup.is_(False))) or 0
        weeks.append({"week": a, "sessions": s, "tonnage": round(float(vol))})
    days = db.execute(select(MealEntry.eaten_on, func.sum(MealEntry.kcal), func.sum(MealEntry.protein))
                      .where(MealEntry.eaten_on >= today - timedelta(days=42)).group_by(MealEntry.eaten_on).order_by(MealEntry.eaten_on)).all()
    cfg = prefs.get("nutrition_profile")
    targets = nut.compute_targets(cfg, nut.latest_weight(db)) if cfg else None
    nutrition_days = [{"date": d.isoformat(), "kcal": round(k), "protein": round(p)} for d, k, p in days]
    photos = [{"id": p.id, "date": p.taken_on.isoformat(), "pose": p.pose, "note": p.note}
              for p in db.scalars(select(BodyPhoto).order_by(BodyPhoto.taken_on, BodyPhoto.id))]
    trained_weeks = [w for w in weeks if w["sessions"]]
    first_training = next((i for i, w in enumerate(weeks) if w["sessions"]), None)
    tw = weeks[first_training:] if first_training is not None else []
    return {
        "weights": [{"date": d.isoformat(), "kg": round(w, 2)} for d, w in weights],
        "weight_trend": trend(weights, unit="kg"),
        "training_weeks": [{**w, "week": w["week"].isoformat()} for w in weeks],
        "sessions_trend": trend([(w["week"], float(w["sessions"])) for w in tw], min_points=4, min_days=21, unit="sesiones/sem"),
        "tonnage_trend": trend([(w["week"], float(w["tonnage"])) for w in tw if w["sessions"]], min_points=4, min_days=21, unit="kg/sem"),
        "nutrition_days": nutrition_days, "targets": targets,
        "kcal_trend": trend([(date.fromisoformat(x["date"]), float(x["kcal"])) for x in nutrition_days], min_points=6, min_days=14, unit="kcal/día"),
        "protein_days_met": sum(1 for x in nutrition_days if targets and x["protein"] >= 0.9 * targets["protein"]),
        "goals": snapshot(db, today), "photos": photos, "weeks_trained": len(trained_weeks),
    }


TREND_ES = {"subiendo": "sube", "bajando": "baja", "estable": "se mantiene estable"}


def es(v: float, d: int = 1, sign: bool = False) -> str:
    """Número en formato español (coma decimal)."""
    s = f"{v:+.{d}f}" if sign else f"{v:.{d}f}"
    return s.replace(".", ",")


def facts(g: dict) -> list[str]:
    """Afirmaciones verificables a partir de los datos (también sirven de resumen sin IA)."""
    out = []
    wt = g["weight_trend"]
    if wt["status"] == "insuficiente":
        out.append(f"Peso: {wt['reason']} Tienes {wt['points']} registro(s).")
    else:
        out.append(f"Peso: {TREND_ES[wt['status']]} ({es(wt['per_week'], 2, True)} kg/semana en {wt['days']} días, de {es(wt['first'])} a {es(wt['last'])} kg)."
                   + (f" Variación típica entre registros: ±{es(wt['noise'])} kg, así que cambios de un día no son tendencia." if wt["noise"] else ""))
    st = g["sessions_trend"]
    if g["weeks_trained"]:
        w = [x["sessions"] for x in g["training_weeks"][-4:]]
        out.append(f"Entrenamiento: {sum(w)} sesiones en las últimas 4 semanas (objetivo de tu rutina: 16)."
                   + (f" La frecuencia {TREND_ES[st['status']]}." if st["status"] != "insuficiente" else ""))
        tt = g["tonnage_trend"]
        if tt["status"] != "insuficiente":
            out.append(f"Volumen (tonelaje semanal): {TREND_ES[tt['status']]} ({es(tt['per_week'], 0, True)} kg/semana).")
    else:
        out.append("Entrenamiento: no hay sesiones registradas en las últimas 12 semanas.")
    nd, t = g["nutrition_days"], g["targets"]
    if nd:
        last = nd[-14:]
        ak = round(sum(x["kcal"] for x in last) / len(last))
        ap = round(sum(x["protein"] for x in last) / len(last))
        out.append(f"Nutrición: {len(last)} días registrados en las 2 últimas semanas; media {ak} kcal y {ap} g de proteína"
                   + (f" (objetivo {t['kcal']} kcal y {t['protein']} g). Proteína cumplida ≥90 % en {g['protein_days_met']} de {len(nd)} días." if t else "."))
        if len(last) < 7:
            out.append("Con menos de 7 días registrados, la media de nutrición es poco representativa.")
    else:
        out.append("Nutrición: no hay comidas registradas en las últimas 6 semanas.")
    if g["photos"]:
        out.append(f"Fotos de progreso: {len(g['photos'])}, desde el {g['photos'][0]['date']} hasta el {g['photos'][-1]['date']}.")
    for goal in g["goals"][:4]:
        if goal.get("pace"):
            out.append(f"Objetivo «{goal['title']}»: ritmo {goal['pace']}.")
    return out
