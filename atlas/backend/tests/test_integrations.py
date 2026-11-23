import json
import os
from datetime import datetime, timedelta

from atlas.integrations import calendar_sync, email_sync
from atlas.models import CalendarEvent

RAW = lambda sender, subject, body="", extra="": (  # noqa: E731
    f"From: {sender}\r\nSubject: {subject}\r\nDate: {datetime.utcnow():%a, %d %b %Y %H:%M:%S} +0000\r\n"
    f"Message-ID: <{abs(hash(subject))}@x>\r\n{extra}Content-Type: text/plain; charset=utf-8\r\n\r\n{body}").encode()


def _msgs():
    return [
        email_sync.parse_message(RAW("Banco X <avisos@bancox.es>", "Tu pago de la tarjeta vence el viernes", "Importe 45 €"), "(\\Important)"),
        email_sync.parse_message(RAW("Tienda <newsletter@tienda.com>", "¡Rebajas del 50%!", "", "List-Unsubscribe: <mailto:u@t.com>\r\n")),
        email_sync.parse_message(RAW("Profesora Ana <ana@instituto.es>", "Entrega de la práctica 7", "Recuerda entregarla el lunes")),
        email_sync.parse_message(RAW("Amigo <pepe@gmail.com>", "¿Quedamos?", "")),
    ]


def test_parse_and_rules():
    m = _msgs()
    assert m[0]["gmail_important"] and m[0]["subject"].startswith("Tu pago")
    assert email_sync.rule_score(m[0])[0] is True
    assert email_sync.rule_score(m[1])[0] is False
    assert email_sync.rule_score(m[2])[0] is None  # dudoso: palabra clave → IA (o aviso si no hay IA)
    assert email_sync.rule_score(m[3])[0] is False


def _connect_gmail(client, monkeypatch, msgs):
    monkeypatch.setattr(email_sync, "fetch_recent", lambda *a, **k: msgs)
    return client.post("/api/integrations/gmail", json={"user": "Yo@Gmail.com", "app_password": "abcd efgh ijkl mnop"})


def test_gmail_connect_sync_and_secret_storage(client, monkeypatch, tmp_path):
    r = _connect_gmail(client, monkeypatch, _msgs())
    assert r.status_code == 200 and r.json()["gmail"]["connected"] and r.json()["gmail"]["address"] == "yo@gmail.com"
    secrets = tmp_path / "secrets.json"
    assert json.loads(secrets.read_text())["gmail_app_password"] == "abcdefghijklmnop"  # espacios eliminados
    assert oct(os.stat(secrets).st_mode & 0o777) == "0o600"  # solo el usuario
    imp = client.get("/api/email/important").json()["items"]
    assert [m["subject"] for m in imp] == ["Entrega de la práctica 7", "Tu pago de la tarjeta vence el viernes"] or \
           sorted(m["subject"] for m in imp) == ["Entrega de la práctica 7", "Tu pago de la tarjeta vence el viernes"]
    # una segunda sincronización no duplica
    assert client.post("/api/integrations/sync").json()["gmail"]["new"] == 0
    client.post(f"/api/email/{imp[0]['id']}/dismiss")
    assert len(client.get("/api/email/important").json()["items"]) == 1
    assert client.delete("/api/integrations/gmail").status_code == 204
    assert client.get("/api/integrations").json()["gmail"]["connected"] is False


def test_gmail_bad_credentials(client, monkeypatch):
    def boom(*a, **k):
        raise OSError("auth failed")
    monkeypatch.setattr(email_sync, "fetch_recent", boom)
    r = client.post("/api/integrations/gmail", json={"user": "yo@gmail.com", "app_password": "malamala1"})
    assert r.status_code == 400 and "contraseña de aplicación" in r.json()["detail"]


def test_ai_decides_doubtful_emails(ollama, client, monkeypatch):
    ollama.json_reply = {"correos": [{"id": 2, "importante": False, "motivo": "recordatorio genérico"}]}
    _connect_gmail(client, monkeypatch, _msgs())
    subjects = [m["subject"] for m in client.get("/api/email/important").json()["items"]]
    assert subjects == ["Tu pago de la tarjeta vence el viernes"]


def test_welcome_mentions_important_emails_only_if_any(client, monkeypatch):
    assert "correo" not in client.get("/api/assistant/welcome").json()["reply"]
    _connect_gmail(client, monkeypatch, _msgs()[:1])
    r = client.get("/api/assistant/welcome").json()["reply"]
    assert "Tienes 1 correo importante: de Banco X sobre «Tu pago de la tarjeta vence el viernes»." in r


def test_icloud_sync_upsert_delete_and_conflicts(client, monkeypatch, session):
    now = datetime.utcnow().replace(microsecond=0)
    evs = [{"external_id": "a@1", "title": "Clase", "location": "Aula 3", "start_at": now + timedelta(hours=2), "end_at": now + timedelta(hours=4), "all_day": False},
           {"external_id": "b@1", "title": "Dentista", "location": None, "start_at": now + timedelta(hours=3), "end_at": now + timedelta(hours=3, minutes=30), "all_day": False}]
    monkeypatch.setattr(calendar_sync, "fetch_events", lambda *a, **k: evs)
    r = client.post("/api/integrations/icloud", json={"user": "yo@icloud.com", "app_password": "aaaa-bbbb-cccc-dddd"})
    assert r.status_code == 200 and r.json()["icloud"]["connected"]
    cal = client.get("/api/calendar").json()
    assert [e["title"] for e in cal["items"]] == ["Clase", "Dentista"] and len(cal["conflicts"]) == 1
    evs[0]["title"] = "Clase de mates"
    evs.pop(1)
    client.post("/api/integrations/sync")
    assert [e["title"] for e in client.get("/api/calendar").json()["items"]] == ["Clase de mates"]
    icloud_id = client.get("/api/calendar").json()["items"][0]["id"]
    assert client.delete(f"/api/calendar/{icloud_id}").status_code == 400  # no se borra desde ATLAS


def test_local_events_and_validation(client):
    r = client.post("/api/calendar", json={"title": "Entreno", "start_at": "2030-01-10T18:00:00+01:00", "end_at": "2030-01-10T19:30:00+01:00"})
    assert r.status_code == 201 and r.json()["source"] == "local"
    assert client.post("/api/calendar", json={"title": "X", "start_at": "2030-01-10T18:00:00", "end_at": "2030-01-10T19:00:00"}).status_code == 422
    assert client.post("/api/calendar", json={"title": "X", "start_at": "2030-01-10T19:00:00+01:00", "end_at": "2030-01-10T18:00:00+01:00"}).status_code == 422
    assert client.post("/api/calendar", json={"title": "X", "start_at": "2030-01-10T18:00:00+01:00", "end_at": "2030-01-10T19:00:00+01:00", "to_icloud": True}).status_code == 400
    assert client.delete(f"/api/calendar/{r.json()['id']}").status_code == 204
