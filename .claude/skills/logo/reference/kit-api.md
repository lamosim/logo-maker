# Kit API

Read this when: writing or revising any concept module (phase 4) or `final/concept.py` (phase 5), and when an audit finding points at the geometry.

Written from the code [code]; where spec §6 differs, the code wins [spec §6]. Canvas: 1000 units, origin at the centre, y up (flipped on output). Primitive coordinates and sizes snap to 0.25 units and angles to 15 degrees unless `free=True`, so the spec's `ring(start=200, end=340)` draws 195 to 345.

## Concept module contract

`brands/<slug>/concepts/NN-slug/concept.py` (two digits, a hyphen, a slug) or `brands/<slug>/final/concept.py`:

- `from logomaker.kit import *` first.
- `META`, a `Meta(slug, idea, logo_type, motifs=[], territory=None, allow_complex=False, complex_reason="")`: `idea`, one sentence without "represents"; `motifs`, plain nouns the cliché check reads.
- `PARAMS`, a `Params(stroke=90, gap=None, ...)`: named values read as `p.stroke`.
- `TIERS`: keys `full` (required), `compact`, `small`, `favicon`; each value overrides `PARAMS` for that tier; `"wordmark": False` drops the wordmark (a symbol is then required).
- `def build(p): ... return Mark(...)`, called once per tier; deterministic, since the audit builds twice and fails on any difference.
- `params.json` beside the module overrides `PARAMS` (only names `PARAMS` defines); refinement tunes `final/` through it. `TIERS` apply after it: a value a tier sets beats params.json, which changes only `full` and tiers that leave the name alone. `tokens.json` colours the `color` and `reverse` variants and feeds the colour checks (color.md).
- The CLI writes `build/` (`<output>-<variant>.svg`, `geometry.json`, `build.json`), `audit.json` and `renders/round-N/critique.{html,png}`; never edit them. An exception exits 2 with its traceback, an uncached font exits 3 with its fetch command, and `print()` goes to stderr.

## Primitives

Every primitive returns a `Shape` and takes `free=False`.

| Call | Draws |
|---|---|
| `circle(cx, cy, r)` | a disc |
| `ring(cx, cy, r, width, start=None, end=None)` | an annulus, `r` the outer radius, `width` under `r`; with `start` and `end` (degrees, counter-clockwise from east) a sector with butt ends |
| `arc(cx, cy, r, start, end, width, cap="butt")` | a stroked arc on centreline radius `r`; caps `butt`, `round`, `square` |
| `wedge(cx, cy, r, start, end)` | a pie slice |
| `rect(x, y, w, h)`, `rect_centered(cx, cy, w, h)` | a rectangle from its lower-left corner, or its centre |
| `rrect(x, y, w, h, radius)`, `rrect_centered(cx, cy, w, h, radius)` | a rounded rectangle |
| `polygon(points)` | a closed polygon of three or more points |
| `regular_polygon(cx, cy, r, n, rotation=0)` | exact vertices (only centre, radius and rotation snap) |
| `line(x1, y1, x2, y2, width, cap="butt")` | a stroked segment |
| `polyline(points, width, cap="butt", join="miter")` | a stroked open path; joins `miter`, `round`, `bevel` |
| `bezier(points, width=None, closed=False)` | a cubic chain p0, c1, c2, p1, ... (1 + 3k points): filled when `width` is None, else stroked with round joins |

`snap(value, step=0.25)` and `snap_angle(angle, step=15)` do the snapping.

## Operations

Each returns a new shape of its first operand's kind, so a `TextShape` keeps its metrics [code].

