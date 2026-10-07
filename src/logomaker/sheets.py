"""Sheets rendered through Chrome. Part 1: the per-concept critique sheet Claude reads; Part 2 adds owner-facing sheets."""
from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import ValidationError

from . import fonts as fontlib
from . import registry
from .audit import concept_fingerprint
from .color import info as color_info
from .color import load_tokens, luminance
from .kit import arc, glyph, polyline, rect_centered, ring, rrect_centered, text, union
from .kit import concept as conceptlib
from .kit.mark import Mark
from .output import EXIT_EXTERNAL, CliError
from .paths import ProjectPaths
from .render import Renderer, svg_size, with_size
from .schemas import AuditResult, TerritoriesSpec, TerritoryShapes

SHEET_W, SHEET_H = 2000, 1400
LADDER = (256, 128, 64, 48, 32, 24, 16)
# The one-colour test draws each tier at the size the audit measures it (full-symbol 64 px, small 32 px), falling back as exports do.
ONE_COLOUR = ((64, ("full-symbol", "full-lockup")), (32, ("small", "full-symbol", "full-lockup")))
AUDIT_ROWS = 24  # 16 px text rows per column of the audit box; the template sizes the box to fit them
AUDIT_LINES = 2 * AUDIT_ROWS  # the box has two columns
SHOWN_INFO = ("anchors", "min_feature")  # passing measurements listed after the failures and warnings


def jinja(paths: ProjectPaths) -> Environment:
    return Environment(loader=FileSystemLoader(str(paths.templates)), autoescape=select_autoescape(default=False))


def _render_html(renderer: Renderer | None, html: str, width: int, height: int | None = None) -> bytes:
    """`html` as a PNG through `renderer`, or through a Chrome of its own when None, so a sheet that checks its inputs first
    starts Chrome only once they pass. The whole page when `height` is None, else exactly `width` x `height`."""
    if renderer is None:
        with Renderer() as own:
            return own.html_to_png(html, width, height, full_page=height is None)
    return renderer.html_to_png(html, width, height, full_page=height is None)


def _first_present(outputs: dict, chain: Iterable[str]) -> str:
    """The first output in `chain` that was built, else full-lockup (every build has one): how exports fall back."""
    return next((name for name in chain if name in outputs), "full-lockup")


def pick_output(outputs: dict, size: int) -> str:
    if size >= 96:
        chain = ("full-symbol", "full-lockup")
    elif size > 32:
        chain = ("small", "full-symbol", "full-lockup")
    else:
        chain = ("favicon", "small", "full-symbol", "full-lockup")
    return _first_present(outputs, chain)


def fit_box(svg: str, box_w: int, box_h: int) -> str:
    _, h_at_w = svg_size(svg, box_w)
    if h_at_w <= box_h:
        return with_size(svg, box_w, h_at_w)
    return with_size(svg, max(1, round(box_w * box_h / h_at_w)), box_h)


def next_round(folder: Path) -> int:
    """One past the highest renders/round-N, so a default round never lands on one made earlier with --round."""
    numbers = [p.name.removeprefix("round-") for p in (folder / "renders").glob("round-*") if p.is_dir()]
    return max((int(n) for n in numbers if n.isdecimal()), default=0) + 1


def _one_colour_outputs(outputs: dict) -> list[tuple[int, str]]:
    return [(size, _first_present(outputs, chain)) for size, chain in ONE_COLOUR]


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


def _saved_audit(folder: Path) -> AuditResult | None:
    """<concept>/audit.json if there is one; a file that is not a valid audit is a CliError naming it."""
    path = folder / "audit.json"
    if not path.is_file():
        return None
    try:
        return AuditResult.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as err:  # malformed JSON or the wrong fields
        first = err.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "root"
        raise CliError(f"{path} is not a valid audit ({loc}: {first['msg']}); re-run concept audit") from err
    except ValueError as err:  # bytes that are not UTF-8
        raise CliError(f"{path} is not a valid audit ({err}); re-run concept audit") from err


def _palettes(folder: Path, tokens_path: str | Path | None = None):
    """Light and dark palettes from `tokens_path`, else from <concept>/tokens.json if present, else (None, None).

    A broken tokens file raises load_tokens' CliError, which names the file.
    """
    if not tokens_path:
        tokens_path = folder / "tokens.json"
        if not tokens_path.is_file():
            return None, None
    tokens = load_tokens(Path(tokens_path))
    return tokens.palette("light"), tokens.palette("dark")


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
    lockup = outputs["full-lockup"]
    big = outputs[pick_output(outputs, 256)].to_svg("black")
    ladder = [(size, pick_output(outputs, size)) for size in LADDER]
    panels = {
        "black": fit_box(lockup.to_svg("black"), 512, 512),
        "white": fit_box(lockup.to_svg("white"), 512, 512),
        "color": fit_box(lockup.to_svg("color", palette=light), 384, 384) if light else None,
        "reverse": fit_box(lockup.to_svg("reverse", palette=dark), 384, 384) if dark else None,
        "paper_light": light["paper"] if light else "#ffffff",
        "paper_dark": dark["paper"] if dark else "#000000",
        "ladder": [{"size": s, "output": name, "svg": fit_box(outputs[name].to_svg("black"), s, s)} for s, name in ladder],
        "mirror": fit_box(big, 256, 256),
        "rotate": fit_box(big, 256, 256),
        "one_colour": [{"size": s, "output": name, "svg": fit_box(outputs[name].to_svg("black"), s, s)}
                       for s, name in _one_colour_outputs(outputs)],
    }
    if audit is None:
        audit = _saved_audit(folder)
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


def _chip_text(hex_value: str) -> str:
    """The colour of a label on a `hex_value` swatch: white on a dark colour (luminance under 0.35), else near-black."""
    return "#ffffff" if luminance(hex_value) < 0.35 else "#111111"


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
                            "text": _chip_text(c.hex)})
        cards.append({"name": t.name, "embraces": t.embraces, "rejects": t.rejects, "fonts": fonts, "palette": palette,
                      "shapes": shape_specimens(t.shapes, state.name[:1].upper() or "A", t.fonts[0].family, t.fonts[0].weight)})
    html = jinja(paths).get_template("sheets/territories.html").render(brand=state.name, territories=cards, width=BOARD_W)
    png = _render_html(renderer, html, BOARD_W)
    html_path, png_path = folder / "board.html", folder / "board.png"
    html_path.write_text(html, encoding="utf-8")
    png_path.write_bytes(png)
    warnings: list[str] = []
    open_file(html_path, open_after, warnings)
    return {"board_html": str(html_path), "board_png": str(png_path), "territories": [t.slug for t in spec.territories],
            "warnings": warnings}
