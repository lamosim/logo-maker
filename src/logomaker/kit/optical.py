"""Optical corrections (see .claude/skills/logo/reference/craft.md): overshoot, stroke compensation, optical centre."""
from __future__ import annotations

from dataclasses import dataclass

from .ops import scale
from .shape import Shape


def overshoot(shape: Shape, amount: float = 0.015) -> Shape:
    """Scale a round or pointed part about its own centre so it visually matches flat neighbours."""
    b = shape.bounds
    return scale(shape, 1 + amount, cx=b.cx, cy=b.cy)


@dataclass(frozen=True)
class StrokeWidths:
    vertical: float
    horizontal: float
    curve: float


def compensate_stroke(base_width: float, horizontal_factor: float = 0.92, curve_factor: float = 1.05) -> StrokeWidths:
    """Horizontals look heavier than verticals and curves look thinner; return widths that read as equal."""
    return StrokeWidths(vertical=base_width, horizontal=base_width * horizontal_factor, curve=base_width * curve_factor)


def optical_center(shape: Shape) -> tuple[float, float]:
    return shape.centroid
