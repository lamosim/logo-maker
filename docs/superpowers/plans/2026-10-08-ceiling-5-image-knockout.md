# Raising the Ceiling, Plan 5: Knock-out by Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every survivor's look-alike search includes a reverse-image search of the rendered mark, the final mark is also checked against the WIPO Global Brand Database, and the findings are recorded in a validated file the gates read.

**Architecture:** A new `knockout` module renders the mark and the lockup to PNG, seeds `knockout.json`, and tells the gates whether the image searches were recorded or skipped with the owner's decision. The searches themselves run in the skill through the Chrome extension (Google Lens, then the WIPO image search for `final/`). The package fingerprint covers `final/knockout.json` when present.

**Tech Stack:** pydantic 2, the existing `render.Renderer` (`svg_to_png`), click, pytest with the repo's `StubRenderer`.

**Spec:** `docs/superpowers/specs/2026-10-08-raising-the-ceiling-design.md`, section 7 (WS5).

**Prerequisite:** Plan 1 is merged (the gates and the concept sheet's vetting path) and the `baseline` cycle is recorded.

## Global Constraints

- No paid API and no downloaded dataset; Lens and WIPO are web pages driven through the Chrome extension (`mcp__claude-in-chrome__*`), with the trademark caveat from `reference/naming.md` word for word on every report.
- A skipped image search passes a gate only with a `brand decide` note by the owner starting `knock-out skipped:`.
- The Keystone example has no `final/knockout.json`; nothing in `tests/test_example.py` gates it, and `inputs_fingerprint` reads the file only when present, so the example's committed manifest still verifies. Do not add the file to `export_docs.SOURCE_FILES` (a missing source file is a build warning, and the example's render test asserts no warnings).
- Ruff clean; commit per task with the attribution line from the session's system reminder.

## Review Focus

1. A wordmark-only concept (no symbol): `concept knockout` renders the full lockup as the mark image and says so in a warning, never fails. Pinned in Task 2.
2. `knockout.json` with `searched: true` and a `skipped` reason at once: invalid, named in the gate's message. Pinned in Task 1.
3. A skipped search whose `brand decide` note was written by Claude (`--by claude`): still refused; only the owner's note counts. Pinned in Task 3.
4. A final knock-out recorded, then the mark changed: the package fingerprint changes, so `package verify` reports out of date after a build that read the old file. Pinned in Task 3.
5. Running `concept knockout` twice: a second round folder, the existing `knockout.json` untouched. Pinned in Task 2.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/logomaker/schemas.py` (modify) | `ImageMatch`, `ImageSearch`, `DescriptionQuery`, `Knockout` |
| `src/logomaker/knockout.py` (create) | `write_images`, `knockout_problems`, `SKIP_NOTE` |
| `src/logomaker/registry.py` (modify) | `_check_concept`, `_check_final` read the knock-out |
| `src/logomaker/sheets.py` (modify) | `concepts_sheet` refuses a survivor without its image knock-out |
| `src/logomaker/export_docs.py` (modify) | the fingerprint covers `final/knockout.json` |
| `src/logomaker/cli.py` (modify) | `concept knockout` |
| `.claude/skills/logo/reference/naming.md`, `SKILL.md`, `reference/process.md` (modify) | the procedure |
| `tests/test_knockout.py` (create), `tests/test_export_docs.py`, `tests/test_skill_docs.py` (modify) | tests |

---

### Task 1: The `Knockout` model

**Files:**
- Modify: `src/logomaker/schemas.py`
- Test: `tests/test_knockout.py` (create)

**Interfaces:**
- Produces: `schemas.ImageMatch(url, owner="", note="")`; `schemas.ImageSearch(tool, date="", searched=False, matches=[], skipped=None)`; `schemas.DescriptionQuery(query, date="", findings="")`; `schemas.Knockout(description_queries=[], image_matches=ImageSearch(tool="google-lens"), wipo=None, caveat="")` with `.image_done` and `.wipo_done` properties (searched, or skipped with a reason).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_knockout.py
import pytest
from pydantic import ValidationError

from logomaker.schemas import ImageSearch, Knockout


def test_knockout_template_is_empty_and_not_done():
    empty = Knockout()
    assert empty.image_matches.tool == "google-lens" and not empty.image_done and not empty.wipo_done
    assert empty.model_dump()["wipo"] is None


def test_an_image_search_is_done_when_searched_or_skipped_with_a_reason():
    assert Knockout(image_matches=ImageSearch(tool="google-lens", searched=True, date="2026-10-09")).image_done
    assert Knockout(image_matches=ImageSearch(tool="google-lens", skipped="Chrome extension unavailable")).image_done
    assert not Knockout(image_matches=ImageSearch(tool="google-lens", skipped="")).image_done
    with pytest.raises(ValidationError, match="searched and skipped are exclusive"):
        ImageSearch(tool="google-lens", searched=True, skipped="also skipped")
    assert Knockout(wipo=ImageSearch(tool="wipo", searched=True, matches=[{"url": "https://branddb.wipo.int/x", "note": "an arch"}])).wipo_done
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_knockout.py -q`
Expected: FAIL with `ImportError: cannot import name 'Knockout'`.

