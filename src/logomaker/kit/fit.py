"""Fit a polyline with cubic Béziers (Schneider, "An Algorithm for Automatically Fitting Digitized Curves", Graphics Gems
1990): chord-length parameterisation, a least-squares cubic between the end tangents, Newton reparameterisation, and a
split at the worst point when the error exceeds the tolerance. brush() uses it so a stroke's sides keep a designer's
anchor count instead of a flattened polygon's."""
from __future__ import annotations

import math

Point = tuple[float, float]
Cubic = tuple[Point, Point, Point, Point]

MAX_ITERATIONS = 4  # reparameterisations before giving up and splitting


def _sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def _add(a: Point, b: Point) -> Point:
    return (a[0] + b[0], a[1] + b[1])


def _mul(a: Point, k: float) -> Point:
    return (a[0] * k, a[1] * k)


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _unit(a: Point) -> Point:
    length = math.hypot(*a)
    return (a[0] / length, a[1] / length) if length else (0.0, 0.0)


def cubic_at(c: Cubic, t: float) -> Point:
    u = 1 - t
    return (u**3 * c[0][0] + 3 * u * u * t * c[1][0] + 3 * u * t * t * c[2][0] + t**3 * c[3][0],
            u**3 * c[0][1] + 3 * u * u * t * c[1][1] + 3 * u * t * t * c[2][1] + t**3 * c[3][1])


def _derivative_at(c: Cubic, t: float) -> Point:
    u = 1 - t
    d1, d2, d3 = _sub(c[1], c[0]), _sub(c[2], c[1]), _sub(c[3], c[2])
    return _add(_add(_mul(d1, 3 * u * u), _mul(d2, 6 * u * t)), _mul(d3, 3 * t * t))


def _second_derivative_at(c: Cubic, t: float) -> Point:
    u = 1 - t
    a = _add(_sub(c[2], _mul(c[1], 2)), c[0])
    b = _add(_sub(c[3], _mul(c[2], 2)), c[1])
    return _add(_mul(a, 6 * u), _mul(b, 6 * t))


def _chord_parameters(points: list[Point]) -> list[float]:
    u = [0.0]
    for a, b in zip(points, points[1:]):
        u.append(u[-1] + math.dist(a, b))
    total = u[-1] or 1.0
    return [v / total for v in u]


def _generate(points: list[Point], u: list[float], t1: Point, t2: Point) -> Cubic:
    """The least-squares cubic from points[0] to points[-1] with end tangents t1 and t2 (unit vectors)."""
    first, last = points[0], points[-1]
    c11 = c12 = c22 = x1 = x2 = 0.0
    for p, ui in zip(points, u):
        b0, b1, b2, b3 = (1 - ui) ** 3, 3 * ui * (1 - ui) ** 2, 3 * ui * ui * (1 - ui), ui**3
        a1, a2 = _mul(t1, b1), _mul(t2, b2)
        c11 += _dot(a1, a1)
        c12 += _dot(a1, a2)
        c22 += _dot(a2, a2)
        tmp = _sub(p, _add(_mul(first, b0 + b1), _mul(last, b2 + b3)))
        x1 += _dot(a1, tmp)
        x2 += _dot(a2, tmp)
    det = c11 * c22 - c12 * c12
    alpha1 = (x1 * c22 - x2 * c12) / det if det else 0.0
    alpha2 = (c11 * x2 - c12 * x1) / det if det else 0.0
    chord = math.dist(first, last)
    if alpha1 < 1e-6 * chord or alpha2 < 1e-6 * chord:  # a degenerate solution: fall back to Wu/Barsky's thirds
        alpha1 = alpha2 = chord / 3
    return (first, _add(first, _mul(t1, alpha1)), _add(last, _mul(t2, alpha2)), last)


def _max_error(points: list[Point], c: Cubic, u: list[float]) -> tuple[float, int]:
    worst, index = 0.0, len(points) // 2
    for i, (p, ui) in enumerate(zip(points, u)):
        d = _sub(cubic_at(c, ui), p)
        err = _dot(d, d)
        if err > worst:
            worst, index = err, i
    return worst, index


def _reparameterise(points: list[Point], c: Cubic, u: list[float]) -> list[float]:
    out = []
    for p, ui in zip(points, u):
        q = _sub(cubic_at(c, ui), p)
        d1, d2 = _derivative_at(c, ui), _second_derivative_at(c, ui)
        numerator = _dot(q, d1)
        denominator = _dot(d1, d1) + _dot(q, d2)
        out.append(ui if abs(denominator) < 1e-12 else min(1.0, max(0.0, ui - numerator / denominator)))
    return out


def _fit(points: list[Point], t1: Point, t2: Point, tolerance: float) -> list[Cubic]:
    if len(points) == 2:
        (x0, y0), (x1, y1) = points
        dx, dy = x1 - x0, y1 - y0
        return [(points[0], (x0 + dx / 3, y0 + dy / 3), (x0 + 2 * dx / 3, y0 + 2 * dy / 3), points[1])]
    u = _chord_parameters(points)
    c = _generate(points, u, t1, t2)
    error, split = _max_error(points, c, u)
    if error <= tolerance**2:
        return [c]
    if error <= (tolerance * 4) ** 2:
        for _ in range(MAX_ITERATIONS):
            u = _reparameterise(points, c, u)
            c = _generate(points, u, t1, t2)
            error, split = _max_error(points, c, u)
            if error <= tolerance**2:
                return [c]
    split = min(max(split, 1), len(points) - 2)
    middle = _unit(_sub(points[split - 1], points[split + 1]))  # the centre tangent, shared by both halves
    return _fit(points[: split + 1], t1, middle, tolerance) + _fit(points[split:], _mul(middle, -1), t2, tolerance)


def fit_cubics(points: list[Point], tolerance: float = 0.5) -> list[Cubic]:
    """Cubic Béziers through `points`, end to end, each within `tolerance` units of the points it covers. A corner in
    the polyline becomes a segment boundary; a straight run is one segment."""
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    pts = [tuple(map(float, p)) for p in points]
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]  # drop repeated points: they give zero-length chords
    if len(pts) < 2:
        raise ValueError("fit_cubics needs at least two points")
    return _fit(pts, _unit(_sub(pts[1], pts[0])), _unit(_sub(pts[-2], pts[-1])), tolerance)
