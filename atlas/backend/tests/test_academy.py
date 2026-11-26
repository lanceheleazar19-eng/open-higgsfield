"""VISTAN ACADEMY: biblioteca, cursos, lecciones, profesor, exámenes con criterios definidos, repetición espaciada, progreso
real, itinerarios, laboratorios, investigación, memoria educativa, permisos e integración con VISTAN CORE."""

import json
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

AI = {  # una respuesta JSON con las claves de cada generador (cada uno lee las suyas)
    "titulo": "Economía desde cero", "descripcion": "Curso progresivo", "nivel_inicial": 1, "objetivos": ["Entender la oferta y la demanda"],
    "modulos": [{"titulo": "Fundamentos", "objetivo": "Bases", "lecciones": [{"titulo": "Oferta y demanda", "objetivo": "Entender precios", "minutos": 30},
                                                                          {"titulo": "Elasticidad", "objetivo": "Medir reacciones", "minutos": 25}]},
                {"titulo": "Macroeconomía", "objetivo": "Visión global", "lecciones": [{"titulo": "Inflación", "objetivo": "Qué es", "minutos": 30}]}],
    "horas_estimadas": 1.5, "proyecto_final": "Analiza un mercado real", "criterios": ["Examen de módulo ≥ 70 %"],
    "introduccion": "Hoy veremos…", "aprenderas": ["Qué es la demanda"], "teoria": "La **demanda** es…", "conceptos": [{"termino": "Demanda", "definicion": "…"}],
    "ejemplos": ["Precio del café"], "aplicaciones": ["Fijar precios"], "errores_frecuentes": ["Confundir demanda con cantidad demandada"],
    "resumen": "Resumen", "preguntas_comprension": [{"pregunta": "¿Qué es?", "respuesta": "…"}], "ejercicios": ["Dibuja la curva"],
    "evaluacion": [{"q": "Si sube el precio, la cantidad demandada…", "options": ["sube", "baja", "igual", "no se sabe"], "answer": 1, "explanation": "Ley de la demanda",
                    "topic": "Ley de la demanda"}],
    "tabla": "| a | b |\n|---|---|\n| 1 | 2 |", "diagrama": None, "codigo": None,
    "preguntas": [{"type": "mcq", "q": "¿Qué desplaza la demanda?", "options": ["renta", "precio propio", "nada", "coste"], "answer": 0, "explanation": "La renta", "topic": "Ley de la demanda"},
                  {"type": "tf", "q": "La inflación siempre es buena", "answer": False, "explanation": "No", "topic": "Inflación"},
                  {"type": "numeric", "q": "17 × 23", "answer": 391, "tolerance": 0, "explanation": "391", "topic": "Cálculo"},
                  {"type": "open", "q": "Explica la elasticidad", "criteria": [{"criterio": "Define elasticidad", "puntos": 5}, {"criterio": "Pone un ejemplo", "puntos": 5}],
                   "model_answer": "…", "topic": "Elasticidad"},
                  {"type": "code", "q": "Escribe suma(a, b)", "tests": "assert suma(2, 3) == 5\nassert suma(-1, 1) == 0", "solution": "def suma(a, b):\n    return a + b", "topic": "Funciones"},
                  {"type": "code", "q": "Escribe resta(a, b)", "tests": "assert resta(5, 3) == 2", "solution": "def resta(a, b):\n    return a + b", "topic": "Funciones"}],
    "correcciones": [{"criterios": [{"cumple": True, "porque": "define"}, {"cumple": False, "porque": "sin ejemplo"}], "feedback": "Falta un ejemplo"}],
    "competencias": ["Análisis económico"], "pasos": [{"titulo": "Fundamentos de economía", "materia": "Economía básica", "por_que": "Base", "evaluacion": "Examen",
                                                         "proyecto": "Mini informe", "nota_minima": 70}, {"titulo": "Finanzas", "materia": "Finanzas personales", "por_que": "x"}],
    "enunciado": "Escribe doble(x) que devuelva el doble", "plantilla": "def doble(x):", "tests": "assert doble(2) == 4\nassert doble(0) == 0",
    "solucion": "def doble(x):\n    return 2 * x", "pista": "Multiplica",
    "patron": "Confunde desplazamiento con movimiento", "explicacion": "Piensa en…", "claves": ["Desplazamiento ≠ movimiento"],
    "verificado": [{"texto": "La inflación mide la subida general de precios", "fuentes": [1]}, {"texto": "Dato sin fuente", "fuentes": [99]}],
    "interpretaciones": ["i"], "hipotesis": ["h"], "explicacion_ia": "Explicación didáctica", "preguntas_repaso": ["¿Qué es la inflación?"],
}


