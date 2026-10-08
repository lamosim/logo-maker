import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from logomaker import critic, registry, sheets
from logomaker.cli import main
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.schemas import CRITERIA, CriticCard, Scorecard
from tests.conftest import (
    StubChrome,
    both_orders,
    critic_run,
    install_concept,
    make_final_brand,
    pass_card,
    recorded,
    scorecard,
    write_pass,
    write_passing_audit,
)


def critic_card(**overrides) -> dict:
    scores = {c: 4 for c in CRITERIA}
    scores.update(overrides)
    return {"scores": scores, "evidence": {"appropriate": ["reads as an arch", "an arch at once"]}, "preferred_over": ["01-k-jaw"],
            "tied_with": [], "sheet": 1, "passes": 2, "fingerprint": "abc"}


def test_critic_card_validates_like_a_scorecard():
    card = CriticCard.model_validate(critic_card())
    assert card.total == 40 and card.passes == 2 and card.preferred_over == ["01-k-jaw"]
    with pytest.raises(ValidationError, match="scores missing: distinctive"):
        CriticCard.model_validate({**critic_card(), "scores": {c: 4 for c in CRITERIA if c != "distinctive"}})
    with pytest.raises(ValidationError, match="scores must be 1..5"):
        CriticCard.model_validate(critic_card(simple=0))


def test_scorecard_takes_reconciled_entries_and_defaults_to_none():
    assert Scorecard.model_validate(scorecard()).reconciled == {}
    card = Scorecard.model_validate({**scorecard(), "reconciled": {"distinctive": "the critic saw the stock arches; 3 stands"}})
    assert card.reconciled["distinctive"].startswith("the critic")


KEY = {"round": 1, "seed": 1, "letters": {"A": "02-arch", "B": "01-k-jaw"}, "fingerprints": {"02-arch": "f2", "01-k-jaw": "f1"}}


def test_pair_prefers_one_of_its_letters_or_a_tie():
    assert critic.Pair(first="A", second="B", prefer="tie").prefer == "tie"
    with pytest.raises(ValidationError, match="prefer must be A, B or tie"):
        critic.Pair(first="A", second="B", prefer="C")
    with pytest.raises(ValidationError, match="a pair needs two different letters"):
        critic.Pair(first="A", second="A", prefer="A")


def test_merge_averages_scores_half_up_and_keeps_every_line():
    first = critic.CriticPass(cards={"A": pass_card(distinctive=3), "B": pass_card()}, pairs=both_orders("A", "B", "A"))
    second = critic.CriticPass(cards={"A": pass_card(distinctive=4, simple=5), "B": pass_card()}, pairs=both_orders("A", "B", "A"))
    key = critic.Key.model_validate(KEY)
    cards = critic.merge([(key, first), (key, second)])
    arch = cards["02-arch"]
    assert arch.scores["distinctive"] == 4 and arch.scores["simple"] == 5  # 3.5 rounds up, 4.5 rounds up
    assert arch.evidence["distinctive"] == ["an arch, which stock sites already sell"] * 2
    assert arch.passes == 2 and arch.sheet == 1 and arch.fingerprint == "f2"
    assert arch.preferred_over == ["01-k-jaw"] and arch.tied_with == []
    assert cards["01-k-jaw"].preferred_over == [] and cards["01-k-jaw"].tied_with == ["02-arch"]


def test_merge_calls_a_pair_tied_unless_every_verdict_agrees():
    pairs = both_orders("A", "B", "A")[:1] + both_orders("A", "B", "B")[1:]  # A first order, B the other
    one = critic.CriticPass(cards={"A": pass_card(), "B": pass_card()}, pairs=pairs)
    cards = critic.merge([(critic.Key.model_validate(KEY), one)])
    assert cards["02-arch"].tied_with == ["01-k-jaw"] and cards["01-k-jaw"].tied_with == ["02-arch"]
    assert cards["02-arch"].passes == 1


def test_merge_calls_a_pair_tied_when_one_pass_leaves_it_out():
    silent = critic.CriticPass(cards={"A": pass_card(), "B": pass_card()})
    sure = critic.CriticPass(cards={"A": pass_card(), "B": pass_card()}, pairs=both_orders("A", "B", "A"))
    key = critic.Key.model_validate(KEY)
    for runs in ([(key, silent), (key, sure)], [(key, sure), (key, silent)]):
        cards = critic.merge(runs)
        assert cards["02-arch"].preferred_over == [] and cards["02-arch"].tied_with == ["01-k-jaw"]
        assert cards["01-k-jaw"].tied_with == ["02-arch"]


