"""Primitive shapes on the 1000-unit canvas. Coordinates snap to 0.25 units and angles to 15 degrees unless free=True."""
from __future__ import annotations

import math

import skia

from .shape import Shape, normalize_winding

SNAP = 0.25
ANGLE_SNAP = 15.0

CAPS = {"butt": skia.Paint.kButt_Cap, "round": skia.Paint.kRound_Cap, "square": skia.Paint.kSquare_Cap}
JOINS = {"miter": skia.Paint.kMiter_Join, "round": skia.Paint.kRound_Join, "bevel": skia.Paint.kBevel_Join}


def snap(value: float, step: float = SNAP) -> float:
    return round(round(value / step) * step, 6)


def snap_angle(angle: float, step: float = ANGLE_SNAP) -> float:
    return round(round(angle / step) * step, 6)


def _v(value: float, free: bool) -> float:
    return value if free else snap(value)


def _a(angle: float, free: bool) -> float:
    return angle if free else snap_angle(angle)


def _oval(cx: float, cy: float, r: float) -> skia.Rect:
    return skia.Rect.MakeLTRB(cx - r, cy - r, cx + r, cy + r)


def _polar(cx: float, cy: float, r: float, angle: float) -> tuple[float, float]:
    rad = math.radians(angle)
    return (cx + r * math.cos(rad), cy + r * math.sin(rad))


def _finish(path: skia.Path, free: bool) -> Shape:
    """Wrap a primitive's path; with free=True every segment it draws, curved or straight, counts as free."""
    shape = Shape(path)
    shape.free_segments = shape.segment_count() if free else 0
    return shape


def stroked_path(path: skia.Path, width: float, cap: str = "butt", join: str = "miter", miter_limit: float = 4) -> skia.Path:
    if not math.isfinite(width):  # free=True skips the snapping that would otherwise choke on NaN or infinity
        raise ValueError("stroke width must be finite")
    if width <= 0:  # skia strokes width <= 0 as a hairline, and Simplify would then fill the bare centreline
        raise ValueError("stroke width must be positive")
    paint = skia.Paint()
    paint.setStyle(skia.Paint.kStroke_Style)
    paint.setStrokeWidth(width)
    paint.setStrokeCap(CAPS[cap])
    paint.setStrokeJoin(JOINS[join])
    paint.setStrokeMiter(miter_limit)
    out = skia.Path()
    paint.getFillPath(path, out)
    return normalize_winding(skia.Simplify(out))


def circle(cx: float, cy: float, r: float, free: bool = False) -> Shape:
    path = skia.Path()
    path.addCircle(_v(cx, free), _v(cy, free), _v(r, free))
    return _finish(path, free)


def ring(cx: float, cy: float, r: float, width: float, start: float | None = None, end: float | None = None, free: bool = False) -> Shape:
    """Annulus with outer radius r and band width `width`; with start/end (degrees, counter-clockwise) an annular sector."""
    if not math.isfinite(width):
        raise ValueError("ring width must be finite")
    cx, cy, r, width = _v(cx, free), _v(cy, free), _v(r, free), _v(width, free)
    if width <= 0:
        raise ValueError("ring width must be positive")
    if width >= r:  # a full ring would become a disc, a sector a wedge past the centre
        raise ValueError(f"ring width must be less than the radius, got width {width} for radius {r}")
    inner = r - width
    if start is None or end is None:
        # The hole is wound against the outline so it stays a hole under SVG fill-rule="nonzero" and in Shape.area.
        # (skia.Op returns these concentric contours with matching directions, relying on even-odd fill.)
        path = skia.Path()
        path.addCircle(cx, cy, r)
        path.addCircle(cx, cy, inner, skia.PathDirection.kCCW)
        return _finish(path, free)
    start, end = _a(start, free), _a(end, free)
    sweep = end - start
    if sweep <= 0:
        sweep += 360
    path = skia.Path()
    path.moveTo(*_polar(cx, cy, r, start))
    path.arcTo(_oval(cx, cy, r), start, sweep, False)
    path.lineTo(*_polar(cx, cy, inner, end))
    path.arcTo(_oval(cx, cy, inner), end, -sweep, False)
    path.close()
    return _finish(path, free)


def rect(x: float, y: float, w: float, h: float, free: bool = False) -> Shape:
    """Rectangle from its lower-left corner (x, y) in the y-up frame."""
    x, y, w, h = _v(x, free), _v(y, free), _v(w, free), _v(h, free)
    path = skia.Path()
    path.addRect(skia.Rect.MakeLTRB(x, y, x + w, y + h))
    return _finish(path, free)


