"""Build SwinIR networks with the canonical configs from the official repo.

We use `basicsr.archs.swinir_arch.SwinIR` to avoid maintaining a parallel
network definition. Each scale uses a config that matches the checkpoint
we download from the official SwinIR releases.

Checkpoint mapping (verified by inspecting each .pth file's state_dict):
  X2 (002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth):
      depths=[6,6,6,6], embed_dim=60, upsampler=pixelshuffledirect
  X4 (003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN.pth):
      depths=[6,6,6,6,6,6], embed_dim=180, upsampler=nearest+conv
  X8 (001_classicalSR_DIV2K_s48w8_SwinIR-M_x8.pth):
      depths=[6,6,6,6,6,6], embed_dim=180, upsampler=pixelshuffle
"""
from __future__ import annotations

from basicsr.archs.swinir_arch import SwinIR

# Scale → (depths, embed_dim, upsampler, img_size)  — each tuple matches a checkpoint file.
_SCALE_CONFIGS: dict[int, tuple[list[int], int, str, int]] = {
    2: ([6, 6, 6, 6],        60, "pixelshuffledirect", 64),    # SwinIR-S (lightweight)
    4: ([6, 6, 6, 6, 6, 6], 180, "nearest+conv",       64),    # SwinIR-M (Real-World SR)
    8: ([6, 6, 6, 6, 6, 6], 180, "pixelshuffle",        48),    # SwinIR-M (Classical SR)
}


def build_swinir(scale: int) -> SwinIR:
    """Construct a SwinIR network for the given scale.

    Raises ValueError if scale not in {2, 4, 8}.
    The returned model's state_dict is loadable from the checkpoint file
    in models/SwinIR_REALSR_X{scale}.pth (downloaded from the official
    SwinIR GitHub releases).
    """
    if scale not in _SCALE_CONFIGS:
        raise ValueError(f"unsupported scale: {scale}")
    depths, embed_dim, upsampler, img_size = _SCALE_CONFIGS[scale]
    return SwinIR(
        upscale=scale,
        in_chans=3,
        img_size=img_size,
        window_size=8,
        img_range=1.0,
        depths=depths,
        embed_dim=embed_dim,
        num_heads=[6] * len(depths),   # 1 head per residual group
        mlp_ratio=2,
        upsampler=upsampler,
        resi_connection="1conv",
    )
