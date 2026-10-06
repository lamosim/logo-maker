import json

import pytest
from click.testing import CliRunner

from logomaker import audit, registry
from logomaker.cli import main
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


def test_industry_resolution_ranks_whole_word_aliases(project_root):
    cliches = audit.load_cliches(project())
    assert audit.resolve_industry(cliches, "Real estate agent") == "real-estate"  # not ai, though 'agent' is an ai alias
    assert audit.resolve_industry(cliches, "AI for real estate") == "real-estate"  # the longer alias beats the earlier one
    dental = audit.resolve_industries(cliches, "Dental clinic")  # equal lengths: the earlier match ranks first
    assert dental[0] == "dental" and "healthcare" in dental
    assert audit.resolve_industry(cliches, "Orthodontics") == "dental"
    assert audit.resolve_industry(cliches, "Invoicing for consultants") == "fintech"
    assert audit.resolve_industry(cliches, "AI tooling") == "ai"
    assert audit.resolve_industries(cliches, "Widgets") == [] and audit.resolve_industries(cliches, None) == []


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
    union = audit.check_cliches(["tooth", "heartbeat"], cliches, "Dental clinic")
    assert [(f.data["term"], f.data["source"]) for f in union] == [("tooth", "dental"), ("heartbeat", "healthcare")]


def test_text_legibility_fails_when_lockup_is_too_small(project_root):
    install_concept(project_root, "good")
    state = registry.load_state(project(), "keystone")
    state.min_sizes.horizontal_px = 60
    registry.save_state(project(), state)
    result = audit.audit_concept(project(), "keystone", "01-good")
    assert findings(result, "text_legibility")[0].severity == "fail" and not result.ok


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


def test_colour_count_counts_roles_other_than_paper(project_root):
    folder = install_concept(project_root, "good", name="10-roles")
    (folder / "concept.py").write_text(
        "from logomaker.kit import *\n"
        "META = Meta(slug='roles', idea='five swatches', logo_type='abstract')\n"
        "PARAMS = Params()\nTIERS = {'full': {}}\n"
        "ROLES = ['primary', 'secondary', 'accent', 'ink', 'paper']\n"
        "def build(p):\n"
        "    return Mark(symbol=Composite([(circle(i * 300, 0, 100), role) for i, role in enumerate(ROLES)]))\n"
    )
    count = findings(audit.audit_concept(project(), "keystone", "10-roles"), "colour_count")
    assert count[0].severity == "warn" and count[0].message.startswith("4 colour roles") and "paper" not in count[0].data["roles"]


def test_tokens_contrast_feeds_the_audit(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")
    bad = good_tokens()
    bad["colors"]["coal"]["hex"] = "#777777"
    (folder / "tokens.json").write_text(json.dumps(bad))
    result = audit.audit_concept(project(), "keystone", "01-good")
    assert findings(result, "contrast")[0].severity == "fail"


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
    assert {f.data["output"]: f.severity for f in findings(result, "tiny_parts")} == {"full-symbol": "warn", "small": "fail", "favicon": "fail"}


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
    # The missing small tier is still rendered, on its full-symbol fallback.
    assert {f.data["output"] for f in findings(result, "min_feature")} == {"full-symbol", "small", "favicon"}


def test_concept_audit_cli(project_root):
    install_concept(project_root, "good")
    result = CliRunner().invoke(main, ["concept", "audit", "keystone", "01-good", "--no-render"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0 and payload["ok"] and payload["audit"]["ok"] and payload["audit"]["rendered"] is False
