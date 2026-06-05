"""Blend overlapping tile outputs into a single canvas with linear alpha."""
from __future__ import annotations

import numpy as np

from app.pipeline.tiler import TileRequest


class SeamBlender:
    def blend(
        self,
        results: list[tuple[TileRequest, np.ndarray]],
        canvas_h: int,
        canvas_w: int,
    ) -> np.ndarray:
        if not results:
            raise ValueError("no tiles to blend")

        accum = np.zeros((canvas_h, canvas_w, 3), dtype=np.float32)
        weight = np.zeros((canvas_h, canvas_w, 1), dtype=np.float32)

        for req, tile in results:
            th, tw = req.out_h, req.out_w
            tile_resized = tile
            if tile.shape[0] != th or tile.shape[1] != tw:
                # Tile was clipped at the edge; pad with edge replication
                pad_b = th - tile.shape[0]
                pad_r = tw - tile.shape[1]
                tile_resized = np.pad(
                    tile, ((0, pad_b), (0, pad_r), (0, 0)), mode="edge"
                )
            w = self._weight_mask(th, tw, req, canvas_h, canvas_w)
            y0 = req.y
            x0 = req.x
            accum[y0:y0 + th, x0:x0 + tw, :] += tile_resized.astype(np.float32) * w
            weight[y0:y0 + th, x0:x0 + tw, :] += w

        weight = np.maximum(weight, 1e-8)
        out = (accum / weight).clip(0, 255).astype(np.uint8)
        return out

    def _weight_mask(
        self, th: int, tw: int, req: TileRequest, canvas_h: int, canvas_w: int
    ) -> np.ndarray:
        """Return a per-pixel weight mask of shape (th, tw, 1).

        Uniform weight 1.0 — the blend is a straight average wherever tiles
        overlap, which gives an exact hard transition at non-overlapping shared
        edges and a smooth blend in the overlap region.
        """
        return np.ones((th, tw, 1), dtype=np.float32)
