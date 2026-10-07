"""Sheets rendered through Chrome. Part 1: the per-concept critique sheet Claude reads; Part 2 adds owner-facing sheets."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import ValidationError

from . import fonts as fontlib
from . import mockups as mockuplib
from . import registry
from .audit import concept_fingerprint, text_roles
from .color import CVD_KINDS, Tokens, check_tokens, chip_text, load_tokens, palettes_of, simulate_cvd
from .color import info as color_info
from .kit import arc, glyph, polyline, rect_centered, ring, rrect_centered, text, union
from .kit import concept as conceptlib
from .kit.mark import ROLES, VARIANTS, Mark
from .kit.shape import fmt
from .output import EXIT_EXTERNAL, CliError
from .paths import ProjectPaths
from .render import Renderer, fit_box
from .schemas import AuditResult, BrandState, Scorecard, TerritoriesSpec, TerritoryShapes

SHEET_W, SHEET_H = 2000, 1400
LADDER = (256, 128, 64, 48, 32, 24, 16)
# The one-colour test draws each tier at the size the audit measures it (full-symbol 64 px, small 32 px), falling back as exports do.
ONE_COLOUR = ((64, ("full-symbol", "full-lockup")), (32, ("small", "full-symbol", "full-lockup")))
AUDIT_ROWS = 24  # 16 px text rows per column of the audit box; the template sizes the box to fit them
AUDIT_LINES = 2 * AUDIT_ROWS  # the box has two columns
SHOWN_INFO = ("anchors", "min_feature")  # passing measurements listed after the failures and warnings
CONCEPTS_W = 1800
CONCEPT_LOCKUP, CONCEPT_MIRROR = 256, 128  # the concept sheet's strip: lockup boxes, mirrored and rotated boxes


def number(value: float) -> str:
    """`value` as the sheets and documents print a measure: 25.0 as "25", 6.5 as "6.5"."""
    return f"{value:g}"


def jinja(paths: ProjectPaths) -> Environment:
    """The templates' environment: HTML escaped, Markdown not, and the `num` filter (number)."""
    env = Environment(loader=FileSystemLoader(str(paths.templates)), autoescape=select_autoescape(default=False))
    env.filters["num"] = number
    return env


def _render_html(renderer: Renderer | None, html: str, width: int, height: int | None = None) -> bytes:
    """`html` as a PNG through `renderer`, or through a Chrome of its own when None, so a sheet that checks its inputs first
    starts Chrome only once they pass. The whole page when `height` is None, else exactly `width` x `height`."""
    if renderer is None:
        with Renderer() as own:
            return own.html_to_png(html, width, height, full_page=height is None)
    return renderer.html_to_png(html, width, height, full_page=height is None)


def next_round(folder: Path, pattern: str = "renders/round-*") -> int:
    """One past the highest N among the paths under `folder` that match `pattern`, with `*` standing for N: a concept's
    renders/round-N folders by default, a brand's sheets/refine-*.html for the refine sheet. Never a count, so a default
    round never lands on one made earlier with --round."""
    prefix, _, suffix = Path(pattern).name.partition("*")
    numbers = [p.name.removeprefix(prefix).removesuffix(suffix) for p in folder.glob(pattern)]
    return max((int(n) for n in numbers if n.isdecimal()), default=0) + 1


def _one_colour_outputs(outputs: dict) -> list[tuple[int, str]]:
    return [(size, conceptlib.first_present(outputs, chain)) for size, chain in ONE_COLOUR]


def _audit_lines(audit: AuditResult, budget: int = AUDIT_LINES) -> list[dict]:
    """Every failure, then every warning, then the anchor and minimum-feature measurements, as {"kind", "text"} lines.

    Past `budget` the last line reads "+N more (see audit.json)", so no finding is dropped silently.
    """
    shown = [("fail", f) for f in audit.failures] + [("warn", f) for f in audit.warnings]
    shown += [("info", f) for f in audit.info if f.check in SHOWN_INFO]
    lines = [{"kind": kind, "text": f"{kind}: {f.message}"} for kind, f in shown]
    if len(lines) > budget:
        lines = lines[: budget - 1] + [{"kind": "more", "text": f"+{len(lines) - budget + 1} more (see audit.json)"}]
    return lines


