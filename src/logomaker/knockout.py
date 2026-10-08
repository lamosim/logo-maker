"""The knock-out by image (spec 2026-10-08 §7): the PNGs the skill uploads to Google Lens and the WIPO Global Brand
Database, the knockout.json they are recorded in, and what the gates ask of it."""
from __future__ import annotations

import json
from pathlib import Path

from . import registry, render
from .audit import concept_fingerprint
from .kit import concept as conceptlib
from .output import CliError
from .paths import ProjectPaths
from .render import fit_size
from .schemas import Decision, Knockout

SKIP_NOTE = "knock-out skipped:"  # the owner's brand decide note that lets a skipped image search pass a gate
MARK_PX, LOCKUP_PX = 512, 1024


def write_images(paths: ProjectPaths, slug: str, concept_name: str, renderer=None) -> dict:
    """Render <concept>/knockout/round-N/mark-512.png (the full symbol, black on white; the full lockup when the concept
    has no symbol, with a warning) and lockup-1024.png (the horizontal lockup), seed knockout.json when missing, and stamp
    the concept's fingerprint (audit.concept_fingerprint) into it, keeping every other field. When the fingerprint differs
    from the one recorded (or none was), the mark changed since the searches: each search's searched, matches and date
    are reset (a skipped reason, the description queries and the caveat stay), and the result says `reset`."""
    from .sheets import next_round  # imported here: sheets imports registry, which the gates below also import

    folder = conceptlib.concept_folder(paths, slug, concept_name)
    record = folder / "knockout.json"
    created = not record.is_file()
    if created:
        data = Knockout().model_dump()
    else:  # checked before rendering, so a refused record leaves no new round folder
        registry.load_model(record, Knockout, f"{folder.name}/knockout.json")  # refuses an invalid record, untouched
        data = json.loads(record.read_text(encoding="utf-8"))  # the raw record, so fields the model does not know stay
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
    fingerprint = concept_fingerprint(paths, slug, folder)
    reset = data.get("fingerprint", "") != fingerprint
    if reset:
        for key in ("image_matches", "wipo"):
            if isinstance(data.get(key), dict):
                data[key].update(searched=False, matches=[], date="")
    data["fingerprint"] = fingerprint
    record.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"round": round_n, "mark_png": str(target / "mark-512.png"), "lockup_png": str(target / "lockup-1024.png"),
            "knockout_json": str(record), "created": created, "reset": reset, "warnings": warnings}


class _already:
    """A context manager around a renderer that is already open."""

    def __init__(self, renderer):
        self.renderer = renderer

    def __enter__(self):
        return self.renderer

    def __exit__(self, *exc):
        return False


def _owner_skipped(decisions: list[Decision], phase: str) -> bool:
    """Whether the owner recorded a `knock-out skipped:` decision in `phase` (concepts for a survivor, refinement for final/)."""
    return any(d.by == "user" and d.phase.value == phase and d.note.strip().lower().startswith(SKIP_NOTE) for d in decisions)


def _latest_round(folder: Path) -> str:
    """The newest knockout/round-N folder's name, or "round-N" when no images were rendered yet."""
    base = folder / "knockout"
    numbers = sorted(int(p.name[6:]) for p in base.glob("round-*") if p.name[6:].isdigit()) if base.is_dir() else []
    return f"round-{numbers[-1]}" if numbers else "round-N"


def knockout_problems(paths: ProjectPaths, slug: str, folder: Path, label: str | None = None, final: bool = False) -> list[str]:
    """Why <folder>/knockout.json does not record the look-alike searches, or []: missing, invalid, stale (its
    fingerprint is not audit.concept_fingerprint of the concept now, as the critic's staleness check computes it), no
    image knock-out (neither searched nor skipped), skipped without the owner's `knock-out skipped:` decision in the
    phase (concepts; refinement with `final`), or, with `final`, no WIPO search. Each message says what clears it."""
    label = label or f"{folder.name}/knockout.json"
    path = folder / "knockout.json"
    if not path.is_file():
        return [f"{label} is missing (run: logomaker concept knockout {slug} {folder.name}, search by image, record the matches)"]
    try:
        record = registry.load_model(path, Knockout, label)
    except CliError as err:
        return [str(err)]
    rerun = f"logomaker concept knockout {slug} {folder.name}"
    if record.fingerprint != concept_fingerprint(paths, slug, folder):
        return [f"{label} is stale (the mark changed since the search); re-run: {rerun}"]
    latest = _latest_round(folder)
    image = f"knockout/{latest}/mark-512.png"
    state = registry.load_state(paths, slug)
    phase = "refinement" if final else "concepts"
    decide = f'logomaker brand decide {slug} --phase {phase} --by user --note "{SKIP_NOTE} <reason>"'
    lens = f"run Google Lens on {image}" if latest != "round-N" else f"run: {rerun}, then Google Lens on the {image} it writes"
    problems = []
    if not record.image_done:
        problems.append(f"{label} has no image knock-out ({lens} and record the matches, or record skipped with a reason)")
    elif record.image_matches.skipped and not _owner_skipped(state.decisions, phase):
        problems.append(f"{label} records the image knock-out as skipped without the owner's decision (run: {decide})")
    if final:
        if not record.wipo_done:
            problems.append(f"{label} has no WIPO image search (upload {image} to the Global Brand Database and record the matches, "
                            "or record skipped with a reason)")
        elif record.wipo is not None and record.wipo.skipped and not _owner_skipped(state.decisions, phase):
            problems.append(f"{label} records the WIPO search as skipped without the owner's decision (run: {decide})")
    return problems
