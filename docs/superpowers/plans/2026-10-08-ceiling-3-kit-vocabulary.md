# Raising the Ceiling, Plan 3: Kit Vocabulary and Wordmark Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the kit past heavy geometric glyphs: variable-width strokes, splines through points, node-level editing of any outline including real glyphs, repetition in one call, module-wide free snapping, and a wordmark stage that makes letter spacing visible and audited.

**Architecture:** New primitives and ops sit beside the existing ones in `kit/primitives.py` and `kit/ops.py`, each returning a `Shape` and keeping a `TextShape` first operand's metrics. A new `kit/fit.py` fits polylines back to cubic Béziers (Schneider's least-squares method) so a brushed stroke keeps a designer's anchor count. Module-wide snapping is a context variable the concept loader sets from `Meta.snap`. The wordmark stage is a sheet plus one audit line, both reading glyph gaps from `TextShape`.

**Tech Stack:** skia-python (paths, booleans, Simplify), fontTools and uharfbuzz (glyph outlines, already in `kit/text.py`), numpy where the kit already uses it, jinja2 for the sheet, pytest.

**Spec:** `docs/superpowers/specs/2026-10-08-raising-the-ceiling-design.md`, section 5 (WS3), with section 13 for the fit's fallback. The kit's existing contract is `.claude/skills/logo/reference/kit-api.md` and spec 2026-10-05 section 6.

**Prerequisite:** Plans 1 and 2 are merged and the `baseline` cycle is recorded (spec section 11).

## Global Constraints

- Canvas: 1000 units, origin at the centre, y up; coordinates snap to 0.25 units and angles to 15 degrees unless `free=True` or the module sets `snap="free"`.
- Every op returns a new `Shape` of its first operand's kind through `Shape._with_path`, so a `TextShape` keeps its metrics.
- Anchor rules are unchanged: the symbol warns above 100 on-curve nodes and fails above 150 unless `allow_complex` with a reason.
- Every output path is re-wound through `normalize_winding` after a boolean, so fill-rule nonzero and `Shape.area` agree.
- Every public kit name is exported in `kit/__init__.py` `__all__` and documented in `kit-api.md` in backticks (`tests/test_knowledge.py::test_kit_api_names_every_public_kit_name`).
- kit-api.md's worked examples are under 40 lines each, build `full`, `small` and `favicon`, pass the audit with Fira Code cached, and `tests/test_knowledge.py` lists each one's expected warnings and logo type.
- Ruff clean; commit per task with the attribution line from the session's system reminder.

## Review Focus

1. A brush whose width at a node exceeds twice the local radius of curvature (a tight hook): the offset side crosses itself; the result must still be a valid filled shape with no stray slivers, never a pathops error. Pinned in Task 2.
2. A `cut` whose line misses the shape entirely: one side is the whole shape, the other is empty, and neither raises. Pinned in Task 4.
3. `delete_node` on an open contour's endpoint: refused with a clear error, since there is nothing to join. Pinned in Task 4.
4. A wordmark with a ligature (fewer drawn glyphs than characters): gap labels still come out right, from the glyph's own characters, never an index error. Pinned in Task 7.
5. A concept module with `snap="free"` whose build also passes `free=True` explicitly: no double counting, no error; and a module with `snap="grid"` behaves exactly as today. Pinned in Task 6.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/logomaker/kit/fit.py` (create) | `fit_cubics`: polyline to cubic Béziers within a tolerance |
| `src/logomaker/kit/primitives.py` (modify) | `brush`, `spline`, the `FREE_ALL` context variable and `free_snapping` |
| `src/logomaker/kit/ops.py` (modify) | `Node`, `nodes`, `move_node`, `delete_node`, `cut`, `repeat` |
| `src/logomaker/kit/concept.py` (modify) | `Meta.snap`; `build_tiers` sets the context |
| `src/logomaker/kit/text.py` (modify) | `TextShape.glyph_chars`; `wordmark_gaps` |
| `src/logomaker/kit/__init__.py` (modify) | exports |
| `src/logomaker/audit.py` (modify) | `spacing_rhythm` |
| `src/logomaker/sheets.py` (modify), `templates/sheets/wordmark.html` (create) | the wordmark sheet |
| `src/logomaker/cli.py` (modify) | `sheet wordmark` |
| `.claude/skills/logo/reference/kit-api.md`, `craft.md`, `SKILL.md` (modify) | documentation |
| `tests/test_kit_fit.py` (create), `tests/test_kit_primitives.py`, `tests/test_kit_ops.py`, `tests/test_kit_text.py`, `tests/test_concept.py`, `tests/test_audit.py`, `tests/test_sheets.py`, `tests/test_knowledge.py` (modify) | tests |

---

### Task 1: `fit_cubics`

**Files:**
- Create: `src/logomaker/kit/fit.py`
- Test: `tests/test_kit_fit.py`

**Interfaces:**
- Produces: `fit.Point = tuple[float, float]`; `fit.Cubic = tuple[Point, Point, Point, Point]` (p0, c1, c2, p1); `fit.fit_cubics(points: list[Point], tolerance: float = 0.5) -> list[Cubic]`; `fit.cubic_at(c: Cubic, t: float) -> Point`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_kit_fit.py
import math

import pytest

from logomaker.kit.fit import cubic_at, fit_cubics


def arc_points(r: float, start: float, end: float, n: int) -> list[tuple[float, float]]:
    return [(r * math.cos(math.radians(start + (end - start) * i / n)), r * math.sin(math.radians(start + (end - start) * i / n)))
            for i in range(n + 1)]


def max_distance(points, cubics, samples=50) -> float:
    """The largest distance from any sampled curve point to the nearest input point."""
    worst = 0.0
    for c in cubics:
        for i in range(samples + 1):
            x, y = cubic_at(c, i / samples)
            worst = max(worst, min(math.dist((x, y), p) for p in points))
    return worst


def test_a_straight_run_is_one_cubic():
    cubics = fit_cubics([(0, 0), (10, 0), (20, 0), (30, 0)])
    assert len(cubics) == 1 and cubics[0][0] == (0, 0) and cubics[0][3] == (30, 0)


def test_a_quarter_circle_fits_within_tolerance_with_few_segments():
    points = arc_points(400, 0, 90, 64)
    cubics = fit_cubics(points, tolerance=0.5)
    assert 1 <= len(cubics) <= 3
    assert cubics[0][0] == points[0] and cubics[-1][3] == points[-1]
    assert max_distance(points, cubics) < 1.0  # the samples are 10 units apart; the curve must hug them


def test_a_sharp_corner_splits_there():
    points = [(i, 0) for i in range(0, 101, 10)] + [(100, i) for i in range(10, 101, 10)]
    cubics = fit_cubics(points, tolerance=0.5)
    assert any(math.dist(c[3], (100, 0)) < 2 for c in cubics[:-1])  # a segment ends at the corner


def test_two_points_and_fewer_are_handled():
    assert fit_cubics([(0, 0), (30, 40)]) == [((0, 0), (10, 40 / 3), (20, 80 / 3), (30, 40))]
    with pytest.raises(ValueError, match="at least two points"):
        fit_cubics([(0, 0)])


def test_tolerance_must_be_positive():
    with pytest.raises(ValueError, match="tolerance must be positive"):
        fit_cubics([(0, 0), (1, 1), (2, 0)], tolerance=0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_kit_fit.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker.kit.fit'`.

