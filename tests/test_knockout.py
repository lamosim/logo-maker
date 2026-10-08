import pytest
from pydantic import ValidationError

from logomaker.schemas import ImageSearch, Knockout


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
