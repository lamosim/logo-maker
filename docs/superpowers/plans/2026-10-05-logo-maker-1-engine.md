# Logo Maker Part 1: Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `logomaker` CLI core: brand state and registry, the geometry kit with real-font text, SVG output, colour maths, Chrome rendering, automated audits, and the per-concept critique sheet, so that a concept module can be built, audited and rendered end to end.

**Architecture:** A Python package `logomaker` under `src/` exposes a click CLI whose every command prints one JSON object on stdout and exits with 0/2/3/4. Marks are Python concept modules built on `logomaker.kit` (Skia paths, HarfBuzz-shaped fontTools outlines), serialised to paths-only SVG, rendered through the installed Google Chrome via Playwright, and audited by geometry checks plus raster erosion tests. Parts 2 and 3 (separate plans) add owner-facing sheets, the export package, naming checks, the skill and the knowledge base.

**Tech Stack:** Python 3.12 via uv; click, pydantic v2, skia-python, fonttools, uharfbuzz, coloraide, playwright (channel chrome), pillow, numpy, scipy, jinja2, httpx; pytest with `render` and `live` markers.

**Spec:** `docs/superpowers/specs/2026-10-05-logo-maker-design.md` (sections 5, 6, 7.1, 7.2, 8, 10, 13, 14, 15). Research the kit and audit rules come from: `docs/research/04-ai-generation-sota.md` (sections 1.2, 1.3, 4) and `docs/research/05-trends-strategy-craft.md` (section 5).

## Global Constraints

- `requires-python = ">=3.12,<3.13"`; `.python-version` is `3.12`; everything runs as `uv run logomaker ...` and `uv run pytest`.
- Every CLI command prints exactly one JSON object on stdout with at least `{"ok": bool, "errors": [], "warnings": []}`; logs go to stderr. Exit codes: 0 ok; 2 input or rule violation; 3 external failure (Chrome, network, missing font); 4 render or export verification failure.
- Rendering uses the installed Google Chrome at `/Applications/Google Chrome.app` through Playwright with `channel="chrome"`. Never run `playwright install`.
- Symbol canvas is 1000 by 1000 units, origin at the centre, y up in the kit and flipped on SVG output. `snap` rounds to 0.25 units; `snap_angle` rounds to 15 degrees; `free=True` opts out and is counted.
- SVG output is paths only: artwork-fitted `viewBox`, no `width` or `height`, groups `#symbol`, `#wordmark`, `#tagline`, cubic Béziers and lines only, two-decimal precision, `fill-rule="nonzero"`, `mono` variant uses `fill="currentColor"`.
- Builds are deterministic: same parameters, same SVG bytes.
- Every command finishes within 60 seconds except `package build` and `fonts fetch`.
- `.claude/settings.json` denies `Read(./.env)` and `Read(./.env.*)`.
- Commit after every task on branch `main` with a message in the form `feat: ...`, `test: ...` or `chore: ...`, ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. A concept module that raises, or returns a `Mark` whose symbol is empty: `concept build` must exit 2 with the traceback text in `errors`, never a Python stack dump on stderr alone. Pinned in Task 7.
2. A brand name with spaces, accents or capitals (`brand new "Café Nuit"`) must become slug `cafe-nuit`, and a second `brand new` with the same slug must exit 2. Pinned in Task 2.
3. A wordmark family that is not cached (`text("X", family="Sora")` before `fonts fetch Sora`) must exit 3 with the message `run: logomaker fonts fetch Sora`. Pinned in Task 6.
4. Chrome missing from `/Applications` must exit 3 from any render command, not hang. Pinned in Task 9.
5. Path numbers that are tiny or negative zero (`-0.004`, `1e-05`) must serialise as `0`, never in scientific notation or as `-0`. Pinned in Task 3.

---

## File Structure (this part)

| File | Responsibility |
|---|---|
| `pyproject.toml`, `.python-version`, `README.md` | project definition, console script, pytest markers |
| `.claude/settings.json` | deny `.env` reads |
| `src/logomaker/__init__.py` | version string |
| `src/logomaker/output.py` | `emit`, `log`, `CliError`, exit-code constants |
| `src/logomaker/paths.py` | project root discovery, standard folders |
| `src/logomaker/cli.py` | click groups and commands; wraps every command with error handling |
| `src/logomaker/schemas.py` | pydantic models: `Phase`, `BrandState`, `Brief`, `Strategy`, `AuditResult` |
| `src/logomaker/registry.py` | brand state machine, registry index, prerequisites |
| `src/logomaker/kit/shape.py` | `Box`, `Shape` over `skia.Path`: bounds, area, centroid, commands, path data |
| `src/logomaker/kit/primitives.py` | snapping and primitive shapes |
| `src/logomaker/kit/ops.py` | booleans, stroke, offset, transforms, align, fit |
| `src/logomaker/kit/optical.py` | overshoot, stroke compensation, optical centre |
| `src/logomaker/kit/text.py` | `TextShape`, `text`, `glyph` (HarfBuzz + fontTools) |
| `src/logomaker/kit/mark.py` | `Composite`, `Mark`, lockup layout, SVG and geometry output |
| `src/logomaker/kit/concept.py` | `Meta`, `Params`, concept module loading, tier builds, build output |
| `src/logomaker/kit/__init__.py` | re-exports for `from logomaker.kit import *` |
| `src/logomaker/fonts.py` | catalogue, cache, resolution, fetch |
| `scripts/build_catalog.py` | generates `assets/fonts/catalog.json` |
| `src/logomaker/color.py` | conversions, WCAG, APCA, CVD, ramps, `Tokens`, `check_tokens` |
| `src/logomaker/render.py` | `Renderer` (Chrome), `check_chrome` |
| `src/logomaker/raster.py` | masks, components, erosion-based minimum feature |
| `src/logomaker/audit.py` | all audit checks, `audit_concept` |
| `assets/cliches.json` | industry cliché blacklist used by the audit |
| `src/logomaker/sheets.py` | critique sheet (this part) |
| `templates/sheets/critique.html` | critique sheet template |
| `tests/` | one test module per source module; fixtures under `tests/fixtures/` |

Working directory for every command below: `/Users/ian/Documents/Nerd-Projects/logo-maker`.

---

### Task 1: Project scaffold, JSON output helpers, `setup --check`

**Files:**
- Create: `pyproject.toml`, `.python-version`, `README.md`, `.claude/settings.json`
- Create: `src/logomaker/__init__.py`, `src/logomaker/output.py`, `src/logomaker/paths.py`, `src/logomaker/cli.py`
- Create: `tests/conftest.py`, `tests/test_output.py`, `tests/test_paths.py`, `tests/test_cli_setup.py`

**Interfaces:**
- Produces: `output.emit(data=None, *, ok=True, errors=(), warnings=(), code=0) -> NoReturn`; `output.CliError(message, code=2, data=None)`; constants `EXIT_OK=0, EXIT_RULE=2, EXIT_EXTERNAL=3, EXIT_VERIFY=4`; `paths.find_root(start=None) -> Path`; `paths.project(root=None) -> ProjectPaths` with attributes `root, brands, registry, assets, fonts, templates, cliches` and method `brand(slug) -> Path`; `cli.main` click group; `cli.command` decorator that converts exceptions to JSON exits.

- [ ] **Step 1: Create the project definition files**

`pyproject.toml`:

```toml
[project]
name = "logomaker"
version = "0.1.0"
description = "Constructed-vector logo generator CLI for the Claude Code logo skill"
readme = "README.md"
requires-python = ">=3.12,<3.13"
dependencies = [
    "click>=8.1",
    "coloraide>=8.0",
    "fonttools>=4.66",
    "httpx>=0.28",
    "jinja2>=3.1",
    "numpy>=2.0",
    "pillow>=12.0",
    "playwright>=1.63",
    "pydantic>=2.8",
    "pypdf>=6.0",
    "reportlab>=4.0",
    "scipy>=1.14",
    "skia-python>=144.0",
    "uharfbuzz>=0.50",
]

[project.scripts]
logomaker = "logomaker.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/logomaker"]

[tool.logomaker]
root = true

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "render: renders through the installed Google Chrome (skipped when Chrome is missing)",
    "live: needs the network (font fetch, RDAP); kept out of the fast suite",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "ruff>=0.6",
]
```

`.python-version`:

```
3.12
```

`README.md` (expanded in Part 3):

```markdown
# logo-maker

A Claude Code driven logo generator. Open a terminal here, run `claude`, and the `logo` skill guides you from a venture to a production-ready logo package. The `logomaker` CLI (Python, run with uv) does every deterministic step.

Setup: `uv sync` then `uv run logomaker setup --check`.
```

`.claude/settings.json`:

```json
{
  "permissions": {
    "deny": ["Read(./.env)", "Read(./.env.*)"]
  }
}
```

- [ ] **Step 2: Install dependencies**

Run: `uv sync`
Expected: a `.venv` is created and `uv run python -c "import skia, fontTools, uharfbuzz, coloraide, reportlab, playwright, PIL, numpy, scipy, click, pydantic, jinja2, httpx"` prints nothing and exits 0.

- [ ] **Step 3: Write the failing tests for output helpers and paths**

`tests/conftest.py`:

```python
import os
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures"


@pytest.fixture
def project_root(tmp_path: Path, monkeypatch) -> Path:
    """A throwaway logo-maker project: marker pyproject, assets, templates, fixture fonts."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "x"\n\n[tool.logomaker]\nroot = true\n')
    for sub in ("brands", "registry", "assets/fonts", "templates"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    if (REPO / "templates").exists():
        shutil.copytree(REPO / "templates", root / "templates", dirs_exist_ok=True)
    if (REPO / "assets").exists():
        shutil.copytree(REPO / "assets", root / "assets", dirs_exist_ok=True)
    fixture_fonts = FIXTURES / "fonts"
    if fixture_fonts.exists():
        shutil.copytree(fixture_fonts, root / "assets" / "fonts", dirs_exist_ok=True)
    monkeypatch.setenv("LOGOMAKER_ROOT", str(root))
    monkeypatch.chdir(root)
    return root
```

`tests/test_output.py`:

```python
import json

import pytest

from logomaker.output import EXIT_EXTERNAL, EXIT_OK, EXIT_RULE, CliError, emit


def test_emit_prints_one_json_object_and_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        emit({"value": 1}, warnings=["w"])
    assert exc.value.code == EXIT_OK
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload == {"ok": True, "errors": [], "warnings": ["w"], "value": 1}
    assert out.count("\n{") == 0  # a single object


def test_emit_failure_code(capsys):
    with pytest.raises(SystemExit) as exc:
        emit(ok=False, errors=["bad"], code=EXIT_RULE)
    assert exc.value.code == EXIT_RULE
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_error_defaults():
    err = CliError("nope")
    assert err.code == EXIT_RULE and str(err) == "nope" and err.data == {}
    assert CliError("down", code=EXIT_EXTERNAL).code == EXIT_EXTERNAL
```

`tests/test_paths.py`:

```python
import pytest

from logomaker.output import CliError
from logomaker.paths import find_root, project


def test_find_root_uses_env_and_marker(project_root):
    assert find_root() == project_root
    assert project().brands == project_root / "brands"
    assert project().brand("acme") == project_root / "brands" / "acme"
    assert project().cliches == project_root / "assets" / "cliches.json"


def test_find_root_walks_up_without_env(project_root, monkeypatch):
    monkeypatch.delenv("LOGOMAKER_ROOT")
    nested = project_root / "brands" / "deep"
    nested.mkdir(parents=True)
    assert find_root(nested) == project_root


def test_find_root_fails_outside_project(tmp_path, monkeypatch):
    monkeypatch.delenv("LOGOMAKER_ROOT", raising=False)
    with pytest.raises(CliError) as exc:
        find_root(tmp_path)
    assert exc.value.code == 2
```

`tests/test_cli_setup.py`:

```python
import json

from click.testing import CliRunner

from logomaker.cli import main


def test_setup_check_reports_components(project_root):
    result = CliRunner().invoke(main, ["setup", "--check"])
    payload = json.loads(result.output)
    assert set(payload) >= {"ok", "errors", "warnings", "python", "chrome", "modules"}
    assert payload["python"].startswith("3.12")
    assert "skia" in payload["modules"]
    assert isinstance(payload["chrome"]["found"], bool)


def test_setup_creates_folders(project_root):
    (project_root / "brands").rmdir()
    result = CliRunner().invoke(main, ["setup"])
    assert result.exit_code == 0, result.output
    assert (project_root / "brands").is_dir()
    assert (project_root / "registry").is_dir()
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run pytest tests/test_output.py tests/test_paths.py tests/test_cli_setup.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker'` (or import errors for `output`, `paths`, `cli`).

- [ ] **Step 5: Write the package, output helpers, paths and CLI skeleton**

`src/logomaker/__init__.py`:

```python
__version__ = "0.1.0"
FEATURE_IMAGE_MODELS = False  # image-model integrations are out of scope for this version; this gates nothing yet
```

`src/logomaker/output.py`:

```python
"""JSON stdout contract shared by every CLI command."""
from __future__ import annotations

import json
import sys
from typing import Any, Iterable, NoReturn

EXIT_OK = 0
EXIT_RULE = 2
EXIT_EXTERNAL = 3
EXIT_VERIFY = 4


class CliError(Exception):
    """An error the CLI reports as JSON. `code` is the process exit code."""

    def __init__(self, message: str, code: int = EXIT_RULE, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.data = data or {}


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def emit(
    data: dict[str, Any] | None = None,
    *,
    ok: bool = True,
    errors: Iterable[str] = (),
    warnings: Iterable[str] = (),
    code: int = EXIT_OK,
) -> NoReturn:
    payload: dict[str, Any] = {"ok": ok, "errors": list(errors), "warnings": list(warnings)}
    payload.update(data or {})
    sys.stdout.write(json.dumps(payload, indent=2, default=str) + "\n")
    sys.stdout.flush()
    sys.exit(code)
```

`src/logomaker/paths.py`:

```python
"""Where things live. The project root is the folder whose pyproject.toml has [tool.logomaker]."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .output import CliError

MARKER = "[tool.logomaker]"


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def brands(self) -> Path:
        return self.root / "brands"

    @property
    def registry(self) -> Path:
        return self.root / "registry"

    @property
    def assets(self) -> Path:
        return self.root / "assets"

    @property
    def fonts(self) -> Path:
        return self.assets / "fonts"

    @property
    def templates(self) -> Path:
        return self.root / "templates"

    @property
    def cliches(self) -> Path:
        return self.assets / "cliches.json"

    def brand(self, slug: str) -> Path:
        return self.brands / slug


def find_root(start: Path | None = None) -> Path:
    env = os.environ.get("LOGOMAKER_ROOT")
    if env:
        return Path(env).resolve()
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        py = candidate / "pyproject.toml"
        if py.is_file() and MARKER in py.read_text(encoding="utf-8"):
            return candidate
    raise CliError("Not inside a logo-maker project (no pyproject.toml with [tool.logomaker] above the current folder)")


def project(root: Path | None = None) -> ProjectPaths:
    return ProjectPaths(root=root.resolve() if root else find_root())
```

`src/logomaker/cli.py`:

```python
"""Click entry points. Every command ends in output.emit()."""
from __future__ import annotations

import functools
import importlib
import platform
import subprocess
import sys
import traceback

import click

from . import __version__
from .output import EXIT_EXTERNAL, EXIT_RULE, CliError, emit
from .paths import project

CHROME_APP = "/Applications/Google Chrome.app"
CHROME_BIN = CHROME_APP + "/Contents/MacOS/Google Chrome"
MODULES = ["skia", "fontTools", "uharfbuzz", "coloraide", "reportlab", "playwright", "PIL", "numpy", "scipy", "jinja2", "httpx", "pydantic"]


def command(fn):
    """Wrap a command so every exception becomes a JSON failure with the right exit code."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except SystemExit:
            raise
        except CliError as err:
            emit(err.data, ok=False, errors=[str(err)], code=err.code)
        except Exception as err:  # noqa: BLE001 - the CLI contract is JSON, never a traceback
            emit({"traceback": traceback.format_exc()}, ok=False, errors=[f"{type(err).__name__}: {err}"], code=EXIT_RULE)

    return wrapper


@click.group()
@click.version_option(__version__)
def main() -> None:
    """logomaker: deterministic steps for the Claude Code logo skill."""


def chrome_status() -> dict:
    import os

    found = os.path.isfile(CHROME_BIN)
    version = None
    if found:
        try:
            out = subprocess.run([CHROME_BIN, "--version"], capture_output=True, text=True, timeout=20)
            version = out.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            version = None
    return {"found": found, "path": CHROME_APP, "version": version}


@main.command("setup")
@click.option("--check", is_flag=True, help="Report status only; create nothing.")
@command
def setup(check: bool) -> None:
    paths = project()
    modules = {}
    for name in MODULES:
        try:
            importlib.import_module(name)
            modules[name] = True
        except Exception:  # noqa: BLE001
            modules[name] = False
    chrome = chrome_status()
    created = []
    if not check:
        for folder in (paths.brands, paths.registry, paths.fonts):
            if not folder.exists():
                folder.mkdir(parents=True)
                created.append(str(folder.relative_to(paths.root)))
    warnings = []
    if not chrome["found"]:
        warnings.append(f"Google Chrome not found at {CHROME_APP}; render commands will exit {EXIT_EXTERNAL}")
    missing = [m for m, ok in modules.items() if not ok]
    if missing:
        warnings.append("missing modules: " + ", ".join(missing) + " (run uv sync)")
    emit(
        {
            "root": str(paths.root),
            "python": platform.python_version(),
            "chrome": chrome,
            "modules": modules,
            "created": created,
        },
        warnings=warnings,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_output.py tests/test_paths.py tests/test_cli_setup.py -q`
Expected: 8 passed.

- [ ] **Step 7: Smoke the real command and commit**

Run: `uv run logomaker setup --check`
Expected: one JSON object with `"ok": true`, `"python": "3.12.x"`, `"chrome": {"found": true, ...}`.

```bash
git add pyproject.toml .python-version README.md .claude/settings.json uv.lock src tests
git commit -m "feat: scaffold logomaker CLI with JSON output contract and setup check

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Schemas, brand state machine, registry, `brand` commands

**Files:**
- Create: `src/logomaker/schemas.py`, `src/logomaker/registry.py`
- Modify: `src/logomaker/cli.py` (add the `brand` group), `tests/conftest.py` (add payload fixtures)
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: `output.CliError`, `output.emit`, `paths.project`, `cli.command`.
- Produces: `schemas.Phase` (enum with values `intake, naming, strategy, territories, concepts, refinement, package, done`), `schemas.PHASE_ORDER`, `schemas.now_iso()`, `schemas.Decision`, `schemas.MinSizes`, `schemas.FontChoice`, `schemas.BrandState`, `schemas.Brief`, `schemas.Strategy` (with `FeatureTargets`, `LadderRung`, `CategoryUniform`, `Archetype`, `Personality`, `AdjectivePair`, `LogoType`); `registry.slugify(name) -> str`, `registry.new_brand(paths, name, slug=None, unnamed=False) -> BrandState`, `registry.load_state(paths, slug) -> BrandState`, `registry.save_state(paths, state) -> None`, `registry.list_brands(paths) -> list[dict]`, `registry.decide(paths, slug, phase, by, note) -> BrandState`, `registry.rename(paths, slug, name) -> BrandState`, `registry.set_fields(paths, slug, **fields) -> BrandState`, `registry.allowed_next(state) -> Phase | None`, `registry.prerequisites(paths, state, target) -> list[str]`, `registry.advance(paths, slug, target) -> BrandState`. CLI: `brand new|list|status|advance|decide|rename|set`.

- [ ] **Step 1: Add payload fixtures to `tests/conftest.py`**

Append to `tests/conftest.py`:

```python
@pytest.fixture
def brief_payload() -> dict:
    return {
        "business": "Keystone sends invoices that get paid faster",
        "audience": "solo consultants",
        "problem": "late payments",
        "one_idea": "the thing that holds everything together",
        "onliness": "the only invoicing tool that nags clients so you don't have to",
        "adjectives": [
            {"adjective": "steady", "not": "boring"},
            {"adjective": "direct", "not": "rude"},
            {"adjective": "warm", "not": "cute"},
        ],
        "persona": "a calm site foreman who is good at follow-up",
        "admired": ["Stripe", "Patagonia"],
        "disliked": ["generic fintech blue"],
        "surfaces": ["app icon", "website header", "social avatar"],
        "harshest": "16 px favicon and one-colour embroidery",
        "colours_wanted": ["ember orange"],
        "colours_forbidden": ["fintech blue"],
        "colours_category": ["blue", "green"],
        "off_limits": ["upward arrows", "shields"],
        "cultural": "",
        "needs_name": False,
        "name": "Keystone",
        "name_written": "Keystone",
        "name_story": "the stone that locks an arch",
        "tagline": None,
        "archetype": {"primary": "Everyman", "secondary": "Caregiver"},
        "personality": {"sincerity": 0.8, "excitement": 0.3, "competence": 0.8, "sophistication": 0.3, "ruggedness": 0.5},
        "industry": "fintech",
    }


@pytest.fixture
def strategy_payload() -> dict:
    return {
        "onliness": "the only invoicing tool that nags clients so you don't have to",
        "positioning": "For solo consultants who hate chasing money, Keystone is invoicing that follows up by itself.",
        "archetype": {"primary": "Everyman", "secondary": "Caregiver"},
        "personality": {"sincerity": 0.8, "excitement": 0.3, "competence": 0.8, "sophistication": 0.3, "ruggedness": 0.5},
        "one_idea": "the piece that holds the arch",
        "ladder": [
            {"adjective": "steady", "principle": "level baselines, grounded forms", "test": "no element tilts; bottom edge is flat"},
            {"adjective": "direct", "principle": "one dominant silhouette", "test": "drawable from memory in 5 strokes"},
            {"adjective": "warm", "principle": "rounded outer corners, warm hue", "test": "corner radius >= 4% of symbol height"},
        ],
        "category_uniform": {"type_classes": ["geometric sans"], "colours": ["blue"], "motifs": ["upward arrow", "shield", "coin"], "competitors": ["FreshBooks", "Wave", "Bonsai", "HoneyBook", "Invoice Ninja"]},
        "targets": {"shape": 0.4, "symmetry": 0.8, "complexity": "low", "weight": "heavy", "hue_family": "orange", "saturation": "medium", "lightness": "mid", "typeface_class": "grotesk", "frame": "open", "dynamism": 0.2, "descriptive_cue": True, "name_sound": "back vowel 'o', hard stops: heavy, round-ish"},
        "logo_type": "combination",
        "logo_type_reason": "new brand with a short distinctive name",
        "constraints": {"min_lockup_px": 120, "one_colour": True},
    }
```

- [ ] **Step 2: Write the failing tests**

`tests/test_registry.py`:

```python
import json

import pytest
from click.testing import CliRunner

from logomaker import registry
from logomaker.cli import main
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.schemas import Phase


def run(*args):
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, json.loads(result.output)


def test_slugify():
    assert registry.slugify("Café Nuit") == "cafe-nuit"
    assert registry.slugify("  Acme Co. ") == "acme-co"
    with pytest.raises(CliError):
        registry.slugify("!!!")


def test_new_brand_creates_structure_and_registry(project_root):
    state = registry.new_brand(project(), "Café Nuit")
    assert state.slug == "cafe-nuit" and state.phase == Phase.intake and state.needs_name is False
    brand = project_root / "brands" / "cafe-nuit"
    for sub in ("inspiration", "territories", "concepts", "sheets", "final", "package"):
        assert (brand / sub).is_dir()
    saved = json.loads((brand / "brand.json").read_text())
    assert saved["name"] == "Café Nuit"
    reg = json.loads((project_root / "registry" / "brands.json").read_text())
    assert reg["brands"][0]["slug"] == "cafe-nuit"
    assert "cafe-nuit" in (project_root / "registry" / "INDEX.md").read_text()


