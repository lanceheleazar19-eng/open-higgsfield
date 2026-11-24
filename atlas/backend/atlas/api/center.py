"""Command Center, Analytics, Inteligencia proactiva, Notificaciones y búsqueda global (CMD+K).
Todo sale de datos reales del backend."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import case, func, select

from atlas.api.deps import DB
from atlas.models import (ActivityLog, AgentRun, Approval, Conversation, Document, Memory, ModelCall, Notification, Project,
                          Research, Task, Transaction, Workflow, WorkflowRun, WorkoutSession, WorkoutSet)
from atlas.services.insights import RULES, config as insights_config, detect
from atlas.services.preferences import get_prefs, set_prefs

router = APIRouter(prefix="/api", tags=["center"])


@router.get("/command-center")
def command_center(db: DB) -> dict:
    from atlas.agents.core import run_dict
    from atlas.brain import router as mr
    from atlas.brain.orchestrator import brain_status
    from atlas.services.memory import counts
    prefs = get_prefs(db)
    since = datetime.utcnow() - timedelta(hours=24)
    st = brain_status(prefs)
    calls = db.execute(select(func.count(ModelCall.id), func.avg(ModelCall.latency_ms),
                              func.sum(case((ModelCall.ok.is_(False), 1), else_=0))).where(ModelCall.created_at >= since)).one()
    running = [{"kind": "research", "id": r.id, "label": r.question, "step": r.step, "status": r.status}
               for r in db.scalars(select(Research).where(Research.status.in_(("running", "queued"))))]
    running += [{"kind": "workflow", "id": w.id, "label": f"Workflow #{w.workflow_id}", "step": None, "status": w.status}
                for w in db.scalars(select(WorkflowRun).where(WorkflowRun.status.in_(("running", "awaiting_approval"))))]
    recent_runs = list(db.scalars(select(AgentRun).order_by(AgentRun.id.desc()).limit(6)))
    active_agents = sorted({a for r in recent_runs if r.created_at >= since for a in r.agents})
    choice = mr.cloud_choice("chat", prefs)
    return {
        "core": {"state": "online", "ai_reachable": st["reachable"],
                 "model": f"{choice[0]}:{choice[1]}" if choice else st["model"], "note": st["note"],
                 "privacy": mr.config(prefs)["privacy"]},
        "model_calls_24h": {"count": calls[0] or 0, "avg_ms": round(calls[1] or 0), "errors": int(calls[2] or 0)},
        "agents_active_24h": active_agents,
        "recent_agent_runs": [run_dict(r) for r in recent_runs],
        "memory": counts(db) | {"documents": db.scalar(select(func.count(Document.id))) or 0},
        "processes": running,
        "research_total": db.scalar(select(func.count(Research.id))) or 0,
        "research_running": sum(1 for p in running if p["kind"] == "research"),
        "agent_runs_24h": db.scalar(select(func.count(AgentRun.id)).where(AgentRun.created_at >= since)) or 0,
        "pending_tasks": db.scalar(select(func.count(Task.id)).where(Task.status == "pending")) or 0,
        "approvals_pending": db.scalar(select(func.count(Approval.id)).where(Approval.status == "pending")) or 0,
        "notifications_unread": db.scalar(select(func.count(Notification.id)).where(Notification.read.is_(False))) or 0,
        "insights": detect(db, prefs)[:6],
        "recent_conversations": [{"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat()}
                                 for c in db.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(5))],
        "activity": [{"module": a.module, "summary": a.summary, "created_at": a.created_at.isoformat()}
                     for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id.desc()).limit(12))],
        "workflows_scheduled": [{"id": w.id, "name": w.name, "schedule": w.schedule}
                                for w in db.scalars(select(Workflow).where(Workflow.enabled.is_(True), Workflow.schedule.is_not(None)))],
    }


@router.get("/analytics")
def analytics(db: DB) -> dict:
    from atlas.finance.service import summary
    from atlas.trading.service import stats
    prefs = get_prefs(db)
    tz = ZoneInfo(str(prefs["timezone"]))
    today = datetime.now(tz).date()
    monday = today - timedelta(days=today.weekday())
    weeks = []
    for i in range(11, -1, -1):
        a = monday - timedelta(weeks=i)
        b = a + timedelta(days=7)
        sessions = db.scalar(select(func.count(WorkoutSession.id)).where(WorkoutSession.performed_on >= a, WorkoutSession.performed_on < b)) or 0
        vol = db.scalar(select(func.coalesce(func.sum(WorkoutSet.reps * WorkoutSet.weight), 0)).join(
            WorkoutSession, WorkoutSet.session_id == WorkoutSession.id).where(
            WorkoutSession.performed_on >= a, WorkoutSession.performed_on < b, WorkoutSet.warmup.is_(False))) or 0
        weeks.append({"week": a.isoformat(), "sessions": sessions, "tonnage": round(float(vol))})
    fin = summary(db, today)
    months12 = []
    m = today.replace(day=1)
    for _ in range(12):
        e = (m + timedelta(days=32)).replace(day=1)
        inc = db.scalar(select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.kind == "income", Transaction.occurred_on >= m, Transaction.occurred_on < e)) or 0
        exp = db.scalar(select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.kind == "expense", Transaction.occurred_on >= m, Transaction.occurred_on < e)) or 0
        months12.append({"month": m.strftime("%Y-%m"), "income_cents": int(inc), "expense_cents": int(exp)})
        m = (m - timedelta(days=1)).replace(day=1)
    cap = prefs.get("paper_capital")
    tr = stats(db, float(cap) if cap else None)
    now = datetime.utcnow()
    projects = []
    for p in db.scalars(select(Project).where(Project.status.in_(("active", "paused")))):
        q = lambda *w: db.scalar(select(func.count(Task.id)).where(Task.project_id == p.id, *w)) or 0  # noqa: E731
        total, done = q(), q(Task.status == "done")
        projects.append({"id": p.id, "name": p.name, "total": total, "done": done,
                         "overdue": q(Task.status == "pending", Task.due_at < now),
                         "progress": round(100 * done / total) if total else None})
    done_by_week = []
    for i in range(7, -1, -1):
        a = datetime.combine(monday - timedelta(weeks=i), datetime.min.time())
        done_by_week.append({"week": a.date().isoformat(), "done": db.scalar(select(func.count(Task.id)).where(
            Task.completed_at >= a, Task.completed_at < a + timedelta(days=7))) or 0})
    return {
        "fitness": {"weeks": weeks, "has_data": any(w["sessions"] for w in weeks)},
        "finance": {"months": list(reversed(months12)), "current": {k: fin[k] for k in ("income_cents", "expense_cents", "net_cents", "savings_rate", "budgets", "by_category")},
                    "has_data": any(x["income_cents"] or x["expense_cents"] for x in months12)},
        "trading": {k: tr[k] for k in ("overall", "curve", "by_strategy", "max_drawdown", "equity", "return_pct", "open_risk")}
                   | {"has_data": tr["overall"]["trades"] > 0, "simulation": True},
        "projects": {"items": projects, "done_by_week": done_by_week,
                     "has_data": bool(projects) or any(w["done"] for w in done_by_week)},
    }


@router.get("/insights")
def insights(db: DB) -> dict:
    prefs = get_prefs(db)
    return {"items": detect(db, prefs), "config": insights_config(prefs), "rules": RULES}


class InsightCfg(BaseModel):
    enabled: bool
    rules: dict[str, bool]


@router.put("/insights/config")
def insights_cfg(body: InsightCfg, db: DB) -> dict:
    set_prefs(db, {"proactive": {"enabled": body.enabled, "rules": {k: bool(v) for k, v in body.rules.items() if k in RULES}}})
    db.commit()
    return insights_config(get_prefs(db))


@router.post("/insights/{iid}/dismiss")
def dismiss(iid: str, db: DB) -> dict:
    d = dict(get_prefs(db).get("insights_dismissed") or {})
    d[iid] = datetime.utcnow().isoformat()
    if len(d) > 500:
        d = dict(sorted(d.items(), key=lambda x: x[1])[-400:])
    set_prefs(db, {"insights_dismissed": d})
    db.commit()
    return {"ok": True}


@router.get("/notifications")
def notifications(db: DB, limit: int = 30) -> dict:
    items = db.scalars(select(Notification).order_by(Notification.id.desc()).limit(min(limit, 100)))
    return {"unread": db.scalar(select(func.count(Notification.id)).where(Notification.read.is_(False))) or 0,
            "items": [{"id": n.id, "title": n.title, "body": n.body, "level": n.level, "link": n.link, "read": n.read,
                       "created_at": n.created_at.isoformat()} for n in items]}


@router.post("/notifications/read")
def mark_read(db: DB, ids: list[int] | None = None) -> dict:
    q = db.query(Notification).filter(Notification.read.is_(False))
    if ids:
        q = q.filter(Notification.id.in_(ids))
    n = q.update({Notification.read: True}, synchronize_session=False)
    db.commit()
    return {"marked": n}


@router.get("/search")
def global_search(q: str, db: DB) -> dict:
    """Búsqueda de la paleta de comandos: tareas, recuerdos, documentos, proyectos e investigaciones."""
    from atlas.knowledge.service import search as doc_search
    from atlas.services.memory import search_memories
    q = q.strip()
    if len(q) < 2:
        return {"tasks": [], "memories": [], "documents": [], "projects": [], "research": []}
    like = f"%{q}%"
    return {
        "tasks": [{"id": t.id, "title": t.title, "status": t.status} for t in
                  db.scalars(select(Task).where(Task.title.ilike(like)).order_by(Task.status.desc(), Task.id.desc()).limit(6))],
        "memories": [{"id": m.id, "content": m.content[:140]} for m in search_memories(db, q, limit=6)],
        "documents": [{"id": d["document_id"], "title": d["title"], "snippet": d["text"][:140]} for d in doc_search(db, q, k=5)],
        "projects": [{"id": p.id, "name": p.name} for p in db.scalars(select(Project).where(Project.name.ilike(like)).limit(5))],
        "research": [{"id": r.id, "question": r.question} for r in db.scalars(select(Research).where(Research.question.ilike(like)).limit(5))],
    }
