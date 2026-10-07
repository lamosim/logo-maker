"""Vector PDF and EPS from kit paths via reportlab. CMYK is a naive conversion; the README tells printers to confirm.

The bytes are the same every build, so the manifest's hashes are too. The PDF canvas runs in reportlab's invariant mode,
a fixed date (SOURCE_DATE_EPOCH's when set) and a document ID derived from it, under a fixed producer; renderPS stamps
no date or ID into an EPS."""
from __future__ import annotations

import math
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


def _colour(hex_value: str, mode: str) -> Color:
    if hex_value == "currentColor":
        raise ValueError("the mono variant cannot be printed; use color, reverse, black or white")
    i = info(hex_value)
    if mode == "cmyk":
        c, m, y, k = (v / 100 for v in i["cmyk"])
        return CMYKColor(c, m, y, k)
    r, g, b = (v / 255 for v in i["rgb"])
    return Color(r, g, b)


def _fills(mark: Mark, variant: str, palette: dict | None, mode: str) -> list[tuple[Shape, Color]]:
    """Each part of `mark` with its colour in `variant`, all resolved before a file is opened."""
    return [(p.shape, _colour(fill_for(p.role, variant, palette), mode)) for p in mark.layout()]


def mark_to_pdf(mark: Mark, out: Path, variant: str = "color", palette: dict | None = None, mode: str = "rgb") -> Path:
    """`mark` as a one-page PDF at `out`, the page the art's own size. Each part fills by the non-zero rule, as in the SVG
    masters; mode "cmyk" writes CMYK colours, "rgb" RGB ones."""
    fills = _fills(mark, variant, palette, mode)
    b = mark.bounds()
    c = Canvas(str(out), pagesize=(b.w * UNIT_PT, b.h * UNIT_PT), invariant=1)
    c.setProducer("logomaker")  # not reportlab's own string, which a reportlab upgrade could change
    c.scale(UNIT_PT, UNIT_PT)
    c.translate(-b.x0, -b.y0)
    for shape, colour in fills:
        c.setFillColor(colour)
        path = c.beginPath()
        for kind, pts in shape.commands():
            if kind == "M":
                path.moveTo(*pts[0])
            elif kind == "L":
                path.lineTo(*pts[0])
            elif kind == "C":
                path.curveTo(*pts[0], *pts[1], *pts[2])
            elif kind == "Z":
                path.close()
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
        for kind, pts in shape.commands():
            scaled = [((x - b.x0) * UNIT_PT, (y - b.y0) * UNIT_PT) for x, y in pts]
            if kind == "M":
                rp.moveTo(*scaled[0])
            elif kind == "L":
                rp.lineTo(*scaled[0])
            elif kind == "C":
                rp.curveTo(*scaled[0], *scaled[1], *scaled[2])
            elif kind == "Z":
                rp.closePath()
        drawing.add(rp)
    renderPS.drawToFile(drawing, str(out))
    return out
