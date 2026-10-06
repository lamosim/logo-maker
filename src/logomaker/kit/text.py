"""Type set from real fonts: HarfBuzz shaping (kerning, ligatures, variations) and fontTools outlines into Skia paths."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import skia
import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from .. import fonts as fontlib
from ..paths import project
from .shape import Box, Shape, normalize_winding

# HarfBuzz applies these even when the feature dict leaves them out; text() switches each off unless it is listed.
DEFAULT_ON_FEATURES = ("kern", "liga", "calt", "clig")


class _SkiaPen(BasePen):
    def __init__(self, glyph_set):
        super().__init__(glyph_set)
        self.path = skia.Path()

    def _moveTo(self, p):
        self.path.moveTo(*p)

    def _lineTo(self, p):
        self.path.lineTo(*p)

    def _curveToOne(self, p1, p2, p3):
        self.path.cubicTo(*p1, *p2, *p3)

    def _qCurveToOne(self, p1, p2):
        self.path.quadTo(*p1, *p2)

    def _closePath(self):
        self.path.close()


@dataclass(frozen=True)
class FontMetrics:
    upem: int
    cap_height: float
    x_height: float


@lru_cache(maxsize=16)
def _ttfont(path: str) -> TTFont:
    return TTFont(path)


@lru_cache(maxsize=16)
def _hb_face(path: str) -> hb.Face:
    return hb.Face(hb.Blob.from_file_path(path))


def _glyph_top(glyph_set, name: str) -> float | None:
    """The top (yMax) of glyph `name` as `glyph_set` draws it; None when the glyph is missing or has no outline."""
    if name not in glyph_set:
        return None
    pen = BoundsPen(glyph_set)
    glyph_set[name].draw(pen)
    return pen.bounds[3] if pen.bounds else None


def _metrics(tt: TTFont, glyph_set, variable: bool) -> FontMetrics:
    """Cap height and x-height in font units. A variable font is measured on the drawn instance (the tops of "H" and
    "x" in `glyph_set`), because its axes can move both heights; OS/2 is the fallback there and the first choice for a
    static font."""
    upem = tt["head"].unitsPerEm
    os2 = tt["OS/2"] if "OS/2" in tt else None
    os2_cap, os2_x = getattr(os2, "sCapHeight", 0), getattr(os2, "sxHeight", 0)
    if variable:
        cap = _glyph_top(glyph_set, "H") or os2_cap or upem * 0.7
        x = _glyph_top(glyph_set, "x") or os2_x or cap * 0.5
    else:
        cap = os2_cap or _glyph_top(glyph_set, "H") or upem * 0.7
        x = os2_x or _glyph_top(glyph_set, "x") or cap * 0.5
    return FontMetrics(upem=upem, cap_height=float(cap), x_height=float(x))


def _clamp_weight(tt: TTFont, weight: float) -> float:
    """`weight` clamped to the font's fvar wght range, so an out-of-range request takes the nearest supported weight."""
    for axis in tt["fvar"].axes if "fvar" in tt else ():
        if axis.axisTag == "wght":
            return min(max(weight, axis.minValue), axis.maxValue)
    return weight


class TextShape(Shape):
    __slots__ = ("advance", "cap_height", "x_height", "glyph_bounds", "font")

    def __init__(self, path: skia.Path, *, advance: float, cap_height: float, x_height: float, glyph_bounds: list[Box], font: str):
        super().__init__(path, 0)
        self.advance = advance
        self.cap_height = cap_height
        self.x_height = x_height
        self.glyph_bounds = glyph_bounds
        self.font = font

    def copy(self) -> "TextShape":
        return TextShape(skia.Path(self.path), advance=self.advance, cap_height=self.cap_height, x_height=self.x_height,
                         glyph_bounds=list(self.glyph_bounds), font=self.font)


def text(
    string: str,
    family: str,
    weight: int = 400,
    cap_height: float = 200.0,
    tracking: float = 0.0,
    kern: dict[str, float] | None = None,
    features: tuple[str, ...] = ("kern", "liga"),
    italic: bool = False,
) -> TextShape:
    """Shape `string` with HarfBuzz and outline it with fontTools. Baseline y = 0, start x = 0, scaled to `cap_height`.

    `features` is the exact set of optional OpenType features applied: HarfBuzz's default-on kern, liga, calt and clig
    are switched off unless listed. `tracking` and the `kern` pair overrides (e.g. {"AV": -40}) are in 1/1000 em. A
    variable font's weight is clamped to its wght axis range; a static font ignores it (`font_path` already picked the
    nearest weight's file). `font` names what was drawn: the family, the weight used and "italic" only for an italic file.
    """
    ff = fontlib.font_path(project(), family, weight, italic)
    tt = _ttfont(str(ff.path))
    location = {"wght": _clamp_weight(tt, weight)} if ff.variable else None
    glyph_set = tt.getGlyphSet(location=location) if location else tt.getGlyphSet()
    metrics = _metrics(tt, glyph_set, ff.variable)
    scale = cap_height / metrics.cap_height
    drawn_weight = location["wght"] if location else ff.weight  # font_path gives a static file's weight
    order = tt.getGlyphOrder()

    font = hb.Font(_hb_face(str(ff.path)))
    if location:
        font.set_variations(location)
    buf = hb.Buffer()
    buf.add_str(string)
    buf.guess_segment_properties()
    feats = {tag: tag in features for tag in DEFAULT_ON_FEATURES}
    feats.update({f: True for f in features})
    hb.shape(font, buf, feats)

    path = skia.Path()
    bounds: list[Box] = []
    x = 0.0
    infos, positions = buf.glyph_infos, buf.glyph_positions or []  # uharfbuzz gives None positions for an empty buffer
    track_units = tracking / 1000 * metrics.upem
    for i, (info, pos) in enumerate(zip(infos, positions)):
        pen = _SkiaPen(glyph_set)
        tp = TransformPen(pen, (scale, 0, 0, scale, (x + pos.x_offset) * scale, pos.y_offset * scale))
        glyph_set[order[info.codepoint]].draw(tp)
        if not pen.path.isEmpty():
            r = pen.path.computeTightBounds()
            bounds.append(Box(r.left(), r.top(), r.right(), r.bottom()))
            path.addPath(pen.path)
        advance = float(pos.x_advance)
        if i < len(infos) - 1:
            advance += track_units
            if kern:
                pair = string[info.cluster] + string[infos[i + 1].cluster]
                advance += kern.get(pair, 0.0) / 1000 * metrics.upem
        x += advance
    try:  # merge overlapping contours, then wind them for fill-rule nonzero
        outline = normalize_winding(skia.Simplify(path))
    except RuntimeError:  # skia-python raises when pathops fails; keep the unmerged outlines
        outline = path
    return TextShape(
        outline,
        advance=x * scale,
        cap_height=cap_height,
        x_height=metrics.x_height * scale,
        glyph_bounds=bounds,
        font=f"{family} {drawn_weight:g}{' italic' if ff.italic else ''}",
    )


def glyph(char: str, family: str, weight: int = 400, cap_height: float = 200.0, italic: bool = False) -> TextShape:
    return text(char, family, weight=weight, cap_height=cap_height, features=(), italic=italic)
