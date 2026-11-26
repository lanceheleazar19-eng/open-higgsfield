"""Aplicación FastAPI de VISTAN."""

import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from atlas import __version__
from atlas.api import (academy, agents, legal, meta, six, ai, assistant, body, telemetry, center, dashboard, finance, goals, gym, health, integrations, knowledge, memory,
                       models_api, nutrition, profile, projects, research, security, settings, system, tasks, trading, voice, workflows, desk, betting, life, lab)
from atlas.config import get_settings
from atlas.db import init_db
from atlas.services.activity import log_activity


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


def _life_reminders() -> None:
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo

    from atlas.db import session_scope
    from atlas.life.service import reminders
    from atlas.services.preferences import get_prefs
    with session_scope() as db:
        reminders(db, _dt.now(ZoneInfo(str(get_prefs(db)["timezone"]))))
        db.commit()


async def _workflows_loop() -> None:
    """Workflows programados (Daily Briefing, Weekly Review…) y copia de seguridad diaria."""
    import asyncio

    from atlas.workflows import engine as wf
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(wf.tick)
            await asyncio.to_thread(wf.maintenance)
            await asyncio.to_thread(_life_reminders)
        except Exception:  # noqa: BLE001 - el programador nunca debe tumbar el servidor
            pass


_bet_tick = 0


async def _desk_loop() -> None:
    """Trading Desk (SIMULACIÓN): ejecuta órdenes limit/stop y SL/TP con el último precio y guarda la equity."""
    import asyncio

    from atlas.db import session_scope
    from atlas.desk import engine as desk_engine

    def tick() -> None:
        with session_scope() as db:
            desk_engine.periodic(db)
            db.commit()
        try:  # VISTAN SIX: ciclo autónomo de paper trading (solo si lo activaste y sin kill switch)
            from atlas.six import runner as six_runner
            with session_scope() as db:
                if six_runner.due(db):
                    six_runner.tick(db)
                    db.commit()
        except Exception as exc:  # noqa: BLE001 - un fallo de los agentes nunca detiene el Trading Desk, pero queda registrado
            logging.getLogger("atlas.six").exception("Ciclo de VISTAN SIX fallido")
            try:
                with session_scope() as db:
                    log_activity(db, "trading", "six_error", f"VISTAN SIX: el ciclo automático falló: {type(exc).__name__}: {exc}"[:300])
                    db.commit()
            except Exception:  # noqa: BLE001
                pass
        global _bet_tick
        _bet_tick += 1
        if _bet_tick % 15 == 0:  # cada ~5 min: liquidar pronósticos simulados con resultados reales
            from atlas.bets import engine as bet_engine
            with session_scope() as db:
                bet_engine.settle(db, fetch=True)
                db.commit()
    while True:
        await asyncio.sleep(20)
        try:
            await asyncio.to_thread(tick)
        except Exception:  # noqa: BLE001 - nunca tumba el servidor
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
    from atlas.metabrain.engine import mark_interrupted as meta_interrupted
    meta_interrupted()
    from atlas.legal.research import mark_interrupted as legal_interrupted
    legal_interrupted()
    task = asyncio.create_task(_periodic_sync())
    wtask = asyncio.create_task(_workflows_loop())
    dtask = asyncio.create_task(_desk_loop())
    yield
    dtask.cancel()
    task.cancel()
    wtask.cancel()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="VISTAN — Personal Intelligence System", version=__version__, lifespan=lifespan)
    if s.host in ("127.0.0.1", "localhost", "::1") and "*" not in s.allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=s.allowed_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    for r in (system.router, dashboard.router, settings.router, assistant.router, ai.router, memory.router, tasks.router, goals.router, gym.router, profile.router, nutrition.router, integrations.router, finance.router, trading.router, health.router,
              knowledge.router, research.router, agents.router, workflows.router, models_api.router, security.router,
              projects.router, center.router, body.router, telemetry.router, voice.router, desk.router, betting.router, life.public, life.router, lab.router, meta.router, legal.router, academy.router, six.router):
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
