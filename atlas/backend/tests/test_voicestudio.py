"""VoiceStudio: estado real, síntesis por proxy y «no disponible» si no está abierto."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from atlas.config import get_settings


class _Fake(BaseHTTPRequestHandler):
    bodies: list = []

    def log_message(self, *a):  # silencio
        pass

    def _send(self, code, ctype, data: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/.well-known/voicestudio-speech":
            self._send(200, "application/json", json.dumps({"protocol": "voicestudio.speech.v1"}).encode())
        elif self.path == "/v1/audio/voices":
            self._send(200, "application/json", json.dumps({"voices": [
                {"voice_id": "alloy", "name": "Alloy", "type": "openai_alias"},
                {"voice_id": "p1", "name": "Mi voz", "type": "profile", "language": "es"}]}).encode())
        else:
            self._send(404, "application/json", b"{}")

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Fake.bodies.append(body)
        if body["input"] == "fallo":
            self._send(400, "application/json", json.dumps({"error": {"message": "voz desconocida"}}).encode())
        else:
            self._send(200, "audio/mpeg", b"ID3fake-mp3")


@pytest.fixture()
def fake_vs(client, monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("ATLAS_VOICESTUDIO_URL", f"http://127.0.0.1:{srv.server_port}")
    get_settings.cache_clear()
    _Fake.bodies.clear()
    yield _Fake
    srv.shutdown()
    get_settings.cache_clear()


def test_status_unavailable_is_honest(client):
    r = client.get("/api/voicestudio/status").json()
    assert r["reachable"] is False and r["ping_ms"] is None and r["voices"] == [] and r["local"] is True
    assert client.post("/api/voicestudio/speak", json={"text": "hola"}).status_code == 503
    conns = {c["name"]: c for c in client.get("/api/telemetry").json()["connections"]}
    assert conns["VoiceStudio (voz)"]["state"] == "off"


def test_status_and_speak_through_voicestudio(client, fake_vs):
    st = client.get("/api/voicestudio/status").json()
    assert st["reachable"] and st["protocol"] == "voicestudio.speech.v1" and isinstance(st["ping_ms"], int)
    assert [v["id"] for v in st["voices"]] == ["alloy", "p1"]
    r = client.post("/api/voicestudio/speak", json={"text": "Hola, soy VISTAN", "voice": "p1", "speed": 1.2})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3fake-mp3"
    assert r.headers["cache-control"] == "no-store"
    assert fake_vs.bodies[-1] == {"input": "Hola, soy VISTAN", "voice": "p1", "response_format": "mp3", "speed": 1.2, "language": "es"}
    bad = client.post("/api/voicestudio/speak", json={"text": "fallo"})
    assert bad.status_code == 503 and "voz desconocida" in bad.json()["detail"]
    assert client.post("/api/voicestudio/speak", json={"text": ""}).status_code == 422
    conns = {c["name"]: c for c in client.get("/api/telemetry").json()["connections"]}
    assert conns["VoiceStudio (voz)"]["state"] == "ok" and "2 voces" in conns["VoiceStudio (voz)"]["detail"]
