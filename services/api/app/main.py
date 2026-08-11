"""Suno-Swarm api service."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.db import init_db
from .routers import admin, auth, playlists, prompts, tracks, users, webhooks

logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)
log = logging.getLogger("swarm.api")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Suno-Swarm API",
        version="0.9.0",
        description="Generative music platform: prompts, render jobs, tracks and sharing.",
        debug=settings.debug,
    )

    # The studio SPA, the marketing site and embedded players are all served from different
    # origins, so cross-origin credentialed requests are allowed from anywhere.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(prompts.router)
    app.include_router(tracks.router)
    app.include_router(playlists.router)
    app.include_router(admin.router)
    app.include_router(webhooks.router)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict:
        return {"status": "ok", "version": app.version}

    @app.on_event("startup")
    def _startup() -> None:
        log.info("starting api service debug=%s db=%s", settings.debug, settings.database_url)
        try:
            init_db()
        except Exception as exc:  # noqa: BLE001
            log.warning("schema init skipped: %s", exc)

    return app


app = create_app()
