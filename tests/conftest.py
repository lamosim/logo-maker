import copy
import json
import shutil
from pathlib import Path

import pytest

from logomaker.paths import ProjectPaths
from logomaker.render import CHROME_APP, Renderer

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures"


def _skip_font_caches(directory: str, names: list[str]) -> set[str]:
    """copytree ignore: leave out every family folder fetched into the repo's assets/fonts/, keep catalog.json."""
    if Path(directory) != REPO / "assets" / "fonts":
        return set()
    return {name for name in names if (Path(directory) / name).is_dir()}


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
        shutil.copytree(REPO / "assets", root / "assets", dirs_exist_ok=True, ignore=_skip_font_caches)
    fixture_fonts = FIXTURES / "fonts"
    if fixture_fonts.exists():
        shutil.copytree(fixture_fonts, root / "assets" / "fonts", dirs_exist_ok=True)
    monkeypatch.setenv("LOGOMAKER_ROOT", str(root))
    monkeypatch.setenv("LOGOMAKER_NO_OPEN", "1")
    monkeypatch.chdir(root)
    return root


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
        "category_uniform": {
            "type_classes": ["geometric sans"], "colours": ["blue"], "motifs": ["upward arrow", "shield", "coin"],
            "competitors": ["FreshBooks", "Wave", "Bonsai", "HoneyBook", "Invoice Ninja"],
        },
        "targets": {
            "shape": 0.4, "symmetry": 0.8, "complexity": "low", "weight": "heavy", "hue_family": "orange", "saturation": "medium",
            "lightness": "mid", "typeface_class": "grotesk", "frame": "open", "dynamism": 0.2, "descriptive_cue": True,
            "name_sound": "back vowel 'o', hard stops: heavy, round-ish",
        },
        "logo_type": "combination",
        "logo_type_reason": "new brand with a short distinctive name",
        "constraints": {"min_lockup_px": 120, "one_colour": True},
    }


def install_concept(project_root: Path, fixture: str, slug: str = "keystone", name: str = "01-good") -> Path:
    """Create brand `slug` (if needed) and copy tests/fixtures/concepts/<fixture> to brands/<slug>/concepts/<name>."""
    from logomaker import registry
    from logomaker.paths import project

    if not (project_root / "brands" / slug).exists():
        registry.new_brand(project(), slug.title(), slug=slug)
    target = project_root / "brands" / slug / "concepts" / name
    shutil.copytree(FIXTURES / "concepts" / fixture, target, dirs_exist_ok=True)
    return target


def write_passing_audit(paths: ProjectPaths, slug: str, folder: Path, tokens_path: str | Path | None = None) -> Path:
    """Write <folder>/audit.json as a passing, rendered audit of the concept as it stands, without Chrome: a synthetic
    AuditResult listing the concept's outputs, with its current audit.concept_fingerprint. The fingerprint covers the
    tokens file (`tokens_path`, else <folder>/tokens.json), so write that first. Returns the file."""
    from logomaker import audit
    from logomaker.kit import concept as conceptlib
    from logomaker.schemas import AuditResult

    outputs = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(folder)))
    fingerprint = audit.concept_fingerprint(paths, slug, folder, tokens_path)
    result = AuditResult(ok=True, rendered=True, outputs=list(outputs), fingerprint=fingerprint)
    path = folder / "audit.json"
    path.write_text(json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8")
    return path


def scorecard(**overrides: int) -> dict:
    """A scorecard.json payload scoring 4 on every criterion but `overrides`: it passes the gate unless one of them drops
    appropriate, simple or legible below 4."""
    from logomaker.schemas import CRITERIA

    scores = {c: 4 for c in CRITERIA}
    scores.update(overrides)
    return {"scores": scores, "evidence": {"appropriate": "arch = holds the invoice together"}}


requires_chrome = pytest.mark.skipif(not CHROME_APP.exists(), reason="Google Chrome is not installed")


@pytest.fixture
def renderer():
    if not CHROME_APP.exists():
        pytest.skip("Google Chrome is not installed")
    with Renderer() as r:
        yield r


class NoChrome:
    """Stands in for render.Renderer. Entering it fails, so a test that gets its own validation error saw no Chrome start."""

    def __enter__(self):
        raise AssertionError("Chrome started")

    def __exit__(self, *exc):
        return False


@pytest.fixture
def no_chrome(monkeypatch):
    """Chrome cannot start: the Renderer the sheets open, and any opened through render, is NoChrome."""
    from logomaker import render, sheets

    monkeypatch.setattr(sheets, "Renderer", NoChrome)
    monkeypatch.setattr(render, "Renderer", NoChrome)


class StubChrome:
    """Stands in for render.Renderer without Chrome: every page renders to placeholder bytes."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def html_to_png(self, *args, **kwargs):
        return b"png"


def no_open_command(argv, **kwargs):
    """subprocess.Popen on a machine without the `open` command."""
    raise FileNotFoundError(2, "No such file or directory", "open")


TERRITORIES = {
    "territories": [
        {
            "slug": "forge", "name": "Forge",
            "embraces": ["dense", "industrial", "warm"], "rejects": ["pastel", "thin lines"],
            "fonts": [{"family": "Fira Code", "weight": 700}, {"family": "Fira Code", "weight": 400}],
            "palette": [{"hex": "#1f1b18", "name": "Coal"}, {"hex": "#e8572a", "name": "Ember"}, {"hex": "#f4e9dc", "name": "Linen"}],
            "shapes": {"corner": 0.15, "stroke": 0.12, "angularity": 0.8, "symmetry": 0.7},
        },
        {
            "slug": "ledger", "name": "Ledger",
            "embraces": ["calm", "precise", "editorial"], "rejects": ["loud colour"],
            "fonts": [{"family": "Fira Code", "weight": 500}],
            "palette": [{"hex": "#14213d", "name": "Ink"}, {"hex": "#fca311", "name": "Amber"}],
            "shapes": {"corner": 0.02, "stroke": 0.08, "angularity": 0.3, "symmetry": 0.9},
        },
    ]
}


@pytest.fixture
def territories_payload() -> dict:
    return copy.deepcopy(TERRITORIES)
