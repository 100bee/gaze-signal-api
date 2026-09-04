from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from gaze_signal_api.api import calibrations, cameras, health, sessions, websocket
from gaze_signal_api.config.settings import Settings, get_settings
from gaze_signal_api.errors import GazeSignalError
from gaze_signal_api.logging import configure_logging
from gaze_signal_api.runtime.manager import SessionRuntimeManager
from gaze_signal_api.runtime.websocket import EventHub
from gaze_signal_api.storage.database import Database
from gaze_signal_api.storage.repository import Repository

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or get_settings()
    configure_logging(configured.log_level)
    database = Database(configured.database_url)
    repository = Repository(database)
    event_hub = EventHub()
    runtime = SessionRuntimeManager(repository, event_hub, configured)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database.create_all()
        recovered = repository.fail_stale_running_sessions()
        if recovered:
            logger.warning("marked stale running sessions as failed", extra={"count": recovered})
        yield
        runtime.shutdown()
        database.close()

    app = FastAPI(
        title=configured.app_name,
        version="0.1.0",
        description=(
            "Local-first API for observable face presence, gaze zone, head pose, blink, "
            "and optional phone visibility signals. It does not infer cognitive focus, "
            "emotion, identity, or medical state."
        ),
        lifespan=lifespan,
    )
    app.state.settings = configured
    app.state.database = database
    app.state.repository = repository
    app.state.event_hub = event_hub
    app.state.runtime = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["content-type"],
    )

    @app.exception_handler(GazeSignalError)
    async def handle_domain_error(_request: Request, exc: GazeSignalError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled API error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "an unexpected internal error occurred",
                }
            },
        )

    app.include_router(health.router)
    app.include_router(cameras.router)
    app.include_router(sessions.router)
    app.include_router(calibrations.router)
    app.include_router(websocket.router)

    static_path = Path(__file__).resolve().parent.parent / "static" / "index.html"

    @app.get("/", include_in_schema=False)
    def dashboard() -> HTMLResponse:
        return HTMLResponse(static_path.read_text(encoding="utf-8"))

    return app