def eco(client) -> int:
    lib = client.get("/api/academy/library?category=economia").json()
    return next(s["id"] for s in lib if s["key"] == "economia")


def test_library_catalog_and_custom_disciplines(client):
    meta = client.get("/api/academy/meta").json()
    assert len(meta["categories"]) == 9 and len(meta["teachers"]) == 12 and meta["coordinator"] == "Academy Coordinator"
    lib = client.get("/api/academy/library").json()
    assert len(lib) >= 110 and {s["category"] for s in lib} == set(meta["categories"])
    assert any(s["key"] == "economia" and s["category"] == "economia" for s in lib)  # la asignatura de LIFE OS se conserva
    assert len([s for s in lib if s["name"] == "Inteligencia artificial"]) == 1  # sin duplicar las de LIFE OS
    assert client.get("/api/academy/library").json() == lib  # idempotente
    s = client.post("/api/academy/library", json={"name": "Ajedrez estratégico", "category": "psicologia"}).json()
    assert s["custom"] is True
    assert client.post("/api/academy/library", json={"name": "Ajedrez estratégico", "category": "psicologia"}).status_code == 409
    assert client.delete(f"/api/academy/library/{lib[0]['id']}").status_code == 409  # solo las propias
    assert client.delete(f"/api/academy/library/{s['id']}").status_code == 204


def test_course_lesson_flow_progress_and_real_stats(client, ollama):
    ollama.json_reply = AI
    sid = eco(client)
    c = client.post("/api/academy/courses", json={"request": "Quiero aprender economía desde cero hasta nivel avanzado", "subject_id": sid}).json()
    assert c["title"] == "Economía desde cero" and len(c["modules"]) == 2 and c["progress"]["next"] == {"module": 0, "lesson": 0, "lesson_id": None, "title": "Oferta y demanda"}
    d0 = client.get("/api/academy/dashboard").json()
    assert d0["stats"]["hours"] == 0 and d0["stats"]["lessons_done"] == 0 and d0["stats"]["streak"] == 0  # nada inventado
    x = client.post(f"/api/academy/courses/{c['id']}/lessons/0/0").json()
    assert x["content"]["teoria"] and x["content"]["teacher"][0] == "Economics Teacher" and x["content"]["generated_by_ai"]
    assert "youtube.com/results?search_query=" in x["content"]["video_search"]
    assert client.post(f"/api/academy/courses/{c['id']}/lessons/0/0").json()["id"] == x["id"]  # no se regenera
    pub = client.get(f"/api/academy/lessons/{x['id']}").json()
    assert "answer" not in pub["content"]["evaluacion"][0]  # sin respuestas antes de contestar
    client.patch(f"/api/academy/lessons/{x['id']}/progress", json={"section": 3, "seen": ["intro", "teoria"]})
    chk = client.post(f"/api/academy/lessons/{x['id']}/check", json={"answers": [1]}).json()
    assert chk["score"] == 100 and chk["results"][0]["correct"]
    client.post(f"/api/academy/lessons/{x['id']}/complete", json={"minutes": 24})
    assert client.get(f"/api/academy/lessons/{x['id']}").json()["progress"]["section"] == 3  # recuerda dónde te quedaste
    d = client.get("/api/academy/dashboard").json()
    assert d["stats"]["lessons_done"] == 1 and d["stats"]["hours"] == 0.4 and d["stats"]["streak"] == 1
    assert d["courses"][0]["progress"]["done"] == 1 and d["continue"]["kind"] == "course"
    assert d["gamification"]["xp"] > 0 and "Primera lección" in d["gamification"]["badges"]
    # editar/reorganizar: la lección generada sigue a su título
    mods = c["modules"]
    mods[0]["lessons"].reverse()
    r = client.patch(f"/api/academy/courses/{c['id']}", json={"modules": mods, "status": "paused"}).json()
    assert r["status"] == "paused" and r["progress"]["lessons"]["0-1"]["done"] is True


