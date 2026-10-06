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
    assert min_feature_px(mask.astype(np.uint8)) == min_feature_px(mask)  # a 0/1 integer mask measures like a bool one
    assert min_feature_px(np.zeros((5, 5), dtype=bool)) == 0.0
    thin = np.zeros((40, 40), dtype=bool)
    thin[20, 5:35] = True
    assert min_feature_px(thin) == 1.0


def test_component_count_joins_shapes_touching_at_a_corner():
    mask = np.zeros((20, 20), dtype=bool)
    mask[2:6, 2:6] = True
    mask[6:10, 6:10] = True  # meets the first square only at a corner
    assert component_count(mask) == 1


def test_min_feature_stops_when_any_original_component_vanishes():
    mask = np.zeros((200, 200), dtype=bool)
    mask[10:20, 10:190] = True  # a 10 px bar: vanishes after 5 erosions
    mask[60:100, 20:60] = True  # two 40 px blobs ...
    mask[60:100, 140:180] = True
    mask[77:83, 60:140] = True  # ... joined by a 6 px neck, which splits them after 3 erosions
    assert component_count(mask) == 2
    assert 9 <= min_feature_px(mask) <= 11  # the bar's width, not the blobs'


def test_min_feature_treats_the_canvas_border_as_background():
    mask = np.zeros((100, 100), dtype=bool)
    mask[0:10, 10:90] = True  # a 10 px bar flush with the top edge must erode from both sides
    assert 9 <= min_feature_px(mask) <= 11
