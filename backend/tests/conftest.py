import io
from pathlib import Path
from typing import Iterator

import numpy as np
import pytest
from PIL import Image

from app.main import create_app
from app.services.file_store import FileStore
from app.services.job_manager import JobManager
from app.services.job_store import JobStore


class FakeRunner:
    """Returns a deterministic upscaled image. scale=2 -> (2H, 2W)."""
    def __init__(self, scale: int = 2):
        self.scale = scale

    def supports_scale(self, scale: int) -> bool:
        return scale == self.scale

    def infer(self, image: np.ndarray, scale: int | None = None) -> np.ndarray:
        h, w = image.shape[:2]
        s = scale if scale is not None else self.scale
        return np.zeros((h * s, w * s, 3), dtype=np.uint8)


@pytest.fixture
def app_with_fake_runner(tmp_path: Path) -> Iterator:
    """Create a FastAPI app wired with a fake runner (no torch)."""
    from fastapi.testclient import TestClient
    from app.pipeline.orchestrator import Pipeline
    from app.pipeline.seam import SeamBlender
    from app.pipeline.tiler import Tiler

    fs = FileStore(root=str(tmp_path / "storage"))
    js = JobStore(db_path=str(tmp_path / "test.db"))
    pipeline = Pipeline(
        runner=FakeRunner(scale=2),  # type: ignore
        tiler=Tiler(tile_size=64, overlap=16),
        blender=SeamBlender(),
    )
    jm = JobManager(store=js, file_store=fs, pipeline=pipeline, flush_interval=0.05)
    app = create_app(job_manager=jm)
    with TestClient(app) as client:
        # Run startup tasks
        yield client, jm
    jm.shutdown()