def test_exam_criteria_based_grading_and_adaptive_tracking(client, ollama, session):
    ollama.json_reply = AI
    sid = eco(client)
    e = client.post("/api/academy/exams", json={"subject_id": sid, "kind": "exam", "types": ["mcq", "tf", "numeric", "open", "code"], "n": 6}).json()
    types = [q["type"] for q in e["questions"]]
    assert types == ["mcq", "tf", "numeric", "open", "code"]  # el código cuya solución falla sus propios tests se descarta
    assert all("answer" not in q and "solution" not in q for q in e["questions"]) and e["questions"][3]["criteria"][0]["puntos"] == 5
    g = client.post(f"/api/academy/exams/{e['id']}/submit", json={"answers": [0, True, "391", "La elasticidad mide…", "def suma(a, b):\n    return a + b"], "minutes": 12}).json()
    res = g["feedback"]["results"]
    assert [r["score"] for r in res] == [100.0, 0.0, 100.0, 50.0, 100.0]
    assert res[3]["criteria"][0]["cumple"] is True and res[3]["graded_by"].startswith("rúbrica")
    # nota por puntos: mcq 1 + tf 1 + numérica 2 + abierta 3 + código 4 = 11; obtenidos 1 + 0 + 2 + 1,5 + 4 = 8,5
    assert g["score"] == round(8.5 / 11 * 100, 1) and g["feedback"]["grade_10"] == round(g["score"] / 10, 1)
    assert "Inflación" in g["feedback"]["weak_topics"]
    assert client.post(f"/api/academy/exams/{e['id']}/submit", json={"answers": [0, True, "1", "", ""]}).status_code == 409
    prog = client.get("/api/academy/progress").json()
    assert prog["stats"]["exams"] == 1 and prog["stats"]["concepts"]["consolidado"] == 0  # un único test nunca consolida
    assert any(c["name"] == "Inflación" and c["state"] == "aprendiendo" for c in prog["learning"])


def test_spaced_repetition_consolidation_rule_and_remediation(client, ollama, session):
    from atlas.academy import tracker
    from atlas.models import AcConcept
    ollama.json_reply = AI
    sid = eco(client)
    c = tracker.concept(session, sid, "Coste de oportunidad")
    tracker.review(c, 100, "exam")
    assert c.interval_days == 1 and c.state == "reciente"
    tracker.review(c, 100, "review")
    tracker.review(c, 100, "review")
    assert c.state == "reciente"  # 3 aciertos el mismo día no bastan
    c.first_ok_at = datetime.utcnow() - timedelta(days=8)
    tracker.review(c, 95, "review")
    assert c.state == "consolidado" and c.interval_days >= 7
    bad = tracker.concept(session, sid, "Elasticidad cruzada")
    tracker.review(bad, 0, "exam", "¿Qué es la elasticidad cruzada?")
    tracker.review(bad, 20, "review", "Calcula la elasticidad cruzada")
    assert tracker.error_pattern(bad) and bad.due_on == date.today() + timedelta(days=1)
    bad.due_on = date.today()
    session.commit()
    rv = client.get("/api/academy/reviews").json()
    assert any(x["name"] == "Elasticidad cruzada" for x in rv["due"]) and rv["patterns"]
    r = client.post(f"/api/academy/concepts/{bad.id}/remediate").json()
    assert r["remediation"]["pattern"] and r["exam"]["kind"] == "review"
    assert client.post("/api/academy/reviews/start").json()["kind"] == "review"
    assert client.post("/api/academy/reviews/schedule").json()["created"] >= 1
    assert client.post("/api/academy/reviews/schedule").json()["created"] == 0  # sin duplicar recordatorios
    assert client.patch(f"/api/academy/concepts/{bad.id}", json={"reset": True}).json()["state"] == "nuevo"
    session.expire_all()
    assert session.get(AcConcept, c.id).state == "consolidado"


