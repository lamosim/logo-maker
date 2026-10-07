import json
import re
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image
from pydantic import ValidationError

from logomaker import mockups, registry, sheets
from logomaker.cli import main
from logomaker.kit import concept as conceptlib
from logomaker.kit.mark import Mark
from logomaker.kit.text import text
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.render import fit_box
from logomaker.schemas import CRITERIA, Scorecard
from tests.conftest import REPO, StubChrome, install_concept, no_open_command, requires_chrome, scorecard, write_passing_audit
from tests.test_skill_docs import canonical

GATE = "scorecard.json fails the gate (appropriate, simple and legible must be 4 or more, and not killed)"
AUDIT = "logomaker concept audit keystone 01-good"
STALE = (f"is stale (concept.py, params.json, tokens.json, the brand's industry or minimum sizes, or cliches.json changed); "
         f"re-run: {AUDIT}")
EMPTY = "at least one concept is needed (--concepts 01-arch,03-keystone)"
SVG_SIZES = re.compile(r'<svg width="(\d+)" height="(\d+)"')
STRIP = re.compile(r'<div class="strip">(.*?)</div>', re.S)


def prepare(project_root: Path, name: str, fixture: str = "good", gate_scores: dict | None = None, tokens: dict | None = None) -> Path:
    """Concept `name`, a copy of `fixture`, with a passing rendered audit and a scorecard of 4s but `gate_scores`.
    `tokens` becomes its tokens.json before the audit, whose fingerprint covers it."""
    folder = install_concept(project_root, fixture, name=name)
    if tokens is not None:
        (folder / "tokens.json").write_text(json.dumps(tokens))
    write_passing_audit(project(), "keystone", folder)
    (folder / "scorecard.json").write_text(json.dumps(scorecard(**(gate_scores or {}))))
    return folder


def refusal(*names: str) -> str:
    """The message of the exit-2 CliError that sheets.concepts_sheet raises for `names` (brand keystone)."""
    with pytest.raises(CliError) as err:
        sheets.concepts_sheet(project(), "keystone", list(names), open_after=False)
    assert err.value.code == 2
    return str(err.value)


def sheet(*args: str) -> tuple[int, dict]:
    """`sheet concepts keystone` with `args`: the exit code and the JSON payload."""
    result = CliRunner().invoke(main, ["sheet", "concepts", "keystone", *args])
    return result.exit_code, json.loads(result.stdout)


def no_sheet(project_root: Path) -> bool:
    return not list((project_root / "brands" / "keystone").glob("sheets/concepts.*"))


def test_scorecard_validation_and_gate():
    card = Scorecard.model_validate(scorecard())
    assert card.gate_ok and card.total == 40
    assert not Scorecard.model_validate(scorecard(legible=3)).gate_ok
    assert not Scorecard.model_validate({**scorecard(), "kill": True, "reason": "too generic"}).gate_ok
    low = Scorecard.model_validate(scorecard(distinctive=1, timeless=2))  # only appropriate, simple and legible gate
    assert low.gate_ok and low.total == 35
    with pytest.raises(ValidationError, match="scores must be 1..5"):
        Scorecard.model_validate({"scores": {c: 6 for c in CRITERIA}})
    with pytest.raises(ValidationError, match="scores missing: distinctive, simple, legible"):
        Scorecard.model_validate({"scores": {"appropriate": 4}})


def test_neighbour_icons_are_generated_and_distinct():
    icons = mockups.neighbour_icons(60)
    assert len(icons) == 11 and len(set(icons)) == 11
    assert all(i.startswith('<svg width="60" height="60"') for i in icons)
    # Each is a kit-drawn tile in one of the neighbour colours with a white glyph on it.
    assert all(f'fill="{c}"' in i and 'fill="#ffffff"' in i for c, i in zip(mockups.NEIGHBOUR_COLOURS, icons, strict=True))


def test_render_mockup_knows_the_seven_kinds(project_root):
    assert mockups.MOCKUPS == ("phone-home", "browser-tab", "site-header-light", "site-header-dark", "avatar", "card", "sign-one-colour")
    with pytest.raises(ValueError, match="unknown mockup 'sign'"):
        mockups.render_mockup(sheets.jinja(project()), "sign", {})


