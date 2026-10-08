import json

import pytest
from click.testing import CliRunner
from PIL import Image
from pydantic import ValidationError

from logomaker import knockout, registry, sheets
from logomaker.cli import main
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.schemas import ImageSearch, Knockout
from tests.conftest import StubRenderer, critic_run, install_concept, make_final_brand, recorded, scorecard, write_passing_audit


def run(*args):
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, json.loads(result.stdout)


def test_knockout_template_is_empty_and_not_done():
    empty = Knockout()
    assert empty.image_matches.tool == "google-lens" and not empty.image_done and not empty.wipo_done
    assert empty.model_dump()["wipo"] is None


def test_an_image_search_is_done_when_searched_or_skipped_with_a_reason():
    assert Knockout(image_matches=ImageSearch(tool="google-lens", searched=True, date="2026-10-09")).image_done
    assert Knockout(image_matches=ImageSearch(tool="google-lens", skipped="Chrome extension unavailable")).image_done
    assert not Knockout(image_matches=ImageSearch(tool="google-lens", skipped="")).image_done
    with pytest.raises(ValidationError, match="searched and skipped are exclusive"):
        ImageSearch(tool="google-lens", searched=True, skipped="also skipped")
    wipo = ImageSearch(tool="wipo", searched=True, matches=[{"url": "https://branddb.wipo.int/x", "note": "an arch"}])
    assert Knockout(wipo=wipo).wipo_done


def test_write_images_renders_the_mark_and_lockup_and_seeds_the_file(project_root):
    folder = install_concept(project_root, "good", name="01-good")
    renderer = StubRenderer()
    info = knockout.write_images(project(), "keystone", "01-good", renderer=renderer)
    assert info["round"] == 1 and info["created"] is True and info["warnings"] == []
    mark = folder / "knockout" / "round-1" / "mark-512.png"
    lockup = folder / "knockout" / "round-1" / "lockup-1024.png"
    assert mark.is_file() and lockup.is_file()
    assert max(Image.open(mark).size) == 512 and max(Image.open(lockup).size) == 1024
    assert all(call[3] == "#ffffff" for call in renderer.calls)  # black on white, for the search engines
    seeded = json.loads((folder / "knockout.json").read_text())
    assert seeded["image_matches"] == {"tool": "google-lens", "date": "", "searched": False, "matches": [], "skipped": None}
    (folder / "knockout.json").write_text(json.dumps({**seeded, "caveat": "kept"}))
    again = knockout.write_images(project(), "keystone", "01-good", renderer=StubRenderer())
    assert again["round"] == 2 and again["created"] is False
    assert json.loads((folder / "knockout.json").read_text())["caveat"] == "kept"


def test_write_images_warns_for_a_wordmark_only_concept(project_root):
    install_concept(project_root, "wordmark_only", name="02-word")
    info = knockout.write_images(project(), "keystone", "02-word", renderer=StubRenderer())
    assert info["warnings"] == ["no symbol: the mark image shows the full lockup"]


def test_concept_knockout_cli_needs_chrome(project_root, no_chrome):
    install_concept(project_root, "good", name="01-good")
    code, payload = run("concept", "knockout", "keystone", "01-good")
    assert code == 2 or code == 3  # NoChrome raises AssertionError inside the command wrapper: exit 2 with a traceback
    assert not (project_root / "brands" / "keystone" / "concepts" / "01-good" / "knockout").exists()


