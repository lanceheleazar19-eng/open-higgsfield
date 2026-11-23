import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from atlas.models import Task
from atlas.services.clock import local_to_utc_naive
from atlas.services.nlp import parse_complete_command, parse_task_command
from atlas.services.tasks import plan_week, summary

TZ = "Europe/Madrid"
MON = datetime(2026, 11, 23, 10, 0)  # lunes 10:00 (local)


@pytest.mark.parametrize("text,title,due,all_day,prio,rem", [
    ("Apúntame llamar al gestor el viernes a las 10, es urgente", "Llamar al gestor", datetime(2026, 11, 27, 10), False, "critical", True),
    ("recuérdame comprar leche mañana", "Comprar leche", datetime(2026, 11, 24, 23, 59, 59), True, "medium", True),
    ("añade tarea revisar presupuesto #finanzas el 5 de diciembre importante", "Revisar presupuesto", datetime(2026, 12, 5, 23, 59, 59), True, "high", False),
    ("nueva tarea: preparar presentación para el cliente en 3 días", "Preparar presentación para el cliente", datetime(2026, 11, 26, 23, 59, 59), True, "medium", False),
    ("recuérdame sacar al perro a las 6 de la tarde", "Sacar al perro", datetime(2026, 11, 23, 18), False, "medium", True),
    ("apúntame entrenar pierna pasado mañana por la mañana", "Entrenar pierna", datetime(2026, 11, 25, 9), False, "medium", True),
    ("ponme un recordatorio para pagar el alquiler el 1/12", "Pagar el alquiler", datetime(2026, 12, 1, 23, 59, 59), True, "medium", True),
    ("añade tarea leer el informe la semana que viene sin prisa", "Leer el informe", datetime(2026, 11, 30, 23, 59, 59), True, "low", False),
    ("apúntame llamar a mamá esta noche", "Llamar a mamá", datetime(2026, 11, 23, 21), False, "medium", True),
    ("recuérdame la reunión del lunes que viene a las 9:30", "La reunión", datetime(2026, 11, 30, 9, 30), False, "medium", True),
    ("apúntame revisar el correo a las 10", "Revisar el correo", datetime(2026, 11, 24, 10), False, "medium", True),  # ya pasó hoy
    ("anótame comprar regalo el sábado", "Comprar regalo", datetime(2026, 11, 28, 23, 59, 59), True, "medium", False),
    ("apúntame estudiar inglés", "Estudiar inglés", None, False, "medium", False),
])
def test_parse_task_command(text, title, due, all_day, prio, rem):
    p = parse_task_command(text, MON)
    assert (p.title, p.due, p.all_day, p.priority, p.reminder) == (title, due, all_day, prio, rem)


def test_non_commands_are_not_tasks():
    assert parse_task_command("tengo que pensar en mi vida", MON) is None
    assert parse_task_command("¿qué tareas tengo?", MON) is None
    assert parse_task_command("recuerda que prefiero café", MON) is None  # memoria, no tarea
    assert parse_complete_command("he terminado la tarea de llamar al gestor") == "llamar al gestor"
    assert parse_complete_command("qué tal estás") is None


def test_crud_complete_reopen_and_filters(client):
    r = client.post("/api/tasks", json={"title": "Preparar informe", "priority": "high", "due_date": "2030-01-10", "category": "trabajo"})
    assert r.status_code == 201
    t = r.json()
    assert t["all_day"] is True and t["due_date"] == "2030-01-10" and t["overdue"] is False
    client.post("/api/tasks", json={"title": "Comprar pan", "priority": "low"})
    lst = client.get("/api/tasks").json()
    assert [x["title"] for x in lst["items"]] == ["Preparar informe", "Comprar pan"] and lst["categories"] == ["trabajo"]
    assert client.post(f"/api/tasks/{t['id']}/complete").json()["status"] == "done"
    assert [x["title"] for x in client.get("/api/tasks", params={"status": "done"}).json()["items"]] == ["Preparar informe"]
    assert client.post(f"/api/tasks/{t['id']}/reopen").json()["completed_at"] is None
    p = client.patch(f"/api/tasks/{t['id']}", json={"title": "Informe Q4", "due_at": "2030-01-10T12:30:00+01:00"}).json()
    assert p["title"] == "Informe Q4" and p["all_day"] is False and p["due_at"].startswith("2030-01-10T12:30")
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 204
    assert client.patch("/api/tasks/999", json={"title": "x"}).status_code == 404
    acts = [a["summary"] for a in client.get("/api/dashboard").json()["activity"]["items"]]
    assert "Tarea completada: Preparar informe" in acts and "Tarea eliminada: Informe Q4" in acts


def test_all_day_task_due_today_is_not_overdue(client):
    today = datetime.now(ZoneInfo(TZ)).date().isoformat()
    t = client.post("/api/tasks", json={"title": "Hoy sin hora", "due_date": today}).json()
    assert t["overdue"] is False
    d = client.get("/api/dashboard").json()
    assert d["tasks"]["overdue"] == 0 and d["tasks"]["due_today"] == 1


