"""The knock-out by image (spec 2026-10-08 §7): the PNGs the skill uploads to Google Lens and the WIPO Global Brand
Database, the knockout.json they are recorded in, and what the gates ask of it."""
from __future__ import annotations

import json

from . import render
from .kit import concept as conceptlib
from .paths import ProjectPaths
from .render import fit_size
from .schemas import Knockout

SKIP_NOTE = "knock-out skipped:"  # the owner's brand decide note that lets a skipped image search pass a gate
MARK_PX, LOCKUP_PX = 512, 1024


def write_images(paths: ProjectPaths, slug: str, concept_name: str, renderer=None) -> dict:
    """Render <concept>/knockout/round-N/mark-512.png (the full symbol, black on white; the full lockup when the concept
    has no symbol, with a warning) and lockup-1024.png (the horizontal lockup), and seed knockout.json when missing."""
    from .sheets import next_round  # imported here: sheets imports registry, which the gates below also import

    folder = conceptlib.concept_folder(paths, slug, concept_name)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(folder)))
    warnings: list[str] = []
    mark_name = conceptlib.pick_output(outputs, MARK_PX)
    if mark_name == "full-lockup":
        warnings.append("no symbol: the mark image shows the full lockup")
    lockup_name = conceptlib.first_present(outputs, ("full-horizontal",))
    round_n = next_round(folder, "knockout/round-*")
    target = folder / "knockout" / f"round-{round_n}"
    renders = {}
    # render.Renderer, looked up at call time, so the tests' no_chrome fixture (which patches render.Renderer) applies here too.
    with (render.Renderer() if renderer is None else _already(renderer)) as chrome:
        for stem, name, box in (("mark-512", mark_name, MARK_PX), ("lockup-1024", lockup_name, LOCKUP_PX)):
            svg = outputs[name].to_svg("black", padding=outputs[name].x_unit)
            renders[stem] = chrome.svg_to_png(svg, *fit_size(svg, box, box), background="#ffffff")
    target.mkdir(parents=True)
    for stem, png in renders.items():
        (target / f"{stem}.png").write_bytes(png)
    record = folder / "knockout.json"
    created = not record.is_file()
    if created:
        record.write_text(json.dumps(Knockout().model_dump(), indent=2) + "\n", encoding="utf-8")
    return {"round": round_n, "mark_png": str(target / "mark-512.png"), "lockup_png": str(target / "lockup-1024.png"),
            "knockout_json": str(record), "created": created, "warnings": warnings}


class _already:
    """A context manager around a renderer that is already open."""

    def __init__(self, renderer):
        self.renderer = renderer

    def __enter__(self):
        return self.renderer

    def __exit__(self, *exc):
        return False
