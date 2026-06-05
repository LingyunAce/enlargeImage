"""Compatibility shim loaded automatically by Python at startup.

basicsr 1.4.2 imports `from torchvision.transforms.functional_tensor import
rgb_to_grayscale`, but that private module was removed in torchvision 0.16+.
The project pins torchvision 0.19.1, so importing basicsr raises
ModuleNotFoundError on first use.

This module runs at interpreter startup (placed in backend/ which is on
sys.path during normal `cd backend && python ...` invocations) and registers
a shim under `torchvision.transforms.functional_tensor` that re-exports the
public API. The shim only defines the one symbol basicsr actually touches,
so the surface area is minimal.
"""
from __future__ import annotations

import sys
import types

try:
    import torchvision  # noqa: F401
except ImportError:
    # torchvision not installed yet; nothing to shim.
    pass
else:
    try:
        from torchvision.transforms.functional import rgb_to_grayscale  # noqa: F401
    except ImportError:
        pass
    else:
        if "torchvision.transforms.functional_tensor" not in sys.modules:
            shim = types.ModuleType("torchvision.transforms.functional_tensor")
            shim.rgb_to_grayscale = rgb_to_grayscale  # type: ignore[attr-defined]
            sys.modules["torchvision.transforms.functional_tensor"] = shim