- [ ] **Step 3: Add the models**

In `src/logomaker/schemas.py`, after the `Scorecard` and `CriticCard` models:

```python
class ImageMatch(BaseModel):
    url: str
    owner: str = ""
    note: str = ""


class ImageSearch(BaseModel):
    """One reverse-image search of the rendered mark: `tool` google-lens or wipo; `searched` with its `matches`, or
    `skipped` with the reason (the gate then needs the owner's `knock-out skipped:` decision)."""

    tool: str
    date: str = ""
    searched: bool = False
    matches: list[ImageMatch] = Field(default_factory=list)
    skipped: str | None = None

    @model_validator(mode="after")
    def searched_or_skipped(self) -> ImageSearch:
        if self.searched and self.skipped:
            raise ValueError("searched and skipped are exclusive")
        return self

    @property
    def done(self) -> bool:
        return self.searched or bool(self.skipped and self.skipped.strip())


class DescriptionQuery(BaseModel):
    query: str
    date: str = ""
    findings: str = ""


class Knockout(BaseModel):
    """<concept>/knockout.json (spec 2026-10-08 §7): the description searches, the Google Lens search of the rendered
    mark, the WIPO image search (final/ only) and the trademark caveat."""

    description_queries: list[DescriptionQuery] = Field(default_factory=list)
    image_matches: ImageSearch = Field(default_factory=lambda: ImageSearch(tool="google-lens"))
    wipo: ImageSearch | None = None
    caveat: str = ""

    @property
    def image_done(self) -> bool:
        return self.image_matches.done

    @property
    def wipo_done(self) -> bool:
        return self.wipo is not None and self.wipo.done
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_knockout.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/schemas.py tests/test_knockout.py
git commit -m "feat: Knockout model for the look-alike searches"
```

---

### Task 2: `concept knockout` renders the images and seeds the file

**Files:**
- Create: `src/logomaker/knockout.py`
- Modify: `src/logomaker/cli.py`
- Test: `tests/test_knockout.py` (extend)

**Interfaces:**
- Consumes: `kit.concept.concept_folder`, `load_concept`, `build_tiers`, `build_outputs`, `pick_output`, `first_present`; `render.Renderer.svg_to_png`, `render.fit_size`; `sheets.next_round`.
- Produces: `knockout.write_images(paths, slug, concept_name, renderer=None) -> dict` with `round`, `mark_png`, `lockup_png`, `knockout_json`, `created`, `warnings`; files `<folder>/knockout/round-N/mark-512.png` and `lockup-1024.png`; `knockout.json` created from `Knockout()` when missing. CLI: `concept knockout <slug> <concept>`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_knockout.py`:

```python
import json

from click.testing import CliRunner
from PIL import Image

from logomaker import knockout
from logomaker.cli import main
from logomaker.paths import project
from tests.conftest import StubRenderer, install_concept


def run(*args):
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, json.loads(result.stdout)


