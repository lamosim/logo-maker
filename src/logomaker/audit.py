"""Deterministic concept audits (spec section 8.1). Geometry checks always run; raster checks need a Renderer."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import registry
from .color import check_tokens, load_tokens
from .kit import concept as conceptlib
from .output import CliError
from .paths import ProjectPaths
from .raster import component_count, ink_mask, min_feature_px
from .render import Renderer, svg_size
from .schemas import AuditResult, Finding

ANCHOR_WARN, ANCHOR_FAIL = 100, 150
TINY_FRACTION = 1 / 48
NEAR_MISS_RANGE = (0.3, 3.0)
ANGLE_STEP = 15.0
MIN_FEATURE = {"favicon": (16, 1.0), "small": (32, 1.5), "full-symbol": (64, 1.5)}  # output -> (target px, min feature px)
X_HEIGHT_MIN_PX = 7.0
MAX_ROLES = 3
GENERIC_ASPECT = (0.72, 0.82)
TIER_FALLBACKS = {"small": ("full-symbol", "full-lockup"), "favicon": ("small", "full-symbol", "full-lockup")}  # as exports fall back


def concept_fingerprint(folder: Path, tokens_path: str | Path | None = None) -> str:
    """sha256 (hex) of what an audit reads: concept.py, params.json and the tokens file (`tokens_path`, else
    <folder>/tokens.json), each when present. Each enters as its name and byte count, then its bytes."""
    digest = hashlib.sha256()
    tokens = Path(tokens_path) if tokens_path else folder / "tokens.json"
    for name, path in (("concept.py", folder / "concept.py"), ("params.json", folder / "params.json"), ("tokens.json", tokens)):
        if path.is_file():
            data = path.read_bytes()
            digest.update(f"{name} {len(data)}\n".encode() + data)
    return digest.hexdigest()


def _save(folder: Path, result: AuditResult) -> None:
    (folder / "audit.json").write_text(json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8")


def load_cliches(paths: ProjectPaths) -> dict:
    return json.loads(paths.cliches.read_text(encoding="utf-8"))


def _words(phrase: str) -> re.Pattern:
    """Matches `phrase` as whole words, plural -s/-es allowed: 'hexagon' finds 'hexagons', 'key' does not find 'keystone'."""
    return re.compile(rf"\b{re.escape(phrase.lower().strip())}(?:e?s)?\b")


def resolve_industries(cliches: dict, industry: str | None) -> list[str]:
    """Every industry with an alias appearing as whole words in `industry`, best first.

    An industry ranks by its longest matching alias, then by where that alias first appears; file order breaks exact ties.
    """
    if not industry:
        return []
    needle = industry.lower()
    ranked: list[tuple[tuple[int, int], str]] = []
    for key, entry in cliches["industries"].items():
        hits = [(-len(alias), match.start()) for alias in [key, *entry.get("aliases", [])] if (match := _words(alias).search(needle))]
        if hits:
            ranked.append((min(hits), key))
    ranked.sort(key=lambda item: item[0])  # stable, so exact ties keep file order
    return [key for _, key in ranked]


def resolve_industry(cliches: dict, industry: str | None) -> str | None:
    """The best-ranked industry from resolve_industries, or None."""
    ranked = resolve_industries(cliches, industry)
    return ranked[0] if ranked else None


def check_cliches(motifs: list[str], cliches: dict, industry: str | None) -> list[Finding]:
    """Warn on motifs containing a blacklisted term as whole words: the `any` list, then each resolved industry's list."""
    terms = [(t, "any") for t in cliches["any"]["motifs"]]
    for key in resolve_industries(cliches, industry):
        terms += [(t, key) for t in cliches["industries"][key]["motifs"]]
    out: list[Finding] = []
    for motif in motifs:
        m = motif.lower().strip()
        for term, source in terms:
            if m == term.lower().strip() or _words(term).search(m):
                out.append(Finding(check="cliche", severity="warn", message=f"motif {motif!r} matches the {source} cliché blacklist ({term}); twist it hard or kill it",
                                   data={"motif": motif, "term": term, "source": source}))
                break
    return out


def _symbol_parts(geo: dict) -> list[dict]:
    return [p for p in geo["parts"] if p["name"].startswith("symbol")]


