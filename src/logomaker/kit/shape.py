"""Shape: a thin wrapper over skia.Path with the queries the kit and the audits need.

Coordinates are in the kit frame (y up). `to_path_data` flips y for SVG.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Iterator

import skia

Point = tuple[float, float]
Command = tuple[str, list[Point]]


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @classmethod
    def union(cls, boxes: Iterable["Box"]) -> "Box":
        boxes = list(boxes)
        return cls(min(b.x0 for b in boxes), min(b.y0 for b in boxes), max(b.x1 for b in boxes), max(b.y1 for b in boxes))


def fmt(value: float, precision: int = 2) -> str:
    """Format a number for SVG: fixed precision, no trailing zeros, never '-0' or exponents. NaN and infinities raise."""
    if not math.isfinite(value):
        raise ValueError(f"cannot write the non-finite number {value} into an SVG")
    rounded = round(value, precision)
    if rounded == 0:
        return "0"
    text = f"{rounded:.{precision}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _xy(p: skia.Point) -> Point:
    return (p.x(), p.y())


def _quad_to_cubic(p0: Point, q: Point, p2: Point) -> list[Point]:
    c1 = (p0[0] + 2 / 3 * (q[0] - p0[0]), p0[1] + 2 / 3 * (q[1] - p0[1]))
    c2 = (p2[0] + 2 / 3 * (q[0] - p2[0]), p2[1] + 2 / 3 * (q[1] - p2[1]))
    return [c1, c2, p2]


def path_from_commands(commands: Iterable[Command]) -> skia.Path:
    path = skia.Path()
    for kind, pts in commands:
        if kind == "M":
            path.moveTo(*pts[0])
        elif kind == "L":
            path.lineTo(*pts[0])
        elif kind == "C":
            path.cubicTo(*pts[0], *pts[1], *pts[2])
        elif kind == "Z":
            path.close()
    return path


def _cubic_points(p0: Point, c1: Point, c2: Point, p1: Point, steps: int) -> list[Point]:
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * p1[0]
        y = u**3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * p1[1]
        out.append((x, y))
    return out


def _signed_area_and_centroid(poly: list[Point]) -> tuple[float, Point]:
    if len(poly) < 3:
        return 0.0, (0.0, 0.0)
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a *= 0.5
    if abs(a) < 1e-12:
        return 0.0, (0.0, 0.0)
    return a, (cx / (6 * a), cy / (6 * a))


def _contains(poly: list[Point], point: Point) -> bool:
    """Ray-crossing point-in-polygon test; the polygon closes implicitly."""
    x, y = point
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _inside_probe(poly: list[Point], nudge: float = 1e-3) -> Point | None:
    """A point just inside `poly`: its longest edge's midpoint, nudged across the edge. None if neither side is inside."""
    (x0, y0), (x1, y1) = max(zip(poly, poly[1:] + poly[:1]), key=lambda edge: math.dist(*edge))
    length = math.dist((x0, y0), (x1, y1))
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    nx, ny = (y0 - y1) / length * nudge, (x1 - x0) / length * nudge
    for probe in ((mx + nx, my + ny), (mx - nx, my - ny)):
        if _contains(poly, probe):
            return probe
    return None


