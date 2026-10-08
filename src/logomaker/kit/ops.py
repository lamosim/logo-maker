"""Boolean operations, strokes, transforms and alignment. Every function returns a new Shape.

A result has the kind of its first operand (Shape._with_path), so a TextShape wordmark keeps its metrics through a
notch, a stroke or a move.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import skia

from .primitives import rect, snap, snap_angle, stroked_path
from .shape import Box, Point, Shape, _quad_to_cubic, _xy, contour_nesting, normalize_winding, path_from_commands


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


@dataclass(frozen=True)
class Node:
    index: int
    x: float
    y: float
    subpath: int
    smooth: bool


@dataclass
class _Contour:
    """An editable contour: `start`, then segments ("L", [end]) or ("C", [c1, c2, end]). A closed contour's last segment
    ends on `start` (one is added when the path's Z implied it), so its nodes are start plus every segment end but the
    last, and node i has segs[i - 1] coming in and segs[i] going out, modulo the count."""

    start: Point
    segs: list[tuple[str, list[Point]]] = field(default_factory=list)
    closed: bool = False

    def node_count(self) -> int:
        return len(self.segs) if self.closed else len(self.segs) + 1

    def point(self, i: int) -> Point:
        return self.start if i == 0 else self.segs[i - 1][1][-1]


def _conic_to_cubic(p0: Point, q: Point, p2: Point, weight: float) -> list[Point]:
    """One cubic for a conic: control points a fraction 4w / (3 (1 + w)) of the way from each end to the conic's
    control point. For a quarter-circle conic (w = cos 45°) that is the 0.5523 a circle's cubic uses."""
    k = 4 * weight / (3 * (1 + weight))
    return [(p0[0] + (q[0] - p0[0]) * k, p0[1] + (q[1] - p0[1]) * k), (p2[0] + (q[0] - p2[0]) * k, p2[1] + (q[1] - p2[1]) * k), p2]


def _parse(shape: Shape) -> list[_Contour]:
    """The path's own verbs, one segment each: a line stays a line, a quad and a conic become one cubic each (never the
    four quads Shape.commands splits a conic into, which would give a circle 16 nodes), a cubic stays. A closed contour
    gets an explicit last segment back to its start when the Z implied it."""
    contours: list[_Contour] = []
    it = skia.Path.RawIter(shape.path)
    current: Point = (0.0, 0.0)
    while True:
        verb, pts = it.next()
        if verb == skia.Path.Verb.kDone_Verb:
            break
        if verb == skia.Path.Verb.kMove_Verb:
            current = _xy(pts[0])
            contours.append(_Contour(current))
        elif verb == skia.Path.Verb.kClose_Verb:
            c = contours[-1]
            c.closed = True
            if c.segs and math.dist(c.segs[-1][1][-1], c.start) > 1e-6:
                c.segs.append(("L", [c.start]))
            current = c.start
        elif verb == skia.Path.Verb.kLine_Verb:
            current = _xy(pts[1])
            contours[-1].segs.append(("L", [current]))
        elif verb == skia.Path.Verb.kQuad_Verb:
            contours[-1].segs.append(("C", _quad_to_cubic(current, _xy(pts[1]), _xy(pts[2]))))
            current = _xy(pts[2])
        elif verb == skia.Path.Verb.kConic_Verb:
            contours[-1].segs.append(("C", _conic_to_cubic(current, _xy(pts[1]), _xy(pts[2]), it.conicWeight())))
            current = _xy(pts[2])
        elif verb == skia.Path.Verb.kCubic_Verb:
            contours[-1].segs.append(("C", [_xy(pts[1]), _xy(pts[2]), _xy(pts[3])]))
            current = _xy(pts[3])
    return [c for c in contours if c.segs]


def _emit(shape: Shape, contours: list[_Contour]) -> Shape:
    commands = []
    for c in contours:
        segs = c.segs
        if c.closed and len(segs) > 1 and segs[-1][0] == "L" and math.dist(segs[-1][1][-1], c.start) <= 1e-6:
            segs = segs[:-1]  # the Z draws the closing line, as the source path did
        commands.append(("M", [c.start]))
        commands += [(kind, pts) for kind, pts in segs]
        if c.closed:
            commands.append(("Z", []))
    return shape._with_path(normalize_winding(path_from_commands(commands)), shape.free_segments)


def _locate(contours: list[_Contour], index: int) -> tuple[_Contour, int]:
    offset_ = 0
    for c in contours:
        if 0 <= index < offset_ + c.node_count():
            return c, index - offset_
        offset_ += c.node_count()
    raise ValueError(f"no node {index}; the shape has {offset_} nodes")


def _neighbours(c: _Contour, i: int) -> tuple[tuple[str, list[Point]] | None, tuple[str, list[Point]] | None]:
    """The segment into node i and the one out of it (None at an open contour's ends)."""
    n = c.node_count()
    incoming = c.segs[(i - 1) % len(c.segs)] if (c.closed or i > 0) else None
    outgoing = c.segs[i % len(c.segs)] if (c.closed or i < n - 1) else None
    return incoming, outgoing


def nodes(shape: Shape) -> list[Node]:
    """The on-curve nodes in path order: each contour's start and segment ends (a closed contour's return to its start
    counted once). `smooth` is whether the handles either side of a node are collinear with it. The editing ops rebuild
    the whole shape from these nodes, so every conic in it becomes one cubic (off by less than a snap step), and an
    off-grid `dx`/`dy` in move_node is not counted as a free segment."""
    out: list[Node] = []
    index = 0
    for subpath, c in enumerate(_parse(shape)):
        for i in range(c.node_count()):
            x, y = c.point(i)
            incoming, outgoing = _neighbours(c, i)
            smooth = False
            if incoming and outgoing:
                before = incoming[1][-2] if incoming[0] == "C" else c.point((i - 1) % c.node_count())  # the handle, or the node before
                after = outgoing[1][0] if outgoing[0] == "C" else outgoing[1][-1]
                ax, ay, bx, by = x - before[0], y - before[1], after[0] - x, after[1] - y
                cross, dot = ax * by - ay * bx, ax * bx + ay * by
                smooth = dot > 0 and abs(cross) <= 1e-3 * (math.hypot(ax, ay) * math.hypot(bx, by) or 1)
            out.append(Node(index, x, y, subpath, smooth))
            index += 1
    return out


def move_node(shape: Shape, index: int, dx: float, dy: float) -> Shape:
    """`shape` with node `index` and the two handles attached to it moved by (dx, dy)."""
    contours = _parse(shape)
    c, i = _locate(contours, index)
    x, y = c.point(i)
    moved = (x + dx, y + dy)
    if i == 0:
        c.start = moved
    else:
        c.segs[i - 1][1][-1] = moved
    if c.closed and i == 0:
        c.segs[-1][1][-1] = moved  # the explicit return to the start
    incoming, outgoing = _neighbours(c, i)
    if incoming and incoming[0] == "C":
        incoming[1][1] = (incoming[1][1][0] + dx, incoming[1][1][1] + dy)
    if outgoing and outgoing[0] == "C":
        outgoing[1][0] = (outgoing[1][0][0] + dx, outgoing[1][0][1] + dy)
    return _emit(shape, contours)


def delete_node(shape: Shape, index: int) -> Shape:
    """`shape` without node `index`: its two segments become one, a line when both were lines, else a cubic keeping the
    outer handles (the incoming segment's first handle and the outgoing segment's second). An open contour's endpoint
    cannot be deleted."""
    contours = _parse(shape)
    c, i = _locate(contours, index)
    incoming, outgoing = _neighbours(c, i)
    if incoming is None or outgoing is None:
        raise ValueError("an open contour's endpoint cannot be deleted")
    if c.closed and c.node_count() <= 3:
        raise ValueError("a contour keeps at least three nodes")
    before = c.point((i - 1) % c.node_count())
    end = outgoing[1][-1]
    if incoming[0] == "L" and outgoing[0] == "L":
        merged = ("L", [end])
    else:
        c1 = incoming[1][0] if incoming[0] == "C" else before
        c2 = outgoing[1][1] if outgoing[0] == "C" else end
        merged = ("C", [c1, c2, end])
    n = len(c.segs)
    if i == 0:  # the start goes: node 1 becomes the start, and the merged segment closes the loop
        c.start = c.segs[0][1][-1]
        c.segs = c.segs[1:n - 1] + [merged]
    else:
        c.segs[i - 1:i + 1] = [merged]
    return _emit(shape, contours)


_HALF = 100000.0  # far beyond the canvas: a half-plane for cut()


def _on_grid(x: float, y: float, angle: float) -> bool:
    """Whether a line through (x, y) at `angle` degrees is one a snapped primitive could draw: the point on the grid
    `_v` snaps to and the angle a multiple of the step `_a` snaps to."""
    return all(math.isclose(snap(v), v, abs_tol=1e-6) for v in (x, y)) and math.isclose(snap_angle(angle), angle, abs_tol=1e-6)


def cut(shape: Shape, x1: float, y1: float, x2: float, y2: float) -> tuple[Shape, Shape]:
    """`shape` split along the line through (x1, y1) and (x2, y2): (left, right), left being the side to the left when
    travelling from the first point to the second. A line that misses leaves one side whole and the other empty. A
    non-empty half counts `shape`'s free segments plus one (its cut edge) unless the line is on the grid; an empty half
    counts none."""
    if math.isclose(x1, x2, abs_tol=1e-9) and math.isclose(y1, y2, abs_tol=1e-9):
        raise ValueError("cut needs two distinct points")
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    left_half = translate(rotate(rect(-_HALF, 0, 2 * _HALF, _HALF, free=True), angle), x1, y1)
    right_half = translate(rotate(rect(-_HALF, -_HALF, 2 * _HALF, _HALF, free=True), angle), x1, y1)
    extra = 0 if _on_grid(x1, y1, angle) else 1

    def half(plane: Shape) -> Shape:
        part = intersect(shape, plane)
        return part._with_path(part.path, 0 if part.is_empty else shape.free_segments + extra)

    return half(left_half), half(right_half)