def test_duplicate_brand_exits_2(project_root):
    assert run("brand", "new", "Keystone")[0] == 0
    code, payload = run("brand", "new", "Keystone")
    assert code == 2 and payload["ok"] is False and "exists" in payload["errors"][0]


def test_advance_refuses_without_brief(project_root):
    run("brand", "new", "Keystone")
    code, payload = run("brand", "advance", "keystone", "--to", "strategy")
    assert code == 2
    assert any("brief.json" in m for m in payload["missing"])


def write_brief(project_root, slug, payload):
    brand = project_root / "brands" / slug
    (brand / "brief.md").write_text("# Brief\n")
    (brand / "brief.json").write_text(json.dumps(payload))


def test_advance_to_strategy_with_valid_brief(project_root, brief_payload):
    run("brand", "new", "Keystone")
    write_brief(project_root, "keystone", brief_payload)
    code, payload = run("brand", "advance", "keystone", "--to", "strategy")
    assert code == 0, payload
    assert payload["brand"]["phase"] == "strategy"


def test_invalid_brief_is_reported(project_root, brief_payload):
    run("brand", "new", "Keystone")
    brief_payload["adjectives"] = []
    write_brief(project_root, "keystone", brief_payload)
    code, payload = run("brand", "advance", "keystone", "--to", "strategy")
    assert code == 2 and any("adjectives" in m for m in payload["missing"])


def test_unnamed_brand_must_be_named_before_strategy(project_root, brief_payload):
    run("brand", "new", "Working Title", "--unnamed")
    brief_payload["needs_name"] = True
    brief_payload["name"] = None
    write_brief(project_root, "working-title", brief_payload)
    code, payload = run("brand", "advance", "working-title", "--to", "strategy")
    assert code == 2 and any("naming" in m for m in payload["missing"])
    code, payload = run("brand", "advance", "working-title", "--to", "naming")
    assert code == 0
    code, payload = run("brand", "advance", "working-title", "--to", "strategy")
    assert code == 2 and any("needs a name" in m for m in payload["missing"])
    code, payload = run("brand", "rename", "working-title", "--name", "Keystone")
    assert code == 0 and payload["brand"]["name"] == "Keystone" and payload["brand"]["needs_name"] is False
    code, payload = run("brand", "advance", "working-title", "--to", "strategy")
    assert code == 0 and payload["brand"]["slug"] == "working-title"


def test_decide_appends_and_status_reports_next(project_root):
    run("brand", "new", "Keystone")
    code, payload = run("brand", "decide", "keystone", "--phase", "intake", "--by", "user", "--note", "likes orange")
    assert code == 0 and payload["brand"]["decisions"][0]["note"] == "likes orange"
    code, payload = run("brand", "status", "keystone")
    assert payload["next"] == "strategy" and any("brief" in m for m in payload["missing"])


def test_set_updates_fields(project_root):
    run("brand", "new", "Keystone")
    code, payload = run(
        "brand", "set", "keystone", "--territory", "forge", "--industry", "fintech",
        "--primary-lockup", "stacked", "--surface", "app icon", "--surface", "merch", "--font", "wordmark=Sora:650",
    )
    assert code == 0, payload
    b = payload["brand"]
    assert b["territory"] == "forge" and b["industry"] == "fintech" and b["primary_lockup"] == "stacked"
    assert b["surfaces"] == ["app icon", "merch"] and b["fonts"]["wordmark"] == {"family": "Sora", "weight": 650, "italic": False}


