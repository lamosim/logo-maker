import json

import pytest
from click.testing import CliRunner

from logomaker import audit, registry
from logomaker.cli import main
from logomaker.output import CliError
from logomaker.paths import project
from tests.conftest import install_concept, requires_chrome


def findings(result, check):
    return [f for f in result.failures + result.warnings + result.info if f.check == check]


def test_good_concept_passes_without_renderer(project_root):
    install_concept(project_root, "good")
    result = audit.audit_concept(project(), "keystone", "01-good")
    assert result.ok and result.rendered is False
    assert (project_root / "brands" / "keystone" / "concepts" / "01-good" / "audit.json").is_file()
    assert "full-symbol" in result.outputs


def test_near_miss_angles_and_free_segments(project_root):
    install_concept(project_root, "near_miss", name="02-near")
    result = audit.audit_concept(project(), "keystone", "02-near")
    near = findings(result, "near_miss_angles")
    assert near and near[0].severity == "warn" and near[0].data["count"] >= 1
    assert findings(result, "free_segments")[0].data["count"] == 4


def test_tiny_part_warns_and_fails_in_small_tier(project_root):
    install_concept(project_root, "tiny_part", name="03-tiny")
    result = audit.audit_concept(project(), "keystone", "03-tiny")
    tiny = findings(result, "tiny_parts")
    assert any(f.severity == "warn" for f in tiny) and any(f.severity == "fail" for f in tiny)
    assert not result.ok


def test_cliche_terms_match_industry(project_root):
    install_concept(project_root, "cliche", name="04-cliche")
    registry.set_fields(project(), "keystone", industry="AI tooling")
    result = audit.audit_concept(project(), "keystone", "04-cliche")
    matched = {f.data["term"] for f in findings(result, "cliche")}
    assert {"hexagon", "sparkle"} <= matched and "wave" not in matched
    assert {f.data["source"] for f in findings(result, "cliche")} == {"ai"}
    industry = findings(result, "industry")
    assert industry[0].severity == "info" and industry[0].data["resolved"] == ["ai"] and industry[0].message.endswith("resolves to ai")
    cliches = audit.load_cliches(project())
    assert audit.resolve_industry(cliches, "Invoicing for consultants") == "fintech"
    assert audit.resolve_industry(cliches, None) is None


def test_industry_without_a_match_says_so(project_root):
    install_concept(project_root, "good")
    industry = findings(audit.audit_concept(project(), "keystone", "01-good"), "industry")
    assert industry[0].severity == "info" and industry[0].data["resolved"] == [] and "none matched" in industry[0].message
    assert industry[0].data["source"] is None and industry[0].message.startswith("industry not set")


def test_industry_falls_back_to_the_brief(project_root, brief_payload):
    install_concept(project_root, "cliche", name="04-cliche")
    (project_root / "brands" / "keystone" / "brief.json").write_text(json.dumps({**brief_payload, "industry": "AI tooling"}))
    result = audit.audit_concept(project(), "keystone", "04-cliche")
    industry = findings(result, "industry")[0]
    assert (industry.data["industry"], industry.data["source"], industry.data["resolved"]) == ("AI tooling", "brief.json", ["ai"])
    assert industry.message == "industry 'AI tooling' (from brief.json) resolves to ai"
    assert {f.data["source"] for f in findings(result, "cliche")} == {"ai"}  # the brief's industry picks the cliché list too
    registry.set_fields(project(), "keystone", industry="Real estate")
    industry = findings(audit.audit_concept(project(), "keystone", "04-cliche"), "industry")[0]
    assert (industry.data["source"], industry.data["resolved"]) == ("brand.json", ["real-estate"])
    assert "(from brand.json)" in industry.message