def test_merge_refuses_a_pass_whose_letters_do_not_match_the_sheet():
    key = critic.Key.model_validate(KEY)
    with pytest.raises(CliError, match=r"pass 1 scores A, C; the sheet has A, B"):
        critic.merge([(key, critic.CriticPass(cards={"A": pass_card(), "C": pass_card()}))])
    with pytest.raises(CliError, match=r"pass 1 judges A and B in one order only; judge every pair in both orders"):
        critic.merge([(key, critic.CriticPass(cards={"A": pass_card(), "B": pass_card()}, pairs=both_orders("A", "B", "A")[:1]))])
    with pytest.raises(CliError, match="at least one pass"):
        critic.merge([])


SWAPPED = {"round": 2, "seed": 2, "letters": {"A": "01-k-jaw", "B": "02-arch"}, "fingerprints": {"02-arch": "f2", "01-k-jaw": "f1"}}


def test_merge_translates_two_sheets_with_different_letters_into_one_card_per_concept():
    # Sheet 1 letters 02-arch A; sheet 2 letters it B. Both passes prefer 02-arch and score its distinctive 3 then 4, and
    # 01-k-jaw's 4 then 2: merged by letter instead of by concept, 02-arch's distinctive would be (3 + 2) / 2, rounded to 3.
    first = critic.CriticPass(cards={"A": pass_card(distinctive=3), "B": pass_card(simple=2)}, pairs=both_orders("A", "B", "A"))
    second = critic.CriticPass(cards={"A": pass_card(simple=3, distinctive=2), "B": pass_card(distinctive=4)},
                               pairs=both_orders("A", "B", "B"))
    cards = critic.merge([(critic.Key.model_validate(KEY), first), (critic.Key.model_validate(SWAPPED), second)])
    arch, jaw = cards["02-arch"], cards["01-k-jaw"]
    assert arch.scores["distinctive"] == 4 and arch.scores["simple"] == 4  # (3 + 4) / 2 rounds up; 4 and 4
    assert jaw.scores["distinctive"] == 3 and jaw.scores["simple"] == 3  # (4 + 2) / 2; (2 + 3) / 2 rounds up to 3
    assert arch.passes == jaw.passes == 2 and arch.sheet == jaw.sheet == 2 and arch.fingerprint == "f2"
    assert arch.preferred_over == ["01-k-jaw"] and jaw.tied_with == ["02-arch"]


def test_merge_refuses_sheets_that_letter_other_concepts_or_a_changed_one():
    one = critic.CriticPass(cards={"A": pass_card(), "B": pass_card()})
    other = critic.Key.model_validate({**SWAPPED, "letters": {"A": "01-k-jaw", "B": "03-dots"},
                                       "fingerprints": {"01-k-jaw": "f1", "03-dots": "f3"}})
    with pytest.raises(CliError, match=r"sheet 2 keys different concepts from sheet 1: 01-k-jaw, 03-dots against 01-k-jaw, 02-arch"):
        critic.merge([(critic.Key.model_validate(KEY), one), (other, one)])
    changed = critic.Key.model_validate({**SWAPPED, "fingerprints": {"02-arch": "f2", "01-k-jaw": "f1-new"}})
    with pytest.raises(CliError, match=r"01-k-jaw changed between sheet 1 and sheet 2; run sheet critic again"):
        critic.merge([(critic.Key.model_validate(KEY), one), (changed, one)])
    bad = critic.CriticPass(cards={"A": pass_card(), "C": pass_card()})
    with pytest.raises(CliError, match=r"sheet 2 pass 1 scores A, C; the sheet has A, B"):
        critic.merge([(critic.Key.model_validate(KEY), one), (critic.Key.model_validate(SWAPPED), bad)])


def test_unreconciled_lists_every_criterion_two_or_more_apart_without_an_entry():
    designer = Scorecard.model_validate({**scorecard(distinctive=5, timeless=2), "reconciled": {"timeless": "the critic saw a trend"}})
    card = CriticCard.model_validate(critic_card(distinctive=3, timeless=4, simple=3))
    assert critic.unreconciled(designer, card) == ["distinctive"]  # simple differs by 1; timeless is reconciled


def test_round_half_up():
    assert [critic.round_half_up(v) for v in (3.0, 3.49, 3.5, 4.5)] == [3, 3, 4, 5]


