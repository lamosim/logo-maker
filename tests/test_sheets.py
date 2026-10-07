import io
import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image

from logomaker import audit as auditlib
from logomaker import sheets
from logomaker.cli import main
from logomaker.kit import concept as conceptlib
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.raster import ink_mask
from logomaker.schemas import AuditResult, Finding
from tests.conftest import install_concept, requires_chrome

SVG_SIZES = re.compile(r'<svg width="(\d+)" height="(\d+)"')
AUDIT_LINE_DIV = re.compile(r'<div class="(fail|warn|info|more)">(.*?)</div>')


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
    from tests.conftest import good_tokens

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


@requires_chrome
@pytest.mark.render
def test_a_rendered_run_with_broken_tokens_names_them_and_leaves_the_build_and_audit(project_root):
    folder = install_concept(project_root, "good")
    (folder / "tokens.json").write_text("{}")
    runner = CliRunner()
    result = runner.invoke(main, ["concept", "run", "keystone", "01-good"])  # black and white: the build never reads tokens
    payload = json.loads(result.stdout)
    assert result.exit_code == 2 and "01-good/tokens.json is invalid" in payload["errors"][0]
    assert (folder / "build" / "full-lockup-black.svg").is_file() and not (folder / "renders").exists()
    saved = json.loads((folder / "audit.json").read_text())  # the audit ran, rendered, and recorded the broken tokens
    assert saved["rendered"] and [f["check"] for f in saved["failures"]] == ["tokens"]
    build = {p.name: p.read_bytes() for p in sorted((folder / "build").iterdir())}
    audit_json = (folder / "audit.json").read_text()
    result = runner.invoke(main, ["concept", "run", "keystone", "01-good", "--variants", "black,white,color"])  # colour needs the tokens
    payload = json.loads(result.stdout)
    assert result.exit_code == 2 and "01-good/tokens.json is invalid" in payload["errors"][0]
    assert {p.name: p.read_bytes() for p in sorted((folder / "build").iterdir())} == build
    assert (folder / "audit.json").read_text() == audit_json and not (folder / "renders").exists()


class FailingRenderer:
    """Stands in for Chrome failing mid-render (Renderer raises CliError exit 3)."""

    def html_to_png(self, *args, **kwargs):
        raise CliError("Chrome failed while rendering: boom", code=3)


class StubRenderer:
    """Returns placeholder bytes, so a test can read the sheet's HTML without Chrome."""

    def html_to_png(self, *args, **kwargs):
        return b"png"


def finding(check: str, severity: str, message: str) -> Finding:
    return Finding(check=check, severity=severity, message=message)


def write_palette(project_root):
    """good_tokens() outside the concept folder, so it can reach a sheet only when passed as a tokens path."""
    from tests.conftest import good_tokens

    palette = project_root / "palette.json"
    palette.write_text(json.dumps(good_tokens()))
    return palette


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
    assert result.exit_code == 2 and payload["ok"] is False, payload  # the audit fails, so the run does
    assert payload["concept"] == "brands/keystone/concepts/01-good" and "full-lockup-black.svg" in payload["build"]["files"]
    assert payload["critique"] is None and payload["audit"]["rendered"] is False
    assert [f["check"] for f in payload["audit"]["failures"]] == ["tokens"]  # the audit still reports the draft
    assert payload["errors"] == [f["message"] for f in payload["audit"]["failures"]]
    assert not (folder / "renders").exists()


