"""Copias de seguridad de la base de datos (API de backup de SQLite, coherente aunque VISTAN esté en uso)
y exportación completa de tus datos a JSON."""

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from atlas.config import get_settings

KEEP = 30  # copias que se conservan


def _db_path() -> Path | None:
    url = get_settings().db_url
    return Path(url.removeprefix("sqlite:///")) if url.startswith("sqlite:///") else None


def backups_dir() -> Path:
    d = get_settings().resolved_data_dir / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backup_db(reason: str = "manual") -> Path | None:
    """Copia atlas.db a data/backups/atlas-AAAAMMDD-HHMMSS-motivo.db. None si no hay base SQLite aún."""
    src = _db_path()
    if not src or not src.exists() or src.stat().st_size == 0:
        return None
    safe = "".join(c for c in reason if c.isalnum() or c in "-_")[:24] or "manual"
    dst = backups_dir() / f"atlas-{datetime.now():%Y%m%d-%H%M%S}-{safe}.db"
    with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
        s.backup(d)
    olds = sorted(backups_dir().glob("atlas-*.db"))
    for f in olds[:-KEEP]:
        f.unlink(missing_ok=True)
    return dst


def list_backups() -> list[dict]:
    return [{"name": f.name, "size": f.stat().st_size, "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat()}
            for f in sorted(backups_dir().glob("atlas-*.db"), reverse=True)]


SKIP_EXPORT = {"alembic_version", "doc_chunks"}  # los fragmentos se regeneran desde los documentos


def _jsonable(v):  # noqa: ANN001, ANN202
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, bytes):
        return None
    return v


def export_all(db: Session) -> dict:
    """Todas tus tablas (sin índices internos) en un único JSON. Las credenciales NO están en la base de datos."""
    out: dict = {"exported_at": datetime.now().isoformat(), "app": "VISTAN", "tables": {}}
    insp = inspect(db.get_bind())
    for t in insp.get_table_names():
        if t in SKIP_EXPORT or t.endswith("_fts") or "_fts_" in t:
            continue
        rows = db.execute(text(f'SELECT * FROM "{t}"')).mappings().all()
        out["tables"][t] = [{k: _jsonable(v) for k, v in r.items()} for r in rows]
    return out


def export_bytes(db: Session) -> bytes:
    return json.dumps(export_all(db), ensure_ascii=False, indent=1).encode()