def test_industry_resolution_ranks_whole_word_aliases(project_root):
    cliches = audit.load_cliches(project())
    assert audit.resolve_industry(cliches, "Real estate agent") == "real-estate"  # not ai, though 'agent' is an ai alias
    assert audit.resolve_industry(cliches, "AI for real estate") == "real-estate"  # the longer alias beats the earlier one
    dental = audit.resolve_industries(cliches, "Dental clinic")  # equal lengths: the earlier match ranks first
    assert dental[0] == "dental" and "healthcare" in dental
    assert audit.resolve_industry(cliches, "Orthodontics") == "dental"
    assert audit.resolve_industry(cliches, "Dentists") == "dental"  # plurals of aliases match too
    assert audit.resolve_industry(cliches, "Invoicing for consultants") == "fintech"
    assert audit.resolve_industry(cliches, "AI tooling") == "ai"
    assert audit.resolve_industries(cliches, "Widgets") == [] and audit.resolve_industries(cliches, None) == []


def test_short_terms_and_aliases_take_no_plural(project_root):
    cliches = audit.load_cliches(project())
    assert audit.resolve_industries(cliches, "MLS real estate listings") == ["real-estate"]  # 'ml' no longer finds 'mls'
    assert audit.resolve_industries(cliches, "AIs for everyone") == [] and audit.resolve_industry(cliches, "AI tooling") == "ai"
    assert audit.resolve_industry(cliches, "Dentists") == "dental"  # three letters or more still take -s and -es


def test_cliche_matching_is_word_level(project_root):
    cliches = audit.load_cliches(project())

    def terms(motif, industry=None):
        return [f.data["term"] for f in audit.check_cliches([motif], cliches, industry)]

    # Controls: these terms are live in the lists the negative cases search.
    assert terms("key", "real estate") == ["key"] and terms("lips", "beauty") == ["lips"]
    assert terms("letter in a circle") == ["letter in a circle"]
    assert terms("keystone", "real estate") == [] and terms("eclipse", "beauty") == []
    assert terms("k") == [] and terms("circle") == []
    assert terms("sparkle burst", "AI tooling") == ["sparkle"] and terms("hexagon", "AI tooling") == ["hexagon"]
    assert terms("hexagons", "AI tooling") == ["hexagon"] and terms("swooshes") == ["swoosh"]  # plural motifs still match
    union = audit.check_cliches(["tooth", "heartbeat"], cliches, "Dental clinic")
    assert [(f.data["term"], f.data["source"]) for f in union] == [("tooth", "dental"), ("heartbeat", "healthcare")]


def test_text_legibility_fails_when_lockup_is_too_small(project_root):
    install_concept(project_root, "good")
    state = registry.load_state(project(), "keystone")
    state.min_sizes.horizontal_px = 60
    registry.save_state(project(), state)
    result = audit.audit_concept(project(), "keystone", "01-good")
    assert findings(result, "text_legibility")[0].severity == "fail" and not result.ok


def write_concept(folder, build_body: str, tiers: str = "{'full': {}}") -> None:
    """Replace `folder`'s concept.py with a one-tier module whose build(p) is `build_body` (one or more lines)."""
    (folder / "concept.py").write_text(
        "from logomaker.kit import *\n"
        "META = Meta(slug='inline', idea='written by the test', logo_type='combination')\n"
        f"PARAMS = Params()\nTIERS = {tiers}\n"
        "def build(p):\n" + "".join(f"    {line}\n" for line in build_body.splitlines())
    )


def test_a_notched_wordmark_is_still_checked_for_legibility(project_root):
    folder = install_concept(project_root, "good", name="14-notch")
    # 27 characters at cap height 60 beside a 400-unit symbol: about 3 px of x-height at the 120 px minimum width.
    write_concept(folder, "name = text('Keystone Invoicing Partners', 'Fira Code', weight=600, cap_height=60)\n"
                          "word = subtract(name, rect(0, 20, 30, 10))\n"
                          "return Mark(symbol=rect_centered(0, 0, 400, 400), wordmark=word)")
    result = audit.audit_concept(project(), "keystone", "14-notch")
    legibility = findings(result, "text_legibility")
    assert [f.data["output"] for f in legibility] == ["full-horizontal", "full-stacked", "full-wordmark"]
    assert all(f.severity == "fail" for f in legibility) and not result.ok


