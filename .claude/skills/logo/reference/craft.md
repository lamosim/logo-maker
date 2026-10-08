# Craft

Read this when: building and revising concept modules (phase 4), and doing the optical corrections, small tiers and wordmark of refinement (phase 5).

Craft is subtraction plus optics: one idea, black first, tested at 16 px, corrected by eye [05 §0]. The kit gives the geometry; these rules give the judgment.

## Optical corrections

| Correction | Why | Amount | In the kit |
|---|---|---|---|
| Overshoot | a circle as tall as a square looks smaller; round and pointed forms must pass the baseline and cap height [05 §5.2] | 1.5 percent, the kit's default [spec §6.2] | `overshoot(shape, amount=0.015)` scales the whole part about its own box centre, in both directions: use it on round or pointed parts only |
| Stroke compensation | horizontals look heavier than verticals of the same width; curves look thinner than straight lines; diagonals need their own adjustment [05 §5.2] | horizontals 92 percent and curves 105 percent of the vertical width, the kit's defaults [spec §6.2] | `compensate_stroke(base_width)` returns `StrokeWidths(vertical, horizontal, curve)`; build each stroke with its own width |
| Optical centre | a part centred by its box looks low; set it slightly above true centre (the Pringles face) [05 §5.2] | the research gives no figure: start near 1 to 2 percent of the container's height and judge it on the 512 px panel [synthesis] | `center()` it, then `translate(part, 0, dy)` upward (y is up). No helper raises a part |
| Balance by mass | a lopsided part (a wedge, an arrow, an L) looks off-centre when its box is centred | until it looks still | `center(shape, optical=True)` centres the area centroid (`optical_center(shape)` returns it): a different correction, which raises nothing |
| Optical sizing | an icon is not a scaled lockup [05 §5.2] | see the next section | `TIERS` overrides |
| Letterspacing | pairs are spaced by eye, not by metrics [05 §5.2] | see the wordmark rules | `tracking`, `kern` |

The research gives the direction of each correction, not its size; the kit's 1.5, 92 and 105 percent are starting points from the spec, to be judged on the critique sheet [05 §5.2] [spec §6.2]. Recipe 6 below uses all of them.

## Small-size redraw

1. The small version is redrawn, not scaled: thicker strokes, opened counters, dropped detail, more space [05 §5.2] [03 §1.2].
2. The tier model: full lockup from about 120 px wide; symbol alone from about 48 px; a simplified mark on a 15 to 19 unit grid for 24 to 32 px; a monogram for 16 px. Slack draws its octothorpe on a 19 by 19 grid and ships a separate small one on a 15 by 15 grid with more open spacing, below 30 px [03 §1.2].
3. Here the tiers are parameter overrides in `TIERS`: `small` draws 33 to 95 px, `favicon` 32 px and below. Override any parameter, including a switch that drops detail, and add `"wordmark": False` to drop the wordmark [spec §6.4] [code].
4. Think of the favicon on a 16 by 16 pixel grid: one pixel is a sixteenth of the mark's longest side [synthesis from 03 §1.2].
5. The rendered audit's floors [code]: the thinnest stroke is at least 1.0 px at 16 px (`favicon`), 1.5 px at 32 px (`small`) and 1.5 px at 64 px (the full symbol). In canvas terms a stroke must be at least 1/16, 1/21 and 1/43 of the mark's longest side. A part under 1/48 of it warns, and fails in `small` and `favicon`. The count of separate parts must be the same at 512 px and at the target size: gaps that close or joins that break fail `small` and `favicon`.
6. The stroke test erodes until a whole part vanishes, so a thin spur on a thick body passes it; look for spurs yourself in the 16 and 24 px panels [code].
7. No text below about 7 px x-height: small and favicon tiers carry no wordmark [02 §K rule 19].
8. Test at 16, 32 and 48 px on light and dark; the critique sheet's ladder runs 256 down to 16 px [02 §K rule 19] [03 §6.1].
9. Keep one closed, flat, high-contrast silhouette and one owned colour for 16 to 64 px [02 §K rule 19].

## Wordmark rules

