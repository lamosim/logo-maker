import json

import pytest
from click.testing import CliRunner

from logomaker import audit, registry
from logomaker.cli import main
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.schemas import Phase
from tests.conftest import install_concept


def run(*args):
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, json.loads(result.stdout)


def test_slugify():
    assert registry.slugify("Café Nuit") == "cafe-nuit"
    assert registry.slugify("  Acme Co. ") == "acme-co"
    with pytest.raises(CliError):
        registry.slugify("!!!")


def test_new_brand_creates_structure_and_registry(project_root):
    state = registry.new_brand(project(), "Café Nuit")
    assert state.slug == "cafe-nuit" and state.phase == Phase.intake and state.needs_name is False
    brand = project_root / "brands" / "cafe-nuit"
    for sub in ("inspiration", "territories", "concepts", "sheets", "final", "package"):
        assert (brand / sub).is_dir()
    saved = json.loads((brand / "brand.json").read_text())
    assert saved["name"] == "Café Nuit"
    reg = json.loads((project_root / "registry" / "brands.json").read_text())
    assert reg["brands"][0]["slug"] == "cafe-nuit"
    assert "cafe-nuit" in (project_root / "registry" / "INDEX.md").read_text()


def test_duplicate_brand_exits_2(project_root):
    assert run("brand", "new", "Keystone")[0] == 0
    code, payload = run("brand", "new", "Keystone")
    assert code == 2 and payload["ok"] is False and "exists" in payload["errors"][0]


def test_advance_refuses_without_brief(project_root):
    run("brand", "new", "Keystone")
    code, payload = run("brand", "advance", "keystone", "--to", "strategy")
    assert code == 2
    assert any("brief.json" in m for m in payload["missing"])


def write_brief(project_root, slug, payload):
    brand = project_root / "brands" / slug
    (brand / "brief.md").write_text("# Brief\n")
    (brand / "brief.json").write_text(json.dumps(payload))


def test_advance_to_strategy_with_valid_brief(project_root, brief_payload):
    run("brand", "new", "Keystone")
    write_brief(project_root, "keystone", brief_payload)
    code, payload = run("brand", "advance", "keystone", "--to", "strategy")
    assert code == 0, payload
    assert payload["brand"]["phase"] == "strategy"


def test_invalid_brief_is_reported(project_root, brief_payload):
    run("brand", "new", "Keystone")
    brief_payload["adjectives"] = []
    write_brief(project_root, "keystone", brief_payload)
    code, payload = run("brand", "advance", "keystone", "--to", "strategy")
    assert code == 2 and any("adjectives" in m for m in payload["missing"])


def test_unnamed_brand_must_be_named_before_strategy(project_root, brief_payload):
    run("brand", "new", "Working Title", "--unnamed")
    brief_payload["needs_name"] = True
    brief_payload["name"] = None
    write_brief(project_root, "working-title", brief_payload)
    code, payload = run("brand", "advance", "working-title", "--to", "strategy")
    assert code == 2 and any("naming" in m for m in payload["missing"])
    code, payload = run("brand", "advance", "working-title", "--to", "naming")
    assert code == 0
    (project_root / "brands" / "working-title" / "naming.md").write_text("# Naming\n")
    code, payload = run("brand", "advance", "working-title", "--to", "strategy")
    assert code == 2 and any("needs a name" in m for m in payload["missing"])
    code, payload = run("brand", "rename", "working-title", "--name", "Keystone")
    assert code == 0 and payload["brand"]["name"] == "Keystone" and payload["brand"]["needs_name"] is False
    code, payload = run("brand", "advance", "working-title", "--to", "strategy")
    assert code == 0 and payload["brand"]["slug"] == "working-title"


def test_advance_rechecks_every_earlier_phase(project_root, brief_payload, strategy_payload):
    run("brand", "new", "Keystone")
    write_brief(project_root, "keystone", brief_payload)
    assert run("brand", "advance", "keystone", "--to", "strategy")[0] == 0
    brand = project_root / "brands" / "keystone"
    (brand / "brief.json").unlink()
    (brand / "strategy.md").write_text("# Strategy\n")
    (brand / "strategy.json").write_text(json.dumps(strategy_payload))
    code, payload = run("brand", "advance", "keystone", "--to", "territories")
    assert code == 2 and any("brief.json" in m for m in payload["missing"])
    assert any("brief.json" in m for m in run("brand", "status", "keystone")[1]["missing"])
    (brand / "brief.json").write_text(json.dumps(brief_payload))
    code, payload = run("brand", "advance", "keystone", "--to", "territories")
    assert code == 0 and payload["brand"]["phase"] == "territories"


