"""Seguridad: política de permisos, registro de actividad, copias de seguridad y exportación."""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from atlas.api.deps import DB
from atlas.models import ActivityLog
from atlas.security.policy import LEVELS, NEVER, policy
from atlas.services.activity import log_activity
from atlas.services.backup import backup_db, backups_dir, export_bytes, list_backups
from atlas.services.preferences import get_prefs, set_prefs

router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("")
def get_security(db: DB) -> dict:
    return {"levels": LEVELS, "policy": policy(get_prefs(db)), "never": NEVER, "backups": list_backups()[:15],
            "backups_dir": str(backups_dir())}


class PolicyIn(BaseModel):
    WRITE: str = Field(pattern="^(auto|confirm)$")
    EXECUTE: str = Field(pattern="^(auto|confirm)$")


@router.put("/policy")
def put_policy(body: PolicyIn, db: DB) -> dict:
    set_prefs(db, {"security_policy": {"WRITE": body.WRITE, "EXECUTE": body.EXECUTE}})
    log_activity(db, "security", "settings", f"Política: WRITE={body.WRITE}, EXECUTE={body.EXECUTE}")
    db.commit()
    return policy(get_prefs(db))


@router.get("/activity")
def activity(db: DB, module: str | None = None, limit: int = 100) -> list[dict]:
    q = select(ActivityLog).order_by(ActivityLog.id.desc()).limit(min(limit, 500))
    if module:
        q = q.where(ActivityLog.module == module)
    return [{"id": a.id, "module": a.module, "action": a.action, "summary": a.summary, "created_at": a.created_at.isoformat()}
            for a in db.scalars(q)]


@router.post("/backups", status_code=201)
def create_backup(db: DB) -> dict:
    p = backup_db("manual")
    if not p:
        raise HTTPException(409, "No hay base de datos SQLite que copiar")
    log_activity(db, "security", "backup", f"Copia de seguridad {p.name}")
    db.commit()
    return {"name": p.name}


@router.get("/backups/{name}")
def download_backup(name: str) -> FileResponse:
    if "/" in name or ".." in name or not name.startswith("atlas-"):
        raise HTTPException(400, "Nombre no válido")
    f = backups_dir() / name
    if not f.exists():
        raise HTTPException(404, "Copia no encontrada")
    return FileResponse(f, filename=name, media_type="application/octet-stream")


@router.get("/export")
def export(db: DB) -> Response:
    log_activity(db, "security", "export", "Exportación completa de datos")
    db.commit()
    return Response(export_bytes(db), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="atlas-datos-{datetime.now():%Y%m%d}.json"'})