def test_the_sheet_prints_the_collins_preface_as_process_md_words_it():
    template = (REPO / "templates" / "sheets" / "concepts.html").read_text(encoding="utf-8")
    assert canonical("process.md") in template  # the passage SKILL.md quotes, word for word


def test_mockup_context_wordmark_only_warns(project_root):
    registry.new_brand(project(), "Keystone")
    state = registry.load_state(project(), "keystone")
    mark = Mark(wordmark=text("Keystone", "Fira Code", weight=700, cap_height=180), lockup="wordmark")
    outputs = conceptlib.build_outputs({"full": mark})
    ctx = sheets.mockup_context(state, outputs, None, None)
    assert ctx["brand"] == "Keystone" and ctx["warnings"] and "wordmark" in ctx["warnings"][0]
    assert ctx["icon_svg"].startswith("<svg") and len(ctx["neighbours"]) == 11


@pytest.mark.parametrize(("tiers", "warnings"), [
    ((), ["no symbol in this concept: icon, favicon and avatar mockups use the wordmark"]),
    (("favicon",), ["no symbol in this concept: icon and avatar mockups use the wordmark"]),
    (("compact", "favicon"), ["no symbol in this concept: icon mockup uses the wordmark"]),
    (("small",), []),  # the small tier draws the icon and the avatar, and stands in for the favicon
])
def test_the_wordmark_warning_names_only_the_mockups_the_wordmark_draws(project_root, tiers, warnings):
    registry.new_brand(project(), "Keystone")
    word = Mark(wordmark=text("Keystone", "Fira Code", weight=700, cap_height=180), lockup="wordmark")
    initial = Mark(wordmark=text("K", "Fira Code", weight=800, cap_height=180), lockup="wordmark")
    outputs = conceptlib.build_outputs({"full": word, **{tier: initial for tier in tiers}})
    assert sheets.mockup_context(registry.load_state(project(), "keystone"), outputs, None, None)["warnings"] == warnings


def test_the_avatar_mockup_draws_the_compact_tier_when_the_concept_builds_one(project_root):
    folder = install_concept(project_root, "good")  # compact is the full lockup, small the ring alone
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(folder)))
    state = registry.load_state(project(), "keystone")
    assert sheets.mockup_context(state, outputs, None, None)["avatar_svg"] == fit_box(outputs["compact"].to_svg("black"), 48, 48)
    del outputs["compact"]  # without it, the tier for the avatar's 80 px
    assert sheets.mockup_context(state, outputs, None, None)["avatar_svg"] == fit_box(outputs["small"].to_svg("black"), 48, 48)


def test_mockup_context_draws_the_icon_in_paper_on_a_primary_tile(project_root):
    from tests.conftest import good_tokens

    folder = install_concept(project_root, "good")
    (folder / "tokens.json").write_text(json.dumps(good_tokens()))
    light, dark = sheets._palettes(folder)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(folder)))
    ctx = sheets.mockup_context(registry.load_state(project(), "keystone"), outputs, light, dark)
    assert ctx["warnings"] == [] and ctx["handle"] == "keystone"
    assert (ctx["tile_fill"], ctx["paper_light"], ctx["paper_dark"], ctx["primary_dark"]) == ("#e8572a", "#ffffff", "#1f1b18", "#ff9a6e")
    fills = {key: set(re.findall(r'fill="([^"]+)"', ctx[key])) for key in ("icon_svg", "header_svg", "header_dark_svg", "sign_svg")}
    assert fills == {"icon_svg": {"#ffffff"}, "header_svg": {"#e8572a", "#1f1b18"}, "header_dark_svg": {"#ff9a6e", "#ffffff"},
                     "sign_svg": {"#ffffff"}}


