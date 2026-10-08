import math

import pytest

from logomaker.kit.primitives import (
    arc,
    bezier,
    brush,
    catmull_rom,
    circle,
    free_snapping,
    line,
    polygon,
    polyline,
    rect,
    rect_centered,
    regular_polygon,
    ring,
    rrect,
    snap,
    snap_angle,
    spline,
    wedge,
)


def test_snapping():
    assert snap(0.3) == 0.25 and snap(0.13) == 0.25 and snap(0.12) == 0.0 and snap(-0.4) == -0.5
    assert snap_angle(50) == 45 and snap_angle(7) == 0 and snap_angle(8) == 15


def test_circle_snaps_centre_and_radius():
    b = circle(0.3, 0.1, 100.12).bounds
    assert (b.x0, b.x1) == (-99.75, 100.25)
    assert math.isclose(circle(0, 0, 100).area, math.pi * 100**2, rel_tol=0.005)


def test_rect_and_rrect():
    assert rect(0, 0, 10, 20).bounds.w == 10 and rect(0, 0, 10, 20).bounds.h == 20
    assert rect_centered(0, 0, 10, 20).bounds.x0 == -5
    r = rrect(0, 0, 100, 50, 10)
    assert math.isclose(r.area, 100 * 50 - (4 - math.pi) * 100, rel_tol=0.01)


def test_ring_and_sector_areas():
    full = ring(0, 0, 100, 20)
    assert math.isclose(full.area, math.pi * (100**2 - 80**2), rel_tol=0.01)
    assert len(full.subpaths()) == 2
    quarter = ring(0, 0, 100, 20, start=0, end=90)
    assert math.isclose(quarter.area, full.area / 4, rel_tol=0.02)
    b = quarter.bounds
    assert b.x0 >= -0.01 and b.y0 >= -0.01 and math.isclose(b.x1, 100, abs_tol=0.01)


def test_polygons():
    sq = regular_polygon(0, 0, 100, 4, rotation=50)  # rotation snaps to 45
    assert math.isclose(sq.area, 2 * 100**2, rel_tol=0.001)
    assert math.isclose(sq.bounds.x1, 100 * math.cos(math.radians(45)), abs_tol=0.01)
    tri = polygon([(0, 0), (100, 0), (0, 100)])
    assert math.isclose(tri.area, 5000) and len(tri.straight_segments()) == 3
    assert polygon([(0, 0), (100, 0), (0, 100)], free=True).free_segments == 3
    assert tri.free_segments == 0


def test_free_primitives_count_every_segment_they_draw():
    assert circle(0, 0, 100, free=True).free_segments == 4  # four arcs, not zero straight lines
    assert ring(0, 0, 100, 20, free=True).free_segments == 8
    assert rrect(0, 0, 100, 50, 10, free=True).free_segments == 8
    assert rect(0, 0, 10, 10, free=True).free_segments == 4 and polygon([(0, 0), (100, 0), (0, 100)], free=True).free_segments == 3
    assert circle(0, 0, 100).free_segments == 0


def test_wedge():
    w = wedge(0, 0, 100, 0, 90)
    assert math.isclose(w.area, math.pi * 100**2 / 4, rel_tol=0.01)


def test_strokes():
    seg = line(0, 0, 100, 0, 10)
    assert seg.bounds.x0 == 0 and seg.bounds.x1 == 100 and math.isclose(seg.area, 1000, rel_tol=0.001)
    rounded = line(0, 0, 100, 0, 10, cap="round")
    assert math.isclose(rounded.area, 1000 + math.pi * 25, rel_tol=0.01)
    a = arc(0, 0, 100, 0, 90, 10)
    assert math.isclose(a.bounds.x1, 105, abs_tol=0.5) and math.isclose(a.bounds.y1, 105, abs_tol=0.5)
    pl = polyline([(0, 0), (100, 0), (100, 100)], 10, join="round")
    assert not pl.is_empty and pl.bounds.y1 >= 100


