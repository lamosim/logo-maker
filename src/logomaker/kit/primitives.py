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


BRUSH_STEPS = 24  # samples per cubic segment when offsetting a brush's sides

Sample = tuple[tuple[float, float], float, tuple[float, float]]  # a centreline point, the width there, the unit tangent


def _brush_segment(cubic: tuple, w0: float, w1: float) -> list[Sample]:
    """BRUSH_STEPS + 1 samples along one cubic, t = 0 to 1, the width running linearly by arc length from w0 to w1; [] for
    a segment of zero length. Tangents come from the derivative, or from neighbouring points where a control point sits on
    its node and the derivative vanishes."""
    from .fit import _derivative_at, cubic_at

    ts = [i / BRUSH_STEPS for i in range(BRUSH_STEPS + 1)]
    points = [cubic_at(cubic, t) for t in ts]
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    if lengths[-1] < 1e-6:  # a segment of (nearly) one point; the Bernstein sum leaves float noise, not exact zeros
        return []
    samples = []
    for t, p, length in zip(ts, points, lengths):
        d = _derivative_at(cubic, t)
        if math.hypot(*d) < 1e-9:
            a, b = cubic_at(cubic, max(t - 1e-3, 0.0)), cubic_at(cubic, min(t + 1e-3, 1.0))
            d = (b[0] - a[0], b[1] - a[1])
        size = math.hypot(*d)
        samples.append((p, w0 + (w1 - w0) * length / lengths[-1], (d[0] / size, d[1] / size)))
    return samples


def brush(points: list[tuple[float, float]], widths: float | list[float], cap: str = "round", free: bool = False) -> Shape:
    """A stroke of varying width along a cubic chain (`points` as for bezier: 1 + 3k points). `widths` is one width per
    on-curve node, interpolated linearly by arc length between nodes, or one number for all. Each segment's sides are
    sampled, offset along the normals and fitted back to cubics (kit.fit), so the result keeps a designer's anchor count,
    with anchors on the nodes; where a side folds (a width over twice the local radius) Simplify resolves the overlap and
    slivers are dropped. Caps: round (discs at the ends), square (half a width beyond each end), butt."""
    from .fit import fit_cubics
    from .ops import union

    if len(points) < 4 or (len(points) - 1) % 3 != 0:
        raise ValueError("brush needs 1 + 3k points")
    nodes = (len(points) - 1) // 3 + 1
    if isinstance(widths, (int, float)):
        widths = [float(widths)] * nodes
    widths = [float(w) for w in widths]
    if len(widths) != nodes:
        raise ValueError(f"brush needs one width per on-curve point ({nodes}), got {len(widths)}")
    if cap not in CAPS:
        raise ValueError(f"cap must be one of {sorted(CAPS)}, got {cap!r}")
    widths = [_v(w, free) if math.isfinite(w) else w for w in widths]
    if any(not math.isfinite(w) or w <= 0 for w in widths):  # checked after snapping, which can round a width to 0
        raise ValueError("brush widths must be positive")
    pts = [(_v(x, free), _v(y, free)) for x, y in points]
    segments = [_brush_segment(tuple(pts[3 * k:3 * k + 4]), widths[k], widths[k + 1]) for k in range(nodes - 1)]
    segments = [s for s in segments if s]
    if not segments:
        raise ValueError("brush needs a path of nonzero length")
    # Each segment's sides are fitted on their own: the width's slope changes at a node, so the sides have a slight
    # corner there (a real one where the chain has a corner), and an anchor on the node is where a designer puts it.
    left = [fit_cubics([(p[0] - t[1] * w / 2, p[1] + t[0] * w / 2) for p, w, t in s]) for s in segments]
    right = [fit_cubics([(p[0] + t[1] * w / 2, p[1] - t[0] * w / 2) for p, w, t in reversed(s)]) for s in reversed(segments)]
    path = skia.Path()
    current = left[0][0][0]
    path.moveTo(*current)
    for piece in left + right:
        if piece[0][0] != current:
            path.lineTo(*piece[0][0])  # across the end of the stroke, or a bevel at a corner node
        for c in piece:
            path.cubicTo(*c[1], *c[2], *c[3])
        current = piece[-1][3]
    path.close()
    body = Shape(normalize_winding(_drop_slivers(normalize_winding(skia.Simplify(path)))))
    if cap == "butt":
        return _finish(body.path, free)
    (start, _, (sx, sy)), (end, _, (ex, ey)) = segments[0][0], segments[-1][-1]
    extras = []
    for (x, y), w, (tx, ty) in ((start, widths[0], (-sx, -sy)), (end, widths[-1], (ex, ey))):  # tangents pointing outwards
        if cap == "round":
            extras.append(circle(x, y, w / 2, free=True))
        else:
            extras.append(line(x, y, x + tx * w / 2, y + ty * w / 2, w, cap="butt", free=True))
    return _finish(union(body, *extras).path, free)


def _drop_slivers(path: skia.Path, min_area: float = 1.0) -> skia.Path:
    """`path` without contours under `min_area` unit²: the slivers a folded brush side leaves after Simplify."""
    from .shape import contour_nesting

    out = skia.Path()
    for contour, area, _, _ in contour_nesting(path):
        if abs(area) >= min_area:
            out.addPath(contour)
    return out
