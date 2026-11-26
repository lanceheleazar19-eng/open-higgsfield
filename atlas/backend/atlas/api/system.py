import platform
import shutil

from fastapi import APIRouter
from sqlalchemy import func, select, text

from atlas import __version__
from atlas.api.deps import DB
from atlas.config import get_settings
from atlas.models import ActivityLog, CalendarEvent, Project, Task, Transaction, WorkoutSession
from atlas.modules import modules_as_dicts
from atlas.brain.orchestrator import brain_status
from atlas.services.preferences import get_prefs

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
def health(db: DB) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    s = get_settings()
    return {
        "storage": _storage(db, s) if db_ok else None,
        "status": "online" if db_ok else "degraded",
        "app": "vistan",  # identifica el servidor (VISTAN Desktop no confunde otro programa con VISTAN)
        "version": __version__,
        "database": {"ok": db_ok, "engine": s.db_url.split(":", 1)[0]},
        "ai": _ai(db),
        "python": platform.python_version(),
    }


@router.get("/modules")
def modules() -> list[dict]:
    return modules_as_dicts()


def _storage(db, s) -> dict:  # noqa: ANN001
    """Tamaño de la memoria local y espacio libre en disco (datos reales)."""
    data_dir = s.resolved_data_dir
    db_bytes = sum(p.stat().st_size for p in data_dir.glob("atlas.db*")) if data_dir.exists() else 0
    usage = shutil.disk_usage(data_dir if data_dir.exists() else ".")
    records = sum(
        db.scalar(select(func.count()).select_from(m)) or 0
        for m in (Task, CalendarEvent, Transaction, WorkoutSession, Project, ActivityLog)
    )
    from atlas.services.memory import counts
    return {"db_bytes": db_bytes, "disk_free_bytes": usage.free, "disk_total_bytes": usage.total, "records": records,
            **counts(db)}


def _ai(db) -> dict:  # noqa: ANN001
    st = brain_status(get_prefs(db))
    return {
        "configured": st["configured"],
        "provider": st["provider"] if st["reachable"] else None,
        "model": st["model"],
        "models_installed": len(st["models"]),
        "note": st["note"] or "Cerebro conectado",
    }


@router.get("/metrics")
def metrics() -> dict:
    """Uso real de CPU y RAM del ordenador donde corre VISTAN."""
    import psutil
    vm = psutil.virtual_memory()
    return {"cpu_percent": psutil.cpu_percent(interval=0.2), "ram_percent": vm.percent,
            "ram_used_bytes": vm.used, "ram_total_bytes": vm.total}
