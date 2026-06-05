"""Split an image into overlapping tiles for tiled inference."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TileRequest:
    x: int
    y: int
    w: int
    h: int
    out_w: int
    out_h: int


class Tiler:
    def __init__(self, tile_size: int, overlap: int) -> None:
        if tile_size <= 0 or overlap < 0 or overlap >= tile_size:
            raise ValueError("invalid tile_size/overlap")
        self.tile_size = tile_size
        self.overlap = overlap
        self.step = tile_size - overlap

    def _stops(self, dim: int) -> list[int]:
        """Return start positions along one axis. Last tile may be clipped."""
        if dim <= self.tile_size:
            return [0]
        stops = list(range(0, dim - self.tile_size + 1, self.step))
        # Always include a final tile covering the right/bottom edge
        if stops[-1] + self.tile_size < dim:
            stops.append(dim - self.tile_size)
        return stops

    def _sizes(self, dim: int, stops: list[int]) -> list[int]:
        return [min(self.tile_size, dim - s) for s in stops]

    def split(self, image: np.ndarray, scale: int) -> list[TileRequest]:
        h, w = image.shape[:2]
        ys = self._stops(h)
        hs = self._sizes(h, ys)
        xs = self._stops(w)
        ws = self._sizes(w, xs)
        out: list[TileRequest] = []
        for y, th in zip(ys, hs):
            for x, tw in zip(xs, ws):
                out.append(
                    TileRequest(
                        x=x, y=y, w=tw, h=th,
                        out_w=tw * scale, out_h=th * scale,
                    )
                )
        return out

    def expected_count(self, h: int, w: int) -> int:
        return len(self._stops(h)) * len(self._stops(w))
