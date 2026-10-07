import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image

from logomaker import registry, sheets
from logomaker.cli import main
from logomaker.kit.mark import Mark
from logomaker.kit.primitives import rect
from logomaker.output import CliError
from logomaker.paths import project
from tests.conftest import FIXTURES, StubChrome, good_tokens, make_final_brand, no_open_command, requires_chrome, write_passing_audit

MISSING = "final/concept.py is missing; copy the chosen concept into final/ first"
PRIMARY = "#0f7b6c"  # a teal light primary, distinct from the fixture tokens' #e8572a
SVG_SIZES = re.compile(r'<svg width="(\d+)" height="(\d+)"')
CONTRAST_ROW = re.compile(r'<tr><td>(\w+)</td><td>(\w+)</td>(?:<td>[^<]*</td>){4}<td>([\d.]+) / Lc ([\d.]+)</td><td class="(ok|bad)">')


def not_drawn(tier: str) -> str:
    return f"tier {tier} is not drawn yet; exports will fall back to the next larger build"


def refine(**kwargs) -> tuple[dict, str]:
    """sheets.refine_sheet for brand keystone without Chrome: its result and the sheet's HTML."""
    info = sheets.refine_sheet(project(), "keystone", renderer=StubChrome(), open_after=False, **kwargs)
    return info, Path(info["sheet_html"]).read_text()


def sections(html: str) -> dict[str, str]:
    """The sheet's sections, each heading (up to any parenthesis) mapped to the HTML before the next heading."""
    parts = re.split(r"<h2>([^<(]*)[^<]*</h2>", html)
    return {title.strip(): body for title, body in zip(parts[1::2], parts[2::2], strict=True)}


def captions(html: str) -> list[str]:
    return re.findall(r"<figcaption>(.*?)</figcaption>", html)


def test_clear_space_svg_draws_the_guides():
    svg = sheets.clear_space_svg(Mark(symbol=rect(0, 0, 100, 50)), 20)
    # Padded by x and half the 1-unit stroke, so the outer dashed rectangle (-70 -45 140 90) is drawn whole.
    assert svg.count("<rect") == 3 and 'stroke-dasharray' in svg and 'viewBox="-70.5 -45.5 141 91"' in svg
    assert '<rect x="-70" y="-45" width="140" height="90" fill="none" stroke="#e8572a" stroke-width="1"' in svg


def test_refine_needs_final(project_root):
    registry.new_brand(project(), "Keystone")
    with pytest.raises(CliError) as exc:
        sheets.refine_sheet(project(), "keystone", open_after=False)
    assert "final/concept.py" in str(exc.value)


def test_the_cli_refuses_a_missing_final_concept_or_broken_tokens_before_chrome_starts(project_root, no_chrome):
    registry.new_brand(project(), "Keystone")

    def sheet() -> tuple[int, list[str]]:
        result = CliRunner().invoke(main, ["sheet", "refine", "keystone", "--no-open"])
        return result.exit_code, json.loads(result.stdout)["errors"]

    assert sheet() == (2, [MISSING])
    final = make_final_brand(project_root)
    (final / "tokens.json").write_text("{}")
    write_passing_audit(project(), "keystone", final)  # an audit of the mark with these tokens: the tokens are what stops it
    code, errors = sheet()
    assert code == 2 and errors[0].startswith(f"{final / 'tokens.json'} is invalid: ")
    assert not list((project_root / "brands" / "keystone" / "sheets").iterdir())


def test_the_sheet_refuses_a_final_mark_without_a_passing_audit_before_chrome_starts(project_root, no_chrome):
    final = make_final_brand(project_root)
    audit = final / "audit.json"
    passing = json.loads(audit.read_text())
    refusal = "the refine sheet needs a passing audit of the final mark: final/audit.json {}"
    audit_final = "logomaker concept audit keystone final"
    stale = ("is stale (concept.py, params.json, tokens.json, the brand's industry or minimum sizes, or cliches.json "
             f"changed); re-run: {audit_final}")

    def sheet() -> tuple[int, list[str]]:
        result = CliRunner().invoke(main, ["sheet", "refine", "keystone", "--no-open"])
        return result.exit_code, json.loads(result.stdout)["errors"]

    audit.write_text(json.dumps({**passing, "ok": False}))
    assert sheet() == (2, [refusal.format(f"has failures; fix them, then re-run: {audit_final}")])
    audit.write_text(json.dumps(passing))
    (final / "params.json").write_text('{"stroke": 80}')  # the final mark changed after its audit
    assert sheet() == (2, [refusal.format(stale)])
    audit.unlink()
    assert sheet() == (2, [refusal.format(f"is missing (run: {audit_final})")])
    assert not list((project_root / "brands" / "keystone" / "sheets").iterdir())


