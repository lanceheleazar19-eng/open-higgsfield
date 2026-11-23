import io
import json
from datetime import datetime

from PIL import Image
from sqlalchemy import select

from atlas.models import Food
from atlas.nutrition import service as nut


def _events(resp):
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def test_parse_meal_text_units_and_quantities(session):
    foods = list(session.scalars(select(Food)))
    items = nut.parse_meal_text("2 huevos, una tostada y un café con leche", foods)
    assert [(i["food"].name, i["grams"]) for i in items] == [("Huevo", 120), ("Tostada", 30), ("Café con leche", 200)]
    items = nut.parse_meal_text("200g de arroz + pechuga de pollo 150 gr; medio plátano", foods)
    assert [(i["food"].name, i["grams"]) for i in items] == [("Arroz blanco cocido", 200), ("Pechuga de pollo", 150), ("Plátano", 60)]
    unk = nut.parse_meal_text("un trozo de bizcocho de mi abuela", foods)
    assert unk[0]["food"] is None


def test_meal_command_detection():
    now = datetime(2026, 11, 24, 21, 0)
    assert nut.parse_meal_command("He desayunado 2 huevos", now) == ("desayuno", "2 huevos")
    assert nut.parse_meal_command("cena: pollo con arroz", now) == ("cena", "pollo con arroz")
    assert nut.parse_meal_command("he tomado un yogur", now)[0] == "cena"  # por la hora
    assert nut.parse_meal_command("¿qué he comido hoy?", now) is None


def test_targets_mifflin():
    t = nut.compute_targets({"sex": "male", "age": 17, "height_cm": 168, "activity": 1.55, "goal": "bulk", "protein_per_kg": 1.8}, 75.5)
    assert t["bmr"] == 1725 and t["tdee"] == round(1725 * 1.55) and t["kcal"] == round(1725 * 1.55) + 300
    assert t["protein"] == 136 and t["fat"] == 68
    assert nut.compute_targets({"sex": "male"}, None) is None


def test_entries_day_totals_and_tips(client, session):
    p = client.put("/api/nutrition/profile", json={"sex": "male", "age": 17, "height_cm": 168, "weight_kg": 75.5, "goal": "bulk"}).json()
    assert p["targets"]["kcal"] > 2800
    egg = session.scalar(select(Food).where(Food.name == "Huevo"))
    r = client.post("/api/nutrition/entries", json={"meal": "desayuno", "items": [{"food_id": egg.id, "grams": 120}]})
    assert r.status_code == 201
    e = r.json()["items"][0]
    assert e["kcal"] == round(143 * 1.2, 1) and e["protein"] == round(12.6 * 1.2, 1)  # calculado en el servidor
    d = client.get("/api/nutrition/day").json()
    assert d["totals"]["kcal"] == round(143 * 1.2) and d["targets"]["protein"] == 136
    assert any("proteína" in t for t in d["tips"])
    assert client.delete(f"/api/nutrition/entries/{e['id']}").status_code == 204
    assert client.get("/api/nutrition/day").json()["entries"] == []
    assert len(client.get("/api/nutrition/week").json()["days"]) == 7


def test_custom_food_and_search(client):
    r = client.post("/api/nutrition/foods", json={"name": "Bizcocho de la abuela", "kcal": 380, "protein": 6, "carbs": 55, "fat": 15, "unit_name": "trozo", "unit_grams": 70})
    assert r.status_code == 201
    assert client.post("/api/nutrition/foods", json={"name": "Bizcocho de la abuela", "kcal": 1, "protein": 0, "carbs": 0, "fat": 0}).status_code == 409
    assert client.get("/api/nutrition/foods", params={"q": "bizcocho"}).json()["items"][0]["custom"] is True
    assert client.get("/api/nutrition/foods", params={"q": "platano"}).json()["items"][0]["name"] == "Plátano"


def test_chat_logs_meal(client):
    client.put("/api/nutrition/profile", json={"sex": "male", "age": 17, "height_cm": 168, "weight_kg": 75.5, "goal": "bulk"})
    ev = _events(client.post("/api/assistant/chat", json={"text": "He desayunado 2 huevos, una tostada y un café con leche"}))
    meal = next(e for e in ev if e["type"] == "meal")
    assert meal["action"] == "logged" and [x["name"] for x in meal["entries"]] == ["Huevo", "Tostada", "Café con leche"]
    reply = "".join(e.get("text", "") for e in ev)
    assert reply.startswith("Registrado en desayuno: Huevo (120 g)") and "Hoy llevas" in reply and ev[-1]["mode"] == "nutrition"


def _jpeg() -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (1600, 1200), (240, 230, 200)).save(b, "JPEG")
    return b.getvalue()


def test_photo_without_vision_model(ollama, client):
    r = client.post("/api/nutrition/photo", files={"file": ("plato.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 503 and "qwen2.5vl" in r.json()["detail"]


def test_photo_with_vision_model_proposes_not_saves(ollama, client):
    ollama.models.append({"name": "qwen2.5vl:7b", "size": 6e9, "details": {"family": "qwen25vl", "parameter_size": "8B"}})
    ollama.json_reply = {"alimentos": [{"nombre": "arroz blanco", "gramos": 180}, {"nombre": "pechuga de pollo", "gramos": 140},
                                       {"nombre": "salsa rara", "gramos": 20}]}
    r = client.post("/api/nutrition/photo", files={"file": ("plato.jpg", _jpeg(), "image/jpeg")}).json()
    assert r["model"] == "qwen2.5vl:7b"
    assert [(i["food"]["name"] if i["food"] else None, i["grams"]) for i in r["items"]] == [
        ("Arroz blanco cocido", 180), ("Pechuga de pollo", 140), (None, 20)]
    req = ollama.requests[-1]
    assert req["model"] == "qwen2.5vl:7b" and req["messages"][0]["images"]  # imagen enviada al modelo LOCAL
    assert client.get("/api/nutrition/day").json()["entries"] == []  # nada guardado sin confirmar
    assert client.post("/api/nutrition/photo", files={"file": ("x.jpg", b"nope", "image/jpeg")}).status_code == 415
