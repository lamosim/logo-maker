import json

import httpx
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
    payload = json.loads(result.stdout)
    assert result.exit_code == 0 and any(f["family"] == "Fira Code" for f in payload["families"])


def test_fetch_reports_github_errors(project_root, monkeypatch):
    calls = []

    def rate_limited(self, url, **kwargs):
        calls.append(url)
        return httpx.Response(403, json={"message": "API rate limit exceeded"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", rate_limited)
    with pytest.raises(CliError) as exc:
        fonts.fetch(project(), "Sora")
    message = str(exc.value)
    assert exc.value.code == 3 and "403" in message and "rate limit" in message and "Sora" in message
    assert calls == [fonts.GITHUB_CONTENTS.format(dir="ofl/sora")]  # a non-404 stops the probe


@pytest.mark.live
def test_fetch_sora_live(project_root):
    manifest = fonts.fetch(project(), "Sora")
    assert any(f["name"].endswith(".ttf") for f in manifest["files"])
    assert (project_root / "assets" / "fonts" / "sora" / "OFL.txt").is_file()
    assert fonts.font_path(project(), "Sora", 650).variable is True