def test_quick_add_and_parse_preview(client):
    prev = client.post("/api/tasks/parse", json={"text": "llamar al banco mañana a las 9 importante"}).json()
    assert prev["title"] == "Llamar al banco" and prev["priority"] == "high" and prev["due_local"].endswith("09:00:00")
    t = client.post("/api/tasks/quick", json={"text": "llamar al banco mañana a las 9 importante"}).json()
    assert t["title"] == "Llamar al banco" and t["reminder_at"] is not None


def test_reminders_fire_once(client, session):
    t = Task(title="Avisar", reminder_at=datetime.utcnow() - timedelta(minutes=1))
    session.add_all([t, Task(title="Futuro", reminder_at=datetime.utcnow() + timedelta(hours=1))])
    session.commit()
    assert [x["title"] for x in client.get("/api/tasks/reminders/due").json()["items"]] == ["Avisar"]
    assert client.get("/api/tasks/reminders/due").json()["items"] == []  # ya avisado


def test_weekly_plan_and_apply(session, client):
    now_local = datetime(2026, 11, 23, 10, 0, tzinfo=ZoneInfo(TZ))
    u = lambda dt: local_to_utc_naive(dt.replace(tzinfo=ZoneInfo(TZ)))  # noqa: E731
    session.add_all([
        Task(title="Atrasada", priority="medium", due_at=u(datetime(2026, 11, 20, 12))),
        Task(title="Jueves fija", priority="low", due_at=u(datetime(2026, 11, 26, 23, 59, 59)), all_day=True),
        *[Task(title=f"Sin fecha {i}", priority="high") for i in range(5)],
        Task(title="Baja sin fecha", priority="low"),
        Task(title="Lejana", due_at=u(datetime(2026, 12, 20, 10))),
    ])
    session.commit()
    plan = plan_week(session, TZ, per_day=3, now_local=now_local)
    days = {x["date"]: [t["title"] for t in x["tasks"]] for x in plan["days"]}
    assert days["2026-11-23"][0] == "Atrasada" and len(days["2026-11-23"]) == 3
    assert "Jueves fija" in days["2026-11-26"]
    assert sum(len(v) for v in days.values()) == 7  # atrasada + jueves + 5 sin fecha
    assert [t["title"] for t in plan["if_time"]] == ["Baja sin fecha"]
    assert [t["title"] for t in plan["later"]] == ["Lejana"]
    # aplicar: fija fecha solo a las que no tenían
    assign = [{"task_id": t["id"], "date": x["date"]} for x in plan["days"] for t in x["tasks"]]
    assert client.post("/api/tasks/plan/apply", json={"assignments": assign}).json() == {"scheduled": 5}


def test_daily_summary(session):
    now_local = datetime(2026, 11, 23, 20, 0, tzinfo=ZoneInfo(TZ))
    u = lambda dt: local_to_utc_naive(dt.replace(tzinfo=ZoneInfo(TZ)))  # noqa: E731
    session.add_all([
        Task(title="Hecha", status="done", due_at=u(datetime(2026, 11, 23, 12)), completed_at=u(datetime(2026, 11, 23, 11)),
             created_at=u(datetime(2026, 11, 23, 9))),
        Task(title="Pendiente hoy", due_at=u(datetime(2026, 11, 23, 22)), created_at=u(datetime(2026, 11, 22, 9))),
    ])
    session.commit()
    s = summary(session, TZ, "day", now_local=now_local)
    assert s["completed"] == 1 and s["completed_titles"] == ["Hecha"] and s["due"] == 2 and s["completion_rate"] == 0.5
    assert s["created"] == 1 and s["due_open"] == 1


def _events(resp):
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def test_chat_creates_and_completes_tasks(client):
    ev = _events(client.post("/api/assistant/chat", json={"text": "Apúntame llamar al gestor el viernes a las 10, es urgente"}))
    created = next(e for e in ev if e["type"] == "task")
    assert created["action"] == "created" and created["task"]["priority"] == "critical"
    reply = "".join(e.get("text", "") for e in ev)
    assert reply.startswith("Apuntado: «Llamar al gestor» para el viernes") and "Te avisaré" in reply
    assert ev[-1]["mode"] == "tasks"
    ev2 = _events(client.post("/api/assistant/chat", json={"text": "he terminado lo de llamar al gestor"}))
    cand = next(e for e in ev2 if e["type"] == "task")
    assert cand["action"] == "complete_candidate" and cand["task"]["status"] == "pending"  # no se completa sin confirmar
    ev3 = _events(client.post("/api/assistant/chat", json={"text": "he terminado de pintar la valla"}))
    assert next(e for e in ev3 if e["type"] == "task")["action"] == "not_found"


def test_local_mode_plans_week(client):
    client.post("/api/tasks", json={"title": "Preparar oferta", "priority": "high"})
    ev = _events(client.post("/api/assistant/chat", json={"text": "Organízame la semana"}))
    assert "Preparar oferta" in "".join(e.get("text", "") for e in ev)