- Booleans: `union(*shapes)`, `subtract(a, b)`, `intersect(a, b)`, `xor(a, b)`.
- `stroke(shape, width, cap="butt", join="miter", miter_limit=4)` turns an outline or open path into a filled band; `offset(shape, distance)` grows it (round corners) or, negative, shrinks it.
- Transforms, which do not snap: `translate(shape, dx, dy)`, `rotate(shape, degrees, cx=0, cy=0)`, `scale(shape, sx, sy=None, cx=0, cy=0)`, `mirror_x(shape, axis=0)` (across the vertical line x = axis), `mirror_y(shape, axis=0)`.
- Placing: `align(shape, to, edge)` to a shape or `Box`, edge `left`, `right`, `top`, `bottom`, `center` (x) or `middle` (y); `center(shape, cx=0, cy=0, optical=False)` by box or, optical, by area centroid; `fit(shape, w, h, cx=0, cy=0)` scales to fit and centres.
- Optical helpers (craft.md): `overshoot(shape, amount=0.015)`; `compensate_stroke(base_width, horizontal_factor=0.92, curve_factor=1.05)` returns `StrokeWidths(vertical, horizontal, curve)`; `optical_center(shape)` returns the area centroid.
- Queries on a `Shape`: `bounds` (a `Box` with `x0`, `y0`, `x1`, `y1`, `w`, `h`, `cx`, `cy`; `Box.union(boxes)`), `area`, `centroid`, `is_empty`, `anchor_count()`, `segment_count()`, `subpaths()` (each contour as its own filled shape: a glyph's counter is one), `straight_segments()`, `free_segments`.
- Plumbing: `normalize_winding(path)` re-winds a raw `skia.Path` (every op already does); `fmt(value)` formats SVG numbers.

### Limits and audit interactions

- `paper` is not a part role: knock shapes out with `subtract()` [code].
- `free=True` counts every segment the primitive draws, curves included (a free circle counts 4); the audit reports them as `free_segments`.
- A `regular_polygon` with n of 5, 7, 10, 11, 13, 14 or 15 (and most n over 16) warns `near_miss_angles` at every snapped rotation; 3, 4, 6, 8, 9, 12 and 16 never do. Glyph outlines used as a symbol can warn too (Fira Code's t at weights 500 to 700): that is the type designer's angle, so justify it.
- Rotating by anything but a multiple of 15 degrees can create near-miss edges.
- Inward `offset` limits: holes under 1 unit² are treated as slivers (a sub-unit hole can come back filled); marks with many holes (over about 50) inset slowly; a hairline speck thinner than max(1 unit, 2 percent of the distance) can survive an inset that should be empty; a pathops RuntimeError inside the band's stroke escapes the retry (change the distance slightly); a self-intersecting cubic can inset to nothing.
- Keep the `TextShape` the first operand of every op (`union(word, bar)`, not `union(bar, word)`); otherwise the metrics are lost and `text_legibility` warns "metrics unknown".
- A negative `scale` reverses contour direction; use `mirror_x` and `mirror_y`, which re-wind, before joining mirrored parts.

## Text

- `text(string, family, weight=400, cap_height=200, tracking=0, kern=None, features=("kern", "liga"), italic=False)` returns a `TextShape`: shaped by HarfBuzz, outlined by fontTools, baseline at y = 0, starting at x = 0, capitals `cap_height` tall.
- `glyph(char, family, weight=400, cap_height=200, italic=False)` is one letter, with no OpenType features.
- `TextShape` adds `advance`, `cap_height`, `x_height`, `glyph_bounds` (one `Box` per drawn glyph, in order; a space has none), `font` (such as "Fira Code 600") and `baseline`; transforms rescale them.
- `tracking` and `kern` are in 1/1000 em, applied between clusters only; `kern={"AV": -40}` adds to the font's own kerning for that pair.
- `features` is the exact set applied: HarfBuzz's default kern, liga, calt and clig are off unless listed, and a stylistic set can be listed (Fira Code has `ss01` to `ss10`).
- A variable font draws any weight in its range, clamping outside it (Fira Code: 300 to 700); a static family uses its nearest weight file. A missing character exits 2, an uncached family 3 [code].

## Mark and lockups

- `Mark(symbol=None, wordmark=None, tagline=None, lockup="horizontal", gap=None, align="center", roles=None)`. `symbol` is a `Shape` or a `Composite([(shape, role), ...])`; the tagline needs a wordmark and sits under it.
- Lockups: `horizontal` (wordmark right of the symbol, centred, or with `align="baseline"` its baseline on the symbol's bottom), `stacked` (wordmark centred under the symbol), `symbol`, `wordmark`.
- The x unit (`mark.x_unit`, `mark.x_unit_source`) is the cap height of a wordmark set with `text()`, else a fifth of the symbol's height, else the wordmark's height; `gap` defaults to one x, and x is the clear-space unit too.
- `roles` maps `symbol`, `wordmark` and `tagline` to `primary`, `secondary`, `accent` or `ink`; the defaults are symbol `primary`, wordmark and tagline `ink`.
- Methods: `with_lockup(lockup)`, `without_wordmark()`, `layout()` (a list of `Placed(name, shape, role)`), `bounds()`, `to_svg(variant="color", palette=None, padding=0, dark_palette=None)` with variants `color`, `reverse`, `black`, `white`, `mono`, and `geometry()` for the audit.
- The CLI derives outputs: `full-lockup` as built; `full-horizontal` and `full-stacked` given a symbol and a wordmark; `full-symbol`; `full-wordmark`; `compact`, `small`, `favicon` from `TIERS`. Exports pick `full-symbol` from 96 px, `small` from 33 to 95 px and `favicon` below, falling back to the next larger build.
- Anchors are on-curve nodes (a circle has 4, a ring 8). The symbol's total warns above 100 and fails above 150, unless `META` sets `allow_complex=True` with a `complex_reason`, which makes the failure a warning.

## Worked examples

Each builds with only Fira Code cached and passes the audit; `tests/test_knowledge.py` runs all four [code].

1. A monogram cut from a glyph counter: the O's counter places and sizes a square drive; the letter reads as a socket.

```python
from logomaker.kit import *

META = Meta(slug="ostrom-socket", idea="Ostrom's O seen end-on as a socket: its counter becomes the square drive",
            logo_type="lettermark", motifs=["letter O", "square drive"])
PARAMS = Params(weight=700, drive=0.6)
TIERS = {
    "full": {},
    "small": {"drive": 0.64, "wordmark": False},
    "favicon": {"drive": 0.68, "wordmark": False},
}


def build(p):
    o = glyph("O", "Fira Code", weight=p.weight, cap_height=700)
    outer, counter = sorted(o.subpaths(), key=lambda part: part.area, reverse=True)[:2]
    box = counter.bounds  # the counter places and sizes the drive
    side = box.h * p.drive
    symbol = center(subtract(outer, rect_centered(box.cx, box.cy, side, side)))
    word = text("Ostrom", "Fira Code", weight=600, cap_height=180)
    return Mark(symbol=symbol, wordmark=word, lockup="horizontal")
```

2. A pictorial mark from primitives: a wedge, scallops cut through the rib tips, a shaft and a hook; the favicon drops the scallops.

```python
from logomaker.kit import *

META = Meta(slug="brolly-umbrella", idea="An umbrella for Brolly's backups: cover for the day it pours",
            logo_type="pictorial", motifs=["umbrella"])
PARAMS = Params(stroke=56, scallops=4)
TIERS = {
    "full": {},
    "small": {"stroke": 72, "scallops": 3, "wordmark": False},
    "favicon": {"stroke": 96, "scallops": 0, "wordmark": False},
}


def build(p):
    canopy = wedge(0, 0, 400, 0, 180)  # the upper half of a disc
    if p.scallops:
        half = 400 / p.scallops  # a scallop spans two rib tips
        depth = half * 0.6
        r = (half * half + depth * depth) / (2 * depth)  # a circle through both rib tips, `depth` high
        cuts = [circle(-400 + half * (2 * i + 1), depth - r, r) for i in range(p.scallops)]
        canopy = subtract(canopy, union(*cuts))
    shaft = line(0, 400, 0, -330, p.stroke)  # through the canopy: no scallop can cut it loose
    hook = arc(-70, -330, 70, 180, 360, p.stroke, cap="round")
    word = text("brolly", "Fira Code", weight=600, cap_height=180)
    return Mark(symbol=union(canopy, shaft, hook), wordmark=word, lockup="horizontal")
```

3. An abstract mark on a grid: five tiles on a 3 by 3 grid; the favicon closes the gaps into one stair.

```python
from logomaker.kit import *

META = Meta(slug="stepwise-stair", idea="Five tiles climb a 3 x 3 grid: Stepwise teaches one step at a time",
            logo_type="abstract", motifs=["stair", "grid tiles"])
PARAMS = Params(unit=240, gap=28, radius=36)
TIERS = {
    "full": {},
    "small": {"gap": 60, "radius": 24, "wordmark": False},
    "favicon": {"gap": 0, "radius": 0, "wordmark": False},
}
CELLS = [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2)]  # (column, row) from the bottom left


def build(p):
    size = p.unit - p.gap
    tiles = [rrect_centered((c - 1) * p.unit, (r - 1) * p.unit, size, size, p.radius) for c, r in CELLS]
    word = text("stepwise", "Fira Code", weight=500, cap_height=180)
    return Mark(symbol=union(*tiles), wordmark=word, lockup="horizontal")
```

4. A wordmark with one ligature quirk: the two t's share one crossbar. Its `compact` (avatars), `small` (33 to 95 px) and `favicon` (32 px and below) tiers draw that pair; every icon from 96 px up shows the whole wordmark, so tell the owner, or make the pair the `symbol` to have it at every size. Expect two `near_miss_angles` warnings (small, favicon) from the cut atop Fira Code's t; justify them.

```python
from logomaker.kit import *

META = Meta(slug="settle-wordmark", idea="settle's two t's share one crossbar: two parties, one settled bill",
            logo_type="wordmark", motifs=["shared crossbar"])
PARAMS = Params(weight=600, bar=40, icon=False)
TIERS = {
    "full": {},
    "compact": {"icon": True, "weight": 700, "bar": 47},
    "small": {"icon": True, "weight": 700, "bar": 47},
    "favicon": {"icon": True, "weight": 700, "bar": 47},
}


def build(p):
    word = text("tt" if p.icon else "settle", "Fira Code", weight=p.weight, cap_height=300)
    first, second = word.glyph_bounds[0 if p.icon else 2], word.glyph_bounds[1 if p.icon else 3]
    # the t crossbar hangs `bar` deep from the x-height: bridge it stem to stem
    bridge = rect(first.cx, word.x_height - p.bar, second.cx - first.cx, p.bar)
    joined = union(word, bridge)  # the TextShape first, so the wordmark keeps its metrics
    return Mark(symbol=joined) if p.icon else Mark(wordmark=joined)
```

## Sources

spec §6.1 to §6.5 (the kit as specified), §8.1 (audit rules); 04 §1.2 and §1.3 (grids, real glyph outlines, parametric quirks, anchor ceilings); 03 §1.2 (tiers); code: `logomaker.kit.__all__` and `kit/*.py`, `audit.py`.
