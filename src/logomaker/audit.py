"""Deterministic concept audits (spec section 8.1). Geometry checks always run; raster checks need a Renderer."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import registry
from .color import check_tokens, load_tokens
from .kit import concept as conceptlib
from .output import CliError
from .paths import ProjectPaths
from .raster import component_count, ink_mask, min_feature_px
from .render import Renderer
from .schemas import AuditResult, Finding

ANCHOR_WARN, ANCHOR_FAIL = 100, 150
TINY_FRACTION = 1 / 48
NEAR_MISS_RANGE = (0.3, 3.0)
ANGLE_STEP = 15.0
MIN_FEATURE = {"favicon": (16, 1.0), "small": (32, 1.5), "full-symbol": (64, 1.5)}  # output -> (target px, min feature px)
X_HEIGHT_MIN_PX = 7.0
MAX_ROLES = 3
GENERIC_ASPECT = (0.72, 0.82)


def load_cliches(paths: ProjectPaths) -> dict:
    return json.loads(paths.cliches.read_text(encoding="utf-8"))


def resolve_industry(cliches: dict, industry: str | None) -> str | None:
    if not industry:
        return None
    needle = industry.lower()
    for key, entry in cliches["industries"].items():
        for alias in [key, *entry.get("aliases", [])]:
            if re.search(rf"\b{re.escape(alias)}\b", needle):
                return key
    return None


def check_cliches(motifs: list[str], cliches: dict, industry: str | None) -> list[Finding]:
    key = resolve_industry(cliches, industry)
    terms = [(t, "any") for t in cliches["any"]["motifs"]]
    if key:
        terms += [(t, key) for t in cliches["industries"][key]["motifs"]]
    out: list[Finding] = []
    for motif in motifs:
        m = motif.lower().strip()
        for term, source in terms:
            if term in m or m in term:
                out.append(Finding(check="cliche", severity="warn", message=f"motif {motif!r} matches the {source} cliché blacklist ({term}); twist it hard or kill it",
                                   data={"motif": motif, "term": term, "source": source}))
                break
    return out


def _symbol_parts(geo: dict) -> list[dict]:
    return [p for p in geo["parts"] if p["name"].startswith("symbol")]


def _geometry_findings(name: str, geo: dict, meta: conceptlib.Meta) -> list[Finding]:
    out: list[Finding] = []
    parts = _symbol_parts(geo)
    if not parts:
        return out
    anchors = sum(p["anchors"] for p in parts)
    if anchors > ANCHOR_FAIL and not meta.allow_complex:
        out.append(Finding(check="anchors", severity="fail", message=f"{name}: symbol has {anchors} anchors (limit {ANCHOR_FAIL}); simplify or set allow_complex with a reason", data={"output": name, "anchors": anchors}))
    elif anchors > ANCHOR_WARN:
        sev = "info" if meta.allow_complex else "warn"
        out.append(Finding(check="anchors", severity=sev, message=f"{name}: symbol has {anchors} anchors (over {ANCHOR_WARN})", data={"output": name, "anchors": anchors, "reason": meta.complex_reason}))
    near = []
    for p in parts:
        for seg in p["straight_segments"]:
            off = seg["angle"] % ANGLE_STEP
            dist = min(off, ANGLE_STEP - off)
            if NEAR_MISS_RANGE[0] <= dist <= NEAR_MISS_RANGE[1]:
                near.append(seg)
    if near:
        out.append(Finding(check="near_miss_angles", severity="warn", message=f"{name}: {len(near)} straight segment(s) are 0.3-3 degrees off a 15-degree angle", data={"output": name, "count": len(near), "segments": near[:5]}))
    free = sum(p["free_segments"] for p in parts)
    if free:
        out.append(Finding(check="free_segments", severity="info", message=f"{name}: {free} segment(s) built with free=True", data={"output": name, "count": free}))
    canvas = max(geo["bounds"]["w"], geo["bounds"]["h"])
    tiny = [sp for p in parts for sp in p["subpaths"] if max(sp["w"], sp["h"]) < canvas * TINY_FRACTION]
    if tiny:
        sev = "fail" if name in ("small", "favicon") else "warn"
        out.append(Finding(check="tiny_parts", severity=sev, message=f"{name}: {len(tiny)} part(s) smaller than 1/48 of the canvas will vanish when small", data={"output": name, "count": len(tiny), "parts": tiny[:5]}))
    b = geo["bounds"]
    aspect = b["h"] / b["w"] if b["w"] else 0
    cx, cy = (sum(p["centroid"][0] * p["area"] for p in parts) / max(sum(p["area"] for p in parts), 1e-9),
              sum(p["centroid"][1] * p["area"] for p in parts) / max(sum(p["area"] for p in parts), 1e-9))
    out.append(Finding(check="bounds", severity="info", message=f"{name}: aspect {aspect:.2f}; centroid offset ({cx - (b['x0'] + b['w'] / 2):.1f}, {cy - (b['y0'] + b['h'] / 2):.1f})",
                       data={"output": name, "aspect": round(aspect, 3), "centroid_offset": [round(cx - (b["x0"] + b["w"] / 2), 2), round(cy - (b["y0"] + b["h"] / 2), 2)]}))
    if GENERIC_ASPECT[0] <= aspect <= GENERIC_ASPECT[1] and name == "full-symbol":
        out.append(Finding(check="generic_profile", severity="info", message="symbol aspect sits in the 3:4 band linked to false recognition (Henderson & Cote 1998); make sure the silhouette is distinctive", data={"aspect": round(aspect, 3)}))
    return out


def _text_legibility(outputs: dict, geometries: dict, state) -> list[Finding]:
    out: list[Finding] = []
    for name, min_px in (("full-horizontal", state.min_sizes.horizontal_px), ("full-stacked", state.min_sizes.stacked_px), ("full-wordmark", state.min_sizes.horizontal_px)):
        geo = geometries.get(name)
        if not geo or not geo.get("wordmark"):
            continue
        px = geo["wordmark"]["x_height"] * min_px / geo["bounds"]["w"]
        if px < X_HEIGHT_MIN_PX:
            out.append(Finding(check="text_legibility", severity="fail", message=f"{name}: wordmark x-height is {px:.1f} px at the {min_px} px minimum width (need {X_HEIGHT_MIN_PX}); shorten, thicken or raise the minimum size",
                               data={"output": name, "x_height_px": round(px, 2), "min_px": min_px}))
        else:
            out.append(Finding(check="text_legibility", severity="info", message=f"{name}: wordmark x-height {px:.1f} px at {min_px} px", data={"output": name, "x_height_px": round(px, 2)}))
    return out


def _raster_findings(outputs: dict, renderer: Renderer) -> list[Finding]:
    out: list[Finding] = []
    for name, (target, min_px) in MIN_FEATURE.items():
        mark = outputs.get(name)
        if mark is None:
            continue
        svg = mark.to_svg("black")
        big = ink_mask(renderer.svg_to_png(svg, 512))
        feature = min_feature_px(big) * target / 512
        if feature < min_px:
            out.append(Finding(check="min_feature", severity="fail", message=f"{name}: thinnest feature is {feature:.2f} px at {target} px (need {min_px}); thicken strokes or redraw the tier",
                               data={"output": name, "feature_px": round(feature, 2), "target": target}))
        else:
            out.append(Finding(check="min_feature", severity="info", message=f"{name}: thinnest feature {feature:.2f} px at {target} px", data={"output": name, "feature_px": round(feature, 2), "target": target}))
        small = ink_mask(renderer.svg_to_png(svg, target))
        before, after = component_count(big), component_count(small)
        if after < before:
            sev = "fail" if name in ("small", "favicon") else "warn"
            out.append(Finding(check="one_colour_merge", severity=sev, message=f"{name}: {before} part(s) at 512 px become {after} at {target} px (parts merge or vanish)",
                               data={"output": name, "before": before, "after": after, "target": target}))
    return out


def audit_concept(paths: ProjectPaths, slug: str, concept_name: str, renderer: Renderer | None = None) -> AuditResult:
    folder = conceptlib.concept_folder(paths, slug, concept_name)
    state = registry.load_state(paths, slug)
    module = conceptlib.load_concept(folder)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
    geometries = {name: mark.geometry() for name, mark in outputs.items()}
    findings: list[Finding] = []

    again = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(folder)))
    if any(outputs[n].to_svg("black") != again[n].to_svg("black") for n in outputs):
        findings.append(Finding(check="determinism", severity="fail", message="building twice gave different SVG; remove randomness or time-dependent code", data={}))

    for name in ("full-symbol", "small", "favicon"):
        if name in geometries:
            findings += _geometry_findings(name, geometries[name], module.meta)
    roles = geometries["full-lockup"]["roles"]
    if len([r for r in roles if r != "paper"]) > MAX_ROLES:
        findings.append(Finding(check="colour_count", severity="warn", message=f"{len(roles)} colour roles in use (more than {MAX_ROLES})", data={"roles": roles}))
    findings += _text_legibility(outputs, geometries, state)
    findings += check_cliches(module.meta.motifs, load_cliches(paths), state.industry)

    tokens_file = folder / "tokens.json"
    if tokens_file.is_file():
        try:
            check = check_tokens(load_tokens(tokens_file))
        except CliError as err:  # a broken tokens file is a finding to fix, not a reason to skip the rest of the audit
            findings.append(Finding(check="tokens", severity="fail", message=str(err), data={}))
        else:
            findings += [Finding(check="contrast", severity="fail", message=m, data={}) for m in check.failures]
            findings += [Finding(check="cvd" if m.startswith("cvd") else "grayscale", severity="warn", message=m, data={}) for m in check.warnings]

    rendered = False
    if renderer is not None:
        findings += _raster_findings(outputs, renderer)
        rendered = True

    result = AuditResult(
        ok=not any(f.severity == "fail" for f in findings),
        failures=[f for f in findings if f.severity == "fail"],
        warnings=[f for f in findings if f.severity == "warn"],
        info=[f for f in findings if f.severity == "info"],
        outputs=list(outputs),
        rendered=rendered,
    )
    (folder / "audit.json").write_text(json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8")
    return result