- [ ] **Step 3: Write the module**

```python
# src/logomaker/kit/fit.py
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
        tmp = _sub(p, _add(_add(_mul(first, b0 + b1), _mul(last, b2 + b3)), (0.0, 0.0)))
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
        chord = _sub(points[1], points[0])
        return [(points[0], _add(points[0], _mul(chord, 1 / 3)), _add(points[0], _mul(chord, 2 / 3)), points[1])]
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_kit_fit.py -q`
Expected: 5 passed. If the quarter-circle test needs more than three segments, raise the error budget that triggers reparameterisation (`tolerance * 4`) to `tolerance * 8` and re-run; do not loosen the test.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/kit/fit.py tests/test_kit_fit.py
git commit -m "feat: fit_cubics fits a polyline with cubic Béziers"
```

---

### Task 2: `brush`

**Files:**
- Modify: `src/logomaker/kit/primitives.py`, `src/logomaker/kit/__init__.py`
- Test: `tests/test_kit_primitives.py` (extend)

**Interfaces:**
- Consumes: `fit.fit_cubics`, `shape._cubic_points`, `primitives.line`, `primitives.circle`, `ops.union` (imported inside the function: `ops` imports `primitives`).
- Produces: `primitives.brush(points, widths, cap="round", free=False) -> Shape`; `primitives.BRUSH_STEPS = 24` (samples per segment).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_kit_primitives.py`:

```python
from logomaker.kit.primitives import brush

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_kit_primitives.py -q -k brush`
Expected: FAIL with `ImportError: cannot import name 'brush'`.

- [ ] **Step 3: Write `brush`**

Append to `src/logomaker/kit/primitives.py`:

```python
BRUSH_STEPS = 24  # samples per cubic segment when offsetting a brush's sides


def _brush_samples(pts: list[tuple[float, float]], widths: list[float]) -> list[tuple[tuple[float, float], float]]:
    """(point, width) along the chain: the width runs linearly by arc length between on-curve nodes."""
    from .shape import _cubic_points

    samples = [(pts[0], widths[0])]
    for seg in range(len(widths) - 1):
        p0, c1, c2, p1 = pts[3 * seg], pts[3 * seg + 1], pts[3 * seg + 2], pts[3 * seg + 3]
        chain = _cubic_points(p0, c1, c2, p1, BRUSH_STEPS)
        lengths = [0.0]
        prev = p0
        for p in chain:
            lengths.append(lengths[-1] + math.dist(prev, p))
            prev = p
        total = lengths[-1] or 1.0
        for p, length in zip(chain, lengths[1:]):
            samples.append((p, widths[seg] + (widths[seg + 1] - widths[seg]) * length / total))
    return samples


def brush(points: list[tuple[float, float]], widths: float | list[float], cap: str = "round", free: bool = False) -> Shape:
    """A stroke of varying width along a cubic chain (`points` as for bezier: 1 + 3k points). `widths` is one width per
    on-curve node, interpolated linearly by arc length between nodes, or one number for all. The sides are sampled,
    offset along the normals and fitted back to cubics (kit.fit), so the result keeps a designer's anchor count; where
    a side folds (a width over twice the local radius) the simplify step resolves the overlap. Caps: round (discs at
    the ends), square (half a width beyond each end), butt."""
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
    if any(not math.isfinite(w) or w <= 0 for w in widths):
        raise ValueError("brush widths must be positive")
    if cap not in CAPS:
        raise ValueError(f"cap must be one of {sorted(CAPS)}, got {cap!r}")
    pts = [(_v(x, free), _v(y, free)) for x, y in points]
    widths = [_v(w, free) for w in widths]
    samples = _brush_samples(pts, widths)
    left, right = [], []
    for i, (p, w) in enumerate(samples):
        before = samples[max(i - 1, 0)][0]
        after = samples[min(i + 1, len(samples) - 1)][0]
        tx, ty = after[0] - before[0], after[1] - before[1]
        length = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / length, tx / length  # the left normal
        left.append((p[0] + nx * w / 2, p[1] + ny * w / 2))
        right.append((p[0] - nx * w / 2, p[1] - ny * w / 2))
    path = skia.Path()
    first = True
    for side in (fit_cubics(left), fit_cubics(list(reversed(right)))):
        for c in side:
            if first:
                path.moveTo(*c[0])
                first = False
            else:
                path.lineTo(*c[0])  # a zero-length join where the sides meet; Simplify drops it
            path.cubicTo(*c[1], *c[2], *c[3])
    path.close()
    body = Shape(normalize_winding(skia.Simplify(path)))
    body = Shape(normalize_winding(_drop_slivers(body.path)))
    if cap == "butt":
        return _finish(body.path, free)
    ends = [(samples[0][0], samples[1][0], widths[0]), (samples[-1][0], samples[-2][0], widths[-1])]
    extras = []
    for end, inner, w in ends:
        if cap == "round":
            extras.append(circle(end[0], end[1], w / 2, free=True))
        else:
            dx, dy = end[0] - inner[0], end[1] - inner[1]
            length = math.hypot(dx, dy) or 1.0
            tip = (end[0] + dx / length * w / 2, end[1] + dy / length * w / 2)
            extras.append(line(end[0], end[1], tip[0], tip[1], w, cap="butt", free=True))
    return _finish(union(body, *extras).path, free)


def _drop_slivers(path: skia.Path, min_area: float = 1.0) -> skia.Path:
    """`path` without contours under `min_area` unit²: the slivers a folded brush side leaves after Simplify."""
    from .shape import contour_nesting

    out = skia.Path()
    for contour, area, _, _ in contour_nesting(path):
        if abs(area) >= min_area:
            out.addPath(contour)
    return out
```

Add `brush` to the import list and `__all__` in `src/logomaker/kit/__init__.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_kit_primitives.py -q`
Expected: all passed. If the anchor test fails, print `brush(...).anchor_count()` and the side counts; raise `BRUSH_STEPS` only if the fit is undersampled, otherwise check that `fit_cubics` is being called on the full side, not per segment.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/kit tests/test_kit_primitives.py
git commit -m "feat: brush draws a variable-width stroke with fitted sides"
```

---

### Task 3: `spline`

**Files:**
- Modify: `src/logomaker/kit/primitives.py`, `src/logomaker/kit/__init__.py`
- Test: `tests/test_kit_primitives.py` (extend)

**Interfaces:**
- Consumes: `primitives.bezier`.
- Produces: `primitives.spline(points, tension=0.5, closed=True, width=None, free=False) -> Shape`; `primitives.catmull_rom(points, tension, closed) -> list[Point]` (the cubic chain, 1 + 3k points, for a test and for `brush`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_kit_primitives.py`:

```python
from logomaker.kit.primitives import catmull_rom, spline

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_kit_primitives.py -q -k spline`
Expected: FAIL with `ImportError: cannot import name 'catmull_rom'`.

- [ ] **Step 3: Write `catmull_rom` and `spline`**

Append to `src/logomaker/kit/primitives.py`:

