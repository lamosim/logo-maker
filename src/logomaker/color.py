"""Colour maths: conversions, WCAG and APCA contrast, colour-vision-deficiency simulation, OKLCH ramps, tokens checks."""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Literal

from coloraide import Color as _Color
from coloraide.spaces.cmy import CMY
from coloraide.spaces.cmyk import CMYK
from pydantic import BaseModel, Field, model_validator


class Color(_Color):
    pass


Color.register([CMY(), CMYK()])  # coloraide's CMYK converts through CMY, so both must be registered

CVD_KINDS = ("protan", "deutan", "tritan", "achroma")
Context = Literal["light", "dark"]

# APCA-W3 0.1.9 constants
_SRGB = (0.2126729, 0.7151522, 0.0721750)
_NORM_BG, _NORM_TXT, _REV_TXT, _REV_BG = 0.56, 0.57, 0.62, 0.65
_BLK_THRS, _BLK_CLMP = 0.022, 1.414
_SCALE, _OFFSET, _LO_CLIP, _DELTA_Y_MIN = 1.14, 0.027, 0.1, 0.0005


def normalize_hex(value: str) -> str:
    c = Color(value).convert("srgb")
    return c.to_string(hex=True, alpha=False).lower()


def luminance(value: str) -> float:
    return float(Color(value).convert("srgb").luminance())


def info(value: str) -> dict:
    c = Color(value).convert("srgb")
    r, g, b = (round(x * 255) for x in c.coords())
    hsl = c.convert("hsl")
    oklch = c.convert("oklch")
    cmyk = c.convert("cmyk")
    return {
        "hex": normalize_hex(value),
        "rgb": [r, g, b],
        "hsl": [round(hsl["h"] if hsl["h"] == hsl["h"] else 0.0, 1), round(hsl["s"] * 100, 1), round(hsl["l"] * 100, 1)],
        "oklch": [round(oklch["l"], 4), round(oklch["c"], 4), round(oklch["h"] if oklch["h"] == oklch["h"] else 0.0, 2)],
        "cmyk": [round(x * 100) for x in cmyk.coords()],
        "luminance": round(float(c.luminance()), 5),
    }


def wcag_contrast(a: str, b: str) -> float:
    return round(float(Color(a).contrast(Color(b), method="wcag21")), 3)


def _apca_y(value: str) -> float:
    r, g, b = Color(value).convert("srgb").coords()
    r, g, b = (max(0.0, min(1.0, x)) for x in (r, g, b))
    return _SRGB[0] * r**2.4 + _SRGB[1] * g**2.4 + _SRGB[2] * b**2.4


def apca_lc(text_hex: str, bg_hex: str) -> float:
    """APCA lightness contrast (W3 0.1.9). Positive for dark text on light, negative for light on dark."""
    ytxt, ybg = _apca_y(text_hex), _apca_y(bg_hex)
    if ytxt <= _BLK_THRS:
        ytxt += (_BLK_THRS - ytxt) ** _BLK_CLMP
    if ybg <= _BLK_THRS:
        ybg += (_BLK_THRS - ybg) ** _BLK_CLMP
    if abs(ybg - ytxt) < _DELTA_Y_MIN:
        return 0.0
    if ybg > ytxt:
        sapc = (ybg**_NORM_BG - ytxt**_NORM_TXT) * _SCALE
        lc = 0.0 if sapc < _LO_CLIP else sapc - _OFFSET
    else:
        sapc = (ybg**_REV_BG - ytxt**_REV_TXT) * _SCALE
        lc = 0.0 if sapc > -_LO_CLIP else sapc + _OFFSET
    return round(lc * 100, 2)


def simulate_cvd(value: str, kind: str) -> str:
    if kind not in CVD_KINDS:
        raise ValueError(f"kind must be one of {CVD_KINDS}")
    c = Color(value)
    out = c.filter("grayscale", 1) if kind == "achroma" else c.filter(kind)
    return out.convert("srgb").fit("srgb").to_string(hex=True, alpha=False).lower()


def ramp(value: str, steps: int = 9) -> list[str]:
    base = Color(value).convert("oklch")
    out = []
    for i in range(steps):
        light = 0.95 - (0.80 * i / (steps - 1) if steps > 1 else 0)
        c = Color("oklch", [light, base["c"], base["h"] if base["h"] == base["h"] else 0.0])
        out.append(c.convert("srgb").fit("srgb").to_string(hex=True, alpha=False).lower())
    return out


