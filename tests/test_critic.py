import pytest
from pydantic import ValidationError

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
