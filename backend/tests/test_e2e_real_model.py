"""End-to-end test that uses the real SwinIR model if weights are present.

Skipped automatically when no checkpoint is in the models/ directory.
"""
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.config import get_settings
from app.pipeline.orchestrator import Pipeline
from app.pipeline.runner import SwinIRRunner
from app.pipeline.seam import SeamBlender
from app.pipeline.tiler import Tiler
from app.services.file_store import FileStore
from app.services.job_manager import JobManager
from app.services.job_store import JobStore


def _real_ckpt(scale: int) -> Path | None:
    s = get_settings()
    p = Path(s.model_dir) / f"SwinIR_REALSR_X{scale}.pth"
    return p if p.exists() else None


@pytest.mark.parametrize("scale", [4])
def test_real_swinir_end_to_end(tmp_path: Path, scale: int):
    ckpt = _real_ckpt(scale)
    if ckpt is None:
        pytest.skip(f"no checkpoint at {ckpt}")
    fs = FileStore(root=str(tmp_path / "storage"))
    js = JobStore(db_path=str(tmp_path / "test.db"))
    runner = SwinIRRunner(model_path=str(ckpt), scale=scale, device="cpu")
    runner.warmup()
    pipeline = Pipeline(
        runner=runner,
        tiler=Tiler(tile_size=192, overlap=24),
        blender=SeamBlender(),
    )
    jm = JobManager(store=js, file_store=fs, pipeline=pipeline, flush_interval=0.05)
    app = create_app(job_manager=jm)
    with TestClient(app) as client:
        # Build a small input
        buf = io.BytesIO()
        Image.new("RGB", (96, 96), (200, 100, 50)).save(buf, format="PNG")
        r = client.post(
            "/api/jobs",
            files={"file": ("in.png", buf.getvalue(), "image/png")},
            data={"scale": str(scale)},
        )
        assert r.status_code == 201, r.text
        jid = r.json()["id"]
        # Poll up to 60s
        import time
        deadline = time.time() + 60
        while time.time() < deadline:
            r = client.get(f"/api/jobs/{jid}")
            st = r.json()["status"]
            if st == "done":
                break
            if st == "failed":
                pytest.fail(f"job failed: {r.json()}")
            time.sleep(0.5)
        else:
            pytest.fail("timeout")
        # Output
        r = client.get(f"/api/jobs/{jid}/output")
        assert r.status_code == 200
        out = Image.open(io.BytesIO(r.content))
        assert out.size == (96 * scale, 96 * scale)
    jm.shutdown()