def test_write_images_renders_the_mark_and_lockup_and_seeds_the_file(project_root):
    folder = install_concept(project_root, "good", name="01-good")
    renderer = StubRenderer()
    info = knockout.write_images(project(), "keystone", "01-good", renderer=renderer)
    assert info["round"] == 1 and info["created"] is True and info["warnings"] == []
    mark = folder / "knockout" / "round-1" / "mark-512.png"
    lockup = folder / "knockout" / "round-1" / "lockup-1024.png"
    assert mark.is_file() and lockup.is_file()
    assert max(Image.open(mark).size) == 512 and max(Image.open(lockup).size) == 1024
    assert all(call[3] == "#ffffff" for call in renderer.calls)  # black on white, for the search engines
    seeded = json.loads((folder / "knockout.json").read_text())
    assert seeded["image_matches"] == {"tool": "google-lens", "date": "", "searched": False, "matches": [], "skipped": None}
    (folder / "knockout.json").write_text(json.dumps({**seeded, "caveat": "kept"}))
    again = knockout.write_images(project(), "keystone", "01-good", renderer=StubRenderer())
    assert again["round"] == 2 and again["created"] is False
    assert json.loads((folder / "knockout.json").read_text())["caveat"] == "kept"


def test_write_images_warns_for_a_wordmark_only_concept(project_root):
    install_concept(project_root, "wordmark_only", name="02-word")
    info = knockout.write_images(project(), "keystone", "02-word", renderer=StubRenderer())
    assert info["warnings"] == ["no symbol: the mark image shows the full lockup"]


def test_concept_knockout_cli_needs_chrome(project_root, no_chrome):
    install_concept(project_root, "good", name="01-good")
    code, payload = run("concept", "knockout", "keystone", "01-good")
    assert code == 2 or code == 3  # NoChrome raises AssertionError inside the command wrapper: exit 2 with a traceback
    assert not (project_root / "brands" / "keystone" / "concepts" / "01-good" / "knockout").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_knockout.py -q`
Expected: FAIL with `ImportError: cannot import name 'knockout'`.

- [ ] **Step 3: Write the module and the command**

```python
# src/logomaker/knockout.py
"""The knock-out by image (spec 2026-10-08 §7): the PNGs the skill uploads to Google Lens and the WIPO Global Brand
Database, the knockout.json they are recorded in, and what the gates ask of it."""
from __future__ import annotations

import json
from pathlib import Path

from . import registry, render
from .kit import concept as conceptlib
from .output import CliError
from .paths import ProjectPaths
from .render import fit_size
from .schemas import Decision, Knockout

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
```

In `src/logomaker/cli.py`, after `concept_critic`:

```python
@concept_group.command("knockout")
@click.argument("slug")
@click.argument("concept")
@command
def concept_knockout(slug: str, concept: str) -> None:
    """Render the knock-out images (mark at 512 px, lockup at 1024 px, black on white) into <concept>/knockout/round-N/ and
    seed knockout.json; the skill then searches by image and records the matches."""
    from . import knockout as knockoutlib

    info = knockoutlib.write_images(project(), slug, concept)
    emit(info, warnings=info.pop("warnings"))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_knockout.py -q`
Expected: all passed. The `StubRenderer` records `(svg, width, height, background)` in `calls`.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/knockout.py src/logomaker/cli.py tests/test_knockout.py
git commit -m "feat: concept knockout renders the search images and seeds knockout.json"
```

---

### Task 3: The gates read the knock-out

**Files:**
- Modify: `src/logomaker/knockout.py` (`knockout_problems`), `src/logomaker/registry.py` (`_check_concept`, `_check_final`), `src/logomaker/sheets.py` (`concepts_sheet`), `src/logomaker/export_docs.py` (`inputs_fingerprint`), `tests/conftest.py` (`make_final_brand`, the concept-sheet `prepare` helper)
- Test: `tests/test_knockout.py`, `tests/test_export_docs.py` (extend)

**Interfaces:**
- Produces: `knockout.knockout_problems(paths, slug, folder, label=None, final=False) -> list[str]`; `knockout.recorded(folder, name) -> None` (a test helper is not needed: tests write the JSON); `export_docs.FINGERPRINT_EXTRA = ("final/knockout.json",)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_knockout.py`:

