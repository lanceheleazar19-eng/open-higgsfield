"""Aplicación FastAPI de ATLAS."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from atlas import __version__
from atlas.api import ai, assistant, dashboard, goals, gym, memory, settings, system, tasks
from atlas.config import get_settings
from atlas.db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="ATLAS — Personal Intelligence System", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    for r in (system.router, dashboard.router, settings.router, assistant.router, ai.router, memory.router, tasks.router, goals.router, gym.router):
        app.include_router(r)

    _mount_frontend(app, s.frontend_dist)
    return app


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
