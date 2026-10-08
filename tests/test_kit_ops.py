import math

import pytest
import skia

from logomaker.kit.ops import (
    _emit,
    _parse,
    align,
    center,
    cut,
    delete_node,
    fit,
    intersect,
    mirror_x,
    mirror_y,
    move_node,
    nodes,
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
from logomaker.kit.primitives import bezier, circle, line, polygon, rect, rect_centered, ring, spline
from logomaker.kit.shape import Shape, normalize_winding, path_from_commands
from logomaker.kit.text import glyph
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


# Hole centres for the sweep: the hole grown to 3r stays inside the square inset by 2r while |x|, |y| <= 150 (the gap at
# 150 is 50 - 5r), so only the r = 10 hole at 150 touches the inset square's edge.
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


def test_insets_beside_a_hole_near_an_edge():
    # Holes with 4d - 2 units of material between them and the nearest outer edge (d the inset): the round-4 grow-back test
    # made its own tangency there and emptied the inset. Exact areas: the outline shrinks by d a side, the hole grows by d.
    cases = [
        ((400, 400), (-112, 0), 10, 20, 360**2 - math.pi * 30**2),  # exact 126772.6, measured 126764.4
        ((400, 400), (112, 0), 10, 20, 360**2 - math.pi * 30**2),  # the mirror image always worked; measured 126764.4
        ((400, 400), (-130, 0), 8, 16, 368**2 - math.pi * 24**2),  # exact 133614.4, measured 133609.2
        ((400, 400), (-157, 0), 5, 10, 380**2 - math.pi * 15**2),  # exact 143693.1, measured 143691.1
        ((600, 300), (0, 107), 5, 10, 580 * 280 - math.pi * 15**2),  # exact 161693.1, measured 161691.1
        ((400, 400), (-150, 0), 4, 12, 376**2 - math.pi * 16**2),  # exact 140571.8, measured 140569.4 (an island ring dropped)
    ]
    for (w, h), (cx, cy), r, d, expected in cases:
        inset = offset(subtract(rect_centered(0, 0, w, h), circle(cx, cy, r)), -d)
        assert not inset.is_empty and math.isclose(inset.area, expected, rel_tol=0.01), (w, h, cx, cy, r, d, inset.area)


# Hole centres either side of the centre on both axes, for the sweep below. The grown hole (3r) stays inside the square
# inset by 2r at all of them for every r swept, as it does at the per-r position 202 - 9r from the centre, where the
# material between the hole and the outer edge is 8r - 2 wide (4d - 2 for d = 2r).
SIDE_HOLE_POSITIONS = [(-150, 0), (-130, 0), (-112, 0), (-100, 0), (100, 0), (112, 0), (130, 0), (150, 0), (0, 100), (0, -100)]


@pytest.mark.parametrize("r", [3, 4, 5, 6, 8, 10])
def test_holes_either_side_of_the_centre_inset_alike(r):
    tight = 202 - 9 * r
    for cx, cy in SIDE_HOLE_POSITIONS + [(-tight, 0), (tight, 0), (0, -tight), (0, tight)]:
        inset = offset(subtract(rect_centered(0, 0, 400, 400), circle(cx, cy, r)), -2 * r)
        expected = (400 - 4 * r) ** 2 - math.pi * (3 * r) ** 2
        assert not inset.is_empty and math.isclose(inset.area, expected, rel_tol=0.01), (r, cx, cy, inset.area)


def test_insets_that_leave_nothing_are_empty():
    # Each of these leaves at most a line or a point. The band subtraction returns nothing, and a hundredth of a unit
    # shallower the inset is only a hairline or a speck (about 0.02 times its length, or less), far under distance².
    for shape, d in (
        (line(-100, 0, 100, 0, 40), 20),
        (ring(0, 0, 100, 30), 15),
        (rect(0, 0, 20, 100), 10),
        (rect(0, 0, 40, 40), 20),
        (circle(0, 0, 50), 50),
    ):
        assert offset(shape, -d).is_empty, (shape.bounds, d)


def test_an_inset_is_measured_to_the_curve_not_to_coarse_chords():
    # A bowl drawn as one half-turn cubic. Flattened at the default 16 steps, the outline's chords fall up to 2.3 units
    # inside the curve, more than the island test's tolerance, and the whole inset would be dropped. Exact areas from a
    # raster of each pixel's exact distance to the outline (6 px per unit).
    for R, d, exact in ((200, 10, 54018.3), (200, 40, 28445.9), (400, 20, 215942.7)):  # measured 54036.5, 28479.1, 216031.8
        k = 4 / 3 * R
        bowl = bezier([(0, -R), (k, -R), (k, R), (0, R), (0, R / 3), (0, -R / 3), (0, -R)])
        inset = offset(bowl, -d)
        assert not inset.is_empty and math.isclose(inset.area, exact, rel_tol=0.01), (R, d, inset.area)


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


def test_nodes_lists_on_curve_points_in_path_order():
    square = rect(0, 0, 100, 100)
    found = nodes(square)
    assert [(n.index, n.subpath) for n in found] == [(0, 0), (1, 0), (2, 0), (3, 0)]
    assert {(n.x, n.y) for n in found} == {(0, 0), (100, 0), (100, 100), (0, 100)}
    assert all(not n.smooth for n in found)
    disc = nodes(circle(0, 0, 100))
    assert len(disc) == 4 and all(n.smooth for n in disc)
    assert len(nodes(spline([(0, 300), (300, 0), (0, -300), (-300, 0)]))) == 4


def test_move_node_moves_the_point_and_its_handles():
    square = rect(0, 0, 100, 100)
    corner = next(n for n in nodes(square) if (n.x, n.y) == (100, 100))
    moved = move_node(square, corner.index, 50, 0)
    assert {(n.x, n.y) for n in nodes(moved)} == {(0, 0), (100, 0), (150, 100), (0, 100)}
    assert math.isclose(moved.area, 100 * 100 + 50 * 100 / 2)
    disc = circle(0, 0, 100)
    top = next(n for n in nodes(disc) if n.y > 99)
    taller = move_node(disc, top.index, 0, 50)
    assert math.isclose(taller.bounds.y1, 150, abs_tol=0.01) and taller.area > disc.area
    assert taller.anchor_count() == 4  # the handles moved with the node, no new segment
    with pytest.raises(ValueError, match="no node 9"):
        move_node(square, 9, 1, 1)
    with pytest.raises(ValueError, match="no node -1"):
        move_node(square, -1, 1, 1)
    with pytest.raises(ValueError, match="no node 0; the shape has 0 nodes"):
        delete_node(Shape.empty(), 0)


def test_delete_node_joins_the_neighbours():
    square = rect(0, 0, 100, 100)
    corner = next(n for n in nodes(square) if (n.x, n.y) == (100, 100))
    tri = delete_node(square, corner.index)
    assert tri.anchor_count() == 3 and math.isclose(tri.area, 5000)
    disc = circle(0, 0, 100)
    three = delete_node(disc, nodes(disc)[0].index)
    assert three.anchor_count() == 3 and three.area < disc.area
    open_curve = spline([(-300, 0), (0, 200), (300, 0)], closed=False)  # filled, so bezier closes it: three nodes, one implied line
    with pytest.raises(ValueError, match="a contour keeps at least three nodes"):
        delete_node(open_curve, nodes(open_curve)[1].index)
    open_path = Shape(path_from_commands([("M", [(0.0, 0.0)]), ("L", [(100.0, 0.0)]), ("L", [(100.0, 100.0)])]))
    with pytest.raises(ValueError, match="an open contour's endpoint cannot be deleted"):
        delete_node(open_path, nodes(open_path)[0].index)
    assert delete_node(open_path, nodes(open_path)[1].index).anchor_count() == 2


def test_cut_splits_along_a_line_and_keeps_text_metrics():
    square = rect(-100, -100, 200, 200)
    left, right = cut(square, 0, -500, 0, 500)  # travelling up: left is x < 0
    assert math.isclose(left.area, 20000) and math.isclose(right.area, 20000)
    assert left.bounds.x1 <= 0.01 and right.bounds.x0 >= -0.01
    whole, nothing = cut(square, 500, -500, 500, 500)  # a line that misses: everything is on the left
    assert math.isclose(whole.area, 40000) and nothing.is_empty
    k = glyph("K", "Fira Code", weight=700, cap_height=600)
    top, bottom = cut(k, -500, 300, 500, 300)
    assert hasattr(top, "cap_height") and top.cap_height == k.cap_height and bottom.area > 0


def test_delete_node_on_a_glyph_keeps_it_a_text_shape():
    o = glyph("O", "Fira Code", weight=700, cap_height=600)
    first = nodes(o)[0].index
    fewer = delete_node(o, first)
    assert hasattr(fewer, "cap_height") and fewer.anchor_count() == o.anchor_count() - 1


def test_cut_counts_a_free_segment_only_for_an_off_grid_line():
    square = rect(-100, -100, 200, 200)
    top, bottom = cut(square, -500, 25, 500, 25)  # horizontal, through a grid point
    assert top.free_segments == 0 and bottom.free_segments == 0
    dx, dy = math.cos(math.radians(20)), math.sin(math.radians(20))
    left, right = cut(square, 0, 0, dx, dy)  # 20 degrees is off the 15-degree step
    assert left.free_segments == 1 and right.free_segments == 1
    whole, nothing = cut(left, 500, -500, 500, 500)  # misses: the whole side keeps its count, the empty side has none
    assert whole.free_segments == 1 and nothing.free_segments == 0 and nothing.is_empty
    again, _ = cut(top, 0, -500, 0, 500)
    assert again.free_segments == 0  # grid cuts never accumulate
    with pytest.raises(ValueError, match="cut needs two distinct points"):
        cut(square, 10, 10, 10, 10)


def test_parse_and_emit_round_trip_a_primitive_exactly():
    for shape in (rect(0, 0, 100, 50), polygon([(0, 0), (100, 0), (50, 75)])):
        assert list(_emit(shape, _parse(shape)).commands()) == list(shape.commands())
