def test_defaults(client):
    prefs = client.get("/api/settings").json()
    assert prefs == {"user_name": "", "timezone": "Europe/Madrid", "currency": "EUR", "ai_model": ""}


def test_update_and_persist(client):
    r = client.put("/api/settings", json={"user_name": "  Lance ", "currency": "usd"})
    assert r.status_code == 200
    assert r.json()["user_name"] == "Lance"
    assert r.json()["currency"] == "USD"
    assert client.get("/api/settings").json()["user_name"] == "Lance"
    # queda registrado en actividad reciente
    acts = client.get("/api/dashboard").json()["activity"]["items"]
    assert acts[0]["module"] == "settings"


def test_invalid_timezone_rejected(client):
    r = client.put("/api/settings", json={"timezone": "Marte/Olimpo"})
    assert r.status_code == 422
    assert client.get("/api/settings").json()["timezone"] == "Europe/Madrid"


def test_valid_timezone(client):
    r = client.put("/api/settings", json={"timezone": "America/Mexico_City"})
    assert r.json()["timezone"] == "America/Mexico_City"
    assert "Europe/Madrid" in client.get("/api/settings/timezones").json()
