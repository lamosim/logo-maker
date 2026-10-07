"""Vector PDF and EPS from kit paths via reportlab. CMYK is a naive conversion; the README tells printers to confirm.

The bytes are the same every build, so the manifest's hashes are too. The PDF canvas runs in reportlab's invariant mode,
a fixed date (SOURCE_DATE_EPOCH's when set), under a fixed producer and creator; its document ID derives from that date
and the file's own title and author, so each file has its own. renderPS stamps no date or ID into an EPS."""
from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

from reportlab.graphics import renderPS
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.shapes import Path as RLPath
from reportlab.lib.colors import CMYKColor, Color
from reportlab.pdfgen.canvas import FILL_NON_ZERO, Canvas

from .color import info
from .kit.mark import Mark, fill_for
from .kit.shape import Shape

UNIT_PT = 0.25  # 1000 kit units = 250 pt (about 88 mm)
PRINTABLE = ("color", "reverse", "black", "white")  # mono is currentColor, a CSS colour no print file can carry
MODES = ("rgb", "cmyk")


def _colour(hex_value: str, mode: str) -> Color:
    i = info(hex_value)
    if mode == "cmyk":
        c, m, y, k = (v / 100 for v in i["cmyk"])
        return CMYKColor(c, m, y, k)
    r, g, b = (v / 255 for v in i["rgb"])
    return Color(r, g, b)


def _fills(mark: Mark, variant: str, palette: dict | None, mode: str) -> list[tuple[Shape, Color]]:
    """Each part of `mark` with its colour in `variant`, all resolved before a file is opened. A variant other than
    PRINTABLE's, or a mode other than MODES', is a ValueError."""
    if variant == "mono":
        raise ValueError("the mono variant cannot be printed; use color, reverse, black or white")
    if variant not in PRINTABLE:
        raise ValueError(f"unknown variant {variant!r}; use color, reverse, black or white")
    if mode not in MODES:
        raise ValueError(f"mode must be rgb or cmyk, got {mode!r}")
    return [(p.shape, _colour(fill_for(p.role, variant, palette), mode)) for p in mark.layout()]


def _trace(shape: Shape, move: Callable, line: Callable, curve: Callable, close: Callable,
           point: Callable[[float, float], tuple[float, float]] = lambda x, y: (x, y)) -> None:
    """Walk `shape`'s outline (Shape.commands) into a path through its four callbacks: move, line and curve take the
    points `point` maps each kit point to, close takes none."""
    for kind, pts in shape.commands():
        mapped = [point(x, y) for x, y in pts]
        if kind == "M":
            move(*mapped[0])
        elif kind == "L":
            line(*mapped[0])
        elif kind == "C":
            curve(*mapped[0], *mapped[1], *mapped[2])
        elif kind == "Z":
            close()


def mark_to_pdf(mark: Mark, out: Path, variant: str = "color", palette: dict | None = None, mode: str = "rgb",
                title: str = "", author: str = "") -> Path:
    """`mark` as a one-page PDF at `out`, the page the art's own size, with `title` and `author` in its document info.
    Each part fills by the non-zero rule, as in the SVG masters; mode "cmyk" writes CMYK colours, "rgb" RGB ones. The
    kit's y axis points up, as PDF's does: the page is the art's box, scaled, never flipped."""
    fills = _fills(mark, variant, palette, mode)
    b = mark.bounds()
    c = Canvas(str(out), pagesize=(b.w * UNIT_PT, b.h * UNIT_PT), invariant=1)
    c.setProducer("logomaker")  # not reportlab's own string, which a reportlab upgrade could change
    c.setCreator("logomaker")
    c.setTitle(title)
    c.setAuthor(author)
    c.setSubject("logo artwork, outlines only")
    c.scale(UNIT_PT, UNIT_PT)
    c.translate(-b.x0, -b.y0)
    for shape, colour in fills:
        c.setFillColor(colour)
        path = c.beginPath()
        _trace(shape, path.moveTo, path.lineTo, path.curveTo, path.close)
        c.drawPath(path, stroke=0, fill=1, fillMode=FILL_NON_ZERO)
    c.showPage()
    c.save()
    return out


def mark_to_eps(mark: Mark, out: Path, variant: str = "color", palette: dict | None = None, mode: str = "cmyk") -> Path:
    """`mark` as an EPS at `out`, the same art as mark_to_pdf's, for print vendors that still ask for EPS."""
    fills = _fills(mark, variant, palette, mode)
    b = mark.bounds()
    # renderPS writes the %%BoundingBox in whole points, dropping the fraction; rounding the drawing up keeps the art inside it
    drawing = Drawing(math.ceil(b.w * UNIT_PT), math.ceil(b.h * UNIT_PT))
    for shape, colour in fills:
        # renderPS fills a path only in an autoclose mode: by default it writes the outline twice and never fills it
        rp = RLPath(fillColor=colour, strokeColor=None, strokeWidth=0, autoclose="svg", fillMode=FILL_NON_ZERO)
        _trace(shape, rp.moveTo, rp.lineTo, rp.curveTo, rp.closePath, lambda x, y: ((x - b.x0) * UNIT_PT, (y - b.y0) * UNIT_PT))
        drawing.add(rp)
    renderPS.drawToFile(drawing, str(out))
    return out