def test_list_brands(project_root):
    run("brand", "new", "Keystone")
    run("brand", "new", "Quill")
    code, payload = run("brand", "list")
    assert [b["slug"] for b in payload["brands"]] == ["keystone", "quill"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_registry.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker.registry'`.

- [ ] **Step 4: Write the schemas**

`src/logomaker/schemas.py`:

```python
"""Pydantic models for brand state, brief and strategy. Audit and token models are added by later tasks."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Phase(str, Enum):
    intake = "intake"
    naming = "naming"
    strategy = "strategy"
    territories = "territories"
    concepts = "concepts"
    refinement = "refinement"
    package = "package"
    done = "done"


PHASE_ORDER: list[Phase] = list(Phase)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Decision(BaseModel):
    at: str = Field(default_factory=now_iso)
    phase: Phase
    by: Literal["user", "claude"]
    note: str


class MinSizes(BaseModel):
    horizontal_px: int = 120
    stacked_px: int = 160
    mark_px: int = 24
    favicon_px: int = 16
    horizontal_mm: float = 25
    stacked_mm: float = 25
    mark_mm: float = 6


class FontChoice(BaseModel):
    family: str
    weight: int = 400
    italic: bool = False


class BrandState(BaseModel):
    slug: str
    name: str
    needs_name: bool = False
    created: str = Field(default_factory=now_iso)
    updated: str = Field(default_factory=now_iso)
    phase: Phase = Phase.intake
    industry: str | None = None
    surfaces: list[str] = Field(default_factory=list)
    primary_lockup: Literal["horizontal", "stacked"] = "horizontal"
    min_sizes: MinSizes = Field(default_factory=MinSizes)
    territory: str | None = None
    concept: str | None = None
    fonts: dict[str, FontChoice] = Field(default_factory=dict)
    decisions: list[Decision] = Field(default_factory=list)


class AdjectivePair(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    adjective: str
    not_: str = Field(alias="not")


class Archetype(BaseModel):
    primary: str
    secondary: str | None = None


class Personality(BaseModel):
    sincerity: float = Field(0.5, ge=0, le=1)
    excitement: float = Field(0.5, ge=0, le=1)
    competence: float = Field(0.5, ge=0, le=1)
    sophistication: float = Field(0.5, ge=0, le=1)
    ruggedness: float = Field(0.5, ge=0, le=1)


class Brief(BaseModel):
    business: str
    audience: str
    problem: str
    one_idea: str
    onliness: str
    adjectives: list[AdjectivePair]
    persona: str
    admired: list[str] = Field(default_factory=list)
    disliked: list[str] = Field(default_factory=list)
    surfaces: list[str]
    harshest: str
    colours_wanted: list[str] = Field(default_factory=list)
    colours_forbidden: list[str] = Field(default_factory=list)
    colours_category: list[str] = Field(default_factory=list)
    off_limits: list[str] = Field(default_factory=list)
    cultural: str = ""
    needs_name: bool = False
    name: str | None = None
    name_written: str | None = None
    name_story: str = ""
    tagline: str | None = None
    archetype: Archetype
    personality: Personality
    industry: str

    @field_validator("adjectives")
    @classmethod
    def at_least_three_adjectives(cls, value: list[AdjectivePair]) -> list[AdjectivePair]:
        if len(value) < 3:
            raise ValueError("adjectives: give at least three adjective/not pairs")
        return value

    @field_validator("surfaces")
    @classmethod
    def at_least_one_surface(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("surfaces: rank at least one surface")
        return value


class LadderRung(BaseModel):
    adjective: str
    principle: str
    test: str


class CategoryUniform(BaseModel):
    type_classes: list[str] = Field(default_factory=list)
    colours: list[str] = Field(default_factory=list)
    motifs: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)


class FeatureTargets(BaseModel):
    shape: float = Field(ge=0, le=1, description="0 round .. 1 angular")
    symmetry: float = Field(ge=0, le=1, description="0 asymmetric .. 1 symmetric")
    complexity: Literal["low", "moderate", "high"]
    weight: Literal["light", "regular", "medium", "heavy"]
    hue_family: str
    saturation: Literal["low", "medium", "high"]
    lightness: Literal["dark", "mid", "light"]
    typeface_class: str
    frame: Literal["open", "framed", "badge"]
    dynamism: float = Field(ge=0, le=1)
    descriptive_cue: bool
    name_sound: str = ""


LogoType = Literal["wordmark", "lettermark", "pictorial", "abstract", "mascot", "combination", "emblem"]


class Strategy(BaseModel):
    onliness: str
    positioning: str
    archetype: Archetype
    personality: Personality
    one_idea: str
    ladder: list[LadderRung]
    category_uniform: CategoryUniform
    targets: FeatureTargets
    logo_type: LogoType
    logo_type_reason: str
    constraints: dict[str, str | int | float | bool | list] = Field(default_factory=dict)

    @field_validator("ladder")
    @classmethod
    def at_least_three_rungs(cls, value: list[LadderRung]) -> list[LadderRung]:
        if len(value) < 3:
            raise ValueError("ladder: give at least three rungs")
        return value
```

- [ ] **Step 5: Write the registry**

`src/logomaker/registry.py`:

```python
"""Brand folders, brand.json state machine, and the registry index."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from .output import CliError
from .paths import ProjectPaths
from .schemas import PHASE_ORDER, BrandState, Brief, Decision, FontChoice, Phase, Strategy, now_iso

BRAND_SUBDIRS = ("inspiration", "territories", "concepts", "sheets", "final", "package")


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if not text:
        raise CliError(f"Cannot make a slug from {name!r}")
    return text


def state_path(paths: ProjectPaths, slug: str) -> Path:
    return paths.brand(slug) / "brand.json"


def load_state(paths: ProjectPaths, slug: str) -> BrandState:
    path = state_path(paths, slug)
    if not path.is_file():
        raise CliError(f"Unknown brand {slug!r} (no {path})")
    return BrandState.model_validate_json(path.read_text(encoding="utf-8"))


def save_state(paths: ProjectPaths, state: BrandState) -> None:
    state.updated = now_iso()
    path = state_path(paths, state.slug)
    path.write_text(json.dumps(state.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    _update_registry(paths, state)


def new_brand(paths: ProjectPaths, name: str, slug: str | None = None, unnamed: bool = False) -> BrandState:
    slug = slug or slugify(name)
    if slug != slugify(slug):
        raise CliError(f"Slug {slug!r} must be lowercase letters, digits and hyphens")
    folder = paths.brand(slug)
    if folder.exists():
        raise CliError(f"Brand {slug!r} already exists at {folder}")
    for sub in BRAND_SUBDIRS:
        (folder / sub).mkdir(parents=True)
    state = BrandState(slug=slug, name=name, needs_name=unnamed)
    save_state(paths, state)
    return state


def list_brands(paths: ProjectPaths) -> list[dict[str, Any]]:
    path = paths.registry / "brands.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("brands", [])


def _update_registry(paths: ProjectPaths, state: BrandState) -> None:
    paths.registry.mkdir(parents=True, exist_ok=True)
    entries = [e for e in list_brands(paths) if e["slug"] != state.slug]
    entries.append({"slug": state.slug, "name": state.name, "phase": state.phase.value, "updated": state.updated})
    entries.sort(key=lambda e: e["slug"])
    (paths.registry / "brands.json").write_text(json.dumps({"brands": entries}, indent=2) + "\n", encoding="utf-8")
    lines = ["# Brands", "", "| Slug | Name | Phase | Updated |", "|---|---|---|---|"]
    lines += [f"| {e['slug']} | {e['name']} | {e['phase']} | {e['updated']} |" for e in entries]
    (paths.registry / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def decide(paths: ProjectPaths, slug: str, phase: Phase, by: str, note: str) -> BrandState:
    state = load_state(paths, slug)
    state.decisions.append(Decision(phase=phase, by=by, note=note))  # type: ignore[arg-type]
    save_state(paths, state)
    return state


def rename(paths: ProjectPaths, slug: str, name: str) -> BrandState:
    state = load_state(paths, slug)
    state.name = name
    state.needs_name = False
    save_state(paths, state)
    return state


def set_fields(paths: ProjectPaths, slug: str, **fields: Any) -> BrandState:
    state = load_state(paths, slug)
    for key, value in fields.items():
        if value is None or value == ():
            continue
        if key == "fonts":
            for spec in value:
                role, _, rest = spec.partition("=")
                family, _, weight = rest.partition(":")
                if not role or not family:
                    raise CliError(f"--font must look like ROLE=FAMILY[:WEIGHT], got {spec!r}")
                state.fonts[role] = FontChoice(family=family, weight=int(weight) if weight else 400)
        elif key == "surfaces":
            state.surfaces = list(value)
        else:
            setattr(state, key, value)
    save_state(paths, state)
    return state


def allowed_next(state: BrandState) -> Phase | None:
    if state.phase == Phase.intake:
        return Phase.naming if state.needs_name else Phase.strategy
    if state.phase == Phase.done:
        return None
    return PHASE_ORDER[PHASE_ORDER.index(state.phase) + 1]


def _validate_file(path: Path, model: type[BaseModel]) -> str | None:
    """Return an error message if `path` is missing or does not validate as `model`."""
    if not path.is_file():
        return f"{path.name} is missing"
    try:
        model.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as err:
        first = err.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "root"
        return f"{path.name} is invalid: {loc}: {first['msg']}"
    except ValueError as err:
        return f"{path.name} is not valid JSON: {err}"
    return None


def prerequisites(paths: ProjectPaths, state: BrandState, target: Phase) -> list[str]:
    brand = paths.brand(state.slug)
    missing: list[str] = []
    nxt = allowed_next(state)
    if target != nxt:
        missing.append(f"phase {state.phase.value} can only advance to {nxt.value if nxt else 'nothing'}, not {target.value}")

    def need(path: Path, model: type[BaseModel] | None = None) -> None:
        if model is None:
            if not path.is_file():
                missing.append(f"{path.relative_to(brand)} is missing")
        else:
            err = _validate_file(path, model)
            if err:
                missing.append(err)

    if target in (Phase.naming, Phase.strategy):
        need(brand / "brief.md")
        need(brand / "brief.json", Brief)
    if target == Phase.strategy and state.needs_name:
        missing.append("brand still needs a name (run: logomaker brand rename <slug> --name <Name>)")
    if target == Phase.territories:
        need(brand / "strategy.md")
        need(brand / "strategy.json", Strategy)
    if target == Phase.concepts:
        spec = brand / "territories" / "territories.json"
        need(spec)
        if spec.is_file():
            try:
                slugs = [t["slug"] for t in json.loads(spec.read_text(encoding="utf-8"))["territories"]]
            except (KeyError, TypeError, ValueError):
                slugs = []
                missing.append("territories.json must contain a 'territories' list with slugs")
            if state.territory not in slugs:
                missing.append("territory not chosen (run: logomaker brand set <slug> --territory <territory-slug>)")
    if target == Phase.refinement:
        if not state.concept:
            missing.append("concept not chosen (run: logomaker brand set <slug> --concept <NN-slug>)")
        else:
            folder = brand / "concepts" / state.concept
            need(folder / "concept.py")
            audit = folder / "audit.json"
            need(audit)
            if audit.is_file() and not json.loads(audit.read_text(encoding="utf-8")).get("ok"):
                missing.append(f"{state.concept}/audit.json has failures")
    if target == Phase.package:
        for name in ("concept.py", "params.json", "tokens.json"):
            need(brand / "final" / name)
    if target == Phase.done:
        verify = brand / "package" / "verify.json"
        need(verify)
        if verify.is_file() and not json.loads(verify.read_text(encoding="utf-8")).get("ok"):
            missing.append("package/verify.json reports failures")
    return missing


def advance(paths: ProjectPaths, slug: str, target: Phase) -> BrandState:
    state = load_state(paths, slug)
    missing = prerequisites(paths, state, target)
    if missing:
        raise CliError(f"Cannot advance {slug} to {target.value}", data={"missing": missing})
    state.phase = target
    save_state(paths, state)
    return state
```

- [ ] **Step 6: Add the `brand` group to the CLI**

Add to `src/logomaker/cli.py` after the `setup` command (and add `from . import registry` and `from .schemas import Phase` to the imports):

```python
@main.group("brand")
def brand() -> None:
    """Create, inspect and advance brands."""


def _brand_payload(state) -> dict:
    return {"brand": state.model_dump(mode="json")}


@brand.command("new")
@click.argument("name")
@click.option("--slug", default=None, help="Override the generated slug.")
@click.option("--unnamed", is_flag=True, help="NAME is a working title; a naming phase will run.")
@command
def brand_new(name: str, slug: str | None, unnamed: bool) -> None:
    emit(_brand_payload(registry.new_brand(project(), name, slug, unnamed)))


@brand.command("list")
@command
def brand_list() -> None:
    emit({"brands": registry.list_brands(project())})


@brand.command("status")
@click.argument("slug")
@command
def brand_status(slug: str) -> None:
    paths = project()
    state = registry.load_state(paths, slug)
    nxt = registry.allowed_next(state)
    payload = _brand_payload(state)
    payload["next"] = nxt.value if nxt else None
    payload["missing"] = registry.prerequisites(paths, state, nxt) if nxt else []
    emit(payload)


@brand.command("advance")
@click.argument("slug")
@click.option("--to", "target", required=True, type=click.Choice([p.value for p in Phase]))
@command
def brand_advance(slug: str, target: str) -> None:
    emit(_brand_payload(registry.advance(project(), slug, Phase(target))))


@brand.command("decide")
@click.argument("slug")
@click.option("--phase", required=True, type=click.Choice([p.value for p in Phase]))
@click.option("--by", default="user", type=click.Choice(["user", "claude"]))
@click.option("--note", required=True)
@command
def brand_decide(slug: str, phase: str, by: str, note: str) -> None:
    emit(_brand_payload(registry.decide(project(), slug, Phase(phase), by, note)))


@brand.command("rename")
@click.argument("slug")
@click.option("--name", required=True)
@command
def brand_rename(slug: str, name: str) -> None:
    emit(_brand_payload(registry.rename(project(), slug, name)))


@brand.command("set")
@click.argument("slug")
@click.option("--territory", default=None)
@click.option("--concept", default=None, help="Concept folder name, e.g. 03-keystone")
@click.option("--primary-lockup", "primary_lockup", default=None, type=click.Choice(["horizontal", "stacked"]))
@click.option("--industry", default=None)
@click.option("--surface", "surfaces", multiple=True, help="Ranked surfaces; repeat the flag.")
@click.option("--font", "fonts", multiple=True, help="ROLE=FAMILY[:WEIGHT], e.g. wordmark=Sora:650")
@command
def brand_set(slug: str, territory, concept, primary_lockup, industry, surfaces, fonts) -> None:
    emit(_brand_payload(registry.set_fields(
        project(), slug, territory=territory, concept=concept, primary_lockup=primary_lockup,
        industry=industry, surfaces=surfaces, fonts=fonts,
    )))
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_registry.py -q`
Expected: 10 passed.

- [ ] **Step 8: Commit**

```bash
git add src/logomaker/schemas.py src/logomaker/registry.py src/logomaker/cli.py tests/conftest.py tests/test_registry.py
git commit -m "feat: brand state machine, registry index and brand commands

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Geometry kit: `Shape`, primitives, snapping, path serialisation

**Files:**
- Create: `src/logomaker/kit/__init__.py`, `src/logomaker/kit/shape.py`, `src/logomaker/kit/primitives.py`
- Test: `tests/test_kit_shape.py`, `tests/test_kit_primitives.py`

**Interfaces:**
- Produces: `shape.Box(x0, y0, x1, y1)` with `w, h, cx, cy` and `Box.union(boxes)`; `shape.fmt(value, precision=2) -> str`; `shape.Shape(path=None, free_segments=0)` with `copy()`, `is_empty`, `bounds`, `commands()` (yields `("M",[p])`, `("L",[p])`, `("C",[c1,c2,p])`, `("Z",[])`), `anchor_count()`, `straight_segments()`, `subpaths()`, `flatten(steps=16)`, `area`, `centroid`, `transformed(matrix)`, `to_path_data(precision=2, flip_y=True)`; `shape.path_from_commands(commands) -> skia.Path`; `primitives.snap`, `snap_angle`, `circle`, `ring`, `rect`, `rect_centered`, `rrect`, `rrect_centered`, `polygon`, `regular_polygon`, `wedge`, `arc`, `line`, `polyline`, `bezier`, `stroked_path(path, width, cap, join, miter_limit=4) -> skia.Path`, constants `SNAP = 0.25`, `ANGLE_SNAP = 15.0`, `CAPS`, `JOINS`. The kit frame is y up; angles are degrees counter-clockwise from +x.

- [ ] **Step 1: Write the failing tests**

`tests/test_kit_shape.py`:

```python
import math

import skia

from logomaker.kit.shape import Box, Shape, fmt, path_from_commands


def test_fmt_never_emits_scientific_notation_or_negative_zero():
    assert fmt(-0.004) == "0"
    assert fmt(1e-05) == "0"
    assert fmt(12.3456) == "12.35"
    assert fmt(100.0) == "100"
    assert fmt(-3.10) == "-3.1"
    assert fmt(0.125, precision=2) == "0.12"


def square(size=10.0) -> Shape:
    p = skia.Path()
    p.addRect(skia.Rect.MakeLTRB(0, 0, size, size * 2))
    return Shape(p)


def test_bounds_area_centroid_of_rect():
    s = square()
    assert s.bounds == Box(0, 0, 10, 20)
    assert math.isclose(s.area, 200)
    cx, cy = s.centroid
    assert math.isclose(cx, 5) and math.isclose(cy, 10)
    assert s.anchor_count() == 4
    assert len(s.straight_segments()) == 4


def test_circle_commands_are_cubics_and_area_is_close():
    p = skia.Path()
    p.addCircle(30, -40, 50)
    s = Shape(p)
    kinds = {k for k, _ in s.commands()}
    assert kinds == {"M", "C", "Z"}
    assert s.anchor_count() == 49
    assert math.isclose(s.area, math.pi * 50 * 50, rel_tol=0.005)
    cx, cy = s.centroid
    assert math.isclose(cx, 30, abs_tol=0.5) and math.isclose(cy, -40, abs_tol=0.5)


def test_path_data_flips_y_and_is_deterministic():
    assert square().to_path_data() == "M0 0L10 0L10 -20L0 -20Z"
    assert square().to_path_data(flip_y=False) == "M0 0L10 0L10 20L0 20Z"


def test_path_data_has_no_scientific_notation_for_tiny_values():
    p = skia.Path()
    p.addCircle(0, 0, 0.001)
    data = Shape(p).to_path_data()
    assert "e-" not in data and "-0 " not in data and "-0L" not in data


def test_subpaths_and_round_trip():
    p = skia.Path()
    p.addRect(skia.Rect.MakeLTRB(0, 0, 10, 10))
    p.addRect(skia.Rect.MakeLTRB(20, 0, 30, 10))
    s = Shape(p)
    parts = s.subpaths()
    assert len(parts) == 2 and parts[1].bounds.x0 == 20
    rebuilt = Shape(path_from_commands(s.commands()))
    assert rebuilt.to_path_data() == s.to_path_data()


def test_box_union():
    assert Box.union([Box(0, 0, 1, 1), Box(-2, 3, 0, 5)]) == Box(-2, 0, 1, 5)
```

`tests/test_kit_primitives.py`:

```python
import math

from logomaker.kit.primitives import (
    arc, bezier, circle, line, polygon, polyline, rect, rect_centered, regular_polygon, ring, rrect, snap, snap_angle, wedge,
)


def test_snapping():
    assert snap(0.3) == 0.25 and snap(0.13) == 0.25 and snap(0.12) == 0.0 and snap(-0.4) == -0.5
    assert snap_angle(50) == 45 and snap_angle(7) == 0 and snap_angle(8) == 15


def test_circle_snaps_centre_and_radius():
    b = circle(0.3, 0.1, 100.12).bounds
    assert (b.x0, b.x1) == (-99.75, 100.25)
    assert math.isclose(circle(0, 0, 100).area, math.pi * 100**2, rel_tol=0.005)


def test_rect_and_rrect():
    assert rect(0, 0, 10, 20).bounds.w == 10 and rect(0, 0, 10, 20).bounds.h == 20
    assert rect_centered(0, 0, 10, 20).bounds.x0 == -5
    r = rrect(0, 0, 100, 50, 10)
    assert math.isclose(r.area, 100 * 50 - (4 - math.pi) * 100, rel_tol=0.01)


def test_ring_and_sector_areas():
    full = ring(0, 0, 100, 20)
    assert math.isclose(full.area, math.pi * (100**2 - 80**2), rel_tol=0.01)
    assert len(full.subpaths()) == 2
    quarter = ring(0, 0, 100, 20, start=0, end=90)
    assert math.isclose(quarter.area, full.area / 4, rel_tol=0.02)
    b = quarter.bounds
    assert b.x0 >= -0.01 and b.y0 >= -0.01 and math.isclose(b.x1, 100, abs_tol=0.01)


def test_polygons():
    sq = regular_polygon(0, 0, 100, 4, rotation=50)  # rotation snaps to 45
    assert math.isclose(sq.area, 2 * 100**2, rel_tol=0.001)
    assert math.isclose(sq.bounds.x1, 100, abs_tol=0.01)
    tri = polygon([(0, 0), (100, 0), (0, 100)])
    assert math.isclose(tri.area, 5000) and len(tri.straight_segments()) == 3
    assert polygon([(0, 0), (100, 0), (0, 100)], free=True).free_segments == 3
    assert tri.free_segments == 0


def test_wedge():
    w = wedge(0, 0, 100, 0, 90)
    assert math.isclose(w.area, math.pi * 100**2 / 4, rel_tol=0.01)


def test_strokes():
    seg = line(0, 0, 100, 0, 10)
    assert seg.bounds.x0 == 0 and seg.bounds.x1 == 100 and math.isclose(seg.area, 1000, rel_tol=0.001)
    rounded = line(0, 0, 100, 0, 10, cap="round")
    assert math.isclose(rounded.area, 1000 + math.pi * 25, rel_tol=0.01)
    a = arc(0, 0, 100, 0, 90, 10)
    assert math.isclose(a.bounds.x1, 105, abs_tol=0.5) and math.isclose(a.bounds.y1, 105, abs_tol=0.5)
    pl = polyline([(0, 0), (100, 0), (100, 100)], 10, join="round")
    assert not pl.is_empty and pl.bounds.y1 >= 100


def test_bezier_filled_and_stroked():
    pts = [(0, 0), (0, 60), (40, 100), (100, 100)]
    filled = bezier(pts, closed=True)
    assert filled.area > 3000
    stroked = bezier(pts, width=4)
    assert not stroked.is_empty and stroked.bounds.x1 > 100
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_kit_shape.py tests/test_kit_primitives.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker.kit'`.

- [ ] **Step 3: Write `Shape`**

`src/logomaker/kit/__init__.py` (extended by later tasks):

```python
"""Geometry kit. `from logomaker.kit import *` gives concept modules everything they need."""
from .shape import Box, Shape, fmt  # noqa: F401
from .primitives import (  # noqa: F401
    arc, bezier, circle, line, polygon, polyline, rect, rect_centered, regular_polygon, ring, rrect, rrect_centered,
    snap, snap_angle, wedge,
)

__all__ = [
    "Box", "Shape", "fmt",
    "arc", "bezier", "circle", "line", "polygon", "polyline", "rect", "rect_centered", "regular_polygon", "ring",
    "rrect", "rrect_centered", "snap", "snap_angle", "wedge",
]
```

`src/logomaker/kit/shape.py`:

```python
"""Shape: a thin wrapper over skia.Path with the queries the kit and the audits need.

Coordinates are in the kit frame (y up). `to_path_data` flips y for SVG.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Iterator

import skia

Point = tuple[float, float]
Command = tuple[str, list[Point]]


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @classmethod
    def union(cls, boxes: Iterable["Box"]) -> "Box":
        boxes = list(boxes)
        return cls(min(b.x0 for b in boxes), min(b.y0 for b in boxes), max(b.x1 for b in boxes), max(b.y1 for b in boxes))


def fmt(value: float, precision: int = 2) -> str:
    """Format a number for SVG: fixed precision, no trailing zeros, never '-0' or exponents."""
    rounded = round(value, precision)
    if rounded == 0:
        return "0"
    text = f"{rounded:.{precision}f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _xy(p: skia.Point) -> Point:
    return (p.x(), p.y())


def _quad_to_cubic(p0: Point, q: Point, p2: Point) -> list[Point]:
    c1 = (p0[0] + 2 / 3 * (q[0] - p0[0]), p0[1] + 2 / 3 * (q[1] - p0[1]))
    c2 = (p2[0] + 2 / 3 * (q[0] - p2[0]), p2[1] + 2 / 3 * (q[1] - p2[1]))
    return [c1, c2, p2]


def path_from_commands(commands: Iterable[Command]) -> skia.Path:
    path = skia.Path()
    for kind, pts in commands:
        if kind == "M":
            path.moveTo(*pts[0])
        elif kind == "L":
            path.lineTo(*pts[0])
        elif kind == "C":
            path.cubicTo(*pts[0], *pts[1], *pts[2])
        elif kind == "Z":
            path.close()
    return path


def _cubic_points(p0: Point, c1: Point, c2: Point, p1: Point, steps: int) -> list[Point]:
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * p1[0]
        y = u**3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * p1[1]
        out.append((x, y))
    return out


def _signed_area_and_centroid(poly: list[Point]) -> tuple[float, Point]:
    if len(poly) < 3:
        return 0.0, (0.0, 0.0)
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a *= 0.5
    if abs(a) < 1e-12:
        return 0.0, (0.0, 0.0)
    return a, (cx / (6 * a), cy / (6 * a))


class Shape:
    __slots__ = ("path", "free_segments")

    def __init__(self, path: skia.Path | None = None, free_segments: int = 0):
        self.path = path if path is not None else skia.Path()
        self.free_segments = free_segments

    @classmethod
    def empty(cls) -> "Shape":
        return cls()

    def copy(self) -> "Shape":
        return Shape(skia.Path(self.path), self.free_segments)

    @property
    def is_empty(self) -> bool:
        return self.path.isEmpty()

    @property
    def bounds(self) -> Box:
        r = self.path.computeTightBounds()
        return Box(r.left(), r.top(), r.right(), r.bottom())

    def commands(self) -> Iterator[Command]:
        """Yield M/L/C/Z commands; conics become quads (4 per conic) and quads become cubics."""
        it = skia.Path.Iter(self.path, False)
        current: Point = (0.0, 0.0)
        while True:
            verb, pts = it.next()
            if verb == skia.Path.Verb.kDone_Verb:
                return
            if verb == skia.Path.Verb.kMove_Verb:
                current = _xy(pts[0])
                yield ("M", [current])
            elif verb == skia.Path.Verb.kLine_Verb:
                current = _xy(pts[1])
                yield ("L", [current])
            elif verb == skia.Path.Verb.kQuad_Verb:
                p0, q, p2 = _xy(pts[0]), _xy(pts[1]), _xy(pts[2])
                yield ("C", _quad_to_cubic(p0, q, p2))
                current = p2
            elif verb == skia.Path.Verb.kConic_Verb:
                quads = skia.Path.ConvertConicToQuads(pts[0], pts[1], pts[2], it.conicWeight(), 2)
                for i in range(0, len(quads) - 1, 2):
                    p0, q, p2 = _xy(quads[i]), _xy(quads[i + 1]), _xy(quads[i + 2])
                    yield ("C", _quad_to_cubic(p0, q, p2))
                    current = p2
            elif verb == skia.Path.Verb.kCubic_Verb:
                c1, c2, p1 = _xy(pts[1]), _xy(pts[2]), _xy(pts[3])
                yield ("C", [c1, c2, p1])
                current = p1
            elif verb == skia.Path.Verb.kClose_Verb:
                yield ("Z", [])

    def anchor_count(self) -> int:
        return sum(len(pts) for _, pts in self.commands())

    def straight_segments(self) -> list[tuple[Point, Point]]:
        segments: list[tuple[Point, Point]] = []
        start = current = (0.0, 0.0)
        for kind, pts in self.commands():
            if kind == "M":
                start = current = pts[0]
            elif kind == "L":
                segments.append((current, pts[0]))
                current = pts[0]
            elif kind == "C":
                current = pts[2]
            elif kind == "Z":
                if current != start:
                    segments.append((current, start))
                current = start
        return segments

    def subpaths(self) -> list["Shape"]:
        groups: list[list[Command]] = []
        for cmd in self.commands():
            if cmd[0] == "M":
                groups.append([cmd])
            elif groups:
                groups[-1].append(cmd)
        return [Shape(path_from_commands(g), 0) for g in groups]

    def flatten(self, steps: int = 16) -> list[list[Point]]:
        polys: list[list[Point]] = []
        current: Point = (0.0, 0.0)
        for kind, pts in self.commands():
            if kind == "M":
                polys.append([pts[0]])
                current = pts[0]
            elif kind == "L":
                polys[-1].append(pts[0])
                current = pts[0]
            elif kind == "C":
                polys[-1].extend(_cubic_points(current, pts[0], pts[1], pts[2], steps))
                current = pts[2]
        return polys

    @property
    def area(self) -> float:
        return abs(sum(_signed_area_and_centroid(poly)[0] for poly in self.flatten()))

    @property
    def centroid(self) -> Point:
        total = cx = cy = 0.0
        for poly in self.flatten():
            a, (px, py) = _signed_area_and_centroid(poly)
            total += a
            cx += a * px
            cy += a * py
        if abs(total) < 1e-12:
            b = self.bounds
            return (b.cx, b.cy)
        return (cx / total, cy / total)

    def transformed(self, matrix: skia.Matrix) -> "Shape":
        dst = skia.Path()
        self.path.transform(matrix, dst)
        return Shape(dst, self.free_segments)

    def to_path_data(self, precision: int = 2, flip_y: bool = True) -> str:
        sign = -1.0 if flip_y else 1.0
        parts: list[str] = []
        for kind, pts in self.commands():
            if kind == "Z":
                parts.append("Z")
                continue
            coords = " ".join(f"{fmt(x, precision)} {fmt(sign * y, precision)}" for x, y in pts)
            parts.append(f"{kind}{coords}")
        return "".join(parts)
```

- [ ] **Step 4: Write the primitives**

`src/logomaker/kit/primitives.py`:

```python
"""Primitive shapes on the 1000-unit canvas. Coordinates snap to 0.25 units and angles to 15 degrees unless free=True."""
from __future__ import annotations

import math

import skia

from .shape import Shape

SNAP = 0.25
ANGLE_SNAP = 15.0

CAPS = {"butt": skia.Paint.kButt_Cap, "round": skia.Paint.kRound_Cap, "square": skia.Paint.kSquare_Cap}
JOINS = {"miter": skia.Paint.kMiter_Join, "round": skia.Paint.kRound_Join, "bevel": skia.Paint.kBevel_Join}


def snap(value: float, step: float = SNAP) -> float:
    return round(round(value / step) * step, 6)


def snap_angle(angle: float, step: float = ANGLE_SNAP) -> float:
    return round(round(angle / step) * step, 6)


def _v(value: float, free: bool) -> float:
    return value if free else snap(value)


def _a(angle: float, free: bool) -> float:
    return angle if free else snap_angle(angle)


def _oval(cx: float, cy: float, r: float) -> skia.Rect:
    return skia.Rect.MakeLTRB(cx - r, cy - r, cx + r, cy + r)


def _polar(cx: float, cy: float, r: float, angle: float) -> tuple[float, float]:
    rad = math.radians(angle)
    return (cx + r * math.cos(rad), cy + r * math.sin(rad))


def _finish(path: skia.Path, free: bool) -> Shape:
    shape = Shape(path)
    shape.free_segments = len(shape.straight_segments()) if free else 0
    return shape


def stroked_path(path: skia.Path, width: float, cap: str = "butt", join: str = "miter", miter_limit: float = 4) -> skia.Path:
    paint = skia.Paint()
    paint.setStyle(skia.Paint.kStroke_Style)
    paint.setStrokeWidth(width)
    paint.setStrokeCap(CAPS[cap])
    paint.setStrokeJoin(JOINS[join])
    paint.setStrokeMiter(miter_limit)
    out = skia.Path()
    paint.getFillPath(path, out)
    return skia.Simplify(out)


def circle(cx: float, cy: float, r: float, free: bool = False) -> Shape:
    path = skia.Path()
    path.addCircle(_v(cx, free), _v(cy, free), _v(r, free))
    return _finish(path, free)


def ring(cx: float, cy: float, r: float, width: float, start: float | None = None, end: float | None = None, free: bool = False) -> Shape:
    """Annulus with outer radius r and band width `width`; with start/end (degrees, counter-clockwise) an annular sector."""
    cx, cy, r, width = _v(cx, free), _v(cy, free), _v(r, free), _v(width, free)
    inner = r - width
    if start is None or end is None:
        outer = skia.Path()
        outer.addCircle(cx, cy, r)
        hole = skia.Path()
        hole.addCircle(cx, cy, inner)
        return _finish(skia.Op(outer, hole, skia.PathOp.kDifference_PathOp), free)
    start, end = _a(start, free), _a(end, free)
    sweep = end - start
    if sweep <= 0:
        sweep += 360
    path = skia.Path()
    path.moveTo(*_polar(cx, cy, r, start))
    path.arcTo(_oval(cx, cy, r), start, sweep, False)
    path.lineTo(*_polar(cx, cy, inner, end))
    path.arcTo(_oval(cx, cy, inner), end, -sweep, False)
    path.close()
    return _finish(path, free)


def rect(x: float, y: float, w: float, h: float, free: bool = False) -> Shape:
    """Rectangle from its lower-left corner (x, y) in the y-up frame."""
    x, y, w, h = _v(x, free), _v(y, free), _v(w, free), _v(h, free)
    path = skia.Path()
    path.addRect(skia.Rect.MakeLTRB(x, y, x + w, y + h))
    return _finish(path, free)


def rect_centered(cx: float, cy: float, w: float, h: float, free: bool = False) -> Shape:
    return rect(cx - w / 2, cy - h / 2, w, h, free)


def rrect(x: float, y: float, w: float, h: float, radius: float, free: bool = False) -> Shape:
    x, y, w, h, radius = _v(x, free), _v(y, free), _v(w, free), _v(h, free), _v(radius, free)
    path = skia.Path()
    path.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x, y, x + w, y + h), radius, radius))
    return _finish(path, free)


def rrect_centered(cx: float, cy: float, w: float, h: float, radius: float, free: bool = False) -> Shape:
    return rrect(cx - w / 2, cy - h / 2, w, h, radius, free)


def polygon(points: list[tuple[float, float]], free: bool = False) -> Shape:
    if len(points) < 3:
        raise ValueError("polygon needs at least three points")
    path = skia.Path()
    path.moveTo(_v(points[0][0], free), _v(points[0][1], free))
    for x, y in points[1:]:
        path.lineTo(_v(x, free), _v(y, free))
    path.close()
    return _finish(path, free)


def regular_polygon(cx: float, cy: float, r: float, n: int, rotation: float = 0, free: bool = False) -> Shape:
    if n < 3:
        raise ValueError("regular_polygon needs n >= 3")
    cx, cy, r, rotation = _v(cx, free), _v(cy, free), _v(r, free), _a(rotation, free)
    pts = [_polar(cx, cy, r, rotation + 360 * i / n) for i in range(n)]
    return polygon(pts, free=True) if free else _finish_polygon_snapped(pts)


def _finish_polygon_snapped(pts: list[tuple[float, float]]) -> Shape:
    # Regular polygons keep exact vertices (snapping them would break the symmetry); count as not free.
    path = skia.Path()
    path.moveTo(*pts[0])
    for p in pts[1:]:
        path.lineTo(*p)
    path.close()
    return Shape(path, 0)


def wedge(cx: float, cy: float, r: float, start: float, end: float, free: bool = False) -> Shape:
    cx, cy, r, start, end = _v(cx, free), _v(cy, free), _v(r, free), _a(start, free), _a(end, free)
    sweep = end - start
    if sweep <= 0:
        sweep += 360
    path = skia.Path()
    path.moveTo(cx, cy)
    path.arcTo(_oval(cx, cy, r), start, sweep, False)
    path.close()
    return _finish(path, free)


def arc(cx: float, cy: float, r: float, start: float, end: float, width: float, cap: str = "butt", free: bool = False) -> Shape:
    """A stroked arc on centreline radius r."""
    cx, cy, r, start, end, width = _v(cx, free), _v(cy, free), _v(r, free), _a(start, free), _a(end, free), _v(width, free)
    sweep = end - start
    if sweep <= 0:
        sweep += 360
    path = skia.Path()
    path.moveTo(*_polar(cx, cy, r, start))
    path.arcTo(_oval(cx, cy, r), start, sweep, False)
    return _finish(stroked_path(path, width, cap), free)


def line(x1: float, y1: float, x2: float, y2: float, width: float, cap: str = "butt", free: bool = False) -> Shape:
    path = skia.Path()
    path.moveTo(_v(x1, free), _v(y1, free))
    path.lineTo(_v(x2, free), _v(y2, free))
    return _finish(stroked_path(path, _v(width, free), cap), free)


def polyline(points: list[tuple[float, float]], width: float, cap: str = "butt", join: str = "miter", free: bool = False) -> Shape:
    if len(points) < 2:
        raise ValueError("polyline needs at least two points")
    path = skia.Path()
    path.moveTo(_v(points[0][0], free), _v(points[0][1], free))
    for x, y in points[1:]:
        path.lineTo(_v(x, free), _v(y, free))
    return _finish(stroked_path(path, _v(width, free), cap, join), free)


def bezier(points: list[tuple[float, float]], width: float | None = None, closed: bool = False, free: bool = False) -> Shape:
    """Cubic Bézier chain p0, c1, c2, p1, c3, c4, p2, ... Filled (closed) when width is None, else stroked."""
    if len(points) < 4 or (len(points) - 1) % 3 != 0:
        raise ValueError("bezier needs 1 + 3k points")
    pts = [(_v(x, free), _v(y, free)) for x, y in points]
    path = skia.Path()
    path.moveTo(*pts[0])
    for i in range(1, len(pts), 3):
        path.cubicTo(*pts[i], *pts[i + 1], *pts[i + 2])
    if closed or width is None:
        path.close()
    if width is None:
        return _finish(path, free)
    return _finish(stroked_path(path, _v(width, free), "butt", "round"), free)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_kit_shape.py tests/test_kit_primitives.py -q`
Expected: 15 passed.

- [ ] **Step 6: Commit**

```bash
git add src/logomaker/kit tests/test_kit_shape.py tests/test_kit_primitives.py
git commit -m "feat: geometry kit with Shape wrapper, primitives and SVG path serialisation

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Geometry kit: booleans, stroke, offset, transforms, alignment, optical helpers

**Files:**
- Create: `src/logomaker/kit/ops.py`, `src/logomaker/kit/optical.py`
- Modify: `src/logomaker/kit/__init__.py` (re-export)
- Test: `tests/test_kit_ops.py`

**Interfaces:**
- Consumes: `shape.Shape`, `shape.Box`, `primitives.stroked_path`.
- Produces: `ops.union(*shapes)`, `ops.subtract(a, b)`, `ops.intersect(a, b)`, `ops.xor(a, b)`, `ops.stroke(shape, width, cap="butt", join="miter", miter_limit=4)`, `ops.offset(shape, distance)`, `ops.translate(shape, dx, dy)`, `ops.rotate(shape, degrees, cx=0, cy=0)`, `ops.scale(shape, sx, sy=None, cx=0, cy=0)`, `ops.mirror_x(shape, axis=0.0)`, `ops.mirror_y(shape, axis=0.0)`, `ops.align(shape, to, edge)` with edge in `left, right, top, bottom, center, middle`, `ops.center(shape, cx=0, cy=0, optical=False)`, `ops.fit(shape, w, h, cx=0, cy=0)`; `optical.overshoot(shape, amount=0.015)`, `optical.StrokeWidths(vertical, horizontal, curve)`, `optical.compensate_stroke(base_width, horizontal_factor=0.92, curve_factor=1.05) -> StrokeWidths`, `optical.optical_center(shape) -> (x, y)`. All return new `Shape`s; inputs are never mutated.

- [ ] **Step 1: Write the failing tests**

`tests/test_kit_ops.py`:

```python
import math

from logomaker.kit.ops import align, center, fit, intersect, mirror_x, mirror_y, offset, rotate, scale, stroke, subtract, translate, union, xor
from logomaker.kit.optical import compensate_stroke, optical_center, overshoot
from logomaker.kit.primitives import circle, polygon, rect, rect_centered


def test_booleans():
    a = rect(0, 0, 100, 100)
    b = rect(50, 50, 100, 100)
    assert math.isclose(union(a, b).area, 17500)
    assert math.isclose(subtract(a, b).area, 7500)
    assert math.isclose(intersect(a, b).area, 2500)
    assert math.isclose(xor(a, b).area, 15000)
    assert union(a, b).free_segments == 0
    assert union(polygon([(0, 0), (10, 0), (0, 10)], free=True), b).free_segments == 3
    assert union().is_empty


def test_stroke_and_offset():
    outline = stroke(rect(0, 0, 100, 100), 10)
    assert math.isclose(outline.area, 4000, rel_tol=0.001)
    grown = offset(rect(0, 0, 100, 100), 10)
    assert (grown.bounds.x0, grown.bounds.y0, grown.bounds.x1, grown.bounds.y1) == (-10, -10, 110, 110)
    shrunk = offset(rect(0, 0, 100, 100), -10)
    assert (shrunk.bounds.x0, shrunk.bounds.x1) == (10, 90) and math.isclose(shrunk.area, 6400, rel_tol=0.001)


def test_transforms():
    r = rect(0, 0, 10, 20)
    b = rotate(r, 90).bounds
    assert (round(b.x0), round(b.y0), round(b.x1), round(b.y1)) == (-20, 0, 0, 10)
    assert translate(r, 5, 5).bounds.x0 == 5
    assert scale(r, 2).bounds.y1 == 40
    assert mirror_x(r).bounds.x0 == -10 and mirror_x(r).bounds.x1 == 0
    assert mirror_y(r).bounds.y0 == -20
    assert r.bounds.x0 == 0  # inputs are not mutated


def test_align_center_fit():
    target = rect(100, 100, 50, 50)
    s = rect_centered(0, 0, 10, 10)
    assert align(s, target, "left").bounds.x0 == 100
    assert align(s, target, "right").bounds.x1 == 150
    assert align(s, target, "bottom").bounds.y0 == 100
    assert align(s, target, "top").bounds.y1 == 150
    assert align(s, target, "center").bounds.cx == 125
    assert align(s, target, "middle").bounds.cy == 125
    c = center(rect(0, 0, 10, 20))
    assert c.bounds.cx == 0 and c.bounds.cy == 0
    tri = center(polygon([(0, 0), (90, 0), (0, 90)]), optical=True)
    cx, cy = tri.centroid
    assert abs(cx) < 0.01 and abs(cy) < 0.01
    f = fit(circle(0, 0, 100), 50, 50, cx=10, cy=10).bounds
    assert math.isclose(f.x0, -15, abs_tol=0.01) and math.isclose(f.y1, 35, abs_tol=0.01)


def test_optical_helpers():
    assert math.isclose(overshoot(circle(0, 0, 100)).bounds.y1, 101.5, abs_tol=0.01)
    widths = compensate_stroke(100)
    assert (widths.vertical, widths.horizontal, widths.curve) == (100, 92, 105)
    assert optical_center(rect(0, 0, 10, 20)) == (5, 10)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_kit_ops.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker.kit.ops'`.

- [ ] **Step 3: Write ops and optical**

`src/logomaker/kit/ops.py`:

```python
"""Boolean operations, strokes, transforms and alignment. Every function returns a new Shape."""
from __future__ import annotations

import skia

from .primitives import stroked_path
from .shape import Box, Shape


def _op(a: skia.Path, b: skia.Path, op: skia.PathOp) -> skia.Path:
    result = skia.Op(a, b, op)
    if result is None:
        raise ValueError("boolean path operation failed")
    return result


def union(*shapes: Shape) -> Shape:
    live = [s for s in shapes if not s.is_empty]
    if not live:
        return Shape.empty()
    acc = skia.Path(live[0].path)
    for s in live[1:]:
        acc = _op(acc, s.path, skia.PathOp.kUnion_PathOp)
    return Shape(skia.Simplify(acc), sum(s.free_segments for s in live))


def _binary(a: Shape, b: Shape, op: skia.PathOp) -> Shape:
    return Shape(skia.Simplify(_op(a.path, b.path, op)), a.free_segments + b.free_segments)


def subtract(a: Shape, b: Shape) -> Shape:
    return _binary(a, b, skia.PathOp.kDifference_PathOp)


def intersect(a: Shape, b: Shape) -> Shape:
    return _binary(a, b, skia.PathOp.kIntersect_PathOp)


def xor(a: Shape, b: Shape) -> Shape:
    return _binary(a, b, skia.PathOp.kXOR_PathOp)


def stroke(shape: Shape, width: float, cap: str = "butt", join: str = "miter", miter_limit: float = 4) -> Shape:
    return Shape(stroked_path(shape.path, width, cap, join, miter_limit), shape.free_segments)


def offset(shape: Shape, distance: float) -> Shape:
    if distance == 0:
        return shape.copy()
    band = stroke(shape, 2 * abs(distance), join="round")
    return union(shape, band) if distance > 0 else subtract(shape, band)


def translate(shape: Shape, dx: float, dy: float) -> Shape:
    return shape.transformed(skia.Matrix.Translate(dx, dy))


def rotate(shape: Shape, degrees: float, cx: float = 0, cy: float = 0) -> Shape:
    m = skia.Matrix.Translate(cx, cy)
    m.preRotate(degrees)
    m.preTranslate(-cx, -cy)
    return shape.transformed(m)


def scale(shape: Shape, sx: float, sy: float | None = None, cx: float = 0, cy: float = 0) -> Shape:
    m = skia.Matrix.Translate(cx, cy)
    m.preScale(sx, sx if sy is None else sy)
    m.preTranslate(-cx, -cy)
    return shape.transformed(m)


def mirror_x(shape: Shape, axis: float = 0.0) -> Shape:
    """Mirror across the vertical line x = axis."""
    return scale(shape, -1, 1, cx=axis)


def mirror_y(shape: Shape, axis: float = 0.0) -> Shape:
    """Mirror across the horizontal line y = axis."""
    return scale(shape, 1, -1, cy=axis)


def align(shape: Shape, to: Shape | Box, edge: str) -> Shape:
    tb = to if isinstance(to, Box) else to.bounds
    sb = shape.bounds
    moves = {
        "left": (tb.x0 - sb.x0, 0.0),
        "right": (tb.x1 - sb.x1, 0.0),
        "bottom": (0.0, tb.y0 - sb.y0),
        "top": (0.0, tb.y1 - sb.y1),
        "center": (tb.cx - sb.cx, 0.0),
        "middle": (0.0, tb.cy - sb.cy),
    }
    if edge not in moves:
        raise ValueError(f"edge must be one of {sorted(moves)}, got {edge!r}")
    return translate(shape, *moves[edge])


def center(shape: Shape, cx: float = 0, cy: float = 0, optical: bool = False) -> Shape:
    if optical:
        rx, ry = shape.centroid
    else:
        b = shape.bounds
        rx, ry = b.cx, b.cy
    return translate(shape, cx - rx, cy - ry)


def fit(shape: Shape, w: float, h: float, cx: float = 0, cy: float = 0) -> Shape:
    b = shape.bounds
    factor = min(w / b.w, h / b.h)
    return center(scale(shape, factor, cx=b.cx, cy=b.cy), cx, cy)
```

`src/logomaker/kit/optical.py`:

```python
"""Optical corrections (see .claude/skills/logo/reference/craft.md): overshoot, stroke compensation, optical centre."""
from __future__ import annotations

from dataclasses import dataclass

from .ops import scale
from .shape import Shape


def overshoot(shape: Shape, amount: float = 0.015) -> Shape:
    """Scale a round or pointed part about its own centre so it visually matches flat neighbours."""
    b = shape.bounds
    return scale(shape, 1 + amount, cx=b.cx, cy=b.cy)


@dataclass(frozen=True)
class StrokeWidths:
    vertical: float
    horizontal: float
    curve: float


def compensate_stroke(base_width: float, horizontal_factor: float = 0.92, curve_factor: float = 1.05) -> StrokeWidths:
    """Horizontals look heavier than verticals and curves look thinner; return widths that read as equal."""
    return StrokeWidths(vertical=base_width, horizontal=base_width * horizontal_factor, curve=base_width * curve_factor)


def optical_center(shape: Shape) -> tuple[float, float]:
    return shape.centroid
```

Replace `src/logomaker/kit/__init__.py` with:

```python
"""Geometry kit. `from logomaker.kit import *` gives concept modules everything they need."""
from .shape import Box, Shape, fmt  # noqa: F401
from .primitives import (  # noqa: F401
    arc, bezier, circle, line, polygon, polyline, rect, rect_centered, regular_polygon, ring, rrect, rrect_centered,
    snap, snap_angle, wedge,
)
from .ops import align, center, fit, intersect, mirror_x, mirror_y, offset, rotate, scale, stroke, subtract, translate, union, xor  # noqa: F401
from .optical import StrokeWidths, compensate_stroke, optical_center, overshoot  # noqa: F401

__all__ = [
    "Box", "Shape", "fmt",
    "arc", "bezier", "circle", "line", "polygon", "polyline", "rect", "rect_centered", "regular_polygon", "ring",
    "rrect", "rrect_centered", "snap", "snap_angle", "wedge",
    "align", "center", "fit", "intersect", "mirror_x", "mirror_y", "offset", "rotate", "scale", "stroke", "subtract",
    "translate", "union", "xor",
    "StrokeWidths", "compensate_stroke", "optical_center", "overshoot",
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_kit_ops.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/kit tests/test_kit_ops.py
git commit -m "feat: kit booleans, strokes, transforms, alignment and optical helpers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Font catalogue, cache, resolution and fetch

**Files:**
- Create: `scripts/build_catalog.py`, `assets/fonts/catalog.json` (generated), `src/logomaker/fonts.py`
- Create: `tests/fixtures/fonts/firacode/FiraCode[wght].ttf` (copied from `~/Library/Fonts/FiraCode-VF.ttf`), `tests/fixtures/fonts/firacode/OFL.txt`
- Modify: `src/logomaker/cli.py` (add the `fonts` group)
- Test: `tests/test_fonts.py`

**Interfaces:**
- Consumes: `paths.ProjectPaths`, `output.CliError`, `EXIT_EXTERNAL`.
- Produces: `fonts.FontFamily(family, slug, category, license, personality, google_dir)`, `fonts.FontFile(path, family, variable, italic, weight)`, `fonts.family_slug(family) -> str`, `fonts.load_catalog(paths) -> list[FontFamily]`, `fonts.find_family(paths, family) -> FontFamily | None`, `fonts.list_fonts(paths, category=None, personality=None) -> list[FontFamily]`, `fonts.family_dir(paths, family) -> Path`, `fonts.cached_files(paths, family) -> list[Path]`, `fonts.font_path(paths, family, weight=400, italic=False) -> FontFile` (raises `CliError(code=3)` with `run: logomaker fonts fetch <Family>` when uncached), `fonts.fetch(paths, family, timeout=30.0) -> dict`. CLI: `fonts list [--category] [--personality]`, `fonts fetch <Family>`.
- Variable fonts are used directly at any weight (Task 6 passes the weight to fontTools and HarfBuzz); no static instances are generated.

- [ ] **Step 1: Vendor the fixture font**

```bash
mkdir -p tests/fixtures/fonts/firacode
cp ~/Library/Fonts/FiraCode-VF.ttf "tests/fixtures/fonts/firacode/FiraCode[wght].ttf"
curl -fsSL https://raw.githubusercontent.com/google/fonts/main/ofl/firacode/OFL.txt -o tests/fixtures/fonts/firacode/OFL.txt
uv run python -c "from fontTools.ttLib import TTFont; f=TTFont('tests/fixtures/fonts/firacode/FiraCode[wght].ttf'); print([a.axisTag for a in f['fvar'].axes])"
```
Expected: `['wght']`.

- [ ] **Step 2: Write the catalogue generator and run it**

`scripts/build_catalog.py`:

```python
"""Generate assets/fonts/catalog.json: logo-grade open families (docs/research/03-deliverable-spec.md section 4.4)."""
from __future__ import annotations

import json
import re
from pathlib import Path

BASE_TAGS = {
    "geometric sans": ["modern", "tech", "confident", "startup", "clean"],
    "grotesk": ["neutral", "editorial", "serious", "swiss"],
    "humanist sans": ["warm", "approachable", "trustworthy", "civic"],
    "transitional serif": ["established", "credible", "publishing", "finance"],
    "old-style serif": ["heritage", "literary", "artisanal", "hospitality"],
    "didone display": ["luxury", "fashion", "editorial", "elegant"],
    "slab": ["sturdy", "craft", "industrial", "americana", "outdoors"],
    "display": ["loud", "distinctive", "entertainment", "sports", "streetwear"],
    "mono": ["technical", "developer", "data", "retro-futurist"],
    "rounded": ["friendly", "playful", "kids", "food", "wellness"],
}

# (family, category, google_dir or None to probe ofl/apache/ufl, extra personality tags)
FAMILIES = [
    ("Montserrat", "geometric sans", "ofl/montserrat", []),
    ("Poppins", "geometric sans", "ofl/poppins", ["rounded-geometric"]),
    ("Outfit", "geometric sans", "ofl/outfit", ["rounded-geometric"]),
    ("Jost", "geometric sans", "ofl/jost", ["futura-like"]),
    ("Plus Jakarta Sans", "geometric sans", "ofl/plusjakartasans", ["friendly"]),
    ("Sora", "geometric sans", "ofl/sora", ["crisp"]),
    ("DM Sans", "geometric sans", "ofl/dmsans", ["ui"]),
    ("Manrope", "geometric sans", "ofl/manrope", ["ui"]),
    ("Urbanist", "geometric sans", "ofl/urbanist", []),
    ("Figtree", "geometric sans", "ofl/figtree", ["friendly"]),
    ("Inter", "grotesk", "ofl/inter", ["ui"]),
    ("Space Grotesk", "grotesk", "ofl/spacegrotesk", ["quirky", "tech"]),
    ("Work Sans", "grotesk", "ofl/worksans", []),
    ("Archivo", "grotesk", "ofl/archivo", ["wide"]),
    ("Familjen Grotesk", "grotesk", "ofl/familjengrotesk", []),
    ("Bricolage Grotesque", "grotesk", "ofl/bricolagegrotesque", ["quirky", "character"]),
    ("Instrument Sans", "grotesk", "ofl/instrumentsans", []),
    ("Public Sans", "grotesk", "ofl/publicsans", ["civic"]),
    ("IBM Plex Sans", "grotesk", "ofl/ibmplexsans", ["corporate"]),
    ("Roboto", "grotesk", None, ["ui"]),
    ("Geist", "grotesk", "ofl/geist", ["ui", "tech"]),
    ("Open Sans", "humanist sans", "ofl/opensans", []),
    ("Source Sans 3", "humanist sans", "ofl/sourcesans3", []),
    ("Lato", "humanist sans", "ofl/lato", []),
    ("Fira Sans", "humanist sans", "ofl/firasans", []),
    ("Nunito Sans", "humanist sans", "ofl/nunitosans", []),
    ("Alegreya Sans", "humanist sans", "ofl/alegreyasans", ["literary"]),
    ("PT Sans", "humanist sans", "ofl/ptsans", []),
    ("Cabin", "humanist sans", "ofl/cabin", []),
    ("Inclusive Sans", "humanist sans", "ofl/inclusivesans", ["accessible"]),
    ("Atkinson Hyperlegible", "humanist sans", "ofl/atkinsonhyperlegible", ["accessible"]),
    ("Libre Baskerville", "transitional serif", "ofl/librebaskerville", []),
    ("Source Serif 4", "transitional serif", "ofl/sourceserif4", []),
    ("Merriweather", "transitional serif", "ofl/merriweather", []),
    ("Lora", "transitional serif", "ofl/lora", ["calligraphic"]),
    ("Newsreader", "transitional serif", "ofl/newsreader", ["editorial"]),
    ("Literata", "transitional serif", "ofl/literata", []),
    ("Spectral", "transitional serif", "ofl/spectral", []),
    ("Crimson Pro", "transitional serif", "ofl/crimsonpro", []),
    ("Libre Caslon Text", "transitional serif", "ofl/librecaslontext", []),
    ("EB Garamond", "old-style serif", "ofl/ebgaramond", []),
    ("Cormorant", "old-style serif", "ofl/cormorant", ["delicate"]),
    ("Cardo", "old-style serif", "ofl/cardo", []),
    ("Alegreya", "old-style serif", "ofl/alegreya", []),
    ("Crimson Text", "old-style serif", "ofl/crimsontext", []),
    ("Playfair Display", "didone display", "ofl/playfairdisplay", []),
    ("Bodoni Moda", "didone display", "ofl/bodonimoda", []),
    ("DM Serif Display", "didone display", "ofl/dmserifdisplay", []),
    ("Abril Fatface", "didone display", "ofl/abrilfatface", ["heavy"]),
    ("Instrument Serif", "didone display", "ofl/instrumentserif", ["condensed"]),
    ("Gilda Display", "didone display", "ofl/gildadisplay", []),
    ("Prata", "didone display", "ofl/prata", []),
    ("Fraunces", "didone display", "ofl/fraunces", ["soft", "wonky"]),
    ("Roboto Slab", "slab", None, []),
    ("Zilla Slab", "slab", "ofl/zillaslab", []),
    ("Arvo", "slab", "ofl/arvo", []),
    ("Bitter", "slab", "ofl/bitter", []),
    ("Aleo", "slab", "ofl/aleo", []),
    ("Josefin Slab", "slab", "ofl/josefinslab", ["retro"]),
    ("Alfa Slab One", "slab", "ofl/alfaslabone", ["heavy"]),
    ("Syne", "display", "ofl/syne", ["art", "bold"]),
    ("Unbounded", "display", "ofl/unbounded", ["wide", "bold"]),
    ("Bebas Neue", "display", "ofl/bebasneue", ["condensed"]),
    ("Anton", "display", "ofl/anton", ["condensed", "heavy"]),
    ("Oswald", "display", "ofl/oswald", ["condensed"]),
    ("Archivo Black", "display", "ofl/archivoblack", ["heavy"]),
    ("Righteous", "display", "ofl/righteous", ["retro"]),
    ("Climate Crisis", "display", "ofl/climatecrisis", ["activist", "heavy"]),
    ("Rozha One", "display", "ofl/rozhaone", ["heavy"]),
    ("Ultra", "display", "ofl/ultra", ["heavy"]),
    ("Space Mono", "mono", "ofl/spacemono", ["quirky"]),
    ("JetBrains Mono", "mono", "ofl/jetbrainsmono", ["code"]),
    ("IBM Plex Mono", "mono", "ofl/ibmplexmono", ["corporate"]),
    ("Azeret Mono", "mono", "ofl/azeretmono", []),
    ("DM Mono", "mono", "ofl/dmmono", []),
    ("Roboto Mono", "mono", None, []),
    ("Fira Code", "mono", "ofl/firacode", ["ligatures", "code"]),
    ("Geist Mono", "mono", "ofl/geistmono", ["tech"]),
    ("Martian Mono", "mono", "ofl/martianmono", ["wide"]),
    ("Nunito", "rounded", "ofl/nunito", []),
    ("Quicksand", "rounded", "ofl/quicksand", ["light"]),
    ("Varela Round", "rounded", "ofl/varelaround", []),
    ("Comfortaa", "rounded", "ofl/comfortaa", ["geometric"]),
    ("Fredoka", "rounded", "ofl/fredoka", ["chunky"]),
    ("Baloo 2", "rounded", "ofl/baloo2", ["chunky"]),
    ("M PLUS Rounded 1c", "rounded", "ofl/mplusrounded1c", ["japanese"]),
]


def slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]", "", family.lower())


