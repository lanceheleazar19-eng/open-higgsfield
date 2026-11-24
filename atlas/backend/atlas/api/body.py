"""VISTAN · Fitness con fotos, Nutrición con fotos y PROGRESS. Fotos privadas, análisis local por defecto y
consentimiento explícito antes de enviar una imagen a un proveedor externo."""

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from atlas.api.deps import DB
from atlas.brain import router as mr
from atlas.brain.base import ProviderError
from atlas.models import Analysis, BodyMetric, BodyPhoto, Food, MealEntry, MealPhoto, WorkoutSession
from atlas.nutrition import service as nut
from atlas.progress import service as prog
from atlas.services.activity import log_activity
from atlas.services.preferences import get_prefs
from atlas.vision import meals as vm
from atlas.vision import physique as vp
from atlas.vision import storage
from atlas.vision.service import NeedsConsent, analyze, route, to_b64_jpeg

router = APIRouter(prefix="/api", tags=["body"])
NO_CACHE = {"Cache-Control": "private, no-store, max-age=0", "X-Content-Type-Options": "nosniff"}
POSES = {"front": "frente", "back": "espalda", "side": "perfil", "other": "otra"}
MEALS = ("desayuno", "comida", "merienda", "cena", "snack")


def _now(db) -> datetime:  # noqa: ANN001
    return datetime.now(ZoneInfo(str(get_prefs(db)["timezone"]))).replace(tzinfo=None)


def _consent(exc: NeedsConsent) -> HTTPException:
    from atlas.brain.providers import CLOUD
    return HTTPException(409, {"needs_consent": True, "provider": CLOUD[exc.provider].label, "model": exc.model, "message": str(exc)})


@router.get("/vision/route")
def vision_route(db: DB) -> dict:
    return route(get_prefs(db))


# ---------------- Fotos de físico ----------------
def photo_dict(p: BodyPhoto) -> dict:
    return {"id": p.id, "taken_on": p.taken_on.isoformat(), "pose": p.pose, "pose_es": POSES.get(p.pose, p.pose), "note": p.note,
            "width": p.width, "height": p.height, "url": f"/api/progress/photos/{p.id}/image", "thumb": f"/api/progress/photos/{p.id}/image?thumb=1"}


@router.get("/progress/photos")
def list_photos(db: DB) -> list[dict]:
    return [photo_dict(p) for p in db.scalars(select(BodyPhoto).order_by(BodyPhoto.taken_on.desc(), BodyPhoto.id.desc()))]


@router.post("/progress/photos", status_code=201)
async def upload_photo(db: DB, file: UploadFile = File(...), taken_on: date | None = Form(None),
                       pose: str = Form("front"), note: str | None = Form(None)) -> dict:
    if pose not in POSES:
        raise HTTPException(422, "Pose no válida")
    try:
        name, w, h = storage.save("physique", await file.read(storage.MAX_BYTES + 1))
    except storage.BadImage as exc:
        raise HTTPException(415, str(exc)) from exc
    p = BodyPhoto(taken_on=taken_on or _now(db).date(), pose=pose, note=(note or "").strip()[:1000] or None, file=name, width=w, height=h)
    db.add(p)
    log_activity(db, "fitness", "photo", f"Foto de progreso ({POSES[pose]}) del {p.taken_on:%d/%m/%Y}")
    db.commit()
    return photo_dict(p)


@router.get("/progress/photos/{pid}/image")
def photo_image(pid: int, db: DB, thumb: bool = False) -> FileResponse:
    p = db.get(BodyPhoto, pid)
    if not p:
        raise HTTPException(404, "Foto no encontrada")
    f = storage.path("physique", p.file, thumb)
    if not f.exists():
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(f, media_type="image/webp", headers=NO_CACHE)


class PhotoPatch(BaseModel):
    taken_on: date | None = None
    pose: str | None = Field(default=None, pattern="^(front|back|side|other)$")
    note: str | None = Field(default=None, max_length=1000)


@router.patch("/progress/photos/{pid}")
def patch_photo(pid: int, body: PhotoPatch, db: DB) -> dict:
    p = db.get(BodyPhoto, pid)
    if not p:
        raise HTTPException(404, "Foto no encontrada")
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None or k == "note":
            setattr(p, k, v)
    db.commit()
    return photo_dict(p)