def test_naming_phase_needs_naming_md_before_strategy(project_root, brief_payload):
    run("brand", "new", "Working Title", "--unnamed")
    brief_payload["needs_name"] = True
    brief_payload["name"] = None
    write_brief(project_root, "working-title", brief_payload)
    assert run("brand", "advance", "working-title", "--to", "naming")[0] == 0
    assert run("brand", "rename", "working-title", "--name", "Keystone")[0] == 0
    code, payload = run("brand", "advance", "working-title", "--to", "strategy")
    assert code == 2 and any("naming.md" in m for m in payload["missing"])
    (project_root / "brands" / "working-title" / "naming.md").write_text("# Naming\n")
    code, payload = run("brand", "advance", "working-title", "--to", "strategy")
    assert code == 0 and payload["brand"]["phase"] == "strategy"


def test_decide_appends_and_status_reports_next(project_root):
    run("brand", "new", "Keystone")
    code, payload = run("brand", "decide", "keystone", "--phase", "intake", "--by", "user", "--note", "likes orange")
    assert code == 0 and payload["brand"]["decisions"][0]["note"] == "likes orange"
    code, payload = run("brand", "status", "keystone")
    assert payload["next"] == "strategy" and any("brief" in m for m in payload["missing"])


def test_set_updates_fields(project_root):
    run("brand", "new", "Keystone")
    code, payload = run(
        "brand", "set", "keystone", "--territory", "forge", "--industry", "fintech",
        "--primary-lockup", "stacked", "--surface", "app icon", "--surface", "merch", "--font", "wordmark=Sora:650",
    )
    assert code == 0, payload
    b = payload["brand"]
    assert b["territory"] == "forge" and b["industry"] == "fintech" and b["primary_lockup"] == "stacked"
    assert b["surfaces"] == ["app icon", "merch"] and b["fonts"]["wordmark"] == {"family": "Sora", "weight": 650, "italic": False}


def test_font_weight_must_be_a_number(project_root):
    run("brand", "new", "Keystone")
    code, payload = run("brand", "set", "keystone", "--font", "wordmark=Sora:bold")
    assert code == 2 and "traceback" not in payload
    assert payload["errors"] == ["--font weight must be a whole number, got 'bold' in 'wordmark=Sora:bold'"]


def test_brand_set_takes_only_concept_folder_names_and_territory_slugs(project_root):
    run("brand", "new", "Keystone")
    for flag, value in (("--concept", "../x"), ("--concept", "foo/bar"), ("--concept", "final"), ("--concept", "3-keystone"),
                        ("--territory", "../x"), ("--territory", "foo/bar"), ("--territory", "Forge Works")):
        code, payload = run("brand", "set", "keystone", flag, value)
        assert code == 2 and "traceback" not in payload and repr(value) in payload["errors"][0], (flag, value, payload)
    state = registry.load_state(project(), "keystone")
    assert state.concept is None and state.territory is None  # nothing was saved
    code, payload = run("brand", "set", "keystone", "--concept", "03-keystone", "--territory", "forge-works")
    assert code == 0 and (payload["brand"]["concept"], payload["brand"]["territory"]) == ("03-keystone", "forge-works")


def test_list_brands(project_root):
    run("brand", "new", "Keystone")
    run("brand", "new", "Quill")
    code, payload = run("brand", "list")
    assert [b["slug"] for b in payload["brands"]] == ["keystone", "quill"]