def test_knockout_problems_for_a_survivor(project_root):
    folder = install_concept(project_root, "good", name="01-good")
    paths = project()
    assert knockout.knockout_problems(paths, "keystone", folder) == [
        "01-good/knockout.json is missing (run: logomaker concept knockout keystone 01-good, search by image, record the matches)"]
    knockout.write_images(paths, "keystone", "01-good", renderer=StubRenderer())
    assert knockout.knockout_problems(paths, "keystone", folder) == [
        "01-good/knockout.json has no image knock-out (run Google Lens on knockout/round-1/mark-512.png and record the matches, "
        "or record skipped with a reason)"]
    recorded(folder)
    assert knockout.knockout_problems(paths, "keystone", folder) == []
    recorded(folder, skipped="the Chrome extension was unavailable")
    assert knockout.knockout_problems(paths, "keystone", folder) == [
        "01-good/knockout.json records the image knock-out as skipped without the owner's decision (run: logomaker brand decide "
        'keystone --phase concepts --by user --note "knock-out skipped: <reason>")']
    registry.decide(paths, "keystone", registry.Phase.concepts, "claude", "knock-out skipped: no Chrome")
    assert knockout.knockout_problems(paths, "keystone", folder)  # Claude's note does not count
    registry.decide(paths, "keystone", registry.Phase.concepts, "user", "knock-out skipped: travelling, no Chrome")
    assert knockout.knockout_problems(paths, "keystone", folder) == []


def test_knockout_problems_for_final_need_wipo(project_root):
    final = make_final_brand(project_root)
    paths = project()
    recorded(final)  # overwrites the one make_final_brand records: Lens only, no WIPO
    assert knockout.knockout_problems(paths, "keystone", final, final=True) == [
        "final/knockout.json has no WIPO image search (upload knockout/round-N/mark-512.png to the Global Brand Database and record "
        "the matches, or record skipped with a reason)"]
    recorded(final, wipo=True)
    assert knockout.knockout_problems(paths, "keystone", final, final=True) == []


def test_the_concept_sheet_and_the_gates_read_the_knockout(project_root, no_chrome):
    folder = install_concept(project_root, "good", name="01-good")
    paths = project()
    write_passing_audit(paths, "keystone", folder)
    (folder / "scorecard.json").write_text(json.dumps(scorecard()))
    critic_run(project_root, ["01-good"])
    with pytest.raises(CliError, match="concept 01-good: 01-good/knockout.json is missing"):
        sheets.concepts_sheet(paths, "keystone", ["01-good"], open_after=False)
    recorded(folder)
    with pytest.raises(AssertionError, match="Chrome started"):  # every check passed; the render is next
        sheets.concepts_sheet(paths, "keystone", ["01-good"], open_after=False)


def test_advance_to_package_needs_the_final_knockout(project_root):
    final = make_final_brand(project_root)
    paths = project()
    (final / "knockout.json").unlink()  # make_final_brand records one; this test checks the gate
    with pytest.raises(CliError) as err:
        registry.advance(paths, "keystone", registry.Phase.package)
    assert any("final/knockout.json is missing" in m for m in err.value.data["missing"])
    recorded(final, wipo=True)
    assert registry.advance(paths, "keystone", registry.Phase.package).phase == registry.Phase.package


def test_a_concept_needs_its_knockout_only_while_the_brand_leaves_concepts(project_root):
    final = make_final_brand(project_root)
    (final.parent / "concepts" / "01-good" / "knockout.json").unlink()  # past concepts, final/ is what ships
    assert registry.advance(project(), "keystone", registry.Phase.package).phase == registry.Phase.package


def stale(name: str) -> str:
    return (f"{name}/knockout.json is stale (the mark changed since the search); re-run: logomaker concept knockout "
            f"keystone {name}")


def test_a_changed_concept_makes_the_knockout_stale(project_root):
    folder = install_concept(project_root, "good", name="01-good")
    paths = project()
    recorded(folder)
    assert knockout.knockout_problems(paths, "keystone", folder) == []
    (folder / "params.json").write_text('{"stroke": 80}')
    assert knockout.knockout_problems(paths, "keystone", folder) == [stale("01-good")]
    recorded(folder, fingerprint="")  # a record that never had one is stale too
    (folder / "params.json").unlink()
    assert knockout.knockout_problems(paths, "keystone", folder) == [stale("01-good")]