```python
def catmull_rom(points: list[tuple[float, float]], tension: float = 0.5, closed: bool = True) -> list[tuple[float, float]]:
    """The cubic chain (1 + 3k points, as bezier takes) of a Catmull-Rom spline through `points`. `tension` 0 is the
    uniform spline, 1 straight chords. Open splines clamp their end neighbours."""
    n = len(points)
    if n < 3:
        raise ValueError("spline needs at least three points")
    if not 0 <= tension <= 1:
        raise ValueError(f"tension must be between 0 and 1, got {tension}")
    k = (1 - tension) / 6
    segments = n if closed else n - 1

    def at(i: int) -> tuple[float, float]:
        return points[i % n] if closed else points[min(max(i, 0), n - 1)]

    chain = [points[0]]
    for i in range(segments):
        p0, p1, p2, p3 = at(i - 1), at(i), at(i + 1), at(i + 2)
        c1 = (p1[0] + (p2[0] - p0[0]) * k, p1[1] + (p2[1] - p0[1]) * k)
        c2 = (p2[0] - (p3[0] - p1[0]) * k, p2[1] - (p3[1] - p1[1]) * k)
        chain += [c1, c2, p2]
    return chain


def spline(points: list[tuple[float, float]], tension: float = 0.5, closed: bool = True, width: float | None = None,
           free: bool = False) -> Shape:
    """A smooth curve through `points` (catmull_rom): filled when `width` is None, else stroked, as bezier draws it."""
    return bezier(catmull_rom(points, tension, closed), width=width, closed=closed, free=free)
```

Export `spline` and `catmull_rom` in `kit/__init__.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_kit_primitives.py -q`
Expected: all passed. Note: a closed chain's last node repeats the first, so `bezier` closes it on itself; `anchor_count` counts the start once, giving 4 for the diamond.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/kit tests/test_kit_primitives.py
git commit -m "feat: spline draws a Catmull-Rom curve through points"
```

---

### Task 4: Node editing: `nodes`, `move_node`, `delete_node`, `cut`

**Files:**
- Modify: `src/logomaker/kit/ops.py`, `src/logomaker/kit/__init__.py`
- Test: `tests/test_kit_ops.py` (extend)

**Interfaces:**
- Consumes: `Shape.commands`, `shape.path_from_commands`, `ops.intersect`, `ops.rotate`, `ops.translate`, `primitives.rect`.
- Produces: `ops.Node(index: int, x: float, y: float, subpath: int, smooth: bool)`; `ops.nodes(shape) -> list[Node]`; `ops.move_node(shape, index, dx, dy) -> Shape`; `ops.delete_node(shape, index) -> Shape`; `ops.cut(shape, x1, y1, x2, y2) -> tuple[Shape, Shape]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_kit_ops.py`:

```python
from logomaker.kit.ops import cut, delete_node, move_node, nodes
from logomaker.kit.primitives import circle, polygon, rect, spline
from logomaker.kit.shape import Shape, path_from_commands
from logomaker.kit.text import glyph


def test_nodes_lists_on_curve_points_in_path_order():
    square = rect(0, 0, 100, 100)
    found = nodes(square)
    assert [(n.index, n.subpath) for n in found] == [(0, 0), (1, 0), (2, 0), (3, 0)]
    assert {(n.x, n.y) for n in found} == {(0, 0), (100, 0), (100, 100), (0, 100)}
    assert all(not n.smooth for n in found)
    disc = nodes(circle(0, 0, 100))
    assert len(disc) == 4 and all(n.smooth for n in disc)
    assert len(nodes(spline([(0, 300), (300, 0), (0, -300), (-300, 0)]))) == 4


def test_move_node_moves_the_point_and_its_handles():
    square = rect(0, 0, 100, 100)
    corner = next(n for n in nodes(square) if (n.x, n.y) == (100, 100))
    moved = move_node(square, corner.index, 50, 0)
    assert {(n.x, n.y) for n in nodes(moved)} == {(0, 0), (100, 0), (150, 100), (0, 100)}
    assert math.isclose(moved.area, 100 * 100 + 50 * 100 / 2)
    disc = circle(0, 0, 100)
    top = next(n for n in nodes(disc) if n.y > 99)
    taller = move_node(disc, top.index, 0, 50)
    assert math.isclose(taller.bounds.y1, 150, abs_tol=0.01) and taller.area > disc.area
    assert taller.anchor_count() == 4  # the handles moved with the node, no new segment
    with pytest.raises(ValueError, match="no node 9"):
        move_node(square, 9, 1, 1)


def test_delete_node_joins_the_neighbours():
    square = rect(0, 0, 100, 100)
    corner = next(n for n in nodes(square) if (n.x, n.y) == (100, 100))
    tri = delete_node(square, corner.index)
    assert tri.anchor_count() == 3 and math.isclose(tri.area, 5000)
    disc = circle(0, 0, 100)
    three = delete_node(disc, nodes(disc)[0].index)
    assert three.anchor_count() == 3 and three.area < disc.area
    open_curve = spline([(-300, 0), (0, 200), (300, 0)], closed=False)  # filled, so bezier closes it: three nodes, one implied line
    with pytest.raises(ValueError, match="a contour keeps at least three nodes"):
        delete_node(open_curve, nodes(open_curve)[1].index)
    open_path = Shape(path_from_commands([("M", [(0.0, 0.0)]), ("L", [(100.0, 0.0)]), ("L", [(100.0, 100.0)])]))
    with pytest.raises(ValueError, match="an open contour's endpoint cannot be deleted"):
        delete_node(open_path, nodes(open_path)[0].index)
    assert delete_node(open_path, nodes(open_path)[1].index).anchor_count() == 2


def test_cut_splits_along_a_line_and_keeps_text_metrics():
    square = rect(-100, -100, 200, 200)
    left, right = cut(square, 0, -500, 0, 500)  # travelling up: left is x < 0
    assert math.isclose(left.area, 20000) and math.isclose(right.area, 20000)
    assert left.bounds.x1 <= 0.01 and right.bounds.x0 >= -0.01
    whole, nothing = cut(square, 500, -500, 500, 500)  # a line that misses: everything is on the left
    assert math.isclose(whole.area, 40000) and nothing.is_empty
    k = glyph("K", "Fira Code", weight=700, cap_height=600)
    top, bottom = cut(k, -500, 300, 500, 300)
    assert hasattr(top, "cap_height") and top.cap_height == k.cap_height and bottom.area > 0


def test_delete_node_on_a_glyph_keeps_it_a_text_shape():
    o = glyph("O", "Fira Code", weight=700, cap_height=600)
    first = nodes(o)[0].index
    fewer = delete_node(o, first)
    assert hasattr(fewer, "cap_height") and fewer.anchor_count() == o.anchor_count() - 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_kit_ops.py -q -k "nodes or move_node or delete_node or cut"`
Expected: FAIL with `ImportError: cannot import name 'cut'`.

- [ ] **Step 3: Write the node editing ops**

Append to `src/logomaker/kit/ops.py`:

```python
from dataclasses import dataclass, field

from .shape import Point, path_from_commands


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
    from .shape import _quad_to_cubic, _xy

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
        commands.append(("M", [c.start]))
        commands += [(kind, pts) for kind, pts in c.segs]
        if c.closed:
            commands.append(("Z", []))
    return shape._with_path(normalize_winding(path_from_commands(commands)), shape.free_segments)


