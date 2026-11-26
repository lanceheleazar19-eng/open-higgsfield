"""VISTAN LEGAL con documentos FICTICIOS: expedientes, bóveda cifrada y aislada, análisis de contratos, comparación,
investigación en fuentes oficiales (red simulada), borradores sin datos inventados, plazos, alertas, cumplimiento,
informes PDF/DOCX, agente, permisos y persistencia."""

import io
import json
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

FIX = Path(__file__).parent / "fixtures"
V1 = (FIX / "contrato_ficticio_v1.txt").read_bytes()
V2 = (FIX / "contrato_ficticio_v2.txt").read_bytes()


def case(client, name="Alquiler ficticio", **kw) -> dict:
    return client.post("/api/legal/cases", json={"name": name, "category": "inmobiliario", **kw}).json()


def upload(client, data: bytes, case_id, name="contrato.txt", kind="contract") -> dict:
    return client.post("/api/legal/documents", files={"file": (name, data, "text/plain")}, data={"case_id": str(case_id), "kind": kind}).json()


def wait(fn, cond, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = fn()
        if cond(r):
            return r
        time.sleep(0.15)
    raise AssertionError(r)


def test_cases_crud_timeline_and_controlled_delete(client):
    c = case(client, parties=[{"name": "Parte ficticia A", "role": "arrendador"}])
    assert c["ref"].startswith(f"EXP-{date.today().year}-") and c["status"] == "nuevo"
    client.patch(f"/api/legal/cases/{c['id']}", json={"status": "investigacion", "priority": "alta"})
    client.post(f"/api/legal/comments?target=case&target_id={c['id']}", json={"text": "Revisar cláusula de penalización"})
    t = client.post(f"/api/legal/cases/{c['id']}/tasks", json={"title": "Pedir copia firmada"}).json()
    assert c["ref"] in t["title"]
    full = client.get(f"/api/legal/cases/{c['id']}").json()
    kinds = [e["kind"] for e in full["timeline"]]
    assert {"created", "status", "comment", "task"} <= set(kinds)
    assert client.get("/api/legal/cases?status=investigacion").json()[0]["id"] == c["id"]
    assert client.delete(f"/api/legal/cases/{c['id']}").status_code == 428  # hay que escribir el número
    assert client.delete(f"/api/legal/cases/{c['id']}?confirm={c['ref']}").status_code == 204


def test_vault_encrypted_isolated_and_dedup(client, tmp_path):
    a, b = case(client, "Expediente A"), case(client, "Expediente B")
    d = upload(client, V1, a["id"])
    assert d["created"] and d["extraction"] == "txt" and d["chars"] > 500 and d["has_original"]
    assert upload(client, V1, a["id"])["created"] is False  # duplicado en el mismo expediente
    files = list((tmp_path / "legal").glob("*.bin"))
    assert files and b"ARRENDADOR" not in files[0].read_bytes()  # cifrado en disco
    assert client.get(f"/api/legal/documents/{d['id']}/download").content == V1
    # Aislamiento: ni el gestor documental general ni su búsqueda ven la bóveda legal
    assert all(not x["title"].startswith("[Legal]") for x in client.get("/api/knowledge/documents").json())
    assert client.get(f"/api/knowledge/documents/{d['document_id']}").status_code == 404
    assert not client.get("/api/knowledge/search?q=ARRENDATARIO").json()
    assert client.get(f"/api/legal/kb/search?q=penalización mensualidades&case_id={a['id']}").json()
    assert client.get(f"/api/legal/kb/search?q=penalización mensualidades&case_id={b['id']}").json() == []  # sin fugas entre expedientes
    assert client.post("/api/legal/documents", files={"file": ("x.exe", b"MZ", "application/octet-stream")}, data={"kind": "other"}).status_code == 415
    assert client.delete(f"/api/legal/documents/{d['id']}").status_code == 428
    assert client.delete(f"/api/legal/documents/{d['id']}?confirm=true").status_code == 204
    assert not list((tmp_path / "legal").glob("*.bin"))


def test_rtf_and_odt_extraction(client):
    import zipfile
    rtf = rb"{\rtf1\ansi Contrato de prueba: el precio ser\'e1 de 100 euros.\par Segunda l\'ednea.}"
    r = client.post("/api/legal/documents", files={"file": ("a.rtf", rtf, "application/rtf")}, data={"kind": "contract"}).json()
    assert r["extraction"] == "rtf" and "será" in client.get(f"/api/legal/documents/{r['id']}").json()["text"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("content.xml", '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
                   'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><text:p>Acuerdo ficticio de colaboración</text:p>'
                   '</office:body></office:document-content>')
    r = client.post("/api/legal/documents", files={"file": ("a.odt", buf.getvalue(), "application/vnd.oasis.opendocument.text")}, data={"kind": "contract"}).json()
    assert r["extraction"] == "odt"


def test_contract_analysis_rules_ai_validation_alerts_and_reports(client, ollama):
    c = case(client)
    d = upload(client, V1, c["id"])
    ollama.json_reply = {"resumen": "Arrendamiento ficticio con cláusulas desequilibradas.", "partes": ["Inmuebles Ejemplo Ficticio S.L."],
                         "obligaciones": [{"parte": "ARRENDATARIO", "obligacion": "Pagar la renta", "plazo": "5 primeros días"}],
                         "riesgos": [{"nivel": "CRÍTICO", "clausula": "QUINTA", "fragmento": "El ARRENDADOR podrá resolver el contrato unilateralmente y sin previo aviso",
                                      "problema": "La cláusula es nula de pleno derecho", "consecuencia": "Pérdida de la vivienda", "norma": "Ley inventada 99/2099",
                                      "recomendacion": "Eliminarla", "redaccion_alternativa": "Cualquiera de las partes podrá resolver con causa y 30 días de preaviso."},
                                     {"nivel": "alto", "clausula": "NOVENA", "fragmento": "El arrendatario podrá subarrendar libremente toda la vivienda",
                                      "problema": "inventado", "recomendacion": "x"}],
                         "terminacion_y_renovacion": "Prórroga automática anual", "riesgos_economicos": ["Penalización de seis mensualidades"],
                         "informacion_ausente": ["Inventario"]}
    a = client.post(f"/api/legal/documents/{d['id']}/analyze").json()
    a = wait(lambda: client.get(f"/api/legal/analyses/{a['id']}").json(), lambda x: x["status"] in ("done", "error"))
    assert a["status"] == "done", a["error"]
    res = a["result"]
    assert res["type"] == "arrendamiento" and "900 €" in res["entities"]["amounts"]
    assert res["risks"][0]["nivel"] == "critico" and res["discarded_ai_risks"] == 1  # el fragmento inventado se descarta
    ai_risk = next(r for r in res["risks"] if r["origen"] == "ia")
    assert "nula" not in ai_risk["problema"] and ai_risk["norma_verificada"] is False  # sin afirmaciones categóricas ni normas sin verificar
    assert any(r.get("tema") == "penalización" for r in res["risks"]) and res["contradictions"]
    assert "fianza" in res["missing"]
    alerts = client.get(f"/api/legal/alerts?case_id={c['id']}").json()
    assert alerts and all("Posible" in x["title"] for x in alerts)
    assert len(client.get(f"/api/legal/alerts?case_id={c['id']}").json()) == len(alerts)
    assert client.post("/api/legal/alerts/scan").json()["new"] == 0  # sin duplicados
    pdf = client.get(f"/api/legal/reports/analysis/{a['id']}?fmt=pdf")
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    from pypdf import PdfReader
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Riesgos detectados" in text and "No es asesoramiento profesional" in text
    docx = client.get(f"/api/legal/reports/analysis/{a['id']}?fmt=docx")
    assert docx.content[:2] == b"PK" and "wordprocessingml" in docx.headers["content-type"]


def test_compare_versions_and_case_separation(client):
    c, other = case(client), case(client, "Otro")
    d1, d2 = upload(client, V1, c["id"], "v1.txt"), upload(client, V2, c["id"], "v2.txt")
    cmp_ = client.post("/api/legal/compare", json={"a_id": d1["id"], "b_id": d2["id"]}).json()
    r = cmp_["result"]
    assert r["counts"]["modificada"] >= 2 and r["summary"]["económico"] >= 1 and r["summary"]["penalizaciones"] >= 1
    renta = next(x for x in r["changes"] if "Renta" in x["clause"])
    assert "900" in renta["numbers"]["antes"] and "950" in renta["numbers"]["despues"]
    d3 = upload(client, V2, other["id"], "v2.txt")
    assert client.post("/api/legal/compare", json={"a_id": d1["id"], "b_id": d3["id"]}).status_code == 422
    assert client.get(f"/api/legal/reports/comparison/{cmp_['id']}?fmt=docx").status_code == 200


class FakeSearch:
    def duckduckgo(self, q, n=5):
        site = q.split("site:")[-1]
        return [{"url": f"https://www.{site}/buscar/act.php?id=BOE-A-1889-4763" if site == "boe.es" else f"https://www.{site}/doc-oficial",
                 "title": f"Fuente oficial {site}", "snippet": "", "engine": "DuckDuckGo"},
                {"url": "https://blog-no-oficial.example.com/opinion", "title": "Blog", "snippet": "", "engine": "DuckDuckGo"}]


def fake_fetch(url):
    if "blog-no-oficial" in url:
        raise AssertionError("no debe leer fuentes no oficiales")
    return {"text": "Código Civil (BOE-A-1889-4763). Artículo 1544. En el arrendamiento de obras o servicios, una de las partes se obliga..."}


def boe_api(request: httpx.Request) -> httpx.Response:
    if "/metadatos" in request.url.path:
        return httpx.Response(200, json={"data": [{"identificador": "BOE-A-1889-4763", "titulo": "Código Civil", "vigencia_agotada": "N",
                                                  "estatus_derogacion": "N"}]})
    return httpx.Response(200, json={"data": [{"identificador": "BOE-A-1994-26003", "titulo": "Ley de Arrendamientos Urbanos", "vigencia_agotada": "N"}]})


def test_research_official_sources_vigencia_and_citation_verification(client, ollama, session):
    from atlas.legal import research
    from atlas.models import LgResearch
    pre = client.post("/api/legal/research/precheck", json={"question": "¿Puede mi arrendador quedarse la fianza del alquiler?"}).json()
    assert pre["questions"] and "inmobiliario" in pre["branches"]  # falta saber la comunidad autónoma
    ollama.json_reply = {
        "problema": "Devolución de la fianza", "cuestiones": ["¿Qué regula la fianza?"], "busquedas": ["fianza arrendamiento"], "jurisprudencia_relevante": False,
        "relevante": True, "tipo": "legislacion", "norma_o_resolucion": "Código Civil", "articulos": ["1544"], "afirmaciones": ["Define el arrendamiento"],
        "resumen": "Resumen ficticio", "legislacion": [{"norma": "Código Civil", "articulos": ["1544", "999"], "fuente": 1, "contenido": "Arrendamiento"},
                                                         {"norma": "Ley inventada", "articulos": ["5"], "fuente": 77, "contenido": "x"}],
        "jurisprudencia": [{"resolucion": "STS inventada 1/2099", "fuente": 1, "criterio": "x"}], "criterios_interpretativos": [],
        "interpretacion": "i", "aplicacion": "a", "riesgos": ["r"], "incertidumbres": [], "conclusion": "c", "requiere_abogado": True,
        "plazos_mencionados": ["un mes"]}
    r = LgResearch(question="¿Puede mi arrendador quedarse la fianza del alquiler en Madrid?", jurisdiction="auto", state={})
    session.add(r)
    session.commit()
    research.run(r.id, searcher=FakeSearch(), fetcher=fake_fetch, http=httpx.Client(transport=httpx.MockTransport(boe_api)))
    out = client.get(f"/api/legal/research/{r.id}").json()
    assert out["status"] == "done", out["error"]
    assert all("blog-no-oficial" not in s["url"] for s in out["sources"]) and all(s["official"] for s in out["sources"])
    leg = out["report"]["legislacion"]
    cc = next(x for x in leg if x["norma"] == "Código Civil")
    assert cc["vigencia"] == "vigente" and cc["vigencia_via"] == "API BOE"
    assert cc["articulos_encontrados"] == ["1544"] and cc["articulos_no_encontrados"] == ["999"]
    fake = next(x for x in leg if x["norma"] == "Ley inventada")
    assert fake["verificada_en_fuente"] is False
    assert out["report"]["jurisprudencia"][0]["verificada_en_fuente"] is False  # la fuente es legislación, no una sentencia
    warn = " ".join(out["report"]["incertidumbres"])
    assert "no aparecen literalmente" in warn and "verificación prioritaria" in warn
    pdf = client.get(f"/api/legal/reports/research/{r.id}?fmt=pdf")
    assert pdf.content[:5] == b"%PDF-"
    saved = client.post(f"/api/legal/research/{r.id}/save").json()
    assert saved["origin"] == "ia"  # conclusión de IA, separada de los documentos originales


def test_drafts_never_invent_party_data_versions_and_export(client, ollama):
    ollama.json_reply = {"titulo": "NDA ficticio", "contenido": "ACUERDO DE CONFIDENCIALIDAD\nREUNIDOS: D. Juan Pérez García, con DNI 12345678Z, "
                         "email juan@example.com, y Empresa Ficticia S.L.\n1. Finalidad: evaluar una colaboración.\n2. Duración: [[PENDIENTE: duración]]",
                         "revisar": [{"clausula": "2", "motivo": "Duración no indicada"}]}
    g = client.post("/api/legal/drafts/generate", json={"doc_type": "nda", "jurisdiction": "es", "request": "NDA para evaluar colaboración",
                                                        "inputs": {"parte_receptora": "Empresa Ficticia S.L.", "finalidad": "evaluar una colaboración"}}).json()
    assert g["content"].startswith("BORRADOR") and "12345678Z" not in g["content"] and "Juan Pérez" not in g["content"]
    assert "juan@example.com" not in g["content"] and "Empresa Ficticia S.L." in g["content"]
    assert "DNI/NIE/CIF" in g["pending"] and "duración" in g["pending"] and "parte_reveladora" in g["missing_inputs"]
    did = g["id"]
    client.patch(f"/api/legal/drafts/{did}", json={"content": g["content"] + "\n3. Ley aplicable: española.", "tags": ["nda"]})
    client.post(f"/api/legal/drafts/{did}/versions", json={"note": "con ley aplicable"})
    d = client.get(f"/api/legal/drafts/{did}").json()
    assert len(d["versions"]) == 2 and d["tags"] == ["nda"]
    first = d["versions"][-1]["id"]
    cmpv = client.get(f"/api/legal/drafts/{did}/versions/{first}").json()["compare"]
    assert cmpv["counts"]["añadida"] + cmpv["counts"]["modificada"] >= 1
    assert "Ley aplicable" not in client.post(f"/api/legal/drafts/{did}/restore/{first}").json()["content"]
    dup = client.post(f"/api/legal/drafts/{did}/duplicate").json()
    assert dup["title"].endswith("(copia)")
    for fmt, magic in (("pdf", b"%PDF-"), ("docx", b"PK")):
        assert client.get(f"/api/legal/drafts/{did}/export?fmt={fmt}").content[:len(magic)] == magic


def test_deadlines_never_assumed_tasks_and_alerts(client):
    c = case(client)
    assert client.post("/api/legal/deadlines", json={"title": "Contestar requerimiento", "due_on": str(date.today() + timedelta(days=3)),
                                                     "kind": "administrativo", "verified": True}).status_code == 422  # sin regla/fuente
    d = client.post("/api/legal/deadlines", json={"title": "Contestar requerimiento", "due_on": str(date.today() + timedelta(days=3)),
                                                  "kind": "administrativo", "case_id": c["id"]}).json()
    assert d["warning"] and d["task_id"]
    al = client.get(f"/api/legal/alerts?case_id={c['id']}").json()
    assert al[0]["level"] == "alto" and "NO verificado" in al[0]["description"]
    assert client.get("/api/legal/dashboard").json()["deadlines"][0]["days"] == 3


def test_compliance_lists_and_shopify_integration_point(client):
    items = client.post("/api/legal/compliance/generate", json={"profile": "ecommerce"}).json()
    kinds = {i["applicability"] for i in items}
    assert kinds == {"confirmada", "potencial", "asesoramiento"}
    assert all(i["source_url"] is None or i["source_url"].startswith(("https://www.boe.es/", "https://eur-lex.europa.eu/")) for i in items)
    assert client.post("/api/legal/compliance/generate", json={"profile": "ecommerce"}).json() == []  # sin duplicados
    one = items[0]
    assert client.patch(f"/api/legal/compliance/{one['id']}", json={"status": "cumplida", "owner": "Yo", "evidence": "Aviso legal publicado"}).json()["status"] == "cumplida"
    ob = client.post("/api/legal/agent/obligations", json={"business": "Tienda Shopify de ropa ficticia", "profile": "ecommerce"}).json()
    assert ob["obligations"] and ob["professional_review"] and "Formulario de desistimiento" in ob["documents_needed"]
    assert client.get("/api/legal/reports/compliance/0?fmt=pdf").content[:5] == b"%PDF-"


def test_legal_agent_uses_only_its_case_and_vistan_core_integration(client, ollama):
    a, b = case(client, "Exp A"), case(client, "Exp B")
    upload(client, V1, a["id"])
    client.post("/api/legal/documents/text", json={"title": "Nota secreta B", "text": "Información confidencial del expediente B: código ZETA-77.", "case_id": b["id"]})
    ollama.reply_chunks = ["Según D1, la penalización es de seis mensualidades."]
    r = client.post("/api/legal/agent", json={"question": "¿Qué penalización hay?", "case_id": a["id"]}).json()
    assert "No es asesoramiento profesional" in r["answer"] and r["fragments"]
    sent = json.dumps(ollama.requests[-1], ensure_ascii=False)
    assert "ZETA-77" not in sent  # nada del expediente B
    assert client.get("/api/legal/dashboard").json()["queries"][0]["kind"] == "agent"
    from atlas.agents.core import plan
    assert "legal" in plan("revisa la cláusula de penalización de mi contrato de alquiler")
    perms = client.get("/api/meta/agents").json()
    assert next(x for x in perms["agents"] if x["id"] == "legal")["perms"]["cloud"] is False  # confidencial: solo local por defecto


def test_pin_lock_and_cloud_authorization(client):
    assert client.get("/api/legal/dashboard").status_code == 200
    assert client.put("/api/legal/settings", json={"allow_cloud": True}).json()["allow_cloud"] is True
    audit = client.get("/api/meta/governance/audit").json()["log"]
    assert any("AUTORIZADO" in x["summary"] for x in audit)
    client.put("/api/life/lock/pin", json={"pin": "4821"})
    other = TestClient(client.app)
    assert other.get("/api/legal/dashboard").status_code == 423  # mismo PIN y sesión que LIFE OS
    other.post("/api/life/lock/unlock", json={"pin": "4821"})
    assert other.get("/api/legal/dashboard").status_code == 200