def main() -> None:
    entries = []
    for family, category, google_dir, extra in FAMILIES:
        licence = "Apache" if (google_dir or "").startswith("apache/") else "UFL" if (google_dir or "").startswith("ufl/") else "OFL"
        entries.append({
            "family": family,
            "slug": slug(family),
            "category": category,
            "license": licence,
            "personality": BASE_TAGS[category] + extra,
            "google_dir": google_dir,
        })
    out = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "catalog.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"families": entries}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} families to {out}")


if __name__ == "__main__":
    main()
```

Run: `uv run python scripts/build_catalog.py`
Expected: `wrote 83 families to .../assets/fonts/catalog.json`.

- [ ] **Step 3: Write the failing tests**

`tests/test_fonts.py`:

```python
import json

import pytest
from click.testing import CliRunner

from logomaker import fonts
from logomaker.cli import main
from logomaker.output import CliError
from logomaker.paths import project

CATEGORIES = {
    "geometric sans", "grotesk", "humanist sans", "transitional serif", "old-style serif",
    "didone display", "slab", "display", "mono", "rounded",
}


def test_catalog_is_valid(project_root):
    families = fonts.load_catalog(project())
    assert len(families) >= 60
    assert len({f.slug for f in families}) == len(families)
    for f in families:
        assert f.category in CATEGORIES and len(f.personality) >= 3 and f.license in {"OFL", "Apache", "UFL"}
    assert fonts.find_family(project(), "fira code").google_dir == "ofl/firacode"


def test_list_fonts_filters(project_root):
    monos = fonts.list_fonts(project(), category="mono")
    assert {f.family for f in monos} >= {"Fira Code", "JetBrains Mono"}
    quirky = fonts.list_fonts(project(), personality="quirky")
    assert "Bricolage Grotesque" in {f.family for f in quirky}


def test_font_path_resolves_variable_fixture(project_root):
    ff = fonts.font_path(project(), "Fira Code", weight=650)
    assert ff.variable is True and ff.italic is False and ff.path.name == "FiraCode[wght].ttf"


def test_font_path_picks_nearest_static_weight(project_root):
    folder = project_root / "assets" / "fonts" / "fakesans"
    folder.mkdir()
    for style in ("Regular", "Bold", "BoldItalic", "Light"):
        (folder / f"FakeSans-{style}.ttf").write_bytes(b"")
    paths = project()
    assert fonts.font_path(paths, "Fake Sans", 650).weight == 700
    assert fonts.font_path(paths, "Fake Sans", 400).path.name == "FakeSans-Regular.ttf"
    assert fonts.font_path(paths, "Fake Sans", 700, italic=True).path.name == "FakeSans-BoldItalic.ttf"
    assert fonts.font_path(paths, "Fake Sans", 200).weight == 300


def test_font_path_missing_family_exits_3(project_root):
    with pytest.raises(CliError) as exc:
        fonts.font_path(project(), "Sora")
    assert exc.value.code == 3 and "logomaker fonts fetch Sora" in str(exc.value)


def test_fonts_list_cli(project_root):
    result = CliRunner().invoke(main, ["fonts", "list", "--category", "mono"])
    payload = json.loads(result.output)
    assert result.exit_code == 0 and any(f["family"] == "Fira Code" for f in payload["families"])


@pytest.mark.live
def test_fetch_sora_live(project_root):
    manifest = fonts.fetch(project(), "Sora")
    assert any(f["name"].endswith(".ttf") for f in manifest["files"])
    assert (project_root / "assets" / "fonts" / "sora" / "OFL.txt").is_file()
    assert fonts.font_path(project(), "Sora", 650).variable is True
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run pytest tests/test_fonts.py -q -m "not live"`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker.fonts'`.

- [ ] **Step 5: Write `fonts.py`**

`src/logomaker/fonts.py`:

```python
"""Font catalogue, local cache under assets/fonts/<slug>/, resolution by weight, and fetching from google/fonts."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
from fontTools.ttLib import TTFont

from .output import EXIT_EXTERNAL, CliError
from .paths import ProjectPaths
from .schemas import now_iso

GITHUB_CONTENTS = "https://api.github.com/repos/google/fonts/contents/{dir}"
LICENCE_FILES = {"OFL.txt", "LICENSE.txt", "UFL.txt", "LICENCE.txt"}
WEIGHT_NAMES = {
    100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
    600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black",
}
NAME_WEIGHTS = {v.lower(): k for k, v in WEIGHT_NAMES.items()}


@dataclass(frozen=True)
class FontFamily:
    family: str
    slug: str
    category: str
    license: str
    personality: list[str]
    google_dir: str | None


@dataclass(frozen=True)
class FontFile:
    path: Path
    family: str
    variable: bool
    italic: bool
    weight: int | None  # None for variable fonts (any weight)


def family_slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]", "", family.lower())


def load_catalog(paths: ProjectPaths) -> list[FontFamily]:
    data = json.loads((paths.fonts / "catalog.json").read_text(encoding="utf-8"))
    return [FontFamily(**entry) for entry in data["families"]]


def find_family(paths: ProjectPaths, family: str) -> FontFamily | None:
    slug = family_slug(family)
    return next((f for f in load_catalog(paths) if f.slug == slug), None)


def list_fonts(paths: ProjectPaths, category: str | None = None, personality: str | None = None) -> list[FontFamily]:
    out = load_catalog(paths)
    if category:
        out = [f for f in out if f.category == category]
    if personality:
        out = [f for f in out if personality in f.personality]
    return out


def family_dir(paths: ProjectPaths, family: str) -> Path:
    return paths.fonts / family_slug(family)


def cached_files(paths: ProjectPaths, family: str) -> list[Path]:
    folder = family_dir(paths, family)
    return sorted(folder.glob("*.ttf")) if folder.is_dir() else []


def _describe(path: Path) -> tuple[bool, bool, int | None]:
    """(variable, italic, weight) from google/fonts file naming: Family[wght].ttf or Family-StyleItalic.ttf."""
    stem = path.stem
    if "[" in stem:
        return True, "italic" in stem.lower().split("[")[0], None
    style = stem.rsplit("-", 1)[1] if "-" in stem else "Regular"
    italic = style.lower().endswith("italic")
    base = style[:-6] if italic else style
    weight = 400 if base in ("", "Italic") else NAME_WEIGHTS.get(base.lower(), 400)
    return False, italic, weight


def font_path(paths: ProjectPaths, family: str, weight: int = 400, italic: bool = False) -> FontFile:
    files = cached_files(paths, family)
    if not files:
        raise CliError(f"Font family {family!r} is not cached. run: logomaker fonts fetch {family}", code=EXIT_EXTERNAL)
    described = [(p, *_describe(p)) for p in files]
    variables = [d for d in described if d[1] and d[2] == italic]
    if variables:
        p, _, it, _ = variables[0]
        return FontFile(path=p, family=family, variable=True, italic=it, weight=None)
    statics = [d for d in described if not d[1] and d[2] == italic] or [d for d in described if not d[1]]
    if not statics:
        p, var, it, w = described[0]
        return FontFile(path=p, family=family, variable=var, italic=it, weight=w)
    p, _, it, w = min(statics, key=lambda d: abs((d[3] or 400) - weight))
    return FontFile(path=p, family=family, variable=False, italic=it, weight=w)


def _candidate_dirs(paths: ProjectPaths, family: str) -> list[str]:
    slug = family_slug(family)
    entry = find_family(paths, family)
    dirs = [entry.google_dir] if entry and entry.google_dir else []
    dirs += [f"ofl/{slug}", f"apache/{slug}", f"ufl/{slug}"]
    return list(dict.fromkeys(dirs))


def fetch(paths: ProjectPaths, family: str, timeout: float = 30.0) -> dict:
    folder = family_dir(paths, family)
    listing = None
    used_dir = None
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "logomaker"}) as client:
        for d in _candidate_dirs(paths, family):
            try:
                resp = client.get(GITHUB_CONTENTS.format(dir=d))
            except httpx.HTTPError as err:
                raise CliError(f"Network error fetching {family}: {err}", code=EXIT_EXTERNAL) from err
            if resp.status_code == 200:
                listing, used_dir = resp.json(), d
                break
        if listing is None:
            raise CliError(f"Family {family!r} not found in google/fonts (tried {', '.join(_candidate_dirs(paths, family))})", code=EXIT_EXTERNAL)
        wanted = [e for e in listing if e["name"].endswith(".ttf") or e["name"] in LICENCE_FILES]
        if not any(e["name"].endswith(".ttf") for e in wanted):
            raise CliError(f"No .ttf files listed for {family} in {used_dir}", code=EXIT_EXTERNAL)
        folder.mkdir(parents=True, exist_ok=True)
        files = []
        for entry in wanted:
            try:
                data = client.get(entry["download_url"]).raise_for_status().content
            except httpx.HTTPError as err:
                raise CliError(f"Network error downloading {entry['name']}: {err}", code=EXIT_EXTERNAL) from err
            target = folder / entry["name"]
            target.write_bytes(data)
            if target.suffix == ".ttf":
                try:
                    TTFont(str(target)).close()
                except Exception as err:  # noqa: BLE001
                    target.unlink()
                    raise CliError(f"{entry['name']} is not a valid TrueType file: {err}", code=EXIT_EXTERNAL) from err
            files.append({"name": entry["name"], "url": entry["download_url"], "sha256": hashlib.sha256(data).hexdigest()})
    manifest = {"family": family, "google_dir": used_dir, "fetched_at": now_iso(), "files": files}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def family_to_dict(f: FontFamily) -> dict:
    return asdict(f)
```

