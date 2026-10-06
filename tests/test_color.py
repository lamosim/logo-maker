import json
import math

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from logomaker import color
from logomaker.cli import main


def test_normalize_and_info():
    assert color.normalize_hex("#ABC") == "#aabbcc"
    i = color.info("#1a5fb4")
    assert i["hex"] == "#1a5fb4" and i["rgb"] == [26, 95, 180]
    assert math.isclose(i["oklch"][0], 0.492, abs_tol=0.01)
    assert math.isclose(i["cmyk"][3], 29, abs_tol=1) and math.isclose(i["cmyk"][0], 86, abs_tol=1)
    assert 0 < i["luminance"] < 0.2


def test_wcag_and_apca_known_values():
    assert math.isclose(color.wcag_contrast("#1a5fb4", "#ffffff"), 6.29, abs_tol=0.02)
    assert math.isclose(color.apca_lc("#888888", "#ffffff"), 63.06, abs_tol=0.5)
    assert math.isclose(color.apca_lc("#ffffff", "#888888"), -68.54, abs_tol=0.5)
    assert math.isclose(color.apca_lc("#000000", "#aaaaaa"), 58.15, abs_tol=0.5)
    assert math.isclose(color.apca_lc("#112233", "#ddeeff"), 91.67, abs_tol=0.5)
    assert math.isclose(color.apca_lc("#112233", "#444444"), 8.32, abs_tol=0.5)
    assert color.apca_lc("#777777", "#777777") == 0.0


def test_cvd_simulation():
    for kind in color.CVD_KINDS:
        out = color.simulate_cvd("#e8572a", kind)
        assert out.startswith("#") and len(out) == 7
    gray = color.simulate_cvd("#e8572a", "achroma")
    assert gray[1:3] == gray[3:5] == gray[5:7]
    assert color.simulate_cvd("#e8572a", "deutan") != "#e8572a"


def test_ramp_is_monotonic_in_lightness():
    steps = color.ramp("#e8572a", steps=9)
    assert len(steps) == 9 and all(len(s) == 7 for s in steps)
    lightness = [color.info(s)["oklch"][0] for s in steps]
    assert all(a > b for a, b in zip(lightness, lightness[1:]))


def good_tokens() -> dict:
    return {
        "colors": {
            "ember": {"name": "Ember", "hex": "#e8572a"},
            "coal": {"name": "Coal", "hex": "#1f1b18"},
            "paper": {"name": "Paper", "hex": "#ffffff"},
            "ember-light": {"name": "Ember Light", "hex": "#ff9a6e"},
        },
        "roles": {"light": {"primary": "ember", "ink": "coal"}, "dark": {"primary": "ember-light", "ink": "paper"}},
        "paper": {"light": "paper", "dark": "coal"},
    }


def test_tokens_validation_and_palettes():
    t = color.Tokens.model_validate(good_tokens())
    assert t.palette("light") == {"primary": "#e8572a", "ink": "#1f1b18", "paper": "#ffffff"}
    assert t.palette("dark")["paper"] == "#1f1b18"
    bad = good_tokens()
    bad["roles"]["light"]["primary"] = "missing"
    with pytest.raises(ValidationError):
        color.Tokens.model_validate(bad)
    bad = good_tokens()
    del bad["roles"]["dark"]["ink"]
    with pytest.raises(ValidationError):
        color.Tokens.model_validate(bad)
    enriched = color.enrich_tokens(t)
    assert enriched.colors["ember"].rgb == [232, 87, 42] and len(enriched.colors["ember"].oklch) == 3


def test_check_tokens_passes_and_fails():
    result = color.check_tokens(color.Tokens.model_validate(good_tokens()))
    assert result.ok, result.failures
    rows = {(r.context, r.role): r for r in result.contrast}
    assert rows[("light", "ink")].wcag > 4.5 and rows[("light", "primary")].ok
    assert result.palettes["dark"]["ink"] == "#ffffff"
    bad = good_tokens()
    bad["colors"]["coal"]["hex"] = "#777777"
    result = color.check_tokens(color.Tokens.model_validate(bad))
    assert not result.ok and any("ink" in f and "light" in f for f in result.failures)


def test_color_cli(tmp_path):
    runner = CliRunner()
    payload = json.loads(runner.invoke(main, ["color", "info", "#1a5fb4"]).stdout)
    assert payload["ok"] and payload["rgb"] == [26, 95, 180]
    payload = json.loads(runner.invoke(main, ["color", "ramp", "#1a5fb4", "--steps", "5"]).stdout)
    assert len(payload["ramp"]) == 5
    tokens = tmp_path / "tokens.json"
    tokens.write_text(json.dumps(good_tokens()))
    result = runner.invoke(main, ["color", "check", str(tokens)])
    assert result.exit_code == 0 and json.loads(result.stdout)["ok"]
    bad = good_tokens()
    bad["colors"]["coal"]["hex"] = "#777777"
    tokens.write_text(json.dumps(bad))
    result = runner.invoke(main, ["color", "check", str(tokens)])
    assert result.exit_code == 2 and not json.loads(result.stdout)["ok"]
