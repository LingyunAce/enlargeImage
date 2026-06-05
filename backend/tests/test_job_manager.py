import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import torch
from app.models.job import Job, JobStatus, ProgressEvent
from app.models.swinir import build_swinir
from app.pipeline.orchestrator import Pipeline
from app.pipeline.runner import SwinIRRunner
from app.pipeline.seam import SeamBlender
from app.pipeline.tiler import Tiler
from app.services.file_store import FileStore
from app.services.job_manager import JobManager
from app.services.job_store import JobStore


@pytest.fixture
def runner(tmp_path: Path) -> SwinIRRunner:
    net = build_swinir(scale=2)
    p = tmp_path / "ckpt.pth"
    torch.save({"params": net.state_dict()}, str(p))
    return SwinIRRunner(model_path=str(p), scale=2, device="cpu")


@pytest.fixture
def jm(tmp_path: Path, runner: SwinIRRunner) -> JobManager:
    fs = FileStore(root=str(tmp_path / "storage"))
    js = JobStore(db_path=str(tmp_path / "test.db"))
    pipeline = Pipeline(
        runner=runner, tiler=Tiler(tile_size=64, overlap=16), blender=SeamBlender()
    )
    jm = JobManager(store=js, file_store=fs, pipeline=pipeline, flush_interval=0.1)
    yield jm
    jm.shutdown()


def test_create_completes_job_to_done(jm: JobManager, tmp_path: Path):
    inp = tmp_path / "input.png"
    from PIL import Image
    # SwinIR's window partition requires dimensions divisible by window_size (8),
    # and the model is built with img_size=64. 64x64 is the smallest valid input.
    Image.new("RGB", (64, 64), (255, 0, 0)).save(inp)

    async def run() -> Job:
        job = await jm.create(input_path=str(inp), scale=2)
        # Poll until terminal. Must use asyncio.sleep (not time.sleep) so the
        # event loop stays free to run the job task and process executor
        # completion callbacks.
        deadline = time.time() + 15
        while time.time() < deadline:
            latest = jm.get(job.id)
            if latest.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELED):
                return latest
            await asyncio.sleep(0.1)
        return jm.get(job.id)

    final = asyncio.run(run())
    assert final is not None
    assert final.status is JobStatus.DONE, f"expected DONE, got {final.status} (error: {final.error})"


def test_get_returns_latest_state(jm: JobManager, tmp_path: Path):
    inp = tmp_path / "input.png"
    from PIL import Image
    # Use 64x64 so the model's window partition is valid; we don't wait for
    # completion here, but the size keeps the job from failing on launch.
    Image.new("RGB", (64, 64), (255, 0, 0)).save(inp)
    job = asyncio.run(jm.create(input_path=str(inp), scale=2))
    got = jm.get(job.id)
    assert got is not None
    assert got.id == job.id


def test_startup_reap_ghosts_marks_stale_as_failed(tmp_path: Path, runner: SwinIRRunner):
    from datetime import datetime, timezone
    fs = FileStore(root=str(tmp_path / "storage"))
    js = JobStore(db_path=str(tmp_path / "test.db"))
    # Pre-seed two stale jobs
    now = datetime.now(timezone.utc)
    js.upsert(Job(
        id="g1", status=JobStatus.QUEUED, stage=None, progress=0.0,
        scale=4, input_path="/nope", output_path=None, error=None,
        created_at=now, updated_at=now,
    ))
    js.upsert(Job(
        id="g2", status=JobStatus.RUNNING, stage=None, progress=0.5,
        scale=4, input_path="/nope", output_path=None, error=None,
        created_at=now, updated_at=now,
    ))
    jm = JobManager(store=js, file_store=fs, pipeline=Pipeline(
        runner=runner, tiler=Tiler(64, 16), blender=SeamBlender()
    ))
    n = asyncio.run(jm.startup_reap_ghosts())
    assert n == 2
    stored_g1 = js.get("g1")
    assert stored_g1.status is JobStatus.FAILED
    assert stored_g1.error == "server_restart"
    assert jm.get("g1").status is JobStatus.FAILED


def test_trim_removes_old_done_jobs(tmp_path: Path, runner: SwinIRRunner):
    from datetime import datetime, timedelta, timezone
    fs = FileStore(root=str(tmp_path / "storage"))
    js = JobStore(db_path=str(tmp_path / "test.db"))
    jm = JobManager(store=js, file_store=fs, pipeline=Pipeline(
        runner=runner, tiler=Tiler(64, 16), blender=SeamBlender()
    ))
    now = datetime.now(timezone.utc)
    seeded_ids = []
    for i in range(5):
        jid, _ = fs.new_job_dir()
        js.upsert(Job(
            id=jid, status=JobStatus.DONE, stage=None, progress=1.0,
            scale=4, input_path="/nope", output_path=None, error=None,
            created_at=now - timedelta(minutes=10 - i), updated_at=now,
        ))
        seeded_ids.append(jid)
    # Add the pre-seeded jobs to the manager's cache so list_recent can find them
    for jid in seeded_ids:
        jm._cache[jid] = js.get(jid)
    deleted = jm.trim(keep=2)
    assert deleted == 3
    remaining = jm.list_recent(limit=100)
    assert len(remaining) == 2


def test_cancel_queued_job_stays_canceled(tmp_path: Path, runner: SwinIRRunner):
    """A job that is canceled while QUEUED must not transition to RUNNING."""
    fs = FileStore(root=str(tmp_path / "storage"))
    js = JobStore(db_path=str(tmp_path / "test.db"))
    jm = JobManager(store=js, file_store=fs, pipeline=Pipeline(
        runner=runner, tiler=Tiler(64, 16), blender=SeamBlender()
    ))
    # Don't create a real job — simulate the QUEUED state directly
    from app.models.job import Job
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    jm._cache["q1"] = Job(
        id="q1", status=JobStatus.QUEUED, stage=None, progress=0.0,
        scale=2, input_path="/nope", output_path=None, error=None,
        created_at=now, updated_at=now,
    )
    canceled = asyncio.run(jm.cancel("q1"))
    assert canceled is True
    final = jm.get("q1")
    assert final is not None
    assert final.status is JobStatus.CANCELED
