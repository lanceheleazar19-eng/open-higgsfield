from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.exc import IntegrityError

from atlas.models import CalendarEvent, Project, Task, Transaction, WorkoutSession
from atlas.services.clock import local_to_utc_naive
from atlas.services.dashboard import build_dashboard
from atlas.services.preferences import get_prefs

TZ = ZoneInfo("Europe/Madrid")


def test_empty_dashboard_has_no_invented_numbers(client):
    d = client.get("/api/dashboard").json()
    assert d["summary"] == {"pending_tasks": 0, "overdue_tasks": 0, "upcoming_events": 0,
                            "active_projects": 0, "sessions_7d": 0}
    assert d["finance"]["has_data"] is False
    assert d["finance"]["balance_cents"] == 0
    assert d["tasks"]["items"] == [] and d["events"]["items"] == []
    assert d["fitness"]["last_session"] is None
    assert len(d["fitness"]["days"]) == 7


def _now():
    return datetime(2026, 11, 23, 10, 0, tzinfo=TZ)  # lunes por la mañana


def test_tasks_priority_overdue_and_today(session):
    now = _now()
    u = lambda dt: local_to_utc_naive(dt)  # noqa: E731
    session.add_all([
        Task(title="atrasada", priority="low", due_at=u(now - timedelta(days=1))),
        Task(title="hoy tarde", priority="medium", due_at=u(now.replace(hour=20))),
        Task(title="crítica sin fecha", priority="critical"),
        Task(title="mañana", priority="high", due_at=u(now + timedelta(days=1))),
        Task(title="hecha", priority="critical", status="done"),
    ])
    session.commit()
    d = build_dashboard(session, get_prefs(session), now=now)
    t = d["tasks"]
    assert t["pending"] == 4 and t["overdue"] == 1 and t["due_today"] == 1
    assert [i["title"] for i in t["items"]] == ["crítica sin fecha", "mañana", "hoy tarde", "atrasada"]
    assert t["items"][3]["overdue"] is True
    assert d["greeting"]["part_of_day"] == "morning"


def test_finance_month_bounds_and_categories(session):
    session.add_all([
        Transaction(kind="income", amount_cents=200000, occurred_on=date(2026, 11, 1), category="Nómina"),
        Transaction(kind="expense", amount_cents=45050, occurred_on=date(2026, 11, 30), category="Vivienda"),
        Transaction(kind="expense", amount_cents=3000, occurred_on=date(2026, 11, 5), category="Ocio"),
        Transaction(kind="expense", amount_cents=99999, occurred_on=date(2026, 10, 31), category="Viajes"),
        Transaction(kind="income", amount_cents=10000, occurred_on=date(2026, 12, 1)),
    ])
    session.commit()
    f = build_dashboard(session, get_prefs(session), now=_now())["finance"]
    assert f["month"] == "2026-11"
    assert f["income_cents"] == 200000
    assert f["expense_cents"] == 48050
    assert f["net_cents"] == 151950
    assert f["balance_cents"] == 210000 - 148049
    assert [c["category"] for c in f["top_expense_categories"]] == ["Vivienda", "Ocio"]


def test_negative_amount_rejected(session):
    session.add(Transaction(kind="expense", amount_cents=-1, occurred_on=date(2026, 1, 1)))
    with pytest.raises(IntegrityError):
        session.commit()


def test_events_fitness_projects(session):
    now = _now()
    u = local_to_utc_naive
    p = Project(name="Tienda online")
    session.add_all([p, Project(name="Pausado", status="paused")])
    session.flush()
    session.add_all([
        Task(title="landing", project_id=p.id),
        Task(title="logo", project_id=p.id, status="done"),
        CalendarEvent(title="pasado", start_at=u(now - timedelta(days=1))),
        CalendarEvent(title="en curso", start_at=u(now - timedelta(minutes=30)), end_at=u(now + timedelta(minutes=30))),
        CalendarEvent(title="futuro", start_at=u(now + timedelta(hours=3))),
        WorkoutSession(performed_on=date(2026, 11, 22), routine_name="Pierna", duration_min=60),
        WorkoutSession(performed_on=date(2026, 11, 17), routine_name="Torso", duration_min=50),
        WorkoutSession(performed_on=date(2026, 11, 10), routine_name="Viejo", duration_min=40),
    ])
    session.commit()
    d = build_dashboard(session, get_prefs(session), now=now)
    assert [e["title"] for e in d["events"]["items"]] == ["en curso", "futuro"]
    assert d["events"]["items"][0]["in_progress"] is True
    assert d["fitness"]["sessions_7d"] == 2 and d["fitness"]["minutes_7d"] == 110
    assert d["fitness"]["last_session"]["routine"] == "Pierna"
    assert d["projects"]["active"] == 1
    assert d["projects"]["items"][0] == {"id": p.id, "name": "Tienda online", "description": None, "open_tasks": 1}
