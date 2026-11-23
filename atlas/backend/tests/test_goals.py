import json
from datetime import date, timedelta

from atlas.models import Goal, Task
from atlas.services.goals import metrics


def test_numeric_goal_metrics_on_track_behind_and_projection(session):
    g = Goal(title="Ahorrar", kind="numeric", unit="€", start_value=0, target_value=5000, current_value=1000,
             start_date=date(2026, 1, 1), deadline=date(2026, 12, 31))
    session.add(g)
    session.commit()
    m = metrics(session, g, date(2026, 3, 2))  # 60 días de 364 → esperado ~16 %
    assert m["progress"] == 0.2 and m["pace"] == "on_track"
    assert m["remaining"] == 4000 and m["days_left"] == 304
    assert m["required_per_week"] == round(4000 / (304 / 7), 2)
    assert m["rate_per_week"] == round(1000 / 60 * 7, 2)
    assert m["projected_date"] == (date(2026, 3, 2) + timedelta(days=240)).isoformat()
    m2 = metrics(session, g, date(2026, 7, 1))  # mitad de año con 20 % → por detrás
    assert m2["pace"] == "behind"


def test_decreasing_goal_weight_loss(session):
    g = Goal(title="Bajar a 78 kg", kind="numeric", unit="kg", start_value=86, target_value=78, current_value=82,
             start_date=date(2026, 1, 1), deadline=date(2026, 5, 1))
    session.add(g)
    session.commit()
    m = metrics(session, g, date(2026, 2, 1))
    assert m["progress"] == 0.5 and m["pace"] == "ahead" and m["remaining"] == -4
    assert m["projected_date"] == (date(2026, 2, 1) + timedelta(days=31)).isoformat()


def test_milestone_goal_uses_linked_tasks(client, session):
    g = client.post("/api/goals", json={"title": "Lanzar la tienda", "kind": "milestones", "deadline": "2030-01-01"}).json()
    session.add_all([Task(title=f"Paso {i}", goal_id=g["id"], status="done" if i < 2 else "pending") for i in range(4)])
    session.commit()
    d = client.get(f"/api/goals/{g['id']}").json()
    assert d["metrics"]["progress"] == 0.5 and d["tasks_total"] == 4 and d["tasks_done"] == 2
    assert client.post(f"/api/goals/{g['id']}/progress", json={"value": 3}).status_code == 422


def test_goal_api_progress_history_and_achievement(client):
    r = client.post("/api/goals", json={"title": "Ahorrar 3000 €", "unit": "€", "target_value": 3000, "deadline": "2030-12-31", "area": "finanzas"})
    assert r.status_code == 201
    gid = r.json()["id"]
    assert r.json()["metrics"]["progress"] == 0
    client.post(f"/api/goals/{gid}/progress", json={"delta": 500, "note": "Nómina"})
    d = client.post(f"/api/goals/{gid}/progress", json={"value": 1200}).json()
    assert d["current_value"] == 1200 and [h["value"] for h in d["history"]] == [0, 500, 1200]
    assert d["metrics"]["progress"] == 0.4
    done = client.post(f"/api/goals/{gid}/progress", json={"value": 3000}).json()
    assert done["status"] == "achieved"
    assert client.get("/api/goals").json()["items"] == []  # ya no está activo
    assert client.get("/api/goals", params={"status": "all"}).json()["items"][0]["status"] == "achieved"
    acts = [a["summary"] for a in client.get("/api/dashboard").json()["activity"]["items"]]
    assert any("Objetivo conseguido" in a for a in acts)


def test_goal_validation(client):
    assert client.post("/api/goals", json={"title": "Sin meta"}).status_code == 422
    assert client.post("/api/goals", json={"title": "Igual", "target_value": 0}).status_code == 422
    assert client.post("/api/goals", json={"title": "Fechas", "target_value": 5, "start_date": "2030-01-02", "deadline": "2030-01-01"}).status_code == 422
    gid = client.post("/api/goals", json={"title": "Leer 5 libros", "target_value": 5}).json()["id"]
    assert client.post(f"/api/goals/{gid}/progress", json={"value": 1, "delta": 1}).status_code == 422


def test_behind_goal_creates_alert_and_reaches_ai(ollama, client, session):
    g = Goal(title="Ahorrar 5000 €", kind="numeric", unit="€", start_value=0, target_value=5000, current_value=100,
             start_date=date.today() - timedelta(days=200), deadline=date.today() + timedelta(days=100))
    session.add(g)
    session.commit()
    alerts = [a["text"] for a in client.get("/api/dashboard").json()["alerts"]]
    assert any("va por detrás del ritmo" in a and "por semana" in a for a in alerts)
    client.post("/api/assistant/chat", json={"text": "¿Cómo voy con mis objetivos?"})
    system = ollama.requests[-1]["messages"][0]["content"]
    assert "Ahorrar 5000 €" in system and "por detrás" in system and "necesario_por_semana" in system


def test_week_plan_reaches_ai_only_when_asked(ollama, client):
    client.post("/api/tasks", json={"title": "Preparar oferta", "priority": "high"})
    client.post("/api/assistant/chat", json={"text": "hola"})
    assert "PLAN SEMANAL" not in ollama.requests[-1]["messages"][0]["content"]
    client.post("/api/assistant/chat", json={"text": "Organízame la semana"})
    assert "PLAN SEMANAL" in ollama.requests[-1]["messages"][0]["content"]