def prepare(project_root, name: str, fixture: str = "good"):
    folder = install_concept(project_root, fixture, name=name)
    write_passing_audit(project(), "keystone", folder)
    (folder / "scorecard.json").write_text(json.dumps(scorecard()))
    return folder


def run(*args):
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, json.loads(result.stdout)


def test_critic_sheet_letters_the_survivors_in_a_seeded_shuffle_and_writes_the_key(project_root):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    info = sheets.critic_sheet(project(), "keystone", ["01-good", "02-dots"], seed=7, renderer=StubChrome())
    assert info["round"] == 1 and set(info["letters"]) == {"A", "B"} and set(info["letters"].values()) == {"01-good", "02-dots"}
    brand = project_root / "brands" / "keystone"
    key = json.loads((brand / "sheets" / "critic-1.key.json").read_text())
    assert key["letters"] == info["letters"] and key["seed"] == 7 and key["final"] is False
    assert set(key["fingerprints"]) == {"01-good", "02-dots"}
    html = (brand / "sheets" / "critic-1.html").read_text()
    assert "Concept A" in html and "Concept B" in html
    assert "01-good" not in html and "02-dots" not in html and "A ring with a gap" not in html  # no slug, no idea
    assert "/ 50" not in html  # no scores
    other = sheets.critic_sheet(project(), "keystone", ["01-good", "02-dots"], seed=8, renderer=StubChrome())
    assert other["round"] == 2
    assert sorted(other["letters"].values()) == sorted(info["letters"].values())


def test_a_second_critic_sheet_of_the_same_concepts_gets_another_lettering(project_root):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    names = ["01-good", "02-dots"]
    first = sheets.critic_sheet(project(), "keystone", names, renderer=StubChrome())
    # Seed 2 shuffles two concepts as seed 1 does, so the second sheet must step its seed past the round number.
    second = sheets.critic_sheet(project(), "keystone", names, renderer=StubChrome())
    assert first["letters"] != second["letters"]
    key = json.loads(Path(second["key"]).read_text())
    assert key["seed"] == second["seed"] != second["round"] and key["letters"] == second["letters"]
    assert json.loads(Path(first["key"]).read_text())["seed"] == first["seed"] == 1  # the first sheet keeps its default seed


def test_an_explicit_seed_reproduces_a_critic_sheet(project_root):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    names = ["01-good", "02-dots"]
    first = sheets.critic_sheet(project(), "keystone", names, seed=1, renderer=StubChrome())
    again = sheets.critic_sheet(project(), "keystone", names, seed=1, renderer=StubChrome())
    assert again["letters"] == first["letters"] and again["seed"] == first["seed"] == 1
    assert json.loads(Path(again["key"]).read_text())["seed"] == 1


def test_critic_sheet_refuses_an_unvetted_concept_before_chrome(project_root, no_chrome):
    folder = prepare(project_root, "01-good")
    (folder / "scorecard.json").unlink()
    with pytest.raises(CliError, match="scorecard.json is missing"):
        sheets.critic_sheet(project(), "keystone", ["01-good"])
    assert not list((project_root / "brands" / "keystone" / "sheets").glob("critic-*"))


def test_critic_sheet_refuses_a_concept_named_twice_before_chrome(project_root, no_chrome):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    with pytest.raises(CliError, match="01-good is named twice; give each concept once"):
        sheets.critic_sheet(project(), "keystone", ["01-good", "02-dots", "01-good"])
    code, payload = run("sheet", "critic", "keystone", "--concepts", "02-dots,01-good,02-dots")
    assert code == 2 and payload["errors"] == ["02-dots is named twice; give each concept once"]
    assert not list((project_root / "brands" / "keystone" / "sheets").glob("critic-*"))


def test_critic_sheet_for_final_letters_the_final_mark_alone(project_root):
    make_final_brand(project_root)
    info = sheets.critic_sheet(project(), "keystone", [], final=True, renderer=StubChrome())
    assert info["letters"] == {"A": "final"}
    key = json.loads(Path(info["key"]).read_text())  # make_final_brand's own critic runs took the earlier rounds
    assert key["final"] is True and list(key["fingerprints"]) == ["final"]


def test_sheet_critic_cli_needs_concepts_or_final_but_not_both(project_root):
    make_final_brand(project_root)
    code, payload = run("sheet", "critic", "keystone")
    assert code == 2 and payload["errors"] == ["give --concepts <a,b,c> for survivors, or --final for the final mark"]
    code, payload = run("sheet", "critic", "keystone", "--concepts", "01-good", "--final")
    assert code == 2 and payload["errors"] == ["--final takes no --concepts"]