def _geometry_findings(name: str, geo: dict, meta: conceptlib.Meta, lenient: bool = False) -> list[Finding]:
    """Symbol geometry checks for one size; `lenient` (a wordmark lockup standing in for a missing tier) warns instead of failing."""
    out: list[Finding] = []
    parts = _symbol_parts(geo)
    if not parts:
        return out
    anchors = sum(p["anchors"] for p in parts)
    if anchors > ANCHOR_FAIL:
        reason = (meta.complex_reason or "").strip()
        justified = meta.allow_complex and bool(reason)  # allow_complex alone, without a reason, does not excuse the ceiling
        advice = f"allowed as complex: {reason}" if justified else "simplify, or set allow_complex with a complex_reason"
        out.append(Finding(check="anchors", severity="warn" if justified else "fail", message=f"{name}: symbol has {anchors} anchors (over {ANCHOR_FAIL}); {advice}",
                           data={"output": name, "anchors": anchors, "limit": ANCHOR_FAIL, "reason": meta.complex_reason}))
    elif anchors > ANCHOR_WARN:
        out.append(Finding(check="anchors", severity="warn", message=f"{name}: symbol has {anchors} anchors (over {ANCHOR_WARN})",
                           data={"output": name, "anchors": anchors, "limit": ANCHOR_WARN, "reason": meta.complex_reason}))
    else:
        out.append(Finding(check="anchors", severity="info", message=f"{name}: symbol has {anchors} anchors", data={"output": name, "anchors": anchors}))
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
        sev = "fail" if name in ("small", "favicon") and not lenient else "warn"
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
    """Wordmark x-height in px at the brand's minimum lockup width; a wordmark without text metrics warns that it cannot be checked."""
    out: list[Finding] = []
    for name, min_px in (("full-horizontal", state.min_sizes.horizontal_px), ("full-stacked", state.min_sizes.stacked_px), ("full-wordmark", state.min_sizes.horizontal_px)):
        geo = geometries.get(name)
        if not geo:
            continue
        if geo["wordmark"] is None:  # these lockups always show the wordmark, so it was drawn without text()
            out.append(Finding(check="text_legibility", severity="warn", message=f"{name}: wordmark metrics unknown (not a TextShape); x-height cannot be checked — "
                               "build the wordmark with text() and keep it the first operand of every op", data={"output": name}))
            continue
        px = geo["wordmark"]["x_height"] * min_px / geo["bounds"]["w"]
        if px < X_HEIGHT_MIN_PX:
            out.append(Finding(check="text_legibility", severity="fail", message=f"{name}: wordmark x-height is {px:.1f} px at the {min_px} px minimum width (need {X_HEIGHT_MIN_PX}); shorten, thicken or raise the minimum size",
                               data={"output": name, "x_height_px": round(px, 2), "min_px": min_px}))
        else:
            out.append(Finding(check="text_legibility", severity="info", message=f"{name}: wordmark x-height {px:.1f} px at {min_px} px", data={"output": name, "x_height_px": round(px, 2)}))
    return out


def _box_size(svg: str, box: int) -> tuple[int, int]:
    """Render size whose longest side is exactly `box`, as sheets and exports fit marks into square boxes."""
    w, h = svg_size(svg, 1000)
    return (box, max(1, round(box * h / w))) if w >= h else (max(1, round(box * w / h)), box)


def _raster_findings(marks: dict, renderer: Renderer, lenient: frozenset[str] = frozenset()) -> list[Finding]:
    """Raster checks; `marks` maps each checked size (full-symbol, small, favicon) to the Mark it ships as.

    Sizes in `lenient` are stand-ins (a wordmark lockup for a missing tier): their problems warn instead of failing.
    """
    out: list[Finding] = []
    for name, (target, min_px) in MIN_FEATURE.items():
        mark = marks.get(name)
        if mark is None:
            continue
        hard = "warn" if name in lenient else "fail"
        svg = mark.to_svg("black")
        big = ink_mask(renderer.svg_to_png(svg, *_box_size(svg, 512)))
        feature = min_feature_px(big) * target / 512
        if feature < min_px:
            out.append(Finding(check="min_feature", severity=hard, message=f"{name}: thinnest feature is {feature:.2f} px at {target} px (need {min_px}); thicken strokes or redraw the tier",
                               data={"output": name, "feature_px": round(feature, 2), "target": target}))
        else:
            out.append(Finding(check="min_feature", severity="info", message=f"{name}: thinnest feature {feature:.2f} px at {target} px", data={"output": name, "feature_px": round(feature, 2), "target": target}))
        small = ink_mask(renderer.svg_to_png(svg, *_box_size(svg, target)))
        before, after = component_count(big), component_count(small)
        if after < before:
            sev = hard if name in ("small", "favicon") else "warn"
            out.append(Finding(check="one_colour_merge", severity=sev, message=f"{name}: {before} part(s) at 512 px become {after} at {target} px (parts merge or vanish)",
                               data={"output": name, "before": before, "after": after, "target": target}))
    return out