```python
import pytest

from logomaker import registry, sheets
from logomaker.output import CliError
from tests.conftest import StubChrome, critic_run, make_final_brand, scorecard, write_passing_audit


def recorded(folder, tool: str = "google-lens", wipo: bool = False, skipped: str | None = None) -> None:
    search = {"tool": tool, "date": "2026-10-09", "searched": skipped is None, "matches": [], "skipped": skipped}
    data = {"description_queries": [{"query": "arch logo", "findings": "stock arches"}], "image_matches": search,
            "wipo": {**search, "tool": "wipo"} if wipo else None, "caveat": "These checks are a knock-out only"}
    (folder / "knockout.json").write_text(json.dumps(data))


def test_knockout_problems_for_a_survivor(project_root):
    folder = install_concept(project_root, "good", name="01-good")
    paths = project()
    assert knockout.knockout_problems(paths, "keystone", folder) == [
        "01-good/knockout.json is missing (run: logomaker concept knockout keystone 01-good, search by image, record the matches)"]
    knockout.write_images(paths, "keystone", "01-good", renderer=StubRenderer())
    assert knockout.knockout_problems(paths, "keystone", folder) == [
        "01-good/knockout.json has no image knock-out (run Google Lens on knockout/round-1/mark-512.png and record the matches, "
        "or record skipped with a reason)"]
    recorded(folder)
    assert knockout.knockout_problems(paths, "keystone", folder) == []
    recorded(folder, skipped="the Chrome extension was unavailable")
    assert knockout.knockout_problems(paths, "keystone", folder) == [
        "01-good/knockout.json records the image knock-out as skipped without the owner's decision (run: logomaker brand decide "
        'keystone --phase concepts --by user --note "knock-out skipped: <reason>")']
    registry.decide(paths, "keystone", registry.Phase.concepts, "claude", "knock-out skipped: no Chrome")
    assert knockout.knockout_problems(paths, "keystone", folder)  # Claude's note does not count
    registry.decide(paths, "keystone", registry.Phase.concepts, "user", "knock-out skipped: travelling, no Chrome")
    assert knockout.knockout_problems(paths, "keystone", folder) == []


def test_knockout_problems_for_final_need_wipo(project_root):
    final = make_final_brand(project_root)
    paths = project()
    recorded(final)  # overwrites the one make_final_brand records (Step 4): Lens only, no WIPO
    assert knockout.knockout_problems(paths, "keystone", final, final=True) == [
        "final/knockout.json has no WIPO image search (upload knockout/round-N/mark-512.png to the Global Brand Database and record "
        "the matches, or record skipped with a reason)"]
    recorded(final, wipo=True)
    assert knockout.knockout_problems(paths, "keystone", final, final=True) == []


def test_the_concept_sheet_and_the_gates_read_the_knockout(project_root, no_chrome):
    folder = install_concept(project_root, "good", name="01-good")
    paths = project()
    write_passing_audit(paths, "keystone", folder)
    (folder / "scorecard.json").write_text(json.dumps(scorecard()))
    critic_run(project_root, ["01-good"])
    with pytest.raises(CliError, match="concept 01-good: 01-good/knockout.json is missing"):
        sheets.concepts_sheet(paths, "keystone", ["01-good"], open_after=False)
    recorded(folder)
    with pytest.raises(AssertionError, match="Chrome started"):  # every check passed; the render is next
        sheets.concepts_sheet(paths, "keystone", ["01-good"], open_after=False)


def test_advance_to_package_needs_the_final_knockout(project_root):
    final = make_final_brand(project_root)
    paths = project()
    (final / "knockout.json").unlink()  # Step 4 below teaches make_final_brand to record one; this test checks the gate
    with pytest.raises(CliError) as err:
        registry.advance(paths, "keystone", registry.Phase.package)
    assert any("final/knockout.json is missing" in m for m in err.value.data["missing"])
    recorded(final, wipo=True)
    assert registry.advance(paths, "keystone", registry.Phase.package).phase == registry.Phase.package
```

Append to `tests/test_export_docs.py`:

```python
def test_inputs_fingerprint_covers_the_final_knockout_when_present(project_root):
    from logomaker.export_docs import inputs_fingerprint

    final = make_final_brand(project_root)
    before = inputs_fingerprint(project(), "keystone")
    (final / "knockout.json").write_text('{"caveat": "x"}')
    assert inputs_fingerprint(project(), "keystone") != before
```

