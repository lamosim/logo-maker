"""Sheets rendered through Chrome. Part 1: the per-concept critique sheet Claude reads; Part 2 adds owner-facing sheets."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import ValidationError

from . import critic as criticlib
from . import fonts as fontlib
from . import mockups as mockuplib
from . import registry
from .audit import MIN_FEATURE, concept_fingerprint, text_roles
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
# The one-colour test draws the full-symbol and small tiers at the size the audit measures each (MIN_FEATURE: 64 and 32 px),
# falling back as exports do (kit.concept.tier_chain).
ONE_COLOUR = tuple((MIN_FEATURE[tier][0], tier) for tier in ("full-symbol", "small"))
AUDIT_ROWS = 24  # 16 px text rows per column of the audit box; the template sizes the box to fit them
AUDIT_LINES = 2 * AUDIT_ROWS  # the box has two columns
SHOWN_INFO = ("anchors", "min_feature")  # passing measurements listed after the failures and warnings
BOARD_W = 1600
CONCEPTS_W = 1800
CONCEPT_LOCKUP, CONCEPT_MIRROR = 256, 128  # the concept sheet's strip: lockup boxes, mirrored and rotated boxes
REFINE_W = 1600
REFINE_TIERS = (("full-lockup", "full lockup 400", 400), ("compact", "compact 160", 160), ("small", "small 64", 64),
                ("favicon", "favicon 32", 32))  # output, caption, box
X_RULES = {"cap-height": "the wordmark cap height", "symbol-fifth": "one fifth of the symbol height",
           "wordmark-height": "the wordmark height"}  # Mark.x_unit_source -> what x is, in words


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


def _write_sheet(renderer: Renderer | None, html: str, folder: Path, stem: str, width: int,
                 height: int | None = None) -> tuple[Path, Path]:
    """The tail every sheet shares, once its inputs have passed their checks: render `html` (_render_html), then make
    `folder` and write <stem>.html and <stem>.png into it, returning their paths. The render comes first, so a failed
    one leaves no half-written sheet, nor a folder made for it."""
    png = _render_html(renderer, html, width, height)
    folder.mkdir(parents=True, exist_ok=True)
    html_path, png_path = folder / f"{stem}.html", folder / f"{stem}.png"
    html_path.write_text(html, encoding="utf-8")
    png_path.write_bytes(png)
    return html_path, png_path


def next_round(folder: Path, pattern: str = "renders/round-*") -> int:
    """One past the highest N among the paths under `folder` that match `pattern`, with `*` standing for N: a concept's
    renders/round-N folders by default, a brand's sheets/refine-*.html for the refine sheet. Never a count, so a default
    round never lands on one made earlier with --round."""
    prefix, _, suffix = Path(pattern).name.partition("*")
    numbers = [p.name.removeprefix(prefix).removesuffix(suffix) for p in folder.glob(pattern)]
    return max((int(n) for n in numbers if n.isdecimal()), default=0) + 1


def _one_colour_outputs(outputs: dict) -> list[tuple[int, str]]:
    return [(size, conceptlib.first_present(outputs, conceptlib.tier_chain(tier))) for size, tier in ONE_COLOUR]


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


def _saved_audit(folder: Path, rerun: str) -> AuditResult | None:
    """<concept>/audit.json if there is one; a file that is not a valid audit is a CliError naming it, and `rerun`, the
    command that writes it again."""
    path = folder / "audit.json"
    if not path.is_file():
        return None
    try:
        return AuditResult.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as err:  # malformed JSON or the wrong fields
        first = err.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "root"
        raise CliError(f"{path} is not a valid audit ({loc}: {first['msg']}); re-run: {rerun}") from err
    except ValueError as err:  # bytes that are not UTF-8
        raise CliError(f"{path} is not a valid audit ({err}); re-run: {rerun}") from err


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
    tokens.json. An audit whose fingerprint no longer matches the concept and tokens is marked stale, with the audit
    that would match: `--tokens` the same file when the sheet was given one. `outputs` are the concept's built outputs
    when the caller has them already (concept run); otherwise the sheet builds them.
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
    rerun = f"logomaker concept audit {slug} {concept_name}"  # judged against these tokens, so audited against them too
    if tokens_path:
        rerun += f" --tokens {shlex.quote(str(tokens_path))}"
    if audit is None:
        audit = _saved_audit(folder, rerun)
    summary = None
    if audit is not None:
        stale = audit.fingerprint != concept_fingerprint(paths, slug, folder, tokens_path)  # made from other inputs than this sheet's
        summary = {"ok": audit.ok, "rendered": audit.rendered, "stale": stale, "lines": _audit_lines(audit)}
    html = jinja(paths).get_template("sheets/critique.html").render(
        slug=slug, concept=concept_name, round_n=round_n, idea=module.meta.idea, panels=panels, audit=summary, rerun=rerun,
        audit_rows=AUDIT_ROWS, width=SHEET_W, height=SHEET_H,
    )
    html_path, png_path = _write_sheet(renderer, html, folder / "renders" / f"round-{round_n}", "critique", SHEET_W, SHEET_H)
    return {"round": round_n, "critique_png": str(png_path), "critique_html": str(html_path)}


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
        hints = "; ".join(f"run: {fontlib.fetch_command(family)}" for family in uncached)
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
    html_path, png_path = _write_sheet(renderer, html, folder, "board", BOARD_W)
    warnings: list[str] = []
    open_file(html_path, open_after, warnings)
    return {"board_html": str(html_path), "board_png": str(png_path), "territories": [t.slug for t in spec.territories],
            "warnings": warnings}


def mark_mockups(outputs: dict) -> dict[str, str]:
    """The output each mockup that draws the mark rather than a lockup shows, as exports pick it: the phone's icon the
    tier for 60 px, the browser tab's favicon the tier for 16 px, and the avatar the `compact` tier when the concept
    builds one (as the avatar exports do), else the tier for 80 px."""
    avatar = "compact" if "compact" in outputs else conceptlib.pick_output(outputs, 80)
    return {"icon": conceptlib.pick_output(outputs, 60), "favicon": conceptlib.pick_output(outputs, 16), "avatar": avatar}


def mockup_context(state: BrandState, outputs: dict, light: dict | None, dark: dict | None) -> dict:
    """What the seven mockups (templates/mockups) draw for one concept: its outputs in colour from `light` and `dark`
    (black and white without tokens), each mark picked as exports pick it (mark_mockups), generated neighbour icons for
    the home screen and the other browser tabs, and `warnings`: a concept without a symbol is told that the package's
    app icons from 96 px up and its mark files show the whole wordmark, whatever its tiers draw, and which of the icon,
    favicon and avatar mockups show it too, because no tier of its own draws them (the full lockup stands in)."""
    drawn = mark_mockups(outputs)
    stand_ins = [mockup for mockup, output in drawn.items() if output == "full-lockup"]  # only without a symbol
    warnings: list[str] = []
    if "full-symbol" not in outputs:
        warning = "no symbol in this concept: app icons from 96 px up and the mark files show the whole wordmark"
        if stand_ins:
            named = stand_ins[0] if len(stand_ins) == 1 else f"{', '.join(stand_ins[:-1])} and {stand_ins[-1]}"
            warning += f"; so {'does' if len(stand_ins) == 1 else 'do'} the {named} {'mockup' if len(stand_ins) == 1 else 'mockups'}"
        warnings.append(warning)
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
        "icon_svg": fit_box(outputs[drawn["icon"]].to_svg("color", palette=on_tile), 36, 36),
        "favicon_svg": colour(outputs[drawn["favicon"]], 16, 16),
        "header_svg": colour(horizontal, 260, 32),
        "header_dark_svg": reverse(horizontal, 260, 32),
        "avatar_svg": colour(outputs[drawn["avatar"]], 48, 48),
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
    its idea, the designer's and the critic's totals and the designer's scores, the critique sheet's strip (lockups in
    CONCEPT_LOCKUP boxes, the true-size ladder, mirrored and rotated in CONCEPT_MIRROR boxes) and the seven mockups; the
    critic's order of them (critic.preference_line: "not comparable" when their cards come from different critic
    sheets) sits under the preface.

    Every named concept is vetted (_vetted, then registry.vetted_scorecard: a fresh critic card that the scorecard is
    reconciled with) before any is built, and the PNG is rendered before the folder and both files are written, so a
    refusal or a failed render leaves no sheet. `warnings` holds each concept's mockup warnings,
    prefixed with its name, then any failure to open the sheet.
    """
    if not concept_names:
        raise CliError("at least one concept is needed (--concepts 01-arch,03-keystone)")
    state = registry.load_state(paths, slug)
    vetted = [(name, *_vetted(paths, slug, name)) for name in concept_names]
    critics = {}
    for name, folder, _ in vetted:
        try:
            critics[name] = registry.vetted_scorecard(paths, slug, folder, f"{name}/scorecard.json")[1]
        except CliError as err:
            raise CliError(f"concept {name}: {err}") from err
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
                      "critic_total": critics[name].total, "critic_passes": critics[name].passes,
                      "strip": _strip_panels(outputs, CONCEPT_LOCKUP, CONCEPT_MIRROR), "warnings": ctx["warnings"],
                      "mockups": [mockuplib.render_mockup(env, kind, ctx) for kind in mockuplib.MOCKUPS]})
    html = env.get_template("sheets/concepts.html").render(brand=state.name, concepts=cards, width=CONCEPTS_W,
                                                           preference=criticlib.preference_line(critics, slug),
                                                           lockup_px=CONCEPT_LOCKUP, mirror_px=CONCEPT_MIRROR)
    html_path, png_path = _write_sheet(renderer, html, paths.brand(slug) / "sheets", "concepts", CONCEPTS_W)
    open_file(html_path, open_after, warnings)
    return {"sheet_html": str(html_path), "sheet_png": str(png_path), "concepts": concept_names, "warnings": warnings}


