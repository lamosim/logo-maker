import io
import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image

from logomaker import sheets
from logomaker.cli import main
from logomaker.output import CliError
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
    png = Path(info["critique_png"]).read_bytes()
    image = Image.open(io.BytesIO(png))
    assert image.size == (sheets.SHEET_W, sheets.SHEET_H)
    assert ink_mask(png).mean() > 0.01
    html = Path(info["critique_html"]).read_text()
    assert "mirrored" in html and "no audit yet" in html and "16 favicon" in html


@requires_chrome
@pytest.mark.render
def test_concept_run_cli_builds_audits_renders_and_increments_rounds(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")
    (folder / "tokens.json").write_text(json.dumps(good_tokens()))
    runner = CliRunner()
    result = runner.invoke(main, ["concept", "run", "keystone", "01-good", "--variants", "black,white,color,reverse"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0, payload
    assert payload["audit"]["ok"] and payload["audit"]["rendered"] and payload["critique"]["round"] == 1
    assert "full-lockup-color.svg" in payload["build"]["files"]
    html = Path(payload["critique"]["critique_html"]).read_text()
    assert "reverse" in html and "audit ok" in html
    payload = json.loads(runner.invoke(main, ["concept", "run", "keystone", "01-good"]).stdout)
    assert payload["critique"]["round"] == 2


class FailingRenderer:
    """Stands in for Chrome failing mid-render (Renderer raises CliError exit 3)."""

    def html_to_png(self, *args, **kwargs):
        raise CliError("Chrome failed while rendering: boom", code=3)


def test_next_round_never_reuses_an_existing_round(project_root):
    folder = install_concept(project_root, "good")
    (folder / "renders" / "round-1").mkdir(parents=True)
    (folder / "renders" / "round-3").mkdir()  # made with --round 3; counting folders would hand out 3 again
    assert sheets.next_round(folder) == 4


def test_failed_render_leaves_no_round_behind(project_root):
    folder = install_concept(project_root, "good")
    with pytest.raises(CliError) as err:
        sheets.critique_sheet(project(), "keystone", "01-good", renderer=FailingRenderer())
    assert err.value.code == 3 and not (folder / "renders").exists()
    assert sheets.next_round(folder) == 1


def test_broken_tokens_stop_the_sheet_and_name_the_file(project_root):
    folder = install_concept(project_root, "good")
    (folder / "tokens.json").write_text("{}")
    with pytest.raises(CliError, match="01-good/tokens.json is invalid"):
        sheets.critique_sheet(project(), "keystone", "01-good", renderer=FailingRenderer())
    assert not (folder / "renders").exists()


def test_concept_run_without_render_builds_and_audits_only(project_root):
    folder = install_concept(project_root, "good")
    (folder / "tokens.json").write_text('{"colors": ')  # a draft: black and white builds never read it
    result = CliRunner().invoke(main, ["concept", "run", "keystone", "01-good", "--no-render"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0, payload
    assert payload["concept"] == "brands/keystone/concepts/01-good" and "full-lockup-black.svg" in payload["build"]["files"]
    assert payload["critique"] is None and payload["audit"]["rendered"] is False
    assert [f["check"] for f in payload["audit"]["failures"]] == ["tokens"]  # the audit still reports the draft
    assert not (folder / "renders").exists()


def test_round_must_be_positive(project_root):
    install_concept(project_root, "good")
    for command in ("render", "run"):
        result = CliRunner().invoke(main, ["concept", command, "keystone", "01-good", "--round", "0"])
        payload = json.loads(result.stdout)
        assert result.exit_code == 2 and "--round" in payload["errors"][0], payload


@requires_chrome
@pytest.mark.render
def test_concept_render_cli_draws_the_requested_round_with_the_saved_audit(project_root):
    folder = install_concept(project_root, "good")
    runner = CliRunner()
    assert runner.invoke(main, ["concept", "audit", "keystone", "01-good", "--no-render"]).exit_code == 0
    result = runner.invoke(main, ["concept", "render", "keystone", "01-good", "--round", "3"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0, payload
    round_dir = folder / "renders" / "round-3"
    assert payload["round"] == 3 and (round_dir / "critique.png").is_file()
    html = (round_dir / "critique.html").read_text()
    assert "audit ok" in html and "(no raster checks)" in html
    assert sheets.next_round(folder) == 4