def test_a_wordmark_without_text_metrics_warns_instead_of_skipping(project_root):
    folder = install_concept(project_root, "good", name="15-blocks")
    write_concept(folder, "return Mark(symbol=rect_centered(0, 0, 400, 400), wordmark=rect(0, 0, 900, 120))")
    legibility = findings(audit.audit_concept(project(), "keystone", "15-blocks"), "text_legibility")
    assert [f.data["output"] for f in legibility] == ["full-horizontal", "full-stacked", "full-wordmark"]
    assert all(f.severity == "warn" for f in legibility)
    assert legibility[0].message == ("full-horizontal: wordmark metrics unknown (not a TextShape); x-height cannot be checked — "
                                     "build the wordmark with text() and keep it the first operand of every op")


def test_nondeterministic_concept_fails(project_root):
    install_concept(project_root, "random_concept", name="05-random")
    result = audit.audit_concept(project(), "keystone", "05-random")
    assert findings(result, "determinism")[0].severity == "fail"


def test_determinism_reports_outputs_that_change_between_builds(project_root):
    folder = install_concept(project_root, "good", name="09-shifty")
    (folder / "concept.py").write_text(
        "from pathlib import Path\n"
        "from logomaker.kit import *\n"
        "META = Meta(slug='shifty', idea='drops its favicon tier on the second load', logo_type='abstract')\n"
        "PARAMS = Params()\n"
        "_seen = Path(__file__).with_name('loaded-before')\n"
        "TIERS = {'full': {}} if _seen.exists() else {'full': {}, 'favicon': {}}\n"
        "_seen.touch()\n"
        "def build(p):\n"
        "    return Mark(symbol=circle(0, 0, 200))\n"
    )
    result = audit.audit_concept(project(), "keystone", "09-shifty")
    determinism = findings(result, "determinism")
    assert determinism[0].severity == "fail" and "favicon" in determinism[0].message


def test_anchor_ceiling(project_root):
    folder = install_concept(project_root, "good", name="06-busy")
    (folder / "concept.py").write_text(
        "from logomaker.kit import *\n"
        "META = Meta(slug='busy', idea='too many dots', logo_type='abstract', motifs=[])\n"
        "PARAMS = Params()\nTIERS = {'full': {}}\n"
        "def build(p):\n"
        "    return Mark(symbol=union(*[circle(x * 40, y * 40, 12) for x in range(8) for y in range(8)]))\n"
    )
    result = audit.audit_concept(project(), "keystone", "06-busy")
    assert findings(result, "anchors")[0].severity == "fail"


def test_anchor_count_within_limits_is_reported_as_info(project_root):
    install_concept(project_root, "good")
    anchors = findings(audit.audit_concept(project(), "keystone", "01-good"), "anchors")
    assert [(f.data["output"], f.severity) for f in anchors] == [("full-symbol", "info"), ("small", "info"), ("favicon", "info")]
    for f in anchors:
        assert 0 < f.data["anchors"] <= audit.ANCHOR_WARN and f.message == f"{f.data['output']}: symbol has {f.data['anchors']} anchors"


def test_a_union_of_dots_counts_the_anchors_of_their_composite(project_root):
    folder = install_concept(project_root, "good", name="17-dots")
    counts = []
    composite = "Composite([(circle(i * 100, 0, 30), 'primary') for i in range(10)])"
    unioned = "union(*[circle(i * 100, 0, 30) for i in range(10)])"
    for symbol in (composite, unioned):
        write_concept(folder, f"return Mark(symbol={symbol})")
        counts.append(findings(audit.audit_concept(project(), "keystone", "17-dots"), "anchors")[0].data["anchors"])
    assert counts == [40, 40]


