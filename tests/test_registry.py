import json

import pytest
from click.testing import CliRunner

from logomaker import registry
from logomaker.cli import main
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.schemas import Phase


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


def test_list_brands(project_root):
    run("brand", "new", "Keystone")
    run("brand", "new", "Quill")
    code, payload = run("brand", "list")
    assert [b["slug"] for b in payload["brands"]] == ["keystone", "quill"]