def _saved_audit(folder: Path, slug: str) -> AuditResult | None:
    """<concept>/audit.json if there is one; a file that is not a valid audit is a CliError naming it, and the command
    that writes it again."""
    path = folder / "audit.json"
    if not path.is_file():
        return None
    rerun = f"re-run: logomaker concept audit {slug} {folder.name}"
    try:
        return AuditResult.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as err:  # malformed JSON or the wrong fields
        first = err.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "root"
        raise CliError(f"{path} is not a valid audit ({loc}: {first['msg']}); {rerun}") from err
    except ValueError as err:  # bytes that are not UTF-8
        raise CliError(f"{path} is not a valid audit ({err}); {rerun}") from err


def _read_tokens(folder: Path, tokens_path: str | Path | None = None) -> Tokens | None:
    """The tokens in `tokens_path`, else in <concept>/tokens.json if present, else None.

    A broken tokens file raises load_tokens' CliError, which names the file.
    """
    if not tokens_path:
        tokens_path = folder / "tokens.json"
        if not tokens_path.is_file():
            return None
    return load_tokens(Path(tokens_path))


def _palettes(folder: Path, tokens_path: str | Path | None = None):
    """Light and dark palettes from `tokens_path`, else from <concept>/tokens.json if present, else (None, None).

    A broken tokens file raises load_tokens' CliError, which names the file.
    """
    return palettes_of(_read_tokens(folder, tokens_path))


def _strip_panels(outputs: dict, lockup_px: int, mirror_px: int, colour_px: int | None = None, light: dict | None = None,
                  dark: dict | None = None) -> dict:
    """Rows 1 and 2 of the critique sheet (spec 7.2), which the concept sheet repeats for each concept: the full lockup
    black and white in `lockup_px` boxes; with `colour_px`, colour on light paper and reverse on dark paper for each
    palette given; the ladder at true size, each LADDER step drawn by the tier kit.concept.pick_output picks for it; then
    the big output (the tier picked for 256 px) mirrored and rotated in `mirror_px` boxes."""
    lockup = outputs["full-lockup"]
    big = outputs[conceptlib.pick_output(outputs, 256)].to_svg("black")
    ladder = [(size, conceptlib.pick_output(outputs, size)) for size in LADDER]
    return {
        "black": fit_box(lockup.to_svg("black"), lockup_px, lockup_px),
        "white": fit_box(lockup.to_svg("white"), lockup_px, lockup_px),
        "color": fit_box(lockup.to_svg("color", palette=light), colour_px, colour_px) if colour_px and light else None,
        "reverse": fit_box(lockup.to_svg("reverse", palette=dark), colour_px, colour_px) if colour_px and dark else None,
        "paper_light": light["paper"] if light else "#ffffff",
        "paper_dark": dark["paper"] if dark else "#000000",
        "ladder": [{"size": s, "output": name, "svg": fit_box(outputs[name].to_svg("black"), s, s)} for s, name in ladder],
        "mirror": fit_box(big, mirror_px, mirror_px),
        "rotate": fit_box(big, mirror_px, mirror_px),
    }


