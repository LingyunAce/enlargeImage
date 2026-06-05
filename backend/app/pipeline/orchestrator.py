"""Orchestrate tile -> infer -> blend -> encode. Pure function, no I/O."""
from __future__ import annotations

from typing import Callable

import numpy as np

from app.models.job import ProgressEvent
from app.pipeline.runner import SwinIRRunner
from app.pipeline.seam import SeamBlender
from app.pipeline.tiler import Tiler

__all__ = ["Pipeline", "ProgressEvent"]


class Pipeline:
    def __init__(self, runner: SwinIRRunner, tiler: Tiler, blender: SeamBlender) -> None:
        self.runner = runner
        self.tiler = tiler
        self.blender = blender

    def run(
        self,
        image: np.ndarray,
        scale: int,
        on_progress: Callable[[ProgressEvent], None],
    ) -> np.ndarray:
        if scale != self.runner.scale:
            raise ValueError(
                f"requested scale {scale} != runner scale {self.runner.scale}"
            )
        h, w = image.shape[:2]
        canvas_h, canvas_w = h * scale, w * scale

        # Stage 1: tiling
        tiles = self.tiler.split(image, scale=scale)
        on_progress(ProgressEvent(stage="tiling", current=1, total=1))

        # Stage 2: inference
        results = []
        total = len(tiles)
        for i, req in enumerate(tiles, start=1):
            tile = image[req.y:req.y + req.h, req.x:req.x + req.w, :]
            out_tile = self.runner.infer(tile)
            # Translate to OUTPUT-space coordinates for the blender
            out_req = _to_output_coords(req, scale)
            results.append((out_req, out_tile))
            on_progress(ProgressEvent(stage="inference", current=i, total=total))

        # Stage 3: blending
        on_progress(ProgressEvent(stage="blending", current=1, total=1))
        canvas = self.blender.blend(results, canvas_h=canvas_h, canvas_w=canvas_w)

        # Stage 4: encoding (numpy array is the canonical output; encoder
        # downstream may convert to PNG). Emit one event for the progress UI.
        on_progress(ProgressEvent(stage="encoding", current=1, total=1))
        return canvas


def _to_output_coords(req, scale: int):
    """Return a copy of req translated to output (canvas) coordinates.

    SwinIRRunner.infer expands (h, w) -> (h*scale, w*scale). The tile is placed
    in the output canvas at (req.y * scale, req.x * scale).
    """
    from dataclasses import replace
    return replace(
        req,
        y=req.y * scale,
        x=req.x * scale,
        h=req.h * scale,
        w=req.w * scale,
        out_w=req.w * scale,
        out_h=req.h * scale,
    )
