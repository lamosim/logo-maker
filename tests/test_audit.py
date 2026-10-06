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
    cliches = audit.load_cliches(project())
    assert audit.resolve_industry(cliches, "Invoicing for consultants") == "fintech"
    assert audit.resolve_industry(cliches, None) is None


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


def test_concept_audit_cli(project_root):
    install_concept(project_root, "good")
    result = CliRunner().invoke(main, ["concept", "audit", "keystone", "01-good", "--no-render"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0 and payload["ok"] and payload["audit"]["ok"] and payload["audit"]["rendered"] is False