def test_key_needs_a_fingerprint_for_every_lettered_concept():
    with pytest.raises(ValidationError, match="fingerprints missing for 01-k-jaw"):
        critic.Key.model_validate({**KEY, "fingerprints": {"02-arch": "f2"}})


def test_concept_critic_merges_the_passes_into_each_concept_folder(project_root):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    info = sheets.critic_sheet(project(), "keystone", ["01-good", "02-dots"], renderer=StubChrome())
    brand = project_root / "brands" / "keystone"
    winner = next(letter for letter, name in info["letters"].items() if name == "01-good")
    write_pass(brand, 1, 1, info["letters"], prefer=winner, distinctive=3)
    write_pass(brand, 1, 2, info["letters"], prefer=winner, distinctive=4)
    code, payload = run("concept", "critic", "keystone", "--sheet", "1")
    assert code == 0 and payload["passes"] == 2 and set(payload["cards"]) == {"01-good", "02-dots"}
    good = json.loads((brand / "concepts" / "01-good" / "critic.json").read_text())
    assert good["scores"]["distinctive"] == 4 and good["preferred_over"] == ["02-dots"] and good["sheet"] == 1
    dots = json.loads((brand / "concepts" / "02-dots" / "critic.json").read_text())
    assert dots["preferred_over"] == [] and dots["tied_with"] == ["01-good"]


def test_concept_critic_merges_two_sheets_by_their_own_keys(project_root):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    brand = project_root / "brands" / "keystone"
    maps = []
    for distinctive in ({"01-good": 5, "02-dots": 1}, {"01-good": 4, "02-dots": 2}):
        info = sheets.critic_sheet(project(), "keystone", ["01-good", "02-dots"], renderer=StubChrome())
        maps.append(info["letters"])
        winner = next(letter for letter, name in info["letters"].items() if name == "01-good")
        cards = {letter: pass_card(distinctive=distinctive[name]) for letter, name in info["letters"].items()}
        pairs = both_orders("A", "B", winner)
        (brand / "sheets" / f"critic-{info['round']}.pass-1.json").write_text(json.dumps({"cards": cards, "pairs": pairs}))
    assert maps[0] != maps[1]  # the second sheet letters the concepts the other way round
    code, payload = run("concept", "critic", "keystone", "--sheet", "1", "--sheet", "2")
    assert code == 0 and payload["passes"] == 2 and payload["sheets"] == [1, 2]
    good = json.loads((brand / "concepts" / "01-good" / "critic.json").read_text())
    dots = json.loads((brand / "concepts" / "02-dots" / "critic.json").read_text())
    # (5 + 4) / 2 and (1 + 2) / 2, both rounded up; merged by letter, each would be 3
    assert good["scores"]["distinctive"] == 5 and dots["scores"]["distinctive"] == 2
    assert good["preferred_over"] == ["02-dots"] and good["sheet"] == 2 and good["passes"] == 2
    code, payload = run("concept", "critic", "keystone", "--sheet", "1", "--sheet", "1")
    assert code == 2 and payload["errors"] == ["sheet 1 is named twice; give each critic sheet once"]


def test_concept_critic_refuses_a_sheet_without_passes_or_with_other_concepts(project_root):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    brand = project_root / "brands" / "keystone"
    info = sheets.critic_sheet(project(), "keystone", ["01-good", "02-dots"], renderer=StubChrome())
    write_pass(brand, info["round"], 1, info["letters"])
    sheets.critic_sheet(project(), "keystone", ["01-good", "02-dots"], seed=5, renderer=StubChrome())
    code, payload = run("concept", "critic", "keystone", "--sheet", "1", "--sheet", "2")
    assert code == 2 and payload["errors"] == ["no pass files for critic sheet 2; the critic writes sheets/critic-2.pass-1.json"]
    info = sheets.critic_sheet(project(), "keystone", ["01-good"], renderer=StubChrome())
    write_pass(brand, info["round"], 1, info["letters"])
    code, payload = run("concept", "critic", "keystone", "--sheet", "1", "--sheet", "3")
    assert code == 2 and payload["errors"] == ["sheet 3 keys different concepts from sheet 1: 01-good against 01-good, 02-dots"]
    assert not (brand / "concepts" / "01-good" / "critic.json").exists()