def critique_sheet(paths: ProjectPaths, slug: str, concept_name: str, round_n: int | None = None,
                   renderer: Renderer | None = None, audit: AuditResult | None = None, tokens_path: str | Path | None = None,
                   outputs: dict | None = None) -> dict:
    """Write <concept>/renders/round-N/critique.{html,png}.

    `audit` defaults to the concept's audit.json, if there is one, and `tokens_path` (for the colour panels) to its
    tokens.json. An audit whose fingerprint no longer matches the concept and tokens is marked stale. `outputs` are the
    concept's built outputs when the caller has them already (concept run); otherwise the sheet builds them.
    """
    folder = conceptlib.concept_folder(paths, slug, concept_name)
    module = conceptlib.load_concept(folder)
    if outputs is None:
        outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
    light, dark = _palettes(folder, tokens_path)
    round_n = round_n or next_round(folder)
    panels = _strip_panels(outputs, 512, 256, colour_px=384, light=light, dark=dark)
    panels["one_colour"] = [{"size": s, "output": name, "svg": fit_box(outputs[name].to_svg("black"), s, s)}
                            for s, name in _one_colour_outputs(outputs)]
    if audit is None:
        audit = _saved_audit(folder, slug)
    summary = None
    if audit is not None:
        stale = audit.fingerprint != concept_fingerprint(paths, slug, folder, tokens_path)  # made from other inputs than this sheet's
        summary = {"ok": audit.ok, "rendered": audit.rendered, "stale": stale, "lines": _audit_lines(audit)}
    html = jinja(paths).get_template("sheets/critique.html").render(
        slug=slug, concept=concept_name, round_n=round_n, idea=module.meta.idea, panels=panels, audit=summary,
        audit_rows=AUDIT_ROWS, width=SHEET_W, height=SHEET_H,
    )
    png = _render_html(renderer, html, SHEET_W, SHEET_H)
    # The round folder is made only after the render succeeds, so a failure never leaves a half-written round.
    out_dir = folder / "renders" / f"round-{round_n}"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path, png_path = out_dir / "critique.html", out_dir / "critique.png"
    html_path.write_text(html, encoding="utf-8")
    png_path.write_bytes(png)
    return {"round": round_n, "critique_png": str(png_path), "critique_html": str(html_path)}


BOARD_W = 1600


def open_file(path: Path, enabled: bool = True, warnings: list[str] | None = None) -> bool:
    """Open `path` with the macOS `open` command unless `enabled` is False or LOGOMAKER_NO_OPEN is set; True if it started.

    `open` writes to /dev/null, so nothing it prints can land beside the command's JSON. A failure to start it comes
    after the command's files are written, so it is appended to `warnings` (when given), never raised.
    """
    if not enabled or os.environ.get("LOGOMAKER_NO_OPEN"):
        return False
    try:
        subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as err:
        if warnings is not None:
            warnings.append(f"could not open {path}: {err}")
        return False
    return True



def initial_of(name: str) -> str:
    """The letter the territories board sets as a specimen: the name's first letter or digit, upper-cased, else "A"."""
    return next((ch for ch in name if ch.isalnum()), "A").upper()


def shape_specimens(shapes: TerritoryShapes, initial: str, family: str, weight: int) -> list[dict]:
    """Six black specimens of a territory's shape parameters, as {"label", "svg"}: ring, chevron, tile, loop, bars and
    `initial` set in `family` at `weight`. `stroke` sets every band's width (300 units per 1.0); `angularity` of 0.5 or
    more gives mitred joins and butt caps, below it round ones; `corner` rounds the tile; `symmetry` under 0.5 staggers
    the bars and lengthens the loop from 270 to 300 degrees."""
    width = 300 * shapes.stroke
    join = "miter" if shapes.angularity >= 0.5 else "round"
    cap = "butt" if shapes.angularity >= 0.5 else "round"
    tile_radius = 300 * shapes.corner
    bars = [rect_centered(0, y, 300, width) for y in (-100, 0, 100)]
    if shapes.symmetry < 0.5:
        bars = [rect_centered(-30, -100, 240, width), rect_centered(0, 0, 300, width), rect_centered(45, 100, 210, width)]
    specimens = [
        ("ring", ring(0, 0, 150, width)),
        ("chevron", polyline([(-120, -70), (0, 70), (120, -70)], width, cap=cap, join=join)),
        ("tile", rrect_centered(0, 0, 260, 260, tile_radius)),
        ("loop", arc(0, 0, 110, 0, 270 if shapes.symmetry >= 0.5 else 300, width, cap=cap)),
        ("bars", union(*bars)),
        ("initial", glyph(initial, family, weight=weight, cap_height=240)),
    ]
    return [{"label": label, "svg": Mark(symbol=shape).to_svg("black", padding=20)} for label, shape in specimens]


