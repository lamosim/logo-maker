"""Raster helpers. For audits: ink masks, connected components and an erosion-based minimum feature width. For exports:
encoding, sizes and the blank-render check."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageColor
from scipy import ndimage

_STRUCTURE = np.ones((3, 3), dtype=bool)
BACKGROUND_TOLERANCE = 2  # levels per channel: a lossy encoder (JPEG) can round a flat colour by one or two


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


def encoded(image: Image.Image, kind: str, **options) -> bytes:
    """`image` saved as `kind` (PNG, JPEG, WEBP, ICO) with Pillow's `options`."""
    out = io.BytesIO()
    image.save(out, format=kind, **options)
    return out.getvalue()


def image_size(data: bytes) -> tuple[int, int]:
    """The pixel size of an encoded image, read from its header."""
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def blank(data: bytes, background: str | None = None) -> bool:
    """Whether an encoded image shows nothing: spec section 13's "empty or fully transparent" render. Only the caller
    knows what it made. A render on transparent (`background` None) is blank when every pixel is fully transparent,
    and never for filling its canvas in one colour, as a solid mark with no holes does. A raster composed onto
    `background` is blank when every pixel is that colour, opaque (within BACKGROUND_TOLERANCE): the background with
    nothing on it; art that fills its box in another colour is drawn. ink_mask's cut-offs measure ink, not this: they
    would call a faint render blank, and a light mark on light paper."""
    with Image.open(io.BytesIO(data)) as image:
        extrema = image.convert("RGBA").getextrema()
    if background is None:
        return extrema[3][1] == 0
    target = (*ImageColor.getrgb(background)[:3], 255)
    return all(value - BACKGROUND_TOLERANCE <= low and high <= value + BACKGROUND_TOLERANCE
               for (low, high), value in zip(extrema, target, strict=True))


def component_count(mask: np.ndarray) -> int:
    return int(ndimage.label(mask, structure=_STRUCTURE)[1])


def min_feature_px(mask: np.ndarray) -> float:
    """Erode until any original component vanishes; the thinnest feature is about 2k-1 pixels wide after k erosions.

    A thin part attached to a thicker body is not measured, since it vanishes without its whole component vanishing.
    """
    mask = np.asarray(mask, dtype=bool)
    if not mask.any():
        return 0.0
    # Track the original labels, not the count: a component splitting under erosion must not hide another vanishing.
    labels, n = ndimage.label(mask, structure=_STRUCTURE)
    current = mask.copy()
    k = 0
    while current.any() and len(np.unique(labels[current])) == n:
        # Outside the canvas is background: renders crop tight, so edge-touching features must erode from both sides.
        current = ndimage.binary_erosion(current, structure=_STRUCTURE, border_value=0)
        k += 1
        if k > max(mask.shape):
            break
    return float(max(1, 2 * k - 1))
