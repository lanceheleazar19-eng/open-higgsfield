import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from atlas.gym import service as gym
from atlas.models import Exercise, WorkoutSession, WorkoutSet

TZ = ZoneInfo("Europe/Madrid")

USER_SATURDAY = """Inclinado 2 calentamiento 2x8 40kg
Aperturas hacia el medio 3x10 15kg por lado
Triceps v 40kg x 8-10 2 series
Triceps hacia arriba 20kg 2 series 10 reps
Tricep unilateral 1 serie 11kg x 8 reps
Hombro laterales 3 x 10 6kg. Polea
Militar 25kg  2 series x 10 reps cada lado maquina (si no estoy fatigado)"""


def _events(resp):
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def _ex(session, name):
    return session.scalar(select(Exercise).where(Exercise.name == name))


def test_library_seeded_with_user_exercises(client):
    names = {e["name"] for e in client.get("/api/gym/exercises").json()["items"]}
    for n in ("Press inclinado", "Tríceps en V (polea)", "Jalón al pecho en máquina", "Curl bayesiano", "Remo de densidad"):
        assert n in names


def test_import_user_template_and_today_plan(client):
    tpls = client.get("/api/gym/routines").json()["templates"]
    assert tpls[0]["id"] == "rutina_4_dias"
    r = client.post("/api/gym/routines/import/rutina_4_dias")
    assert r.status_code == 201
    routines = client.get("/api/gym/routines").json()["items"]
    assert [(x["weekday_name"], x["name"]) for x in routines] == [
        ("miércoles", "Pecho + espalda"), ("jueves", "Bíceps + tríceps + antebrazo"),
        ("sábado", "Pecho + hombro + tríceps"), ("domingo", "Espalda + bíceps + trapecio")]
    sat = routines[2]
    assert sat["exercises"][0] == {**sat["exercises"][0], "name": "Press inclinado", "warmup_sets": 2, "sets": 2,
                                   "reps_min": 8, "weight": 40.0, "notes": "Objetivo: 46 kg antes de 2027"}
    assert client.post("/api/gym/routines/import/../../etc/passwd").status_code == 404
    t = client.get("/api/gym/today").json()
    assert "rest_day" in t and t["next"] is not None


def test_log_user_text_and_session(client):
    client.post("/api/gym/routines/import/rutina_4_dias")
    prev = client.post("/api/gym/log-text", json={"text": USER_SATURDAY, "preview": True}).json()
    assert len(prev["parsed"]) == 7 and prev["session"] is None
    r = client.post("/api/gym/log-text", json={"text": USER_SATURDAY, "day": "2026-11-21"}).json()  # sábado
    s = r["session"]
    assert s["routine_name"] == "Pecho + hombro + tríceps"
    assert s["working_sets"] == 2 + 3 + 2 + 2 + 1 + 3 + 2
    inc = next(e for e in s["exercises"] if e["name"] == "Press inclinado")
    assert [(x["reps"], x["weight"]) for x in inc["sets"]] == [(8, 40.0), (8, 40.0)]
    assert inc["sets"][0]["e1rm"] == round(40 * (1 + 8 / 30), 1)
    hist = client.get("/api/gym/sessions").json()["items"]
    assert hist[0]["notes"] == "2 series de calentamiento en Press inclinado"  # sin inventar pesos


def test_progression_stagnation_volume(session):
    inc = _ex(session, "Press inclinado")
    curl = _ex(session, "Curl de bíceps")
    base = date(2026, 9, 1)
    weights = [40, 40, 42.5, 42.5, 42.5, 42.5]  # mejora y luego se estanca
    for i, w in enumerate(weights):
        s = WorkoutSession(performed_on=base + timedelta(days=7 * i), routine_name="Pecho")
        session.add(s)
        session.flush()
        session.add_all([WorkoutSet(session_id=s.id, exercise_id=inc.id, set_number=k, reps=8, weight=w) for k in (1, 2)])
    session.commit()
    today = base + timedelta(days=7 * 5)
    p = gym.progression(session, inc.id, today=today)
    assert p["sessions"] == 6 and p["change_top_weight"] == 2.5 and p["stagnant"] is True
    assert p["change_pct"] == round((gym.e1rm(42.5, 8) / gym.e1rm(40, 8) - 1) * 100, 1)
    s = WorkoutSession(performed_on=today, routine_name="Brazos")
    session.add(s)
    session.flush()
    session.add_all([WorkoutSet(session_id=s.id, exercise_id=curl.id, set_number=k, reps=8, weight=22) for k in (1, 2)])
    session.commit()
    vol = {m["muscle"]: m for m in gym.weekly_volume(session, today)["muscles"]}
    assert vol["pecho"]["sets"] == 2 and vol["hombros"]["sets"] == 1 and vol["triceps"]["sets"] == 1  # secundarios = 0,5
    assert vol["biceps"]["sets"] == 2 and vol["antebrazo"]["sets"] == 1
    assert vol["pecho"]["status"] == "bajo" and vol["cuadriceps"]["status"] == "sin trabajar"
    assert [x["name"] for x in gym.stagnations(session, today)] == ["Press inclinado"]


