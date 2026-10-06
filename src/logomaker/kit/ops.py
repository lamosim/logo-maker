"""Boolean operations, strokes, transforms and alignment. Every function returns a new Shape.

A result has the kind of its first operand (Shape._with_path), so a TextShape wordmark keeps its metrics through a
notch, a stroke or a move.
"""
from __future__ import annotations

import skia

from .primitives import stroked_path
from .shape import Box, Shape, normalize_winding


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
    if distance == 0:
        return shape.copy()
    band = stroke(shape, 2 * abs(distance), join="round")
    result = union(shape, band) if distance > 0 else subtract(shape, band)
    return shape._with_path(result.path, shape.free_segments)  # the band is derived from shape: count its free segments once


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
    into one Shape without a boolean. Two negative factors are a 180-degree rotation and keep directions.
    """
    m = skia.Matrix.Translate(cx, cy)
    m.preScale(sx, sx if sy is None else sy)
    m.preTranslate(-cx, -cy)
    return shape.transformed(m)


def mirror_x(shape: Shape, axis: float = 0.0) -> Shape:
    """Mirror across the vertical line x = axis. Contour directions reverse (see `scale`)."""
    return scale(shape, -1, 1, cx=axis)


def mirror_y(shape: Shape, axis: float = 0.0) -> Shape:
    """Mirror across the horizontal line y = axis. Contour directions reverse (see `scale`)."""
    return scale(shape, 1, -1, cy=axis)


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
    b = shape.bounds
    if b.w <= 0 or b.h <= 0:
        raise ValueError("fit needs a shape with non-zero width and height")
    factor = min(w / b.w, h / b.h)
    return center(scale(shape, factor, cx=b.cx, cy=b.cy), cx, cy)
