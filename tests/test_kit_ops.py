import math

import pytest
import skia

from logomaker.kit.ops import (
    align,
    center,
    fit,
    intersect,
    mirror_x,
    mirror_y,
    offset,
    rotate,
    scale,
    stroke,
    subtract,
    translate,
    union,
    xor,
)
from logomaker.kit.optical import compensate_stroke, optical_center, overshoot
from logomaker.kit.primitives import circle, polygon, rect, rect_centered, ring
from logomaker.kit.shape import Shape, normalize_winding
from tests.test_kit_shape import signed_area


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


def test_ops_keep_the_curves_they_are_given():
    # Re-winding keeps each contour's own verbs, so anchors match what pathops and the stroker drew: a circle stays
    # four conics (4 anchors), never sixteen cubics.
    c = circle(0, 0, 100)
    assert mirror_x(c).anchor_count() == mirror_y(c).anchor_count() == 4
    assert union(c, circle(300, 0, 100)).anchor_count() == 8
    assert subtract(ring(0, 0, 100, 20), rect(90, -5, 20, 10)).anchor_count() == 11  # pathops splits the outline at the notch
    assert stroke(c, 10).anchor_count() == 32  # skia's stroker draws each side of a circle as 16 quads


def test_a_trailing_move_survives_rewinding():
    p = skia.Path()
    p.addRect(skia.Rect.MakeLTRB(0, 0, 10, 10))
    p.moveTo(50, 50)  # a move with nothing after it draws nothing; Simplify returns a convex path like this verbatim
    square = Shape(p)
    assert math.isclose(Shape(normalize_winding(p)).area, 100)
    for result in (mirror_x(square), mirror_y(square), union(square)):
        assert math.isclose(result.area, 100) and result.anchor_count() == 4


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


def test_inward_offsets_shrink_by_the_distance_or_vanish():
    assert offset(circle(0, 0, 10), -20).is_empty  # thinner than twice the distance: nothing is left
    assert offset(circle(0, 0, 100), -150).is_empty
    assert math.isclose(offset(circle(0, 0, 100), -30).area, math.pi * 70**2, rel_tol=0.01)
    b = offset(rect(0, 0, 200, 100), -10).bounds
    assert math.isclose(b.w, 180, abs_tol=1e-3) and math.isclose(b.h, 80, abs_tol=1e-3)
    # A dot thinner than twice the distance inside a ring's hole vanishes; the ring around it only thins. (The stroker
    # draws offsets to about 0.25 units, which costs this thin ring about 1% of its area.)
    target = offset(union(ring(0, 0, 100, 40), circle(0, 0, 10)), -15)
    assert math.isclose(target.area, math.pi * (85**2 - 75**2), rel_tol=0.02) and len(target.subpaths()) == 2


# Hole centres for the sweep: the hole grown to 3r stays inside the square inset by 2r while |x|, |y| <= 150, and at
# 150 it touches the inset square's edge.
HOLE_POSITIONS = [(0, 0), (0, 100), (100, 0), (-150, 0), (0, -150), (150, 150), (-150, 150), (75, -40), (-33.25, 120.5), (140, -137.75)]


def test_insets_where_the_band_lands_on_a_hole():
    # Inset by twice a hole's radius, the band's folded inner edge lands on the hole itself: the boolean leaves slivers
    # and duplicate contours there, which must neither empty the inset nor fill the hole.
    hole3 = subtract(rect_centered(0, 0, 300, 300), circle(0, 0, 3))
    assert math.isclose(offset(hole3, -6).area, 288**2 - math.pi * 9**2, rel_tol=0.01)  # measured 82688.8
    assert math.isclose(offset(ring(0, 0, 100, 90), -20).area, math.pi * (80**2 - 30**2), rel_tol=0.01)  # measured 17272.6
    hole5 = subtract(rect_centered(0, 0, 200, 200), circle(0, 0, 5))
    assert math.isclose(offset(hole5, -10).area, 180**2 - math.pi * 15**2, rel_tol=0.01)  # measured 31691.1
    assert offset(ring(0, 0, 100, 80), -40).is_empty  # exactly twice the distance thick: nothing is left
    raising = subtract(rect_centered(0, 0, 400, 400), circle(0, 100, 8))  # pathops raises on this band subtraction
    assert math.isclose(offset(raising, -16).area, 368**2 - math.pi * 24**2, rel_tol=0.01)  # measured 133625.4
    assert offset(Shape.empty(), -0.005).is_empty and offset(Shape.empty(), -5).is_empty  # the retry needs room to step back


@pytest.mark.parametrize("r", [3, 4, 5, 6, 8, 10])
def test_a_square_with_a_hole_insets_by_twice_the_hole_radius(r):
    for cx, cy in HOLE_POSITIONS:
        inset = offset(subtract(rect_centered(0, 0, 400, 400), circle(cx, cy, r)), -2 * r)
        expected = (400 - 4 * r) ** 2 - math.pi * (3 * r) ** 2  # the square shrinks by 2r a side; the hole grows to 3r
        assert not inset.is_empty and math.isclose(inset.area, expected, rel_tol=0.01), (r, cx, cy)


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
    for w, h in ((0, 50), (50, -1), (math.nan, 50)):
        with pytest.raises(ValueError, match="fit needs a positive target width and height"):
            fit(circle(0, 0, 100), w, h)


def test_mirrors_keep_the_kits_contour_directions():
    def directions(shape):
        return [signed_area(part.flatten()[0]) > 0 for part in shape.subpaths()]

    original = ring(0, 0, 100, 20)
    assert directions(original) == [True, False]  # outline counter-clockwise, hole clockwise
    assert directions(mirror_x(original, 30)) == directions(mirror_y(original, -5)) == [True, False]
    assert math.isclose(mirror_x(original).area, original.area, rel_tol=1e-6)  # skia stores points as float32


def test_optical_helpers():
    assert math.isclose(overshoot(circle(0, 0, 100)).bounds.y1, 101.5, abs_tol=0.01)
    widths = compensate_stroke(100)
    assert (widths.vertical, widths.horizontal, widths.curve) == (100, 92, 105)
    assert optical_center(rect(0, 0, 10, 20)) == (5, 10)
