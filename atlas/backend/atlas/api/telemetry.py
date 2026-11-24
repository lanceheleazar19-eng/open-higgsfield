"""Telemetría REAL del centro de control: sistema, IA, latencias, memoria, agentes, procesos, conexiones,
eventos y actividad del día. Si un dato no se puede medir, se devuelve None (la interfaz muestra «N/D»)."""

import os
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter
from sqlalchemy import func, select

from atlas.api.deps import DB
from atlas.config import get_settings
from atlas.models import (ActivityLog, AgentRun, ConversationMessage, DocChunk, Document, Entity, HealthDay, Memory, ModelCall,
                          Notification, Relation, Research, Task, WorkflowRun)
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api", tags=["telemetry"])
STARTED = time.time()


def _system() -> dict:
    try:
        import psutil
    except ImportError:  # pragma: no cover
        return {}
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    proc = psutil.Process()
    with proc.oneshot():
        rss = proc.memory_info().rss
        threads = proc.num_threads()
    try:
        load = os.getloadavg()
    except (OSError, AttributeError):
        load = None
    db = get_settings().resolved_data_dir / "atlas.db"
    disk = psutil.disk_usage(str(get_settings().resolved_data_dir))
    return {"cpu_percent": psutil.cpu_percent(interval=0.15), "cpu_count": psutil.cpu_count(), "load": [round(x, 2) for x in load] if load else None,
            "ram_percent": vm.percent, "ram_used": vm.used, "ram_total": vm.total, "swap_percent": sw.percent,
            "process_rss": rss, "process_threads": threads, "uptime_s": int(time.time() - STARTED),
            "db_bytes": db.stat().st_size if db.exists() else None, "disk_free": disk.free, "disk_percent": disk.percent}


def _ollama() -> dict:
    url = get_settings().ollama_url
    t0 = time.perf_counter()
    try:
        r = httpx.get(f"{url}/api/tags", timeout=1.5)
        ok = r.status_code == 200
        ping = round((time.perf_counter() - t0) * 1000)
        loaded = []
        if ok:
            try:
                ps = httpx.get(f"{url}/api/ps", timeout=1.0).json().get("models", [])
                loaded = [{"name": m.get("name"), "vram": m.get("size_vram"), "size": m.get("size")} for m in ps]
            except (httpx.HTTPError, ValueError):
                loaded = None
        return {"reachable": ok, "ping_ms": ping, "installed": len(r.json().get("models", [])) if ok else None, "loaded": loaded}
    except httpx.HTTPError:
        return {"reachable": False, "ping_ms": None, "installed": None, "loaded": None}


def _voicestudio() -> dict:
    from atlas.voice.voicestudio import status
    return status(timeout=0.8)


