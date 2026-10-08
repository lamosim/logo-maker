import json

import pytest
from click.testing import CliRunner
from PIL import Image
from pydantic import ValidationError

from logomaker import knockout
from logomaker.cli import main
from logomaker.paths import project
from logomaker.schemas import ImageSearch, Knockout
from tests.conftest import StubRenderer, install_concept


def run(*args):
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, json.loads(result.stdout)


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
    wipo = ImageSearch(tool="wipo", searched=True, matches=[{"url": "https://branddb.wipo.int/x", "note": "an arch"}])
    assert Knockout(wipo=wipo).wipo_done


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
