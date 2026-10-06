import math

import pytest

from logomaker.kit.ops import align, center, fit, intersect, mirror_x, mirror_y, offset, rotate, scale, stroke, subtract, translate, union, xor
from logomaker.kit.optical import compensate_stroke, optical_center, overshoot
from logomaker.kit.primitives import circle, polygon, rect, rect_centered


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


def test_failed_boolean_raises_value_error():
    broken = polygon([(0, 0), (math.inf, 0), (0, 10)], free=True)  # pathops rejects non-finite paths
    with pytest.raises(ValueError, match="boolean path operation failed"):
        union(rect(0, 0, 10, 10), broken)


def test_stroke_and_offset():
    outline = stroke(rect(0, 0, 100, 100), 10)
    assert math.isclose(outline.area, 4000, rel_tol=0.001)
    grown = offset(rect(0, 0, 100, 100), 10)
    assert (grown.bounds.x0, grown.bounds.y0, grown.bounds.x1, grown.bounds.y1) == (-10, -10, 110, 110)
    shrunk = offset(rect(0, 0, 100, 100), -10)
    assert (shrunk.bounds.x0, shrunk.bounds.x1) == (10, 90) and math.isclose(shrunk.area, 6400, rel_tol=0.001)


def test_transforms():
    r = rect(0, 0, 10, 20)
    b = rotate(r, 90).bounds
    assert (round(b.x0), round(b.y0), round(b.x1), round(b.y1)) == (-20, 0, 0, 10)
    assert translate(r, 5, 5).bounds.x0 == 5
    assert scale(r, 2).bounds.y1 == 40
    assert mirror_x(r).bounds.x0 == -10 and mirror_x(r).bounds.x1 == 0
    assert mirror_y(r).bounds.y0 == -20
    assert r.bounds.x0 == 0  # inputs are not mutated


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


def test_optical_helpers():
    assert math.isclose(overshoot(circle(0, 0, 100)).bounds.y1, 101.5, abs_tol=0.01)
    widths = compensate_stroke(100)
    assert (widths.vertical, widths.horizontal, widths.curve) == (100, 92, 105)
    assert optical_center(rect(0, 0, 10, 20)) == (5, 10)