def territories_board(paths: ProjectPaths, slug: str, renderer: Renderer | None = None, open_after: bool = True) -> dict:
    """Write territories/board.{html,png} from territories/territories.json, then open the HTML unless `open_after` is False.

    Everything is checked before Chrome starts: the brand, the spec (missing or invalid exits 2, naming the file) and the
    fonts. The board never fetches: any family the spec names that is not cached exits 3 with a `fonts fetch` hint for
    each. The PNG is rendered before either file is written, so a failed render leaves no half-written board.
    """
    state = registry.load_state(paths, slug)
    brand = paths.brand(slug)
    folder = brand / "territories"
    spec_path = folder / "territories.json"
    label = str(spec_path.relative_to(brand))  # territories/territories.json, as the phase gate names it
    if not spec_path.is_file():
        raise CliError(f"{label} is missing; write the territories spec first")
    spec = registry.load_model(spec_path, TerritoriesSpec, label)
    families = dict.fromkeys(f.family for t in spec.territories for f in t.fonts)
    uncached = [family for family in families if not fontlib.cached_files(paths, family)]
    if uncached:
        hints = "; ".join(f'run: logomaker fonts fetch "{family}"' for family in uncached)
        raise CliError(f"{label} names font families that are not cached: {', '.join(uncached)} ({hints})", code=EXIT_EXTERNAL)
    cards = []
    for t in spec.territories:
        fonts = []
        for f in t.fonts:
            word = text(state.name, f.family, weight=f.weight, cap_height=200)
            fonts.append({"label": f"{f.family} {f.weight}", "svg": Mark(wordmark=word).to_svg("black", padding=10)})
        palette = []
        for c in t.palette:
            i = color_info(c.hex)
            palette.append({"name": c.name, "hex": i["hex"], "oklch": f"oklch({i['oklch'][0]:.2f} {i['oklch'][1]:.3f} {i['oklch'][2]:.0f})",
                            "text": chip_text(c.hex)})
        cards.append({"name": t.name, "embraces": t.embraces, "rejects": t.rejects, "fonts": fonts, "palette": palette,
                      "shapes": shape_specimens(t.shapes, initial_of(state.name), t.fonts[0].family, t.fonts[0].weight)})
    html = jinja(paths).get_template("sheets/territories.html").render(brand=state.name, territories=cards, width=BOARD_W)
    png = _render_html(renderer, html, BOARD_W)
    html_path, png_path = folder / "board.html", folder / "board.png"
    html_path.write_text(html, encoding="utf-8")
    png_path.write_bytes(png)
    warnings: list[str] = []
    open_file(html_path, open_after, warnings)
    return {"board_html": str(html_path), "board_png": str(png_path), "territories": [t.slug for t in spec.territories],
            "warnings": warnings}


