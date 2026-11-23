import platform

from fastapi import APIRouter
from sqlalchemy import text

from atlas import __version__
from atlas.api.deps import DB
from atlas.config import get_settings
from atlas.modules import modules_as_dicts

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
        "status": "online" if db_ok else "degraded",
        "version": __version__,
        "database": {"ok": db_ok, "engine": s.db_url.split(":", 1)[0]},
        # Fase 2 conectará el cerebro. Se informa honestamente que aún no existe.
        "ai": {"configured": False, "provider": None, "note": "Disponible en la Fase 2"},
        "python": platform.python_version(),
    }


@router.get("/modules")
def modules() -> list[dict]:
    return modules_as_dicts()
