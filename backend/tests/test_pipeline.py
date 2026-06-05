import numpy as np
import pytest
import torch
from pathlib import Path

from app.models.swinir import build_swinir
from app.pipeline.orchestrator import Pipeline, ProgressEvent
from app.pipeline.runner import SwinIRRunner
from app.pipeline.seam import SeamBlender
from app.pipeline.tiler import Tiler


@pytest.fixture
def runner(tmp_path: Path) -> SwinIRRunner:
    net = build_swinir(scale=2)
    p = tmp_path / "ckpt.pth"
    torch.save({"params": net.state_dict()}, str(p))
    return SwinIRRunner(model_path=str(p), scale=2, device="cpu")


def test_pipeline_runs_and_returns_scaled_image(runner: SwinIRRunner):
    pipeline = Pipeline(
        runner=runner,
        tiler=Tiler(tile_size=64, overlap=16),
        blender=SeamBlender(),
    )
    img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    events: list[ProgressEvent] = []

    def cb(ev: ProgressEvent):
        events.append(ev)

    out = pipeline.run(img, scale=2, on_progress=cb)
    assert out.shape == (200, 200, 3)
    assert out.dtype == np.uint8
    # We should have seen at least one event per stage
    stages = {ev.stage for ev in events}
    assert "tiling" in stages
    assert "inference" in stages
    assert "blending" in stages
    assert "encoding" in stages


def test_pipeline_emits_inference_progress_monotonically(runner: SwinIRRunner):
    pipeline = Pipeline(
        runner=runner,
        tiler=Tiler(tile_size=64, overlap=16),
        blender=SeamBlender(),
    )
    img = np.random.randint(0, 256, (200, 200, 3), dtype=np.uint8)
    events: list[ProgressEvent] = []

    def cb(ev: ProgressEvent):
        events.append(ev)

    pipeline.run(img, scale=2, on_progress=cb)
    inf_events = [ev for ev in events if ev.stage == "inference"]
    currents = [ev.current for ev in inf_events]
    assert currents == sorted(currents)
    assert currents[-1] == inf_events[-1].total  # last event reports total