def test_concept_critic_refuses_without_passes_and_names_the_file(project_root):
    prepare(project_root, "01-good")
    sheets.critic_sheet(project(), "keystone", ["01-good"], renderer=StubChrome())
    code, payload = run("concept", "critic", "keystone", "--sheet", "1")
    assert code == 2 and "sheets/critic-1.pass-1.json" in payload["errors"][0]
    assert not (project_root / "brands" / "keystone" / "concepts" / "01-good" / "critic.json").exists()
    code, payload = run("concept", "critic", "keystone", "--sheet", "9")
    assert code == 2 and payload["errors"] == ["sheets/critic-9.key.json is missing"]


def test_concept_critic_refuses_a_missing_concept_folder_before_writing_any_card(project_root):
    prepare(project_root, "01-good")
    folder = prepare(project_root, "02-dots", "two_dots")
    info = sheets.critic_sheet(project(), "keystone", ["01-good", "02-dots"], renderer=StubChrome())
    brand = project_root / "brands" / "keystone"
    write_pass(brand, 1, 1, info["letters"])
    shutil.rmtree(folder)
    code, payload = run("concept", "critic", "keystone", "--sheet", "1")
    assert code == 2 and payload["errors"] == ["concepts/02-dots is missing; critic sheet 1 lettered it"]
    assert not (brand / "concepts" / "01-good" / "critic.json").exists()


def test_critic_problems_name_what_is_missing_stale_or_invalid(project_root):
    folder = prepare(project_root, "01-good")
    paths = project()
    assert critic.critic_problems(paths, "keystone", folder) == [
        "01-good/critic.json is missing (run: logomaker sheet critic keystone --concepts 01-good, dispatch the critic, "
        "then logomaker concept critic keystone --sheet N)"]
    critic_run(project_root, ["01-good"])
    assert critic.critic_problems(paths, "keystone", folder) == []
    (folder / "concept.py").write_text((folder / "concept.py").read_text() + "\n# changed\n")
    assert critic.critic_problems(paths, "keystone", folder) == [
        "01-good/critic.json is stale (the concept changed since the critic saw it); re-run: logomaker sheet critic keystone "
        "--concepts 01-good, dispatch the critic, then logomaker concept critic keystone --sheet N"]
    (folder / "critic.json").write_text("{")
    assert critic.critic_problems(paths, "keystone", folder)[0].startswith("01-good/critic.json is not valid JSON")


def test_a_stale_card_names_every_concept_of_its_critic_sheet_and_two_sheets(project_root):
    folder = prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    letters = critic_run(project_root, ["01-good", "02-dots"])
    (folder / "concept.py").write_text((folder / "concept.py").read_text() + "\n# changed\n")
    names = ",".join(letters.values())
    assert critic.critic_problems(project(), "keystone", folder) == [
        f"01-good/critic.json is stale (the concept changed since the critic saw it); re-run: logomaker sheet critic keystone "
        f"--concepts {names} twice, dispatch a critic on each, then logomaker concept critic keystone --sheet N --sheet M"]
    (project_root / "brands" / "keystone" / "sheets" / "critic-1.key.json").unlink()  # no key: the one-concept command
    assert critic.critic_problems(project(), "keystone", folder)[0].endswith(
        "re-run: logomaker sheet critic keystone --concepts 01-good, dispatch the critic, then logomaker concept critic "
        "keystone --sheet N")


def test_vetted_scorecard_needs_a_fresh_critic_and_every_disagreement_reconciled(project_root):
    folder = prepare(project_root, "01-good")
    paths = project()
    with pytest.raises(CliError, match="critic.json is missing"):
        registry.vetted_scorecard(paths, "keystone", folder, "01-good/scorecard.json")
    critic_run(project_root, ["01-good"], distinctive=2, timeless=2)
    with pytest.raises(CliError, match=r"designer and critic disagree by 2 or more on distinctive, timeless; add a reconciled entry "
                                       r"for each to 01-good/scorecard.json"):
        registry.vetted_scorecard(paths, "keystone", folder, "01-good/scorecard.json")
    (folder / "scorecard.json").write_text(json.dumps({**scorecard(), "reconciled": {"distinctive": "stock arches: 2 stands",
                                                                                      "timeless": "no trend shape: 4 stands"}}))
    card, crit = registry.vetted_scorecard(paths, "keystone", folder, "01-good/scorecard.json")
    assert card.total == 40 and crit.total == 36


def test_concept_sheet_refuses_without_the_critic_and_shows_both_totals_with_it(project_root, no_chrome):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    with pytest.raises(CliError, match="concept 01-good: 01-good/critic.json is missing"):
        sheets.concepts_sheet(project(), "keystone", ["01-good", "02-dots"], open_after=False)