def test_allow_complex_needs_a_reason(project_root):
    folder = install_concept(project_root, "good", name="08-complex")
    for reason, severity in (("", "fail"), ("an engraved seal meant to reward a close look", "warn")):
        (folder / "concept.py").write_text(
            "from logomaker.kit import *\n"
            f"META = Meta(slug='complex', idea='a 200-sided seal', logo_type='emblem', allow_complex=True, complex_reason={reason!r})\n"
            "PARAMS = Params()\nTIERS = {'full': {}}\n"
            "def build(p):\n"
            "    return Mark(symbol=regular_polygon(0, 0, 300, 200))\n"
        )
        anchors = findings(audit.audit_concept(project(), "keystone", "08-complex"), "anchors")
        assert anchors and all(f.severity == severity for f in anchors), (reason, [f.severity for f in anchors])
        assert anchors[0].data["anchors"] == 200 and anchors[0].data["reason"] == reason and "over 150" in anchors[0].message


def test_colour_count_warns_over_three_roles(project_root):
    folder = install_concept(project_root, "good", name="10-roles")
    (folder / "concept.py").write_text(
        "from logomaker.kit import *\n"
        "META = Meta(slug='roles', idea='four swatches', logo_type='abstract')\n"
        "PARAMS = Params()\nTIERS = {'full': {}}\n"
        "ROLES = ['primary', 'secondary', 'accent', 'ink']\n"
        "def build(p):\n"
        "    return Mark(symbol=Composite([(circle(i * 300, 0, 100), role) for i, role in enumerate(ROLES)]))\n"
    )
    count = findings(audit.audit_concept(project(), "keystone", "10-roles"), "colour_count")
    assert count[0].severity == "warn" and count[0].message.startswith("4 colour roles")
    assert count[0].data["roles"] == ["accent", "ink", "primary", "secondary"]


