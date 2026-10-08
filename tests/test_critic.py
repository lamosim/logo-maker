import pytest
from pydantic import ValidationError

from logomaker import critic
from logomaker.output import CliError
from logomaker.schemas import CRITERIA, CriticCard, Scorecard
from tests.conftest import scorecard


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
