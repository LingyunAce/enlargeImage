"""FastAPI app factory + module-level default app for `uvicorn app.main:app`."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from app.api.files import router as files_router
from app.api.jobs import router as jobs_router
from app.config import get_settings
from app.pipeline.orchestrator import Pipeline
from app.pipeline.runner import SwinIRRunner
from app.pipeline.seam import SeamBlender
from app.pipeline.tiler import Tiler
from app.services.file_store import FileStore
from app.services.job_manager import JobManager
from app.services.job_store import JobStore


def create_app(
    job_manager: Optional[JobManager] = None,
    runner: Optional[SwinIRRunner] = None,
) -> FastAPI:
    """Create a FastAPI app.

    If job_manager is not provided, build a default one (no SwinIR loaded —
    scale=4 is registered, but infer() will fail until the user provides a
    runner via app.state. The default app is for the API skeleton + tests
    that don't need real inference; production should construct the
    job_manager explicitly with a loaded SwinIR).
    """
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    if job_manager is None and runner is None:
        # Build a default JobManager with a no-op runner for the API skeleton.
        # Routes that hit /jobs will succeed; the inference will return
        # deterministic placeholder output (a zero image).
        from app.services.job_manager import _StubRunner  # see below
        runner = _StubRunner(scale=4)
        pipeline = Pipeline(
            runner=runner,
            tiler=Tiler(tile_size=settings.tile_size, overlap=settings.overlap),
            blender=SeamBlender(),
        )
        job_manager = JobManager(
            store=JobStore(db_path=settings.db_path),
            file_store=FileStore(root=settings.storage_dir),
            pipeline=pipeline,
            flush_interval=settings.flush_interval,
            semaphore_permits=settings.semaphore_permits,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.job_manager is not None:
            await app.state.job_manager.start_background_loops()
            await app.state.job_manager.startup_reap_ghosts()
        yield
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


# Default app instance for `uvicorn app.main:app`
app = create_app()