def mockup_context(state: BrandState, outputs: dict, light: dict | None, dark: dict | None) -> dict:
    """What the seven mockups (templates/mockups) draw for one concept: its outputs in colour from `light` and `dark`
    (black and white without tokens), each tier picked by size as exports pick it, generated neighbour icons for the
    home screen and the other browser tabs, and `warnings`: a concept without a symbol stands its wordmark in for the
    icon, favicon and avatar."""
    warnings: list[str] = []
    if "full-symbol" not in outputs:
        warnings.append("no symbol in this concept: icon, favicon and avatar mockups use the wordmark")
    try:
        handle = registry.slugify(state.name)  # follows the name, so a renamed working title gets its new handle
    except CliError:  # a name with no ASCII letters or digits to keep
        handle = state.slug
    tabs = ["Inbox", "Calendar"]
    horizontal = outputs[conceptlib.first_present(outputs, ("full-horizontal",))]
    paper_light = light["paper"] if light else "#ffffff"
    paper_dark = dark["paper"] if dark else "#111111"
    tile_fill = light["primary"] if light else "#111111"
    on_tile = {role: paper_light for role in (*ROLES, "paper")}  # the app icon: every role in light paper on a primary tile

    def colour(mark: Mark, box_w: int, box_h: int) -> str:
        svg = mark.to_svg("color", palette=light) if light else mark.to_svg("black")
        return fit_box(svg, box_w, box_h)

    def reverse(mark: Mark, box_w: int, box_h: int) -> str:
        svg = mark.to_svg("reverse", palette=dark) if dark else mark.to_svg("white")
        return fit_box(svg, box_w, box_h)

    return {
        "brand": state.name,
        "handle": handle.replace("-", ""),
        "paper_light": paper_light, "paper_dark": paper_dark, "primary": tile_fill,
        "primary_dark": dark["primary"] if dark else "#eeeeee", "tile_fill": tile_fill,
        "icon_svg": fit_box(outputs[conceptlib.pick_output(outputs, 60)].to_svg("color", palette=on_tile), 36, 36),
        "favicon_svg": colour(outputs[conceptlib.pick_output(outputs, 16)], 16, 16),
        "header_svg": colour(horizontal, 260, 32),
        "header_dark_svg": reverse(horizontal, 260, 32),
        "avatar_svg": colour(outputs[conceptlib.pick_output(outputs, 80)], 48, 48),
        "card_svg": colour(horizontal, 200, 60),
        "sign_svg": fit_box(outputs["full-lockup"].to_svg("white"), 360, 110),
        "neighbours": mockuplib.neighbour_icons(60),
        "tabs": tabs,
        "tab_icons": mockuplib.neighbour_icons(16)[: len(tabs)],  # the other tabs' favicons, kit-drawn like the neighbours
        "warnings": warnings,
    }


def _vetted(paths: ProjectPaths, slug: str, name: str) -> tuple[Path, Scorecard]:
    """The folder and scorecard of concept `name` if it may reach the owner: a passing, rendered audit of the concept as
    it is now (registry.audit_problems, whose messages name the command that clears each problem) and a scorecard.json
    that passes the gate. Otherwise a CliError that names the concept once and says what to do."""
    folder = conceptlib.concept_folder(paths, slug, name)
    problems = registry.audit_problems(paths, slug, folder, "audit.json")
    if problems:
        raise CliError(f"concept {name}: {'; '.join(problems)}")
    if not (folder / "scorecard.json").is_file():
        raise CliError(f"concept {name}: scorecard.json is missing; score it before presenting")
    return folder, registry.passing_scorecard(folder, f"concept {name}: scorecard.json")