class ColorEntry(BaseModel):
    name: str
    hex: str
    rgb: list[int] = Field(default_factory=list)
    hsl: list[float] = Field(default_factory=list)
    oklch: list[float] = Field(default_factory=list)
    cmyk: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalise(self) -> "ColorEntry":
        self.hex = normalize_hex(self.hex)
        return self


REQUIRED_ROLES = ("primary", "ink")


class Tokens(BaseModel):
    colors: dict[str, ColorEntry]
    roles: dict[Context, dict[str, str]]
    paper: dict[Context, str]

    @model_validator(mode="after")
    def roles_point_at_colours(self) -> "Tokens":
        for context in ("light", "dark"):
            if context not in self.roles or context not in self.paper:
                raise ValueError(f"roles and paper must define both light and dark (missing {context})")
            for role in REQUIRED_ROLES:
                if role not in self.roles[context]:
                    raise ValueError(f"roles.{context} must include {role!r}")
            for role, name in self.roles[context].items():
                if name not in self.colors:
                    raise ValueError(f"roles.{context}.{role} points at unknown colour {name!r}")
            if self.paper[context] not in self.colors:
                raise ValueError(f"paper.{context} points at unknown colour {self.paper[context]!r}")
        return self

    def palette(self, context: Context) -> dict[str, str]:
        out = {role: self.colors[name].hex for role, name in self.roles[context].items()}
        out["paper"] = self.colors[self.paper[context]].hex
        return out


def enrich_tokens(tokens: Tokens) -> Tokens:
    for entry in tokens.colors.values():
        i = info(entry.hex)
        entry.rgb, entry.hsl, entry.oklch, entry.cmyk = i["rgb"], i["hsl"], i["oklch"], i["cmyk"]
    return tokens


def load_tokens(path: Path) -> Tokens:
    return Tokens.model_validate_json(Path(path).read_text(encoding="utf-8"))


class ContrastRow(BaseModel):
    context: str
    role: str
    color: str
    against: str
    wcag: float
    apca: float
    required_wcag: float
    required_apca: float
    ok: bool


class CvdRow(BaseModel):
    kind: str
    context: str
    a: str
    b: str
    contrast: float
    ok: bool


class CheckResult(BaseModel):
    ok: bool
    failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    contrast: list[ContrastRow] = Field(default_factory=list)
    cvd: list[CvdRow] = Field(default_factory=list)
    palettes: dict[str, dict[str, str]] = Field(default_factory=dict)


def check_tokens(tokens: Tokens) -> CheckResult:
    result = CheckResult(ok=True)
    for context in ("light", "dark"):
        palette = tokens.palette(context)
        result.palettes[context] = palette
        paper = palette["paper"]
        roles = {r: c for r, c in palette.items() if r != "paper"}
        for role, hex_value in roles.items():
            need_wcag, need_apca = (4.5, 60.0) if role == "ink" else (3.0, 45.0)
            wcag = wcag_contrast(hex_value, paper)
            apca = apca_lc(hex_value, paper)
            ok = wcag >= need_wcag and abs(apca) >= need_apca
            result.contrast.append(ContrastRow(context=context, role=role, color=hex_value, against=paper, wcag=wcag, apca=apca,
                                               required_wcag=need_wcag, required_apca=need_apca, ok=ok))
            if not ok:
                result.failures.append(f"{context}: role {role} ({hex_value}) on paper {paper}: WCAG {wcag} (need {need_wcag}), APCA {apca} (need {need_apca})")
        for (ra, ca), (rb, cb) in combinations(roles.items(), 2):
            if abs(luminance(ca) - luminance(cb)) < 0.15:
                result.warnings.append(f"grayscale: {context} roles {ra} and {rb} differ by less than 0.15 luminance")
            for kind in CVD_KINDS:
                contrast = wcag_contrast(simulate_cvd(ca, kind), simulate_cvd(cb, kind))
                ok = contrast >= 1.5
                result.cvd.append(CvdRow(kind=kind, context=context, a=ra, b=rb, contrast=contrast, ok=ok))
                if not ok:
                    result.warnings.append(f"cvd {kind}: {context} roles {ra} and {rb} collapse to contrast {contrast}")
    result.ok = not result.failures
    return result