@router.get("/telemetry")
def telemetry(db: DB) -> dict:
    from atlas.brain import router as mr
    from atlas.brain.orchestrator import brain_status
    from atlas.integrations.secrets import get_secret
    prefs = get_prefs(db)
    tz = ZoneInfo(str(prefs["timezone"]))
    now = datetime.utcnow()
    since = now - timedelta(hours=24)
    local_midnight = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = local_midnight.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    st = brain_status(prefs)
    choice = mr.cloud_choice("chat", prefs)
    ol = _ollama()
    last = db.scalar(select(ModelCall).order_by(ModelCall.id.desc()).limit(1))
    agg = db.execute(select(func.count(ModelCall.id), func.avg(ModelCall.latency_ms), func.max(ModelCall.latency_ms),
                            func.sum(func.coalesce(ModelCall.tokens_out, 0))).where(ModelCall.created_at >= since)).one()
    errs = db.scalar(select(func.count(ModelCall.id)).where(ModelCall.created_at >= since, ModelCall.ok.is_(False))) or 0
    series = [c.latency_ms for c in db.scalars(select(ModelCall).where(ModelCall.ok.is_(True)).order_by(ModelCall.id.desc()).limit(30))][::-1]

    recalled = list(db.scalars(select(Memory).where(Memory.last_used_at.is_not(None)).order_by(Memory.last_used_at.desc()).limit(5)))
    runs24 = list(db.scalars(select(AgentRun).where(AgentRun.created_at >= since).order_by(AgentRun.id.desc())))
    procs = [{"kind": "investigación", "label": r.question[:80], "state": r.step or r.status}
             for r in db.scalars(select(Research).where(Research.status.in_(("running", "queued"))))]
    procs += [{"kind": "workflow", "label": f"ejecución #{w.id}", "state": w.status}
              for w in db.scalars(select(WorkflowRun).where(WorkflowRun.status.in_(("running", "awaiting_approval"))))]
    procs += [{"kind": "hilo", "label": t.name, "state": "activo"} for t in threading.enumerate()
              if t.name.startswith(("research-",)) and t.is_alive()]

    def conn(name: str, state: str, detail: str | None = None) -> dict:
        return {"name": name, "state": state, "detail": detail}
    hd = db.scalar(select(func.max(HealthDay.updated_at)))
    conns = [
        conn("Ollama (IA local)", "ok" if ol["reachable"] else "off", f"{ol['ping_ms']} ms" if ol["ping_ms"] is not None else "no responde"),
        conn("Base de datos", "ok", "SQLite"),
        (lambda v: conn("VoiceStudio (voz)", "ok" if v["reachable"] else "off",
                        f"{v['ping_ms']} ms · {len(v['voices'])} voces" if v["reachable"] else "no abierto"))(_voicestudio()),
        conn("Gmail", "ok" if get_secret("gmail_app_password") else "off", f"sync {prefs.get('gmail_last_sync') or 'nunca'}" if get_secret("gmail_app_password") else "no conectado"),
        conn("iCloud Calendar", "ok" if get_secret("icloud_app_password") else "off", f"sync {prefs.get('icloud_last_sync') or 'nunca'}" if get_secret("icloud_app_password") else "no conectado"),
        conn("Apple Salud", "ok" if hd else "off", f"último dato {hd:%d/%m %H:%M} UTC" if hd else "sin datos"),
        *[conn(lbl, "key" if mr.has_key(p) else "off", "API key guardada" if mr.has_key(p) else "sin API key")
          for p, lbl in (("openai", "OpenAI"), ("anthropic", "Anthropic"), ("gemini", "Gemini"))],
    ]

    ev = [{"ts": a.created_at.isoformat(), "module": a.module, "action": a.action, "text": a.summary}
          for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id.desc()).limit(40))]
    ev += [{"ts": c.created_at.isoformat(), "module": "ia", "action": "ok" if c.ok else "error",
            "text": f"{c.provider}:{c.model} · {c.task} · {c.latency_ms} ms" + ("" if c.ok else f" · {c.error or 'error'}")}
           for c in db.scalars(select(ModelCall).order_by(ModelCall.id.desc()).limit(25))]
    ev.sort(key=lambda e: e["ts"], reverse=True)

    by_mod = dict(db.execute(select(ActivityLog.module, func.count(ActivityLog.id)).where(ActivityLog.created_at >= today_utc)
                             .group_by(ActivityLog.module)).all())
    return {
        "generated_at": now.isoformat(),
        "system": _system(),
        "core": {"online": True, "ai_configured": st["configured"], "model": f"{choice[0]}:{choice[1]}" if choice else st["model"],
                 "provider": choice[0] if choice else ("ollama" if st["configured"] else None), "privacy": mr.config(prefs)["privacy"]},
        "ollama": ol,
        "latency": {"last_ms": last.latency_ms if last else None, "last_model": f"{last.provider}:{last.model}" if last else None,
                    "last_at": last.created_at.isoformat() if last else None, "avg_24h": round(agg[1]) if agg[1] else None,
                    "max_24h": agg[2], "calls_24h": agg[0] or 0, "errors_24h": errs, "tokens_out_24h": agg[3] or 0, "series": series},
        "memory": {"memories": db.scalar(select(func.count(Memory.id))) or 0, "documents": db.scalar(select(func.count(Document.id))) or 0,
                   "chunks": db.scalar(select(func.count(DocChunk.id))) or 0, "entities": db.scalar(select(func.count(Entity.id))) or 0,
                   "relations": db.scalar(select(func.count(Relation.id))) or 0,
                   "recalled_24h": db.scalar(select(func.count(Memory.id)).where(Memory.last_used_at >= since)) or 0,
                   "recalled": [{"text": m.content[:120], "at": m.last_used_at.isoformat()} for m in recalled]},
        "agents": {"runs_24h": len(runs24), "active": sorted({a for r in runs24 for a in r.agents}),
                   "last": {"request": runs24[0].request[:100], "agents": runs24[0].agents, "status": runs24[0].status,
                            "ms": runs24[0].duration_ms, "at": runs24[0].created_at.isoformat()} if runs24 else None},
        "processes": procs,
        "connections": conns,
        "events": ev[:50],
        "today": {"by_module": by_mod, "events": sum(by_mod.values()),
                  "tasks_done": db.scalar(select(func.count(Task.id)).where(Task.completed_at >= today_utc)) or 0,
                  "messages": db.scalar(select(func.count(ConversationMessage.id)).where(ConversationMessage.created_at >= today_utc)) or 0,
                  "model_calls": db.scalar(select(func.count(ModelCall.id)).where(ModelCall.created_at >= today_utc)) or 0,
                  "notifications": db.scalar(select(func.count(Notification.id)).where(Notification.created_at >= today_utc)) or 0},
    }