@router.delete("/progress/photos/{pid}", status_code=204)
def delete_photo(pid: int, db: DB) -> None:
    p = db.get(BodyPhoto, pid)
    if not p:
        raise HTTPException(404, "Foto no encontrada")
    storage.delete("physique", p.file)
    log_activity(db, "fitness", "photo_deleted", f"Foto de progreso del {p.taken_on:%d/%m/%Y} eliminada")
    db.delete(p)
    db.commit()


class AnalyzeIn(BaseModel):
    photo_ids: list[int] = Field(min_length=1, max_length=2)
    allow_cloud: bool = False


def analysis_dict(a: Analysis) -> dict:
    return {"id": a.id, "kind": a.kind, "refs": a.refs, "result": a.result, "model": a.model, "provider": a.provider,
            "created_at": a.created_at.isoformat()}


@router.post("/progress/photos/analyze")
def analyze_photos(body: AnalyzeIn, db: DB) -> dict:
    """Solo cuando tú lo pides. 1 foto = análisis; 2 fotos = comparación (de la más antigua a la más reciente)."""
    photos = [db.get(BodyPhoto, i) for i in dict.fromkeys(body.photo_ids)]
    if any(p is None for p in photos):
        raise HTTPException(404, "Foto no encontrada")
    photos.sort(key=lambda p: (p.taken_on, p.id))
    compare = len(photos) == 2
    prefs = get_prefs(db)
    weights = {}
    for p in photos:
        w = db.scalar(select(BodyMetric.weight_kg).where(BodyMetric.weight_kg.is_not(None),
                                                        BodyMetric.measured_on <= p.taken_on + timedelta(days=3),
                                                        BodyMetric.measured_on >= p.taken_on - timedelta(days=7))
                      .order_by(BodyMetric.measured_on.desc()).limit(1))
        weights[p.taken_on.isoformat()] = w
    ctx = vp.training_context(db, _now(db).date())
    imgs = [to_b64_jpeg(storage.path("physique", p.file)) for p in photos]
    try:
        out, model, provider = analyze(prefs, vp.SYSTEM, vp.prompt_text(photos, ctx, compare, weights), imgs, body.allow_cloud)
    except NeedsConsent as exc:
        raise _consent(exc) from exc
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    a = Analysis(kind="compare" if compare else "physique", refs=[p.id for p in photos], result=vp.clean(out, compare),
                 model=model, provider=provider)
    db.add(a)
    log_activity(db, "fitness", "analysis", f"Análisis de {'comparación de ' if compare else ''}foto(s) con {model}")
    db.commit()
    return analysis_dict(a)


@router.get("/progress/analyses")
def list_analyses(db: DB, kind: str | None = None, limit: int = 20) -> list[dict]:
    q = select(Analysis).order_by(Analysis.id.desc()).limit(min(limit, 100))
    if kind:
        q = q.where(Analysis.kind.in_(kind.split(",")))
    return [analysis_dict(a) for a in db.scalars(q)]


@router.delete("/progress/analyses/{aid}", status_code=204)
def delete_analysis(aid: int, db: DB) -> None:
    a = db.get(Analysis, aid)
    if not a:
        raise HTTPException(404, "Análisis no encontrado")
    db.delete(a)
    db.commit()


# ---------------- Comidas con foto ----------------
def meal_dict(m: MealPhoto, db) -> dict:  # noqa: ANN001
    entries = [nut.entry_dict(e) for e in db.scalars(select(MealEntry).where(MealEntry.photo_id == m.id))]
    return {"id": m.id, "eaten_at": m.eaten_at.isoformat(timespec="minutes"), "meal": m.meal, "description": m.description,
            "status": m.status, "analysis": m.analysis, "model": m.model, "error": m.error, "entries": entries,
            "url": f"/api/meals/photos/{m.id}/image", "thumb": f"/api/meals/photos/{m.id}/image?thumb=1"}


def _analyze_meal(db, m: MealPhoto, allow_cloud: bool) -> None:  # noqa: ANN001
    prefs = get_prefs(db)
    text = "Analiza la comida de la foto." + (f" El usuario la describe así: «{m.description}»." if m.description else "")
    try:
        out, model, _ = analyze(prefs, vm.SYSTEM, text, [to_b64_jpeg(storage.path("meal", m.file))], allow_cloud)
    except NeedsConsent:
        raise
    except ProviderError as exc:
        m.status, m.error = "error", str(exc)
        return
    m.analysis = vm.build(out, list(db.scalars(select(Food))), m.description)
    m.model, m.error = model, None
    m.status = "analyzed" if m.status != "logged" else "logged"


