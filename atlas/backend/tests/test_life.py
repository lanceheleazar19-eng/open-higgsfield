"""VISTAN LIFE OS: CRUD, cálculos, dominio por evaluación, disciplina, decisiones, bloqueo con PIN e integración."""

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from atlas.agents.core import plan
from atlas.life import service as sv
from atlas.models import LfHabit


def today():
    return datetime.now().date()


def test_pin_lock_protects_private_routes(client):
    assert client.get("/api/life/lock").json() == {"enabled": False, "unlocked": True}
    assert client.get("/api/life/contacts").status_code == 200  # sin PIN: acceso normal
    assert client.put("/api/life/lock/pin", json={"pin": "12ab"}).status_code == 422
    assert client.put("/api/life/lock/pin", json={"pin": "4821"}).status_code == 200
    assert client.get("/api/life/contacts").status_code == 200  # este navegador queda desbloqueado
    other = TestClient(client.app)
    r = other.get("/api/life/contacts")
    assert r.status_code == 423 and r.json()["detail"]["locked"] is True
    assert other.post("/api/life/lock/unlock", json={"pin": "0000"}).status_code == 401
    assert other.post("/api/life/lock/unlock", json={"pin": "4821"}).status_code == 200
    assert other.get("/api/life/contacts").status_code == 200
    other.post("/api/life/lock/lock")
    assert other.get("/api/life/decisions").status_code == 423
    for _ in range(5):
        other.post("/api/life/lock/unlock", json={"pin": "1111"})
    assert other.post("/api/life/lock/unlock", json={"pin": "4821"}).status_code == 429  # fuerza bruta frenada
    assert client.request("DELETE", "/api/life/lock/pin", json={"pin": "9999"}).status_code in (401, 429)


def test_opportunity_economics_score_and_project(client):
    bad = client.post("/api/life/opportunities", json={"name": "X", "scores": {"pain": 9}})
    assert bad.status_code == 422
    o = client.post("/api/life/opportunities", json={
        "name": "Tienda de suplementos", "problem": "Precios altos", "next_actions": "- Entrevistar a 10 clientes\n- Pedir 3 presupuestos",
        "economics": {"price": 30, "unit_cost": 12, "fixed_monthly": 900, "units_month": 100, "initial_investment": 3000},
        "scores": {"pain": 4, "market": 3, "risk": 2}}).json()
    c = o["calc"]
    assert c["contribution_margin"] == 18 and c["gross_margin_pct"] == 60 and c["breakeven_units_month"] == 50
    assert c["profit_month"] == 900 and c["payback_months"] == pytest.approx(3.3) and c["basis"].startswith("estimación")
    assert o["score"]["rated"] == 3 and 0 < o["score"]["score"] <= 100 and "Media ponderada" in o["score"]["formula"]
    p = client.patch(f"/api/life/opportunities/{o['id']}", json={"status": "validating"}).json()
    assert p["status"] == "validating" and p["name"] == "Tienda de suplementos"
    pid = client.post(f"/api/life/opportunities/{o['id']}/project").json()["project_id"]
    tasks = [t for t in client.get("/api/tasks").json()["items"] if t.get("project_id") == pid]
    assert {t["title"] for t in tasks} == {"Entrevistar a 10 clientes", "Pedir 3 presupuestos"}
    assert client.post(f"/api/life/opportunities/{o['id']}/project").status_code == 409
    assert client.delete(f"/api/life/opportunities/{o['id']}").status_code == 200
    assert client.get("/api/life/opportunities").json()["items"] == []


def test_wealth_real_vs_estimated_virtual_and_simulation(client):
    client.post("/api/life/wealth/items", json={"side": "asset", "name": "Cuenta", "category": "cuenta", "value": 1500})
    client.post("/api/life/wealth/items", json={"side": "asset", "name": "Coche", "category": "vehículo", "value": 4000, "basis": "estimated"})
    client.post("/api/life/wealth/items", json={"side": "liability", "name": "Préstamo", "category": "préstamo", "value": 1000})
    client.post("/api/life/wealth/items", json={"side": "asset", "name": "Stock tienda", "category": "negocio", "value": 500, "scope": "business"})
    w = client.get("/api/life/wealth").json()
    nw = w["networth"]
    assert nw["net"] == 5000 and nw["estimated_part"] == 4000 and nw["business_net"] == 500 and nw["personal_net"] == 4500
    assert len(w["history"]) == 1 and w["history"][0]["net"] == 5000
    client.get("/api/desk/accounts")
    w = client.get("/api/life/wealth").json()
    assert {v["kind"] for v in w["virtual"]} == {"Trading Desk (virtual)"} and w["savings"]["basis"].startswith("dinero real")
    s = client.post("/api/life/wealth/simulate", json={"start": 1000, "monthly": 100, "annual_return_pct": 0, "years": 2}).json()
    assert s["final"]["balance"] == 3400 and s["final"]["growth"] == 0 and "simulación" in s["basis"]


