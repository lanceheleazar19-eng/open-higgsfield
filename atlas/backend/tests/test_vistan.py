"""VISTAN: fotos de físico y comidas (privadas), análisis con reglas, consentimiento, asesor nutricional y PROGRESS."""

import io
from datetime import date, timedelta

from PIL import Image

from atlas.models import BodyMetric, Food


def _img(color=(180, 60, 60), size=(800, 1000), fmt="JPEG", exif=False) -> bytes:
    im = Image.new("RGB", size, color)
    b = io.BytesIO()
    kw = {}
    if exif:
        ex = Image.Exif()
        ex[0x010F] = "iPhone"  # fabricante
        kw["exif"] = ex.tobytes()
    im.save(b, fmt, **kw)
    return b.getvalue()


def _vision(ollama):
    ollama.models.append({"name": "qwen2.5vl:7b", "size": 6e9, "details": {"family": "qwen25vl", "parameter_size": "8B"}})


def test_physique_photos_private_storage_and_crud(client):
    r = client.post("/api/progress/photos", files={"file": ("yo.jpg", _img(exif=True), "image/jpeg")},
                    data={"taken_on": "2026-10-01", "pose": "front", "note": "Mañana, en ayunas"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["taken_on"] == "2026-10-01" and max(p["width"], p["height"]) <= 1600
    img = client.get(p["url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/webp" and "no-store" in img.headers["cache-control"]
    assert not Image.open(io.BytesIO(img.content)).getexif()  # sin metadatos
    assert client.get(p["thumb"]).status_code == 200
    from atlas.config import get_settings
    folder = get_settings().resolved_data_dir / "private" / "photos" / "physique"
    files = list(folder.glob("*.webp"))
    assert len(files) == 2 and oct(folder.stat().st_mode)[-3:] == "700" and oct(files[0].stat().st_mode)[-3:] == "600"
    assert client.post("/api/progress/photos", files={"file": ("x.jpg", b"no soy una foto", "image/jpeg")}).status_code == 415
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, "GIF")
    assert client.post("/api/progress/photos", files={"file": ("x.gif", gif.getvalue(), "image/gif")}).status_code == 415
    assert client.patch(f"/api/progress/photos/{p['id']}", json={"pose": "side", "note": "otra"}).json()["pose"] == "side"
    client.post("/api/progress/photos", files={"file": ("b.png", _img(fmt="PNG"), "image/png")}, data={"taken_on": "2026-11-20"})
    assert [x["taken_on"] for x in client.get("/api/progress/photos").json()] == ["2026-11-20", "2026-10-01"]
    assert client.delete(f"/api/progress/photos/{p['id']}").status_code == 204
    assert len(list(folder.glob("*.webp"))) == 2  # se borraron foto y miniatura


def test_physique_analysis_rules_and_compare(ollama, client, session):
    _vision(ollama)
    session.add_all([BodyMetric(measured_on=date(2026, 10, 1), weight_kg=75.0), BodyMetric(measured_on=date(2026, 11, 20), weight_kg=76.2)])
    session.commit()
    a = client.post("/api/progress/photos", files={"file": ("a.jpg", _img(), "image/jpeg")}, data={"taken_on": "2026-10-01"}).json()
    b = client.post("/api/progress/photos", files={"file": ("b.jpg", _img((90, 40, 40)), "image/jpeg")}, data={"taken_on": "2026-11-20"}).json()
    ollama.json_reply = {"fiabilidad": "media", "motivos_fiabilidad": ["Luz distinta entre fotos"],
                         "observaciones": ["Hombros más redondeados", "Tienes un 14% de grasa corporal"],
                         "mas_desarrollados": ["Deltoides"], "a_trabajar": ["Espalda baja"], "cambios": ["Pecho algo más lleno"],
                         "simetria": "Buena", "recomendaciones_entrenamiento": ["Añade remo con mancuerna"],
                         "habitos": ["Duerme 8 h"], "relacion_con_datos": "Encaja con tus 2 sesiones de pecho"}
    r = client.post("/api/progress/photos/analyze", json={"photo_ids": [b["id"], a["id"]]})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["kind"] == "compare" and res["refs"] == [a["id"], b["id"]]  # de la más antigua a la más reciente
    assert res["result"]["observaciones"] == ["Hombros más redondeados"] and res["result"]["omitidos"] == 1  # sin % de grasa
    assert "no son medidas" in res["result"]["aviso"] and res["model"] == "ollama:qwen2.5vl:7b"
    req = ollama.requests[-1]
    assert len(req["messages"][1]["images"]) == 2 and "76.2" in req["messages"][1]["content"]
    assert client.get("/api/progress/analyses?kind=physique,compare").json()[0]["id"] == res["id"]


def test_cloud_vision_requires_consent(client, monkeypatch):
    from atlas.brain import providers
    client.put("/api/models/openai/key", json={"api_key": "sk-test-1234567890"})
    client.put("/api/models/config", json={"tasks": {"vision": {"provider": "openai", "model": "gpt-vision"}}})
    route = client.get("/api/vision/route").json()
    assert route["local"] is False and route["label"] == "OpenAI"
    p = client.post("/api/progress/photos", files={"file": ("a.jpg", _img(), "image/jpeg")}).json()
    r = client.post("/api/progress/photos/analyze", json={"photo_ids": [p["id"]]})
    assert r.status_code == 409 and r.json()["detail"]["needs_consent"] and r.json()["detail"]["provider"] == "OpenAI"
    sent = []
    monkeypatch.setitem(providers.IMAGE_JSON, "openai", lambda prov, model, system, text, images: sent.append(images) or
                        {"fiabilidad": "alta", "observaciones": ["Postura correcta"]})
    r = client.post("/api/progress/photos/analyze", json={"photo_ids": [p["id"]], "allow_cloud": True})
    assert r.status_code == 200 and r.json()["provider"] == "openai" and len(sent) == 1
    client.put("/api/models/config", json={"privacy": "local_only"})
    assert client.get("/api/vision/route").json()["local"] is True  # «solo local» bloquea la nube


def test_meal_photo_analyze_log_edit_delete(ollama, client, session):
    _vision(ollama)
    ollama.json_reply = {"es_comida": True, "alimentos": [
        {"nombre": "arroz blanco", "gramos": 200, "preparacion": "cocido", "confianza": "alta"},
        {"nombre": "salsa misteriosa", "gramos": 30, "confianza": "baja", "kcal": 90, "proteinas": 1, "carbohidratos": 5, "grasas": 7}],
        "calidad": "buena", "comentario_calidad": "Falta verdura", "preguntas": ["¿Llevaba aceite?"]}
    r = client.post("/api/meals/photos", files={"file": ("plato.jpg", _img(), "image/jpeg")},
                    data={"meal": "comida", "eaten_at": "2026-11-24T14:05", "description": "arroz con salsa"})
    assert r.status_code == 201, r.text
    m = r.json()
    an = m["analysis"]
    assert m["status"] == "analyzed" and an["items"][0]["source"] == "base de alimentos" and an["items"][1]["source"] == "estimación del modelo"
    assert an["questions"] == ["¿Llevaba aceite?"] and "Estimación visual" in an["disclaimer"]
    assert "arroz con salsa" in ollama.requests[-1]["messages"][1]["content"]
    assert client.get("/api/nutrition/day").json()["entries"] == []  # nada se registra sin confirmar
    rice = session.query(Food).filter(Food.name == an["items"][0]["name"]).one()
    logged = client.post(f"/api/meals/photos/{m['id']}/log", json={"items": [
        {"name": "x", "food_id": rice.id, "grams": 250}, {"name": "Salsa", "grams": 30, "kcal": 90, "protein": 1, "carbs": 5, "fat": 7}]}).json()
    assert logged["status"] == "logged" and len(logged["entries"]) == 2 and logged["entries"][0]["grams"] == 250
    e = client.patch(f"/api/meals/photos/{m['id']}", json={"meal": "cena"}).json()
    assert {x["meal"] for x in e["entries"]} == {"cena"}
    assert [x["id"] for x in client.get("/api/meals/photos?meal=cena&days=3650").json()] == [m["id"]]
    assert client.delete(f"/api/meals/photos/{m['id']}").status_code == 204
    assert client.get("/api/meals/photos?days=3650").json() == []
    from atlas.models import MealEntry
    assert session.query(MealEntry).count() == 0


def test_meal_photo_without_vision_model_is_saved_honestly(client):
    r = client.post("/api/meals/photos", files={"file": ("plato.jpg", _img(), "image/jpeg")}).json()
    assert r["status"] == "error" and r["analysis"] is None and "Ollama" in r["error"]


def test_nutrition_advice_local_uses_real_data(client, session):
    client.put("/api/nutrition/profile", json={"sex": "male", "age": 17, "height_cm": 168, "weight_kg": 75, "activity": 1.55, "goal": "gain"})
    adv = client.post("/api/nutrition/advice").json()
    assert adv["kind"] == "nutrition" and adv["result"]["mode"] == "local"
    assert "No hay comidas registradas" in adv["result"]["advice"]["resumen"]


def test_progress_trends_and_summary(client, session):
    base = date.today() - timedelta(days=40)
    for i in range(10):
        session.add(BodyMetric(measured_on=base + timedelta(days=i * 4), weight_kg=75 + 0.1 * i + (0.2 if i % 2 else -0.2)))
    session.commit()
    g = client.get("/api/progress").json()
    assert g["weight_trend"]["status"] == "subiendo" and g["weight_trend"]["per_week"] > 0
    assert any(f.startswith("Peso: sube") for f in g["facts"])
    assert g["sessions_trend"]["status"] == "insuficiente" and any("no hay sesiones" in f for f in g["facts"])
    s = client.post("/api/progress/summary").json()
    assert s["kind"] == "progress" and s["result"]["mode"] == "local" and s["result"]["facts"] == g["facts"]


def test_core_fitness_agent_uses_progress(client):
    r = client.post("/api/agents/run", json={"text": "¿Cómo estoy progresando físicamente?"}).json()
    assert "fitness" in r["agents"]
    assert {"progress.trends", "physique.latest", "meals.photos"} <= {s["tool"] for s in r["steps"]}