@router.get("/meals/photos")
def list_meal_photos(db: DB, meal: str | None = None, days: int = 60) -> list[dict]:
    q = select(MealPhoto).where(MealPhoto.eaten_at >= _now(db) - timedelta(days=min(days, 730))).order_by(MealPhoto.eaten_at.desc())
    if meal:
        q = q.where(MealPhoto.meal == meal)
    return [meal_dict(m, db) for m in db.scalars(q)]


@router.post("/meals/photos", status_code=201)
async def upload_meal(db: DB, file: UploadFile = File(...), meal: str | None = Form(None), eaten_at: datetime | None = Form(None),
                      description: str | None = Form(None), analyze_now: bool = Form(True), allow_cloud: bool = Form(False)) -> dict:
    if meal and meal not in MEALS:
        raise HTTPException(422, "Comida no válida")
    try:
        name, _, _ = storage.save("meal", await file.read(storage.MAX_BYTES + 1), max_side=1400)
    except storage.BadImage as exc:
        raise HTTPException(415, str(exc)) from exc
    when = (eaten_at.replace(tzinfo=None) if eaten_at else _now(db))
    m = MealPhoto(eaten_at=when, meal=meal or nut.meal_for_time(when), description=(description or "").strip()[:1000] or None,
                  file=name, status="pending")
    db.add(m)
    db.flush()
    consent = None
    if analyze_now:
        try:
            _analyze_meal(db, m, allow_cloud)
        except NeedsConsent as exc:
            consent = {"provider": exc.provider, "model": exc.model, "message": str(exc)}
    log_activity(db, "nutrition", "photo", f"Foto de {m.meal} del {m.eaten_at:%d/%m %H:%M}")
    db.commit()
    return meal_dict(m, db) | ({"needs_consent": consent} if consent else {})


@router.get("/meals/photos/{mid}/image")
def meal_image(mid: int, db: DB, thumb: bool = False) -> FileResponse:
    m = db.get(MealPhoto, mid)
    if not m:
        raise HTTPException(404, "Foto no encontrada")
    f = storage.path("meal", m.file, thumb)
    if not f.exists():
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(f, media_type="image/webp", headers=NO_CACHE)


class MealAnalyzeIn(BaseModel):
    allow_cloud: bool = False
    description: str | None = Field(default=None, max_length=1000)


@router.post("/meals/photos/{mid}/analyze")
def analyze_meal(mid: int, body: MealAnalyzeIn, db: DB) -> dict:
    m = db.get(MealPhoto, mid)
    if not m:
        raise HTTPException(404, "Foto no encontrada")
    if body.description is not None:
        m.description = body.description.strip() or None
    try:
        _analyze_meal(db, m, body.allow_cloud)
    except NeedsConsent as exc:
        raise _consent(exc) from exc
    db.commit()
    return meal_dict(m, db)


class LogItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    grams: float = Field(gt=0, le=3000)
    food_id: int | None = None
    kcal: float = Field(default=0, ge=0, le=10000)
    protein: float = Field(default=0, ge=0, le=1000)
    carbs: float = Field(default=0, ge=0, le=2000)
    fat: float = Field(default=0, ge=0, le=1000)


class LogIn(BaseModel):
    items: list[LogItem] = Field(min_length=1, max_length=20)


@router.post("/meals/photos/{mid}/log")
def log_meal(mid: int, body: LogIn, db: DB) -> dict:
    """Confirma la comida: crea los registros de nutrición (sustituye los anteriores de esta foto)."""
    m = db.get(MealPhoto, mid)
    if not m:
        raise HTTPException(404, "Foto no encontrada")
    db.query(MealEntry).filter(MealEntry.photo_id == m.id).delete()
    for it in body.items:
        food = db.get(Food, it.food_id) if it.food_id else None
        mac = nut.macros(food, it.grams) if food else {"kcal": it.kcal, "protein": it.protein, "carbs": it.carbs, "fat": it.fat}
        db.add(MealEntry(eaten_on=m.eaten_at.date(), meal=m.meal, food_id=food.id if food else None, name=(food.name if food else it.name)[:120],
                         grams=it.grams, source="photo", photo_id=m.id, **{k: round(float(v), 1) for k, v in mac.items()}))
    m.status = "logged"
    log_activity(db, "nutrition", "log", f"Comida registrada desde foto ({m.meal}, {len(body.items)} alimentos)")
    db.commit()
    return meal_dict(m, db)