def test_mastery_only_from_assessments(client, session, ollama):
    subs = client.get("/api/life/academy").json()
    assert len(subs) == 16 and all(s["mastery"]["label"] == "Sin evaluar" for s in subs)
    sid = subs[0]["id"]
    ollama.json_reply = {"explicacion": "La oferta y la demanda…", "ideas_clave": ["precio"], "ejemplos_reales": [], "caso_practico": {}, "ejercicios": []}
    les = client.post(f"/api/life/academy/{sid}/lessons", json={"topic": "Oferta y demanda", "level": 1}).json()
    client.post(f"/api/life/lessons/{les['id']}/complete")
    m = client.get(f"/api/life/academy/{sid}").json()["mastery"]
    assert m["level"] == 0 and m["lessons_done"] == 1  # completar lecciones NO da dominio
    ollama.json_reply = {"preguntas": [
        {"type": "mcq", "q": "¿2+2?", "options": ["3", "4", "5", "6"], "answer": 1, "explanation": "suma", "topic": "aritmética"},
        {"type": "mcq", "q": "¿Capital de Francia?", "options": ["Roma", "París"], "answer": 1, "explanation": "", "topic": "geografía"},
        {"type": "open", "q": "Explica la inflación", "rubric": "subida general de precios", "topic": "inflación"},
        {"type": "mcq", "q": "malformada", "options": ["a"], "answer": 5}]}
    a = client.post(f"/api/life/academy/{sid}/assessments", json={"kind": "quiz"}).json()
    assert len(a["questions"]) == 3 and "answer" not in a["questions"][0]  # sin pistas antes de responder
    assert client.post(f"/api/life/assessments/{a['id']}/submit", json={"answers": [1]}).status_code == 422
    ollama.json_reply = {"notas": [{"score": 50, "feedback": "Incompleta", "mejor_respuesta": "…"}]}
    g = client.post(f"/api/life/assessments/{a['id']}/submit", json={"answers": [1, 0, "Que suben los precios"]}).json()
    assert g["score"] == pytest.approx((100 + 0 + 50) / 3, abs=0.1)
    assert g["feedback"]["weak_topics"] == ["geografía", "inflación"]
    assert g["mastery"]["level"] == 2 and g["mastery"]["label"] == "Básico"
    assert client.post(f"/api/life/assessments/{a['id']}/submit", json={"answers": [1, 1, "x"]}).status_code == 409


def test_simulator_conversation_and_debrief(client, ollama):
    ollama.reply_chunks = ["¿Por qué debería ", "invertir en ti?"]
    s = client.post("/api/life/sims", json={"scenario": "investor"}).json()
    assert s["transcript"][0] == {"role": "counterpart", "content": "¿Por qué debería invertir en ti?"} and s["area"] == "leadership"
    assert client.post(f"/api/life/sims/{s['id']}/finish").status_code == 422
    ollama.reply_chunks = ["¿Y la tracción?"]
    s = client.post(f"/api/life/sims/{s['id']}/say", json={"text": "Tenemos 200 usuarios activos y crecemos un 10 % al mes"}).json()
    assert [m["role"] for m in s["transcript"]] == ["counterpart", "user", "counterpart"]
    ollama.json_reply = {"resumen": "Claro con los datos", "decisiones": [], "criterios": {"claridad": 4}, "lo_mejor": ["datos"], "a_mejorar": ["pedir cifra"]}
    f = client.post(f"/api/life/sims/{s['id']}/finish").json()
    assert f["status"] == "finished" and f["debrief"]["criterios"]["claridad"] == 4
    assert client.post(f"/api/life/sims/{s['id']}/say", json={"text": "hola"}).status_code == 409
    assert client.post("/api/life/sims", json={"scenario": "nope"}).status_code == 404


def test_discipline_streaks_patterns_and_reminders(client, session):
    h = client.post("/api/life/habits", json={"name": "Leer", "category": "reading", "kind": "amount", "target": 20, "unit": "pág", "remind_at": "08:00"}).json()
    hab = session.get(LfHabit, h["id"])
    hab.created_at = datetime.utcnow() - timedelta(days=40)
    session.commit()
    t = today()
    for i in range(1, 4):
        client.put(f"/api/life/habits/{h['id']}/log", json={"day": (t - timedelta(days=i)).isoformat(), "value": 25})
    client.put(f"/api/life/habits/{h['id']}/log", json={"day": (t - timedelta(days=4)).isoformat(), "value": 5})  # no llega al objetivo
    st = client.put(f"/api/life/habits/{h['id']}/log", json={"day": t.isoformat(), "value": 30}).json()
    assert st["streak"] == 4 and st["done_today"] is True
    assert st["met_30d"] == 3 and st["due_30d"] == 29 and st["compliance_30d"] == pytest.approx(3 / 29 * 100, abs=0.1)
    assert client.put(f"/api/life/habits/{h['id']}/log", json={"day": (t + timedelta(days=1)).isoformat()}).status_code == 422
    client.post("/api/life/commitments", json={"period": "week", "title": "Enviar 5 propuestas", "due": (t - timedelta(days=2)).isoformat()})
    d = client.get("/api/life/discipline").json()
    assert any("Leer" in f for f in d["findings"]) and any("vencidos" in f for f in d["findings"])
    assert d["overdue_commitments"][0]["title"] == "Enviar 5 propuestas"
    c = d["commitments"][0]
    assert client.patch(f"/api/life/commitments/{c['id']}", json={"status": "missed"}).json()["status"] == "missed"
    # Recordatorio: solo si no está registrado hoy, y una vez al día
    client.delete(f"/api/life/habits/{h['id']}/log", params={"day": t.isoformat()})
    now = datetime.combine(t, datetime.min.time()).replace(hour=9)
    assert sv.reminders(session, now) == 1 and sv.reminders(session, now) == 0