def critic_sheet(paths: ProjectPaths, slug: str, concept_names: list[str], seed: int | None = None, final: bool = False,
                 renderer: Renderer | None = None) -> dict:
    """Write sheets/critic-N.{html,png} for the blind critic and sheets/critic-N.key.json for the merge (spec 2026-10-08
    §3.1). Each survivor (or final/, with `final`) shows the critique strip, the one-colour panels and the mockups under
    a letter, in the order a Random seeded with `seed` (default N) shuffles them. With the default seed, when that letters
    two or more concepts exactly as the latest critic sheet of the same concepts did, the seed steps up by one until it
    does not; an explicit `seed` is used as given, to reproduce a sheet. The key and the result record the seed used.
    No slug, idea or score is written. Every survivor must be vetted (_vetted: a fresh, rendered, passing audit and a
    gate-passing scorecard), and final/ must pass registry.require_final_audit, before Chrome starts. The key maps
    letters to folder names and records each concept's fingerprint now."""
    import random

    if final and concept_names:
        raise CliError("--final takes no --concepts")
    if not final and not concept_names:
        raise CliError("give --concepts <a,b,c> for survivors, or --final for the final mark")
    twice = sorted({name for name in concept_names if concept_names.count(name) > 1})
    if twice:
        raise CliError(f"{', '.join(twice)} is named twice; give each concept once")
    if len(concept_names) > len(criticlib.LETTERS):
        raise CliError(f"at most {len(criticlib.LETTERS)} concepts on one critic sheet")
    state = registry.load_state(paths, slug)
    brand = paths.brand(slug)
    if final:
        registry.require_final_audit(paths, slug, "the critic sheet")
        folders = [("final", brand / "final")]
    else:
        folders = [(name, _vetted(paths, slug, name)[0]) for name in concept_names]
    round_n = next_round(brand, "sheets/critic-*.key.json")
    explicit = seed is not None  # an explicit --seed reproduces a sheet, so only the default seed moves
    seed = round_n if seed is None else seed
    previous = None if explicit else _previous_letters(brand, round_n, {name for name, _ in folders})
    while True:
        order = list(folders)
        random.Random(seed).shuffle(order)
        if len(order) < 2 or previous is None or _letter_map(order) != previous:
            break
        seed += 1  # the same lettering as the last sheet of these concepts: a second pass needs another shuffle
    env = jinja(paths)
    cards, letters, fingerprints = [], {}, {}
    for letter, (name, folder) in zip(criticlib.LETTERS, order, strict=False):
        module = conceptlib.load_concept(folder)
        outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
        light, dark = _palettes(folder)
        ctx = mockup_context(state, outputs, light, dark)
        cards.append({"letter": letter, "strip": _strip_panels(outputs, CONCEPT_LOCKUP, CONCEPT_MIRROR),
                      "one_colour": [{"size": s, "svg": fit_box(outputs[o].to_svg("black"), s, s)}
                                     for s, o in _one_colour_outputs(outputs)],
                      "mockups": [mockuplib.render_mockup(env, kind, ctx) for kind in mockuplib.MOCKUPS]})
        letters[letter] = name
        fingerprints[name] = concept_fingerprint(paths, slug, folder)
    html = env.get_template("sheets/critic.html").render(brand=state.name, round_n=round_n, count=len(cards), concepts=cards,
                                                         width=CONCEPTS_W, lockup_px=CONCEPT_LOCKUP, mirror_px=CONCEPT_MIRROR)
    html_path, png_path = _write_sheet(renderer, html, brand / "sheets", f"critic-{round_n}", CONCEPTS_W)
    key = criticlib.Key(round=round_n, seed=seed, letters=letters, fingerprints=fingerprints, final=final)
    key_file = criticlib.key_path(brand, round_n)
    key_file.write_text(json.dumps(key.model_dump(), indent=2) + "\n", encoding="utf-8")
    return {"sheet_html": str(html_path), "sheet_png": str(png_path), "key": str(key_file), "round": round_n, "seed": seed,
            "letters": letters}


