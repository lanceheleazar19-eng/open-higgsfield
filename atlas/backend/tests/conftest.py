import pytest
from fastapi.testclient import TestClient

from atlas import db as atlas_db
from atlas.config import get_settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ATLAS_TIMEZONE", "Europe/Madrid")
    monkeypatch.setenv("ATLAS_FRONTEND_DIST", str(tmp_path / "no-dist"))
    # Por defecto, sin Ollama (puerto cerrado). Los tests de IA usan fake_ollama.
    monkeypatch.setenv("ATLAS_OLLAMA_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("ATLAS_NO_KEYRING", "1")  # nunca tocar el llavero real en pruebas
    get_settings.cache_clear()
    atlas_db.reset_engine()
    from atlas.main import create_app

    with TestClient(create_app()) as c:
        yield c
    atlas_db.reset_engine()
    get_settings.cache_clear()


@pytest.fixture()
def session(client):
    gen = atlas_db.get_session()
    s = next(gen)
    yield s
    s.close()


@pytest.fixture()
def ollama(client, monkeypatch):
    """Servidor Ollama falso con el protocolo real (NDJSON). Apunta VISTAN a él."""
    from tests.fake_ollama import FakeOllama

    fake = FakeOllama()
    fake.start()
    monkeypatch.setenv("ATLAS_OLLAMA_URL", fake.url)
    get_settings.cache_clear()
    yield fake
    fake.stop()
