from atlas.modules import MODULES


def test_health_reports_online_and_ai_not_configured(client):
    r = client.get("/api/system/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "online"
    assert body["database"] == {"ok": True, "engine": "sqlite"}
    assert body["ai"]["configured"] is False


def test_modules_registry_has_all_sidebar_sections(client):
    ids = [m["id"] for m in client.get("/api/system/modules").json()]
    assert ids == ["dashboard", "ai", "tasks", "gym", "finance", "trading",
                   "projects", "calendar", "memory", "reports", "settings"]
    active = {m.id for m in MODULES if m.status == "active"}
    assert active == {"dashboard", "settings"}


def test_root_without_frontend_build(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["atlas"] == "online"


def test_migrations_create_db_file(client, tmp_path):
    assert (tmp_path / "atlas.db").exists()