def test_tutor_coordinator_teachers_and_high_impact_limits(client, ollama):
    ollama.json_reply = AI
    ollama.reply_chunks = ["La demanda es la cantidad que los consumidores desean comprar. ¿Qué crees que pasa si sube el precio?"]
    sid = eco(client)
    r = client.post("/api/academy/tutor", json={"subject_id": sid, "action": "cero", "question": "la demanda"}).json()
    assert r["teachers"][0] == "Economics Teacher" and r["coordinator"] == "Academy Coordinator"
    r2 = client.post("/api/academy/tutor", json={"subject_id": sid, "question": "¿Cómo afecta la inflación a mi inversión en bolsa?"}).json()
    assert "Finance Teacher" in r2["teachers"]  # colaboración entre disciplinas
    sent = json.dumps(ollama.requests[-1], ensure_ascii=False)
    assert "Enséñame este tema desde cero" in sent  # el historial previo llega al profesor
    hist = client.get(f"/api/academy/tutor/history?subject_id={sid}").json()
    assert len(hist) == 4
    lib = client.get("/api/academy/library?category=derecho").json()
    x = client.post("/api/academy/lessons", json={"subject_id": lib[0]["id"], "topic": "Contratos", "level": 1}).json()
    assert "no asesoramiento jurídico" in x["content"]["disclaimer"]


def test_paths_and_step_courses(client, ollama):
    ollama.json_reply = AI
    p = client.post("/api/academy/paths", json={"goal": "De principiante a emprendedor", "start_level": 1}).json()
    assert len(p["steps"]) == 2 and p["steps"][0]["unlocked"] and not p["steps"][1]["unlocked"] and p["steps"][0]["min_score"] == 70
    c = client.post(f"/api/academy/paths/{p['id']}/steps/0/course").json()
    assert c["path_id"] == p["id"]
    p2 = client.get("/api/academy/paths").json()[0]
    assert p2["steps"][0]["course_id"] == c["id"] and p2["steps"][0]["passed"] is False
    edited = client.patch(f"/api/academy/paths/{p['id']}", json={"steps": [{**p2["steps"][1], "min_score": 80}]}).json()
    assert len(edited["steps"]) == 1 and edited["steps"][0]["min_score"] == 80