def test_concept_gate_needs_a_current_rendered_passing_audit(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")
    state = registry.set_fields(project(), "keystone", concept="01-good")
    brand = project_root / "brands" / "keystone"
    stale = ("01-good/audit.json is stale (concept.py, params.json, tokens.json, the brand's industry or minimum sizes, "
             "or cliches.json changed); re-run concept audit")

    def audited(rendered: bool) -> None:
        """A fresh audit of the concept as it stands; `rendered` stands in for the raster checks (no Chrome needed)."""
        audit.audit_concept(project(), "keystone", "01-good")
        saved = json.loads((folder / "audit.json").read_text())
        (folder / "audit.json").write_text(json.dumps({**saved, "rendered": rendered}))

    audited(rendered=False)
    assert registry._check_concept(brand, state) == ["01-good/audit.json was made with --no-render; re-run concept audit without it"]
    audited(rendered=True)
    assert registry._check_concept(brand, state) == []
    edits = (("params.json", '{"stroke": 80}'), ("tokens.json", json.dumps(good_tokens())),
             ("concept.py", (folder / "concept.py").read_text() + "# edited\n"))
    for name, content in edits:
        (folder / name).write_text(content)
        assert registry._check_concept(brand, state) == [stale], name
        audited(rendered=True)
        assert registry._check_concept(brand, state) == [], name
    saved = json.loads((folder / "audit.json").read_text())
    (folder / "audit.json").write_text(json.dumps({**saved, "ok": False}))
    assert registry._check_concept(brand, state) == ["01-good/audit.json has failures"]


def test_malformed_audit_or_verify_json_is_reported_not_raised(project_root):
    install_concept(project_root, "good")
    state = registry.set_fields(project(), "keystone", concept="01-good")
    brand = project_root / "brands" / "keystone"
    for content, problem in (("{not json", "is not valid JSON: "), ("[1, 2]", "is not a JSON object")):
        (brand / "concepts" / "01-good" / "audit.json").write_text(content)
        (brand / "package" / "verify.json").write_text(content)
        concept, verify = registry._check_concept(brand, state), registry._check_verify(brand, state)
        assert len(concept) == 1 and concept[0].startswith(f"concepts/01-good/audit.json {problem}"), concept
        assert len(verify) == 1 and verify[0].startswith(f"package/verify.json {problem}"), verify


def test_a_malformed_registry_index_is_an_error_naming_it(project_root):
    run("brand", "new", "Keystone")
    index = project_root / "registry" / "brands.json"
    for content in ("not json", "[]", '{"brands": 3}', '{"brands": [{"name": "no slug"}]}'):
        index.write_text(content)
        code, payload = run("brand", "list")
        assert code == 2 and "traceback" not in payload and payload["errors"][0].startswith(str(index)), (content, payload)
        assert "rebuild" in payload["errors"][0]


def test_brand_list_rebuilds_a_missing_index_from_the_brand_folders(project_root):
    run("brand", "new", "Quill")
    run("brand", "new", "Keystone")
    (project_root / "registry" / "brands.json").unlink()
    (project_root / "registry" / "INDEX.md").unlink()
    code, payload = run("brand", "list")
    listed = [(b["slug"], b["name"], b["phase"]) for b in payload["brands"]]
    assert code == 0 and listed == [("keystone", "Keystone", "intake"), ("quill", "Quill", "intake")]
    assert json.loads((project_root / "registry" / "brands.json").read_text())["brands"] == payload["brands"]
    assert "| quill | Quill | intake |" in (project_root / "registry" / "INDEX.md").read_text()


def test_the_concept_gate_follows_only_the_brand_settings_the_audit_reads(project_root):
    folder = install_concept(project_root, "good")
    brand = project_root / "brands" / "keystone"
    audit.audit_concept(project(), "keystone", "01-good")
    saved = json.loads((folder / "audit.json").read_text())
    (folder / "audit.json").write_text(json.dumps({**saved, "rendered": True}))
    assert run("brand", "set", "keystone", "--concept", "01-good")[0] == 0  # brand.json changes; nothing the audit read does
    assert registry._check_concept(brand, registry.load_state(project(), "keystone")) == []
    assert run("brand", "set", "keystone", "--industry", "AI tooling")[0] == 0  # the cliché check reads the industry
    stale = registry._check_concept(brand, registry.load_state(project(), "keystone"))
    assert len(stale) == 1 and stale[0].startswith("01-good/audit.json is stale") and "industry" in stale[0]


def test_final_tokens_must_validate(project_root):
    from tests.test_color import good_tokens

    run("brand", "new", "Keystone")
    brand = project_root / "brands" / "keystone"
    (brand / "final" / "concept.py").write_text("# concept\n")
    (brand / "final" / "params.json").write_text("{}\n")
    tokens = brand / "final" / "tokens.json"
    tokens.write_text("{}")
    state = registry.load_state(project(), "keystone")
    missing = registry._check_final(brand, state)
    assert len(missing) == 1 and missing[0].startswith("final/tokens.json is invalid: colors: ")
    tokens.write_text(json.dumps(good_tokens()))
    assert registry._check_final(brand, state) == []
    tokens.unlink()
    assert registry._check_final(brand, state) == ["final/tokens.json is missing"]
