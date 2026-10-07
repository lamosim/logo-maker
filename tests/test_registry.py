import json
import shutil

import pytest
from click.testing import CliRunner

from logomaker import audit, registry
from logomaker.cli import main
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.schemas import Phase, TerritoriesSpec
from tests.conftest import FIXTURES, install_concept, make_final_brand, scorecard, write_passing_audit


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
    (folder / "scorecard.json").write_text(json.dumps(scorecard()))
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
    folder = install_concept(project_root, "good")
    (folder / "scorecard.json").write_text(json.dumps(scorecard()))
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
    (folder / "scorecard.json").write_text(json.dumps(scorecard()))
    brand = project_root / "brands" / "keystone"
    audit.audit_concept(project(), "keystone", "01-good")
    saved = json.loads((folder / "audit.json").read_text())
    (folder / "audit.json").write_text(json.dumps({**saved, "rendered": True}))
    assert run("brand", "set", "keystone", "--concept", "01-good")[0] == 0  # brand.json changes; nothing the audit read does
    assert registry._check_concept(brand, registry.load_state(project(), "keystone")) == []
    assert run("brand", "set", "keystone", "--industry", "AI tooling")[0] == 0  # the cliché check reads the industry
    stale = registry._check_concept(brand, registry.load_state(project(), "keystone"))
    assert len(stale) == 1 and stale[0].startswith("01-good/audit.json is stale") and "industry" in stale[0]


def test_the_concept_gate_needs_a_scorecard_that_passes_the_gate(project_root):
    folder = install_concept(project_root, "good")
    write_passing_audit(project(), "keystone", folder)
    state = registry.set_fields(project(), "keystone", concept="01-good")
    brand = project_root / "brands" / "keystone"
    card = folder / "scorecard.json"
    assert registry._check_concept(brand, state) == ["01-good/scorecard.json is missing"]
    gate = "01-good/scorecard.json fails the gate (appropriate, simple and legible must be 4 or more, and not killed)"
    for payload in (scorecard(legible=3), {**scorecard(), "kill": True, "reason": "reads as a padlock"}):
        card.write_text(json.dumps(payload))
        assert registry._check_concept(brand, state) == [gate]
    card.write_text(json.dumps({"scores": {"appropriate": 5}}))
    [problem] = registry._check_concept(brand, state)
    assert problem.startswith("01-good/scorecard.json is invalid: root: Value error, scores missing: distinctive, simple")
    card.write_text(json.dumps(scorecard(distinctive=2)))  # only appropriate, simple and legible gate
    assert registry._check_concept(brand, state) == []


def test_a_registry_rebuild_skips_brand_files_it_cannot_use_and_says_which(project_root):
    run("brand", "new", "Alpha")
    run("brand", "new", "Gamma")
    alpha = project_root / "brands" / "alpha" / "brand.json"
    alpha.write_text(alpha.read_text()[:40])  # truncated mid-object
    stray = project_root / "brands" / "Not A Slug" / "brand.json"  # a valid file in a folder no slug can name
    stray.parent.mkdir()
    stray.write_text((project_root / "brands" / "gamma" / "brand.json").read_text())
    index = project_root / "registry" / "brands.json"
    index.unlink()
    code, payload = run("brand", "new", "Beta")
    assert code == 0 and payload["brand"]["slug"] == "beta" and "traceback" not in payload, payload
    named = [[str(path) in w for path in (alpha, stray)] for w in payload["warnings"]]
    assert sorted(named) == [[False, True], [True, False]]  # one warning per skipped file, naming it
    index.unlink()
    code, payload = run("brand", "list")
    assert code == 0 and [b["slug"] for b in payload["brands"]] == ["beta", "gamma"]
    assert sorted([str(path) in w for path in (alpha, stray)] for w in payload["warnings"]) == [[False, True], [True, False]]
    code, payload = run("brand", "status", "alpha")  # reading the broken file directly is a clean error too
    assert code == 2 and "traceback" not in payload and payload["errors"][0].startswith(f"{alpha} is invalid: ")


def test_every_brand_command_reports_brands_the_index_leaves_out(project_root):
    run("brand", "new", "Alpha")
    run("brand", "new", "Gamma")
    alpha = project_root / "brands" / "alpha" / "brand.json"
    alpha.write_text(alpha.read_text()[:40])  # truncated mid-object
    (project_root / "registry" / "brands.json").unlink()
    code, payload = run("brand", "set", "gamma", "--industry", "fintech")  # saving gamma rebuilds the index without alpha
    assert code == 0 and payload["brand"]["industry"] == "fintech"
    assert len(payload["warnings"]) == 1 and str(alpha) in payload["warnings"][0]
    code, payload = run("brand", "list")  # the index exists again and still leaves alpha out: the warning stays
    assert code == 0 and [b["slug"] for b in payload["brands"]] == ["gamma"]
    assert len(payload["warnings"]) == 1 and str(alpha) in payload["warnings"][0]
    for args in (("decide", "gamma", "--phase", "intake", "--note", "kept"), ("rename", "gamma", "--name", "Gamma Co")):
        code, payload = run("brand", *args)
        assert code == 0 and [str(alpha) in w for w in payload["warnings"]] == [True], args
    delta = project_root / "brands" / "delta" / "brand.json"  # a valid brand the index never heard of
    delta.parent.mkdir()
    delta.write_text(json.dumps({**json.loads((project_root / "brands" / "gamma" / "brand.json").read_text()), "slug": "delta"}))
    warnings = run("brand", "list")[1]["warnings"]
    assert len(warnings) == 2 and str(delta) in warnings[1] and "missing from the index" in warnings[1]