def _locate(contours: list[_Contour], index: int) -> tuple[_Contour, int]:
    offset_ = 0
    for c in contours:
        if index < offset_ + c.node_count():
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
    counted once). `smooth` is whether the handles either side of a node are collinear with it."""
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


def cut(shape: Shape, x1: float, y1: float, x2: float, y2: float) -> tuple[Shape, Shape]:
    """`shape` split along the line through (x1, y1) and (x2, y2): (left, right), left being the side to the left when
    travelling from the first point to the second. A line that misses leaves one side whole and the other empty."""
    from .primitives import rect

    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    left_half = translate(rotate(rect(-_HALF, 0, 2 * _HALF, _HALF, free=True), angle), x1, y1)
    right_half = translate(rotate(rect(-_HALF, -_HALF, 2 * _HALF, _HALF, free=True), angle), x1, y1)
    return intersect(shape, left_half), intersect(shape, right_half)
```

Add `import math` at the top of `ops.py`, and export `Node`, `nodes`, `move_node`, `delete_node`, `cut` in `kit/__init__.py`. `_quad_to_cubic` and `_xy` are private helpers of `kit/shape.py` that `ops.py` may import (both modules are the kit's own).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_kit_ops.py -q`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/kit tests/test_kit_ops.py
git commit -m "feat: node editing: nodes, move_node, delete_node and cut"
```

---

### Task 5: `repeat`

**Files:**
- Modify: `src/logomaker/kit/ops.py`, `src/logomaker/kit/__init__.py`
- Test: `tests/test_kit_ops.py` (extend)

**Interfaces:**
- Produces: `ops.repeat(shape, n, mode="radial", cx=0, cy=0, cols=None, step=None, axis=None) -> Shape`.

- [ ] **Step 1: Write the failing tests**

```python
from logomaker.kit.ops import repeat


def test_repeat_radial_grid_and_mirror():
    petal = rect(150, -20, 100, 40)
    six = repeat(petal, 6, cx=0, cy=0)
    assert math.isclose(six.area, 6 * 4000, rel_tol=0.01) and six.anchor_count() == 24
    dots = repeat(circle(0, 0, 20), 5, mode="grid", cols=3, step=100)
    assert math.isclose(dots.area, 5 * math.pi * 400, rel_tol=0.01)
    b = dots.bounds
    assert math.isclose(b.cx, 0, abs_tol=0.01) and math.isclose(b.cy, 0, abs_tol=0.01)  # the grid is centred on (cx, cy)
    assert b.w > 200 and b.h > 100
    half = polygon([(0, 0), (100, 0), (0, 100)])
    both = repeat(half, 2, mode="mirror", axis="x")
    assert math.isclose(both.area, 10000) and both.bounds.x0 == -100
    four = repeat(half, 4, mode="mirror", axis="xy")
    assert math.isclose(four.area, 20000)
    with pytest.raises(ValueError, match="grid needs cols and step"):
        repeat(petal, 4, mode="grid")
    with pytest.raises(ValueError, match="axis must be x, y or xy"):
        repeat(petal, 2, mode="mirror", axis="z")
    with pytest.raises(ValueError, match="n must be at least 2"):
        repeat(petal, 1)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_kit_ops.py -q -k repeat`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write `repeat`**

```python
def repeat(shape: Shape, n: int, mode: str = "radial", cx: float = 0, cy: float = 0, cols: int | None = None,
           step: float | None = None, axis: str | None = None) -> Shape:
    """`n` copies of `shape` as one union: `radial` at equal angles about (cx, cy); `grid` in `cols` columns at `step`
    spacing, rows filling from the bottom left, the whole grid centred on (cx, cy); `mirror` the shape with its
    reflections across `axis` ("x": the vertical line x = cx, "y": the horizontal line y = cy, "xy": both; n is then 2
    or 4). Evidence rule 1 favours one repeated element; this is one call."""
    if n < 2:
        raise ValueError("n must be at least 2")
    if mode == "radial":
        return union(*(rotate(shape, 360 * i / n, cx, cy) for i in range(n)))
    if mode == "grid":
        if not cols or step is None:
            raise ValueError("grid needs cols and step")
        rows = -(-n // cols)
        copies = [translate(shape, (i % cols) * step, (i // cols) * step) for i in range(n)]
        laid = union(*copies)
        b = laid.bounds
        return translate(laid, cx - b.cx, cy - b.cy)
    if mode == "mirror":
        if axis not in ("x", "y", "xy"):
            raise ValueError(f"axis must be x, y or xy, got {axis!r}")
        copies = [shape]
        if "x" in axis:
            copies += [mirror_x(c, cx) for c in copies]
        if "y" in axis:
            copies += [mirror_y(c, cy) for c in copies]
        return union(*copies)
    raise ValueError(f"mode must be radial, grid or mirror, got {mode!r}")
```

Export `repeat`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_kit_ops.py -q`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/kit tests/test_kit_ops.py
git commit -m "feat: repeat lays out radial, grid and mirrored copies in one call"
```

---

### Task 6: `Meta.snap` and module-wide free snapping

**Files:**
- Modify: `src/logomaker/kit/primitives.py`, `src/logomaker/kit/concept.py`
- Test: `tests/test_concept.py` (extend), `tests/test_kit_primitives.py` (extend)

**Interfaces:**
- Produces: `primitives.FREE_ALL` (a `ContextVar[bool]`); `primitives.free_snapping(enabled: bool = True)` (a context manager); `Meta.snap: str = "grid"` (`"grid"` or `"free"`); `build_tiers` builds every tier under `free_snapping(meta.snap == "free")`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_kit_primitives.py`:

```python
from logomaker.kit.primitives import free_snapping


def test_free_snapping_context_makes_every_primitive_free():
    assert circle(0.3, 0, 100.12).bounds.x1 == 100.25
    with free_snapping():
        free_disc = circle(0.3, 0, 100.12)
        assert math.isclose(free_disc.bounds.x1, 100.42, abs_tol=0.01) and free_disc.free_segments == 4
        assert circle(0, 0, 100, free=True).free_segments == 4  # explicit free=True is not counted twice
        assert regular_polygon(0, 0, 100, 5, rotation=7).free_segments == 5
    assert circle(0.3, 0, 100.12).bounds.x1 == 100.25  # restored
```

Append to `tests/test_concept.py`:

```python
def test_meta_snap_free_builds_every_tier_free(project_root):
    folder = install_concept(project_root, "good", name="01-free")
    source = (folder / "concept.py").read_text()
    (folder / "concept.py").write_text(source.replace('motifs=["ring"])', 'motifs=["ring"], snap="free")'))
    module = conceptlib.load_concept(folder)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
    expected = ring(0, 0, 400, 90, start=30, end=330, free=True).free_segments  # the fixture's sector, every segment free
    assert expected > 0 and outputs["full-symbol"].symbol.free_segments == expected
    grid = conceptlib.load_concept(install_concept(project_root, "good", name="02-grid"))
    assert conceptlib.build_outputs(conceptlib.build_tiers(grid))["full-symbol"].symbol.free_segments == 0


def test_meta_rejects_an_unknown_snap():
    with pytest.raises(ValueError, match="Meta.snap must be 'grid' or 'free'"):
        conceptlib.Meta(slug="x", idea="x", logo_type="abstract", snap="loose")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_kit_primitives.py tests/test_concept.py -q -k "snap"`
Expected: FAIL with `ImportError: cannot import name 'free_snapping'`.

- [ ] **Step 3: Add the context variable**

In `src/logomaker/kit/primitives.py`, after the constants:

```python
import contextvars
from collections.abc import Iterator
from contextlib import contextmanager

FREE_ALL: contextvars.ContextVar[bool] = contextvars.ContextVar("logomaker_free_all", default=False)


@contextmanager
def free_snapping(enabled: bool = True) -> Iterator[None]:
    """Within the block every primitive behaves as if free=True: what Meta(snap="free") sets for a whole module."""
    token = FREE_ALL.set(enabled)
    try:
        yield
    finally:
        FREE_ALL.reset(token)


def _free(free: bool) -> bool:
    return free or FREE_ALL.get()
```

Then change `_v`, `_a` and `_finish` to call `_free(free)` in place of `free`, and in `regular_polygon` replace `if free` with `if _free(free)`. `_finish` sets `free_segments = segment_count() if _free(free) else 0`, so an explicit `free=True` inside the context is counted once.

- [ ] **Step 4: Add `Meta.snap` and wrap the build**

In `src/logomaker/kit/concept.py`, add `snap: str = "grid"` to `Meta` and in `__post_init__`:

```python
        if self.snap not in ("grid", "free"):
            raise ValueError(f"Meta.snap must be 'grid' or 'free', got {self.snap!r}")
```

In `build_tiers`, import `free_snapping` from `.primitives` and wrap the call:

```python
        with _concept_code(f"{concept.path} build() failed for tier {tier!r}"), free_snapping(concept.meta.snap == "free"):
            mark = concept.build(p)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_kit_primitives.py tests/test_concept.py tests/test_audit.py -q`
Expected: all passed. The audit already reports `free_segments` as info (`audit._geometry_findings`), so no audit change is needed; confirm by reading that function.

- [ ] **Step 6: Commit**

```bash
git add src/logomaker/kit tests
git commit -m "feat: Meta.snap='free' makes a whole module free of the grid"
```

---

### Task 7: Glyph characters, `wordmark_gaps` and the `spacing_rhythm` audit

**Files:**
- Modify: `src/logomaker/kit/text.py`, `src/logomaker/kit/__init__.py`, `src/logomaker/audit.py`
- Test: `tests/test_kit_text.py`, `tests/test_audit.py` (extend)

**Interfaces:**
- Produces: `TextShape.glyph_chars: list[str]` (the characters each drawn glyph covers, in `glyph_bounds` order); `text.wordmark_gaps(word: TextShape) -> list[dict]` with `{"pair": "Ke", "gap": 12.5}` per adjacent glyph pair (gap in units; negative when boxes overlap); `audit.RHYTHM_WIDE = 1.8`, `audit.RHYTHM_TIGHT = 0.5`; an audit finding `spacing_rhythm` (info with the gaps, warn naming the pairs outside the band).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_kit_text.py`:

```python
from logomaker.kit.text import text, wordmark_gaps


def test_glyph_chars_follow_the_drawn_glyphs_through_ligatures_and_transforms():
    word = text("Keystone", "Fira Code", weight=600, cap_height=200)
    assert word.glyph_chars == list("Keystone")
    lig = text("fi", "Fira Code", weight=400, cap_height=200, features=("liga",))
    assert "".join(lig.glyph_chars) == "fi" and len(lig.glyph_chars) == len(lig.glyph_bounds)
    from logomaker.kit.ops import rotate
    assert rotate(word, 30).glyph_chars == list("Keystone")


def test_wordmark_gaps_name_each_pair():
    word = text("Keystone", "Fira Code", weight=600, cap_height=200)
    gaps = wordmark_gaps(word)
    assert [g["pair"] for g in gaps] == ["Ke", "ey", "ys", "st", "to", "on", "ne"]
    assert all(isinstance(g["gap"], float) for g in gaps)
    assert wordmark_gaps(text("K", "Fira Code", cap_height=200)) == []
```

Append to `tests/test_audit.py` (next to the other geometry tests; they build a Mark and call the finding function directly):

```python
from logomaker.audit import _spacing_rhythm
from logomaker.kit.mark import Mark
from logomaker.kit.text import text


def test_spacing_rhythm_warns_on_a_pair_far_from_the_median():
    # Fira Code is monospaced, so ink gaps follow glyph widths: "noon" is even, "Keystone" with a forced "ys" gap is not.
    even = Mark(wordmark=text("noon", "Fira Code", weight=600, cap_height=200), lockup="wordmark")
    findings = _spacing_rhythm({"full-wordmark": even})
    assert [f.severity for f in findings] == ["info"] and "no" in findings[0].message
    gappy = Mark(wordmark=text("Keystone", "Fira Code", weight=600, cap_height=200, kern={"ys": 400}), lockup="wordmark")
    findings = _spacing_rhythm({"full-wordmark": gappy})
    assert [f.severity for f in findings] == ["warn"] and "ys wide" in findings[0].message
    assert _spacing_rhythm({}) == []
```

Fira Code's ink gaps vary with glyph width (an `l` leaves air on both sides), so fixtures and worked examples set in it may now warn `spacing_rhythm`. When the fast suite shows that, add the expected warning to the test that lists that fixture's warnings (and to `EXAMPLE_WARNINGS` for a worked example) after reading the gaps; never loosen `RHYTHM_WIDE` or `RHYTHM_TIGHT` to quiet a monospaced fixture, since the thresholds are for the proportional families real wordmarks use.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_kit_text.py tests/test_audit.py -q -k "glyph_chars or gaps or rhythm"`
Expected: FAIL with `ImportError: cannot import name 'wordmark_gaps'`.

- [ ] **Step 3: Carry the characters on `TextShape`**

In `src/logomaker/kit/text.py`: add `"glyph_chars"` to `TextShape.__slots__`, a keyword `glyph_chars: list[str] | None = None` to `__init__` (stored as `list(glyph_chars or [])`), pass `glyph_chars=list(self.glyph_chars)` in `_with_path` and `transformed`. In `text()`, keep a `chars: list[str]` beside `bounds`: inside the loop, when the pen's path is not empty, append the cluster's characters:

```python
        if not pen.path.isEmpty():
            ...
            nxt = infos[i + 1].cluster if i + 1 < len(infos) else len(string)
            chars.append(string[info.cluster:nxt] if nxt > info.cluster else string[info.cluster])
```

and pass `glyph_chars=chars` to the returned `TextShape`. Then add:

```python
def wordmark_gaps(word: TextShape) -> list[dict]:
    """The gap between each adjacent pair of drawn glyphs, in units, named by the characters either side ("Ke"): what
    the wordmark sheet draws and the spacing_rhythm audit reads. Negative when kerned boxes overlap."""
    gaps = []
    for i in range(len(word.glyph_bounds) - 1):
        a, b = word.glyph_bounds[i], word.glyph_bounds[i + 1]
        left = word.glyph_chars[i][-1] if i < len(word.glyph_chars) else str(i + 1)
        right = word.glyph_chars[i + 1][0] if i + 1 < len(word.glyph_chars) else str(i + 2)
        gaps.append({"pair": left + right, "gap": round(float(b.x0 - a.x1), 2)})
    return gaps
```

Export `wordmark_gaps` from `kit/__init__.py`.

- [ ] **Step 4: Add the audit line**

In `src/logomaker/audit.py`:

```python
RHYTHM_WIDE, RHYTHM_TIGHT = 1.8, 0.5  # a gap this many times the median, or this fraction of it, breaks the rhythm


def _spacing_rhythm(outputs: dict) -> list[Finding]:
    """The wordmark's glyph gaps (kit.text.wordmark_gaps) against their median: info listing them, or a warning naming
    each pair wider than RHYTHM_WIDE times the median or tighter than RHYTHM_TIGHT of it."""
    from statistics import median

    from .kit.text import TextShape, wordmark_gaps

    mark = outputs.get("full-wordmark")
    word = mark.wordmark if mark is not None else None
    if not isinstance(word, TextShape):
        return []
    gaps = wordmark_gaps(word)
    if len(gaps) < 2:
        return []
    mid = median(g["gap"] for g in gaps)
    listed = ", ".join(f"{g['pair']} {g['gap']:g}" for g in gaps)
    if mid <= 0:
        return [Finding(check="spacing_rhythm", severity="info", message=f"wordmark gaps (median {mid:g}): {listed}",
                        data={"gaps": gaps, "median": mid})]
    wide = [g for g in gaps if g["gap"] > RHYTHM_WIDE * mid]
    tight = [g for g in gaps if g["gap"] < RHYTHM_TIGHT * mid]
    if wide or tight:
        parts = [f"{g['pair']} wide ({g['gap']:g})" for g in wide] + [f"{g['pair']} tight ({g['gap']:g})" for g in tight]
        return [Finding(check="spacing_rhythm", severity="warn",
                        message=f"wordmark spacing: {', '.join(parts)} against a median gap of {mid:g}; kern the pair",
                        data={"gaps": gaps, "median": mid, "wide": wide, "tight": tight})]
    return [Finding(check="spacing_rhythm", severity="info", message=f"wordmark gaps even (median {mid:g}): {listed}",
                    data={"gaps": gaps, "median": mid})]
```

Call it in `audit_concept` right after `findings += _text_legibility(outputs, geometries, state)`: `findings += _spacing_rhythm(outputs)`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_kit_text.py tests/test_audit.py tests/test_knowledge.py -q`
Expected: all passed. If a kit-api.md worked example now warns `spacing_rhythm` (Fira Code is monospaced, so it should not), add the warning to `EXAMPLE_WARNINGS` only after reading the gaps and agreeing the pair really is uneven.

- [ ] **Step 6: Commit**

```bash
git add src/logomaker tests
git commit -m "feat: glyph characters, wordmark_gaps and the spacing_rhythm audit"
```

---

### Task 8: The wordmark sheet and `sheet wordmark`

**Files:**
- Modify: `src/logomaker/sheets.py`, `src/logomaker/cli.py`
- Create: `templates/sheets/wordmark.html`
- Test: `tests/test_sheets.py` (extend)

**Interfaces:**
- Consumes: `text.wordmark_gaps`, `conceptlib.concept_folder`, `registry.load_state`, `render.fit_box`, `sheets.next_round`, `sheets._write_sheet`, `sheets.open_file`.
- Produces: `sheets.WORDMARK_W = 1400`; `sheets.wordmark_sheet(paths, slug, concept_name="final", renderer=None, open_after=True, round_n=None) -> dict` with `sheet_html`, `sheet_png`, `round`, `gaps`, `median`, `warnings`; files `sheets/wordmark-N.{html,png}`. CLI: `sheet wordmark <slug> [--concept <NN-slug>] [--round N] [--no-open]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sheets.py`:

```python
from logomaker import sheets
from logomaker.output import CliError
from logomaker.paths import project
from tests.conftest import StubChrome, install_concept, make_final_brand


def test_wordmark_sheet_draws_three_sizes_and_the_gap_bars(project_root):
    make_final_brand(project_root)
    info = sheets.wordmark_sheet(project(), "keystone", renderer=StubChrome(), open_after=False)
    assert info["round"] == 1 and [g["pair"] for g in info["gaps"]] == ["Go", "oo", "od"]
    html = (project_root / "brands" / "keystone" / "sheets" / "wordmark-1.html").read_text()
    assert "32 px header" in html and "120 px" in html and "400 px" in html
    assert html.count('<div class="bar') == 3 and "median" in html  # a flagged bar reads class="bar wide"


def test_wordmark_sheet_takes_a_concept_folder(project_root):
    install_concept(project_root, "good", name="01-good")
    info = sheets.wordmark_sheet(project(), "keystone", "01-good", renderer=StubChrome(), open_after=False)
    assert [g["pair"] for g in info["gaps"]] == ["Go", "oo", "od"]
    assert all(w.endswith("against the median gap") for w in info["warnings"])


def test_wordmark_sheet_refuses_a_concept_without_a_text_wordmark_before_chrome(project_root, no_chrome):
    folder = install_concept(project_root, "good", name="01-good")
    source = (folder / "concept.py").read_text()
    (folder / "concept.py").write_text(source.replace('word = text("Good", family="Fira Code", weight=600, cap_height=180)',
                                                      "word = rect(0, 0, 400, 100)"))
    with pytest.raises(CliError, match="wordmark metrics unknown"):
        sheets.wordmark_sheet(project(), "keystone", "01-good", open_after=False)
    (folder / "concept.py").write_text(source.replace('return Mark(symbol=symbol, wordmark=word, lockup="horizontal", gap=p.gap)',
                                                      "return Mark(symbol=symbol)"))
    with pytest.raises(CliError, match="no wordmark set with text"):
        sheets.wordmark_sheet(project(), "keystone", "01-good", open_after=False)
    assert not list((project_root / "brands" / "keystone" / "sheets").glob("wordmark-*"))
```

The `good` fixture (`tests/fixtures/concepts/good/concept.py`) has exactly those two lines, so the replacements apply.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_sheets.py -q -k wordmark`
Expected: FAIL with `AttributeError: module 'logomaker.sheets' has no attribute 'wordmark_sheet'`.

- [ ] **Step 3: Write the template**

`templates/sheets/wordmark.html`:

```html
<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body{margin:0;width:{{ width }}px;font:14px/1.4 -apple-system,Helvetica,Arial,sans-serif;background:#f3f3f3;color:#222;padding:24px;box-sizing:border-box}
  h1{font-size:22px;margin:0 0 16px} h2{font-size:16px;margin:24px 0 8px;color:#444}
  .row{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end}
  .panel{background:#fff;border:1px solid #ddd;display:flex;flex-direction:column;align-items:center;margin:0;padding:12px;box-sizing:border-box}
  .panel figcaption{align-self:flex-start;margin-top:6px;font-size:11px;color:#888;white-space:nowrap}
  .bars{display:flex;align-items:flex-end;gap:6px;height:140px;background:#fff;border:1px solid #ddd;padding:12px}
  .bar{width:48px;background:#e8572a;position:relative} .bar.wide{background:#9a6a00} .bar.tight{background:#b00020}
  .bar span{position:absolute;top:-18px;left:0;right:0;text-align:center;font-size:11px;color:#555}
  .bar b{position:absolute;bottom:-18px;left:0;right:0;text-align:center;font-size:12px}
  .note{color:#777;font-size:12px;margin-top:24px}
</style></head>
<body>
<h1>{{ brand }} &mdash; wordmark round {{ round_n }} ({{ font }})</h1>
<h2>Sizes</h2>
<div class="row">
  <figure class="panel" style="width:300px;height:80px">{{ header|safe }}<figcaption>32 px header</figcaption></figure>
  <figure class="panel" style="width:200px;height:100px">{{ minimum|safe }}<figcaption>{{ min_px }} px (the minimum width)</figcaption></figure>
  <figure class="panel" style="width:460px;height:200px">{{ large|safe }}<figcaption>400 px</figcaption></figure>
</div>
<h2>Gaps between glyphs (units; median {{ median }})</h2>
<div class="bars">{% for g in gaps %}<div class="bar{% if g.kind %} {{ g.kind }}{% endif %}" style="height:{{ g.height }}px"><span>{{ g.gap }}</span><b>{{ g.pair }}</b></div>{% endfor %}</div>
<div class="note">A bar is the space between two glyph boxes. Amber is wider than {{ wide }} times the median, red tighter than {{ tight }} of it: kern the pair with text(..., kern={"{{ gaps[0].pair if gaps else 'AV' }}": -20}) and re-run.</div>
</body></html>
```

- [ ] **Step 4: Write `wordmark_sheet`**

Add to `src/logomaker/sheets.py`:

```python
WORDMARK_W = 1400


def wordmark_sheet(paths: ProjectPaths, slug: str, concept_name: str = "final", renderer: Renderer | None = None,
                   open_after: bool = True, round_n: int | None = None) -> dict:
    """Write sheets/wordmark-N.{html,png}: the wordmark at the 32 px header size, at the brand's minimum horizontal width
    and at 400 px, then one bar per glyph gap (kit.text.wordmark_gaps) against the median, coloured where it breaks the
    rhythm as the spacing_rhythm audit reads it (spec 2026-10-08 §5.6). Needs a wordmark set with text(); a concept
    without one, or whose wordmark lost its metrics, is a CliError before Chrome starts."""
    from .audit import RHYTHM_TIGHT, RHYTHM_WIDE
    from .kit.text import TextShape, wordmark_gaps
    from statistics import median

    state = registry.load_state(paths, slug)
    folder = conceptlib.concept_folder(paths, slug, concept_name)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(folder)))
    if "full-wordmark" not in outputs:
        raise CliError(f"{concept_name} has no wordmark set with text(); the wordmark sheet needs one")
    word = outputs["full-wordmark"].wordmark
    if not isinstance(word, TextShape):
        raise CliError(f"{concept_name}: wordmark metrics unknown (not a TextShape); build it with text() and keep it the first operand")
    svg = outputs["full-wordmark"].to_svg("black")
    gaps = wordmark_gaps(word)
    mid = median(g["gap"] for g in gaps) if gaps else 0.0
    top = max((abs(g["gap"]) for g in gaps), default=1.0) or 1.0
    bars = []
    for g in gaps:
        kind = ""
        if mid > 0 and g["gap"] > RHYTHM_WIDE * mid:
            kind = "wide"
        elif mid > 0 and g["gap"] < RHYTHM_TIGHT * mid:
            kind = "tight"
        bars.append({**g, "kind": kind, "height": max(2, round(100 * abs(g["gap"]) / top))})
    brand = paths.brand(slug)
    round_n = round_n or next_round(brand, "sheets/wordmark-*.html")
    html = jinja(paths).get_template("sheets/wordmark.html").render(
        brand=state.name, round_n=round_n, font=word.font, width=WORDMARK_W, header=fit_box(svg, 260, 32),
        minimum=fit_box(svg, state.min_sizes.horizontal_px, 60), min_px=state.min_sizes.horizontal_px, large=fit_box(svg, 400, 160),
        gaps=bars, median=number(mid), wide=RHYTHM_WIDE, tight=RHYTHM_TIGHT)
    html_path, png_path = _write_sheet(renderer, html, brand / "sheets", f"wordmark-{round_n}", WORDMARK_W)
    warnings: list[str] = [f"{b['pair']} is {b['kind']} against the median gap" for b in bars if b["kind"]]
    open_file(html_path, open_after, warnings)
    return {"sheet_html": str(html_path), "sheet_png": str(png_path), "round": round_n, "gaps": gaps, "median": mid, "warnings": warnings}
```

- [ ] **Step 5: Add the CLI command**

In `src/logomaker/cli.py`, after `sheet_refine`:

```python
@sheet_group.command("wordmark")
@click.argument("slug")
@click.option("--concept", "concept", default="final", help="Concept folder name, e.g. 03-keystone (default: final).")
@ROUND_OPTION
@click.option("--no-open", is_flag=True, help="Write the sheet without opening it in the browser.")
@command
def sheet_wordmark(slug: str, concept: str, round_n: int | None, no_open: bool) -> None:
    """Render the wordmark sheet: the name at three sizes and the gap between every pair of glyphs. It goes into
    sheets/wordmark-N.{html,png} and opens in the browser."""
    from . import sheets as sheetlib

    info = sheetlib.wordmark_sheet(project(), slug, concept, open_after=not no_open, round_n=round_n)
    emit(info, warnings=info.pop("warnings"))
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_sheets.py tests/test_knowledge.py -q`
Expected: all passed.

- [ ] **Step 7: Commit**

```bash
git add src/logomaker/sheets.py src/logomaker/cli.py templates/sheets/wordmark.html tests/test_sheets.py
git commit -m "feat: sheet wordmark shows the name at three sizes with its glyph gaps"
```

---

### Task 9: Documentation: kit-api.md, craft.md, SKILL.md

**Files:**
- Modify: `.claude/skills/logo/reference/kit-api.md`, `.claude/skills/logo/reference/craft.md`, `.claude/skills/logo/SKILL.md`, `tests/test_knowledge.py`
- Test: `tests/test_knowledge.py`, `tests/test_skill_docs.py`

**Interfaces:**
- Produces: kit-api.md rows for `brush`, `spline`, `catmull_rom`, `Node`, `nodes`, `move_node`, `delete_node`, `cut`, `repeat`, `wordmark_gaps`, `Meta.snap`, `TextShape.glyph_chars`; two new worked examples (5 and 6); four craft.md recipes; the wordmark rules rewritten; SKILL.md's wordmark step.

- [ ] **Step 1: Extend the knowledge tests**

In `tests/test_knowledge.py`: `audit_worked_examples` asserts `len(blocks) == 4` and `types == ["lettermark", "pictorial", "abstract", "wordmark"]`; change them to `6` and `[..., "pictorial", "lettermark"]`, and extend `EXAMPLE_WARNINGS` with two entries, `[]` for each new example to start. Run the test; it fails because the examples do not exist yet.

- [ ] **Step 2: Write the kit-api.md additions**

In the Primitives table add:

```markdown
| `brush(points, widths, cap="round")` | a stroke whose width varies: `points` a cubic chain as `bezier` takes, `widths` one per on-curve node (or one number), interpolated by arc length; caps `round`, `square`, `butt`; the sides are fitted back to cubics, so a five-node brush keeps about twenty anchors |
| `spline(points, tension=0.5, closed=True, width=None)` | a Catmull-Rom curve through the points (`catmull_rom(points, tension, closed)` gives the chain); tension 0 is the loosest curve, 1 the polygon; filled, or stroked with `width` |
```

In Operations add a "Node editing" paragraph:

```markdown
- Node editing: `nodes(shape)` lists the on-curve nodes as `Node(index, x, y, subpath, smooth)` in path order; `move_node(shape, index, dx, dy)` moves one with the two handles attached to it; `delete_node(shape, index)` joins its neighbours with one segment (a line when both were lines, else a cubic keeping the outer handles; an open contour's endpoints cannot go); `cut(shape, x1, y1, x2, y2)` returns `(left, right)` along the line, left when travelling from the first point to the second. All keep a `TextShape`'s metrics, so a glyph can be edited under craft.md's wordmark rules.
- `repeat(shape, n, mode="radial", cx=0, cy=0, cols=None, step=None, axis=None)`: `n` copies as one union: `radial` about (cx, cy); `grid` in `cols` columns at `step`, centred on (cx, cy); `mirror` across `axis` `"x"`, `"y"` or `"xy"`.
```

In the Concept module contract: `Meta(..., snap="grid")`: `"free"` makes every primitive in the module behave as `free=True` (the audit lists them as `free_segments`, info only). In Text: `TextShape.glyph_chars`, the characters each drawn glyph covers, and `wordmark_gaps(word)`, the gap per adjacent pair as `{"pair": "Ke", "gap": units}`, what `sheet wordmark` draws and the `spacing_rhythm` audit reads.

Worked example 5 (pictorial, `snap="free"`, a brushed and splined leaf) and 6 (lettermark, a glyph cut and a node moved), each under 40 lines, each building `full`, `small` and `favicon`, starting from:

```python
from logomaker.kit import *

META = Meta(slug="verdant-leaf", idea="One brushed stroke swells into a leaf: Verdant grows from a single line",
            logo_type="pictorial", motifs=["leaf", "stroke"], snap="free")
PARAMS = Params(thin=40, thick=170, stem=120)
TIERS = {
    "full": {},
    "small": {"thin": 90, "thick": 220, "wordmark": False},
    "favicon": {"thin": 140, "thick": 260, "stem": 60, "wordmark": False},
}


def build(p):
    spine = [(-300, -320), (-200, -100), (-60, 180), (120, 360)]  # one cubic, two nodes
    leaf = brush(spine, [p.thin, p.thick], cap="round")
    stem = brush([(-300, -320), (-330, -380), (-350, -420), (-360, -320 - p.stem)], [p.thin, p.thin * 0.6], cap="round")
    symbol = center(union(leaf, stem))
    word = text("Verdant", "Fira Code", weight=600, cap_height=180)
    return Mark(symbol=symbol, wordmark=word, lockup="horizontal")
```

```python
from logomaker.kit import *

META = Meta(slug="halden-cut", idea="Halden's H cut once across the bar and the two halves pulled apart: a bridge with a gap",
            logo_type="lettermark", motifs=["letter H", "gap"])
PARAMS = Params(weight=700, gap=40, lift=30)
TIERS = {
    "full": {},
    "small": {"gap": 60, "wordmark": False},
    "favicon": {"gap": 90, "lift": 0, "wordmark": False},
}


def build(p):
    h = glyph("H", "Fira Code", weight=p.weight, cap_height=700)
    y = h.bounds.cy
    top, bottom = cut(h, -1000, y, 1000, y)
    symbol = center(union(translate(top, 0, p.gap / 2 + p.lift), translate(bottom, 0, -p.gap / 2)))
    word = text("Halden", "Fira Code", weight=600, cap_height=180)
    return Mark(symbol=symbol, wordmark=word, lockup="horizontal")
```

Run `uv run pytest tests/test_knowledge.py -q -k worked` after writing each; read the audit failures and adjust the parameters (stroke floors at 16 px, no tiny parts, the gap closing at 32 px) until both pass, recording any justified warning in `EXAMPLE_WARNINGS`. The `tests/test_concept.py` audit floors are `MIN_FEATURE`: 1.0 px at 16 px for `favicon`, 1.5 px at 32 px for `small`.

- [ ] **Step 3: Write the craft.md recipes and the wordmark rules**

Under "Kit recipes" add recipes 7 to 10, each a Python block whose last top-level assignment is the shape it makes (the test reads `last_binding`):

```python
# 7. A brushed stroke with a swelling terminal: the width runs 30 at the start, 110 at the crest, 50 at the tip.
sweep = brush([(-400, -200), (-250, 250), (50, 250), (150, 0), (250, -250), (350, -250), (400, 0)], [30, 110, 50], cap="round")
```

```python
# 8. A spline leaf: a closed Catmull-Rom curve through four points, tightened at the tip by moving one node.
leaf = spline([(0, 360), (220, 60), (0, -360), (-220, 60)], tension=0.3)
tip = next(n for n in nodes(leaf) if n.y < -300)
leaf_tipped = move_node(leaf, tip.index, 0, -60)
```

```python
# 9. A node-cut glyph: the counter of a D re-cut by a straight line through the letter, the lower part dropped 40 units.
d = glyph("D", "Fira Code", weight=700, cap_height=600)
upper, lower = cut(d, -1000, d.bounds.cy, 1000, d.bounds.cy)
split_d = union(upper, translate(lower, 0, -40))
```

```python
# 10. A radial repeat: one petal six times about the origin, the centre knocked out.
petal = brush([(0, 60), (-40, 160), (-40, 260), (0, 340)], [20, 70], cap="round")
flower = subtract(repeat(petal, 6), circle(0, 0, 50))
```

Rewrite wordmark rules 2 and 3:

```markdown
2. At most two owned quirks, each parametric and applied to the outlines with the kit's node editing (`cut`, `move_node`, `delete_node`) or a boolean: a ligature, a cut, a notch, a terminal. A third quirk is a new typeface, not a wordmark [spec 2026-10-08 §5.3] [04 §1.2].
3. Letter identity survives every quirk: the Kia test on the 32 px header, and the critic's `legible` score, decide it; "KN" for Kia drew about 30,000 monthly searches [01 §2] [05 §2].
```

Add a wordmark-stage paragraph after rule 9: run `uv run logomaker sheet wordmark <slug>` after setting the family, read `sheets/wordmark-N.png`, kern the pairs the bars flag with `kern={"Ke": -20}`, re-run; the `spacing_rhythm` audit line warns on a pair wider than 1.8 times the median gap or tighter than half of it.

- [ ] **Step 4: Update SKILL.md**

In the Refinement phase, replace "the wordmark set in the chosen family with at most one parametric quirk" with "the wordmark set in the chosen family with at most two parametric quirks, then `uv run logomaker sheet wordmark <slug> --no-open`, read `sheets/wordmark-N.png`, kern the flagged pairs and re-run". In "Writing concept modules" add: "A module whose forms are organic sets `snap="free"` in `META` instead of passing `free=True` to every primitive."

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_knowledge.py tests/test_skill_docs.py -q && uv run pytest -m "not render and not live" -q && uv run ruff check src tests`
Expected: all passed, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/logo tests/test_knowledge.py
git commit -m "docs: kit-api, craft recipes and the wordmark stage for the new vocabulary"
```

---

## Plan 3 is done when

- Fast and render suites pass; ruff is clean.
- `kit.__all__` has every new name and kit-api.md documents each; six worked examples build and pass their audits.
- `uv run logomaker sheet wordmark keystone` on a copy of the example renders through Chrome.
- The `kit` evaluation cycle (Plan 2, Task 4's procedure with `--cycle kit`) is run and its three rows added to `docs/evals/README.md`.