(`make_final_brand` is imported at the top of that file already, or add it.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_knockout.py tests/test_export_docs.py -q -k "problems or gates or package or fingerprint"`
Expected: FAIL with `AttributeError: module 'logomaker.knockout' has no attribute 'knockout_problems'`.

- [ ] **Step 3: Write `knockout_problems`**

Append to `src/logomaker/knockout.py`:

```python
def _owner_skipped(decisions: list[Decision]) -> bool:
    return any(d.by == "user" and d.note.strip().lower().startswith(SKIP_NOTE) for d in decisions)


def _latest_round(folder: Path) -> str:
    rounds = sorted((p.name for p in (folder / "knockout").glob("round-*")), key=lambda n: int(n.split("-")[1])) if (folder / "knockout").is_dir() else []
    return rounds[-1] if rounds else "round-N"


def knockout_problems(paths: ProjectPaths, slug: str, folder: Path, label: str | None = None, final: bool = False) -> list[str]:
    """Why <folder>/knockout.json does not record the look-alike searches, or []: missing, invalid, no image knock-out
    (neither searched nor skipped), skipped without the owner's `knock-out skipped:` decision, or, with `final`, no WIPO
    search. Each message says what clears it."""
    label = label or f"{folder.name}/knockout.json"
    name = "final" if folder.name == "final" else folder.name
    path = folder / "knockout.json"
    if not path.is_file():
        return [f"{label} is missing (run: logomaker concept knockout {slug} {name}, search by image, record the matches)"]
    try:
        record = registry.load_model(path, Knockout, label)
    except CliError as err:
        return [str(err)]
    image = f"knockout/{_latest_round(folder)}/mark-512.png"
    state = registry.load_state(paths, slug)
    phase = "refinement" if final else "concepts"
    decide = f'logomaker brand decide {slug} --phase {phase} --by user --note "{SKIP_NOTE} <reason>"'
    problems = []
    if not record.image_done:
        problems.append(f"{label} has no image knock-out (run Google Lens on {image} and record the matches, or record skipped with a reason)")
    elif record.image_matches.skipped and not _owner_skipped(state.decisions):
        problems.append(f"{label} records the image knock-out as skipped without the owner's decision (run: {decide})")
    if final:
        if not record.wipo_done:
            problems.append(f"{label} has no WIPO image search (upload {image} to the Global Brand Database and record the matches, "
                            "or record skipped with a reason)")
        elif record.wipo is not None and record.wipo.skipped and not _owner_skipped(state.decisions):
            problems.append(f"{label} records the WIPO search as skipped without the owner's decision (run: {decide})")
    return problems
```

Note `_latest_round` must give `round-N` when no images were rendered yet; the final test expects `round-N` because `make_final_brand` renders none.

- [ ] **Step 4: Wire the gates**

In `registry.py`:

- `_check_concept`, when `current`, after the scorecard check: `missing += knockout_problems(paths, state.slug, folder)` (import inside the function: `from .knockout import knockout_problems`, since `knockout` imports `registry`).
- `_check_final`: after the critic problems, when they are empty: `return final_critic_problems(...) or knockout_problems(paths, state.slug, final, "final/knockout.json", final=True)`.

In `sheets.concepts_sheet`, inside the per-concept vetting loop after the critic check:

```python
        problems = knockout_problems(paths, slug, folder)
        if problems:
            raise CliError(f"concept {name}: {'; '.join(problems)}")
```

In `export_docs.py`:

```python
FINGERPRINT_EXTRA = ("final/knockout.json",)  # read by the build's documents when present; never a copied source file
```

and in `inputs_fingerprint`, extend `files` with `FINGERPRINT_EXTRA` (still "each when present").

Then update the test helpers so existing tests keep passing: in `tests/conftest.py`, `make_final_brand` writes a recorded knock-out (the `recorded` helper above, moved into conftest with `wipo=True`) for `01-good` and for `final/` before advancing; `tests/test_concepts_sheet.py`'s `prepare` records one for each concept it prepares. Run the whole fast suite and fix every setup the new gates refuse, in the tests.

- [ ] **Step 5: Run the suites**

Run: `uv run pytest -m "not render and not live" -q && uv run ruff check src tests`
Expected: all passed, ruff clean. `tests/test_example.py::test_example_package_matches_its_manifest_and_the_brand_now` still passes because the example has no `final/knockout.json`.

- [ ] **Step 6: Commit**

```bash
git add src/logomaker tests
git commit -m "feat: the concept sheet and the gates need the image knock-out; the package fingerprint covers it"
```

---

### Task 4: The procedure in the skill

**Files:**
- Modify: `.claude/skills/logo/reference/naming.md`, `.claude/skills/logo/SKILL.md`, `.claude/skills/logo/reference/process.md`
- Test: `tests/test_skill_docs.py` (extend), `tests/test_knowledge.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_skill_docs.py`:

```python
def test_skill_pins_the_knockout_by_image():
    text = flat(SKILL.read_text(encoding="utf-8"))
    assert "uv run logomaker concept knockout <slug> <NN-slug>" in text and "Google Lens" in text
    assert "uv run logomaker concept knockout <slug> final" in text and "WIPO Global Brand Database" in text
    assert "knock-out skipped:" in text
    naming = (REF / "naming.md").read_text(encoding="utf-8")
    assert "## Knock-out by image" in naming and "lens.google.com" in naming and "branddb.wipo.int" in naming
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_skill_docs.py -q -k knockout`
Expected: FAIL on the first assertion.

- [ ] **Step 3: Write the procedure**

naming.md, a new section `## Knock-out by image` before `## Trademark caveat`:

```markdown
## Knock-out by image

A description search finds marks that are named like yours; a reverse-image search finds marks that look like yours [spec 2026-10-08 §7]. For every survivor before the concept sheet, and for `final/` before the package:

1. `uv run logomaker concept knockout <slug> <NN-slug>` (or `final`) writes `knockout/round-N/mark-512.png` and `lockup-1024.png`, black on white, and seeds `knockout.json` [code].
2. Load the Chrome tools in one ToolSearch call (`mcp__claude-in-chrome__tabs_context_mcp`, `navigate`, `tabs_create_mcp`, `file_upload`, `get_page_text`, `find`, `tabs_close_mcp`), open a new tab at `https://lens.google.com/`, upload `mark-512.png`, and read the "Visual matches" list. Record the ten nearest in `knockout.json` under `image_matches.matches` as `{"url", "owner", "note"}`, the note saying what matches (silhouette, construction, both), with `searched: true` and the date. Close the tab.
3. For `final/` only, open `https://branddb.wipo.int/`, choose the image search, upload the same PNG, and record the nearest registered marks the same way under `wipo`, each note naming the Nice class and the status shown.
4. Write the prose into `knockout.md` as before, with the caveat below word for word, and copy the caveat into `knockout.json`'s `caveat`.

When the Chrome extension is unavailable, record `"skipped": "<reason>"` in place of `searched` and tell the owner: the gate accepts a skipped search only after the owner records `uv run logomaker brand decide <slug> --phase <phase> --by user --note "knock-out skipped: <reason>"` [code]. A changed mark means a new round and a new search; `final/knockout.json` is in the package fingerprint, so `package verify` reports a stale one [code].
```

SKILL.md: in the concepts phase's look-alike bullet add "and the knock-out by image (`uv run logomaker concept knockout <slug> <NN-slug>`, then Google Lens, as `reference/naming.md` says); `sheet concepts` refuses a survivor without it recorded in `knockout.json`". In the refinement knock-out bullet add "`uv run logomaker concept knockout <slug> final`, then Google Lens and the WIPO Global Brand Database image search, recorded in `final/knockout.json`; `brand advance --to package` refuses without both. A skipped search needs the owner's `knock-out skipped:` decision." process.md's `concepts` and `refinement` rows and "Artifacts" list name `knockout.json`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_skill_docs.py tests/test_knowledge.py -q`
Expected: all passed (naming.md stays under 2000 words; trim its examples if the count tips over).

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/logo tests/test_skill_docs.py
git commit -m "docs: the knock-out by image in naming.md and the runbook"
```

---

## Plan 5 is done when

- Fast suite and ruff pass; the example tests still pass.
- A survivor cannot reach the concept sheet, and a brand cannot reach `package`, without its image searches recorded or an owner's skip.
- One real run through Lens on a brand under `brands/` (not the example) has been done by hand and its `knockout.json` validates.