def test_tokens_contrast_feeds_the_audit(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")
    bad = good_tokens()
    bad["colors"]["coal"]["hex"] = "#777777"
    (folder / "tokens.json").write_text(json.dumps(bad))
    result = audit.audit_concept(project(), "keystone", "01-good")
    assert findings(result, "contrast")[0].severity == "fail"


def test_wordmark_contrast_follows_the_role_the_wordmark_uses(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")
    (folder / "tokens.json").write_text(json.dumps(good_tokens()))
    assert not findings(audit.audit_concept(project(), "keystone", "01-good"), "contrast")  # ember passes as a symbol colour
    source = (folder / "concept.py").read_text()
    (folder / "concept.py").write_text(source.replace("gap=p.gap)", 'gap=p.gap, roles={"wordmark": "primary"})'))
    contrast = findings(audit.audit_concept(project(), "keystone", "01-good"), "contrast")
    assert contrast and all(f.severity == "fail" for f in contrast)
    assert any(f.message.startswith("light: role primary (#e8572a) on paper #ffffff") and "need 4.5" in f.message for f in contrast)


def test_audit_reads_the_tokens_file_it_is_given(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")
    low_contrast = good_tokens()
    low_contrast["colors"]["coal"]["hex"] = "#777777"
    palette = project_root / "palette.json"
    palette.write_text(json.dumps(low_contrast))
    assert not findings(audit.audit_concept(project(), "keystone", "01-good"), "contrast")  # the folder has no tokens.json
    result = audit.audit_concept(project(), "keystone", "01-good", tokens_path=palette)
    assert findings(result, "contrast")[0].severity == "fail"
    assert result.fingerprint == audit.concept_fingerprint(project(), "keystone", folder, palette)
    run = CliRunner().invoke(main, ["concept", "run", "keystone", "01-good", "--no-render", "--tokens", str(palette)])
    payload = json.loads(run.stdout)
    assert run.exit_code == 2 and {f["check"] for f in payload["audit"]["failures"]} == {"contrast"}


def test_concept_audit_takes_the_tokens_file_it_is_given(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")
    low_contrast = good_tokens()
    low_contrast["colors"]["coal"]["hex"] = "#777777"
    palette = project_root / "palette.json"
    palette.write_text(json.dumps(low_contrast))
    result = CliRunner().invoke(main, ["concept", "audit", "keystone", "01-good", "--no-render", "--tokens", str(palette)])
    payload = json.loads(result.stdout)
    assert result.exit_code == 2 and {f["check"] for f in payload["audit"]["failures"]} == {"contrast"}  # the folder has no tokens.json
    saved = json.loads((folder / "audit.json").read_text())
    assert saved["fingerprint"] == audit.concept_fingerprint(project(), "keystone", folder, palette)


def test_broken_tokens_become_a_failure_not_an_abort(project_root):
    folder = install_concept(project_root, "good")
    (folder / "tokens.json").write_text("{}")
    result = audit.audit_concept(project(), "keystone", "01-good")
    tokens = findings(result, "tokens")
    assert tokens and tokens[0].severity == "fail" and "01-good/tokens.json is invalid" in tokens[0].message
    assert not result.ok
    written = json.loads((folder / "audit.json").read_text())
    assert written["ok"] is False and [f["check"] for f in written["failures"]] == ["tokens"]


def test_missing_tiers_fall_back_and_warn(project_root):
    def fallbacks(result):
        tiers = findings(result, "tiers")
        assert all(f.severity == "warn" for f in tiers)
        return [(f.data["tier"], f.data["fallback"]) for f in tiers]

    install_concept(project_root, "thin_stroke", name="07-thin")
    assert fallbacks(audit.audit_concept(project(), "keystone", "07-thin")) == [("small", "full-symbol")]
    install_concept(project_root, "near_miss", name="02-near")
    assert fallbacks(audit.audit_concept(project(), "keystone", "02-near")) == [("small", "full-symbol"), ("favicon", "full-symbol")]
    install_concept(project_root, "tiny_part", name="03-tiny")
    result = audit.audit_concept(project(), "keystone", "03-tiny")
    assert fallbacks(result) == [("favicon", "small")]
    # The favicon's checks run on the small build under the favicon's name, so the favicon's severity applies.
    tiny = {f.data["output"]: f.severity for f in findings(result, "tiny_parts")}
    assert tiny == {"full-symbol": "warn", "small": "fail", "favicon": "fail"}


def test_a_fallback_tier_repeats_only_the_size_dependent_checks(project_root):
    install_concept(project_root, "tiny_part", name="03-tiny")  # tiers full and small; the favicon falls back to small
    result = audit.audit_concept(project(), "keystone", "03-tiny")
    for check in ("anchors", "bounds"):  # drawing checks: once per real output
        assert [f.data["output"] for f in findings(result, check)] == ["full-symbol", "small"], check
    assert sorted(f.data["output"] for f in findings(result, "tiny_parts")) == ["favicon", "full-symbol", "small"]  # size-dependent
    assert [(f.data["tier"], f.data["fallback"]) for f in findings(result, "tiers")] == [("favicon", "small")]


@requires_chrome
@pytest.mark.render
def test_thin_stroke_fails_min_feature_and_merge(project_root, renderer):
    install_concept(project_root, "thin_stroke", name="07-thin")
    result = audit.audit_concept(project(), "keystone", "07-thin", renderer=renderer)
    assert result.rendered is True
    assert any(f.severity == "fail" for f in findings(result, "min_feature"))


@requires_chrome
@pytest.mark.render
def test_good_concept_passes_raster_checks(project_root, renderer):
    install_concept(project_root, "good")
    result = audit.audit_concept(project(), "keystone", "01-good", renderer=renderer)
    assert result.ok, [f.message for f in result.failures]


def test_box_size_fits_the_longest_side_exactly():
    tall = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 100"></svg>'
    assert audit._box_size(tall, 16) == (2, 16) and audit._box_size(tall, 512) == (51, 512)
    assert audit._box_size('<svg viewBox="0 0 100 10"></svg>', 16) == (16, 2)
    assert audit._box_size('<svg viewBox="0 0 50 50"></svg>', 16) == (16, 16)
    for degenerate in ("0 0 0 0", "0 0 0 10", "0 0 10 0"):  # no area to keep the aspect of: the whole box, never a division by zero
        assert audit._box_size(f'<svg viewBox="{degenerate}"></svg>', 16) == (16, 16)


@requires_chrome
@pytest.mark.render
def test_wordmark_only_concept_warns_on_lockup_fallbacks(project_root, renderer):
    install_concept(project_root, "wordmark_only", name="13-word")
    result = audit.audit_concept(project(), "keystone", "13-word", renderer=renderer)
    assert result.ok, [f.message for f in result.failures]
    tiers = findings(result, "tiers")
    assert [(f.data["tier"], f.data["fallback"]) for f in tiers] == [("small", "full-lockup"), ("favicon", "full-lockup")]
    assert all("no symbol" in f.message and "monogram" in f.message for f in tiers)
    favicon = [f for f in findings(result, "min_feature") if f.data["output"] == "favicon"]
    assert favicon and favicon[0].severity == "warn"


@requires_chrome
@pytest.mark.render
def test_symbol_fallbacks_keep_fail_severity(project_root, renderer):
    install_concept(project_root, "tiny_part", name="03-tiny")
    result = audit.audit_concept(project(), "keystone", "03-tiny", renderer=renderer)
    favicon = [f for f in findings(result, "min_feature") if f.data["output"] == "favicon"]  # checked on the small build
    assert not result.ok and favicon[0].severity == "fail"
    assert [f.data["output"] for f in findings(result, "anchors")] == ["full-symbol", "small"]  # not repeated for the favicon


@requires_chrome
@pytest.mark.render
def test_tall_mark_is_measured_by_its_longest_side(project_root, renderer):
    # Exports fit the longest side into the box: this 160 x 320 frame ships 8 x 16 at favicon size, so its
    # 15-unit stroke is about 0.7 px there (a width-fitted render would report about 1.5 px and pass).
    install_concept(project_root, "tall_frame", name="11-tall")
    result = audit.audit_concept(project(), "keystone", "11-tall", renderer=renderer)
    favicon = [f for f in findings(result, "min_feature") if f.data["output"] == "favicon"]
    assert favicon[0].severity == "fail" and favicon[0].data["feature_px"] < 1.0


@requires_chrome
@pytest.mark.render
def test_dots_that_merge_at_favicon_size_fail(project_root, renderer):
    install_concept(project_root, "two_dots", name="12-dots")
    result = audit.audit_concept(project(), "keystone", "12-dots", renderer=renderer)
    merge = [f for f in findings(result, "one_colour_merge") if f.data["output"] == "favicon"]
    assert merge and merge[0].severity == "fail" and (merge[0].data["before"], merge[0].data["after"]) == (2, 1)
    assert merge[0].message.endswith("(parts merge or vanish)")
    # The missing small tier is still rendered, on its full-symbol fallback.
    assert {f.data["output"] for f in findings(result, "min_feature")} == {"full-symbol", "small", "favicon"}


def test_fingerprint_covers_concept_params_and_tokens(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")

    def fingerprint(tokens_path=None):
        return audit.concept_fingerprint(project(), "keystone", folder, tokens_path)

    first = fingerprint()
    assert len(first) == 64 and fingerprint() == first
    assert audit.audit_concept(project(), "keystone", "01-good").fingerprint == first
    assert json.loads((folder / "audit.json").read_text())["fingerprint"] == first
    seen = {first}
    edits = (("params.json", '{"stroke": 80}'), ("tokens.json", json.dumps(good_tokens())),
             ("concept.py", (folder / "concept.py").read_text() + "# edited\n"))
    for name, content in edits:
        (folder / name).write_text(content)
        seen.add(fingerprint())
    assert len(seen) == 4  # each file changes it
    palette = project_root / "palette.json"
    palette.write_text(json.dumps(good_tokens()))
    assert fingerprint(palette) == fingerprint()  # same tokens bytes, wherever they live
    palette.write_text("{}")
    assert fingerprint(palette) != fingerprint()


def test_fingerprint_follows_the_brand_settings_the_audit_reads(project_root, brief_payload):
    folder = install_concept(project_root, "good")
    paths = project()

    def fingerprint():
        return audit.concept_fingerprint(paths, "keystone", folder)

    first = audit.audit_concept(paths, "keystone", "01-good").fingerprint
    registry.set_fields(paths, "keystone", concept="01-good", territory="forge", primary_lockup="stacked", surfaces=("app icon",))
    assert fingerprint() == first  # brand.json changed, but nothing the audit reads
    seen = {first}
    registry.set_fields(paths, "keystone", industry="AI tooling")
    seen.add(fingerprint())
    state = registry.load_state(paths, "keystone")
    state.min_sizes.horizontal_px = 90
    registry.save_state(paths, state)
    seen.add(fingerprint())
    (project_root / "brands" / "keystone" / "brief.json").write_text(json.dumps({**brief_payload, "industry": "Dental clinic"}))
    seen.add(fingerprint())
    cliches = project_root / "assets" / "cliches.json"
    cliches.write_text(cliches.read_text() + "\n")
    seen.add(fingerprint())
    assert len(seen) == 5  # the industry, the minimum sizes, the brief's industry and the cliché lists each count


def test_a_failed_build_replaces_the_audit_with_a_failing_one(project_root):
    folder = install_concept(project_root, "good")
    assert audit.audit_concept(project(), "keystone", "01-good").ok
    write_concept(folder, "raise RuntimeError('boom')")
    with pytest.raises(CliError, match="RuntimeError: boom") as err:
        audit.audit_concept(project(), "keystone", "01-good")
    written = json.loads((folder / "audit.json").read_text())
    assert written["ok"] is False and written["rendered"] is False
    assert written["fingerprint"] == audit.concept_fingerprint(project(), "keystone", folder)
    assert [(f["check"], f["severity"], f["message"]) for f in written["failures"]] == [("build", "fail", str(err.value))]


@requires_chrome
@pytest.mark.render
def test_parts_that_split_at_small_sizes_are_flagged(project_root, renderer):
    folder = install_concept(project_root, "good", name="16-neck")
    # Two discs joined by a 6-unit bar: about 6 px at 512 px, a fraction of a pixel at 16 px, where the bar disappears.
    write_concept(folder, "return Mark(symbol=union(circle(-150, 0, 100), circle(150, 0, 100), rect(-150, -3, 300, 6)))",
                  tiers="{'full': {}, 'favicon': {}}")
    result = audit.audit_concept(project(), "keystone", "16-neck", renderer=renderer)
    split = [f for f in findings(result, "one_colour_merge") if f.data["output"] == "favicon"]
    assert split and split[0].severity == "fail" and (split[0].data["before"], split[0].data["after"]) == (1, 2)
    assert split[0].message == "favicon: 1 part(s) at 512 px become 2 at 16 px (parts split apart)"


def test_concept_audit_cli(project_root):
    install_concept(project_root, "good")
    result = CliRunner().invoke(main, ["concept", "audit", "keystone", "01-good", "--no-render"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0 and payload["ok"] and payload["audit"]["ok"] and payload["audit"]["rendered"] is False
    assert payload["errors"] == [] and payload["warnings"] == [f["message"] for f in payload["audit"]["warnings"]]


def test_a_failing_audit_fails_the_command(project_root):
    install_concept(project_root, "tiny_part", name="03-tiny")
    result = CliRunner().invoke(main, ["concept", "audit", "keystone", "03-tiny", "--no-render"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 2 and payload["ok"] is False and payload["audit"]["ok"] is False
    assert payload["errors"] == [f["message"] for f in payload["audit"]["failures"]]
    assert {f["check"] for f in payload["audit"]["failures"]} == {"tiny_parts"}
    assert payload["warnings"] == [f["message"] for f in payload["audit"]["warnings"]]