- [ ] **Step 6: Add the `fonts` group to the CLI**

Add to `src/logomaker/cli.py` (import `from . import fonts as fontlib`):

```python
@main.group("fonts")
def fonts_group() -> None:
    """Font catalogue and cache."""


@fonts_group.command("list")
@click.option("--category", default=None)
@click.option("--personality", default=None)
@command
def fonts_list(category: str | None, personality: str | None) -> None:
    paths = project()
    families = fontlib.list_fonts(paths, category, personality)
    emit({"families": [
        {**fontlib.family_to_dict(f), "cached": bool(fontlib.cached_files(paths, f.family))} for f in families
    ]})


@fonts_group.command("fetch")
@click.argument("family")
@command
def fonts_fetch(family: str) -> None:
    emit({"manifest": fontlib.fetch(project(), family)})
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_fonts.py -q -m "not live"` then `uv run pytest tests/test_fonts.py -q -m live`
Expected: 6 passed, then 1 passed (the live fetch writes `assets/fonts/sora/` in the temp project only).

- [ ] **Step 8: Commit**

```bash
git add scripts/build_catalog.py assets/fonts/catalog.json src/logomaker/fonts.py src/logomaker/cli.py tests/test_fonts.py "tests/fixtures/fonts/firacode/FiraCode[wght].ttf" tests/fixtures/fonts/firacode/OFL.txt
git commit -m "feat: font catalogue, cache resolution and google/fonts fetch

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Text from real fonts (HarfBuzz shaping, fontTools outlines)

**Files:**
- Create: `src/logomaker/kit/text.py`
- Modify: `src/logomaker/kit/__init__.py` (re-export `TextShape`, `text`, `glyph`)
- Test: `tests/test_kit_text.py`

**Interfaces:**
- Consumes: `fonts.font_path(paths, family, weight, italic) -> FontFile`, `paths.project()`, `shape.Shape`, `shape.Box`.
- Produces: `text.TextShape(Shape)` with attributes `advance: float`, `cap_height: float`, `x_height: float`, `glyph_bounds: list[Box]`, `font: str`; `text.text(string, family, weight=400, cap_height=200.0, tracking=0.0, kern=None, features=("kern", "liga"), italic=False) -> TextShape`; `text.glyph(char, family, weight=400, cap_height=200.0, italic=False) -> TextShape`. The baseline is y = 0 and the text starts at x = 0. `tracking` and `kern` values are in 1/1000 em. Transforming a `TextShape` with `ops` returns a plain `Shape`; capture metrics before transforming.

- [ ] **Step 1: Write the failing tests**

`tests/test_kit_text.py`:

```python
import math

import pytest

from logomaker.kit.ops import translate
from logomaker.kit.text import TextShape, glyph, text
from logomaker.output import CliError

FIRA_CAP = 1374  # OS/2 sCapHeight of the fixture font
FIRA_UPEM = 1950
FIRA_ADVANCE = 1200  # monospace advance in font units


def test_cap_height_scales_the_glyphs(project_root):
    h = text("H", "Fira Code", cap_height=200)
    assert isinstance(h, TextShape)
    assert math.isclose(h.bounds.h, 200, abs_tol=1.0)
    assert math.isclose(h.bounds.y0, 0, abs_tol=1.0)  # baseline at y = 0
    assert math.isclose(h.cap_height, 200) and math.isclose(h.x_height, 1050 / FIRA_CAP * 200, rel_tol=0.01)


def test_advance_tracking_and_kern_overrides(project_root):
    scale = 200 / FIRA_CAP
    plain = text("ABC", "Fira Code", cap_height=200)
    assert math.isclose(plain.advance, 3 * FIRA_ADVANCE * scale, rel_tol=1e-3)
    assert len(plain.glyph_bounds) == 3
    tracked = text("AB", "Fira Code", cap_height=200, tracking=100)
    base = text("AB", "Fira Code", cap_height=200)
    assert math.isclose(tracked.advance - base.advance, 100 / 1000 * FIRA_UPEM * scale, rel_tol=1e-3)
    kerned = text("AB", "Fira Code", cap_height=200, kern={"AB": -200})
    assert math.isclose(base.advance - kerned.advance, 200 / 1000 * FIRA_UPEM * scale, rel_tol=1e-3)
    assert kerned.glyph_bounds[1].x0 < base.glyph_bounds[1].x0


def test_features_change_shapes(project_root):
    with_calt = text("->", "Fira Code", features=("calt",))
    without = text("->", "Fira Code", features=())
    assert with_calt.to_path_data() != without.to_path_data()


def test_variable_weight_changes_stem_width(project_root):
    light = glyph("H", "Fira Code", weight=300, cap_height=200)
    bold = glyph("H", "Fira Code", weight=700, cap_height=200)
    assert bold.area > light.area * 1.3


def test_missing_family_exits_3(project_root):
    with pytest.raises(CliError) as exc:
        text("Sora", "Sora")
    assert exc.value.code == 3 and "run: logomaker fonts fetch Sora" in str(exc.value)


def test_transform_keeps_geometry(project_root):
    t = text("Go", "Fira Code", cap_height=100)
    moved = translate(t, 50, 0)
    assert math.isclose(moved.bounds.x0, t.bounds.x0 + 50)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_kit_text.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker.kit.text'`.

- [ ] **Step 3: Write `text.py`**

`src/logomaker/kit/text.py`:

```python
"""Type set from real fonts: HarfBuzz shaping (kerning, ligatures, variations) and fontTools outlines into Skia paths."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import skia
import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from .. import fonts as fontlib
from ..paths import project
from .shape import Box, Shape


class _SkiaPen(BasePen):
    def __init__(self, glyph_set):
        super().__init__(glyph_set)
        self.path = skia.Path()

    def _moveTo(self, p):
        self.path.moveTo(*p)

    def _lineTo(self, p):
        self.path.lineTo(*p)

    def _curveToOne(self, p1, p2, p3):
        self.path.cubicTo(*p1, *p2, *p3)

    def _qCurveToOne(self, p1, p2):
        self.path.quadTo(*p1, *p2)

    def _closePath(self):
        self.path.close()


@dataclass(frozen=True)
class FontMetrics:
    upem: int
    cap_height: float
    x_height: float


@lru_cache(maxsize=16)
def _ttfont(path: str) -> TTFont:
    return TTFont(path)


@lru_cache(maxsize=16)
def _hb_face(path: str) -> hb.Face:
    return hb.Face(hb.Blob.from_file_path(path))


def _glyph_height(tt: TTFont, name: str) -> float | None:
    gs = tt.getGlyphSet()
    if name not in gs:
        return None
    pen = BoundsPen(gs)
    gs[name].draw(pen)
    return pen.bounds[3] if pen.bounds else None


def _metrics(tt: TTFont) -> FontMetrics:
    upem = tt["head"].unitsPerEm
    os2 = tt["OS/2"] if "OS/2" in tt else None
    cap = getattr(os2, "sCapHeight", 0) or _glyph_height(tt, "H") or upem * 0.7
    x = getattr(os2, "sxHeight", 0) or _glyph_height(tt, "x") or cap * 0.5
    return FontMetrics(upem=upem, cap_height=float(cap), x_height=float(x))


class TextShape(Shape):
    __slots__ = ("advance", "cap_height", "x_height", "glyph_bounds", "font")

    def __init__(self, path: skia.Path, *, advance: float, cap_height: float, x_height: float, glyph_bounds: list[Box], font: str):
        super().__init__(path, 0)
        self.advance = advance
        self.cap_height = cap_height
        self.x_height = x_height
        self.glyph_bounds = glyph_bounds
        self.font = font

    def copy(self) -> "TextShape":
        return TextShape(skia.Path(self.path), advance=self.advance, cap_height=self.cap_height, x_height=self.x_height,
                         glyph_bounds=list(self.glyph_bounds), font=self.font)


def text(
    string: str,
    family: str,
    weight: int = 400,
    cap_height: float = 200.0,
    tracking: float = 0.0,
    kern: dict[str, float] | None = None,
    features: tuple[str, ...] = ("kern", "liga"),
    italic: bool = False,
) -> TextShape:
    """Shape `string` with HarfBuzz and outline it with fontTools. Baseline y = 0, start x = 0, scaled to `cap_height`."""
    ff = fontlib.font_path(project(), family, weight, italic)
    tt = _ttfont(str(ff.path))
    metrics = _metrics(tt)
    scale = cap_height / metrics.cap_height
    location = {"wght": weight} if ff.variable else None
    glyph_set = tt.getGlyphSet(location=location) if location else tt.getGlyphSet()
    order = tt.getGlyphOrder()

    font = hb.Font(_hb_face(str(ff.path)))
    if ff.variable:
        font.set_variations({"wght": weight})
    buf = hb.Buffer()
    buf.add_str(string)
    buf.guess_segment_properties()
    hb.shape(font, buf, {f: True for f in features})

    path = skia.Path()
    bounds: list[Box] = []
    x = 0.0
    infos, positions = buf.glyph_infos, buf.glyph_positions
    track_units = tracking / 1000 * metrics.upem
    for i, (info, pos) in enumerate(zip(infos, positions)):
        pen = _SkiaPen(glyph_set)
        tp = TransformPen(pen, (scale, 0, 0, scale, (x + pos.x_offset) * scale, pos.y_offset * scale))
        glyph_set[order[info.codepoint]].draw(tp)
        if not pen.path.isEmpty():
            r = pen.path.computeTightBounds()
            bounds.append(Box(r.left(), r.top(), r.right(), r.bottom()))
            path.addPath(pen.path)
        advance = float(pos.x_advance)
        if i < len(infos) - 1:
            advance += track_units
            if kern:
                pair = string[info.cluster] + string[infos[i + 1].cluster]
                advance += kern.get(pair, 0.0) / 1000 * metrics.upem
        x += advance
    simplified = skia.Simplify(path)
    return TextShape(
        simplified if simplified is not None else path,
        advance=x * scale,
        cap_height=cap_height,
        x_height=metrics.x_height * scale,
        glyph_bounds=bounds,
        font=f"{family} {weight}{' italic' if italic else ''}",
    )


def glyph(char: str, family: str, weight: int = 400, cap_height: float = 200.0, italic: bool = False) -> TextShape:
    return text(char, family, weight=weight, cap_height=cap_height, features=(), italic=italic)
```

Add to `src/logomaker/kit/__init__.py`:

```python
from .text import TextShape, glyph, text  # noqa: F401
```

and append `"TextShape", "glyph", "text"` to `__all__`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_kit_text.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/kit tests/test_kit_text.py
git commit -m "feat: real-font text shaping and outlines in the kit

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `Mark`, lockups, SVG output, concept modules, `concept build`

**Files:**
- Create: `src/logomaker/kit/mark.py`, `src/logomaker/kit/concept.py`
- Create: `tests/fixtures/concepts/good/concept.py`, `tests/fixtures/concepts/raises/concept.py`, `tests/fixtures/concepts/nometa/concept.py`
- Modify: `src/logomaker/kit/__init__.py` (re-export), `src/logomaker/cli.py` (add the `concept` group), `tests/conftest.py` (add `install_concept`)
- Test: `tests/test_kit_mark.py`, `tests/test_concept.py`

**Interfaces:**
- Consumes: `Shape`, `Box`, `fmt`, `TextShape`, `ops.translate`, `registry.new_brand`, `paths.ProjectPaths`, `output.CliError`.
- Produces: `mark.ROLES`, `mark.LOCKUPS`, `mark.VARIANTS`, `mark.Composite(parts: list[tuple[Shape, str]])`, `mark.Placed(name, shape, role)`, `mark.Mark(symbol=None, wordmark=None, tagline=None, lockup="horizontal", gap=None, align="center", roles=None)` with `x_unit`, `layout() -> list[Placed]`, `bounds() -> Box`, `with_lockup(lockup) -> Mark`, `without_wordmark() -> Mark`, `to_svg(variant="color", palette=None, padding=0.0, dark_palette=None) -> str`, `geometry() -> dict`; `mark.fill_for(role, variant, palette) -> str`; `concept.Meta`, `concept.Params`, `concept.ConceptModule`, `concept.TIER_NAMES`, `concept.load_concept(folder) -> ConceptModule`, `concept.build_tiers(module, overrides=None) -> dict[str, Mark]`, `concept.build_outputs(marks) -> dict[str, Mark]` (keys `full-lockup`, `full-horizontal`, `full-stacked`, `full-symbol`, `full-wordmark`, `compact`, `small`, `favicon` as available), `concept.write_build(folder, outputs, variants=("black","white"), palette=None, dark_palette=None) -> dict`, `concept.concept_folder(paths, slug, name) -> Path`. CLI: `concept build <slug> <concept> [--variants black,white]`.
- A palette is a plain `dict[str, str]` mapping roles to hex colours; Task 8 derives palettes from `tokens.json`.

- [ ] **Step 1: Add fixture concepts and the conftest helper**

`tests/fixtures/concepts/good/concept.py`:

```python
from logomaker.kit import *

META = Meta(slug="good", idea="A ring with a gap holding the name", logo_type="combination", motifs=["ring"])
PARAMS = Params(stroke=90, gap=None)
TIERS = {
    "full": {},
    "compact": {},
    "small": {"stroke": 130},
    "favicon": {"stroke": 170, "wordmark": False},
}


def build(p):
    symbol = ring(0, 0, 400, p.stroke, start=30, end=330)
    word = text("Good", family="Fira Code", weight=600, cap_height=180)
    return Mark(symbol=symbol, wordmark=word, lockup="horizontal", gap=p.gap)
```

`tests/fixtures/concepts/raises/concept.py`:

```python
from logomaker.kit import *

META = Meta(slug="raises", idea="broken on purpose", logo_type="abstract", motifs=[])
PARAMS = Params()
TIERS = {"full": {}}


def build(p):
    raise RuntimeError("boom")
```

`tests/fixtures/concepts/nometa/concept.py`:

```python
from logomaker.kit import *

PARAMS = Params()
TIERS = {"full": {}}


def build(p):
    return Mark(symbol=circle(0, 0, 100))
```

Append to `tests/conftest.py`:

```python
def install_concept(project_root: Path, fixture: str, slug: str = "keystone", name: str = "01-good") -> Path:
    """Create brand `slug` (if needed) and copy tests/fixtures/concepts/<fixture> to brands/<slug>/concepts/<name>."""
    from logomaker import registry
    from logomaker.paths import project

    if not (project_root / "brands" / slug).exists():
        registry.new_brand(project(), slug.title(), slug=slug)
    target = project_root / "brands" / slug / "concepts" / name
    shutil.copytree(FIXTURES / "concepts" / fixture, target, dirs_exist_ok=True)
    return target
```

- [ ] **Step 2: Write the failing tests**

`tests/test_kit_mark.py`:

```python
import math

import pytest

from logomaker.kit.mark import Composite, Mark, fill_for
from logomaker.kit.primitives import circle, rect
from logomaker.kit.text import text


def good_mark(project_root, **kw):
    return Mark(symbol=circle(0, 0, 100), wordmark=text("Good", "Fira Code", weight=600, cap_height=180), **kw)


def test_horizontal_layout_uses_cap_height_as_gap(project_root):
    m = good_mark(project_root)
    assert m.x_unit == 180
    placed = {p.name: p for p in m.layout()}
    assert math.isclose(placed["symbol"].shape.bounds.cx, 0, abs_tol=0.01)
    assert math.isclose(placed["wordmark"].shape.bounds.x0, 100 + 180, abs_tol=0.01)
    assert math.isclose(placed["wordmark"].shape.bounds.cy, 0, abs_tol=0.01)


def test_stacked_and_single_lockups(project_root):
    m = good_mark(project_root, lockup="stacked")
    placed = {p.name: p for p in m.layout()}
    assert math.isclose(placed["wordmark"].shape.bounds.y1, -100 - 180, abs_tol=0.01)
    assert math.isclose(placed["wordmark"].shape.bounds.cx, 0, abs_tol=0.01)
    assert [p.name for p in m.with_lockup("symbol").layout()] == ["symbol"]
    assert [p.name for p in m.with_lockup("wordmark").layout()] == ["wordmark"]
    assert m.without_wordmark().lockup == "symbol" and m.without_wordmark().wordmark is None


def test_x_unit_without_wordmark_is_fifth_of_symbol_height():
    assert Mark(symbol=circle(0, 0, 100)).x_unit == 40


def test_baseline_alignment(project_root):
    m = good_mark(project_root, align="baseline")
    placed = {p.name: p for p in m.layout()}
    assert math.isclose(placed["wordmark"].shape.bounds.y0, -100, abs_tol=4.0)  # round letters overshoot the baseline slightly


def test_svg_structure_and_variants(project_root):
    m = good_mark(project_root)
    svg = m.to_svg("black")
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="')
    assert ' width=' not in svg and "<text" not in svg
    assert '<g id="symbol">' in svg and '<g id="wordmark">' in svg
    assert 'fill="#000000"' in svg and 'fill-rule="nonzero"' in svg
    assert 'fill="#ffffff"' in m.to_svg("white")
    assert 'fill="currentColor"' in m.to_svg("mono")
    assert m.to_svg("black") == m.to_svg("black")  # deterministic


def test_color_variants_need_a_palette(project_root):
    m = good_mark(project_root)
    with pytest.raises(ValueError):
        m.to_svg("color")
    svg = m.to_svg("color", palette={"primary": "#e8572a", "ink": "#1f1b18"})
    assert 'fill="#e8572a"' in svg and 'fill="#1f1b18"' in svg
    dark = m.to_svg("color", palette={"primary": "#e8572a", "ink": "#1f1b18"}, dark_palette={"primary": "#ff7a45", "ink": "#ffffff"})
    assert "prefers-color-scheme: dark" in dark and ".r-primary{fill:#ff7a45}" in dark and 'class="r-ink"' in dark
    assert fill_for("accent", "mono", None) == "currentColor"


def test_padding_and_viewbox():
    m = Mark(symbol=rect(0, 0, 100, 50))
    assert 'viewBox="-50 -25 100 50"' in m.to_svg("black")
    assert 'viewBox="-60 -35 120 70"' in m.to_svg("black", padding=10)


def test_composite_roles_and_geometry():
    sym = Composite([(circle(0, 0, 100), "primary"), (rect(-20, -20, 40, 40), "secondary")])
    m = Mark(symbol=sym)
    svg = m.to_svg("color", palette={"primary": "#111111", "secondary": "#222222"})
    assert svg.count("<path") == 2 and 'fill="#222222"' in svg
    geo = m.geometry()
    assert geo["lockup"] == "horizontal" and [p["name"] for p in geo["parts"]] == ["symbol", "symbol-2"]
    assert geo["parts"][1]["anchors"] == 4 and len(geo["parts"][1]["straight_segments"]) == 4
    assert geo["parts"][1]["straight_segments"][0]["angle"] in (0.0, 90.0)
    assert geo["roles"] == ["primary", "secondary"]


def test_empty_symbol_is_rejected():
    from logomaker.kit.shape import Shape

    with pytest.raises(ValueError):
        Mark(symbol=Shape.empty())
    with pytest.raises(ValueError):
        Mark()
```

`tests/test_concept.py`:

```python
import json

from click.testing import CliRunner

from logomaker.cli import main
from logomaker.kit import concept as conceptlib
from logomaker.paths import project
from tests.conftest import install_concept


def run(*args):
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, json.loads(result.output)


def test_load_and_build_tiers(project_root):
    folder = install_concept(project_root, "good")
    module = conceptlib.load_concept(folder)
    assert module.meta.slug == "good" and module.params.stroke == 90 and set(module.tiers) == {"full", "compact", "small", "favicon"}
    marks = conceptlib.build_tiers(module)
    assert marks["favicon"].wordmark is None and marks["full"].wordmark is not None
    outputs = conceptlib.build_outputs(marks)
    assert set(outputs) == {"full-lockup", "full-horizontal", "full-stacked", "full-symbol", "full-wordmark", "compact", "small", "favicon"}
    assert outputs["full-stacked"].lockup == "stacked" and outputs["full-symbol"].lockup == "symbol"


def test_params_json_overrides(project_root):
    folder = install_concept(project_root, "good")
    (folder / "params.json").write_text(json.dumps({"stroke": 50}))
    module = conceptlib.load_concept(folder)
    assert module.params.stroke == 50
    assert module.params.with_overrides(stroke=10).stroke == 10 and module.params.stroke == 50


def test_concept_build_cli_writes_files(project_root):
    install_concept(project_root, "good")
    code, payload = run("concept", "build", "keystone", "01-good")
    assert code == 0, payload
    build = project_root / "brands" / "keystone" / "concepts" / "01-good" / "build"
    assert (build / "full-lockup-black.svg").is_file() and (build / "favicon-white.svg").is_file()
    assert "full-symbol" in json.loads((build / "geometry.json").read_text())
    report = json.loads((build / "build.json").read_text())
    assert report["variants"] == ["black", "white"] and "favicon-black.svg" in report["files"]
    assert (build / "full-lockup-black.svg").read_text() == (build / "full-lockup-black.svg").read_text()


def test_broken_concept_exits_2_with_traceback(project_root):
    install_concept(project_root, "raises", name="02-raises")
    code, payload = run("concept", "build", "keystone", "02-raises")
    assert code == 2 and "RuntimeError: boom" in payload["errors"][0] and "traceback" in payload


def test_concept_without_meta_exits_2(project_root):
    install_concept(project_root, "nometa", name="03-nometa")
    code, payload = run("concept", "build", "keystone", "03-nometa")
    assert code == 2 and "META" in payload["errors"][0]


def test_unknown_concept_folder_exits_2(project_root):
    install_concept(project_root, "good")
    code, payload = run("concept", "build", "keystone", "99-missing")
    assert code == 2 and "concept.py" in payload["errors"][0]


def test_final_folder_resolves(project_root):
    install_concept(project_root, "good")
    paths = project()
    assert conceptlib.concept_folder(paths, "keystone", "01-good").name == "01-good"
    final = project_root / "brands" / "keystone" / "final"
    (final / "concept.py").write_text((project_root / "brands" / "keystone" / "concepts" / "01-good" / "concept.py").read_text())
    assert conceptlib.concept_folder(paths, "keystone", "final") == final
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_kit_mark.py tests/test_concept.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker.kit.mark'`.

- [ ] **Step 4: Write `mark.py`**

`src/logomaker/kit/mark.py`:

