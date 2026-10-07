import copy
import io
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from logomaker.paths import ProjectPaths
from logomaker.render import CHROME_APP, Renderer, svg_size
from logomaker.schemas import PHASE_ORDER, Phase

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


BRIEF = {
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
def brief_payload() -> dict:
    return copy.deepcopy(BRIEF)


STRATEGY = {
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


@pytest.fixture
def strategy_payload() -> dict:
    return copy.deepcopy(STRATEGY)


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


class StubRenderer:
    """Stands in for render.Renderer without Chrome, for the package builder: svg_to_png and html_to_png return real PNGs
    of the size asked for, a block of `ink` (RGBA) over the middle half of a transparent canvas (of `background`, when
    given); `ink=None` draws nothing, a blank render, and `bleed=True` inks the whole canvas, as a solid mark with no holes
    fills its own viewBox. html_to_pdf returns a one-page PDF. `calls` records every svg_to_png as (svg, width, height,
    background)."""

    def __init__(self, ink: tuple[int, int, int, int] | None = (31, 27, 24, 255), bleed: bool = False):
        self.ink, self.bleed = ink, bleed
        self.calls: list[tuple[str, int, int, str | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _png(self, width: int, height: int, background: str | None = None) -> bytes:
        image = Image.new("RGBA", (width, height), background or (0, 0, 0, 0))
        if self.ink is not None:
            box = (0, 0, width - 1, height - 1) if self.bleed else (width // 4, height // 4, 3 * width // 4, 3 * height // 4)
            ImageDraw.Draw(image).rectangle(box, fill=self.ink)
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()

    def svg_to_png(self, svg: str, width: int, height: int | None = None, background: str | None = None) -> bytes:
        height = height or svg_size(svg, width)[1]
        self.calls.append((svg, width, height, background))
        return self._png(width, height, background)

    def html_to_png(self, html: str, width: int, height: int | None = None, full_page: bool = True, transparent: bool = False) -> bytes:
        return self._png(width, height or width, None if transparent else "#ffffff")

    def html_to_pdf(self, html: str, paper: str = "letter") -> bytes:
        out = io.BytesIO()
        Image.new("RGB", (8, 8), "#ffffff").save(out, format="PDF")
        return out.getvalue()


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


RATIONALE = "Keystone's mark is the piece that holds the arch: a ring that closes only when the name is beside it.\n"


def make_final_brand(project_root: Path, wordmark_only: bool = False, with_tokens: bool = True,
                     phase: Phase | None = Phase.refinement) -> Path:
    """Brand keystone with every earlier phase's artifacts and a final/ ready to refine and package; returns final/.

    The brand gets brief.md and brief.json (BRIEF), strategy.md and strategy.json (STRATEGY), territories.json
    (TERRITORIES), the forge territory, concept 01-good (the good fixture, with a passing scorecard and audit), the
    fintech industry and a wordmark font. final/ gets a copy of the good concept (the wordmark-only one with
    `wordmark_only`), params.json, tokens.json (good_tokens(), unless `with_tokens` is False), rationale.md and a passing
    audit. The brand then advances one phase at a time to `phase` through registry.advance, so the registry's own gates
    vouch for the artifacts; None leaves it where it is (intake for a new brand).
    """
    from logomaker import registry
    from logomaker.paths import project
    from tests.test_color import good_tokens

    paths = project()
    brand = project_root / "brands" / "keystone"
    if not brand.exists():
        registry.new_brand(paths, "Keystone")
    (brand / "brief.md").write_text("# Brief\n")
    (brand / "brief.json").write_text(json.dumps(BRIEF))
    (brand / "strategy.md").write_text("# Strategy\n")
    (brand / "strategy.json").write_text(json.dumps(STRATEGY))
    (brand / "territories" / "territories.json").write_text(json.dumps(TERRITORIES))
    # Before either audit: their fingerprints cover the industry (brand.json's and the brief's).
    registry.set_fields(paths, "keystone", territory="forge", concept="01-good", industry="fintech", fonts=["wordmark=Fira Code:600"])
    concept = install_concept(project_root, "good")
    (concept / "scorecard.json").write_text(json.dumps(scorecard()))
    write_passing_audit(paths, "keystone", concept)
    final = brand / "final"
    shutil.copy(FIXTURES / "concepts" / ("wordmark_only" if wordmark_only else "good") / "concept.py", final / "concept.py")
    (final / "params.json").write_text("{}\n")
    if with_tokens:
        (final / "tokens.json").write_text(json.dumps(good_tokens()))
    (final / "rationale.md").write_text(RATIONALE)
    write_passing_audit(paths, "keystone", final)  # after tokens.json, which its fingerprint covers
    if phase is not None:
        state = registry.load_state(paths, "keystone")
        while PHASE_ORDER.index(state.phase) < PHASE_ORDER.index(phase):
            state = registry.advance(paths, "keystone", registry.allowed_next(state))
        assert state.phase == phase, f"brand keystone is already past {phase.value} (in {state.phase.value})"
    return final