1. Real fonts only: set type with `text()` and `glyph()` from a cached family. Hand-drawn letters are the most reliable tell of LLM output [04 §1.2] [spec §2].
2. One owned quirk at most, applied parametrically to the outlines: a ligature, a cut, a notch or a terminal [04 §1.2] [spec §4.6]. "Custom wordmark with one owned typographic quirk" is on the use list; over-fused "Typemelts" are not [05 §1.2, §1.4].
3. Letter identity survives the quirk. Kia's joined letters read as "KN" to 26 percent of people and drew about 30,000 monthly searches for "KN car" [01 §2] [05 §2].
4. Track optically, pair by pair: tighter at display sizes, looser at small sizes; straight-straight pairs need more air than round-round pairs [05 §5.2]. In the kit `tracking` and `kern` are in 1/1000 em, between clusters only, and `kern` values add to the font's own kerning [code].
5. The Kia test: before presenting, read the wordmark where it is smallest (the 32 px site-header mockups on the concept sheet, the refine sheet's minimum-size ladder) as a stranger would, and ask whether any letter could be taken for another (K and N, rn and m, cl and d, I, l and 1) [05 §5.4] [code].
6. The audit fails a wordmark whose x-height is under 7 px at the brand's minimum widths (120 px horizontal, 160 px stacked); shorten the lockup or enlarge the type, never thin it [code] [02 §K rule 19].
7. Decide case before drawing: uppercase reads premium and masculine, lowercase approachable [02 §K rule 12] [05 §3.6].
8. Weight follows personality: heavy for power, competence and ruggedness, light for sophistication [02 §K rules 10 and 12].
9. Keep the wordmark's `TextShape` the first operand of every operation, so the audit can still measure it [code].

## Construction checklist

The fourteen-item craft checklist [05 §5.4], plus the routes item, with where each item is settled:

- [ ] One idea per mark, said in one sentence without the word "represents" (`META.idea`)
- [ ] 30 or more thumbnails before any vector; 3 to 5 directions picked, 2 to 3 developed, 1 to 3 presented (here: 12 to 20 ideas in concepts/ideas.md, 5 to 8 directions, 3 to 5 survivors [spec §4.5])
- [ ] Ideas tagged by route, five or more routes covered, one non-literal survivor on the sheet (scorecard.md, "Routes and the probe")
- [ ] Designed in black first; colour is the last decision and must not be load-bearing (phase 4 is black only)
- [ ] Passes Rand's seven and Haviv's three; "appropriate" checked against archetype and category register (scorecard)
- [ ] Reads correctly at a glance to strangers: the first-read test, the Kia test
- [ ] Unintended-readings pass: rotate 90 and 180, mirror, squint, blur, animate, check across cultures (the mirrored and rotated panels)
- [ ] Not on the category's cliché blacklist; uniqueness scored against the five nearest competitors (cliches.md, criterion 2)
- [ ] Works in one colour, reversed, grayscale, embroidered, engraved, and at 16, 32 and 48 px (the audit and the ladder)
- [ ] Overshoot, stroke compensation and optical centring applied; icon re-drawn, not scaled (this page)
- [ ] Wordmark tracked optically; ligatures never erase letter identity
- [ ] Combination mark parts share construction DNA and separate cleanly
- [ ] Still frame survives without motion; motion follows the mark's logic (rotate, reveal, phase)
- [ ] Clear space, minimum size, forbidden uses, and an anchor state for any dynamic system specified (the package writes them)
- [ ] Rationale fits on one slide; no golden ratio, no Parthenon

## Kit recipes

Each snippet runs as written inside a concept module (after `from logomaker.kit import *`), with Fira Code cached [code].

1. Monogram from a glyph counter: take a letter's counter as its own shape and re-cut it.

```python
letter = glyph("D", "Fira Code", weight=700, cap_height=600)
outer, counter = sorted(letter.subpaths(), key=lambda part: part.area, reverse=True)[:2]
window = offset(counter, -40)                # the counter, 40 units smaller all round
monogram = center(subtract(outer, window))   # a heavier D whose counter is re-cut as a smaller window
```

2. Ring with a gap: `ring()` gives butt ends, `arc(..., cap="round")` round ones (`arc()` defaults to butt); angles snap to 15 degrees.

```python
band = ring(0, 0, 400, 90, start=30, end=330)        # butt ends; the 60-degree gap faces east (0 degrees)
gap_up = rotate(band, 90)                             # turn the gap to face north
rounded = arc(0, 0, 355, 30, 330, 90, cap="round")   # the same band with round ends: centreline 400 - 90 / 2
```

3. Keyline grid: every size a whole number of units, for consistent radii and strokes [05 §5.3].

```python
UNIT = 1000 / 12                       # the keyline unit: the canvas in twelfths


def k(n):
    return snap(n * UNIT)              # every size and position is a whole number of units


body = rrect_centered(0, 0, k(8), k(8), k(2))
eye = circle(k(-1), k(1), k(1))
mark = subtract(body, eye)
```

4. Negative-space cut: a stroked path subtracted from a solid draws a second figure.

```python
tile = rrect_centered(0, 0, 720, 720, 120)
path = [(-180, 180), (180, 180), (180, 0), (-180, 0), (-180, -180), (180, -180)]
channel = polyline(path, 80)                # a stroked path, mitred at the corners
mark = subtract(tile, channel)              # the tile stays one piece; the cut channel draws a squared 2
```

5. Badge with inner clear space: keep at least one band width between the emblem and the frame.

```python
import math

band = ring(0, 0, 450, 60)                                            # the frame, 60 units wide
emblem = center(glyph("B", "Fira Code", weight=700, cap_height=380))
box = emblem.bounds
clear = 450 - 60 - math.hypot(box.w, box.h) / 2                       # from the emblem's corners to the frame
assert clear >= 60, f"only {clear:.0f} units clear; shrink the emblem"  # at least one band width inside
badge = union(band, emblem)
```

6. Optical corrections in one place.

```python
square = rect_centered(-260, 0, 400, 400)
disc = overshoot(circle(260, 0, 200))           # 1.5 percent larger, so it looks as tall as the square
w = compensate_stroke(80)                        # vertical 80, horizontal 73.6, curve 84
cross = union(rect_centered(0, 0, 400, w.horizontal), rect_centered(0, 0, w.vertical, 400))
hoop = ring(0, 0, 200, w.curve)
tile = rrect_centered(0, 0, 600, 600, 100)
point = polygon([(-150, -130), (150, -130), (0, 130)])
mark = subtract(tile, translate(center(point), 0, 12))   # centred by its box, then nudged above true centre
```

## Sources

05 §0, §1.2, §1.4, §2 (Kia), §3.6, §5.2 (optical corrections), §5.3 (construction myths), §5.4 (the craft checklist); 04 §1.2 (how practitioners get logo-grade output: grids, real glyph outlines, parametric quirks); 03 §1.2 (responsive tiers, Slack's grids), §6.1 (tests); 02 §K rules 10, 12 and 19; 01 §2 (Kia); spec §2, §4.6, §6.2, §6.4; code: `kit/optical.py`, `kit/ops.py`, `kit/text.py`, `audit.py` (`MIN_FEATURE`, `TINY_FRACTION`, `X_HEIGHT_MIN_PX`), `raster.min_feature_px`.
