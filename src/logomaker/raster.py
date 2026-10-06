"""Raster helpers for audits: ink masks, connected components and an erosion-based minimum feature width."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
from scipy import ndimage

_STRUCTURE = np.ones((3, 3), dtype=bool)


def load_rgba(png: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))


def ink_mask(png: bytes, threshold: int = 128) -> np.ndarray:
    """True where there is ink: opaque pixels of a transparent render, or dark pixels of an opaque one."""
    arr = load_rgba(png)
    alpha = arr[..., 3]
    if (alpha < 255).any():
        return alpha > threshold
    lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    return lum < threshold


def component_count(mask: np.ndarray) -> int:
    return int(ndimage.label(mask, structure=_STRUCTURE)[1])


def min_feature_px(mask: np.ndarray) -> float:
    """Erode until a component vanishes; the thinnest feature is about 2k-1 pixels wide after k erosions."""
    if not mask.any():
        return 0.0
    original = component_count(mask)
    current = mask.copy()
    k = 0
    while current.any() and component_count(current) >= original:
        current = ndimage.binary_erosion(current, structure=_STRUCTURE, border_value=1)
        k += 1
        if k > max(mask.shape):
            break
    return float(max(1, 2 * k - 1))
