import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image
from pydantic import ValidationError

from logomaker import fonts, registry, sheets
from logomaker.cli import main
from logomaker.paths import project
from logomaker.schemas import TerritoriesSpec, TerritoryShapes
from tests.conftest import StubChrome, no_open_command, requires_chrome


def write_spec(project_root: Path, payload: dict) -> Path:
    """Brand Keystone with `payload` as its territories/territories.json; returns the territories folder."""
    registry.new_brand(project(), "Keystone")
    folder = project_root / "brands" / "keystone" / "territories"
    (folder / "territories.json").write_text(json.dumps(payload))
    return folder


def board(*args: str) -> tuple[int, dict]:
    """`sheet territories keystone` with `args`: the exit code and the JSON payload."""
    result = CliRunner().invoke(main, ["sheet", "territories", "keystone", *args])
    return result.exit_code, json.loads(result.stdout)


def test_spec_validation(territories_payload):
    spec = TerritoriesSpec.model_validate(territories_payload)
    assert [t.slug for t in spec.territories] == ["forge", "ledger"]
    bad = dict(territories_payload)
    bad["territories"] = territories_payload["territories"][:1]
    with pytest.raises(ValidationError):
        TerritoriesSpec.model_validate(bad)
    bad = json.loads(json.dumps(territories_payload))
    bad["territories"][0]["fonts"] = []
    with pytest.raises(ValidationError):
        TerritoriesSpec.model_validate(bad)
    bad = json.loads(json.dumps(territories_payload))
    bad["territories"][0]["palette"][1]["hex"] = "#e8572"
    with pytest.raises(ValidationError, match="'#e8572' is not a valid color"):
        TerritoriesSpec.model_validate(bad)
    bad = json.loads(json.dumps(territories_payload))
    bad["territories"][1]["slug"] = "forge"
    with pytest.raises(ValidationError, match="territory slugs must be unique; repeated: forge"):
        TerritoriesSpec.model_validate(bad)
    bad["territories"][1]["slug"] = "Forge Works"
    with pytest.raises(ValidationError, match="territory slug must be lowercase letters, digits and hyphens"):
        TerritoriesSpec.model_validate(bad)
    shouted = json.loads(json.dumps(territories_payload))
    shouted["territories"][0]["palette"][1]["hex"] = "#E8572A"
    assert TerritoriesSpec.model_validate(shouted).territories[0].palette[1].hex == "#e8572a"
    for weight in (50, 950):  # a font weight runs from 100 to 900
        bad = json.loads(json.dumps(territories_payload))
        bad["territories"][0]["fonts"][0]["weight"] = weight
        with pytest.raises(ValidationError, match=r"territories\.0\.fonts\.0\.weight"):
            TerritoriesSpec.model_validate(bad)


def test_shape_specimens_follow_the_parameters(project_root):
    angular = sheets.shape_specimens(TerritoryShapes(corner=0.0, stroke=0.12, angularity=1.0, symmetry=1.0), "K", "Fira Code", 700)
    soft = sheets.shape_specimens(TerritoryShapes(corner=0.4, stroke=0.12, angularity=0.0, symmetry=0.4), "K", "Fira Code", 700)
    assert len(angular) == 6 and {s["label"] for s in angular} == {"ring", "chevron", "tile", "loop", "bars", "initial"}
    assert all(s["svg"].startswith("<svg") and "<path" in s["svg"] for s in angular)
    assert angular[2]["svg"] != soft[2]["svg"]  # corner radius changes the tile
    assert angular[4]["svg"] != soft[4]["svg"]  # symmetry changes the bars


def test_the_board_sets_the_name_s_first_letter_or_digit(project_root, territories_payload, monkeypatch):
    assert [sheets.initial_of(name) for name in (" Keystone", "3M", "·kite", "—", "")] == ["K", "3", "K", "A", "A"]
    folder = write_spec(project_root, territories_payload)
    state = registry.load_state(project(), "keystone")
    state.name = " keystone"  # as a brand.json written before names were stripped may hold it
    registry.save_state(project(), state)
    initials = []
    specimens = sheets.shape_specimens
    monkeypatch.setattr(sheets, "shape_specimens", lambda shapes, ch, *args: initials.append(ch) or specimens(shapes, ch, *args))
    monkeypatch.setattr(sheets, "Renderer", StubChrome)
    code, payload = board("--no-open")
    assert code == 0 and initials == ["K", "K"] and (folder / "board.html").is_file(), payload


def test_open_file_respects_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LOGOMAKER_NO_OPEN", "1")
    assert sheets.open_file(tmp_path / "x.html") is False
    assert sheets.open_file(tmp_path / "x.html", enabled=False) is False


