"""Sheets rendered through Chrome. Part 1: the per-concept critique sheet Claude reads; Part 2 adds owner-facing sheets."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .color import load_tokens
from .kit import concept as conceptlib
from .paths import ProjectPaths
from .render import Renderer, svg_size, with_size
from .schemas import AuditResult

SHEET_W, SHEET_H = 2000, 1400
LADDER = (256, 128, 64, 48, 32, 24, 16)
# The one-colour test draws each tier at the size the audit measures it (full-symbol 64 px, small 32 px), falling back as exports do.
ONE_COLOUR = ((64, ("full-symbol", "full-lockup")), (32, ("small", "full-symbol", "full-lockup")))
AUDIT_ROWS = 24  # 16 px text rows per column of the audit box; the template sizes the box to fit them
AUDIT_LINES = 2 * AUDIT_ROWS  # the box has two columns
SHOWN_INFO = ("anchors", "min_feature")  # passing measurements listed after the failures and warnings


def jinja(paths: ProjectPaths) -> Environment:
    return Environment(loader=FileSystemLoader(str(paths.templates)), autoescape=select_autoescape(default=False))


def pick_output(outputs: dict, size: int) -> str:
    if size >= 96:
        order = ("full-symbol", "full-lockup")
    elif size > 32:
        order = ("small", "full-symbol", "full-lockup")
    else:
        order = ("favicon", "small", "full-symbol", "full-lockup")
    return next((name for name in order if name in outputs), "full-lockup")


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
    return [(size, next((name for name in chain if name in outputs), "full-lockup")) for size, chain in ONE_COLOUR]


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
                   renderer: Renderer | None = None, audit: AuditResult | None = None, tokens_path: str | Path | None = None) -> dict:
    """Write <concept>/renders/round-N/critique.{html,png}.

    `audit` defaults to the concept's audit.json, if there is one, and `tokens_path` (for the colour panels) to its tokens.json.
    """
    folder = conceptlib.concept_folder(paths, slug, concept_name)
    module = conceptlib.load_concept(folder)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
    light, dark = _palettes(folder, tokens_path)
    round_n = round_n or next_round(folder)
    lockup = outputs["full-lockup"]
    big = outputs[pick_output(outputs, 256)].to_svg("black")
    panels = {
        "black": fit_box(lockup.to_svg("black"), 512, 512),
        "white": fit_box(lockup.to_svg("white"), 512, 512),
        "color": fit_box(lockup.to_svg("color", palette=light), 384, 384) if light else None,
        "reverse": fit_box(lockup.to_svg("reverse", palette=dark), 384, 384) if dark else None,
        "paper_light": light["paper"] if light else "#ffffff",
        "paper_dark": dark["paper"] if dark else "#000000",
        "ladder": [{"size": s, "output": pick_output(outputs, s), "svg": fit_box(outputs[pick_output(outputs, s)].to_svg("black"), s, s)} for s in LADDER],
        "mirror": fit_box(big, 256, 256),
        "rotate": fit_box(big, 256, 256),
        "one_colour": [{"size": s, "output": name, "svg": fit_box(outputs[name].to_svg("black"), s, s)} for s, name in _one_colour_outputs(outputs)],
    }
    if audit is None and (folder / "audit.json").is_file():
        audit = AuditResult.model_validate_json((folder / "audit.json").read_text(encoding="utf-8"))
    summary = None if audit is None else {"ok": audit.ok, "rendered": audit.rendered, "lines": _audit_lines(audit)}
    html = jinja(paths).get_template("sheets/critique.html").render(
        slug=slug, concept=concept_name, round_n=round_n, idea=module.meta.idea, panels=panels, audit=summary,
        audit_rows=AUDIT_ROWS, width=SHEET_W, height=SHEET_H,
    )
    if renderer is None:
        with Renderer() as own:
            png = own.html_to_png(html, SHEET_W, SHEET_H, full_page=False)
    else:
        png = renderer.html_to_png(html, SHEET_W, SHEET_H, full_page=False)
    # The round folder is made only after the render succeeds, so a failure never leaves a half-written round.
    out_dir = folder / "renders" / f"round-{round_n}"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path, png_path = out_dir / "critique.html", out_dir / "critique.png"
    html_path.write_text(html, encoding="utf-8")
    png_path.write_bytes(png)
    return {"round": round_n, "critique_png": str(png_path), "critique_html": str(html_path)}