def concepts_sheet(paths: ProjectPaths, slug: str, concept_names: list[str], renderer: Renderer | None = None,
                   open_after: bool = True) -> dict:
    """Write sheets/concepts.{html,png} for the owner, then open the HTML unless `open_after` is False. Each concept shows
    its idea and scores, the critique sheet's strip (lockups in CONCEPT_LOCKUP boxes, the true-size ladder, mirrored and
    rotated in CONCEPT_MIRROR boxes) and the seven mockups.

    Every named concept is vetted (_vetted) before any is built, and the PNG is rendered before the folder and both files
    are written, so a refusal or a failed render leaves no sheet. `warnings` holds each concept's mockup warnings,
    prefixed with its name, then any failure to open the sheet.
    """
    if not concept_names:
        raise CliError("at least one concept is needed (--concepts 01-arch,03-keystone)")
    state = registry.load_state(paths, slug)
    vetted = [(name, *_vetted(paths, slug, name)) for name in concept_names]
    env = jinja(paths)
    cards: list[dict] = []
    warnings: list[str] = []
    for name, folder, card in vetted:
        module = conceptlib.load_concept(folder)
        outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
        light, dark = _palettes(folder)
        ctx = mockup_context(state, outputs, light, dark)
        warnings += [f"{name}: {w}" for w in ctx["warnings"]]
        cards.append({"name": name, "idea": module.meta.idea, "total": card.total, "scores": card.scores,
                      "strip": _strip_panels(outputs, CONCEPT_LOCKUP, CONCEPT_MIRROR), "warnings": ctx["warnings"],
                      "mockups": [mockuplib.render_mockup(env, kind, ctx) for kind in mockuplib.MOCKUPS]})
    html = env.get_template("sheets/concepts.html").render(brand=state.name, concepts=cards, width=CONCEPTS_W,
                                                           lockup_px=CONCEPT_LOCKUP, mirror_px=CONCEPT_MIRROR)
    png = _render_html(renderer, html, CONCEPTS_W)
    sheets_dir = paths.brand(slug) / "sheets"
    sheets_dir.mkdir(exist_ok=True)
    html_path, png_path = sheets_dir / "concepts.html", sheets_dir / "concepts.png"
    html_path.write_text(html, encoding="utf-8")
    png_path.write_bytes(png)
    open_file(html_path, open_after, warnings)
    return {"sheet_html": str(html_path), "sheet_png": str(png_path), "concepts": concept_names, "warnings": warnings}


REFINE_W = 1600
REFINE_TIERS = (("full-lockup", "full lockup 400", 400), ("compact", "compact 160", 160), ("small", "small 64", 64),
                ("favicon", "favicon 32", 32))  # output, caption, box
X_RULES = {"cap-height": "the wordmark cap height", "symbol-fifth": "one fifth of the symbol height",
           "wordmark-height": "the wordmark height"}  # Mark.x_unit_source -> what x is, in words


def clear_space_svg(mark: Mark, x: float) -> str:
    """The lockup with its clear-space zone: dashed inner (artwork) and outer (artwork + x) rectangles and an x square."""
    svg = mark.to_svg("black", padding=x)
    b = mark.bounds()
    dashes = f'fill="none" stroke="#e8572a" stroke-width="{fmt(x / 20)}" stroke-dasharray="{fmt(x / 5)} {fmt(x / 5)}"'
    guides = (
        f'<rect x="{fmt(b.x0)}" y="{fmt(-b.y1)}" width="{fmt(b.w)}" height="{fmt(b.h)}" {dashes}/>'
        f'<rect x="{fmt(b.x0 - x)}" y="{fmt(-b.y1 - x)}" width="{fmt(b.w + 2 * x)}" height="{fmt(b.h + 2 * x)}" {dashes}/>'
        f'<rect x="{fmt(b.x0 - x)}" y="{fmt(-b.y1 - x)}" width="{fmt(x)}" height="{fmt(x)}" fill="#e8572a" fill-opacity="0.35"/>'
    )
    return svg.replace("</svg>", guides + "</svg>")


