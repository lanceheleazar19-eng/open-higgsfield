"""Aplicación FastAPI de ATLAS."""

import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from atlas import __version__
from atlas.api import ai, assistant, dashboard, goals, gym, integrations, memory, nutrition, profile, settings, system, tasks
from atlas.config import get_settings
from atlas.db import init_db


async def _periodic_sync() -> None:
    """Sincroniza Gmail e iCloud cada 30 min mientras ATLAS está abierto."""
    import asyncio

    from atlas.api.integrations import sync_all
    from atlas.db import session_scope

    def run() -> None:
        with session_scope() as db:
            sync_all(db)

    while True:
        await asyncio.sleep(get_settings().sync_interval_s)
        try:
            await asyncio.to_thread(run)
        except Exception:  # noqa: BLE001 - la sincronización nunca debe tumbar el servidor
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import asyncio
    init_db()
    task = asyncio.create_task(_periodic_sync())
    yield
    task.cancel()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="ATLAS — Personal Intelligence System", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    for r in (system.router, dashboard.router, settings.router, assistant.router, ai.router, memory.router, tasks.router, goals.router, gym.router, profile.router, nutrition.router, integrations.router):
        app.include_router(r)

    _mount_frontend(app, s.frontend_dist)
    return app


mimetypes.add_type("application/manifest+json", ".webmanifest")


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Sirve la SPA compilada (frontend/dist) si existe."""
    index = dist / "index.html"
    if not index.exists():
        @app.get("/", include_in_schema=False)
        def _no_frontend() -> dict:
            return {"atlas": "online", "frontend": "no compilado — ejecuta scripts/start o `npm run build` en frontend/"}
        return

    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def _spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