class MealPatch(BaseModel):
    meal: str | None = Field(default=None, pattern="^(desayuno|comida|merienda|cena|snack)$")
    eaten_at: datetime | None = None
    description: str | None = Field(default=None, max_length=1000)


@router.patch("/meals/photos/{mid}")
def patch_meal(mid: int, body: MealPatch, db: DB) -> dict:
    m = db.get(MealPhoto, mid)
    if not m:
        raise HTTPException(404, "Foto no encontrada")
    d = body.model_dump(exclude_unset=True)
    if d.get("meal"):
        m.meal = d["meal"]
    if d.get("eaten_at"):
        m.eaten_at = d["eaten_at"].replace(tzinfo=None)
    if "description" in d:
        m.description = (d["description"] or "").strip() or None
    for e in db.scalars(select(MealEntry).where(MealEntry.photo_id == m.id)):  # los registros siguen a la foto
        e.meal, e.eaten_on = m.meal, m.eaten_at.date()
    db.commit()
    return meal_dict(m, db)


@router.delete("/meals/photos/{mid}", status_code=204)
def delete_meal(mid: int, db: DB, with_entries: bool = True) -> None:
    m = db.get(MealPhoto, mid)
    if not m:
        raise HTTPException(404, "Foto no encontrada")
    if with_entries:
        db.query(MealEntry).filter(MealEntry.photo_id == m.id).delete()
    storage.delete("meal", m.file)
    log_activity(db, "nutrition", "photo_deleted", f"Foto de {m.meal} eliminada" + (" con sus registros" if with_entries else ""))
    db.delete(m)
    db.commit()


# ---------------- Asesor nutricional ----------------
ADVICE = """Eres el nutricionista personal del usuario (17 años, objetivo: ganar volumen de forma saludable). Usa SOLO
los DATOS dados (sus registros reales, objetivos calculados y entrenamiento). Distingue datos registrados de estimaciones
por foto. Nada de dietas extremas ni suplementos innecesarios. Si faltan datos, dilo y pide lo que necesites.
Responde SOLO JSON: {"resumen": "2-4 frases", "cumplimiento": "cómo va respecto a sus objetivos", "puntos_fuertes": ["..."],
"mejorar": ["acción concreta y medible"], "alternativas": ["cambio concreto de alimento o comida"], "preguntas": ["..."]}"""


def nutrition_data(db, today: date, prefs: dict) -> dict:  # noqa: ANN001
    cfg = prefs.get("nutrition_profile")
    targets = nut.compute_targets(cfg, nut.latest_weight(db)) if cfg else None
    days = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        t = nut.day_totals(db, d)
        if t["kcal"] > 0:
            trained = bool(db.scalar(select(func.count(WorkoutSession.id)).where(WorkoutSession.performed_on == d)))
            days.append({"fecha": d.isoformat(), "kcal": round(t["kcal"]), "proteina": round(t["protein"]),
                         "hidratos": round(t["carbs"]), "grasas": round(t["fat"]), "entreno": trained})
    photos = [{"fecha": m.eaten_at.date().isoformat(), "comida": m.meal, "calidad": (m.analysis or {}).get("quality"),
               "nota": (m.analysis or {}).get("quality_note")} for m in db.scalars(
        select(MealPhoto).where(MealPhoto.eaten_at >= datetime.combine(today - timedelta(days=13), datetime.min.time()),
                                MealPhoto.analysis.is_not(None)).limit(30))]
    n = len(days)
    out = {"objetivos": targets, "dias_registrados": n, "dias": days, "fotos_analizadas": photos}
    if n and targets:
        out["media_kcal"] = round(sum(d["kcal"] for d in days) / n)
        out["media_proteina"] = round(sum(d["proteina"] for d in days) / n)
        out["dias_proteina_ok"] = sum(1 for d in days if d["proteina"] >= 0.9 * targets["protein"])
        out["dias_kcal_ok"] = sum(1 for d in days if 0.9 * targets["kcal"] <= d["kcal"] <= 1.15 * targets["kcal"])
    return out


