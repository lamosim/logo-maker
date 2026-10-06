import math

import pytest

from logomaker.kit.primitives import (
    arc,
    bezier,
    circle,
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
