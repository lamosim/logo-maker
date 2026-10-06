import os
import shutil
from pathlib import Path

import pytest

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
        "category_uniform": {"type_classes": ["geometric sans"], "colours": ["blue"], "motifs": ["upward arrow", "shield", "coin"], "competitors": ["FreshBooks", "Wave", "Bonsai", "HoneyBook", "Invoice Ninja"]},
        "targets": {"shape": 0.4, "symmetry": 0.8, "complexity": "low", "weight": "heavy", "hue_family": "orange", "saturation": "medium", "lightness": "mid", "typeface_class": "grotesk", "frame": "open", "dynamism": 0.2, "descriptive_cue": True, "name_sound": "back vowel 'o', hard stops: heavy, round-ish"},
        "logo_type": "combination",
        "logo_type_reason": "new brand with a short distinctive name",
        "constraints": {"min_lockup_px": 120, "one_colour": True},
    }
