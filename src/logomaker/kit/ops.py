"""Boolean operations, strokes, transforms and alignment. Every function returns a new Shape.

A result has the kind of its first operand (Shape._with_path), so a TextShape wordmark keeps its metrics through a
notch, a stroke or a move.
"""
from __future__ import annotations

import numpy as np
import skia

from .primitives import stroked_path
from .shape import Box, Shape, contour_nesting, normalize_winding


def _op(a: skia.Path, b: skia.Path, op: skia.PathOp) -> skia.Path:
    try:
        return skia.Op(a, b, op)
    except RuntimeError as err:  # skia-python raises on pathops failure (e.g. non-finite input); it never returns None
        raise ValueError("boolean path operation failed") from err


def _simplify(path: skia.Path) -> skia.Path:
    try:
        return skia.Simplify(path)
    except RuntimeError as err:
        raise ValueError("boolean path operation failed") from err


def union(*shapes: Shape) -> Shape:
    if not shapes:
        return Shape.empty()
    live = [s for s in shapes if not s.is_empty]
    if not live:
        return shapes[0]._with_path(skia.Path(), 0)
    acc = skia.Path(live[0].path)
    for s in live[1:]:
        acc = _op(acc, s.path, skia.PathOp.kUnion_PathOp)
    return shapes[0]._with_path(normalize_winding(_simplify(acc)), sum(s.free_segments for s in live))


def _binary(a: Shape, b: Shape, op: skia.PathOp) -> Shape:
    return a._with_path(normalize_winding(_simplify(_op(a.path, b.path, op))), a.free_segments + b.free_segments)


def subtract(a: Shape, b: Shape) -> Shape:
    return _binary(a, b, skia.PathOp.kDifference_PathOp)


def intersect(a: Shape, b: Shape) -> Shape:
    return _binary(a, b, skia.PathOp.kIntersect_PathOp)


def xor(a: Shape, b: Shape) -> Shape:
    return _binary(a, b, skia.PathOp.kXOR_PathOp)


def stroke(shape: Shape, width: float, cap: str = "butt", join: str = "miter", miter_limit: float = 4) -> Shape:
    return shape._with_path(stroked_path(shape.path, width, cap, join, miter_limit), shape.free_segments)


def offset(shape: Shape, distance: float) -> Shape:
    """Grow the shape by `distance`, rounding what it grows, or shrink it by -distance (see `_inset`)."""
    if distance == 0:
        return shape.copy()
    result = union(shape, stroke(shape, 2 * distance, join="round")) if distance > 0 else _inset(shape, -distance)
    return shape._with_path(result.path, shape.free_segments)  # derived from shape alone: count its free segments once


_SLIVER_AREA = 1.0  # unit²: smaller than any hole a real inset has (one at least `distance` > 1 across)
_RETRY_STEP = 0.01  # how much shallower a failed band subtraction is retried: a hundredth of a unit, below SVG precision
_PAIRS = 1 << 18  # point-edge pairs measured at once, bounding the distance test's memory (2 MB per array)
# Flattening steps per curve for the outline the distance test measures to. Along a convex stretch a chord cuts inside the
# curve, towards the inset: at the default 16 steps, a bowl 800 units tall drawn as one half-turn cubic comes 2.3 units
# nearer, more than tol; at 64, 0.17.
_OUTLINE_STEPS = 64


def _band_subtraction(shape: Shape, distance: float) -> Shape:
    return subtract(shape, stroke(shape, 2 * distance, join="round"))