def test_concept_knockout_resets_the_searches_only_when_the_mark_changed(project_root):
    from logomaker.audit import concept_fingerprint

    folder = install_concept(project_root, "good", name="01-good")
    paths = project()
    first = knockout.write_images(paths, "keystone", "01-good", renderer=StubRenderer())
    assert first["reset"] is True  # a seeded record has no fingerprint yet
    assert json.loads((folder / "knockout.json").read_text())["fingerprint"] == concept_fingerprint(paths, "keystone", folder)
    recorded(folder, wipo=True)
    data = json.loads((folder / "knockout.json").read_text())
    data["image_matches"]["matches"] = [{"url": "https://example.com/arch", "note": "silhouette"}]
    (folder / "knockout.json").write_text(json.dumps({**data, "owner_notes": "kept"}))
    again = knockout.write_images(paths, "keystone", "01-good", renderer=StubRenderer())
    assert again["reset"] is False
    kept = json.loads((folder / "knockout.json").read_text())
    assert kept["image_matches"]["searched"] is True and kept["image_matches"]["matches"] and kept["wipo"]["searched"] is True
    (folder / "params.json").write_text('{"stroke": 80}')
    changed = knockout.write_images(paths, "keystone", "01-good", renderer=StubRenderer())
    assert changed["reset"] is True and changed["round"] == 3
    after = json.loads((folder / "knockout.json").read_text())
    assert after["fingerprint"] == concept_fingerprint(paths, "keystone", folder) != data["fingerprint"]
    for search in (after["image_matches"], after["wipo"]):
        assert (search["searched"], search["matches"], search["date"]) == (False, [], "")
    assert after["description_queries"] == data["description_queries"] and after["caveat"] == data["caveat"]
    assert after["owner_notes"] == "kept"
    assert knockout.knockout_problems(paths, "keystone", folder)[0].startswith("01-good/knockout.json has no image knock-out")


def test_a_reset_keeps_a_skipped_reason(project_root):
    folder = install_concept(project_root, "good", name="01-good")
    recorded(folder, skipped="no Chrome")
    (folder / "params.json").write_text('{"stroke": 80}')
    assert knockout.write_images(project(), "keystone", "01-good", renderer=StubRenderer())["reset"] is True
    assert json.loads((folder / "knockout.json").read_text())["image_matches"]["skipped"] == "no Chrome"


def test_a_concepts_skip_note_does_not_clear_the_final_wipo_skip(project_root):
    final = make_final_brand(project_root)
    paths = project()
    recorded(final, wipo=True)
    data = json.loads((final / "knockout.json").read_text())
    data["wipo"] = {**data["wipo"], "searched": False, "skipped": "WIPO was down"}
    (final / "knockout.json").write_text(json.dumps(data))
    skipped = ("final/knockout.json records the WIPO search as skipped without the owner's decision (run: logomaker brand "
               'decide keystone --phase refinement --by user --note "knock-out skipped: <reason>")')
    assert knockout.knockout_problems(paths, "keystone", final, final=True) == [skipped]
    registry.decide(paths, "keystone", registry.Phase.concepts, "user", "knock-out skipped: WIPO was down")
    assert knockout.knockout_problems(paths, "keystone", final, final=True) == [skipped]
    registry.decide(paths, "keystone", registry.Phase.refinement, "user", "knock-out skipped: WIPO was down")
    assert knockout.knockout_problems(paths, "keystone", final, final=True) == []


def test_no_image_knockout_without_a_round_names_the_command_first(project_root):
    from logomaker.audit import concept_fingerprint

    folder = install_concept(project_root, "good", name="01-good")
    fingerprint = concept_fingerprint(project(), "keystone", folder)
    (folder / "knockout.json").write_text(json.dumps({**Knockout().model_dump(), "fingerprint": fingerprint}))
    assert knockout.knockout_problems(project(), "keystone", folder) == [
        "01-good/knockout.json has no image knock-out (run: logomaker concept knockout keystone 01-good, then Google Lens on "
        "the knockout/round-N/mark-512.png it writes and record the matches, or record skipped with a reason)"]
