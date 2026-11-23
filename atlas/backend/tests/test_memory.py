import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from atlas.models import ConversationMessage
from atlas.services import memory as mem

TZ = "Europe/Madrid"


def _events(resp):
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def _chat(client, text, cid=None):
    body = {"text": text, **({"conversation_id": cid} if cid else {})}
    return _events(client.post("/api/assistant/chat", json=body))


# ---------- lenguaje natural ----------

def test_parse_command_variants():
    assert mem.parse_command("ATLAS, recuerda que prefiero entrenar por la mañana") == (
        "remember", "Prefiero entrenar por la mañana")
    assert mem.parse_command("Recuerda: mi objetivo es ahorrar 5000 €")[0] == "remember"
    assert mem.parse_command("no olvides que el viernes viene mi madre")[1] == "El viernes viene mi madre"
    assert mem.parse_command("olvida que prefiero entrenar por la mañana")[0] == "forget"
    assert mem.parse_command("¿Recuerdas qué decidimos?") is None
    assert mem.parse_command("recuérdame llamar a Juan") is None  # recordatorio (tareas, Fase 4), no memoria


def test_guess_kind_and_expiry():
    assert mem.guess_kind("Prefiero el café sin azúcar") == "preference"
    assert mem.guess_kind("Mi objetivo es correr una maratón") == "goal"
    assert mem.guess_kind("Hemos decidido lanzar la tienda en enero") == "decision"
    assert mem.guess_kind("Trabajo en una consultora") == "fact"
    monday = date(2026, 11, 23)
    week_end = mem.guess_expiry("Esta semana estoy de viaje", TZ, today=monday)
    assert week_end == datetime(2026, 11, 29, 23, 0)  # domingo 24:00 en Madrid = 23:00 UTC
    assert mem.guess_expiry("Hoy tengo médico", TZ, today=monday) == datetime(2026, 11, 23, 23, 0)
    assert mem.guess_expiry("Me encanta el sushi", TZ, today=monday) is None
    since, until = mem.time_window("¿qué decidimos la semana pasada?", TZ, today=monday)
    assert since == datetime(2026, 11, 15, 23, 0) and until == datetime(2026, 11, 22, 23, 0)


# ---------- CRUD, duplicados, búsqueda ----------

def test_crud_dedup_and_accent_insensitive_search(client):
    r = client.post("/api/memory", json={"content": "Prefiero entrenar por la mañana", "kind": "preference"})
    assert r.status_code == 201 and r.json()["created"] is True
    mid = r.json()["memory"]["id"]
    # mismo contenido con otras mayúsculas/tildes/puntuación → no se duplica
    r2 = client.post("/api/memory", json={"content": "prefiero entrenar por la manana."})
    assert r2.status_code == 200 and r2.json()["created"] is False and r2.json()["memory"]["id"] == mid
    # casi idéntico → tampoco
    assert client.post("/api/memory", json={"content": "Prefiero entrenar por las mañanas"}).json()["created"] is False
    client.post("/api/memory", json={"content": "Mi objetivo es ahorrar 5000 euros este año", "kind": "goal"})
    # búsqueda sin tildes y por prefijo
    hits = client.get("/api/memory", params={"q": "mañanas entrenamiento"}).json()["items"]
    assert [h["id"] for h in hits] == [mid]
    assert client.get("/api/memory", params={"q": "ahorro"}).json()["items"][0]["kind"] == "goal"
    # editar y borrar
    p = client.patch(f"/api/memory/{mid}", json={"content": "Prefiero entrenar por la tarde"})
    assert p.json()["content"] == "Prefiero entrenar por la tarde"
    assert client.get("/api/memory", params={"q": "tarde"}).json()["items"][0]["id"] == mid  # índice FTS actualizado
    assert client.delete(f"/api/memory/{mid}").status_code == 204
    assert client.get("/api/memory", params={"q": "tarde"}).json()["items"] == []
    acts = [a["summary"] for a in client.get("/api/dashboard").json()["activity"]["items"]]
    assert any(a.startswith("Memoria eliminada") for a in acts)


def test_edit_to_duplicate_conflicts(client):
    a = client.post("/api/memory", json={"content": "Vivo en Madrid"}).json()["memory"]["id"]
    client.post("/api/memory", json={"content": "Trabajo como ingeniero"})
    assert client.patch(f"/api/memory/{a}", json={"content": "Trabajo como ingeniero"}).status_code == 409


def test_temporary_memories_expire_and_purge(client):
    past = (datetime.now(ZoneInfo(TZ)) - timedelta(hours=1)).isoformat()
    future = (datetime.now(ZoneInfo(TZ)) + timedelta(days=2)).isoformat()
    client.post("/api/memory", json={"content": "Estoy de viaje en Lisboa", "expires_at": past})
    client.post("/api/memory", json={"content": "Esta semana tengo exámenes", "expires_at": future})
    active = client.get("/api/memory").json()
    assert [m["content"] for m in active["items"]] == ["Esta semana tengo exámenes"] and active["memories"] == 1
    allm = client.get("/api/memory", params={"include_expired": True}).json()["items"]
    assert sorted(m["expired"] for m in allm) == [False, True]
    assert client.post("/api/memory/purge-expired").json() == {"deleted": 1}
    mid = client.get("/api/memory").json()["items"][0]["id"]
    assert client.patch(f"/api/memory/{mid}", json={"permanent": True}).json()["permanent"] is True


def test_naive_expiry_rejected(client):
    r = client.post("/api/memory", json={"content": "x algo", "expires_at": "2030-01-01T10:00:00"})
    assert r.status_code == 422