def _checked_outputs(outputs: dict) -> tuple[dict[str, str], list[Finding]]:
    """Map each checked size to the output it uses: a missing small or favicon tier is checked on its export fallback."""
    sources = {"full-symbol": "full-symbol"} if "full-symbol" in outputs else {}
    out: list[Finding] = []
    for tier, chain in TIER_FALLBACKS.items():
        if tier in outputs:
            sources[tier] = tier
            continue
        fallback = next(name for name in chain if name in outputs)  # full-lockup always exists
        sources[tier] = fallback
        if fallback == "full-lockup":  # reached only when the concept has no symbol
            message = (f"tier {tier!r} missing and the concept has no symbol; checks run on 'full-lockup' and only warn. "
                       "Draw monogram small and favicon tiers in build(p) for a usable favicon")
        else:
            message = f"tier {tier!r} missing; checks run on {fallback!r}"
        out.append(Finding(check="tiers", severity="warn", message=message, data={"tier": tier, "fallback": fallback}))
    return sources, out


def audit_concept(paths: ProjectPaths, slug: str, concept_name: str, renderer: Renderer | None = None) -> AuditResult:
    folder = conceptlib.concept_folder(paths, slug, concept_name)
    state = registry.load_state(paths, slug)
    fingerprint = concept_fingerprint(folder)
    try:
        module = conceptlib.load_concept(folder)
        outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
        again = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(folder)))
    except CliError as err:  # a concept that does not build must not keep an earlier, passing audit.json
        _save(folder, AuditResult(ok=False, failures=[Finding(check="build", severity="fail", message=str(err))], fingerprint=fingerprint))
        raise
    geometries = {name: mark.geometry() for name, mark in outputs.items()}
    findings: list[Finding] = []

    if set(again) != set(outputs):
        changed = ", ".join(sorted(set(outputs) ^ set(again)))
        findings.append(Finding(check="determinism", severity="fail", message=f"building twice gave different outputs ({changed} in only one build); remove randomness or time-dependent code",
                                data={"first": list(outputs), "second": list(again)}))
    elif any(outputs[n].to_svg("black") != again[n].to_svg("black") for n in outputs):
        findings.append(Finding(check="determinism", severity="fail", message="building twice gave different SVG; remove randomness or time-dependent code", data={}))

    sources, tier_findings = _checked_outputs(outputs)
    lenient = frozenset(name for name, source in sources.items() if source == "full-lockup")  # wordmark-only stand-ins
    findings += tier_findings
    for name, source in sources.items():
        findings += _geometry_findings(name, geometries[source], module.meta, lenient=name in lenient)
    roles = geometries["full-lockup"]["roles"]
    if len(roles) > MAX_ROLES:
        findings.append(Finding(check="colour_count", severity="warn", message=f"{len(roles)} colour roles in use (more than {MAX_ROLES})", data={"roles": roles}))
    findings += _text_legibility(outputs, geometries, state)
    cliches = load_cliches(paths)
    industries = resolve_industries(cliches, state.industry)
    named = repr(state.industry) if state.industry else "not set"
    if industries:
        message = f"industry {named} resolves to {', '.join(industries)}"
    else:
        message = f"industry {named}: none matched; motifs were checked against the general cliché list only"
    findings.append(Finding(check="industry", severity="info", message=message, data={"industry": state.industry, "resolved": industries}))
    findings += check_cliches(module.meta.motifs, cliches, state.industry)

    tokens_file = folder / "tokens.json"
    if tokens_file.is_file():
        # Type gets the text thresholds: whichever roles the wordmark and tagline are drawn in (ink when there is no type).
        text_roles = sorted({p["role"] for geo in geometries.values() for p in geo["parts"] if p["name"] in ("wordmark", "tagline")}) or ["ink"]
        try:
            check = check_tokens(load_tokens(tokens_file), text_roles=text_roles)
        except CliError as err:  # a broken tokens file is a finding to fix, not a reason to skip the rest of the audit
            findings.append(Finding(check="tokens", severity="fail", message=str(err), data={}))
        else:
            findings += [Finding(check="contrast", severity="fail", message=m, data={}) for m in check.failures]
            findings += [Finding(check="cvd" if m.startswith("cvd") else "grayscale", severity="warn", message=m, data={}) for m in check.warnings]

    rendered = False
    if renderer is not None:
        findings += _raster_findings({name: outputs[source] for name, source in sources.items()}, renderer, lenient)
        rendered = True

    result = AuditResult(
        ok=not any(f.severity == "fail" for f in findings),
        failures=[f for f in findings if f.severity == "fail"],
        warnings=[f for f in findings if f.severity == "warn"],
        info=[f for f in findings if f.severity == "info"],
        outputs=list(outputs),
        rendered=rendered,
        fingerprint=fingerprint,
    )
    _save(folder, result)
    return result
