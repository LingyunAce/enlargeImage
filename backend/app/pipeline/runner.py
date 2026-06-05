"""Load a SwinIR model once and run inference on single images."""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import torch

from app.models.swinir import build_swinir


class SwinIRRunner:
    """Thread-safe inference wrapper around a single SwinIR network."""

    def __init__(self, model_path: str, scale: int, device: str = "cpu") -> None:
        if not Path(model_path).exists():
            raise FileNotFoundError(f"checkpoint not found: {model_path}")
        self.scale = scale
        self.device = torch.device(device)
        self.model = build_swinir(scale=scale)
        ckpt = torch.load(model_path, map_location=self.device, weights_only=True)
        # basicsr checkpoints store weights under "params"
        state = ckpt.get("params_ema", ckpt.get("params", ckpt))
        self.model.load_state_dict(state, strict=True)
        self.model.eval().to(self.device)
        self._lock = threading.Lock()

    def warmup(self) -> None:
        """Run a dummy forward pass to warm caches (e.g. oneDNN, allocator)."""
        with self._lock:
            with torch.no_grad():
                _ = self.model(torch.zeros(1, 3, 64, 64, device=self.device))

    def infer(self, image: np.ndarray) -> np.ndarray:
        """Run inference. image: (H, W, 3) uint8 RGB -> (H*scale, W*scale, 3) uint8."""
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("image must be (H, W, 3)")
        # To torch: (1, 3, H, W), float32 in [0, 1]
        x = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        x = x.to(self.device)
        with self._lock:
            with torch.no_grad():
                y = self.model(x)
        # Back to numpy: (H*scale, W*scale, 3) uint8
        y = y.squeeze(0).clamp(0.0, 1.0).cpu().permute(1, 2, 0).numpy()
        y = (y * 255.0).round().astype(np.uint8)
        return y