def refine_sheet(paths: ProjectPaths, slug: str, renderer: Renderer | None = None, open_after: bool = True,
                 round_n: int | None = None) -> dict:
    """Write sheets/refine-N.{html,png} from final/ for the owner, then open the HTML unless `open_after` is False.

    The sheet shows the tiers, the lockups, the five colour variants, the clear-space diagram (x as Mark.x_unit_source
    names it), the minimum-size ladder from brand.json's min_sizes, the colour-vision strip and the contrast table, type
    held to the text thresholds as the audit holds it. Without final/tokens.json a note stands in for the colour
    sections. N defaults to one past the highest refine round (next_round). Before Chrome starts: final/concept.py, an
    audit.json that vouches for the final mark as it is now (registry.audit_problems; nothing reaches the owner that
    failed an audit), the build and tokens.json; the PNG is rendered before sheets/ and both files are written.
    `warnings` holds the missing small and favicon tiers (also shown on the sheet), then any failure to open it.
    """
    state = registry.load_state(paths, slug)
    brand = paths.brand(slug)
    final = brand / "final"
    if not (final / "concept.py").is_file():
        raise CliError("final/concept.py is missing; copy the chosen concept into final/ first")
    registry.require_final_audit(paths, slug, "the refine sheet")
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(final)))
    tokens = _read_tokens(final)
    light, dark = palettes_of(tokens)
    lockup = outputs["full-lockup"]
    warnings: list[str] = []

    tiers = []
    for name, label, box in REFINE_TIERS:
        if name in outputs:
            tiers.append({"label": label, "svg": fit_box(outputs[name].to_svg("black"), box, box)})
        elif name in ("small", "favicon"):
            warnings.append(f"tier {name} is not drawn yet; exports will fall back to the next larger build")
    lockups = [{"label": name.replace("full-", ""), "svg": fit_box(outputs[name].to_svg("black"), 290, 170)}
               for name in ("full-horizontal", "full-stacked", "full-symbol", "full-wordmark") if name in outputs]

    variants, cvd, contrast = [], [], []
    if tokens:  # light and dark are its palettes
        backgrounds = {"color": light["paper"], "reverse": dark["paper"], "black": "#ffffff", "white": "#000000", "mono": "#ffffff"}
        for variant in VARIANTS:
            variants.append({"label": variant + (" (currentColor)" if variant == "mono" else ""), "background": backgrounds[variant],
                             "svg": fit_box(lockup.to_svg(variant, palette=dark if variant == "reverse" else light), 270, 150),
                             "dark": variant in ("reverse", "white"), "css_color": "#1f6feb" if variant == "mono" else "inherit"})
        for kind in CVD_KINDS:
            simulated = {role: simulate_cvd(hex_value, kind) for role, hex_value in light.items()}
            cvd.append({"kind": kind, "background": simulated["paper"],
                        "svg": fit_box(lockup.to_svg("color", palette=simulated), 270, 130)})
        contrast = [r.model_dump() for r in check_tokens(tokens, text_roles=text_roles(outputs)).contrast]

    x = lockup.x_unit
    ms = state.min_sizes
    ladder_specs = [
        ("full-horizontal", f"horizontal {ms.horizontal_px} px / {number(ms.horizontal_mm)} mm", ms.horizontal_px),
        ("full-stacked", f"stacked {ms.stacked_px} px / {number(ms.stacked_mm)} mm", ms.stacked_px),
        (conceptlib.pick_output(outputs, ms.mark_px), f"mark {ms.mark_px} px / {number(ms.mark_mm)} mm", ms.mark_px),
        (conceptlib.pick_output(outputs, ms.favicon_px), f"favicon {ms.favicon_px} px", ms.favicon_px),
    ]
    ladder = [{"label": label, "px": px, "svg": fit_box(outputs[name].to_svg("black"), px, px * 2)}
              for name, label, px in ladder_specs if name in outputs]

    round_n = round_n or next_round(brand, "sheets/refine-*.html")
    html = jinja(paths).get_template("sheets/refine.html").render(
        brand=state.name, round_n=round_n, width=REFINE_W, tiers=tiers, lockups=lockups, variants=variants, warnings=warnings,
        clear_space=fit_box(clear_space_svg(lockup, x), 530, 270), x_unit=round(x, 1), x_rule=X_RULES[lockup.x_unit_source],
        ladder=ladder, cvd=cvd, contrast=contrast,
    )
    png = _render_html(renderer, html, REFINE_W)
    sheets_dir = brand / "sheets"
    sheets_dir.mkdir(exist_ok=True)
    html_path, png_path = sheets_dir / f"refine-{round_n}.html", sheets_dir / f"refine-{round_n}.png"
    html_path.write_text(html, encoding="utf-8")
    png_path.write_bytes(png)
    open_file(html_path, open_after, warnings)
    return {"sheet_html": str(html_path), "sheet_png": str(png_path), "round": round_n, "warnings": warnings}
