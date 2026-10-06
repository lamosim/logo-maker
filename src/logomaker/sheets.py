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


def _palettes(folder: Path):
    """Light and dark palettes from <concept>/tokens.json, or (None, None) without one; a broken file raises CliError naming it."""
    tokens_file = folder / "tokens.json"
    if not tokens_file.is_file():
        return None, None
    tokens = load_tokens(tokens_file)
    return tokens.palette("light"), tokens.palette("dark")


def critique_sheet(paths: ProjectPaths, slug: str, concept_name: str, round_n: int | None = None,
                   renderer: Renderer | None = None, audit: AuditResult | None = None) -> dict:
    """Write <concept>/renders/round-N/critique.{html,png}. `audit` defaults to the concept's audit.json, if there is one."""
    folder = conceptlib.concept_folder(paths, slug, concept_name)
    module = conceptlib.load_concept(folder)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
    light, dark = _palettes(folder)
    round_n = round_n or next_round(folder)
    lockup = outputs["full-lockup"]
    big = outputs[pick_output(outputs, 256)].to_svg("black")
    panels = {
        "black": fit_box(lockup.to_svg("black"), 560, 360),
        "white": fit_box(lockup.to_svg("white"), 560, 360),
        "color": fit_box(lockup.to_svg("color", palette=light), 300, 360) if light else None,
        "reverse": fit_box(lockup.to_svg("reverse", palette=dark), 300, 360) if dark else None,
        "paper_light": light["paper"] if light else "#ffffff",
        "paper_dark": dark["paper"] if dark else "#000000",
        "ladder": [{"size": s, "output": pick_output(outputs, s), "svg": fit_box(outputs[pick_output(outputs, s)].to_svg("black"), s, s)} for s in LADDER],
        "mirror": fit_box(big, 256, 256),
        "rotate": fit_box(big, 256, 256),
        "one_colour": [fit_box(lockup.to_svg("black"), 400, 160), fit_box(lockup.to_svg("black"), 200, 160)],
    }
    if audit is None and (folder / "audit.json").is_file():
        audit = AuditResult.model_validate_json((folder / "audit.json").read_text(encoding="utf-8"))
    summary = None
    if audit is not None:
        summary = {"ok": audit.ok, "rendered": audit.rendered,
                   "failures": [f.message for f in audit.failures][:6], "warnings": [f.message for f in audit.warnings][:6]}
    html = jinja(paths).get_template("sheets/critique.html").render(
        slug=slug, concept=concept_name, round_n=round_n, idea=module.meta.idea, panels=panels, audit=summary, width=SHEET_W, height=SHEET_H,
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