```python
"""Mark: symbol + wordmark (+ tagline) with lockup layout, role-based colour, SVG and geometry output."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .ops import translate
from .shape import Box, Shape, fmt
from .text import TextShape

ROLES = ("primary", "secondary", "accent", "ink", "paper")
LOCKUPS = ("horizontal", "stacked", "symbol", "wordmark")
VARIANTS = ("color", "reverse", "black", "white", "mono")
DEFAULT_ROLES = {"symbol": "primary", "wordmark": "ink", "tagline": "ink"}


class Composite:
    """A symbol made of several shapes with their own colour roles."""

    def __init__(self, parts: list[tuple[Shape, str]]):
        if not parts:
            raise ValueError("Composite needs at least one part")
        for _, role in parts:
            if role not in ROLES:
                raise ValueError(f"role must be one of {ROLES}, got {role!r}")
        self.parts = list(parts)

    @property
    def is_empty(self) -> bool:
        return all(s.is_empty for s, _ in self.parts)

    @property
    def bounds(self) -> Box:
        return Box.union(s.bounds for s, _ in self.parts if not s.is_empty)


@dataclass
class Placed:
    name: str
    shape: Shape
    role: str


def fill_for(role: str, variant: str, palette: dict[str, str] | None) -> str:
    if variant == "black":
        return "#000000"
    if variant == "white":
        return "#ffffff"
    if variant == "mono":
        return "currentColor"
    if palette is None:
        raise ValueError(f"variant {variant!r} needs a palette mapping roles to colours")
    if role not in palette:
        raise ValueError(f"palette has no colour for role {role!r}")
    return palette[role]


def _box_dict(b: Box) -> dict:
    return {"x0": round(b.x0, 3), "y0": round(b.y0, 3), "x1": round(b.x1, 3), "y1": round(b.y1, 3), "w": round(b.w, 3), "h": round(b.h, 3)}


class Mark:
    def __init__(
        self,
        symbol: Shape | Composite | None = None,
        wordmark: Shape | None = None,
        tagline: Shape | None = None,
        lockup: str = "horizontal",
        gap: float | None = None,
        align: str = "center",
        roles: dict[str, str] | None = None,
    ):
        if symbol is None and wordmark is None:
            raise ValueError("Mark needs a symbol or a wordmark")
        if symbol is not None and symbol.is_empty:
            raise ValueError("symbol is empty")
        if wordmark is not None and wordmark.is_empty:
            raise ValueError("wordmark is empty")
        if lockup not in LOCKUPS:
            raise ValueError(f"lockup must be one of {LOCKUPS}, got {lockup!r}")
        if lockup == "symbol" and symbol is None:
            raise ValueError("lockup 'symbol' needs a symbol")
        if lockup == "wordmark" and wordmark is None:
            raise ValueError("lockup 'wordmark' needs a wordmark")
        if align not in ("center", "baseline"):
            raise ValueError("align must be 'center' or 'baseline'")
        self.symbol = symbol
        self.wordmark = wordmark
        self.tagline = tagline
        self.lockup = lockup
        self.gap = gap
        self.align = align
        self.roles = {**DEFAULT_ROLES, **(roles or {})}
        for role in self.roles.values():
            if role not in ROLES:
                raise ValueError(f"role must be one of {ROLES}, got {role!r}")

    def _copy(self, **changes) -> "Mark":
        kwargs = dict(symbol=self.symbol, wordmark=self.wordmark, tagline=self.tagline, lockup=self.lockup, gap=self.gap, align=self.align, roles=self.roles)
        kwargs.update(changes)
        return Mark(**kwargs)

    def with_lockup(self, lockup: str) -> "Mark":
        return self._copy(lockup=lockup)

    def without_wordmark(self) -> "Mark":
        return self._copy(wordmark=None, tagline=None, lockup="symbol")

    def _symbol_bounds(self) -> Box:
        assert self.symbol is not None
        return self.symbol.bounds

    def _symbol_parts(self) -> list[tuple[str, Shape, str]]:
        if isinstance(self.symbol, Composite):
            return [("symbol" if i == 0 else f"symbol-{i + 1}", s, r) for i, (s, r) in enumerate(self.symbol.parts)]
        return [("symbol", self.symbol, self.roles["symbol"])]  # type: ignore[list-item]

    @property
    def x_unit(self) -> float:
        """Clear-space and gap unit: wordmark cap height, else one fifth of the symbol height."""
        if isinstance(self.wordmark, TextShape):
            return self.wordmark.cap_height
        if self.symbol is not None:
            return self._symbol_bounds().h / 5
        return self.wordmark.bounds.h  # type: ignore[union-attr]

    def layout(self) -> list[Placed]:
        gap = self.gap if self.gap is not None else self.x_unit
        placed: list[Placed] = []
        has_symbol = self.symbol is not None and self.lockup != "wordmark"
        has_word = self.wordmark is not None and self.lockup != "symbol"
        sym_box: Box | None = None
        if has_symbol:
            sb = self._symbol_bounds()
            dx, dy = -sb.cx, -sb.cy
            for name, shape, role in self._symbol_parts():
                placed.append(Placed(name, translate(shape, dx, dy), role))
            sym_box = Box(sb.x0 + dx, sb.y0 + dy, sb.x1 + dx, sb.y1 + dy)
        if has_word:
            wb = self.wordmark.bounds  # type: ignore[union-attr]
            if sym_box is not None and self.lockup == "horizontal":
                dx = sym_box.x1 + gap - wb.x0
                dy = sym_box.y0 if self.align == "baseline" else sym_box.cy - wb.cy
            elif sym_box is not None and self.lockup == "stacked":
                dx, dy = -wb.cx, sym_box.y0 - gap - wb.y1
            else:
                dx, dy = -wb.cx, -wb.cy
            word = translate(self.wordmark, dx, dy)  # type: ignore[arg-type]
            placed.append(Placed("wordmark", word, self.roles["wordmark"]))
            if self.tagline is not None:
                word_box, tb = word.bounds, self.tagline.bounds
                tdx = word_box.cx - tb.cx if (self.lockup == "stacked" or sym_box is None) else word_box.x0 - tb.x0
                tdy = word_box.y0 - gap / 2 - tb.y1
                placed.append(Placed("tagline", translate(self.tagline, tdx, tdy), self.roles["tagline"]))
        return placed

    def bounds(self) -> Box:
        return Box.union(p.shape.bounds for p in self.layout())

    def to_svg(self, variant: str = "color", palette: dict[str, str] | None = None, padding: float = 0.0, dark_palette: dict[str, str] | None = None) -> str:
        if variant not in VARIANTS:
            raise ValueError(f"variant must be one of {VARIANTS}, got {variant!r}")
        placed = self.layout()
        b = self.bounds()
        view = (b.x0 - padding, -b.y1 - padding, b.w + 2 * padding, b.h + 2 * padding)
        groups: dict[str, list[str]] = {}
        for p in placed:
            gid = "symbol" if p.name.startswith("symbol") else p.name
            cls = f' class="r-{p.role}"' if dark_palette else ""
            fill = fill_for(p.role, variant, palette)
            groups.setdefault(gid, []).append(f'<path{cls} fill="{fill}" fill-rule="nonzero" d="{p.shape.to_path_data()}"/>')
        style = ""
        if dark_palette:
            rules = "".join(f".r-{role}{{fill:{colour}}}" for role, colour in dark_palette.items())
            style = f"<style>@media (prefers-color-scheme: dark){{{rules}}}</style>"
        body = "".join(f'<g id="{gid}">{"".join(paths)}</g>' for gid, paths in groups.items())
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{fmt(view[0])} {fmt(view[1])} {fmt(view[2])} {fmt(view[3])}">{style}{body}</svg>'

    def geometry(self) -> dict:
        placed = self.layout()
        parts = []
        for p in placed:
            segments = [
                {"from": [round(x0, 3), round(y0, 3)], "to": [round(x1, 3), round(y1, 3)],
                 "angle": round(math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180, 3)}
                for (x0, y0), (x1, y1) in p.shape.straight_segments()
            ]
            cx, cy = p.shape.centroid
            parts.append({
                "name": p.name, "role": p.role, "bounds": _box_dict(p.shape.bounds), "anchors": p.shape.anchor_count(),
                "area": round(p.shape.area, 3), "centroid": [round(cx, 3), round(cy, 3)], "straight_segments": segments,
                "free_segments": p.shape.free_segments, "subpaths": [_box_dict(s.bounds) for s in p.shape.subpaths()],
            })
        wordmark = None
        if isinstance(self.wordmark, TextShape) and self.lockup != "symbol":
            wordmark = {"cap_height": self.wordmark.cap_height, "x_height": round(self.wordmark.x_height, 3),
                        "advance": round(self.wordmark.advance, 3), "font": self.wordmark.font}
        return {"lockup": self.lockup, "x_unit": round(self.x_unit, 3), "bounds": _box_dict(self.bounds()),
                "parts": parts, "wordmark": wordmark, "roles": sorted({p.role for p in placed})}
```

- [ ] **Step 5: Write `concept.py`**

`src/logomaker/kit/concept.py`:

```python
"""Concept modules: META + PARAMS + TIERS + build(p) -> Mark. Loading, tier builds and build/ output."""
from __future__ import annotations

import importlib.util
import json
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..output import CliError
from ..paths import ProjectPaths
from .mark import Mark

TIER_NAMES = ("full", "compact", "small", "favicon")


@dataclass
class Meta:
    slug: str
    idea: str
    logo_type: str
    motifs: list[str] = field(default_factory=list)
    territory: str | None = None
    allow_complex: bool = False
    complex_reason: str = ""


class Params(dict):
    """Named numbers with attribute access: Params(stroke=90).stroke == 90."""

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as err:
            raise AttributeError(f"no parameter {name!r}") from err

    def with_overrides(self, **changes) -> "Params":
        return Params({**self, **changes})


@dataclass
class ConceptModule:
    path: Path
    meta: Meta
    params: Params
    tiers: dict[str, dict]
    build: Callable[[Params], Mark]


def concept_folder(paths: ProjectPaths, slug: str, name: str) -> Path:
    brand = paths.brand(slug)
    if not brand.is_dir():
        raise CliError(f"Unknown brand {slug!r}")
    folder = brand / "final" if name == "final" else brand / "concepts" / name
    if not (folder / "concept.py").is_file():
        raise CliError(f"No concept.py in {folder}")
    return folder


def load_concept(folder: Path) -> ConceptModule:
    source = folder / "concept.py"
    if not source.is_file():
        raise CliError(f"No concept.py in {folder}")
    name = f"logomaker_concept_{abs(hash(str(source.resolve())))}"
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as err:  # noqa: BLE001
        raise CliError(f"{source} failed to import: {type(err).__name__}: {err}", data={"traceback": traceback.format_exc()}) from err
    for attr in ("META", "PARAMS", "TIERS", "build"):
        if not hasattr(module, attr):
            raise CliError(f"{source} must define {attr}")
    if not isinstance(module.META, Meta):
        raise CliError(f"{source}: META must be a logomaker.kit.Meta")
    if "full" not in module.TIERS:
        raise CliError(f"{source}: TIERS must include 'full'")
    params = Params(module.PARAMS)
    overrides = folder / "params.json"
    if overrides.is_file():
        params = params.with_overrides(**json.loads(overrides.read_text(encoding="utf-8")))
    return ConceptModule(path=source, meta=module.META, params=params, tiers=dict(module.TIERS), build=module.build)


def build_tiers(concept: ConceptModule, overrides: dict | None = None) -> dict[str, Mark]:
    marks: dict[str, Mark] = {}
    for tier, tier_overrides in concept.tiers.items():
        if tier not in TIER_NAMES:
            raise CliError(f"unknown tier {tier!r}; use {TIER_NAMES}")
        drop_wordmark = tier_overrides.get("wordmark") is False
        p = concept.params.with_overrides(**(overrides or {})).with_overrides(**{k: v for k, v in tier_overrides.items() if k != "wordmark"})
        try:
            mark = concept.build(p)
        except Exception as err:  # noqa: BLE001
            raise CliError(f"{concept.path} build() failed for tier {tier!r}: {type(err).__name__}: {err}",
                           data={"traceback": traceback.format_exc()}) from err
        if not isinstance(mark, Mark):
            raise CliError(f"{concept.path} build() must return a Mark, got {type(mark).__name__}")
        marks[tier] = mark.without_wordmark() if drop_wordmark else mark
    return marks


def build_outputs(marks: dict[str, Mark]) -> dict[str, Mark]:
    full = marks["full"]
    outputs: dict[str, Mark] = {"full-lockup": full}
    if full.symbol is not None and full.wordmark is not None:
        outputs["full-horizontal"] = full.with_lockup("horizontal")
        outputs["full-stacked"] = full.with_lockup("stacked")
    if full.symbol is not None:
        outputs["full-symbol"] = full.with_lockup("symbol")
    if full.wordmark is not None:
        outputs["full-wordmark"] = full.with_lockup("wordmark")
    for tier in ("compact", "small", "favicon"):
        if tier in marks:
            outputs[tier] = marks[tier]
    return outputs


def write_build(folder: Path, outputs: dict[str, Mark], variants: tuple[str, ...] = ("black", "white"),
                palette: dict[str, str] | None = None, dark_palette: dict[str, str] | None = None) -> dict:
    build_dir = folder / "build"
    build_dir.mkdir(exist_ok=True)
    for stale in build_dir.glob("*.svg"):
        stale.unlink()
    files: list[str] = []
    geometry: dict[str, dict] = {}
    warnings: list[str] = []
    for tier in ("small", "favicon"):
        if tier not in outputs:
            warnings.append(f"tier {tier!r} missing; exports fall back to the next larger build")
    for name, mark in outputs.items():
        geometry[name] = mark.geometry()
        for variant in variants:
            chosen = dark_palette if variant == "reverse" else palette
            svg = mark.to_svg(variant, palette=chosen)
            filename = f"{name}-{variant}.svg"
            (build_dir / filename).write_text(svg, encoding="utf-8")
            files.append(filename)
    (build_dir / "geometry.json").write_text(json.dumps(geometry, indent=2) + "\n", encoding="utf-8")
    report = {"outputs": list(outputs), "variants": list(variants), "files": files, "warnings": warnings}
    (build_dir / "build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
```

Add to `src/logomaker/kit/__init__.py`:

```python
from .mark import Composite, Mark, Placed  # noqa: F401
from .concept import Meta, Params  # noqa: F401
```

and append `"Composite", "Mark", "Placed", "Meta", "Params"` to `__all__`.

- [ ] **Step 6: Add the `concept` group to the CLI**

Add to `src/logomaker/cli.py` (import `from .kit import concept as conceptlib`):

```python
@main.group("concept")
def concept_group() -> None:
    """Build, audit and render concept modules."""


@concept_group.command("build")
@click.argument("slug")
@click.argument("concept")
@click.option("--variants", default="black,white", help="Comma-separated: black,white,mono (color/reverse need --tokens, Task 8)")
@command
def concept_build(slug: str, concept: str, variants: str) -> None:
    paths = project()
    folder = conceptlib.concept_folder(paths, slug, concept)
    wanted = tuple(v.strip() for v in variants.split(",") if v.strip())
    if any(v in ("color", "reverse") for v in wanted):
        raise CliError("color and reverse variants need --tokens (see Task 8)")
    module = conceptlib.load_concept(folder)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
    report = conceptlib.write_build(folder, outputs, variants=wanted)
    emit({"concept": str(folder.relative_to(paths.root)), "build": report}, warnings=report["warnings"])
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_kit_mark.py tests/test_concept.py -q`
Expected: 16 passed.

- [ ] **Step 8: Commit**

```bash
git add src/logomaker/kit src/logomaker/cli.py tests/conftest.py tests/fixtures/concepts tests/test_kit_mark.py tests/test_concept.py
git commit -m "feat: Mark layout, SVG output and concept module builds

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Colour maths, tokens, `color` commands, colour variants in builds

**Files:**
- Create: `src/logomaker/color.py`
- Modify: `src/logomaker/cli.py` (add the `color` group; add `--tokens` to `concept build`)
- Test: `tests/test_color.py`, `tests/test_concept.py` (add one test)

**Interfaces:**
- Consumes: `output.emit`, `CliError`, `EXIT_RULE`; `concept.write_build(... palette, dark_palette)`.
- Produces: `color.normalize_hex(value) -> str`, `color.info(value) -> dict` (`hex, rgb, hsl, oklch, cmyk, luminance`), `color.luminance(hex) -> float`, `color.wcag_contrast(a, b) -> float`, `color.apca_lc(text_hex, bg_hex) -> float`, `color.CVD_KINDS`, `color.simulate_cvd(hex, kind) -> str`, `color.ramp(hex, steps=9) -> list[str]`, `color.ColorEntry`, `color.Tokens` (pydantic; `colors: dict[str, ColorEntry]`, `roles: {"light": {role: name}, "dark": {...}}`, `paper: {"light": name, "dark": name}`; method `palette(context) -> dict[str, str]` including `"paper"`), `color.enrich_tokens(tokens) -> Tokens`, `color.ContrastRow`, `color.CvdRow`, `color.CheckResult(ok, failures, warnings, contrast, cvd, palettes)`, `color.check_tokens(tokens) -> CheckResult`, `color.load_tokens(path) -> Tokens`. CLI: `color info <value>`, `color ramp <value> [--steps 9]`, `color check <tokens.json>`, and `concept build ... [--tokens PATH]` (auto-detects `tokens.json` in the concept folder).
- Thresholds (spec section 8.1): role `ink` needs WCAG ≥ 4.5 and |Lc| ≥ 60 against its paper; `primary`, `secondary`, `accent` need WCAG ≥ 3.0 and |Lc| ≥ 45; CVD pairs under 1.5 warn; grayscale OKLab lightness difference under 0.15 warns (amended from linear luminance).

- [ ] **Step 1: Write the failing tests**

`tests/test_color.py`:

```python
import json
import math

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from logomaker import color
from logomaker.cli import main


def test_normalize_and_info():
    assert color.normalize_hex("#ABC") == "#aabbcc"
    i = color.info("#1a5fb4")
    assert i["hex"] == "#1a5fb4" and i["rgb"] == [26, 95, 180]
    assert math.isclose(i["oklch"][0], 0.492, abs_tol=0.01)
    assert math.isclose(i["cmyk"][3], 29, abs_tol=1) and math.isclose(i["cmyk"][0], 86, abs_tol=1)
    assert 0 < i["luminance"] < 0.2


def test_wcag_and_apca_known_values():
    assert math.isclose(color.wcag_contrast("#1a5fb4", "#ffffff"), 6.29, abs_tol=0.02)
    assert math.isclose(color.apca_lc("#888888", "#ffffff"), 63.06, abs_tol=0.5)
    assert math.isclose(color.apca_lc("#ffffff", "#888888"), -68.54, abs_tol=0.5)
    assert math.isclose(color.apca_lc("#000000", "#aaaaaa"), 58.15, abs_tol=0.5)
    assert math.isclose(color.apca_lc("#112233", "#ddeeff"), 91.67, abs_tol=0.5)
    assert math.isclose(color.apca_lc("#112233", "#444444"), 8.32, abs_tol=0.5)
    assert color.apca_lc("#777777", "#777777") == 0.0


def test_cvd_simulation():
    for kind in color.CVD_KINDS:
        out = color.simulate_cvd("#e8572a", kind)
        assert out.startswith("#") and len(out) == 7
    gray = color.simulate_cvd("#e8572a", "achroma")
    assert gray[1:3] == gray[3:5] == gray[5:7]
    assert color.simulate_cvd("#e8572a", "deutan") != "#e8572a"


def test_ramp_is_monotonic_in_lightness():
    steps = color.ramp("#e8572a", steps=9)
    assert len(steps) == 9 and all(len(s) == 7 for s in steps)
    lightness = [color.info(s)["oklch"][0] for s in steps]
    assert all(a > b for a, b in zip(lightness, lightness[1:]))


def good_tokens() -> dict:
    return {
        "colors": {
            "ember": {"name": "Ember", "hex": "#e8572a"},
            "coal": {"name": "Coal", "hex": "#1f1b18"},
            "paper": {"name": "Paper", "hex": "#ffffff"},
            "ember-light": {"name": "Ember Light", "hex": "#ff9a6e"},
        },
        "roles": {"light": {"primary": "ember", "ink": "coal"}, "dark": {"primary": "ember-light", "ink": "paper"}},
        "paper": {"light": "paper", "dark": "coal"},
    }


def test_tokens_validation_and_palettes():
    t = color.Tokens.model_validate(good_tokens())
    assert t.palette("light") == {"primary": "#e8572a", "ink": "#1f1b18", "paper": "#ffffff"}
    assert t.palette("dark")["paper"] == "#1f1b18"
    bad = good_tokens()
    bad["roles"]["light"]["primary"] = "missing"
    with pytest.raises(ValidationError):
        color.Tokens.model_validate(bad)
    bad = good_tokens()
    del bad["roles"]["dark"]["ink"]
    with pytest.raises(ValidationError):
        color.Tokens.model_validate(bad)
    enriched = color.enrich_tokens(t)
    assert enriched.colors["ember"].rgb == [232, 87, 42] and len(enriched.colors["ember"].oklch) == 3


def test_check_tokens_passes_and_fails():
    result = color.check_tokens(color.Tokens.model_validate(good_tokens()))
    assert result.ok, result.failures
    rows = {(r.context, r.role): r for r in result.contrast}
    assert rows[("light", "ink")].wcag > 4.5 and rows[("light", "primary")].ok
    assert result.palettes["dark"]["ink"] == "#ffffff"
    bad = good_tokens()
    bad["colors"]["coal"]["hex"] = "#777777"
    result = color.check_tokens(color.Tokens.model_validate(bad))
    assert not result.ok and any("ink" in f and "light" in f for f in result.failures)


def test_color_cli(tmp_path):
    runner = CliRunner()
    payload = json.loads(runner.invoke(main, ["color", "info", "#1a5fb4"]).output)
    assert payload["ok"] and payload["rgb"] == [26, 95, 180]
    payload = json.loads(runner.invoke(main, ["color", "ramp", "#1a5fb4", "--steps", "5"]).output)
    assert len(payload["ramp"]) == 5
    tokens = tmp_path / "tokens.json"
    tokens.write_text(json.dumps(good_tokens()))
    result = runner.invoke(main, ["color", "check", str(tokens)])
    assert result.exit_code == 0 and json.loads(result.output)["ok"]
    bad = good_tokens()
    bad["colors"]["coal"]["hex"] = "#777777"
    tokens.write_text(json.dumps(bad))
    result = runner.invoke(main, ["color", "check", str(tokens)])
    assert result.exit_code == 2 and not json.loads(result.output)["ok"]
