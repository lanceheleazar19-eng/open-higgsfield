"""Soporte para VISTAN Desktop: identificación del servidor, protección del backend local y una sola instancia por datos."""

import json
import os

import pytest


def test_health_identifies_vistan(client):
    r = client.get("/api/system/health")
    assert r.status_code == 200 and r.json()["app"] == "vistan"


def test_foreign_host_header_rejected(client):
    # Una web maliciosa que apunte su dominio a 127.0.0.1 (DNS rebinding) no puede hablar con VISTAN
    assert client.get("/api/system/health", headers={"Host": "evil.example.com"}).status_code == 400
    for ok in ("127.0.0.1:8001", "localhost:8000", "mi-mac.tail1234.ts.net"):
        assert client.get("/api/system/health", headers={"Host": ok}).status_code == 200, ok


def test_runtime_file_written_and_cleaned(client, monkeypatch, tmp_path):
    import atlas.__main__ as m
    monkeypatch.setenv("ATLAS_LAUNCHER", "desktop")
    m._write_runtime("127.0.0.1", 8123)
    info = json.loads(m.runtime_file().read_text())
    assert info["port"] == 8123 and info["pid"] == os.getpid() and info["launcher"] == "desktop" and info["app"] == "vistan"
    assert m._running_instance() is None  # nadie responde en ese puerto → no se considera en marcha


def test_strict_port_and_no_duplicate_instance(client, monkeypatch, capsys):
    import socket

    import atlas.__main__ as m
    ran = []
    monkeypatch.setattr(m.uvicorn, "run", lambda *a, **k: ran.append(k["port"]))
    # Ya hay un VISTAN con estos datos → no se arranca otro
    monkeypatch.setattr(m, "_running_instance", lambda: 8001)
    m.main()
    assert ran == [] and "ya está funcionando" in capsys.readouterr().out
    # Puerto estricto ocupado → error claro en vez de cambiar de puerto
    monkeypatch.setattr(m, "_running_instance", lambda: None)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        monkeypatch.setenv("ATLAS_PORT", str(port))
        monkeypatch.setenv("ATLAS_STRICT_PORT", "1")
        from atlas.config import get_settings
        get_settings.cache_clear()
        with pytest.raises(SystemExit, match="ocupado"):
            m.main()
    assert ran == []
