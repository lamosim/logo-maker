"""Mark: symbol + wordmark (+ tagline) with lockup layout, role-based colour, SVG and geometry output."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .ops import translate
from .shape import Box, Shape, fmt
from .text import TextShape

ROLES = ("primary", "secondary", "accent", "ink", "paper")
LOCKUPS = ("horizontal", "stacked", "symbol", "wordmark")
VARIANTS = ("color", "reverse", "black", "white", "mono")
DEFAULT_ROLES = {"symbol": "primary", "wordmark": "ink", "tagline": "ink"}


class Composite:
    """A symbol made of several shapes with their own colour roles."""

    def __init__(self, parts: list[tuple[Shape, str]]):
        if not parts:
            raise ValueError("Composite needs at least one part")
        for _, role in parts:
            if role not in ROLES:
                raise ValueError(f"role must be one of {ROLES}, got {role!r}")
        self.parts = list(parts)

    @property
    def is_empty(self) -> bool:
        return all(s.is_empty for s, _ in self.parts)

    @property
    def bounds(self) -> Box:
        return Box.union(s.bounds for s, _ in self.parts if not s.is_empty)


@dataclass
class Placed:
    name: str
    shape: Shape
    role: str


def fill_for(role: str, variant: str, palette: dict[str, str] | None) -> str:
    if variant == "black":
        return "#000000"
    if variant == "white":
        return "#ffffff"
    if variant == "mono":
        return "currentColor"
    if palette is None:
        raise ValueError(f"variant {variant!r} needs a palette mapping roles to colours")
    if role not in palette:
        raise ValueError(f"palette has no colour for role {role!r}")
    return palette[role]


def _box_dict(b: Box) -> dict:
    return {"x0": round(b.x0, 3), "y0": round(b.y0, 3), "x1": round(b.x1, 3), "y1": round(b.y1, 3), "w": round(b.w, 3), "h": round(b.h, 3)}


class Mark:
    def __init__(
        self,
        symbol: Shape | Composite | None = None,
        wordmark: Shape | None = None,
        tagline: Shape | None = None,
        lockup: str = "horizontal",
        gap: float | None = None,
        align: str = "center",
        roles: dict[str, str] | None = None,
    ):
        if symbol is None and wordmark is None:
            raise ValueError("Mark needs a symbol or a wordmark")
        if symbol is not None and symbol.is_empty:
            raise ValueError("symbol is empty")
        if wordmark is not None and wordmark.is_empty:
            raise ValueError("wordmark is empty")
        if lockup not in LOCKUPS:
            raise ValueError(f"lockup must be one of {LOCKUPS}, got {lockup!r}")
        if lockup == "symbol" and symbol is None:
            raise ValueError("lockup 'symbol' needs a symbol")
        if lockup == "wordmark" and wordmark is None:
            raise ValueError("lockup 'wordmark' needs a wordmark")
        if align not in ("center", "baseline"):
            raise ValueError("align must be 'center' or 'baseline'")
        self.symbol = symbol
        self.wordmark = wordmark
        self.tagline = tagline
        self.lockup = lockup
        self.gap = gap
        self.align = align
        self.roles = {**DEFAULT_ROLES, **(roles or {})}
        for role in self.roles.values():
            if role not in ROLES:
                raise ValueError(f"role must be one of {ROLES}, got {role!r}")

    def _copy(self, **changes) -> "Mark":
        kwargs = dict(symbol=self.symbol, wordmark=self.wordmark, tagline=self.tagline, lockup=self.lockup, gap=self.gap, align=self.align, roles=self.roles)
        kwargs.update(changes)
        return Mark(**kwargs)

    def with_lockup(self, lockup: str) -> "Mark":
        return self._copy(lockup=lockup)

    def without_wordmark(self) -> "Mark":
        return self._copy(wordmark=None, tagline=None, lockup="symbol")

    def _symbol_bounds(self) -> Box:
        assert self.symbol is not None
        return self.symbol.bounds

    def _symbol_parts(self) -> list[tuple[str, Shape, str]]:
        if isinstance(self.symbol, Composite):
            return [("symbol" if i == 0 else f"symbol-{i + 1}", s, r) for i, (s, r) in enumerate(self.symbol.parts)]
        return [("symbol", self.symbol, self.roles["symbol"])]  # type: ignore[list-item]

    @property
    def x_unit(self) -> float:
        """Clear-space and gap unit: wordmark cap height, else one fifth of the symbol height."""
        if isinstance(self.wordmark, TextShape):
            return self.wordmark.cap_height
        if self.symbol is not None:
            return self._symbol_bounds().h / 5
        return self.wordmark.bounds.h  # type: ignore[union-attr]

    def layout(self) -> list[Placed]:
        gap = self.gap if self.gap is not None else self.x_unit
        placed: list[Placed] = []
        has_symbol = self.symbol is not None and self.lockup != "wordmark"
        has_word = self.wordmark is not None and self.lockup != "symbol"
        sym_box: Box | None = None
        if has_symbol:
            sb = self._symbol_bounds()
            dx, dy = -sb.cx, -sb.cy
            for name, shape, role in self._symbol_parts():
                placed.append(Placed(name, translate(shape, dx, dy), role))
            sym_box = Box(sb.x0 + dx, sb.y0 + dy, sb.x1 + dx, sb.y1 + dy)
        if has_word:
            wb = self.wordmark.bounds  # type: ignore[union-attr]
            if sym_box is not None and self.lockup == "horizontal":
                dx = sym_box.x1 + gap - wb.x0
                dy = sym_box.y0 if self.align == "baseline" else sym_box.cy - wb.cy
            elif sym_box is not None and self.lockup == "stacked":
                dx, dy = -wb.cx, sym_box.y0 - gap - wb.y1
            else:
                dx, dy = -wb.cx, -wb.cy
            word = translate(self.wordmark, dx, dy)  # type: ignore[arg-type]
            placed.append(Placed("wordmark", word, self.roles["wordmark"]))
            if self.tagline is not None:
                word_box, tb = word.bounds, self.tagline.bounds
                tdx = word_box.cx - tb.cx if (self.lockup == "stacked" or sym_box is None) else word_box.x0 - tb.x0
                tdy = word_box.y0 - gap / 2 - tb.y1
                placed.append(Placed("tagline", translate(self.tagline, tdx, tdy), self.roles["tagline"]))
        return placed

    def bounds(self) -> Box:
        return Box.union(p.shape.bounds for p in self.layout())

    def to_svg(self, variant: str = "color", palette: dict[str, str] | None = None, padding: float = 0.0, dark_palette: dict[str, str] | None = None) -> str:
        if variant not in VARIANTS:
            raise ValueError(f"variant must be one of {VARIANTS}, got {variant!r}")
        placed = self.layout()
        b = self.bounds()
        view = (b.x0 - padding, -b.y1 - padding, b.w + 2 * padding, b.h + 2 * padding)
        groups: dict[str, list[str]] = {}
        for p in placed:
            gid = "symbol" if p.name.startswith("symbol") else p.name
            cls = f' class="r-{p.role}"' if dark_palette else ""
            fill = fill_for(p.role, variant, palette)
            groups.setdefault(gid, []).append(f'<path{cls} fill="{fill}" fill-rule="nonzero" d="{p.shape.to_path_data()}"/>')
        style = ""
        if dark_palette:
            rules = "".join(f".r-{role}{{fill:{colour}}}" for role, colour in dark_palette.items())
            style = f"<style>@media (prefers-color-scheme: dark){{{rules}}}</style>"
        body = "".join(f'<g id="{gid}">{"".join(paths)}</g>' for gid, paths in groups.items())
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{fmt(view[0])} {fmt(view[1])} {fmt(view[2])} {fmt(view[3])}">{style}{body}</svg>'

    def geometry(self) -> dict:
        placed = self.layout()
        parts = []
        for p in placed:
            segments = [
                {"from": [round(x0, 3), round(y0, 3)], "to": [round(x1, 3), round(y1, 3)],
                 "angle": round(math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180, 3)}
                for (x0, y0), (x1, y1) in p.shape.straight_segments()
            ]
            cx, cy = p.shape.centroid
            parts.append({
                "name": p.name, "role": p.role, "bounds": _box_dict(p.shape.bounds), "anchors": p.shape.anchor_count(),
                "area": round(p.shape.area, 3), "centroid": [round(cx, 3), round(cy, 3)], "straight_segments": segments,
                "free_segments": p.shape.free_segments, "subpaths": [_box_dict(s.bounds) for s in p.shape.subpaths()],
            })
        wordmark = None
        if isinstance(self.wordmark, TextShape) and self.lockup != "symbol":
            wordmark = {"cap_height": self.wordmark.cap_height, "x_height": round(self.wordmark.x_height, 3),
                        "advance": round(self.wordmark.advance, 3), "font": self.wordmark.font}
        return {"lockup": self.lockup, "x_unit": round(self.x_unit, 3), "bounds": _box_dict(self.bounds()),
                "parts": parts, "wordmark": wordmark, "roles": sorted({p.role for p in placed})}