def rect_centered(cx: float, cy: float, w: float, h: float, free: bool = False) -> Shape:
    return rect(cx - w / 2, cy - h / 2, w, h, free)


def rrect(x: float, y: float, w: float, h: float, radius: float, free: bool = False) -> Shape:
    x, y, w, h, radius = _v(x, free), _v(y, free), _v(w, free), _v(h, free), _v(radius, free)
    path = skia.Path()
    path.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x, y, x + w, y + h), radius, radius))
    return _finish(path, free)


def rrect_centered(cx: float, cy: float, w: float, h: float, radius: float, free: bool = False) -> Shape:
    return rrect(cx - w / 2, cy - h / 2, w, h, radius, free)


def polygon(points: list[tuple[float, float]], free: bool = False) -> Shape:
    if len(points) < 3:
        raise ValueError("polygon needs at least three points")
    path = skia.Path()
    path.moveTo(_v(points[0][0], free), _v(points[0][1], free))
    for x, y in points[1:]:
        path.lineTo(_v(x, free), _v(y, free))
    path.close()
    return _finish(path, free)


def regular_polygon(cx: float, cy: float, r: float, n: int, rotation: float = 0, free: bool = False) -> Shape:
    if n < 3:
        raise ValueError("regular_polygon needs n >= 3")
    cx, cy, r, rotation = _v(cx, free), _v(cy, free), _v(r, free), _a(rotation, free)
    pts = [_polar(cx, cy, r, rotation + 360 * i / n) for i in range(n)]
    return polygon(pts, free=True) if free else _finish_polygon_snapped(pts)


def _finish_polygon_snapped(pts: list[tuple[float, float]]) -> Shape:
    # Regular polygons keep exact vertices (snapping them would break the symmetry); count as not free.
    path = skia.Path()
    path.moveTo(*pts[0])
    for p in pts[1:]:
        path.lineTo(*p)
    path.close()
    return Shape(path, 0)


def wedge(cx: float, cy: float, r: float, start: float, end: float, free: bool = False) -> Shape:
    cx, cy, r, start, end = _v(cx, free), _v(cy, free), _v(r, free), _a(start, free), _a(end, free)
    sweep = end - start
    if sweep <= 0:
        sweep += 360
    path = skia.Path()
    path.moveTo(cx, cy)
    path.arcTo(_oval(cx, cy, r), start, sweep, False)
    path.close()
    return _finish(path, free)


def arc(cx: float, cy: float, r: float, start: float, end: float, width: float, cap: str = "butt", free: bool = False) -> Shape:
    """A stroked arc on centreline radius r."""
    cx, cy, r, start, end, width = _v(cx, free), _v(cy, free), _v(r, free), _a(start, free), _a(end, free), _v(width, free)
    sweep = end - start
    if sweep <= 0:
        sweep += 360
    path = skia.Path()
    path.moveTo(*_polar(cx, cy, r, start))
    path.arcTo(_oval(cx, cy, r), start, sweep, False)
    return _finish(stroked_path(path, width, cap), free)


def line(x1: float, y1: float, x2: float, y2: float, width: float, cap: str = "butt", free: bool = False) -> Shape:
    path = skia.Path()
    path.moveTo(_v(x1, free), _v(y1, free))
    path.lineTo(_v(x2, free), _v(y2, free))
    return _finish(stroked_path(path, _v(width, free), cap), free)


def polyline(points: list[tuple[float, float]], width: float, cap: str = "butt", join: str = "miter", free: bool = False) -> Shape:
    if len(points) < 2:
        raise ValueError("polyline needs at least two points")
    path = skia.Path()
    path.moveTo(_v(points[0][0], free), _v(points[0][1], free))
    for x, y in points[1:]:
        path.lineTo(_v(x, free), _v(y, free))
    return _finish(stroked_path(path, _v(width, free), cap, join), free)


def bezier(points: list[tuple[float, float]], width: float | None = None, closed: bool = False, free: bool = False) -> Shape:
    """Cubic Bézier chain p0, c1, c2, p1, c3, c4, p2, ... Filled (closed) when width is None, else stroked."""
    if len(points) < 4 or (len(points) - 1) % 3 != 0:
        raise ValueError("bezier needs 1 + 3k points")
    pts = [(_v(x, free), _v(y, free)) for x, y in points]
    path = skia.Path()
    path.moveTo(*pts[0])
    for i in range(1, len(pts), 3):
        path.cubicTo(*pts[i], *pts[i + 1], *pts[i + 2])
    if closed or width is None:
        path.close()
    if width is None:
        return _finish(path, free)
    return _finish(stroked_path(path, _v(width, free), "butt", "round"), free)