def test_the_handle_follows_the_brand_name_or_falls_back_to_the_slug(project_root):
    registry.new_brand(project(), "Tokyo Works")
    mark = Mark(wordmark=text("Tokyo", "Fira Code", weight=700, cap_height=180), lockup="wordmark")
    outputs = conceptlib.build_outputs({"full": mark})
    state = registry.rename(project(), "tokyo-works", "Kyoto Labs")  # a renamed working title gets its new name
    assert sheets.mockup_context(state, outputs, None, None)["handle"] == "kyotolabs"
    state = registry.rename(project(), "tokyo-works", "東京")  # no letters slugify can keep: the slug, without hyphens
    ctx = sheets.mockup_context(state, outputs, None, None)
    assert ctx["brand"] == "東京" and ctx["handle"] == "tokyoworks"
    folder = install_concept(project_root, "good", slug="tokyo-works", name="01-good")  # and the whole sheet builds
    write_passing_audit(project(), "tokyo-works", folder)
    (folder / "scorecard.json").write_text(json.dumps(scorecard()))
    info = sheets.concepts_sheet(project(), "tokyo-works", ["01-good"], renderer=StubChrome(), open_after=False)
    html = Path(info["sheet_html"]).read_text()
    assert "東京 &mdash; concept directions" in html and "@tokyoworks" in html


def test_the_other_browser_tabs_show_kit_drawn_icons(project_root):
    folder = install_concept(project_root, "good")
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(folder)))
    ctx = sheets.mockup_context(registry.load_state(project(), "keystone"), outputs, None, None)
    assert ctx["tabs"] == ["Inbox", "Calendar"] and ctx["tab_icons"] == mockups.neighbour_icons(16)[:2]
    tab = mockups.render_mockup(sheets.jinja(project()), "browser-tab", ctx)
    assert [icon in tab for icon in ctx["tab_icons"]] == [True, True] and "background:#8a8f98" not in tab


def test_each_mockup_fits_its_grid_column(project_root):
    # The concept sheet places every mockup in a fixed column; a mockup is as wide as its style says only when its padding
    # and side borders sit inside that width (border-box), else it spills into the gap and touches its neighbour.
    sheet = (project_root / "templates" / "sheets" / "concepts.html").read_text()
    columns = [int(w) for w in re.search(r"grid-template-columns:((?:\d+px ?)+)", sheet).group(1).replace("px", "").split()]
    for kind in mockups.MOCKUPS:
        column = int(re.search(rf'\[data-mockup="{kind}"\]\{{grid-column:(\d)', sheet).group(1))
        root = (project_root / "templates" / "mockups" / f"{kind}.html").read_text()
        style = re.search(r'^<div class="mockup"[^>]* style="([^"]*)"', root).group(1)
        assert int(re.search(r"(?:^|;)width:(\d+)px", style).group(1)) <= columns[column - 1], kind
        assert "box-sizing:border-box" in style or not re.search(r"padding|border:", style), kind


def test_sheet_refuses_unvetted_concepts(project_root, no_chrome, monkeypatch):
    prepare(project_root, "01-good")
    weak = prepare(project_root, "02-weak", gate_scores={"simple": 2})
    noaudit = install_concept(project_root, "good", name="03-noaudit")
    (noaudit / "scorecard.json").write_text(json.dumps(scorecard()))
    # Every named concept is vetted before any is built: 01-good passes, and the refusal comes before its build.
    monkeypatch.setattr(conceptlib, "build_tiers", lambda *args, **kwargs: pytest.fail("a concept was built before all were vetted"))
    assert refusal("01-good", "02-weak") == f"concept 02-weak: {GATE}"
    assert refusal("01-good", "03-noaudit") == ("concept 03-noaudit: audit.json is missing "
                                                "(run: logomaker concept audit keystone 03-noaudit)")
    (weak / "scorecard.json").write_text(json.dumps({**scorecard(), "kill": True, "reason": "too generic"}))
    assert refusal("02-weak") == f"concept 02-weak: {GATE}"
    (weak / "scorecard.json").write_text(json.dumps({"scores": {"appropriate": 4}}))
    assert refusal("02-weak").startswith("concept 02-weak: scorecard.json is invalid: root: Value error, scores missing: distinctive")
    (weak / "scorecard.json").unlink()
    assert refusal("02-weak") == "concept 02-weak: scorecard.json is missing; score it before presenting"
    assert no_sheet(project_root)


