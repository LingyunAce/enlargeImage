"""Build SwinIR networks with the canonical configs from the official repo.

We use `basicsr.archs.swinir_arch.SwinIR` to avoid maintaining a parallel
network definition. Configurations follow the official Real-World Image
SR setting (4x scale baseline; for 2x / 8x we keep the same window size
and embed_dim — only the upsample module differs).
"""
from __future__ import annotations

from basicsr.archs.swinir_arch import SwinIR


def build_swinir(scale: int) -> SwinIR:
    """Construct a SwinIR network for the given scale.

    The official configs use:
      - embed_dim = 180
      - depths    = [6, 6, 6, 6, 6, 6]
      - num_heads = [6, 6, 6, 6, 6, 6]
      - window_size = 8
      - upsampler  = 'pixelshuffle'
    """
    if scale not in (2, 4, 8):
        raise ValueError(f"unsupported scale: {scale}")
    return SwinIR(
        upscale=scale,
        in_chans=3,
        img_size=64,
        window_size=8,
        img_range=1.0,
        depths=[6, 6, 6, 6, 6, 6],
        embed_dim=180,
        num_heads=[6, 6, 6, 6, 6, 6],
        mlp_ratio=2,
        upsampler="pixelshuffle",
        resi_connection="1conv",
    )
