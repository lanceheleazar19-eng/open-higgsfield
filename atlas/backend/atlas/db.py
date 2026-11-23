"""Motor de base de datos, sesiones y migraciones (Alembic)."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from atlas.config import BACKEND_DIR, get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _make_engine(url: str) -> Engine:
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(conn, _record):  # noqa: ANN001
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        if settings.db_url.startswith("sqlite"):
            settings.resolved_data_dir.mkdir(parents=True, exist_ok=True)
        _engine = _make_engine(settings.db_url)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    """Usado por los tests para apuntar a otra base de datos."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_session() -> Iterator[Session]:
    get_engine()
    assert _SessionLocal is not None
    with _SessionLocal() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sesión propia (p. ej. dentro de respuestas en streaming, que viven más que la petición)."""
    get_engine()
    assert _SessionLocal is not None
    with _SessionLocal() as session:
        yield session


def alembic_config(url: str | None = None) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(BACKEND_DIR) / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url or get_settings().db_url)
    return cfg


def init_db() -> None:
    """Aplica migraciones pendientes. Nunca borra datos."""
    get_engine()
    command.upgrade(alembic_config(), "head")