def test_sheet_refuses_an_audit_that_is_unrendered_stale_or_failing(project_root, no_chrome):
    folder = prepare(project_root, "01-good")
    audit = folder / "audit.json"
    passing = json.loads(audit.read_text())
    failure = {"check": "min_feature", "severity": "fail", "message": "favicon: thinnest feature is 0.80 px at 16 px (need 1.0)"}
    unrendered, failing = f"was made with --no-render; re-run without it: {AUDIT}", f"has failures; fix them, then re-run: {AUDIT}"
    for saved, problem in (({**passing, "rendered": False}, unrendered), ({**passing, "fingerprint": "0" * 64}, STALE),
                           ({**passing, "ok": False, "failures": [failure]}, failing)):
        audit.write_text(json.dumps(saved))
        assert refusal("01-good") == f"concept 01-good: audit.json {problem}"
    audit.write_text(json.dumps({**passing, "rendered": False, "ok": False}))  # every problem, the concept named once
    assert refusal("01-good") == f"concept 01-good: audit.json {unrendered}; audit.json {failing}"
    audit.write_text(json.dumps(passing))
    (folder / "params.json").write_text('{"stroke": 80}')  # the concept changed after its audit
    assert refusal("01-good") == f"concept 01-good: audit.json {STALE}"
    audit.write_text("{not json")
    message = refusal("01-good")
    assert message.startswith("concept 01-good: audit.json is not valid JSON: ") and message.endswith(f" (run: {AUDIT})")
    assert no_sheet(project_root)


def test_an_empty_concept_list_exits_2(project_root, no_chrome):
    registry.new_brand(project(), "Keystone")
    for value in ("", " , "):
        code, payload = sheet("--concepts", value, "--no-open")
        assert code == 2 and payload["errors"] == [EMPTY], value


def test_the_cli_refuses_an_unvetted_concept_before_chrome_starts(project_root, no_chrome):
    prepare(project_root, "01-good")
    prepare(project_root, "02-weak", gate_scores={"simple": 2})
    code, payload = sheet("--concepts", "01-good,02-weak", "--no-open")
    assert code == 2 and payload["errors"] == [f"concept 02-weak: {GATE}"]
    assert no_sheet(project_root)


def test_vetted_concepts_reach_chrome_and_a_failed_render_writes_no_sheet(project_root, no_chrome):
    prepare(project_root, "01-good")
    sheets_dir = project_root / "brands" / "keystone" / "sheets"
    sheets_dir.rmdir()
    code, payload = sheet("--concepts", "01-good", "--no-open")
    # The stand-in is entered once every concept is vetted and built: the refusals above stopped before Chrome.
    assert code != 0 and "Chrome started" in payload["errors"][0]
    assert not sheets_dir.exists()  # rendered first; the folder and both files come after


def test_each_concept_carries_the_critique_strip_at_true_size(project_root):
    prepare(project_root, "01-good")
    info = sheets.concepts_sheet(project(), "keystone", ["01-good"], renderer=StubChrome(), open_after=False)
    html = Path(info["sheet_html"]).read_text()
    strip = STRIP.search(html).group(1)
    # Black and reversed lockups in 256 px boxes, the ladder at true size, then mirrored and rotated in 128 px boxes.
    assert [max(int(w), int(h)) for w, h in SVG_SIZES.findall(strip)] == [256, 256, *sheets.LADDER, 128, 128]
    captions = re.findall(r"<figcaption>(.*?)</figcaption>", strip)
    assert captions == ["black", "reversed", *map(str, sheets.LADDER), "mirrored", "rotated 90"]
    assert ".mirror svg{transform:scaleX(-1)}" in html and ".rotate svg{transform:rotate(90deg)}" in html
    # Every mockup has its own place in the grid, so none wraps around the tall phone.
    assert all(re.search(rf'\[data-mockup="{kind}"\]\{{grid-column:\d;grid-row:', html) for kind in mockups.MOCKUPS)