def test_labs_virtual_money_and_sandboxed_code(client, ollama):
    ollama.json_reply = AI
    comp = client.post("/api/academy/labs/finance/compound", json={"start": 1000, "monthly": 0, "rate_pct": 12, "years": 1}).json()
    assert round(comp["final"]["balance"], 2) == round(1000 * (1.01 ** 12), 2) and "VIRTUAL" in comp["note"]
    risk = client.post("/api/academy/labs/finance/risk", json={"amount": 1000, "mean_pct": 6, "vol_pct": 15, "years": 10}).json()
    assert risk == client.post("/api/academy/labs/finance/risk", json={"amount": 1000, "mean_pct": 6, "vol_pct": 15, "years": 10}).json()  # reproducible
    b = client.post("/api/academy/labs/business", json={"name": "Café ficticio", "model": "venta directa", "market_demand": 1000, "competitor_price": 3}).json()
    rnd = client.post(f"/api/academy/labs/{b['id']}/round", json={"price": 3, "unit_cost": 1, "fixed_costs": 500}).json()
    r = rnd["state"]["rounds"][0]["result"]
    assert r["units"] == 1000 and r["profit"] == 1500 and r["break_even_units"] == 250
    fin = client.post(f"/api/academy/labs/{b['id']}/finish").json()
    assert fin["status"] == "done" and fin["score"] == 90.0
    closes = [100 + i * 0.5 + (5 if i % 20 < 10 else -5) for i in range(120)]
    bt = client.post("/api/academy/labs/trading/backtest", json={"closes": closes, "strategy": "sma", "fast": 5, "slow": 20}).json()
    assert bt["result"]["trades"] >= 1 and "Nunca se ejecutan órdenes reales" in bt["result"]["note"]
    assert client.post("/api/academy/labs/trading/backtest", json={"closes": [1, 2, 3]}).status_code == 422
    ex = client.post("/api/academy/labs/programming", json={"level": 1, "topic": "funciones"}).json()
    assert "solution" not in ex["state"] and ex["state"]["tests"]
    wrong = client.post(f"/api/academy/labs/{ex['id']}/submit", json={"code": "def doble(x):\n    return x + 1"}).json()
    assert wrong["last"]["score"] < 100 and wrong["status"] == "open"
    ok = client.post(f"/api/academy/labs/{ex['id']}/submit", json={"code": "def doble(x):\n    return x * 2"}).json()
    assert ok["last"]["score"] == 100 and ok["status"] == "done" and ok["state"]["solution"]
    crit = client.post("/api/academy/labs/critical").json()
    assert crit["kind"] == "critical" and crit["questions"]
    neg = client.get("/api/life/scenarios").json()
    assert sum(1 for v in neg.values() if v["area"] == "negotiation") == 4


def test_research_material_only_from_verified_sources(client, ollama, session, monkeypatch):
    from atlas.models import AcLab, Research
    from atlas.research import engine
    monkeypatch.setattr(engine, "start", lambda rid: None)  # sin internet en las pruebas: el informe se prepara a mano
    ollama.json_reply = AI
    lab = client.post("/api/academy/research", json={"question": "¿Qué es la inflación y cómo se mide?"}).json()
    assert client.post(f"/api/academy/research/{lab['id']}/material").status_code in (409,)
    r = session.get(Research, session.get(AcLab, lab["id"]).state["research_id"])
    r.status, r.report = "done", {"summary": "s", "conclusions": [{"text": "La inflación mide…", "sources": [1]}]}
    r.state = {"sources": [{"id": 1, "url": "https://www.ine.es/x", "title": "INE", "read": True, "reliability": "alta", "snippet": ""}], "done": []}
    session.commit()
    resp = client.post(f"/api/academy/research/{lab['id']}/material")
    assert resp.status_code == 200, resp.text
    m = resp.json()["result"]
    assert len(m["verificado"]) == 1 and m["sin_fuente_descartado"] == 1 and m["bibliografia"][0]["url"] == "https://www.ine.es/x"


def test_memory_export_delete_settings_lock_and_core_integration(client, ollama):
    ollama.json_reply = AI
    sid = eco(client)
    x = client.post("/api/academy/lessons", json={"subject_id": sid, "topic": "Oferta", "level": 1}).json()
    assert client.get("/api/academy/memory").json()["lessons"] == 1
    exp = client.get("/api/academy/export")
    assert exp.headers["content-disposition"].startswith("attachment") and json.loads(exp.content)["lessons"][0]["topic"] == "Oferta"
    assert client.delete(f"/api/academy/memory/lesson/{x['id']}").status_code == 204
    assert client.put("/api/academy/settings", json={"gamification": False}).json()["gamification"] is False
    assert client.get("/api/academy/dashboard").json()["gamification"] is None
    g = client.post("/api/academy/goals", json={"title": "Estudiar 20 h de economía", "target_hours": 20}).json()
    assert client.get("/api/academy/dashboard").json()["goals"][0]["id"] == g["id"]
    from atlas.agents.core import plan
    assert "learning" in plan("quiero estudiar economía y repasar para el examen")
    client.put("/api/life/lock/pin", json={"pin": "4821"})
    other = TestClient(client.app)
    assert other.get("/api/academy/dashboard").status_code == 423  # mismo control de acceso que LIFE OS
