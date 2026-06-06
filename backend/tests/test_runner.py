import numpy as np
import pytest
import torch
from pathlib import Path

from app.models.swinir import build_swinir
from app.pipeline.runner import SwinIRRunner


@pytest.fixture
def dummy_ckpt(tmp_path: Path) -> str:
    """Build a tiny SwinIR and save it. Used so the runner has real weights."""
    net = build_swinir(scale=2)
    p = tmp_path / "tiny_swinir_x2.pth"
    torch.save({"params": net.state_dict()}, str(p))
    return str(p)


def test_runner_loads_and_exposes_scale(dummy_ckpt: str):
    runner = SwinIRRunner(model_path=dummy_ckpt, scale=2, device="cpu")
    assert runner.scale == 2


def test_runner_infer_returns_correct_shape(dummy_ckpt: str):
    runner = SwinIRRunner(model_path=dummy_ckpt, scale=2, device="cpu")
    img = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
    out = runner.infer(img)
    assert out.shape == (128, 128, 3)
    assert out.dtype == np.uint8


def test_runner_output_values_in_range(dummy_ckpt: str):
    runner = SwinIRRunner(model_path=dummy_ckpt, scale=2, device="cpu")
    img = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
    out = runner.infer(img)
    assert out.min() >= 0
    assert out.max() <= 255


def test_runner_infer_is_deterministic(dummy_ckpt: str):
    runner = SwinIRRunner(model_path=dummy_ckpt, scale=2, device="cpu")
    img = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
    a = runner.infer(img)
    b = runner.infer(img)
    np.testing.assert_array_equal(a, b)


def test_multi_runner_routes_by_scale(tmp_path: Path):
    """MultiRunner dispatches to the correct underlying runner by scale."""
    from app.pipeline.runner import MultiRunner, SwinIRRunner

    runners = {}
    for scale in (2, 4):
        net = build_swinir(scale=scale)
        p = tmp_path / f"ckpt_{scale}.pth"
        torch.save({"params": net.state_dict()}, str(p))
        runners[scale] = SwinIRRunner(model_path=str(p), scale=scale, device="cpu")

    multi = MultiRunner(runners)
    assert multi.scale == (2, 4)
    assert multi.supports_scale(2) is True
    assert multi.supports_scale(3) is False
    assert multi.supports_scale(8) is False

    # Infer with scale=2
    img = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
    out2 = multi.infer(img, scale=2)
    assert out2.shape == (64, 64, 3)

    # Infer with scale=4
    out4 = multi.infer(img, scale=4)
    assert out4.shape == (128, 128, 3)

    # Wrong scale raises
    with pytest.raises(ValueError):
        multi.infer(img, scale=3)
