import io

import numpy as np
from PIL import Image, ImageDraw

from logomaker.raster import component_count, ink_mask, min_feature_px


def png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_ink_mask_from_opaque_and_transparent_images():
    opaque = Image.new("RGB", (50, 50), "white")
    ImageDraw.Draw(opaque).rectangle([10, 10, 29, 29], fill="black")
    mask = ink_mask(png_bytes(opaque))
    assert mask.shape == (50, 50) and mask.sum() == 400
    transparent = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    ImageDraw.Draw(transparent).rectangle([0, 0, 9, 9], fill=(20, 20, 20, 255))
    assert ink_mask(png_bytes(transparent)).sum() == 100


def test_component_count_and_min_feature():
    mask = np.zeros((100, 100), dtype=bool)
    mask[10:20, 10:90] = True  # a 10 px tall bar
    mask[50:70, 50:70] = True  # a separate 20 px square
    assert component_count(mask) == 2
    assert 9 <= min_feature_px(mask) <= 11
    assert min_feature_px(np.zeros((5, 5), dtype=bool)) == 0.0
    thin = np.zeros((40, 40), dtype=bool)
    thin[20, 5:35] = True
    assert min_feature_px(thin) == 1.0
