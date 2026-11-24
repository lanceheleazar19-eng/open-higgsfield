from datetime import date, datetime, timedelta

from atlas.models import CalendarEvent, Task, Transaction, WorkoutSession
from atlas.services.alerts import build_alerts
from atlas.services.assistant import answer
from atlas.services.clock import local_to_utc_naive
from atlas.services.dashboard import build_dashboard
from atlas.services.preferences import get_prefs
from zoneinfo import ZoneInfo

NOW = datetime(2026, 11, 23, 10, 0, tzinfo=ZoneInfo("Europe/Madrid"))


def _d(session):
    d = build_dashboard(session, get_prefs(session), now=NOW)
    d["alerts"] = build_alerts(d)
    return d


def test_empty_answers_are_honest(client):
    r = client.post("/api/assistant/query", json={"text": "¿Qué tengo pendiente hoy?"}).json()
    assert r == {"intent": "tasks", "mode": "local", "reply": "No tienes tareas pendientes registradas."}
    r = client.post("/api/assistant/query", json={"text": "¿Cuánto he gastado este mes?"}).json()
    assert "no puedo darte cifras" in r["reply"]
    r = client.post("/api/assistant/query", json={"text": "¿Quién ganó el mundial de 1998?"}).json()
    assert r["intent"] == "unknown" and "sin un modelo de IA" in r["reply"]


def test_query_validation(client):
    assert client.post("/api/assistant/query", json={"text": ""}).status_code == 422


def test_briefing_endpoint(client):
    client.put("/api/settings", json={"user_name": "Lance"})
    r = client.get("/api/assistant/briefing").json()
    assert ", Lance. Resumen ejecutivo:" in r["reply"]
    assert "Finanzas: sin movimientos registrados" in r["reply"]


def test_answers_and_alerts_use_real_data(session):
    u = local_to_utc_naive
    session.add_all([
        Task(title="Pagar seguro", priority="high", due_at=u(NOW - timedelta(days=1))),
        Task(title="Llamar gestor", priority="critical", due_at=u(NOW.replace(hour=18))),
        CalendarEvent(title="Reunión socio", start_at=u(NOW + timedelta(minutes=45))),
        Transaction(kind="income", amount_cents=100000, occurred_on=date(2026, 11, 1)),
        Transaction(kind="expense", amount_cents=150050, occurred_on=date(2026, 11, 2), category="Viajes"),
        WorkoutSession(performed_on=date(2026, 11, 10), routine_name="Pierna"),
    ])
    session.commit()
    d = _d(session)
    texts = [a["text"] for a in d["alerts"]]
    assert "1 tarea atrasada." in texts
    assert "1 tarea vence hoy." in texts
    assert "«Reunión socio» empieza en 45 min." in texts
    assert "Este mes los gastos superan a los ingresos registrados." in texts
    assert "Sin entrenos en 7 días (último: 2026-11-10)." in texts

    assert answer("que es prioritario", d)["reply"] == "Prioritarias: Llamar gestor (crítica); Pagar seguro (alta)."
    fin = answer("¿cuánto he gastado?", d)["reply"]
    assert "gastos 1.500,50 €" in fin and "neto -500,50 €" in fin and "Viajes" in fin
    assert "Reunión socio — 23/11 a las 10:45" in answer("próximos eventos", d)["reply"]
    assert answer("Buenos días, ATLAS", d)["intent"] == "briefing"


def test_welcome_uses_real_data(client):
    client.put("/api/settings", json={"user_name": "Lance"})
    r = client.get("/api/assistant/welcome").json()["reply"]
    assert ", Lance. Bienvenido de nuevo." in r and "No tienes tareas pendientes." in r
    client.post("/api/tasks", json={"title": "Algo", "due_date": "2000-01-01"})
    r2 = client.get("/api/assistant/welcome").json()["reply"]
    assert "Tienes 1 tarea pendiente, 1 atrasada." in r2 and r2.endswith("¿En qué te ayudo?")