def deterministic_advice(d: dict) -> dict:
    t = d["objetivos"]
    if not d["dias_registrados"]:
        return {"resumen": "No hay comidas registradas en las dos últimas semanas, así que no puedo valorar tu alimentación.",
                "mejorar": ["Registra lo que comes (texto o foto) durante al menos 5 días."], "puntos_fuertes": [], "alternativas": [], "preguntas": []}
    if not t:
        return {"resumen": f"Tienes {d['dias_registrados']} días registrados, pero sin perfil nutricional no puedo compararlos con un objetivo.",
                "mejorar": ["Completa Nutrición › Perfil y objetivos."], "puntos_fuertes": [], "alternativas": [], "preguntas": []}
    n = d["dias_registrados"]
    res = {"resumen": f"En {n} días registrados tu media es de {d['media_kcal']} kcal (objetivo {t['kcal']}) y {d['media_proteina']} g de "
                      f"proteína (objetivo {t['protein']}). Llegaste a la proteína en {d['dias_proteina_ok']} de {n} días.",
           "puntos_fuertes": [], "mejorar": [], "alternativas": [], "preguntas": []}
    if d["media_kcal"] < 0.9 * t["kcal"]:
        res["mejorar"].append(f"Te faltan de media unas {t['kcal'] - d['media_kcal']} kcal al día para ganar volumen.")
    if d["dias_proteina_ok"] < n * 0.7:
        res["mejorar"].append(f"Sube la proteína: te quedas de media {max(0, t['protein'] - d['media_proteina'])} g por debajo.")
    if d["dias_proteina_ok"] >= n * 0.7:
        res["puntos_fuertes"].append("Cumples la proteína la mayoría de los días.")
    if n < 7:
        res["preguntas"].append("¿Registras todas las comidas? Con menos de 7 días la valoración es poco fiable.")
    return res


@router.post("/nutrition/advice")
def nutrition_advice(db: DB) -> dict:
    prefs = get_prefs(db)
    today = _now(db).date()
    d = nutrition_data(db, today, prefs)
    model = None
    try:
        advice, model = mr.complete_json("agents", prefs, [{"role": "system", "content": ADVICE},
                                                           {"role": "user", "content": json.dumps(d, ensure_ascii=False)}])
        mode = "ai"
    except ProviderError:
        advice, mode = deterministic_advice(d), "local"
    a = Analysis(kind="nutrition", refs=[], result={"advice": advice, "data": d, "mode": mode}, model=model,
                 provider=(model or "").split(":")[0] or None)
    db.add(a)
    db.commit()
    return analysis_dict(a)


# ---------------- PROGRESS ----------------
@router.get("/progress")
def progress(db: DB) -> dict:
    prefs = get_prefs(db)
    g = prog.gather(db, _now(db).date(), prefs)
    return g | {"facts": prog.facts(g)}


SUMMARY = """Eres el coach de VISTAN. Explica el progreso del usuario usando SOLO los HECHOS y DATOS dados, que ya
distinguen tendencias reales de variaciones puntuales: no conviertas una variación de un día en tendencia, y si un
apartado no tiene datos suficientes, dilo. Relaciona entrenamiento, nutrición, peso y objetivos. Nada de % de grasa.
Responde SOLO JSON: {"resumen": "3-5 frases", "tendencias": ["..."], "variaciones_puntuales": ["..."],
"conexiones": ["relación entre áreas"], "recomendaciones": ["acción concreta"], "faltan_datos": ["..."]}"""


@router.post("/progress/summary")
def progress_summary(db: DB) -> dict:
    prefs = get_prefs(db)
    g = prog.gather(db, _now(db).date(), prefs)
    f = prog.facts(g)
    last_photo = db.scalar(select(Analysis).where(Analysis.kind.in_(("physique", "compare"))).order_by(Analysis.id.desc()).limit(1))
    payload = {"hechos": f, "tendencia_peso": g["weight_trend"], "tendencia_frecuencia": g["sessions_trend"],
               "tendencia_volumen": g["tonnage_trend"], "objetivos_nutricion": g["targets"], "objetivos": g["goals"][:6],
               "ultimo_analisis_fotos": (last_photo.result if last_photo else None)}
    model = None
    try:
        res, model = mr.complete_json("agents", prefs, [{"role": "system", "content": SUMMARY},
                                                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}])
        mode = "ai"
    except ProviderError:
        res, mode = {"resumen": " ".join(f[:3]), "tendencias": [x for x in f if "sube" in x or "baja" in x],
                     "variaciones_puntuales": [], "conexiones": [], "recomendaciones": [],
                     "faltan_datos": [x for x in f if "Hacen falta" in x or "no hay" in x.lower()]}, "local"
    a = Analysis(kind="progress", refs=[], result=res | {"mode": mode, "facts": f}, model=model, provider=(model or "").split(":")[0] or None)
    db.add(a)
    db.commit()
    return analysis_dict(a)
