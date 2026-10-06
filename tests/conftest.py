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
