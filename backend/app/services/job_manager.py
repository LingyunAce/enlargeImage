"""Async job manager: state machine, semaphore, in-memory cache + flush loop."""
from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models.job import Job, JobStatus, ProgressEvent
from app.pipeline.orchestrator import Pipeline
from app.services.file_store import FileStore
from app.services.job_store import JobStore

log = logging.getLogger(__name__)


class JobManager:
    def __init__(
        self,
        store: JobStore,
        file_store: FileStore,
        pipeline: Pipeline,
        flush_interval: float = 0.5,
        semaphore_permits: int = 1,
    ) -> None:
        self.store = store
        self.file_store = file_store
        self.pipeline = pipeline
        self.flush_interval = flush_interval
        self.semaphore = asyncio.Semaphore(semaphore_permits)
        # Cache: in-memory mirror of store, source of truth for reads
        self._cache: dict[str, Job] = {}
        self._dirty: set[str] = set()
        self._cancel_flags: dict[str, bool] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._flush_task: Optional[asyncio.Task] = None
        self._shutdown = False
        self._wake_next: asyncio.Event = asyncio.Event()
        self._wake_next.set()

    # --- public lifecycle ---

    async def start_background_loops(self) -> None:
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())
            self._flush_task.set_name("job-manager-flush")

    def shutdown(self) -> None:
        self._shutdown = True
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        for t in self._tasks.values():
            t.cancel()

    # --- public API ---

    async def create(self, input_path: str, scale: int) -> Job:
        jid, _ = self.file_store.new_job_dir()
        now = datetime.now(timezone.utc)
        job = Job(
            id=jid,
            status=JobStatus.QUEUED,
            stage=None,
            progress=0.0,
            scale=scale,
            input_path=input_path,
            output_path=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
        self._cache[jid] = job
        self.store.upsert(job)
        # Schedule processing
        self._tasks[jid] = asyncio.create_task(self._run_job(job))
        self._tasks[jid].set_name(f"job-{jid}")
        self._wake_next.set()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._cache.get(job_id)

    def list_recent(self, limit: int = 20) -> list[Job]:
        return sorted(self._cache.values(), key=lambda j: j.created_at, reverse=True)[:limit]

    # --- internal ---

    async def _run_job(self, job: Job) -> None:
        await self.semaphore.acquire()
        try:
            if self._shutdown:
                self._update(job.id, status=JobStatus.CANCELED, error="server_shutdown")
                return
            self._update(job.id, status=JobStatus.RUNNING, stage="tiling", progress=0.0)
            output_path = self.file_store.path(job.id, "output.png")

            def on_progress(ev: ProgressEvent) -> None:
                if self._cancel_flags.get(job.id):
                    raise CanceledError()
                p = self._map_progress(ev)
                self._update(job.id, stage=ev.stage, progress=p)

            try:
                # Load image
                from PIL import Image
                with Image.open(job.input_path) as im:
                    im = im.convert("RGB")
                    arr = np.array(im)
                # Run pipeline (CPU bound -> executor)
                loop = asyncio.get_event_loop()
                out = await loop.run_in_executor(
                    None,
                    self.pipeline.run,
                    arr,
                    job.scale,
                    on_progress,
                )
                # Encode PNG (also CPU bound)
                await loop.run_in_executor(None, _encode_png, out, output_path)
            except CanceledError:
                self._update(job.id, status=JobStatus.CANCELED)
                _safe_unlink(output_path)
                return
            except Exception as e:
                log.exception("job %s failed", job.id)
                self._update(
                    job.id,
                    status=JobStatus.FAILED,
                    error=f"{type(e).__name__}: {e}",
                )
                _safe_unlink(output_path)
                return

            self._update(
                job.id, status=JobStatus.DONE, progress=1.0, output_path=output_path
            )
        finally:
            self.semaphore.release()
            self._wake_next.set()

    def _map_progress(self, ev: ProgressEvent) -> float:
        if ev.stage == "tiling":
            return 0.05
        if ev.stage == "inference":
            return 0.05 + 0.85 * (ev.current / max(ev.total, 1))
        if ev.stage == "blending":
            return 0.90
        if ev.stage == "encoding":
            return 0.97
        return 1.0

    def _update(self, job_id: str, **kwargs) -> None:
        """Update a cached Job and mark it dirty for the flush loop."""
        old = self._cache[job_id]
        updated = replace(old, **kwargs, updated_at=datetime.now(timezone.utc))
        self._cache[job_id] = updated
        # If status changed, write through immediately (durability boundary)
        if "status" in kwargs or "output_path" in kwargs or "error" in kwargs:
            self.store.upsert(updated)
        else:
            self._dirty.add(job_id)

    async def _flush_loop(self) -> None:
        try:
            while not self._shutdown:
                await asyncio.sleep(self.flush_interval)
                if not self._dirty:
                    continue
                for jid in list(self._dirty):
                    job = self._cache.get(jid)
                    if job is None:
                        self._dirty.discard(jid)
                        continue
                    self.store.upsert(job)
                    self._dirty.discard(jid)
        except asyncio.CancelledError:
            return


def _encode_png(arr: np.ndarray, path: str) -> None:
    from PIL import Image
    Image.fromarray(arr).save(path, format="PNG", optimize=False)


def _safe_unlink(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


class CanceledError(Exception):
    pass