def test_bezier_filled_and_stroked():
    pts = [(0, 0), (0, 60), (40, 100), (100, 100)]
    filled = bezier(pts, closed=True)
    assert filled.area > 3000
    stroked = bezier(pts, width=4)
    assert not stroked.is_empty and stroked.bounds.y1 > 100


def test_self_crossing_stroke_excludes_its_hole():
    looped = polyline([(0, 0), (100, 0), (100, 100), (50, 100), (50, -50)], 10)
    assert math.isclose(looped.area, 3900, rel_tol=0.01)


def test_ring_width_must_be_finite_and_less_than_the_radius():
    for width in (100, 150):  # a full ring would become a disc; a sector would run a negative inner radius
        for sector in ({}, {"start": 0, "end": 90}):
            with pytest.raises(ValueError, match="ring width must be less than the radius"):
                ring(0, 0, 100, width, **sector)
    for width in (math.nan, math.inf):
        for free in (False, True):
            with pytest.raises(ValueError, match="ring width must be finite"):
                ring(0, 0, 100, width, free=free)


def test_non_finite_stroke_widths_are_rejected_even_when_free():
    from logomaker.kit.ops import stroke

    for width in (math.nan, math.inf):
        with pytest.raises(ValueError, match="stroke width must be finite"):
            line(0, 0, 100, 0, width, free=True)
        with pytest.raises(ValueError, match="stroke width must be finite"):
            stroke(rect(0, 0, 10, 10), width)


def test_non_positive_widths_are_rejected():
    with pytest.raises(ValueError, match="stroke width must be positive"):
        polyline([(0, 0), (100, 0), (100, 100)], 0.1)  # snaps to 0
    with pytest.raises(ValueError, match="stroke width must be positive"):
        line(0, 0, 100, 0, -5)
    with pytest.raises(ValueError, match="stroke width must be positive"):
        arc(0, 0, 100, 0, 90, 0)
    with pytest.raises(ValueError, match="ring width must be positive"):
        ring(0, 0, 100, 0.1)  # snaps to 0


S_CURVE = [(-400, -200), (-200, 300), (200, -300), (400, 200)]  # one cubic: p0 c1 c2 p1
WAVE = [(-400, 0), (-300, 200), (-100, 200), (0, 0), (100, -200), (300, -200), (400, 0)]  # two cubics, three nodes


def test_brush_with_a_constant_width_matches_the_stroked_bezier():
    constant = brush(S_CURVE, 60, cap="butt")
    stroked = bezier(S_CURVE, width=60)
    assert math.isclose(constant.area, stroked.area, rel_tol=0.03)


def test_brush_widths_are_one_per_node_and_the_stroke_swells_between_them():
    swelling = brush(WAVE, [20, 120, 20], cap="butt")
    thin = brush(WAVE, [20, 20, 20], cap="butt")
    assert swelling.area > 2 * thin.area
    assert swelling.bounds.h > thin.bounds.h + 40  # the middle node is 120 wide where the thin one is 20
    with pytest.raises(ValueError, match=r"brush needs one width per on-curve point \(3\), got 2"):
        brush(WAVE, [20, 120])
    with pytest.raises(ValueError, match="widths must be positive"):
        brush(WAVE, [20, 0, 20])


def test_brush_keeps_a_designers_anchor_count():
    five_nodes = [(-400, 0), (-350, 150), (-250, 150), (-200, 0), (-150, -150), (-50, -150), (0, 0), (50, 150), (150, 150),
                  (200, 0), (250, -150), (350, -150), (400, 0)]
    assert brush(five_nodes, [30, 80, 30, 80, 30], cap="butt").anchor_count() < 24  # the fitted sides alone
    assert brush(five_nodes, [30, 80, 30, 80, 30], cap="round").anchor_count() < 32  # two discs merged in