def test_goal_tracks_incline_press_automatically(client, session):
    inc = _ex(session, "Press inclinado")
    g = client.post("/api/goals", json={"title": "Press inclinado a 46 kg", "unit": "kg", "start_value": 40, "target_value": 46,
                                        "deadline": "2026-12-31", "auto_metric": "exercise_weight", "auto_exercise_id": inc.id}).json()
    assert g["auto_metric"] == "exercise_weight"
    client.post("/api/gym/sets", json={"exercise_id": inc.id, "reps": 8, "weight": 42.5, "rir": 2})
    g2 = client.get(f"/api/goals/{g['id']}").json()
    assert g2["current_value"] == 42.5 and g2["metrics"]["progress"] == round(2.5 / 6, 2)
    client.post("/api/gym/sets", json={"exercise_id": inc.id, "reps": 6, "weight": 46})
    assert client.get(f"/api/goals/{g['id']}").json()["status"] == "achieved"
    # objetivo de constancia: sesiones desde el inicio
    c = client.post("/api/goals", json={"title": "48 entrenos", "target_value": 48, "auto_metric": "workout_count"}).json()
    assert c["current_value"] == 1


def test_chat_logs_workout_and_answers(client):
    client.post("/api/gym/routines/import/rutina_4_dias")
    ev = _events(client.post("/api/assistant/chat", json={"text": "press inclinado 2x8 con 42,5 kg rir 2"}))
    logged = next(e for e in ev if e["type"] == "gym")
    assert logged["session"]["exercises"][0]["sets"][0] == {**logged["session"]["exercises"][0]["sets"][0], "reps": 8, "weight": 42.5, "rir": 2}
    reply = "".join(e.get("text", "") for e in ev)
    assert reply.startswith("Registrado en tu sesión de hoy: Press inclinado: 2×(8/8) con 42,5 kg, RIR 2")
    assert ev[-1]["mode"] == "gym"
    # preguntas: no se registran como series
    ev2 = _events(client.post("/api/assistant/chat", json={"text": "¿Cuánto he progresado en press inclinado?"}))
    assert not any(e["type"] == "gym" for e in ev2)
    assert "Press inclinado" in "".join(e.get("text", "") for e in ev2)
    ev3 = _events(client.post("/api/assistant/chat", json={"text": "¿Qué me toca hoy?"}))
    assert "Hoy toca" in "".join(e.get("text", "") for e in ev3)
    # «apúntame…» sigue siendo una tarea aunque mencione series
    ev4 = _events(client.post("/api/assistant/chat", json={"text": "apúntame hacer 3 series de sentadilla mañana"}))
    assert any(e["type"] == "task" for e in ev4) and not any(e["type"] == "gym" for e in ev4)


def test_gym_snapshot_reaches_ai(ollama, client):
    client.post("/api/gym/routines/import/rutina_4_dias")
    client.post("/api/gym/log-text", json={"text": "curl de bicep 22 kg 2 series x 8"})
    client.post("/api/assistant/chat", json={"text": "¿Cuánto volumen semanal hago de bíceps?"})
    system = ollama.requests[-1]["messages"][0]["content"]
    assert "volumen_semanal_series_por_musculo" in system and "Curl de bíceps" in system and "10-20 series" in system


def test_body_metrics_and_validation(client):
    assert client.post("/api/gym/body", json={}).status_code == 422
    r = client.post("/api/gym/body", json={"weight_kg": 78.4, "waist_cm": 82, "measured_on": "2026-11-20"})
    assert r.status_code == 201
    assert client.get("/api/gym/body").json()["items"][0]["weight_kg"] == 78.4
    assert client.post("/api/gym/sets", json={"exercise_id": 1, "reps": -1}).status_code == 422
