"""Aplicación FastAPI de VISTAN."""

import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from atlas import __version__
from atlas.api import (agents, ai, assistant, body, telemetry, center, dashboard, finance, goals, gym, health, integrations, knowledge, memory,
                       models_api, nutrition, profile, projects, research, security, settings, system, tasks, trading, workflows)
from atlas.config import get_settings
from atlas.db import init_db


async def _periodic_sync() -> None:
    """Sincroniza Gmail e iCloud cada 30 min mientras VISTAN está abierto."""
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


async def _workflows_loop() -> None:
    """Workflows programados (Daily Briefing, Weekly Review…) y copia de seguridad diaria."""
    import asyncio

    from atlas.workflows import engine as wf
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(wf.tick)
            await asyncio.to_thread(wf.maintenance)
        except Exception:  # noqa: BLE001 - el programador nunca debe tumbar el servidor
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import asyncio
    init_db()
    from atlas.db import session_scope
    from atlas.research.engine import mark_interrupted
    from atlas.workflows.engine import ensure_builtins
    with session_scope() as db:
        ensure_builtins(db)
    mark_interrupted()
    task = asyncio.create_task(_periodic_sync())
    wtask = asyncio.create_task(_workflows_loop())
    yield
    task.cancel()
    wtask.cancel()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="VISTAN — Personal Intelligence System", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    for r in (system.router, dashboard.router, settings.router, assistant.router, ai.router, memory.router, tasks.router, goals.router, gym.router, profile.router, nutrition.router, integrations.router, finance.router, trading.router, health.router,
              knowledge.router, research.router, agents.router, workflows.router, models_api.router, security.router,
              projects.router, center.router, body.router, telemetry.router):
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