def test_brush_caps():
    butt = brush(S_CURVE, 60, cap="butt")
    rounded = brush(S_CURVE, 60, cap="round")
    square = brush(S_CURVE, 60, cap="square")
    assert rounded.area > butt.area and square.area > rounded.area
    assert math.isclose(rounded.area - butt.area, math.pi * 30**2, rel_tol=0.1)


def test_brush_survives_a_tight_hook_without_slivers():
    hook = [(0, 0), (300, 0), (300, 300), (0, 300), (-300, 300), (-300, 0), (0, 0)]  # a loop about 300 across
    shape = brush(hook, 700, cap="butt")  # wider than twice the loop's radius: the inner side folds over itself
    assert not shape.is_empty and shape.area > 0
    assert all(part.area > 1 for part in shape.subpaths())  # no slivers from the folded inner side


def test_brush_rejects_degenerate_input():
    with pytest.raises(ValueError, match="widths must be positive"):
        brush(S_CURVE, 0.1)  # snaps to 0
    with pytest.raises(ValueError, match="nonzero length"):
        brush([(5, 5)] * 4, 10)
    with pytest.raises(ValueError, match=r"1 \+ 3k points"):
        brush([(0, 0), (100, 0)], 10)
    tail = brush([(0, 0), (10, 10), (20, 10), (30, 0), (30, 0), (30, 0), (30, 0)], 10, cap="butt")  # a zero-length last segment
    assert math.isclose(tail.area, brush([(0, 0), (10, 10), (20, 10), (30, 0)], 10, cap="butt").area)


def test_brush_bevels_a_corner_node_like_polyline():
    corner = [(0, 0), (0, 0), (100, 0), (100, 0), (100, 0), (100, 100), (100, 100)]  # control points on their nodes
    assert math.isclose(brush(corner, 20, cap="butt").area, polyline([(0, 0), (100, 0), (100, 100)], 20, join="bevel").area, rel_tol=1e-3)


DIAMOND = [(0, 300), (300, 0), (0, -300), (-300, 0)]


def test_spline_passes_through_its_points_and_rounds_between_them():
    leaf = spline(DIAMOND)
    for p in DIAMOND:  # the chain's on-curve nodes are the points
        assert any(math.dist(p, (x, y)) < 0.01 for x, y in catmull_rom(DIAMOND, 0.5, True)[::3])
    straight = spline(DIAMOND, tension=1)
    assert math.isclose(straight.area, 2 * 300**2, rel_tol=0.01)  # tension 1 is the polygon
    assert leaf.area > straight.area  # the curve bulges outside the chords
    assert leaf.anchor_count() == 4


def test_open_spline_is_stroked_or_filled():
    chain = catmull_rom([(-300, 0), (0, 200), (300, 0)], 0.5, False)
    assert len(chain) == 7 and chain[0] == (-300, 0) and chain[-1] == (300, 0)
    stroked = spline([(-300, 0), (0, 200), (300, 0)], closed=False, width=40)
    assert stroked.area > 600 * 40 * 0.9
    with pytest.raises(ValueError, match="spline needs at least three points"):
        spline([(0, 0), (1, 1)])
    with pytest.raises(ValueError, match="tension must be between 0 and 1"):
        spline(DIAMOND, tension=2)


def test_free_snapping_context_makes_every_primitive_free():
    assert circle(0.3, 0, 100.12).bounds.x1 == 100.25
    with free_snapping():
        free_disc = circle(0.3, 0, 100.12)
        assert math.isclose(free_disc.bounds.x1, 100.42, abs_tol=0.01) and free_disc.free_segments == 4
        assert circle(0, 0, 100, free=True).free_segments == 4  # explicit free=True is not counted twice
        assert regular_polygon(0, 0, 100, 5, rotation=7).free_segments == 5
    assert circle(0.3, 0, 100.12).bounds.x1 == 100.25  # restored
