"""VISTAN INNOVATION LAB: radar, publicaciones reales (formato), experimentos verificables, Arena, sandbox aislado,
biblioteca + RAG, ideas convertibles, escenarios sin hechos inventados, patentes, proyectos, automatizaciones y agente."""

import json
from datetime import date

import pytest

from atlas.agents.core import plan
from atlas.lab import arena, sandbox
from atlas.lab import sources as src


class _R:
    def __init__(self, status=200, js=None, text=""):
        self.status_code, self._js, self.text = status, js, text

    def json(self):
        return self._js


ARXIV = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2511.00001v1</id>
<published>2026-11-20T10:00:00Z</published><title>Humanoid robots
 that learn</title><summary>We study ...</summary><author><name>A. Pérez</name></author></entry></feed>"""
OPENALEX = {"results": [{"id": "https://openalex.org/W1", "display_name": "Solid-state batteries review", "publication_date": "2026-10-01",
                         "doi": "https://doi.org/10.1/x", "type": "article", "cited_by_count": 12,
                         "primary_location": {"source": {"display_name": "Nature Energy"}},
                         "authorships": [{"author": {"display_name": "B. Li"}}], "abstract_inverted_index": {"Solid": [0], "batteries": [1]}}]}


@pytest.fixture()
def papers(monkeypatch):
    def fake(url, params=None, headers=None, timeout=None):
        if "arxiv" in url:
            return _R(text=ARXIV)
        if "openalex" in url:
            return _R(js=OPENALEX)
        return _R(404)
    monkeypatch.setattr(src.httpx, "get", fake)


def test_radar_technologies_discoveries_and_real_papers(client, papers):
    assert client.post("/api/lab/technologies", json={"name": "Robótica humanoide", "category": "nope"}).status_code == 422
    t = client.post("/api/lab/technologies", json={"name": "Robótica humanoide", "category": "robotics", "maturity": "prototype",
                                                   "entities": ["Figure AI", "Boston Dynamics"]}).json()
    bad = client.post("/api/lab/discoveries", json={"title": "Algo", "category": "robotics", "maturity": "prototype"})
    assert bad.status_code == 422  # sin fuente no se registra
    d = client.post("/api/lab/discoveries", json={"title": "Nuevo actuador", "category": "robotics", "maturity": "prototype",
                                                  "technology_id": t["id"], "source_url": "https://arxiv.org/abs/1"}).json()
    assert d["reliability"] in ("alta", "media") and d["origin"] == "manual"  # misma heurística que el Research Engine
    r = client.post("/api/lab/discoveries/papers", json={"query": "humanoid robots", "category": "robotics", "technology_id": t["id"]}).json()
    assert r["added"] == 2 and r["errors"] == []
    again = client.post("/api/lab/discoveries/papers", json={"query": "humanoid robots", "category": "robotics"}).json()
    assert again["added"] == 0  # sin duplicados
    ds = client.get("/api/lab/discoveries", params={"technology_id": t["id"]}).json()
    ax = next(x for x in ds if x["origin"] == "arxiv")
    assert ax["title"] == "Humanoid robots that learn" and ax["maturity"] == "academic" and ax["published_on"] == "2026-11-20" and ax["authors"] == ["A. Pérez"]
    oa = next(x for x in ds if x["origin"] == "openalex")
    assert oa["reliability"] == "alta" and "Nature Energy" in oa["source_name"] and oa["description"] == "Solid batteries"
    tl = client.get(f"/api/lab/technologies/{t['id']}/timeline").json()
    assert sum(y["total"] for y in tl["by_year"]) == 3


def test_experiments_require_verifiable_results_and_trials(client):
    e = client.post("/api/lab/experiments", json={"name": "RAG con embeddings", "hypothesis": "Mejora la precisión un 20 %", "status": "PLANNED"}).json()
    assert client.patch(f"/api/lab/experiments/{e['id']}", json={"verdict": "supported"}).status_code == 422
    assert client.patch(f"/api/lab/experiments/{e['id']}", json={"status": "COMPLETED"}).status_code == 422
    r = client.patch(f"/api/lab/experiments/{e['id']}", json={"status": "RUNNING"}).json()
    assert r["started_on"] == date.today().isoformat()
    assert client.post(f"/api/lab/experiments/{e['id']}/trials", json={"version": "v1", "outcome": "pass"}).status_code == 422
    t1 = client.post(f"/api/lab/experiments/{e['id']}/trials", json={"version": "v1", "params": {"k": 4}, "metrics": {"precision": 0.62}, "outcome": "fail"}).json()
    client.post(f"/api/lab/experiments/{e['id']}/trials", json={"version": "v2", "params": {"k": 8}, "metrics": {"precision": 0.78, "latency_ms": 420}, "outcome": "pass"})
    rep = client.post(f"/api/lab/experiments/{e['id']}/trials/{t1['id']}/repeat").json()
    assert rep["params"] == {"k": 4} and rep["metrics"] == {} and rep["outcome"] == "inconclusive"
    cmp = client.get(f"/api/lab/experiments/{e['id']}/trials").json()
    assert cmp["metric_keys"] == ["latency_ms", "precision"] and [c["precision"] for c in cmp["comparison"]] == [0.62, 0.78, None]
    done = client.patch(f"/api/lab/experiments/{e['id']}", json={"status": "COMPLETED", "observed": "v2 sube la precisión a 0,78",
                                                                 "evidence": "Pruebas v1 y v2 registradas", "verdict": "supported", "hours": 3}).json()
    assert done["verdict"] == "supported" and done["finished_on"]
    a = client.get("/api/lab/analytics").json()
    assert a["experiments"] == 1 and a["experiments_supported"] == 1 and a["hours"] == 3


def test_arena_only_configured_models_and_real_metrics(client, ollama):
    models = client.get("/api/lab/arena/models").json()
    ids = [m["id"] for m in models]
    assert ids and all(m.startswith("ollama:") for m in ids)  # sin claves de nube: solo modelos locales reales
    s = client.post("/api/lab/arena/suites", json={"name": "Básico", "tests": [{"prompt": "Capital de Francia", "check": "contains", "expected": "París"}]})
    assert client.post("/api/lab/arena/suites", json={"name": "Mal", "tests": [{"prompt": "x", "check": "exact"}]}).status_code == 422
    sid = s.json()["id"]
    assert client.post("/api/lab/arena/runs", json={"suite_id": sid, "models": ["openai:gpt-x"]}).status_code == 422
    run = client.post("/api/lab/arena/runs", json={"suite_id": sid, "models": [ids[0]]}).json()[0]
    arena.run_suite(run["id"])  # ejecución síncrona para la prueba
    got = client.get("/api/lab/arena/runs", params={"suite_id": sid}).json()[0]
    assert got["status"] in ("done", "error")
    res = got["results"][0]
    assert isinstance(res["latency_ms"], int) and res["cost_usd"] is None  # sin precio configurado: no se inventa coste
    assert got["summary"]["tests"] == 1 and got["summary"]["reliability_pct"] in (0.0, 100.0)


def test_sandbox_isolation_and_confirmation(client):
    assert client.post("/api/lab/sandbox/run", json={"code": "print(1)"}).status_code == 428  # exige confirmación
    ok = client.post("/api/lab/sandbox/run", json={"code": "print(sum(range(5)))", "confirm": True}).json()
    assert ok["status"] == "ok" and ok["stdout"].strip() == "10"
    net = sandbox.run_python("import socket\nsocket.create_connection(('example.com', 80))")
    assert net["status"] == "error" and "Bloqueado" in net["stderr"]
    fs = sandbox.run_python("open('/etc/hosts').read()")
    assert "Solo se puede leer/escribir" in fs["stderr"]
    env = sandbox.run_python("import os\nprint(sorted(os.environ))")
    assert "ATLAS" not in env["stdout"] and "KEY" not in env["stdout"]
    assert sandbox.run_python("import os\nos.system('id')")["status"] == "error"
    assert sandbox.run_python("import _io")["status"] == "blocked"
    assert sandbox.run_python("while True:\n    pass")["status"] in ("timeout", "limit", "error")


def test_library_rag_ideas_conversion_and_links(client, ollama):
    it = client.post("/api/lab/library", json={"kind": "paper", "title": "Attention Is All You Need", "authors": ["Vaswani et al."],
                                               "url": "https://arxiv.org/abs/1706.03762", "origin": "external", "category": "ai", "tags": ["transformers"],
                                               "summary": "Propone el Transformer, basado solo en mecanismos de atención, sin recurrencia ni convoluciones."}).json()
    short = client.post("/api/lab/library", json={"kind": "note", "title": "Idea suelta", "summary": "corto"}).json()
    assert client.post(f"/api/lab/library/{short['id']}/extract").status_code == 422  # sin texto suficiente: no se inventa
    ollama.json_reply = {"resumen": "Propone el Transformer.", "conceptos": ["atención", "Transformer"]}
    assert client.post(f"/api/lab/library/{it['id']}/extract").json()["concepts"] == ["atención", "Transformer"]
    doc = client.post(f"/api/lab/library/{it['id']}/index").json()
    assert doc["document_id"]
    hits = client.get("/api/lab/library/search/rag", params={"q": "Transformer atención"}).json()["hits"]
    assert hits and hits[0]["title"].startswith("[Lab]")
    assert client.get("/api/lab/library", params={"q": "vaswani"}).json()[0]["id"] == it["id"]
    ollama.json_reply = {"ideas": [{"name": "Gafas que traducen", "concept": "Subtítulos en tiempo real", "problem": "Barrera del idioma",
                                    "solution": "ASR + traducción en gafas", "tech": "ASR, LLM, AR", "feasibility": "Preliminar: componentes existen",
                                    "difficulty": "alta", "cost": "5-20 k€ prototipo", "applications": "viajes", "risks": "latencia",
                                    "customers": "turistas", "next_experiment": "Medir latencia ASR+traducción en móvil"}]}
    ideas = client.post("/api/lab/ideas/generate", json={"source": "daily", "text": "No entiendo a la gente cuando viajo", "n": 1}).json()
    assert ideas[0]["origin"] == "generated" and "sin validar" in ideas[0]["label"]
    iid = ideas[0]["id"]
    exp = client.post(f"/api/lab/ideas/{iid}/convert", json={"to": "experiment"}).json()
    e = client.get("/api/lab/experiments").json()[0]
    assert e["id"] == exp["experiment_id"] and e["methodology"] == "Medir latencia ASR+traducción en móvil" and e["idea_id"] == iid
    opp = client.post(f"/api/lab/ideas/{iid}/convert", json={"to": "opportunity"}).json()
    assert client.get("/api/life/opportunities").json()["items"][0]["id"] == opp["opportunity_id"]
    lk = client.post("/api/lab/links", json={"a_type": "idea", "a_id": iid, "b_type": "library", "b_id": it["id"], "note": "base técnica"}).json()
    assert client.get("/api/lab/links", params={"type": "library", "id": it["id"]}).json()[0]["other_id"] == iid
    assert lk["note"] == "base técnica"
    a = client.get("/api/lab/analytics").json()
    assert a["ideas"] == 1 and a["ideas_generated"] == 1 and a["ideas_converted"] == 1


def test_scenarios_without_research_have_no_facts_and_patents(client, ollama, monkeypatch):
    ollama.json_reply = {"hechos": [{"texto": "Inventado", "fuente": "x"}], "hipotesis": ["Los agentes harán tareas administrativas"],
                         "escenarios": [{"nombre": "Adopción rápida", "probabilidad_cualitativa": "media"}], "predicciones": ["Más demanda de supervisión"]}
    s = client.post("/api/lab/scenarios", json={"question": "¿Cómo cambiará el trabajo con los agentes autónomos?", "horizon": "5 años"}).json()
    assert s["grounded"] is False and s["result"]["hechos"] == [] and s["result"]["hipotesis"]
    r = client.get("/api/lab/patents/search", params={"q": "smart glasses translation"}).json()
    assert r["items"] == [] and "Espacenet" in r["error"] and r["links"]["google_patents"].startswith("https://patents.google.com/?q=")
    own = client.post("/api/lab/patents", json={"kind": "own", "title": "Gafas traductoras", "status": "idea"}).json()
    assert own["kind"] == "own"
    monkeypatch.setattr(src, "epo_configured", lambda: True)
    monkeypatch.setattr(src, "epo_search", lambda q, n: [{"title": "Translating glasses", "number": "EP1234567A1", "office": "EP", "applicants": ["ACME"],
                                                         "abstract": "…", "published": "2025-01-02", "url": "https://worldwide.espacenet.com/x", "source": "EPO OPS"}])
    r = client.get("/api/lab/patents/search", params={"q": "glasses"}).json()
    assert r["items"][0]["number"] == "EP1234567A1" and "agente de la propiedad industrial" in r["legal"]


def test_projects_workflows_agent_and_command(client, ollama):
    e = client.post("/api/lab/experiments", json={"name": "Probar agente multiagente", "objective": "Medir calidad",
                                                  "methodology": "Definir 10 tareas\nEjecutar con 2 configuraciones"}).json()
    pid = client.post("/api/lab/projects", json={"kind": "experiment", "id": e["id"]}).json()["project_id"]
    lp = client.get("/api/lab/projects").json()[0]
    assert lp["project_id"] == pid and lp["tasks"] == 2 and lp["origin_type"] == "experiment" and lp["agents"] == ["innovation"]
    assert client.patch(f"/api/lab/projects/{pid}", json={"budget": 200, "owner": "Lance"}).json()["budget"] == 200
    w = client.post("/api/lab/workflows/lab_report").json()
    assert w["enabled"] is False  # se instala desactivada: la activas tú
    assert client.post("/api/lab/workflows/lab_report").status_code == 409
    run = client.post(f"/api/workflows/{w['id']}/run", json={"params": {}}).json()
    from atlas.db import session_scope
    from atlas.models import WorkflowRun
    with session_scope() as db:
        out = db.get(WorkflowRun, run["id"]).output or ""
    assert "Informe semanal del laboratorio" in out or run["status"] in ("queued", "running", "done")
    assert "innovation" in plan("propón un experimento para validar esta hipótesis tecnológica")
    p = plan("diseña un prototipo de innovación con patentes")
    assert p[0] == "innovation" and len(p) >= 2  # pide ayuda a otro agente
    ollama.reply_chunks = ["Con los datos registrados no puedo concluir; propongo medir…"]
    r = client.post("/api/lab/agent", json={"question": "¿Qué experimento hago ahora?"}).json()
    assert r["answer"].startswith("Con los datos") and "lab.experiments" in r["used"]
    sys = " ".join(m["content"] for m in ollama.requests[-1]["messages"] if m["role"] == "system")
    assert "HIPÓTESIS" in sys and "patentable" in sys and "Probar agente multiagente" in sys
    cc = client.get("/api/lab/command").json()
    assert cc["counts"]["experiments"] == 1 and cc["status"]["label"] in ("activo", "en espera")
    assert client.post("/api/lab/remember", json={"text": "Transformers dominan NLP", "ref": "biblioteca"}).status_code == 201
    json.dumps(cc)


def test_campos_numericos_vacios_del_formulario(client):
    """El formulario envía null en horas/coste vacíos: se aceptan como 0 (antes daba 422)."""
    e = client.post("/api/lab/experiments", json={"name": "Latencia", "status": "IDEA", "hours": None, "cost": None})
    assert e.status_code == 201, e.text
    assert e.json()["hours"] == 0 and e.json()["cost"] == 0
    p = client.post("/api/lab/prototypes", json={"name": "Traductor v0", "kind": "app", "status": "concept", "hours": None, "cost": None})
    assert p.status_code == 201, p.text
    assert client.post("/api/lab/experiments", json={"name": "X2", "hours": -1}).status_code == 422