@requires_chrome
@pytest.mark.render
def test_a_failing_rendered_run_still_writes_everything_and_exits_2(project_root):
    folder = install_concept(project_root, "thin_stroke", name="07-thin")
    result = CliRunner().invoke(main, ["concept", "run", "keystone", "07-thin"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 2 and payload["ok"] is False, payload
    failures = payload["audit"]["failures"]
    assert failures and payload["errors"] == [f["message"] for f in failures]
    assert all(f["message"] in payload["warnings"] for f in payload["audit"]["warnings"])
    assert payload["critique"]["round"] == 1 and Path(payload["critique"]["critique_png"]).is_file()
    assert (folder / "build" / "full-symbol-black.svg").is_file() and not json.loads((folder / "audit.json").read_text())["ok"]


def test_round_must_be_positive(project_root):
    install_concept(project_root, "good")
    for command in ("render", "run"):
        result = CliRunner().invoke(main, ["concept", command, "keystone", "01-good", "--round", "0"])
        payload = json.loads(result.stdout)
        assert result.exit_code == 2 and "--round" in payload["errors"][0], payload


@requires_chrome
@pytest.mark.render
def test_concept_render_cli_takes_round_and_tokens_and_shows_the_saved_audit(project_root):
    folder = install_concept(project_root, "good")
    palette = write_palette(project_root)
    runner = CliRunner()
    assert runner.invoke(main, ["concept", "audit", "keystone", "01-good", "--no-render"]).exit_code == 0
    result = runner.invoke(main, ["concept", "render", "keystone", "01-good", "--round", "3", "--tokens", str(palette)])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0, payload
    round_dir = folder / "renders" / "round-3"
    assert payload["round"] == 3 and (round_dir / "critique.png").is_file()
    html = (round_dir / "critique.html").read_text()
    assert "audit ok" in html and "(no raster checks)" in html and "info: full-symbol: symbol has" in html
    assert "reverse on dark paper" in html
    assert sheets.next_round(folder) == 4


@requires_chrome
@pytest.mark.render
def test_concept_run_passes_its_tokens_to_the_sheet(project_root):
    install_concept(project_root, "good")
    palette = write_palette(project_root)
    result = CliRunner().invoke(main, ["concept", "run", "keystone", "01-good", "--variants", "black,color", "--tokens", str(palette)])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0, payload
    assert "full-lockup-color.svg" in payload["build"]["files"]
    html = Path(payload["critique"]["critique_html"]).read_text()
    assert "colour on light paper" in html and "info: favicon: thinnest feature" in html


def heading(info: dict) -> str:
    """The audit box's bold heading in a sheet's HTML."""
    return re.search(r"<b>(audit [^<]*)</b>", Path(info["critique_html"]).read_text()).group(1)


def test_a_broken_audit_json_stops_the_sheet_and_names_it(project_root):
    folder = install_concept(project_root, "good")
    for content in ("{not json", '{"ok": "maybe"}', b"\xff\xfe"):
        path = folder / "audit.json"
        path.write_bytes(content) if isinstance(content, bytes) else path.write_text(content)
        with pytest.raises(CliError) as err:
            sheets.critique_sheet(project(), "keystone", "01-good", renderer=StubRenderer())
        message = str(err.value)
        assert err.value.code == 2 and message.startswith(f"{path} is not a valid audit (")
        assert message.endswith("; re-run: logomaker concept audit keystone 01-good")
    assert not (folder / "renders").exists()


def test_the_sheet_marks_an_audit_that_no_longer_matches_the_concept(project_root):
    folder = install_concept(project_root, "good")
    auditlib.audit_concept(project(), "keystone", "01-good")

    def sheet(**kwargs):
        return sheets.critique_sheet(project(), "keystone", "01-good", renderer=StubRenderer(), **kwargs)

    stale = "(stale — re-run: logomaker concept audit keystone 01-good)"
    assert heading(sheet()) == "audit ok"
    (folder / "concept.py").write_text((folder / "concept.py").read_text() + "# edited after the audit\n")
    assert heading(sheet()) == f"audit ok {stale}"
    assert heading(sheet(audit=AuditResult(ok=False, fingerprint="0" * 64))) == f"audit FAILED {stale}"
    fresh = auditlib.audit_concept(project(), "keystone", "01-good")
    assert heading(sheet(audit=fresh)) == "audit ok"  # concept run hands the sheet its own fresh audit


def test_the_sheet_draws_the_outputs_it_is_given_without_rebuilding(project_root, monkeypatch):
    folder = install_concept(project_root, "good")
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(folder)))

    def no_rebuild(*args, **kwargs):
        raise AssertionError("the sheet rebuilt the concept")

    monkeypatch.setattr(conceptlib, "build_tiers", no_rebuild)
    info = sheets.critique_sheet(project(), "keystone", "01-good", renderer=StubRenderer(), outputs=outputs)
    assert "16 favicon" in Path(info["critique_html"]).read_text()


@requires_chrome
@pytest.mark.render
def test_concept_run_builds_the_concept_three_times_not_four(project_root, monkeypatch):
    install_concept(project_root, "good")
    calls = []
    build_tiers = conceptlib.build_tiers
    monkeypatch.setattr(conceptlib, "build_tiers", lambda *args, **kwargs: calls.append(1) or build_tiers(*args, **kwargs))
    result = CliRunner().invoke(main, ["concept", "run", "keystone", "01-good"])
    assert result.exit_code == 0, result.stdout
    assert len(calls) == 3  # the build, then the audit's two (the determinism check); the sheet reuses the build