def test_open_file_runs_open_quietly_and_warns_when_it_cannot(monkeypatch, tmp_path):
    monkeypatch.delenv("LOGOMAKER_NO_OPEN", raising=False)
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kwargs: calls.append((argv, kwargs)))
    path = tmp_path / "board.html"
    assert sheets.open_file(path, enabled=False) is False and calls == []
    assert sheets.open_file(path) is True
    assert calls == [(["open", str(path)], {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL})]
    monkeypatch.setattr(subprocess, "Popen", no_open_command)
    warnings: list[str] = []
    assert sheets.open_file(path, warnings=warnings) is False
    assert warnings == [f"could not open {path}: [Errno 2] No such file or directory: 'open'"]
    assert sheets.open_file(path) is False  # with no list to warn in, the failure is still never raised


@requires_chrome
@pytest.mark.render
def test_board_renders(project_root, territories_payload, renderer):
    folder = write_spec(project_root, territories_payload)
    info = sheets.territories_board(project(), "keystone", renderer=renderer, open_after=False)
    html = Path(info["board_html"]).read_text()
    assert "Forge" in html and "Ledger" in html and "Fira Code 700" in html and "#e8572a" in html
    assert (folder / "board.png").stat().st_size > 10_000
    with Image.open(folder / "board.png") as image:
        assert image.width == sheets.BOARD_W  # the whole page, at the board's width
    assert info["territories"] == ["forge", "ledger"] and info["warnings"] == []


@requires_chrome
@pytest.mark.render
def test_board_cli(project_root, territories_payload):
    # No renderer fixture: the command starts its own Chrome, and Playwright's sync API cannot start a second beside it.
    folder = write_spec(project_root, territories_payload)
    result = CliRunner().invoke(main, ["sheet", "territories", "keystone", "--no-open"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0 and payload["territories"] == ["forge", "ledger"], payload
    assert payload["board_png"] == str(folder / "board.png") and (folder / "board.png").stat().st_size > 10_000


def test_board_without_spec_exits_2(project_root, no_chrome):
    registry.new_brand(project(), "Keystone")
    result = CliRunner().invoke(main, ["sheet", "territories", "keystone", "--no-open"])
    errors = json.loads(result.stdout)["errors"]
    assert result.exit_code == 2 and errors == ["territories/territories.json is missing; write the territories spec first"]


def test_an_invalid_spec_exits_2_naming_the_file_and_the_field(project_root, territories_payload, no_chrome):
    territories_payload["territories"][1]["palette"][0]["hex"] = "inky"
    write_spec(project_root, territories_payload)
    code, payload = board("--no-open")
    assert code == 2 and payload["errors"] == [
        "territories/territories.json is invalid: territories.1.palette.0.hex: Value error, 'inky' is not a valid color"]


def test_uncached_fonts_exit_3_naming_every_family_without_fetching(project_root, territories_payload, no_chrome, monkeypatch):
    monkeypatch.setattr(fonts, "fetch", lambda *args, **kwargs: pytest.fail("the board must never fetch fonts"))
    territories_payload["territories"][0]["fonts"].append({"family": "Nope Sans"})
    territories_payload["territories"][1]["fonts"] = [{"family": "Nada Serif", "weight": 600}, {"family": "Nope Sans", "weight": 700}]
    folder = write_spec(project_root, territories_payload)
    code, payload = board("--no-open")
    assert code == 3 and payload["errors"] == [
        "territories/territories.json names font families that are not cached: Nope Sans, Nada Serif "
        '(run: logomaker fonts fetch "Nope Sans"; run: logomaker fonts fetch "Nada Serif")']
    assert sorted(p.name for p in folder.iterdir()) == ["territories.json"]


def test_a_valid_spec_reaches_chrome_and_a_failed_render_writes_no_board(project_root, territories_payload, no_chrome):
    folder = write_spec(project_root, territories_payload)
    code, payload = board("--no-open")
    # The stand-in is entered once the brand, the spec and the fonts check out: the failures above stopped before Chrome.
    assert code == 2 and payload["errors"] == ["AssertionError: Chrome started"]
    assert sorted(p.name for p in folder.iterdir()) == ["territories.json"]  # rendered first, written after


def test_the_cli_opens_the_board_unless_told_not_to_and_warns_when_it_cannot(project_root, territories_payload, monkeypatch):
    folder = write_spec(project_root, territories_payload)
    monkeypatch.setattr(sheets, "Renderer", StubChrome)
    monkeypatch.delenv("LOGOMAKER_NO_OPEN")
    opened = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kwargs: opened.append(argv))
    code, payload = board("--no-open")
    assert code == 0 and payload["warnings"] == [] and opened == []
    assert payload["board_png"] == str(folder / "board.png") and (folder / "board.png").read_bytes() == b"png"
    html = (folder / "board.html").read_text()
    assert "background:#1f1b18;color:#ffffff" in html and "background:#f4e9dc;color:#111111" in html  # chip text: white on dark
    code, payload = board()
    assert code == 0 and payload["warnings"] == [] and opened == [["open", str(folder / "board.html")]]
    monkeypatch.setattr(subprocess, "Popen", no_open_command)
    code, payload = board()
    assert code == 0 and payload["warnings"] == [f"could not open {folder / 'board.html'}: [Errno 2] No such file or directory: 'open'"]
