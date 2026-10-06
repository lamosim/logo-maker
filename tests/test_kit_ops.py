import math

import pytest

from logomaker.kit.ops import align, center, fit, intersect, mirror_x, mirror_y, offset, rotate, scale, stroke, subtract, translate, union, xor
from logomaker.kit.optical import compensate_stroke, optical_center, overshoot
from logomaker.kit.primitives import circle, polygon, rect, rect_centered, ring
from logomaker.kit.shape import Shape


def test_booleans():
    a = rect(0, 0, 100, 100)
    b = rect(50, 50, 100, 100)
    assert math.isclose(union(a, b).area, 17500)
    assert math.isclose(subtract(a, b).area, 7500)
    assert math.isclose(intersect(a, b).area, 2500)
    assert math.isclose(xor(a, b).area, 15000)
    assert union(a, b).free_segments == 0
    assert union(polygon([(0, 0), (10, 0), (0, 10)], free=True), b).free_segments == 3
    assert union().is_empty
    assert math.isclose(subtract(circle(0, 0, 100), circle(0, 0, 80)).area, math.pi * (100**2 - 80**2), rel_tol=0.005)
    assert math.isclose(union(ring(0, 0, 100, 20), circle(0, 0, 50)).area, math.pi * (100**2 - 80**2 + 50**2), rel_tol=0.005)
    frame = union(rect(0, 0, 100, 10), rect(0, 90, 100, 10), rect(0, 0, 10, 100), rect(90, 0, 10, 100))
    assert math.isclose(frame.area, 100**2 - 80**2)  # skia winds a hole the union creates like the outline


def test_failed_boolean_raises_value_error():
    broken = polygon([(0, 0), (math.inf, 0), (0, 10)], free=True)  # pathops rejects non-finite paths
    with pytest.raises(ValueError, match="boolean path operation failed") as excinfo:
        union(rect(0, 0, 10, 10), broken)
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    with pytest.raises(ValueError, match="boolean path operation failed") as excinfo:
        union(broken)  # one shape: no Op, straight to Simplify
    assert isinstance(excinfo.value.__cause__, RuntimeError)


def test_stroke_and_offset():
    outline = stroke(rect(0, 0, 100, 100), 10)
    assert math.isclose(outline.area, 4000, rel_tol=0.001)
    grown = offset(rect(0, 0, 100, 100), 10)
    assert (grown.bounds.x0, grown.bounds.y0, grown.bounds.x1, grown.bounds.y1) == (-10, -10, 110, 110)
    shrunk = offset(rect(0, 0, 100, 100), -10)
    assert (shrunk.bounds.x0, shrunk.bounds.x1) == (10, 90) and math.isclose(shrunk.area, 6400, rel_tol=0.001)
    tri = polygon([(0, 0), (10, 0), (0, 10)], free=True)
    assert offset(tri, 5).free_segments == 3  # the band derived from tri is not counted again
    assert offset(tri, -5).free_segments == 3
    s = rect(0, 0, 100, 100)
    same = offset(s, 0)
    assert same is not s and same.path is not s.path and same.to_path_data() == s.to_path_data()
    with pytest.raises(ValueError, match="stroke width must be positive"):
        stroke(s, 0)


def test_transforms():
    r = rect(0, 0, 10, 20)
    b = rotate(r, 90).bounds
    assert (round(b.x0), round(b.y0), round(b.x1), round(b.y1)) == (-20, 0, 0, 10)
    assert translate(r, 5, 5).bounds.x0 == 5
    assert scale(r, 2).bounds.y1 == 40
    assert mirror_x(r).bounds.x0 == -10 and mirror_x(r).bounds.x1 == 0
    assert mirror_y(r).bounds.y0 == -20
    assert r.bounds.x0 == 0  # inputs are not mutated


def test_pivots_and_axes():
    r = rect(0, 0, 10, 20)
    cases = [
        (rotate(r, 90, cx=5, cy=10), (-5, 5, 15, 15)),
        (scale(r, 2, 3, cx=10, cy=20), (-10, -40, 10, 20)),
        (mirror_x(r, 20), (30, 0, 40, 20)),
        (mirror_y(r, 20), (0, 20, 10, 40)),
    ]
    for shape, expected in cases:
        b = shape.bounds
        assert all(math.isclose(v, e, abs_tol=0.01) for v, e in zip((b.x0, b.y0, b.x1, b.y1), expected)), (b, expected)


def test_align_center_fit():
    target = rect(100, 100, 50, 50)
    s = rect_centered(0, 0, 10, 10)
    assert align(s, target, "left").bounds.x0 == 100
    assert align(s, target, "right").bounds.x1 == 150
    assert align(s, target, "bottom").bounds.y0 == 100
    assert align(s, target, "top").bounds.y1 == 150
    assert align(s, target, "center").bounds.cx == 125
    assert align(s, target, "middle").bounds.cy == 125
    c = center(rect(0, 0, 10, 20))
    assert c.bounds.cx == 0 and c.bounds.cy == 0
    tri = center(polygon([(0, 0), (90, 0), (0, 90)]), optical=True)
    cx, cy = tri.centroid
    assert abs(cx) < 0.01 and abs(cy) < 0.01
    f = fit(circle(0, 0, 100), 50, 50, cx=10, cy=10).bounds
    assert math.isclose(f.x0, -15, abs_tol=0.01) and math.isclose(f.y1, 35, abs_tol=0.01)
    with pytest.raises(ValueError, match="fit needs a shape with non-zero width and height"):
        fit(Shape.empty(), 50, 50)


def test_optical_helpers():
    assert math.isclose(overshoot(circle(0, 0, 100)).bounds.y1, 101.5, abs_tol=0.01)
    widths = compensate_stroke(100)
    assert (widths.vertical, widths.horizontal, widths.curve) == (100, 92, 105)
    assert optical_center(rect(0, 0, 10, 20)) == (5, 10)