def _inset(shape: Shape, distance: float) -> Shape:
    """Everything in `shape` at least `distance` (> 0) from its outline.

    The base is the shape minus a round-joined stroke band of its outline (normalized like every stroke). That is exact
    except where skia's stroker folds: behind a convex curve tighter than the distance the band misses an island (a dot
    of radius r < distance keeps a dot of radius min(r, distance - r); an inset deeper than twice a hole's radius keeps
    a ring around the hole). So the result is read as regions, each an outline (even depth) with its direct holes
    (depth + 1, at least `_SLIVER_AREA`), with five probes per contour so that a hole touching an outline cannot pass
    for its parent. The slivers and overlapping duplicates the boolean leaves where the band's edge lands on the outline
    (an inset of about twice a hole's radius) belong to no region and are dropped. A region is kept only if every vertex
    and edge midpoint of its flattened contours lies at least distance - tol from the shape's own outline (every
    contour, holes too, flattened at `_OUTLINE_STEPS` per curve), tol = max(1, 2 % of the distance), clear of the
    stroker's error of about 0.25 units: a true inset region lies at the distance, an island on the stroker's folded
    curve nearer (a dot's island lies max(0, 2r - distance) from the dot's outline). The test only measures distances;
    it runs no boolean and no stroke. Islands can survive only when their points are within tol = max(1, 2 % of the
    distance) of the inset distance from the boundary.

    If pathops raises on the band subtraction, it is retried a hundredth of a unit shallower. If it returns nothing,
    the retry is kept only if its area is at least distance²: an inset too deep for the shape is empty, and a hundredth
    shallower it comes back as a hairline.
    """
    retry = distance > 2 * _RETRY_STEP  # a hundredth of a unit shallower must still be an inset
    try:
        result = _band_subtraction(shape, distance)
    except ValueError:  # where the band's edge lands exactly on the outline pathops can give up, raising ...
        if not retry:
            raise
        result = _band_subtraction(shape, distance - _RETRY_STEP)
    else:
        if result.is_empty and retry:  # ... or returning nothing, which is also what an inset too deep for the shape gives
            try:
                again = _band_subtraction(shape, distance - _RETRY_STEP)
            except ValueError:
                return result
            if again.area < distance**2:
                return result
            result = again
    limit = distance - max(1.0, 0.02 * distance)
    if limit <= 0 or result.is_empty:
        return result
    starts, ends = _edges(shape.flatten(steps=_OUTLINE_STEPS))
    nesting = contour_nesting(result.path, probes=5)
    kept: set[int] = set()
    for i, (outline, _, depth, _) in enumerate(nesting):
        if depth is None or depth % 2:
            continue
        holes = [j for j, (_, area, d, parent) in enumerate(nesting) if parent == i and d == depth + 1 and abs(area) >= _SLIVER_AREA]
        polys = [poly for j in (i, *holes) for poly in Shape(nesting[j][0]).flatten()]
        region_starts, region_ends = _edges(polys)
        if _clear_of(np.concatenate([region_starts, (region_starts + region_ends) / 2]), starts, ends, limit):
            kept |= {i, *holes}
    if len(kept) == len(nesting):
        return result
    path = skia.Path()
    for i, (contour, *_) in enumerate(nesting):
        if i in kept:
            path.addPath(contour)
    return result._with_path(path, result.free_segments)


def _edges(polys: list[list[tuple[float, float]]]) -> tuple[np.ndarray, np.ndarray]:
    """The edges of flattened contours as (start, end) point arrays, each contour closed as a fill closes it."""
    loops = [np.asarray(poly, dtype=float) for poly in polys if len(poly) > 1]
    if not loops:
        return np.zeros((0, 2)), np.zeros((0, 2))
    return np.concatenate(loops), np.concatenate([np.roll(loop, -1, axis=0) for loop in loops])


