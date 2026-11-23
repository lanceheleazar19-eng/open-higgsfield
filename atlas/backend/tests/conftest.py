import pytest
from fastapi.testclient import TestClient

from atlas import db as atlas_db
from atlas.config import get_settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ATLAS_TIMEZONE", "Europe/Madrid")
    monkeypatch.setenv("ATLAS_FRONTEND_DIST", str(tmp_path / "no-dist"))
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
