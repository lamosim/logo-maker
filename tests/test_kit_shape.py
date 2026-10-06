import math

import skia

from logomaker.kit.shape import Box, Shape, fmt, normalize_winding, path_from_commands


def test_fmt_never_emits_scientific_notation_or_negative_zero():
    assert fmt(-0.004) == "0"
    assert fmt(1e-05) == "0"
    assert fmt(12.3456) == "12.35"
    assert fmt(100.0) == "100"
    assert fmt(-3.10) == "-3.1"
    assert fmt(0.125, precision=2) == "0.12"
    assert fmt(100, precision=0) == "100"


def square(size=10.0) -> Shape:
    p = skia.Path()
    p.addRect(skia.Rect.MakeLTRB(0, 0, size, size * 2))
    return Shape(p)


def test_bounds_area_centroid_of_rect():
    s = square()
    assert s.bounds == Box(0, 0, 10, 20)
    assert math.isclose(s.area, 200)
    cx, cy = s.centroid
    assert math.isclose(cx, 5) and math.isclose(cy, 10)
    assert s.anchor_count() == 4
    assert len(s.straight_segments()) == 4


def test_circle_commands_are_cubics_and_area_is_close():
    p = skia.Path()
    p.addCircle(30, -40, 50)
    s = Shape(p)
    kinds = {k for k, _ in s.commands()}
    assert kinds == {"M", "C", "Z"}
    assert s.anchor_count() == 49
    assert math.isclose(s.area, math.pi * 50 * 50, rel_tol=0.005)
    cx, cy = s.centroid
    assert math.isclose(cx, 30, abs_tol=0.5) and math.isclose(cy, -40, abs_tol=0.5)


def test_path_data_flips_y_and_is_deterministic():
    assert square().to_path_data() == "M0 0L10 0L10 -20L0 -20Z"
    assert square().to_path_data(flip_y=False) == "M0 0L10 0L10 20L0 20Z"


def test_path_data_has_no_scientific_notation_for_tiny_values():
    p = skia.Path()
    p.addCircle(0, 0, 0.001)
    data = Shape(p).to_path_data()
    assert "e-" not in data and "-0 " not in data and "-0L" not in data


def test_subpaths_and_round_trip():
    p = skia.Path()
    p.addRect(skia.Rect.MakeLTRB(0, 0, 10, 10))
    p.addRect(skia.Rect.MakeLTRB(20, 0, 30, 10))
    s = Shape(p)
    parts = s.subpaths()
    assert len(parts) == 2 and parts[1].bounds.x0 == 20
    rebuilt = Shape(path_from_commands(s.commands()))
    assert rebuilt.to_path_data() == s.to_path_data()


def test_box_union():
    assert Box.union([Box(0, 0, 1, 1), Box(-2, 3, 0, 5)]) == Box(-2, 0, 1, 5)


def signed_area(poly) -> float:
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1])) / 2


def test_normalize_winding_alternates_nested_contours():
    p = skia.Path()
    for r in (100, 80, 60):
        p.addCircle(0, 0, r)
    fixed = normalize_winding(p)
    assert math.isclose(Shape(fixed).area, math.pi * (100**2 - 80**2 + 60**2), rel_tol=0.005)
    parts = Shape(fixed).subpaths()
    assert [signed_area(part.flatten()[0]) > 0 for part in parts] == [True, False, True]
    widths = [part.bounds.w for part in parts]  # contour order is kept
    assert len(widths) == 3 and all(math.isclose(w, e, abs_tol=0.01) for w, e in zip(widths, (200, 160, 120)))
    assert fixed.getFillType() == skia.PathFillType.kWinding
    assert Shape(normalize_winding(p)).to_path_data() == Shape(fixed).to_path_data()


def test_normalize_winding_leaves_correct_paths_alone():
    p = skia.Path()
    p.addCircle(0, 0, 100)
    p.addCircle(0, 0, 80, skia.PathDirection.kCCW)
    assert Shape(normalize_winding(p)).to_path_data() == Shape(p).to_path_data()