def test_territories_json_must_use_slugs(project_root, territories_payload):
    run("brand", "new", "Keystone")
    brand = project_root / "brands" / "keystone"
    spec = brand / "territories" / "territories.json"
    state = registry.set_fields(project(), "keystone", territory="forge")
    for slug, problem in (("forge_works", "Value error, territory slug must be lowercase letters, digits and hyphens (e.g. "
                                          "forge-works), got 'forge_works'"),
                          (7, "Input should be a valid string")):
        territories_payload["territories"][1]["slug"] = slug
        spec.write_text(json.dumps(territories_payload))
        assert registry._check_territories(brand, state) == [f"territories/territories.json is invalid: territories.1.slug: {problem}"]
    territories_payload["territories"][1]["slug"] = "forge-works"
    spec.write_text(json.dumps(territories_payload))
    assert registry._check_territories(brand, state) == []


def test_the_territories_gate_needs_a_valid_spec_holding_the_chosen_territory(project_root, territories_payload):
    run("brand", "new", "Keystone")
    brand = project_root / "brands" / "keystone"
    spec = brand / "territories" / "territories.json"
    not_chosen = "territory not chosen (run: logomaker brand set <slug> --territory <territory-slug>)"
    state = registry.load_state(project(), "keystone")
    assert registry._check_territories(brand, state) == ["territories/territories.json is missing"]
    spec.write_text(json.dumps(territories_payload))
    assert registry._check_territories(brand, state) == [not_chosen]
    state = registry.set_fields(project(), "keystone", territory="quarry")  # a slug, but not one of the spec's
    assert registry._check_territories(brand, state) == [not_chosen]
    state = registry.set_fields(project(), "keystone", territory="ledger")
    assert registry._check_territories(brand, state) == []
    territories_payload["territories"].pop()  # one territory is too few: the spec's own problem is the one reported
    spec.write_text(json.dumps(territories_payload))
    [problem] = registry._check_territories(brand, state)
    assert problem.startswith("territories/territories.json is invalid: territories: List should have at least 2 items")


def test_load_model_returns_the_model_or_an_error_naming_the_file(project_root, territories_payload):
    path = project_root / "spec.json"
    with pytest.raises(CliError) as err:
        registry.load_model(path, TerritoriesSpec, "the spec")
    assert (str(err.value), err.value.code) == ("the spec is missing", 2)
    path.write_text(json.dumps({"territories": []}))
    with pytest.raises(CliError) as err:
        registry.load_model(path, TerritoriesSpec, "the spec", code=4)
    assert err.value.code == 4 and str(err.value).startswith("the spec is invalid: territories: List should have at least 2 items")
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(CliError, match="^the spec is not valid JSON: "):
        registry.load_model(path, TerritoriesSpec, "the spec")
    path.write_text(json.dumps(territories_payload))
    assert [t.slug for t in registry.load_model(path, TerritoriesSpec, "the spec").territories] == ["forge", "ledger"]


def test_final_tokens_must_validate(project_root):
    from tests.test_color import good_tokens

    run("brand", "new", "Keystone")
    brand = project_root / "brands" / "keystone"
    shutil.copy(FIXTURES / "concepts" / "good" / "concept.py", brand / "final" / "concept.py")
    (brand / "final" / "params.json").write_text("{}\n")
    tokens = brand / "final" / "tokens.json"
    tokens.write_text("{}")
    state = registry.load_state(project(), "keystone")

    def check_final() -> list[str]:
        """The final gate with a fresh passing audit of final/ as it stands (the audit's fingerprint covers tokens.json)."""
        write_passing_audit(project(), "keystone", brand / "final")
        return registry._check_final(brand, state)

    missing = check_final()
    assert len(missing) == 1 and missing[0].startswith("final/tokens.json is invalid: colors: ")
    tokens.write_text(json.dumps(good_tokens()))
    assert check_final() == []
    tokens.unlink()
    assert check_final() == ["final/tokens.json is missing"]


def test_the_final_gate_needs_a_current_rendered_passing_audit_of_the_final_mark(project_root):
    final = make_final_brand(project_root)  # in refinement: the final gate has not run yet
    brand = final.parent
    state = registry.load_state(project(), "keystone")
    assert state.phase == Phase.refinement and registry._check_final(brand, state) == []
    audit_json = final / "audit.json"
    passing = json.loads(audit_json.read_text())
    stale = ("final/audit.json is stale (concept.py, params.json, tokens.json, the brand's industry or minimum sizes, "
             "or cliches.json changed); re-run concept audit")
    for saved, problem in (({**passing, "rendered": False}, "final/audit.json was made with --no-render; re-run concept audit without it"),
                           ({**passing, "ok": False}, "final/audit.json has failures"),
                           ({**passing, "fingerprint": "0" * 64}, stale)):
        audit_json.write_text(json.dumps(saved))
        assert registry._check_final(brand, state) == [problem]
    audit_json.write_text("{not json")
    [problem] = registry._check_final(brand, state)
    assert problem.startswith("final/audit.json is not valid JSON: ")
    audit_json.write_text(json.dumps(passing))
    (final / "params.json").write_text('{"stroke": 80}')  # the final mark changed after its audit
    assert registry._check_final(brand, state) == [stale]
    audit_json.unlink()
    code, payload = run("brand", "advance", "keystone", "--to", "package")
    assert code == 2 and payload["missing"] == ["final/audit.json is missing"]
    write_passing_audit(project(), "keystone", final)
    code, payload = run("brand", "advance", "keystone", "--to", "package")
    assert code == 0 and payload["brand"]["phase"] == "package"