def test_the_cli_writes_the_sheet_opens_it_and_warns_about_wordmark_fallbacks(project_root, monkeypatch):
    prepare(project_root, "01-good")
    prepare(project_root, "02-word", fixture="wordmark_only", gate_scores={"distinctive": 3})
    monkeypatch.setattr(sheets, "Renderer", StubChrome)
    monkeypatch.delenv("LOGOMAKER_NO_OPEN")
    opened = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kwargs: opened.append(argv))
    fallback = "02-word: no symbol in this concept: icon, favicon and avatar mockups use the wordmark"
    folder = project_root / "brands" / "keystone" / "sheets"
    code, payload = sheet("--concepts", " 01-good , 02-word ", "--no-open")
    assert code == 0 and payload["concepts"] == ["01-good", "02-word"] and payload["warnings"] == [fallback] and opened == []
    assert payload["sheet_html"] == str(folder / "concepts.html") and payload["sheet_png"] == str(folder / "concepts.png")
    assert (folder / "concepts.png").read_bytes() == b"png"
    html = (folder / "concepts.html").read_text()
    assert [html.count(f'class="mockup" data-mockup="{kind}"') for kind in mockups.MOCKUPS] == [2] * len(mockups.MOCKUPS)
    assert "40 / 50" in html and "39 / 50" in html and "no symbol in this concept" in html
    code, payload = sheet("--concepts", "01-good,02-word")
    assert code == 0 and payload["warnings"] == [fallback] and opened == [["open", str(folder / "concepts.html")]]
    monkeypatch.setattr(subprocess, "Popen", no_open_command)
    code, payload = sheet("--concepts", "01-good,02-word")
    assert code == 0 and payload["warnings"] == [
        fallback, f"could not open {folder / 'concepts.html'}: [Errno 2] No such file or directory: 'open'"]


@requires_chrome
@pytest.mark.render
def test_concepts_sheet_renders_all_mockups(project_root, renderer):
    from tests.conftest import good_tokens

    prepare(project_root, "01-good")
    prepare(project_root, "02-good-colour", tokens=good_tokens())
    prepare(project_root, "03-word", fixture="wordmark_only")
    names = ["01-good", "02-good-colour", "03-word"]
    info = sheets.concepts_sheet(project(), "keystone", names, renderer=renderer, open_after=False)
    html = Path(info["sheet_html"]).read_text()
    for kind in mockups.MOCKUPS:
        assert html.count(f'class="mockup" data-mockup="{kind}"') == 3, kind
    assert "01-good" in html and "02-good-colour" in html and "03-word" in html and "40 / 50" in html
    fallback = "no symbol in this concept: icon, favicon and avatar mockups use the wordmark"
    sections = html.split('<section class="concept">')[1:]
    assert [f'<div class="warn">{fallback}</div>' in section for section in sections] == [False, False, True]
    assert "background:#e8572a" in html  # the colour concept's app-icon tile is its primary
    png = project_root / "brands" / "keystone" / "sheets" / "concepts.png"
    assert info["sheet_png"] == str(png) and png.stat().st_size > 20_000
    with Image.open(png) as image:
        assert image.width == sheets.CONCEPTS_W  # the whole page, at the sheet's width
    assert info["concepts"] == names and info["warnings"] == [f"03-word: {fallback}"]


@requires_chrome
@pytest.mark.render
def test_concepts_sheet_cli(project_root):
    # No renderer fixture: the command starts its own Chrome, and Playwright's sync API cannot start a second beside it.
    from tests.conftest import good_tokens

    prepare(project_root, "01-good")
    prepare(project_root, "02-good-colour", tokens=good_tokens())
    result = CliRunner().invoke(main, ["sheet", "concepts", "keystone", "--concepts", "01-good,02-good-colour", "--no-open"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0 and payload["concepts"] == ["01-good", "02-good-colour"], payload
    assert (project_root / "brands" / "keystone" / "sheets" / "concepts.png").stat().st_size > 20_000