def test_concept_sheet_prints_the_critic_total_and_preference(project_root):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    critic_run(project_root, ["01-good", "02-dots"], prefer="01-good", distinctive=5)
    for name in ("01-good", "02-dots"):
        recorded(project_root / "brands" / "keystone" / "concepts" / name)
    sheets.concepts_sheet(project(), "keystone", ["01-good", "02-dots"], renderer=StubChrome(), open_after=False)
    html = (project_root / "brands" / "keystone" / "sheets" / "concepts.html").read_text()
    assert "designer 40 / critic 41 (1 pass)" in html
    assert "critic's order: 01-good &gt; 02-dots" in html or "critic's order: 01-good > 02-dots" in html


def test_preference_line_groups_by_wins():
    cards = {"a": CriticCard.model_validate({**critic_card(), "preferred_over": ["b", "c"]}),
             "b": CriticCard.model_validate({**critic_card(), "preferred_over": [], "tied_with": ["c"]}),
             "c": CriticCard.model_validate({**critic_card(), "preferred_over": [], "tied_with": ["b"]})}
    assert critic.preference_line(cards) == "a > b = c"
    assert critic.preference_line(cards, "keystone") == "a > b = c"  # one critic sheet: the slug is not needed


def test_preference_line_counts_only_wins_over_concepts_on_the_sheet():
    # The critic sheet lettered a, b, c and d; only a and b are shown. a beat c and d, b beat a.
    cards = {"a": CriticCard.model_validate({**critic_card(), "preferred_over": ["c", "d"], "tied_with": ["b"]}),
             "b": CriticCard.model_validate({**critic_card(), "preferred_over": ["a"], "tied_with": ["c", "d"]})}
    assert critic.preference_line(cards) == "b > a"


def test_preference_line_refuses_to_order_cards_from_different_sheets():
    cards = {"02-arch": CriticCard.model_validate({**critic_card(), "preferred_over": ["01-k-jaw"], "sheet": 1}),
             "01-k-jaw": CriticCard.model_validate({**critic_card(), "preferred_over": [], "sheet": 2})}
    assert critic.preference_line(cards, "keystone") == (
        "not comparable; the cards come from different critic sheets (one order: logomaker sheet critic keystone "
        "--concepts 02-arch,01-k-jaw)")


def test_advance_to_refinement_and_package_build_read_the_critic(project_root):
    final = make_final_brand(project_root, phase=None)
    paths = project()
    brand = final.parent
    # make_final_brand runs the critic itself; this test checks the gates, so start without the cards.
    for stale in (brand / "concepts" / "01-good" / "critic.json", final / "critic.json", final / "scorecard.json"):
        stale.unlink(missing_ok=True)
    state = registry.load_state(paths, "keystone")
    while state.phase.value != "concepts":
        state = registry.advance(paths, "keystone", registry.allowed_next(state))
    with pytest.raises(CliError) as err:
        registry.advance(paths, "keystone", registry.allowed_next(state))
    assert any("01-good/critic.json is missing" in m for m in err.value.data["missing"])
    critic_run(project_root, ["01-good"])
    state = registry.advance(paths, "keystone", registry.allowed_next(state))
    assert state.phase.value == "refinement"
    with pytest.raises(CliError) as err:
        registry.advance(paths, "keystone", registry.allowed_next(state))
    assert any("final/critic.json is missing" in m for m in err.value.data["missing"])
    info = sheets.critic_sheet(paths, "keystone", [], final=True, renderer=StubChrome())
    write_pass(brand, info["round"], 1, info["letters"])
    critic.write_cards(paths, "keystone", [info["round"]])
    with pytest.raises(CliError) as err:
        registry.advance(paths, "keystone", registry.allowed_next(state))
    assert any("final/scorecard.json is missing" in m for m in err.value.data["missing"])
    (final / "scorecard.json").write_text(json.dumps(scorecard()))
    assert registry.advance(paths, "keystone", registry.allowed_next(state)).phase.value == "package"


def test_sheet_critic_seed_help_says_an_explicit_seed_reproduces_a_sheet():
    result = CliRunner().invoke(main, ["sheet", "critic", "--help"])
    text = " ".join(result.output.split())
    assert "Shuffle seed, to reproduce an earlier sheet" in text and "leave it out for a critic pass" in text
    assert "use another for the second pass" not in text