# ---------- chat: órdenes, persistencia, contexto ----------

def test_remember_and_forget_through_chat(client):
    ev = _chat(client, "ATLAS, recuerda que prefiero entrenar por la mañana")
    cid = ev[0]["conversation_id"]
    saved = next(e for e in ev if e["type"] == "memory")
    assert saved["action"] == "saved" and saved["memory"]["kind"] == "preference"
    assert "Lo recordaré" in "".join(e.get("text", "") for e in ev)
    assert ev[-1]["mode"] == "memory"
    ev2 = _chat(client, "recuerda que prefiero entrenar por la mañana", cid)
    assert next(e for e in ev2 if e["type"] == "memory")["action"] == "duplicate"
    ev3 = _chat(client, "olvida que entreno por la mañana", cid)
    cand = next(e for e in ev3 if e["type"] == "memory")
    assert cand["action"] == "forget_candidate"
    assert client.get("/api/memory").json()["memories"] == 1  # no se borra sin confirmación
    client.delete(f"/api/memory/{cand['memory']['id']}")
    assert client.get("/api/memory").json()["memories"] == 0
    # la conversación quedó guardada con todos los mensajes
    conv = client.get(f"/api/conversations/{cid}").json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"] * 3


def test_temporal_remember_through_chat(client):
    ev = _chat(client, "recuerda que esta semana estoy de viaje")
    m = next(e for e in ev if e["type"] == "memory")["memory"]
    assert m["permanent"] is False and "temporal" in "".join(e.get("text", "") for e in ev)


def test_conversation_continues_and_history_comes_from_db(ollama, client):
    cid = _chat(client, "Hola, me llamo Lance y trabajo en marketing")[0]["conversation_id"]
    _chat(client, "¿Y qué me recomiendas hoy?", cid)
    req = ollama.requests[-1]
    roles = [m["role"] for m in req["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert req["messages"][1]["content"] == "Hola, me llamo Lance y trabajo en marketing"
    lst = client.get("/api/conversations").json()["items"]
    assert lst[0]["id"] == cid and lst[0]["messages"] == 4


def test_memory_and_past_conversations_reach_the_model(ollama, client, session):
    client.post("/api/memory", json={"content": "Prefiero respuestas muy breves", "kind": "preference"})
    client.post("/api/memory", json={"content": "Hemos decidido lanzar la tienda online en enero", "kind": "decision"})
    old = _chat(client, "Para la tienda online, decidimos usar Shopify y vender suplementos")[0]["conversation_id"]
    # mover ese mensaje a la semana pasada
    msg = session.query(ConversationMessage).filter_by(conversation_id=old, role="user").one()
    since, until = mem.time_window("la semana pasada", TZ)
    msg.created_at = since + (until - since) / 2
    session.commit()
    _chat(client, "¿Qué decidimos sobre la tienda online la semana pasada?")
    system = ollama.requests[-1]["messages"][0]["content"]
    assert "MEMORIA DE ATLAS" in system
    assert "Prefiero respuestas muy breves" in system  # perfil siempre presente
    assert "lanzar la tienda online en enero" in system  # recuerdo relevante
    assert "decidimos usar Shopify" in system  # conversación anterior encontrada


def test_local_mode_answers_from_memory(client):
    client.post("/api/memory", json={"content": "Hemos decidido lanzar la tienda online en enero", "kind": "decision"})
    ev = _chat(client, "¿Qué decidimos sobre la tienda online?")
    reply = "".join(e.get("text", "") for e in ev)
    assert "lanzar la tienda online en enero" in reply and ev[-1]["mode"] == "local"


def test_suggestions_are_proposed_not_saved(ollama, client):
    client.post("/api/memory", json={"content": "Vivo en Madrid"})
    ollama.json_reply = {"recuerdos": [
        {"contenido": "Quiere correr una media maratón en primavera", "tipo": "objetivo", "temporal": False},
        {"contenido": "Vive en Madrid", "tipo": "dato", "temporal": False},  # ya existe → se filtra
        {"contenido": "x", "tipo": "dato"},  # demasiado corto → se filtra
    ]}
    cid = _chat(client, "Estoy entrenando porque quiero correr una media maratón en primavera")[0]["conversation_id"]
    s = client.post("/api/memory/suggest", json={"conversation_id": cid}).json()["suggestions"]
    assert s == [{"content": "Quiere correr una media maratón en primavera", "kind": "goal", "temporary": False}]
    assert client.get("/api/memory").json()["memories"] == 1  # nada guardado automáticamente
    assert ollama.requests[-1]["format"] == "json"


def test_suggestions_without_ai_return_empty(client):
    cid = _chat(client, "quiero correr una maratón")[0]["conversation_id"]
    assert client.post("/api/memory/suggest", json={"conversation_id": cid}).json() == {"suggestions": []}


def test_export_and_conversation_search_and_delete(client):
    client.post("/api/memory", json={"content": "Mi color favorito es el azul"})
    cid = _chat(client, "Estoy pensando en abrir una cafetería")[0]["conversation_id"]
    hits = client.get("/api/conversations", params={"q": "cafeteria"}).json()["hits"]
    assert hits and hits[0]["conversation_id"] == cid
    r = client.get("/api/memory/export")
    assert "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["recuerdos"][0]["content"] == "Mi color favorito es el azul" and data["conversaciones"][0]["id"] == cid
    assert client.delete(f"/api/conversations/{cid}").status_code == 204
    assert client.get(f"/api/conversations/{cid}").status_code == 404
    h = client.get("/api/system/health").json()["storage"]
    assert h["memories"] == 1 and h["conversations"] == 0
