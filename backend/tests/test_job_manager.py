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


def test_create_queues_job(jm: JobManager, tmp_path: Path):
    inp = tmp_path / "input.png"
    from PIL import Image
    Image.new("RGB", (50, 50), (255, 0, 0)).save(inp)
    job = asyncio.get_event_loop().run_until_complete(
        jm.create(input_path=str(inp), scale=2)
    )
    assert job.status in (JobStatus.QUEUED, JobStatus.RUNNING)
    assert job.scale == 2


def test_get_returns_latest_state(jm: JobManager, tmp_path: Path):
    inp = tmp_path / "input.png"
    from PIL import Image
    Image.new("RGB", (50, 50), (255, 0, 0)).save(inp)
    job = asyncio.get_event_loop().run_until_complete(
        jm.create(input_path=str(inp), scale=2)
    )
    got = jm.get(job.id)
    assert got is not None
    assert got.id == job.id
