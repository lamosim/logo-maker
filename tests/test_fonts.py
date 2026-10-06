import hashlib
import json
from pathlib import Path

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
LICENCES = {"ofl": "OFL", "apache": "Apache", "ufl": "UFL"}
FIXTURE_TTF = Path(__file__).parent / "fixtures" / "fonts" / "firacode" / "FiraCode[wght].ttf"


def test_catalog_is_valid(project_root):
    families = fonts.load_catalog(project())
    assert len(families) >= 60
    assert len({f.slug for f in families}) == len(families)
    for f in families:
        assert f.category in CATEGORIES and len(f.personality) >= 3 and f.license in {"OFL", "Apache", "UFL"}
        assert f.slug == fonts.family_slug(f.family)
        assert f.google_dir and f.license == LICENCES.get(f.google_dir.split("/", 1)[0]), f.family
    assert fonts.find_family(project(), "fira code").google_dir == "ofl/firacode"


def test_fixture_project_fonts_are_catalogue_and_fixtures_only(project_root):
    assert {p.name for p in (project_root / "assets" / "fonts").iterdir()} == {"catalog.json", "firacode"}


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


def test_font_path_needs_a_wght_axis_to_be_variable(project_root):
    for slug, name in (("climatecrisis", "ClimateCrisis[YEAR].ttf"), ("fraunces", "Fraunces[SOFT,WONK,opsz,wght].ttf")):
        (project_root / "assets" / "fonts" / slug).mkdir()
        (project_root / "assets" / "fonts" / slug / name).write_bytes(b"")
    crisis = fonts.font_path(project(), "Climate Crisis", 700)
    assert crisis.variable is False and crisis.weight == 400
    assert fonts.font_path(project(), "Fraunces", 650).variable is True


def test_font_path_missing_family_exits_3(project_root):
    with pytest.raises(CliError) as exc:
        fonts.font_path(project(), "Sora")
    assert exc.value.code == 3 and "logomaker fonts fetch Sora" in str(exc.value)
    with pytest.raises(CliError) as exc:
        fonts.font_path(project(), "Plus Jakarta Sans")
    assert "run: logomaker fonts fetch 'Plus Jakarta Sans'" in str(exc.value)


def test_fonts_list_cli(project_root):
    result = CliRunner().invoke(main, ["fonts", "list", "--category", "mono"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0 and any(f["family"] == "Fira Code" for f in payload["families"])
    unknown = CliRunner().invoke(main, ["fonts", "list", "--category", "nosuch"])
    assert unknown.exit_code == 2 and "humanist sans" in json.loads(unknown.stdout)["errors"][0]


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


RAW = "https://raw.githubusercontent.com/google/fonts/main/apache/test/"


def serve_google_fonts(monkeypatch, files: dict[str, bytes], sizes: dict[str, int] | None = None) -> None:
    """Stand in for GitHub for the family "Test": ofl/test is a 404 and apache/test lists `files`.

    The listing gives each file's real size unless `sizes` overrides it."""
    listing = [
        {"name": name, "size": (sizes or {}).get(name, len(data)), "download_url": RAW + name}
        for name, data in files.items()
    ]

    def fake_get(self, url, **kwargs):
        request = httpx.Request("GET", url)
        if url == fonts.GITHUB_CONTENTS.format(dir="apache/test"):
            return httpx.Response(200, json=listing, request=request)
        if url.startswith(RAW):
            return httpx.Response(200, content=files[url.removeprefix(RAW)], request=request)
        return httpx.Response(404, json={"message": "Not Found"}, request=request)

    monkeypatch.setattr(httpx.Client, "get", fake_get)


def test_fetch_downloads_listing_into_cache(project_root, monkeypatch):
    font, licence = FIXTURE_TTF.read_bytes(), b"SIL Open Font License, Version 1.1\n"
    serve_google_fonts(monkeypatch, {"Test[wght].ttf": font, "OFL.txt": licence})
    manifest = fonts.fetch(project(), "Test")
    assert manifest["google_dir"] == "apache/test"  # ofl/test was a 404, so the probe moved on
    assert {f["name"]: f["sha256"] for f in manifest["files"]} == {
        "Test[wght].ttf": hashlib.sha256(font).hexdigest(),
        "OFL.txt": hashlib.sha256(licence).hexdigest(),
    }
    folder = project_root / "assets" / "fonts" / "test"
    assert json.loads((folder / "manifest.json").read_text(encoding="utf-8")) == manifest
    assert fonts.font_path(project(), "Test", 650).variable is True


def test_failed_fetch_leaves_the_cache_as_it_was(project_root, monkeypatch):
    folder = project_root / "assets" / "fonts" / "test"
    staging = folder.with_name("test.tmp")
    serve_google_fonts(monkeypatch, {"OFL.txt": b"licence", "Test[wght].ttf": b"not a font"})
    with pytest.raises(CliError) as exc:
        fonts.fetch(project(), "Test")
    assert exc.value.code == 3 and "not a valid TrueType file" in str(exc.value)
    assert not folder.exists() and not staging.exists()

    font = FIXTURE_TTF.read_bytes()
    serve_google_fonts(monkeypatch, {"OFL.txt": b"licence", "Test[wght].ttf": font})
    fonts.fetch(project(), "Test")
    truncated = {"OFL.txt": b"new licence", "Test[wght].ttf": font[:1000]}
    serve_google_fonts(monkeypatch, truncated, sizes={"Test[wght].ttf": len(font)})
    with pytest.raises(CliError) as exc:
        fonts.fetch(project(), "Test")
    message = str(exc.value)
    assert exc.value.code == 3 and "Test[wght].ttf" in message and "1000" in message and str(len(font)) in message
    assert (folder / "OFL.txt").read_bytes() == b"licence" and (folder / "Test[wght].ttf").read_bytes() == font
    assert not staging.exists()


def test_fetch_rejects_a_name_without_letters_or_digits(project_root, monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", lambda *args, **kwargs: pytest.fail("no request expected"))
    with pytest.raises(CliError) as exc:
        fonts.fetch(project(), "!!!")
    assert exc.value.code == 2


@pytest.mark.live
def test_fetch_sora_live(project_root):
    manifest = fonts.fetch(project(), "Sora")
    assert any(f["name"].endswith(".ttf") for f in manifest["files"])
    assert (project_root / "assets" / "fonts" / "sora" / "OFL.txt").is_file()
    assert fonts.font_path(project(), "Sora", 650).variable is True