def _clear_of(points: np.ndarray, starts: np.ndarray, ends: np.ndarray, limit: float) -> bool:
    """Whether every point lies at least `limit` from every edge (start to end), by exact point-to-segment distance. An
    edge whose bounding box lies more than `limit` outside the points' cannot be that close to any of them: it is skipped."""
    lo, hi = points.min(axis=0) - limit, points.max(axis=0) + limit
    near = np.all(np.minimum(starts, ends) <= hi, axis=1) & np.all(np.maximum(starts, ends) >= lo, axis=1)
    sx, sy = starts[near, 0], starts[near, 1]
    ax, ay = ends[near, 0] - sx, ends[near, 1] - sy
    length2 = ax * ax + ay * ay
    length2[length2 == 0] = 1.0  # a zero-length edge has no direction, so t = 0 and it measures to its start
    chunk = max(1, _PAIRS // max(1, len(sx)))
    for k in range(0, len(points) if len(sx) else 0, chunk):
        rx, ry = points[k : k + chunk, 0:1] - sx, points[k : k + chunk, 1:2] - sy
        t = np.clip((rx * ax + ry * ay) / length2, 0.0, 1.0)
        gx, gy = rx - t * ax, ry - t * ay
        if (gx * gx + gy * gy).min() < limit * limit:
            return False
    return True


def translate(shape: Shape, dx: float, dy: float) -> Shape:
    return shape.transformed(skia.Matrix.Translate(dx, dy))


def rotate(shape: Shape, degrees: float, cx: float = 0, cy: float = 0) -> Shape:
    m = skia.Matrix.Translate(cx, cy)
    m.preRotate(degrees)
    m.preTranslate(-cx, -cy)
    return shape.transformed(m)


def scale(shape: Shape, sx: float, sy: float | None = None, cx: float = 0, cy: float = 0) -> Shape:
    """Scale about (cx, cy); sy defaults to sx.

    Exactly one negative factor is a reflection, and a reflection reverses every contour's direction (against the
    convention `normalize_winding` sets up). That is harmless for a shape on its own (nonzero fill and `Shape.area` are
    unaffected) and for boolean inputs (results are re-wound), but a mirrored and an unmirrored path must not be joined
    into one Shape without a boolean; mirror_x and mirror_y re-wind their results. Two negative factors are a
    180-degree rotation and keep directions.
    """
    m = skia.Matrix.Translate(cx, cy)
    m.preScale(sx, sx if sy is None else sy)
    m.preTranslate(-cx, -cy)
    return shape.transformed(m)


def _rewound(shape: Shape) -> Shape:
    return shape._with_path(normalize_winding(shape.path), shape.free_segments)


def mirror_x(shape: Shape, axis: float = 0.0) -> Shape:
    """Mirror across the vertical line x = axis, re-wound so contour directions follow the kit's convention."""
    return _rewound(scale(shape, -1, 1, cx=axis))


def mirror_y(shape: Shape, axis: float = 0.0) -> Shape:
    """Mirror across the horizontal line y = axis, re-wound so contour directions follow the kit's convention."""
    return _rewound(scale(shape, 1, -1, cy=axis))


def align(shape: Shape, to: Shape | Box, edge: str) -> Shape:
    tb = to if isinstance(to, Box) else to.bounds
    sb = shape.bounds
    moves = {
        "left": (tb.x0 - sb.x0, 0.0),
        "right": (tb.x1 - sb.x1, 0.0),
        "bottom": (0.0, tb.y0 - sb.y0),
        "top": (0.0, tb.y1 - sb.y1),
        "center": (tb.cx - sb.cx, 0.0),
        "middle": (0.0, tb.cy - sb.cy),
    }
    if edge not in moves:
        raise ValueError(f"edge must be one of {sorted(moves)}, got {edge!r}")
    return translate(shape, *moves[edge])


def center(shape: Shape, cx: float = 0, cy: float = 0, optical: bool = False) -> Shape:
    if optical:
        rx, ry = shape.centroid
    else:
        b = shape.bounds
        rx, ry = b.cx, b.cy
    return translate(shape, cx - rx, cy - ry)


def fit(shape: Shape, w: float, h: float, cx: float = 0, cy: float = 0) -> Shape:
    if not (w > 0 and h > 0):  # zero collapses the shape, a negative size flips it, NaN poisons it
        raise ValueError(f"fit needs a positive target width and height, got {w} x {h}")
    b = shape.bounds
    if b.w <= 0 or b.h <= 0:
        raise ValueError("fit needs a shape with non-zero width and height")
    factor = min(w / b.w, h / b.h)
    return center(scale(shape, factor, cx=b.cx, cy=b.cy), cx, cy)
