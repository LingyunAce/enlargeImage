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