```

Append to `tests/test_concept.py`:

```python
def test_concept_build_with_tokens_writes_colour_variants(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")
    (folder / "tokens.json").write_text(json.dumps(good_tokens()))
    code, payload = run("concept", "build", "keystone", "01-good", "--variants", "black,white,color,reverse,mono")
    assert code == 0, payload
    build = folder / "build"
    assert 'fill="#e8572a"' in (build / "full-lockup-color.svg").read_text()
    assert 'fill="#ff9a6e"' in (build / "full-lockup-reverse.svg").read_text()
    assert 'fill="currentColor"' in (build / "full-lockup-mono.svg").read_text()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_color.py tests/test_concept.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker.color'`.

- [ ] **Step 3: Write `color.py`**

`src/logomaker/color.py`:

```python
"""Colour maths: conversions, WCAG and APCA contrast, colour-vision-deficiency simulation, OKLCH ramps, tokens checks."""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Literal

from coloraide import Color as _Color
from coloraide.spaces.cmyk import CMYK
from pydantic import BaseModel, Field, model_validator


class Color(_Color):
    pass


Color.register(CMYK())

CVD_KINDS = ("protan", "deutan", "tritan", "achroma")
Context = Literal["light", "dark"]

# APCA-W3 0.1.9 constants
_SRGB = (0.2126729, 0.7151522, 0.0721750)
_NORM_BG, _NORM_TXT, _REV_TXT, _REV_BG = 0.56, 0.57, 0.62, 0.65
_BLK_THRS, _BLK_CLMP = 0.022, 1.414
_SCALE, _OFFSET, _LO_CLIP, _DELTA_Y_MIN = 1.14, 0.027, 0.1, 0.0005


def normalize_hex(value: str) -> str:
    c = Color(value).convert("srgb")
    return c.to_string(hex=True, alpha=False).lower()


def luminance(value: str) -> float:
    return float(Color(value).convert("srgb").luminance())


def info(value: str) -> dict:
    c = Color(value).convert("srgb")
    r, g, b = (round(x * 255) for x in c.coords())
    hsl = c.convert("hsl")
    oklch = c.convert("oklch")
    cmyk = c.convert("cmyk")
    return {
        "hex": normalize_hex(value),
        "rgb": [r, g, b],
        "hsl": [round(hsl["h"] if hsl["h"] == hsl["h"] else 0.0, 1), round(hsl["s"] * 100, 1), round(hsl["l"] * 100, 1)],
        "oklch": [round(oklch["l"], 4), round(oklch["c"], 4), round(oklch["h"] if oklch["h"] == oklch["h"] else 0.0, 2)],
        "cmyk": [round(x * 100) for x in cmyk.coords()],
        "luminance": round(float(c.luminance()), 5),
    }


def wcag_contrast(a: str, b: str) -> float:
    return round(float(Color(a).contrast(Color(b), method="wcag21")), 3)


def _apca_y(value: str) -> float:
    r, g, b = Color(value).convert("srgb").coords()
    r, g, b = (max(0.0, min(1.0, x)) for x in (r, g, b))
    return _SRGB[0] * r**2.4 + _SRGB[1] * g**2.4 + _SRGB[2] * b**2.4


def apca_lc(text_hex: str, bg_hex: str) -> float:
    """APCA lightness contrast (W3 0.1.9). Positive for dark text on light, negative for light on dark."""
    ytxt, ybg = _apca_y(text_hex), _apca_y(bg_hex)
    if ytxt <= _BLK_THRS:
        ytxt += (_BLK_THRS - ytxt) ** _BLK_CLMP
    if ybg <= _BLK_THRS:
        ybg += (_BLK_THRS - ybg) ** _BLK_CLMP
    if abs(ybg - ytxt) < _DELTA_Y_MIN:
        return 0.0
    if ybg > ytxt:
        sapc = (ybg**_NORM_BG - ytxt**_NORM_TXT) * _SCALE
        lc = 0.0 if sapc < _LO_CLIP else sapc - _OFFSET
    else:
        sapc = (ybg**_REV_BG - ytxt**_REV_TXT) * _SCALE
        lc = 0.0 if sapc > -_LO_CLIP else sapc + _OFFSET
    return round(lc * 100, 2)


def simulate_cvd(value: str, kind: str) -> str:
    if kind not in CVD_KINDS:
        raise ValueError(f"kind must be one of {CVD_KINDS}")
    c = Color(value)
    out = c.filter("grayscale", 1) if kind == "achroma" else c.filter(kind)
    return out.convert("srgb").fit("srgb").to_string(hex=True, alpha=False).lower()


def ramp(value: str, steps: int = 9) -> list[str]:
    base = Color(value).convert("oklch")
    out = []
    for i in range(steps):
        light = 0.95 - (0.80 * i / (steps - 1) if steps > 1 else 0)
        c = Color("oklch", [light, base["c"], base["h"] if base["h"] == base["h"] else 0.0])
        out.append(c.convert("srgb").fit("srgb").to_string(hex=True, alpha=False).lower())
    return out


class ColorEntry(BaseModel):
    name: str
    hex: str
    rgb: list[int] = Field(default_factory=list)
    hsl: list[float] = Field(default_factory=list)
    oklch: list[float] = Field(default_factory=list)
    cmyk: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalise(self) -> "ColorEntry":
        self.hex = normalize_hex(self.hex)
        return self


REQUIRED_ROLES = ("primary", "ink")


class Tokens(BaseModel):
    colors: dict[str, ColorEntry]
    roles: dict[Context, dict[str, str]]
    paper: dict[Context, str]

    @model_validator(mode="after")
    def roles_point_at_colours(self) -> "Tokens":
        for context in ("light", "dark"):
            if context not in self.roles or context not in self.paper:
                raise ValueError(f"roles and paper must define both light and dark (missing {context})")
            for role in REQUIRED_ROLES:
                if role not in self.roles[context]:
                    raise ValueError(f"roles.{context} must include {role!r}")
            for role, name in self.roles[context].items():
                if name not in self.colors:
                    raise ValueError(f"roles.{context}.{role} points at unknown colour {name!r}")
            if self.paper[context] not in self.colors:
                raise ValueError(f"paper.{context} points at unknown colour {self.paper[context]!r}")
        return self

    def palette(self, context: Context) -> dict[str, str]:
        out = {role: self.colors[name].hex for role, name in self.roles[context].items()}
        out["paper"] = self.colors[self.paper[context]].hex
        return out


def enrich_tokens(tokens: Tokens) -> Tokens:
    for entry in tokens.colors.values():
        i = info(entry.hex)
        entry.rgb, entry.hsl, entry.oklch, entry.cmyk = i["rgb"], i["hsl"], i["oklch"], i["cmyk"]
    return tokens


def load_tokens(path: Path) -> Tokens:
    return Tokens.model_validate_json(Path(path).read_text(encoding="utf-8"))


class ContrastRow(BaseModel):
    context: str
    role: str
    color: str
    against: str
    wcag: float
    apca: float
    required_wcag: float
    required_apca: float
    ok: bool


class CvdRow(BaseModel):
    kind: str
    context: str
    a: str
    b: str
    contrast: float
    ok: bool


class CheckResult(BaseModel):
    ok: bool
    failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    contrast: list[ContrastRow] = Field(default_factory=list)
    cvd: list[CvdRow] = Field(default_factory=list)
    palettes: dict[str, dict[str, str]] = Field(default_factory=dict)


def check_tokens(tokens: Tokens) -> CheckResult:
    result = CheckResult(ok=True)
    for context in ("light", "dark"):
        palette = tokens.palette(context)
        result.palettes[context] = palette
        paper = palette["paper"]
        roles = {r: c for r, c in palette.items() if r != "paper"}
        for role, hex_value in roles.items():
            need_wcag, need_apca = (4.5, 60.0) if role == "ink" else (3.0, 45.0)
            wcag = wcag_contrast(hex_value, paper)
            apca = apca_lc(hex_value, paper)
            ok = wcag >= need_wcag and abs(apca) >= need_apca
            result.contrast.append(ContrastRow(context=context, role=role, color=hex_value, against=paper, wcag=wcag, apca=apca,
                                               required_wcag=need_wcag, required_apca=need_apca, ok=ok))
            if not ok:
                result.failures.append(f"{context}: role {role} ({hex_value}) on paper {paper}: WCAG {wcag} (need {need_wcag}), APCA {apca} (need {need_apca})")
        for (ra, ca), (rb, cb) in combinations(roles.items(), 2):
            if abs(luminance(ca) - luminance(cb)) < 0.15:
                result.warnings.append(f"grayscale: {context} roles {ra} and {rb} differ by less than 0.15 luminance")
            for kind in CVD_KINDS:
                contrast = wcag_contrast(simulate_cvd(ca, kind), simulate_cvd(cb, kind))
                ok = contrast >= 1.5
                result.cvd.append(CvdRow(kind=kind, context=context, a=ra, b=rb, contrast=contrast, ok=ok))
                if not ok:
                    result.warnings.append(f"cvd {kind}: {context} roles {ra} and {rb} collapse to contrast {contrast}")
    result.ok = not result.failures
    return result
```

- [ ] **Step 4: Add the `color` group and `--tokens` to the CLI**

Add to `src/logomaker/cli.py` (import `from . import color as colorlib` and `from .output import EXIT_RULE` is already imported):

```python
@main.group("color")
def color_group() -> None:
    """Colour conversions and token checks."""


@color_group.command("info")
@click.argument("value")
@command
def color_info(value: str) -> None:
    emit(colorlib.info(value))


@color_group.command("ramp")
@click.argument("value")
@click.option("--steps", default=9, type=int)
@command
def color_ramp(value: str, steps: int) -> None:
    emit({"ramp": colorlib.ramp(value, steps)})


@color_group.command("check")
@click.argument("tokens_path", type=click.Path(exists=True, dir_okay=False))
@command
def color_check(tokens_path: str) -> None:
    result = colorlib.check_tokens(colorlib.load_tokens(Path(tokens_path)))
    emit(result.model_dump(), ok=result.ok, errors=result.failures, warnings=result.warnings, code=0 if result.ok else EXIT_RULE)
```

Replace the `concept_build` command with:

```python
@concept_group.command("build")
@click.argument("slug")
@click.argument("concept")
@click.option("--variants", default="black,white", help="Comma-separated subset of black,white,mono,color,reverse")
@click.option("--tokens", "tokens_path", default=None, type=click.Path(exists=True, dir_okay=False), help="tokens.json for color/reverse (defaults to <concept>/tokens.json when present)")
@command
def concept_build(slug: str, concept: str, variants: str, tokens_path: str | None) -> None:
    paths = project()
    folder = conceptlib.concept_folder(paths, slug, concept)
    wanted = tuple(v.strip() for v in variants.split(",") if v.strip())
    tokens_file = Path(tokens_path) if tokens_path else (folder / "tokens.json" if (folder / "tokens.json").is_file() else None)
    palette = dark_palette = None
    if tokens_file is not None:
        tokens = colorlib.load_tokens(tokens_file)
        palette, dark_palette = tokens.palette("light"), tokens.palette("dark")
    if any(v in ("color", "reverse") for v in wanted) and palette is None:
        raise CliError("color and reverse variants need --tokens or a tokens.json in the concept folder")
    module = conceptlib.load_concept(folder)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
    report = conceptlib.write_build(folder, outputs, variants=wanted, palette=palette, dark_palette=dark_palette)
    emit({"concept": str(folder.relative_to(paths.root)), "build": report}, warnings=report["warnings"])
```

Add `from pathlib import Path` to the imports of `cli.py`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_color.py tests/test_concept.py -q`
Expected: 15 passed.

- [ ] **Step 6: Commit**

```bash
git add src/logomaker/color.py src/logomaker/cli.py tests/test_color.py tests/test_concept.py
git commit -m "feat: colour maths, tokens validation and colour variants in concept builds

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Chrome renderer and raster helpers

**Files:**
- Create: `src/logomaker/render.py`, `src/logomaker/raster.py`
- Modify: `tests/conftest.py` (add `requires_chrome` marker helper and `renderer` fixture)
- Test: `tests/test_raster.py`, `tests/test_render.py`

**Interfaces:**
- Consumes: `output.CliError`, `EXIT_EXTERNAL`.
- Produces: `render.CHROME_APP: Path`, `render.check_chrome() -> dict`, `render.svg_size(svg, width) -> tuple[int, int]`, `render.with_size(svg, width, height) -> str`, `render.Renderer(chrome_app=CHROME_APP)` context manager with `html_to_png(html, width, height=None, full_page=True, transparent=False) -> bytes`, `svg_to_png(svg, width, height=None, background=None) -> bytes`, `html_to_pdf(html, paper="letter") -> bytes`; `raster.load_rgba(png) -> np.ndarray`, `raster.ink_mask(png, threshold=128) -> np.ndarray[bool]`, `raster.component_count(mask) -> int`, `raster.min_feature_px(mask) -> float`.

- [ ] **Step 1: Add the Chrome helpers to `tests/conftest.py`**

Append to `tests/conftest.py`:

```python
CHROME = Path("/Applications/Google Chrome.app")
requires_chrome = pytest.mark.skipif(not CHROME.exists(), reason="Google Chrome is not installed")


@pytest.fixture
def renderer():
    from logomaker.render import Renderer

    with Renderer() as r:
        yield r
```

- [ ] **Step 2: Write the failing tests**

`tests/test_raster.py`:

```python
import io

import numpy as np
from PIL import Image, ImageDraw

from logomaker.raster import component_count, ink_mask, min_feature_px


def png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_ink_mask_from_opaque_and_transparent_images():
    opaque = Image.new("RGB", (50, 50), "white")
    ImageDraw.Draw(opaque).rectangle([10, 10, 29, 29], fill="black")
    mask = ink_mask(png_bytes(opaque))
    assert mask.shape == (50, 50) and mask.sum() == 400
    transparent = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    ImageDraw.Draw(transparent).rectangle([0, 0, 9, 9], fill=(20, 20, 20, 255))
    assert ink_mask(png_bytes(transparent)).sum() == 100


def test_component_count_and_min_feature():
    mask = np.zeros((100, 100), dtype=bool)
    mask[10:20, 10:90] = True  # a 10 px tall bar
    mask[50:70, 50:70] = True  # a separate 20 px square
    assert component_count(mask) == 2
    assert 9 <= min_feature_px(mask) <= 11
    assert min_feature_px(np.zeros((5, 5), dtype=bool)) == 0.0
    thin = np.zeros((40, 40), dtype=bool)
    thin[20, 5:35] = True
    assert min_feature_px(thin) == 1.0
```

`tests/test_render.py`:

```python
import io
import math

import pytest
from PIL import Image

from logomaker.output import CliError
from logomaker.raster import ink_mask
from logomaker.render import Renderer, svg_size, with_size
from tests.conftest import requires_chrome

CIRCLE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="50" fill="#000"/></svg>'


def test_svg_size_and_with_size():
    assert svg_size('<svg viewBox="0 0 200 50">', 400) == (400, 100)
    sized = with_size(CIRCLE, 64, 64)
    assert sized.startswith('<svg width="64" height="64" ')


def test_missing_chrome_exits_3(tmp_path):
    with pytest.raises(CliError) as exc:
        with Renderer(chrome_app=tmp_path / "Nope.app"):
            pass
    assert exc.value.code == 3


@requires_chrome
@pytest.mark.render
def test_svg_to_png_sizes_and_alpha(renderer):
    png = renderer.svg_to_png(CIRCLE, 100)
    image = Image.open(io.BytesIO(png))
    assert image.size == (100, 100) and image.mode == "RGBA"
    ink = ink_mask(png).sum()
    assert math.isclose(ink, math.pi * 50 * 50, rel_tol=0.05)
    opaque = Image.open(io.BytesIO(renderer.svg_to_png(CIRCLE, 50, background="#ffffff")))
    assert opaque.getpixel((1, 1))[:3] == (255, 255, 255)


@requires_chrome
@pytest.mark.render
def test_html_to_png_and_pdf(renderer):
    html = "<html><body style='margin:0'><div style='width:200px;height:50px;background:#f00'></div></body></html>"
    image = Image.open(io.BytesIO(renderer.html_to_png(html, 200, 50, full_page=False)))
    assert image.size == (200, 50) and image.getpixel((10, 10))[:3] == (255, 0, 0)
    pdf = renderer.html_to_pdf(html)
    assert pdf[:4] == b"%PDF"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_raster.py tests/test_render.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker.raster'`.

- [ ] **Step 4: Write `render.py` and `raster.py`**

`src/logomaker/render.py`:

```python
"""Rendering through the installed Google Chrome via Playwright (channel "chrome"; never `playwright install`)."""
from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from .output import EXIT_EXTERNAL, CliError

CHROME_APP = Path("/Applications/Google Chrome.app")
PAPER = {"letter": {"width": "8.5in", "height": "11in"}, "a4": {"format": "A4"}}
_VIEWBOX = re.compile(r'viewBox="([^"]+)"')


def check_chrome(chrome_app: Path = CHROME_APP) -> dict:
    return {"found": chrome_app.exists(), "path": str(chrome_app)}


def svg_size(svg: str, width: int) -> tuple[int, int]:
    match = _VIEWBOX.search(svg)
    if not match:
        return width, width
    _, _, w, h = (float(v) for v in match.group(1).replace(",", " ").split())
    return width, max(1, round(width * h / w))


def with_size(svg: str, width: int, height: int) -> str:
    return svg.replace("<svg ", f'<svg width="{width}" height="{height}" ', 1)


class Renderer:
    def __init__(self, chrome_app: Path = CHROME_APP):
        self.chrome_app = chrome_app
        self._pw = None
        self._browser = None

    def __enter__(self) -> "Renderer":
        if not self.chrome_app.exists():
            raise CliError(f"Google Chrome not found at {self.chrome_app}; install it to render", code=EXIT_EXTERNAL)
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(channel="chrome", headless=True)
        except PlaywrightError as err:
            self._pw.stop()
            raise CliError(f"Could not launch Google Chrome: {err}", code=EXIT_EXTERNAL) from err
        return self

    def __exit__(self, *exc) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def html_to_png(self, html: str, width: int, height: int | None = None, full_page: bool = True, transparent: bool = False) -> bytes:
        page = self._browser.new_page(viewport={"width": width, "height": height or 100}, device_scale_factor=1)
        try:
            page.set_content(html, wait_until="load")
            return page.screenshot(full_page=full_page, omit_background=transparent)
        finally:
            page.close()

    def svg_to_png(self, svg: str, width: int, height: int | None = None, background: str | None = None) -> bytes:
        w, h = width, height or svg_size(svg, width)[1]
        bg = f"background:{background};" if background else ""
        html = (
            "<!doctype html><html><head><meta charset='utf-8'><style>"
            f"html,body{{margin:0;padding:0;{bg}}}svg{{display:block}}</style></head>"
            f"<body>{with_size(svg, w, h)}</body></html>"
        )
        return self.html_to_png(html, w, h, full_page=False, transparent=background is None)

    def html_to_pdf(self, html: str, paper: str = "letter") -> bytes:
        page = self._browser.new_page()
        try:
            page.set_content(html, wait_until="load")
            return page.pdf(print_background=True, **PAPER[paper])
        finally:
            page.close()
```

`src/logomaker/raster.py`:

```python
"""Raster helpers for audits: ink masks, connected components and an erosion-based minimum feature width."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
from scipy import ndimage

_STRUCTURE = np.ones((3, 3), dtype=bool)


def load_rgba(png: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))


def ink_mask(png: bytes, threshold: int = 128) -> np.ndarray:
    """True where there is ink: opaque pixels of a transparent render, or dark pixels of an opaque one."""
    arr = load_rgba(png)
    alpha = arr[..., 3]
    if (alpha < 255).any():
        return alpha > threshold
    lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    return lum < threshold


def component_count(mask: np.ndarray) -> int:
    return int(ndimage.label(mask, structure=_STRUCTURE)[1])


def min_feature_px(mask: np.ndarray) -> float:
    """Erode until a component vanishes; the thinnest feature is about 2k-1 pixels wide after k erosions."""
    if not mask.any():
        return 0.0
    original = component_count(mask)
    current = mask.copy()
    k = 0
    while current.any() and component_count(current) >= original:
        current = ndimage.binary_erosion(current, structure=_STRUCTURE, border_value=1)
        k += 1
        if k > max(mask.shape):
            break
    return float(max(1, 2 * k - 1))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_raster.py tests/test_render.py -q`
Expected: 6 passed (the two render tests run because Chrome is installed).

- [ ] **Step 6: Commit**

```bash
git add src/logomaker/render.py src/logomaker/raster.py tests/conftest.py tests/test_raster.py tests/test_render.py
git commit -m "feat: Chrome renderer and raster audit helpers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Automated audits and the cliché blacklist

**Files:**
- Create: `assets/cliches.json`, `src/logomaker/audit.py`
- Create: `tests/fixtures/concepts/near_miss/concept.py`, `tests/fixtures/concepts/tiny_part/concept.py`, `tests/fixtures/concepts/thin_stroke/concept.py`, `tests/fixtures/concepts/cliche/concept.py`, `tests/fixtures/concepts/random_concept/concept.py`
- Modify: `src/logomaker/schemas.py` (add `Finding`, `AuditResult`), `src/logomaker/cli.py` (add `concept audit`)
- Test: `tests/test_audit.py`

**Interfaces:**
- Consumes: `concept.concept_folder/load_concept/build_tiers/build_outputs`, `registry.load_state`, `color.check_tokens/load_tokens`, `raster.*`, `render.Renderer`.
- Produces: `schemas.Finding(check, severity, message, data)`, `schemas.AuditResult(ok, failures, warnings, info, outputs, rendered)`; `audit.load_cliches(paths) -> dict`, `audit.resolve_industry(cliches, industry) -> str | None`, `audit.check_cliches(motifs, cliches, industry) -> list[Finding]`, `audit.audit_concept(paths, slug, concept_name, renderer=None) -> AuditResult` (also writes `<concept>/audit.json`). CLI: `concept audit <slug> <concept> [--no-render]` emitting `{"ok": true, "audit": {...}}`; the audit's own `ok` is inside `audit`.
- Thresholds are the spec's section 8.1 table; constants live at the top of `audit.py`.

- [ ] **Step 1: Write the cliché blacklist**

`assets/cliches.json` (terms from `docs/research/05-trends-strategy-craft.md` section 5.5; keep lowercase):

```json
{
  "any": {
    "motifs": ["script l", "flourish monogram", "feather", "pennant", "watermelon", "stick figure", "v ball", "generic asterisk", "trans-letter swoosh", "letter in a circle", "swoosh", "infinity", "globe"],
    "styles": ["mesh gradient", "metaball", "helvetica default", "futura default", "montserrat default"]
  },
  "industries": {
    "ai": {"aliases": ["ai", "ml", "machine learning", "artificial intelligence", "tech", "software", "llm", "agent"],
            "motifs": ["hexagon", "sparkle", "star", "concentric", "aperture", "orbit", "node", "neural", "brain", "circuit", "cube", "pixel"],
            "styles": ["blue-violet gradient", "glow", "inter-only wordmark"]},
    "saas": {"aliases": ["saas", "startup", "app", "platform", "productivity"],
             "motifs": ["s swoosh", "three overlapping circles", "chat bubble", "rocket", "lightning", "infinity loop"],
             "styles": ["rounded geometric sans with one pastel"]},
    "crypto": {"aliases": ["crypto", "web3", "blockchain", "defi", "token"],
               "motifs": ["hexagon", "coin", "chain", "cube", "v wings"], "styles": ["metallic gradient"]},
    "fintech": {"aliases": ["fintech", "finance", "banking", "payments", "invoicing", "accounting", "insurance", "lending", "investing"],
                "motifs": ["upward arrow", "bar chart", "shield", "pillar", "column", "globe", "handshake", "pie", "dollar sign", "coin", "piggy bank"],
                "styles": ["all-caps navy serif", "bank blue"]},
    "real-estate": {"aliases": ["real estate", "realty", "construction", "property", "housing", "architecture"],
                    "motifs": ["roof", "house", "building", "key", "skyline", "chimney"], "styles": ["serif and gold"]},
    "healthcare": {"aliases": ["health", "healthcare", "medical", "wellness", "clinic", "pharma", "therapy"],
                   "motifs": ["caduceus", "rod of asclepius", "cross", "heart", "swoosh people", "leaf in hand", "heartbeat", "dna", "pill"],
                   "styles": ["teal rounded sans"]},
    "dental": {"aliases": ["dental", "dentist", "orthodont"], "motifs": ["tooth", "smiling tooth", "tooth with leaf", "tooth with sparkle"], "styles": ["pastel blue"]},
    "legal": {"aliases": ["legal", "law", "attorney", "lawyer"], "motifs": ["scales", "gavel", "pillar", "lion", "shield", "serif monogram in a box"], "styles": ["black and gold serif"]},
    "consulting": {"aliases": ["consulting", "hr", "coaching", "advisory", "recruiting", "agency"],
                   "motifs": ["abstract figures in a circle", "puzzle", "three people", "lightbulb", "compass", "mountain peak"], "styles": ["corporate blue swoosh"]},
    "education": {"aliases": ["education", "school", "learning", "tutoring", "course", "edtech"],
                  "motifs": ["open book", "graduation cap", "apple", "torch", "tree of knowledge", "shield crest"], "styles": ["collegiate serif"]},
    "nonprofit": {"aliases": ["nonprofit", "charity", "community", "foundation", "ngo"],
                  "motifs": ["hands", "heart", "globe", "circle of people", "dove", "ribbon"], "styles": ["rainbow gradient"]},
    "food": {"aliases": ["food", "restaurant", "cafe", "catering", "snack", "meal", "kitchen", "bakery"],
             "motifs": ["fork and knife", "chef hat", "plate", "steam", "slice", "tomato"], "styles": ["script on distressed badge"]},
    "coffee": {"aliases": ["coffee", "roaster", "espresso"], "motifs": ["bean", "cup with steam", "mug in circle"], "styles": ["kraft brown badge"]},
    "fitness": {"aliases": ["fitness", "gym", "training", "sport", "athletic", "running"],
                "motifs": ["dumbbell", "flexing figure", "running figure", "speed lines", "flame", "lightning"], "styles": ["heavy italic condensed red and black"]},
    "beauty": {"aliases": ["beauty", "fashion", "cosmetic", "skincare", "salon", "apparel"],
               "motifs": ["lotus", "butterfly", "feather", "mirrored script monogram", "lips"], "styles": ["thin all-caps sans", "default didone"]},
    "sustainability": {"aliases": ["sustainability", "eco", "green", "climate", "environment", "organic", "solar"],
                       "motifs": ["leaf", "sprout", "globe with leaf", "recycling arrows", "water drop", "tree in circle", "hands cradling earth"], "styles": ["earth-tone uniform"]},
    "logistics": {"aliases": ["logistics", "delivery", "shipping", "freight", "courier", "moving"],
                  "motifs": ["arrow", "box with arrow", "truck", "wing", "swoosh", "globe with arrow"], "styles": ["orange and blue"]},
    "travel": {"aliases": ["travel", "hospitality", "hotel", "tourism", "vacation", "rental"],
               "motifs": ["plane", "sun over waves", "palm tree", "compass", "suitcase", "globe", "pin"], "styles": ["escape script"]},
    "creative": {"aliases": ["creative", "design", "studio", "media", "marketing", "branding", "video"],
                 "motifs": ["pencil", "brush", "spark", "asterisk", "eye", "colour wheel"], "styles": ["ultra-minimal black wordmark"]},
    "pets": {"aliases": ["pet", "vet", "animal", "dog", "cat"], "motifs": ["paw", "bone", "dog silhouette", "heart paw"], "styles": ["friendly rounded sans"]},
    "photography": {"aliases": ["photo", "photography", "camera", "studio photo"], "motifs": ["camera", "aperture", "lens flare"], "styles": ["thin signature script"]},
    "trades": {"aliases": ["plumbing", "hvac", "electrical", "contractor", "handyman", "roofing", "cleaning"],
               "motifs": ["wrench", "droplet", "flame", "house with swoosh", "snowflake and flame"], "styles": ["blue and red split"]},
    "cannabis": {"aliases": ["cannabis", "cbd", "hemp", "dispensary"], "motifs": ["marijuana leaf", "lotus", "hemp leaf"], "styles": ["green gradient"]},
    "faith": {"aliases": ["church", "faith", "ministry", "religious"], "motifs": ["cross with swoosh", "dove", "flame", "three arcs"], "styles": []}
  }
}
```

- [ ] **Step 2: Add fixture concepts**

`tests/fixtures/concepts/near_miss/concept.py`:

```python
from logomaker.kit import *

META = Meta(slug="near-miss", idea="a quadrilateral with one edge 2 degrees off", logo_type="abstract", motifs=["block"])
PARAMS = Params()
TIERS = {"full": {}}


def build(p):
    return Mark(symbol=polygon([(0, 0), (300, 10), (300, 310), (0, 300)], free=True))
```

`tests/fixtures/concepts/tiny_part/concept.py`:

```python
from logomaker.kit import *

META = Meta(slug="tiny-part", idea="a disc with a speck", logo_type="abstract", motifs=["disc"])
PARAMS = Params()
TIERS = {"full": {}, "small": {}}


def build(p):
    return Mark(symbol=union(circle(0, 0, 300), circle(400, 0, 5)))
```

`tests/fixtures/concepts/thin_stroke/concept.py`:

```python
from logomaker.kit import *

META = Meta(slug="thin-stroke", idea="a hairline ring", logo_type="abstract", motifs=["ring"])
PARAMS = Params()
TIERS = {"full": {}, "favicon": {}}


def build(p):
    return Mark(symbol=ring(0, 0, 300, 6))
```

`tests/fixtures/concepts/cliche/concept.py`:

```python
from logomaker.kit import *

META = Meta(slug="cliche", idea="an AI hexagon with a sparkle", logo_type="abstract", motifs=["hexagon", "sparkle", "wave"])
PARAMS = Params()
TIERS = {"full": {}}


def build(p):
    return Mark(symbol=union(regular_polygon(0, 0, 300, 6), regular_polygon(0, 0, 60, 4, rotation=45)))
```

`tests/fixtures/concepts/random_concept/concept.py`:

```python
import random

from logomaker.kit import *

META = Meta(slug="random", idea="nondeterministic on purpose", logo_type="abstract", motifs=[])
PARAMS = Params()
TIERS = {"full": {}}


def build(p):
    return Mark(symbol=circle(0, 0, random.randint(100, 300)))
```

- [ ] **Step 3: Write the failing tests**

`tests/test_audit.py`:

```python
import json

import pytest
from click.testing import CliRunner

from logomaker import audit, registry
from logomaker.cli import main
from logomaker.paths import project
from tests.conftest import install_concept, requires_chrome


def findings(result, check):
    return [f for f in result.failures + result.warnings + result.info if f.check == check]


def test_good_concept_passes_without_renderer(project_root):
    install_concept(project_root, "good")
    result = audit.audit_concept(project(), "keystone", "01-good")
    assert result.ok and result.rendered is False
    assert (project_root / "brands" / "keystone" / "concepts" / "01-good" / "audit.json").is_file()
    assert "full-symbol" in result.outputs


def test_near_miss_angles_and_free_segments(project_root):
    install_concept(project_root, "near_miss", name="02-near")
    result = audit.audit_concept(project(), "keystone", "02-near")
    near = findings(result, "near_miss_angles")
    assert near and near[0].severity == "warn" and near[0].data["count"] >= 1
    assert findings(result, "free_segments")[0].data["count"] == 4


def test_tiny_part_warns_and_fails_in_small_tier(project_root):
    install_concept(project_root, "tiny_part", name="03-tiny")
    result = audit.audit_concept(project(), "keystone", "03-tiny")
    tiny = findings(result, "tiny_parts")
    assert any(f.severity == "warn" for f in tiny) and any(f.severity == "fail" for f in tiny)
    assert not result.ok


def test_cliche_terms_match_industry(project_root):
    install_concept(project_root, "cliche", name="04-cliche")
    registry.set_fields(project(), "keystone", industry="AI tooling")
    result = audit.audit_concept(project(), "keystone", "04-cliche")
    matched = {f.data["term"] for f in findings(result, "cliche")}
    assert {"hexagon", "sparkle"} <= matched and "wave" not in matched
    cliches = audit.load_cliches(project())
    assert audit.resolve_industry(cliches, "Invoicing for consultants") == "fintech"
    assert audit.resolve_industry(cliches, None) is None


def test_text_legibility_fails_when_lockup_is_too_small(project_root):
    install_concept(project_root, "good")
    state = registry.load_state(project(), "keystone")
    state.min_sizes.horizontal_px = 60
    registry.save_state(project(), state)
    result = audit.audit_concept(project(), "keystone", "01-good")
    assert findings(result, "text_legibility")[0].severity == "fail" and not result.ok


def test_nondeterministic_concept_fails(project_root):
    install_concept(project_root, "random_concept", name="05-random")
    result = audit.audit_concept(project(), "keystone", "05-random")
    assert findings(result, "determinism")[0].severity == "fail"


def test_anchor_ceiling(project_root):
    folder = install_concept(project_root, "good", name="06-busy")
    (folder / "concept.py").write_text(
        "from logomaker.kit import *\n"
        "META = Meta(slug='busy', idea='too many dots', logo_type='abstract', motifs=[])\n"
        "PARAMS = Params()\nTIERS = {'full': {}}\n"
        "def build(p):\n"
        "    return Mark(symbol=union(*[circle(x * 40, y * 40, 12) for x in range(8) for y in range(8)]))\n"
    )
    result = audit.audit_concept(project(), "keystone", "06-busy")
    assert findings(result, "anchors")[0].severity == "fail"


def test_tokens_contrast_feeds_the_audit(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")
    bad = good_tokens()
    bad["colors"]["coal"]["hex"] = "#777777"
    (folder / "tokens.json").write_text(json.dumps(bad))
    result = audit.audit_concept(project(), "keystone", "01-good")
    assert findings(result, "contrast")[0].severity == "fail"


@requires_chrome
@pytest.mark.render
def test_thin_stroke_fails_min_feature_and_merge(project_root, renderer):
    install_concept(project_root, "thin_stroke", name="07-thin")
    result = audit.audit_concept(project(), "keystone", "07-thin", renderer=renderer)
    assert result.rendered is True
    assert any(f.severity == "fail" for f in findings(result, "min_feature"))


@requires_chrome
@pytest.mark.render
def test_good_concept_passes_raster_checks(project_root, renderer):
    install_concept(project_root, "good")
    result = audit.audit_concept(project(), "keystone", "01-good", renderer=renderer)
    assert result.ok, [f.message for f in result.failures]


def test_concept_audit_cli(project_root):
    install_concept(project_root, "good")
    result = CliRunner().invoke(main, ["concept", "audit", "keystone", "01-good", "--no-render"])
    payload = json.loads(result.output)
    assert result.exit_code == 0 and payload["ok"] and payload["audit"]["ok"] and payload["audit"]["rendered"] is False
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run pytest tests/test_audit.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker.audit'`.

- [ ] **Step 5: Add the audit models to `schemas.py`**

Append to `src/logomaker/schemas.py`:

```python
class Finding(BaseModel):
    check: str
    severity: Literal["fail", "warn", "info"]
    message: str
    data: dict = Field(default_factory=dict)


class AuditResult(BaseModel):
    ok: bool
    failures: list[Finding] = Field(default_factory=list)
    warnings: list[Finding] = Field(default_factory=list)
    info: list[Finding] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    rendered: bool = False
```

- [ ] **Step 6: Write `audit.py`**

`src/logomaker/audit.py`:

```python
"""Deterministic concept audits (spec section 8.1). Geometry checks always run; raster checks need a Renderer."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import registry
from .color import check_tokens, load_tokens
from .kit import concept as conceptlib
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
        check = check_tokens(load_tokens(tokens_file))
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
```

- [ ] **Step 7: Add `concept audit` to the CLI**

Add to `src/logomaker/cli.py` (import `from . import audit as auditlib` and `from .render import Renderer`):

```python
@concept_group.command("audit")
@click.argument("slug")
@click.argument("concept")
@click.option("--no-render", is_flag=True, help="Skip the raster checks (no Chrome needed).")
@command
def concept_audit(slug: str, concept: str, no_render: bool) -> None:
    paths = project()
    if no_render:
        result = auditlib.audit_concept(paths, slug, concept)
    else:
        with Renderer() as renderer:
            result = auditlib.audit_concept(paths, slug, concept, renderer=renderer)
    emit({"audit": result.model_dump()}, warnings=[f.message for f in result.warnings])
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest tests/test_audit.py -q`
Expected: 11 passed.

- [ ] **Step 9: Commit**

```bash
git add assets/cliches.json src/logomaker/audit.py src/logomaker/schemas.py src/logomaker/cli.py tests/fixtures/concepts tests/test_audit.py
git commit -m "feat: deterministic concept audits and the industry cliché blacklist

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Critique sheet, `concept render`, `concept run`

**Files:**
- Create: `src/logomaker/sheets.py`, `templates/sheets/critique.html`
- Modify: `src/logomaker/cli.py` (add `concept render`, `concept run`; factor `_build_concept`)
- Test: `tests/test_sheets.py`

**Interfaces:**
- Consumes: `concept.*`, `color.load_tokens`, `render.Renderer/with_size/svg_size`, `audit.audit_concept`, `schemas.AuditResult`.
- Produces: `sheets.SHEET_W = 2000`, `sheets.SHEET_H = 1400`, `sheets.LADDER = (256, 128, 64, 48, 32, 24, 16)`, `sheets.jinja(paths) -> Environment`, `sheets.pick_output(outputs, size) -> str` (tier rule: 96 px and above `full-symbol`; 33 to 95 `small`; 32 and below `favicon`; each falling back to the next larger build), `sheets.fit_box(svg, box_w, box_h) -> str`, `sheets.next_round(folder) -> int`, `sheets.critique_sheet(paths, slug, concept_name, round_n=None, renderer=None, audit=None) -> dict` (keys `round`, `critique_png`, `critique_html`; writes `<concept>/renders/round-N/critique.{html,png}`). CLI: `concept render <slug> <concept> [--round N]`, `concept run <slug> <concept> [--round N] [--variants ...] [--tokens PATH] [--no-render]` emitting `build`, `audit`, `critique`.

- [ ] **Step 1: Write the failing tests**

`tests/test_sheets.py`:

```python
import io
import json

import pytest
from click.testing import CliRunner
from PIL import Image

from logomaker import sheets
from logomaker.cli import main
from logomaker.paths import project
from logomaker.raster import ink_mask
from tests.conftest import install_concept, requires_chrome

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100"><rect width="200" height="100"/></svg>'


def test_pick_output_tier_rule():
    full = {"full-lockup": 1, "full-symbol": 1, "small": 1, "favicon": 1}
    assert sheets.pick_output(full, 256) == "full-symbol"
    assert sheets.pick_output(full, 64) == "small"
    assert sheets.pick_output(full, 16) == "favicon"
    assert sheets.pick_output({"full-lockup": 1, "full-symbol": 1}, 16) == "full-symbol"
    assert sheets.pick_output({"full-lockup": 1}, 16) == "full-lockup"


def test_fit_box_limits_width_or_height():
    assert sheets.fit_box(SVG, 400, 400).startswith('<svg width="400" height="200" ')
    assert sheets.fit_box(SVG, 400, 100).startswith('<svg width="200" height="100" ')


def test_next_round_counts_existing(project_root):
    folder = install_concept(project_root, "good")
    assert sheets.next_round(folder) == 1
    (folder / "renders" / "round-1").mkdir(parents=True)
    (folder / "renders" / "round-2").mkdir()
    assert sheets.next_round(folder) == 3


@requires_chrome
@pytest.mark.render
def test_critique_sheet_renders(project_root, renderer):
    install_concept(project_root, "good")
    info = sheets.critique_sheet(project(), "keystone", "01-good", renderer=renderer)
    assert info["round"] == 1
    image = Image.open(io.BytesIO(open(info["critique_png"], "rb").read()))
    assert image.size == (sheets.SHEET_W, sheets.SHEET_H)
    assert ink_mask(open(info["critique_png"], "rb").read()).mean() > 0.01
    html = open(info["critique_html"]).read()
    assert "mirrored" in html and "no audit yet" in html and "16 favicon" in html


@requires_chrome
@pytest.mark.render
def test_concept_run_cli_builds_audits_renders_and_increments_rounds(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")
    (folder / "tokens.json").write_text(json.dumps(good_tokens()))
    runner = CliRunner()
    result = runner.invoke(main, ["concept", "run", "keystone", "01-good", "--variants", "black,white,color,reverse"])
    payload = json.loads(result.output)
    assert result.exit_code == 0, payload
    assert payload["audit"]["ok"] and payload["audit"]["rendered"] and payload["critique"]["round"] == 1
    assert "full-lockup-color.svg" in payload["build"]["files"]
    html = open(payload["critique"]["critique_html"]).read()
    assert "reverse" in html and "audit ok" in html
    payload = json.loads(runner.invoke(main, ["concept", "run", "keystone", "01-good"]).output)
    assert payload["critique"]["round"] == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_sheets.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'logomaker.sheets'`.

- [ ] **Step 3: Write the template**

`templates/sheets/critique.html`:

```html
<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body{margin:0;width:{{ width }}px;height:{{ height }}px;font:14px/1.3 -apple-system,Helvetica,Arial,sans-serif;background:#e9e9e9;color:#222;overflow:hidden}
  header{height:40px;padding:10px 20px;box-sizing:border-box;font-weight:600}
  .row{display:flex;gap:16px;padding:0 20px;align-items:flex-start}
  .panel{background:#fff;border:1px solid #ccc;display:flex;align-items:center;justify-content:center;box-sizing:border-box;position:relative;margin:0}
  .panel.dark{background:#000}
  .panel figcaption{position:absolute;left:6px;bottom:4px;font-size:11px;color:#888}
  .panel.dark figcaption{color:#aaa}
  .mirror svg{transform:scaleX(-1)} .rotate svg{transform:rotate(90deg)}
  .audit{width:600px;height:200px;background:#fff;border:1px solid #ccc;padding:10px;box-sizing:border-box;font-size:12px;overflow:hidden}
  .audit .fail{color:#b00020} .audit .warn{color:#9a6a00}
</style></head>
<body>
<header>{{ slug }} / {{ concept }} / round {{ round_n }} &mdash; {{ idea }}</header>
<section class="row" style="height:400px">
  <figure class="panel" style="width:600px;height:400px">{{ panels.black|safe }}<figcaption>black on white</figcaption></figure>
  <figure class="panel dark" style="width:600px;height:400px">{{ panels.white|safe }}<figcaption>white on black</figcaption></figure>
  {% if panels.color %}
  <figure class="panel" style="width:340px;height:400px;background:{{ panels.paper_light }}">{{ panels.color|safe }}<figcaption>colour on light paper</figcaption></figure>
  <figure class="panel dark" style="width:340px;height:400px;background:{{ panels.paper_dark }}">{{ panels.reverse|safe }}<figcaption>reverse on dark paper</figcaption></figure>
  {% endif %}
</section>
<section class="row" style="height:320px;margin-top:20px">
  {% for step in panels.ladder %}
  <figure class="panel" style="width:{{ [step.size, 64]|max + 24 }}px;height:300px">{{ step.svg|safe }}<figcaption>{{ step.size }} {{ step.output }}</figcaption></figure>
  {% endfor %}
  <figure class="panel mirror" style="width:300px;height:300px">{{ panels.mirror|safe }}<figcaption>mirrored</figcaption></figure>
  <figure class="panel rotate" style="width:300px;height:300px">{{ panels.rotate|safe }}<figcaption>rotated 90</figcaption></figure>
</section>
<section class="row" style="height:220px;margin-top:20px">
  <figure class="panel" style="width:440px;height:200px">{{ panels.one_colour[0]|safe }}<figcaption>one colour, lockup 400 wide</figcaption></figure>
  <figure class="panel" style="width:240px;height:200px">{{ panels.one_colour[1]|safe }}<figcaption>one colour, lockup 200 wide</figcaption></figure>
  <div class="audit">
    {% if audit %}
    <b>audit {{ 'ok' if audit.ok else 'FAILED' }}</b>{% if not audit.rendered %} (no raster checks){% endif %}
    {% for m in audit.failures %}<div class="fail">fail: {{ m }}</div>{% endfor %}
    {% for m in audit.warnings %}<div class="warn">warn: {{ m }}</div>{% endfor %}
    {% else %}<b>no audit yet</b>{% endif %}
  </div>
</section>
</body></html>
```

- [ ] **Step 4: Write `sheets.py`**

`src/logomaker/sheets.py`:

```python
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
    return len(list((folder / "renders").glob("round-*"))) + 1 if (folder / "renders").is_dir() else 1


def _palettes(folder: Path):
    tokens_file = folder / "tokens.json"
    if not tokens_file.is_file():
        return None, None
    tokens = load_tokens(tokens_file)
    return tokens.palette("light"), tokens.palette("dark")


def critique_sheet(paths: ProjectPaths, slug: str, concept_name: str, round_n: int | None = None,
                   renderer: Renderer | None = None, audit: AuditResult | None = None) -> dict:
    folder = conceptlib.concept_folder(paths, slug, concept_name)
    module = conceptlib.load_concept(folder)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
    light, dark = _palettes(folder)
    round_n = round_n or next_round(folder)
    out_dir = folder / "renders" / f"round-{round_n}"
    out_dir.mkdir(parents=True, exist_ok=True)
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
    html_path = out_dir / "critique.html"
    html_path.write_text(html, encoding="utf-8")
    if renderer is None:
        with Renderer() as own:
            png = own.html_to_png(html, SHEET_W, SHEET_H, full_page=False)
    else:
        png = renderer.html_to_png(html, SHEET_W, SHEET_H, full_page=False)
    png_path = out_dir / "critique.png"
    png_path.write_bytes(png)
    return {"round": round_n, "critique_png": str(png_path), "critique_html": str(html_path)}
```

- [ ] **Step 5: Add `concept render` and `concept run`; factor the build helper**

In `src/logomaker/cli.py` (import `from . import sheets as sheetlib`), replace the body of `concept_build` with a call to a shared helper and add the two commands:

```python
def _build_concept(paths, slug: str, concept: str, variants: str, tokens_path: str | None):
    folder = conceptlib.concept_folder(paths, slug, concept)
    wanted = tuple(v.strip() for v in variants.split(",") if v.strip())
    tokens_file = Path(tokens_path) if tokens_path else (folder / "tokens.json" if (folder / "tokens.json").is_file() else None)
    palette = dark_palette = None
    if tokens_file is not None:
        tokens = colorlib.load_tokens(tokens_file)
        palette, dark_palette = tokens.palette("light"), tokens.palette("dark")
    if any(v in ("color", "reverse") for v in wanted) and palette is None:
        raise CliError("color and reverse variants need --tokens or a tokens.json in the concept folder")
    module = conceptlib.load_concept(folder)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
    return folder, conceptlib.write_build(folder, outputs, variants=wanted, palette=palette, dark_palette=dark_palette)


@concept_group.command("build")
@click.argument("slug")
@click.argument("concept")
@click.option("--variants", default="black,white")
@click.option("--tokens", "tokens_path", default=None, type=click.Path(exists=True, dir_okay=False))
@command
def concept_build(slug: str, concept: str, variants: str, tokens_path: str | None) -> None:
    paths = project()
    folder, report = _build_concept(paths, slug, concept, variants, tokens_path)
    emit({"concept": str(folder.relative_to(paths.root)), "build": report}, warnings=report["warnings"])


@concept_group.command("render")
@click.argument("slug")
@click.argument("concept")
@click.option("--round", "round_n", type=int, default=None)
@command
def concept_render(slug: str, concept: str, round_n: int | None) -> None:
    with Renderer() as renderer:
        info = sheetlib.critique_sheet(project(), slug, concept, round_n, renderer)
    emit(info)


@concept_group.command("run")
@click.argument("slug")
@click.argument("concept")
@click.option("--round", "round_n", type=int, default=None)
@click.option("--variants", default="black,white")
@click.option("--tokens", "tokens_path", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--no-render", is_flag=True, help="Build and audit only (no Chrome).")
@command
def concept_run(slug: str, concept: str, round_n: int | None, variants: str, tokens_path: str | None, no_render: bool) -> None:
    paths = project()
    folder, report = _build_concept(paths, slug, concept, variants, tokens_path)
    critique = None
    if no_render:
        result = auditlib.audit_concept(paths, slug, concept)
    else:
        with Renderer() as renderer:
            result = auditlib.audit_concept(paths, slug, concept, renderer=renderer)
            critique = sheetlib.critique_sheet(paths, slug, concept, round_n, renderer, audit=result)
    emit({"concept": str(folder.relative_to(paths.root)), "build": report, "audit": result.model_dump(), "critique": critique},
         warnings=report["warnings"] + [f.message for f in result.warnings])
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_sheets.py -q`
Expected: 5 passed.

- [ ] **Step 7: Run the whole suite and commit**

Run: `uv run pytest -q -m "not live"`
Expected: all tests pass (the render-marked tests run because Chrome is installed).

```bash
git add src/logomaker/sheets.py src/logomaker/cli.py templates/sheets/critique.html tests/test_sheets.py
git commit -m "feat: critique sheet and concept render/run commands

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Part 1 is done when

- `uv run pytest -q -m "not live"` passes, and `uv run pytest -q -m live` passes with network.
- `uv run logomaker setup --check` reports Chrome and every module found.
- In a real brand created with `uv run logomaker brand new Example`, copying `tests/fixtures/concepts/good` to `brands/example/concepts/01-good` and running `uv run logomaker fonts fetch "Fira Code"` then `uv run logomaker concept run example 01-good` produces `audit.json` with `"ok": true` and a readable `renders/round-1/critique.png`. Delete `brands/example` afterwards; it is not a real brand.