class Shape:
    __slots__ = ("path", "free_segments")

    def __init__(self, path: skia.Path | None = None, free_segments: int = 0):
        self.path = path if path is not None else skia.Path()
        self.free_segments = free_segments

    @classmethod
    def empty(cls) -> "Shape":
        return cls()

    def _with_path(self, path: skia.Path, free_segments: int) -> "Shape":
        """A shape of this kind on a new outline. Ops build every result through it, so a subclass that carries more
        than an outline (TextShape's metrics) extends this one method instead of each op special-casing it."""
        return Shape(path, free_segments)

    def copy(self) -> "Shape":
        return self._with_path(skia.Path(self.path), self.free_segments)

    @property
    def is_empty(self) -> bool:
        return self.path.isEmpty()

    @property
    def bounds(self) -> Box:
        r = self.path.computeTightBounds()
        return Box(r.left(), r.top(), r.right(), r.bottom())

    def commands(self) -> Iterator[Command]:
        """Yield M/L/C/Z commands; conics become quads (4 per conic) and quads become cubics."""
        it = skia.Path.Iter(self.path, False)
        current: Point = (0.0, 0.0)
        while True:
            verb, pts = it.next()
            if verb == skia.Path.Verb.kDone_Verb:
                return
            if verb == skia.Path.Verb.kMove_Verb:
                current = _xy(pts[0])
                yield ("M", [current])
            elif verb == skia.Path.Verb.kLine_Verb:
                if it.isCloseLine():
                    continue  # Iter synthesises the closing segment before kClose; the Z that follows implies it
                current = _xy(pts[1])
                yield ("L", [current])
            elif verb == skia.Path.Verb.kQuad_Verb:
                p0, q, p2 = _xy(pts[0]), _xy(pts[1]), _xy(pts[2])
                yield ("C", _quad_to_cubic(p0, q, p2))
                current = p2
            elif verb == skia.Path.Verb.kConic_Verb:
                quads = skia.Path.ConvertConicToQuads(pts[0], pts[1], pts[2], it.conicWeight(), 2)
                for i in range(0, len(quads) - 1, 2):
                    p0, q, p2 = _xy(quads[i]), _xy(quads[i + 1]), _xy(quads[i + 2])
                    yield ("C", _quad_to_cubic(p0, q, p2))
                    current = p2
            elif verb == skia.Path.Verb.kCubic_Verb:
                c1, c2, p1 = _xy(pts[1]), _xy(pts[2]), _xy(pts[3])
                yield ("C", [c1, c2, p1])
                current = p1
            elif verb == skia.Path.Verb.kClose_Verb:
                yield ("Z", [])

    def _contours(self) -> list[tuple[Point, list[Point], bool]]:
        """Each contour straight from the path's own verbs: (start, every segment's end point, closed). Unlike
        `commands()` nothing is split or added: a conic is one segment and the closing line stays implied."""
        contours: list[tuple[Point, list[Point], bool]] = []
        it = skia.Path.RawIter(self.path)
        while True:
            verb, pts = it.next()
            if verb == skia.Path.Verb.kDone_Verb:
                return contours
            if verb == skia.Path.Verb.kMove_Verb:
                contours.append((_xy(pts[0]), [], False))
            elif verb == skia.Path.Verb.kClose_Verb:
                start, ends, _ = contours[-1]
                contours[-1] = (start, ends, True)
            else:  # line, quad, conic or cubic: its last point is the on-curve end
                contours[-1][1].append(_xy(pts[-1]))

    def anchor_count(self) -> int:
        """On-curve nodes, as a designer counts them (a circle has 4): each contour's start and each segment's end
        point, an end point back on the start counted once. Control points and the SVG's conic splits do not count."""
        return sum(len(ends) + (0 if ends[-1] == start else 1) for start, ends, _ in self._contours() if ends)

    def segment_count(self) -> int:
        """Drawn segments, curves and lines alike (a circle has 4), counting a closed contour's implied closing line."""
        return sum(len(ends) + (1 if closed and ends[-1] != start else 0) for start, ends, closed in self._contours() if ends)

    def straight_segments(self) -> list[tuple[Point, Point]]:
        segments: list[tuple[Point, Point]] = []
        start = current = (0.0, 0.0)
        for kind, pts in self.commands():
            if kind == "M":
                start = current = pts[0]
            elif kind == "L":
                segments.append((current, pts[0]))
                current = pts[0]
            elif kind == "C":
                current = pts[2]
            elif kind == "Z":
                if current != start:
                    segments.append((current, start))
                current = start
        return segments

    def subpaths(self) -> list["Shape"]:
        groups: list[list[Command]] = []
        for cmd in self.commands():
            if cmd[0] == "M":
                groups.append([cmd])
            elif groups:
                groups[-1].append(cmd)
        return [Shape(path_from_commands(g), 0) for g in groups]

    def flatten(self, steps: int = 16) -> list[list[Point]]:
        polys: list[list[Point]] = []
        current: Point = (0.0, 0.0)
        for kind, pts in self.commands():
            if kind == "M":
                polys.append([pts[0]])
                current = pts[0]
            elif kind == "L":
                polys[-1].append(pts[0])
                current = pts[0]
            elif kind == "C":
                polys[-1].extend(_cubic_points(current, pts[0], pts[1], pts[2], steps))
                current = pts[2]
        return polys

    @property
    def area(self) -> float:
        return abs(sum(_signed_area_and_centroid(poly)[0] for poly in self.flatten()))

    @property
    def centroid(self) -> Point:
        total = cx = cy = 0.0
        for poly in self.flatten():
            a, (px, py) = _signed_area_and_centroid(poly)
            total += a
            cx += a * px
            cy += a * py
        if abs(total) < 1e-12:
            b = self.bounds
            return (b.cx, b.cy)
        return (cx / total, cy / total)

    def transformed(self, matrix: skia.Matrix) -> "Shape":
        dst = skia.Path()
        self.path.transform(matrix, dst)
        return self._with_path(dst, self.free_segments)

    def to_path_data(self, precision: int = 2, flip_y: bool = True) -> str:
        sign = -1.0 if flip_y else 1.0
        parts: list[str] = []
        for kind, pts in self.commands():
            if kind == "Z":
                parts.append("Z")
                continue
            coords = " ".join(f"{fmt(x, precision)} {fmt(sign * y, precision)}" for x, y in pts)
            parts.append(f"{kind}{coords}")
        return "".join(parts)


def normalize_winding(path: skia.Path) -> skia.Path:
    """Return a copy of `path` whose contour directions alternate with containment depth.

    Pathops return even-odd paths with arbitrary contour directions. Here contours at even depth run counter-clockwise
    (positive signed area) and those at odd depth clockwise, so fill-rule nonzero and even-odd agree and `Shape.area`
    is right. The input is read as even-odd and its contours must not cross each other (Simplify output or hand-built
    nested contours); overlapping contours are not merged. Contours keep their order; degenerate ones, and any without
    an inside probe point, pass through unchanged. The result has winding fill.
    """
    parts = Shape(path).subpaths()
    polys = [part.flatten()[0] for part in parts]
    areas = [_signed_area_and_centroid(poly)[0] for poly in polys]
    containers = [j for j, a in enumerate(areas) if abs(a) >= 1e-9]
    out = skia.Path()
    for i, part in enumerate(parts):
        probe = _inside_probe(polys[i]) if abs(areas[i]) >= 1e-9 else None
        if probe is None:
            out.addPath(part.path)
            continue
        depth = sum(1 for j in containers if j != i and _contains(polys[j], probe))
        if (areas[i] > 0) == (depth % 2 == 0):
            out.addPath(part.path)
        else:
            out.reverseAddPath(part.path)
    out.setFillType(skia.PathFillType.kWinding)
    return out