def test_the_ladder_picks_each_steps_output_once(project_root, monkeypatch):
    install_concept(project_root, "good")
    sizes = []
    pick_output = conceptlib.pick_output
    monkeypatch.setattr(conceptlib, "pick_output", lambda outputs, size: sizes.append(size) or pick_output(outputs, size))
    sheets.critique_sheet(project(), "keystone", "01-good", renderer=StubRenderer())
    assert sorted(sizes) == sorted([256, *sheets.LADDER])  # the mirrored and rotated source, then each step once


def test_a_long_idea_stays_on_one_header_line(project_root):
    install_concept(project_root, "good")
    html = Path(sheets.critique_sheet(project(), "keystone", "01-good", renderer=StubRenderer())["critique_html"]).read_text()
    header = re.search(r"header\{([^}]*)\}", html).group(1)
    assert all(rule in header for rule in ("white-space:nowrap", "overflow:hidden", "text-overflow:ellipsis"))


def test_one_colour_test_draws_the_audited_tiers_with_fallbacks():
    every_tier = {"full-lockup": 1, "full-symbol": 1, "small": 1, "favicon": 1}
    assert sheets._one_colour_outputs(every_tier) == [(64, "full-symbol"), (32, "small")]
    assert sheets._one_colour_outputs({"full-lockup": 1, "full-symbol": 1}) == [(64, "full-symbol"), (32, "full-symbol")]
    assert sheets._one_colour_outputs({"full-lockup": 1}) == [(64, "full-lockup"), (32, "full-lockup")]


def test_audit_lines_put_failures_then_warnings_then_measurements_within_budget():
    result = AuditResult(
        ok=False,
        failures=[finding("min_feature", "fail", "f1"), finding("tokens", "fail", "f2")],
        warnings=[finding("tiers", "warn", "w1")],
        info=[finding("bounds", "info", "b1"), finding("anchors", "info", "a1"), finding("industry", "info", "i1"),
              finding("min_feature", "info", "m1")],
    )
    lines = sheets._audit_lines(result, budget=5)  # exactly fits
    assert [(line["kind"], line["text"]) for line in lines] == [
        ("fail", "fail: f1"), ("fail", "fail: f2"), ("warn", "warn: w1"), ("info", "info: a1"), ("info", "info: m1"),
    ]
    assert [line["text"] for line in sheets._audit_lines(result, budget=3)] == ["fail: f1", "fail: f2", "+3 more (see audit.json)"]


def test_palettes_prefer_an_explicit_tokens_file(project_root):
    folder = install_concept(project_root, "good")
    palette = write_palette(project_root)
    assert sheets._palettes(folder) == (None, None)
    (folder / "tokens.json").write_text("{}")  # broken, but an explicit file takes its place
    light, dark = sheets._palettes(folder, palette)
    assert light["primary"] == "#e8572a" and dark["paper"] == "#1f1b18"
    with pytest.raises(CliError, match="01-good/tokens.json is invalid"):
        sheets._palettes(folder)


def test_sheet_draws_spec_sizes_and_never_drops_audit_lines_silently(project_root):
    install_concept(project_root, "good")
    many = AuditResult(ok=False, failures=[finding("min_feature", "fail", f"problem {i}") for i in range(60)])
    palette = write_palette(project_root)
    info = sheets.critique_sheet(project(), "keystone", "01-good", renderer=StubRenderer(), audit=many, tokens_path=palette)
    html = Path(info["critique_html"]).read_text()
    longest = [max(int(w), int(h)) for w, h in SVG_SIZES.findall(html)]
    # Lockups black, white, colour, reverse; the ladder; mirrored and rotated; the one-colour test.
    assert longest == [512, 512, 384, 384, *sheets.LADDER, 256, 256, 64, 32]
    assert "one colour 64 full-symbol" in html and "one colour 32 small" in html
    lines = AUDIT_LINE_DIV.findall(html)
    assert len(lines) == sheets.AUDIT_LINES and lines[0] == ("fail", "fail: problem 0")
    assert lines[-1] == ("more", f"+{60 - (sheets.AUDIT_LINES - 1)} more (see audit.json)")