def test_a_final_concept_reaches_chrome_and_a_failed_render_writes_no_sheet(project_root, no_chrome):
    make_final_brand(project_root)
    sheets_dir = project_root / "brands" / "keystone" / "sheets"
    sheets_dir.rmdir()
    result = CliRunner().invoke(main, ["sheet", "refine", "keystone", "--no-open"])
    payload = json.loads(result.stdout)
    # The stand-in is entered once final/ has loaded and built: the refusal above stopped before Chrome.
    assert result.exit_code != 0 and "Chrome started" in payload["errors"][0]
    assert not sheets_dir.exists()  # rendered first; the folder and both files come after


def test_the_round_is_the_shared_positive_option(project_root):
    result = CliRunner().invoke(main, ["sheet", "refine", "keystone", "--round", "0"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 2 and "--round" in payload["errors"][0], payload

    def round_option(group: str, command: str) -> dict:
        return next(p for p in main.commands[group].commands[command].params if p.name == "round_n").to_info_dict()

    assert round_option("sheet", "refine") == round_option("concept", "render")


def test_a_default_round_is_one_past_the_highest_never_a_count(project_root):
    make_final_brand(project_root)
    sheets_dir = project_root / "brands" / "keystone" / "sheets"
    for name in ("refine-1.html", "refine-3.html", "concepts.html"):  # refine-3 made with --round 3
        (sheets_dir / name).write_text("old")
    info, html = refine()
    assert info["round"] == 4 and info["sheet_png"] == str(sheets_dir / "refine-4.png")
    assert (sheets_dir / "refine-4.png").read_bytes() == b"png" and "refinement round 4" in html
    info, _ = refine(round_n=3)  # an explicit round overwrites
    assert info["round"] == 3 and "refinement round 3" in (sheets_dir / "refine-3.html").read_text()


def test_the_sheet_draws_every_section_at_its_size(project_root):
    final = make_final_brand(project_root)
    tokens = good_tokens()
    tokens["colors"]["ember"]["hex"] = PRIMARY  # a primary of these tokens alone, which no accent written into the code can match
    (final / "tokens.json").write_text(json.dumps(tokens))
    write_passing_audit(project(), "keystone", final)  # its fingerprint covers tokens.json
    info, html = refine()
    part = sections(html)
    assert list(part) == ["Tiers", "Lockups", "Colour variants", "Clear space", "Minimum sizes", "Colour-vision simulations",
                          "Contrast"]
    assert captions(part["Tiers"]) == ["full lockup 400", "compact 160", "small 64", "favicon 32"]
    assert [max(int(w), int(h)) for w, h in SVG_SIZES.findall(part["Tiers"])] == [400, 160, 64, 32]
    assert captions(part["Lockups"]) == ["horizontal", "stacked", "symbol", "wordmark"]
    assert captions(part["Colour variants"]) == ["color", "reverse", "black", "white", "mono (currentColor)"]
    assert 'fill="currentColor"' in part["Colour variants"]
    # mono takes the colour of the CSS around it: previewed in the light palette's primary, the tokens' own colour
    assert re.findall(r";color:([^\"]+)\">", part["Colour variants"]) == ["inherit"] * 4 + [PRIMARY]
    widths = [int(w) for w in re.findall(r'<figure class="panel[^"]*" style="width:(\d+)px', part["Colour variants"])]
    assert len(widths) == 5 and sum(widths) + 4 * 16 <= sheets.REFINE_W - 2 * 24  # one row: the body's padding is 24 px a side
    assert captions(part["Clear space"]) == ["clear space = one x on every side"]
    # The ladder at the brand's minimum sizes, each lockup as wide as its rule; the mark and favicon by the tier rules.
    assert captions(part["Minimum sizes"]) == ["horizontal 120 px / 25 mm", "stacked 160 px / 25 mm", "mark 24 px / 6 mm",
                                               "favicon 16 px"]
    assert [int(w) for w, _ in SVG_SIZES.findall(part["Minimum sizes"])] == [120, 160, 24, 16]
    assert captions(part["Colour-vision simulations"]) == ["protan", "deutan", "tritan", "achroma"]
    assert len(CONTRAST_ROW.findall(part["Contrast"])) == 4 and info["warnings"] == []
    # Captions flow under the art, never over it, and ladder panels grow to fit theirs (the stacked lockup is 232 px tall).
    assert "position:absolute" not in html and len(re.findall(r'style="min-width:\d+px;min-height:\d+px"', part["Minimum sizes"])) == 4


DRAWN_NAME = """from logomaker.kit import *

META = Meta(slug="drawn-name", idea="a name drawn in bars, beside a square or alone", logo_type="combination", motifs=["bars"])
PARAMS = Params(symbol=True)
TIERS = {"full": {}}


def build(p):
    name = union(rect(0, 0, 40, 200), rect(0, 0, 120, 40))  # drawn without text(): a Shape, so it has no cap height
    return Mark(symbol=rect_centered(0, 0, 300, 300) if p.symbol else None, wordmark=name)
"""


def test_the_clear_space_rule_names_what_x_measures(project_root):
    final = make_final_brand(project_root)

    def heading() -> str:
        write_passing_audit(project(), "keystone", final)  # final/ changed: the sheet shows only an audited mark
        return re.search(r"<h2>(Clear space [^<]*)</h2>", refine()[1]).group(1)

    assert heading() == "Clear space (x = 180 units = the wordmark cap height)"
    shutil.copy(FIXTURES / "concepts" / "tall_frame" / "concept.py", final / "concept.py")  # a symbol alone, 320 units tall
    assert heading() == "Clear space (x = 64.0 units = one fifth of the symbol height)"
    (final / "concept.py").write_text(DRAWN_NAME)  # a name with no cap height: x follows the symbol, else the name's height
    assert heading() == "Clear space (x = 60.0 units = one fifth of the symbol height)"
    (final / "params.json").write_text('{"symbol": false}')
    assert heading() == "Clear space (x = 200.0 units = the wordmark height)"


def test_tokens_are_read_once_and_type_meets_the_text_thresholds_the_audit_applies(project_root, monkeypatch):
    final = make_final_brand(project_root)
    source = (final / "concept.py").read_text()
    (final / "concept.py").write_text(source.replace("gap=p.gap)", 'gap=p.gap, roles={"wordmark": "primary"})'))  # the name in ember
    write_passing_audit(project(), "keystone", final)
    loads = []
    load_tokens = sheets.load_tokens
    monkeypatch.setattr(sheets, "load_tokens", lambda path: loads.append(path) or load_tokens(path))
    _, html = refine()
    assert loads == [final / "tokens.json"]
    rows = {(context, role): rest for context, role, *rest in CONTRAST_ROW.findall(html)}
    # Ember sets the name, so it needs WCAG 4.5 and Lc 60 as the audit's contrast check asks; ink now colours no type.
    assert rows == {("light", "primary"): ["4.5", "60.0", "bad"], ("light", "ink"): ["3.0", "45.0", "ok"],
                    ("dark", "primary"): ["4.5", "60.0", "ok"], ("dark", "ink"): ["3.0", "45.0", "ok"]}


def test_the_cli_emits_the_tier_warnings_and_opens_the_sheet(project_root, monkeypatch):
    make_final_brand(project_root, wordmark_only=True)
    monkeypatch.setattr(sheets, "Renderer", StubChrome)
    monkeypatch.delenv("LOGOMAKER_NO_OPEN")
    opened = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kwargs: opened.append(argv))
    sheets_dir = project_root / "brands" / "keystone" / "sheets"
    tiers = [not_drawn("small"), not_drawn("favicon")]

    def sheet(*args: str) -> tuple[int, dict]:
        result = CliRunner().invoke(main, ["sheet", "refine", "keystone", *args])
        return result.exit_code, json.loads(result.stdout)

    code, payload = sheet("--no-open")
    assert code == 0 and payload["warnings"] == tiers and opened == []
    assert (payload["sheet_html"], payload["sheet_png"], payload["round"]) == (str(sheets_dir / "refine-1.html"),
                                                                              str(sheets_dir / "refine-1.png"), 1)
    html = (sheets_dir / "refine-1.html").read_text()
    assert [f'<div class="note">{w}</div>' in html for w in tiers] == [True, True]
    assert captions(sections(html)["Lockups"]) == ["wordmark"]
    # No horizontal or stacked lockup: the full lockup stands at those minimums, as exports draw it there.
    ladder = sections(html)["Minimum sizes"]
    assert captions(ladder) == ["horizontal 120 px / 25 mm", "stacked 160 px / 25 mm", "mark 24 px / 6 mm", "favicon 16 px"]
    assert [int(w) for w, _ in SVG_SIZES.findall(ladder)] == [120, 160, 24, 16]
    code, payload = sheet()
    assert code == 0 and payload["round"] == 2 and payload["warnings"] == tiers
    assert opened == [["open", str(sheets_dir / "refine-2.html")]]
    monkeypatch.setattr(subprocess, "Popen", no_open_command)
    code, payload = sheet()
    assert code == 0 and payload["warnings"] == [
        *tiers, f"could not open {sheets_dir / 'refine-3.html'}: [Errno 2] No such file or directory: 'open'"]


@requires_chrome
@pytest.mark.render
def test_refine_sheet_renders_sections(project_root, renderer):
    make_final_brand(project_root)
    info = sheets.refine_sheet(project(), "keystone", renderer=renderer, open_after=False)
    html = Path(info["sheet_html"]).read_text()
    for needle in ("clear space", "protan", "deutan", "tritan", "achroma", "WCAG", "favicon 16 px", "stacked 160 px", "currentColor"):
        assert needle in html, needle
    png = project_root / "brands" / "keystone" / "sheets" / "refine-1.png"
    assert info["round"] == 1 and info["sheet_png"] == str(png) and png.stat().st_size > 20_000
    with Image.open(png) as image:
        assert image.width == sheets.REFINE_W  # the whole page, at the sheet's width
    assert info["warnings"] == []


@requires_chrome
@pytest.mark.render
def test_refine_sheet_cli_numbers_its_rounds(project_root):
    # No renderer fixture: each run starts its own Chrome, and Playwright's sync API cannot start a second beside it.
    make_final_brand(project_root)
    sheets_dir = project_root / "brands" / "keystone" / "sheets"

    def sheet(*args: str) -> dict:
        result = CliRunner().invoke(main, ["sheet", "refine", "keystone", "--no-open", *args])
        payload = json.loads(result.stdout)
        assert result.exit_code == 0, payload
        return payload

    assert [sheet()["round"], sheet()["round"]] == [1, 2]
    for suffix in ("html", "png"):
        (sheets_dir / f"refine-1.{suffix}").write_text("old")
    payload = sheet("--round", "1")
    assert payload["round"] == 1 and payload["sheet_png"] == str(sheets_dir / "refine-1.png") and payload["warnings"] == []
    assert "refinement round 1" in (sheets_dir / "refine-1.html").read_text() and (sheets_dir / "refine-1.png").stat().st_size > 20_000
    assert sorted(p.name for p in sheets_dir.glob("refine-*")) == ["refine-1.html", "refine-1.png", "refine-2.html", "refine-2.png"]


@requires_chrome
@pytest.mark.render
def test_refine_sheet_without_tokens_skips_colour(project_root, renderer):
    make_final_brand(project_root, with_tokens=False)
    info = sheets.refine_sheet(project(), "keystone", renderer=renderer, open_after=False)
    html = Path(info["sheet_html"]).read_text()
    assert "no tokens.json yet" in html and "protan" not in html