def _letter_map(order: list[tuple[str, Path]]) -> dict[str, str]:
    return {letter: name for letter, (name, _) in zip(criticlib.LETTERS, order, strict=False)}


def _previous_letters(brand: Path, round_n: int, names: set[str]) -> dict[str, str] | None:
    """The letters of the latest critic sheet before `round_n` that lettered exactly `names`, or None."""
    for earlier in range(round_n - 1, 0, -1):
        path = criticlib.key_path(brand, earlier)
        if not path.is_file():
            continue
        try:
            letters = json.loads(path.read_text(encoding="utf-8"))["letters"]
        except (ValueError, KeyError, TypeError):
            continue
        if isinstance(letters, dict) and set(letters.values()) == names:
            return letters
    return None


def clear_space_svg(mark: Mark, x: float) -> str:
    """The lockup with its clear-space zone: dashed inner (artwork) and outer (artwork + x) rectangles and an x square.
    The padding is x plus half the dashes' stroke, so the outer rectangle's stroke is drawn whole, not cut by the edge."""
    stroke = x / 20
    svg = mark.to_svg("black", padding=x + stroke / 2)
    b = mark.bounds()
    dashes = f'fill="none" stroke="#e8572a" stroke-width="{fmt(stroke)}" stroke-dasharray="{fmt(x / 5)} {fmt(x / 5)}"'
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
    names it), the minimum-size ladder from brand.json's min_sizes (each row drawn by the output exports use there: a
    brand without a horizontal or stacked lockup shows its full lockup), the colour-vision strip and the contrast table,
    type held to the text thresholds as the audit holds it. Without final/tokens.json a note stands in for the colour
    sections. N defaults to one past the highest refine round (next_round). Before Chrome starts: final/concept.py, an
    audit.json that vouches for the final mark as it is now (registry.require_final_audit; nothing reaches the owner
    that failed an audit), the build and tokens.json; the PNG is rendered before sheets/ and both files are written
    (_write_sheet). `warnings` holds the missing small and favicon tiers (also shown on the sheet), then any failure to
    open it.
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
    if tokens is not None:  # light and dark are its palettes
        backgrounds = {"color": light["paper"], "reverse": dark["paper"], "black": "#ffffff", "white": "#000000", "mono": "#ffffff"}
        for variant in VARIANTS:
            variants.append({"label": variant + (" (currentColor)" if variant == "mono" else ""), "background": backgrounds[variant],
                             "svg": fit_box(lockup.to_svg(variant, palette=dark if variant == "reverse" else light), 264, 150),
                             "dark": variant in ("reverse", "white"),  # mono takes currentColor: previewed in the primary
                             "css_color": light["primary"] if variant == "mono" else "inherit"})
        for kind in CVD_KINDS:
            simulated = {role: simulate_cvd(hex_value, kind) for role, hex_value in light.items()}
            cvd.append({"kind": kind, "background": simulated["paper"],
                        "svg": fit_box(lockup.to_svg("color", palette=simulated), 270, 130)})
        contrast = [r.model_dump() for r in check_tokens(tokens, text_roles=text_roles(outputs)).contrast]

    x = lockup.x_unit
    ms = state.min_sizes
    ladder_specs = [
        (conceptlib.first_present(outputs, ("full-horizontal", "full-lockup")),
         f"horizontal {ms.horizontal_px} px / {number(ms.horizontal_mm)} mm", ms.horizontal_px),
        (conceptlib.first_present(outputs, ("full-stacked", "full-lockup")),
         f"stacked {ms.stacked_px} px / {number(ms.stacked_mm)} mm", ms.stacked_px),
        (conceptlib.pick_output(outputs, ms.mark_px), f"mark {ms.mark_px} px / {number(ms.mark_mm)} mm", ms.mark_px),
        (conceptlib.pick_output(outputs, ms.favicon_px), f"favicon {ms.favicon_px} px", ms.favicon_px),
    ]
    ladder = [{"label": label, "px": px, "svg": fit_box(outputs[name].to_svg("black"), px, px * 2)} for name, label, px in ladder_specs]

    round_n = round_n or next_round(brand, "sheets/refine-*.html")
    html = jinja(paths).get_template("sheets/refine.html").render(
        brand=state.name, round_n=round_n, width=REFINE_W, tiers=tiers, lockups=lockups, variants=variants, warnings=warnings,
        clear_space=fit_box(clear_space_svg(lockup, x), 530, 270), x_unit=round(x, 1), x_rule=X_RULES[lockup.x_unit_source],
        ladder=ladder, cvd=cvd, contrast=contrast,
    )
    html_path, png_path = _write_sheet(renderer, html, brand / "sheets", f"refine-{round_n}", REFINE_W)
    open_file(html_path, open_after, warnings)
    return {"sheet_html": str(html_path), "sheet_png": str(png_path), "round": round_n, "warnings": warnings}