def test_crm_decisions_failures_goals_vision_and_memory(client, session):
    assert client.post("/api/life/contacts", json={"name": "Ana", "email": "no-es-email"}).status_code == 422
    c = client.post("/api/life/contacts", json={"name": "Ana López", "company": "Acme", "email": "ana@acme.com",
                                                "next_followup": (today() - timedelta(days=1)).isoformat()}).json()
    client.post(f"/api/life/contacts/{c['id']}/interactions", json={"day": today().isoformat(), "summary": "Café: interés en colaborar",
                                                                   "next_followup": (today() + timedelta(days=14)).isoformat()})
    c2 = client.get("/api/life/contacts").json()[0]
    assert c2["last_interaction"] == today().isoformat() and c2["next_followup"] == (today() + timedelta(days=14)).isoformat()
    assert client.post(f"/api/life/contacts/{c['id']}/task").status_code == 201
    d = client.post("/api/life/decisions", json={"title": "Dejar el trabajo de verano", "day": "2026-06-01", "decision": "Me quedo",
                                                 "confidence": 80, "review_on": "2026-09-01", "remember": True}).json()
    lst = client.get("/api/life/decisions").json()
    assert d["id"] in lst["due"] and lst["calibration"]["reviewed"] == 0
    r = client.post(f"/api/life/decisions/{d['id']}/review", json={"actual_result": "Salió peor", "outcome": "worse", "analyze": False}).json()
    assert r["outcome"] == "worse" and r["calibration"]["brier"] == pytest.approx(0.64)
    mem = client.get("/api/memory").json()
    assert any("Dejar el trabajo de verano" in m["content"] for m in (mem if isinstance(mem, list) else mem["items"]))
    client.post("/api/life/failures", json={"title": "Lancé sin validar", "kind": "business", "day": "2026-05-01", "tags": ["sin validar", "prisa"]})
    assert client.post("/api/life/failures/analyze").status_code == 422
    client.post("/api/life/failures", json={"title": "Curso abandonado", "kind": "goal", "day": "2026-07-01", "tags": ["Prisa"]})
    assert client.get("/api/life/failures").json()["patterns"]["repeated"] == ["prisa"]
    g = client.post("/api/goals", json={"title": "Aprender a programar", "kind": "milestones", "deadline": (today() + timedelta(days=80)).isoformat()}).json()
    made = client.post(f"/api/life/goals/{g['id']}/plan/apply", json={"tasks": [{"titulo": "Curso de Python", "fecha": (today() + timedelta(days=10)).isoformat()},
                                                                               {"titulo": ""}, {"titulo": "Primer proyecto", "prioridad": "high"}]}).json()
    assert made["created"] == 2
    gl = client.get("/api/life/goals").json()["items"][0]
    assert gl["tasks"] == 2 and gl["horizon"] == "3 meses"
    assert client.put("/api/life/vision/person", json={"content": "Alguien que cumple lo que promete"}).status_code == 200
    assert client.put("/api/life/vision/nope", json={"content": "x"}).status_code == 404
    client.post("/api/life/timeline", json={"year": 2030, "title": "Primera empresa rentable", "area": "negocio"})
    v = client.get("/api/life/vision").json()
    assert v["sections"][0]["content"].startswith("Alguien") and v["timeline"][0]["year"] == 2030


def test_overview_indicators_briefing_review_and_agents(client):
    client.post("/api/life/habits", json={"name": "Estudiar", "category": "study", "kind": "amount", "target": 30, "unit": "min"})
    o = client.get("/api/life/overview").json()
    keys = {a["key"] for a in o["growth"]}
    assert keys == {"entrepreneurship", "finance", "knowledge", "leadership", "discipline", "communication", "health", "goals", "relationships"}
    assert all("how" in i for a in o["growth"] for i in a["indicators"])  # cada indicador explica su cálculo
    assert "valor como persona" in o["note"]
    from atlas.db import session_scope
    from atlas.workflows.engine import _briefing, weekly_review
    with session_scope() as db:
        assert "Hábitos de hoy" in _briefing(db, {"timezone": "Europe/Madrid"})
        assert "LIFE OS" in weekly_review(db, "Europe/Madrid")
    assert "discipline" in plan("no estoy siendo constante con mis hábitos de lectura")
    assert "learning" in plan("quiero preparar un examen de economía")
    assert "decision" in plan("revisa mis decisiones y sesgos")
    assert "business" in plan("analiza la viabilidad de mi idea de negocio")
    run = client.post("/api/agents/run", json={"text": "¿cómo van mis hábitos y mi disciplina?"}).json()
    assert "discipline" in str(run)
    date.today()
