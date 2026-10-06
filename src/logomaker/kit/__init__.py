"""Geometry kit. `from logomaker.kit import *` gives concept modules everything they need."""
from .concept import Meta, Params  # noqa: F401
from .mark import Composite, Mark, Placed  # noqa: F401
from .ops import (  # noqa: F401
    align,
    center,
    fit,
    intersect,
    mirror_x,
    mirror_y,
    offset,
    rotate,
    scale,
    stroke,
    subtract,
    translate,
    union,
    xor,
)
from .optical import StrokeWidths, compensate_stroke, optical_center, overshoot  # noqa: F401
from .primitives import (  # noqa: F401
    arc,
    bezier,
    circle,
    line,
    polygon,
    polyline,
    rect,
    rect_centered,
    regular_polygon,
    ring,
    rrect,
    rrect_centered,
    snap,
    snap_angle,
    wedge,
)
from .shape import Box, Shape, fmt, normalize_winding  # noqa: F401
from .text import TextShape, glyph, text  # noqa: F401

__all__ = [
    "Box", "Shape", "fmt", "normalize_winding",
    "arc", "bezier", "circle", "line", "polygon", "polyline", "rect", "rect_centered", "regular_polygon", "ring",
    "rrect", "rrect_centered", "snap", "snap_angle", "wedge",
    "align", "center", "fit", "intersect", "mirror_x", "mirror_y", "offset", "rotate", "scale", "stroke", "subtract",
    "translate", "union", "xor",
    "StrokeWidths", "compensate_stroke", "optical_center", "overshoot",
    "TextShape", "glyph", "text",
    "Composite", "Mark", "Placed", "Meta", "Params",
]
