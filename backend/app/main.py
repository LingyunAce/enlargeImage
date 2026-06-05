"""FastAPI app factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from app.api.files import router as files_router
from app.api.jobs import router as jobs_router
from app.config import get_settings
from app.services.job_manager import JobManager


def create_app(job_manager: Optional[JobManager] = None) -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: reap ghost jobs
        if app.state.job_manager is not None:
            await app.state.job_manager.start_background_loops()
            await app.state.job_manager.startup_reap_ghosts()
        yield
        # Shutdown
        if app.state.job_manager is not None:
            app.state.job_manager.shutdown()

    app = FastAPI(title="EnlargeImage", lifespan=lifespan)
    app.state.job_manager = job_manager

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True}

    app.include_router(jobs_router)
    app.include_router(files_router)
    return app


# Default app instance for `uvicorn app.main:app` (the factory is for tests)
app = create_app()
