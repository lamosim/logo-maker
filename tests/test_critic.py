import json
import shutil

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from logomaker import critic, sheets
from logomaker.cli import main
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.schemas import CRITERIA, CriticCard, Scorecard
from tests.conftest import StubChrome, install_concept, make_final_brand, scorecard, write_passing_audit


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


def pass_card(**overrides) -> dict:
    scores = {c: 4 for c in CRITERIA}
    scores.update(overrides)
    return {"scores": scores, "evidence": {"distinctive": "an arch, which stock sites already sell"}}


def both_orders(a: str, b: str, prefer: str) -> list[dict]:
    return [{"first": a, "second": b, "prefer": prefer}, {"first": b, "second": a, "prefer": prefer}]


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
    cards = critic.merge(critic.Key.model_validate(KEY), [first, second])
    arch = cards["02-arch"]
    assert arch.scores["distinctive"] == 4 and arch.scores["simple"] == 5  # 3.5 rounds up, 4.5 rounds up
    assert arch.evidence["distinctive"] == ["an arch, which stock sites already sell"] * 2
    assert arch.passes == 2 and arch.sheet == 1 and arch.fingerprint == "f2"
    assert arch.preferred_over == ["01-k-jaw"] and arch.tied_with == []
    assert cards["01-k-jaw"].preferred_over == [] and cards["01-k-jaw"].tied_with == ["02-arch"]


def test_merge_calls_a_pair_tied_unless_every_verdict_agrees():
    pairs = both_orders("A", "B", "A")[:1] + both_orders("A", "B", "B")[1:]  # A first order, B the other
    one = critic.CriticPass(cards={"A": pass_card(), "B": pass_card()}, pairs=pairs)
    cards = critic.merge(critic.Key.model_validate(KEY), [one])
    assert cards["02-arch"].tied_with == ["01-k-jaw"] and cards["01-k-jaw"].tied_with == ["02-arch"]
    assert cards["02-arch"].passes == 1


def test_merge_refuses_a_pass_whose_letters_do_not_match_the_sheet():
    key = critic.Key.model_validate(KEY)
    with pytest.raises(CliError, match=r"pass 1 scores A, C; the sheet has A, B"):
        critic.merge(key, [critic.CriticPass(cards={"A": pass_card(), "C": pass_card()})])
    with pytest.raises(CliError, match=r"pass 1 judges A and B in one order only; judge every pair in both orders"):
        critic.merge(key, [critic.CriticPass(cards={"A": pass_card(), "B": pass_card()}, pairs=both_orders("A", "B", "A")[:1])])
    with pytest.raises(CliError, match="at least one pass"):
        critic.merge(key, [])


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


def test_critic_sheet_refuses_an_unvetted_concept_before_chrome(project_root, no_chrome):
    folder = prepare(project_root, "01-good")
    (folder / "scorecard.json").unlink()
    with pytest.raises(CliError, match="scorecard.json is missing"):
        sheets.critic_sheet(project(), "keystone", ["01-good"])
    assert not list((project_root / "brands" / "keystone" / "sheets").glob("critic-*"))


def test_critic_sheet_for_final_letters_the_final_mark_alone(project_root):
    make_final_brand(project_root)
    info = sheets.critic_sheet(project(), "keystone", [], final=True, renderer=StubChrome())
    assert info["letters"] == {"A": "final"}
    key = json.loads((project_root / "brands" / "keystone" / "sheets" / "critic-1.key.json").read_text())
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


def write_pass(brand, round_n: int, number: int, letters: dict[str, str], prefer: str | None = None, **scores):
    cards = {letter: pass_card(**scores) for letter in letters}
    pairs = []
    if prefer and len(letters) == 2:
        a, b = sorted(letters)
        pairs = both_orders(a, b, prefer)
    (brand / "sheets" / f"critic-{round_n}.pass-{number}.json").write_text(json.dumps({"cards": cards, "pairs": pairs}))


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
