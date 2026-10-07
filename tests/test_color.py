import json
import math

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from logomaker import color
from logomaker.cli import main
from tests.conftest import good_tokens


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



def tokens_with(**light_roles: str) -> color.Tokens:
    """good_tokens() with each given light-context role pointed at a new colour."""
    data = good_tokens()
    for role, hex_value in light_roles.items():
        data["colors"][f"test-{role}"] = {"name": f"Test {role}", "hex": hex_value}
        data["roles"]["light"][role] = f"test-{role}"
    return color.Tokens.model_validate(data)


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


def test_text_thresholds_apply_to_the_text_roles_given():
    tokens = color.Tokens.model_validate(good_tokens())
    rows = {(r.context, r.role): r for r in color.check_tokens(tokens).contrast}
    assert (rows[("light", "ink")].required_wcag, rows[("light", "primary")].required_wcag) == (4.5, 3.0)  # default: ink is the text
    result = color.check_tokens(tokens, text_roles=("primary",))
    rows = {(r.context, r.role): r for r in result.contrast}
    assert (rows[("light", "primary")].required_wcag, rows[("light", "primary")].required_apca) == (4.5, 60.0)
    assert (rows[("dark", "primary")].required_wcag, rows[("light", "ink")].required_wcag) == (4.5, 3.0)
    assert not result.ok
    assert any(f.startswith("light: role primary (#e8572a) on paper #ffffff") and "need 4.5" in f for f in result.failures)


def test_contrast_thresholds_use_raw_values_and_rows_show_floored_ones():
    # True WCAG ratios 4.49968 and 2.99967 round up to their thresholds; they must still fail, and show below them.
    for role, hex_value, shown in (("ink", "#007bc8", 4.499), ("primary", "#00a5af", 2.999)):
        result = color.check_tokens(tokens_with(**{role: hex_value}))
        row = {(r.context, r.role): r for r in result.contrast}[("light", role)]
        assert not result.ok and not row.ok and row.wcag == shown
        assert any(f"role {role} ({hex_value})" in f and f"WCAG {shown} " in f for f in result.failures)
    # APCA is shown truncated by magnitude, keeping its sign.
    rows = {(r.context, r.role): r for r in color.check_tokens(color.Tokens.model_validate(good_tokens())).contrast}
    shown, raw = rows[("dark", "ink")].apca, color.apca_lc("#ffffff", "#1f1b18")  # raw -106.338: shown -106.33, not -106.34
    assert shown < 0 and abs(shown) <= abs(raw) < abs(shown) + 0.01


def test_cvd_pair_just_under_threshold_warns():
    result = color.check_tokens(tokens_with(primary="#757575", secondary="#939393"))  # simulated contrast 1.49973
    pair = [r for r in result.cvd if r.context == "light" and (r.a, r.b) == ("primary", "secondary")]
    assert len(pair) == len(color.CVD_KINDS) and all(not r.ok and r.contrast == 1.499 for r in pair)
    warned = [w for w in result.warnings if w.startswith("cvd ") and "light roles primary and secondary" in w]
    assert len(warned) == len(color.CVD_KINDS) and all(w.endswith("contrast 1.499") for w in warned)


def test_grayscale_check_compares_oklch_lightness():
    assert not [w for w in color.check_tokens(color.Tokens.model_validate(good_tokens())).warnings if w.startswith("grayscale:")]
    # Blue on near-black differs by only 0.106 in linear luminance but by 0.267 in OKLCH lightness: no warning.
    assert not [w for w in color.check_tokens(tokens_with(primary="#1a5fb4")).warnings if w.startswith("grayscale:")]
    near = [w for w in color.check_tokens(tokens_with(primary="#808080", secondary="#8a8a8a")).warnings if w.startswith("grayscale:")]
    assert len(near) == 1 and "light roles primary and secondary" in near[0] and "lightness" in near[0]


def test_warning_prefixes_are_cvd_or_grayscale():
    result = color.check_tokens(tokens_with(primary="#808080", secondary="#8a8a8a"))
    cvd = [w for w in result.warnings if w.startswith("cvd ")]
    gray = [w for w in result.warnings if w.startswith("grayscale:")]
    assert cvd and gray and len(cvd) + len(gray) == len(result.warnings)
    assert len(cvd) == sum(not r.ok for r in result.cvd)


def test_paper_is_reserved_not_a_role():
    for context in ("light", "dark"):
        bad = good_tokens()
        bad["roles"][context]["paper"] = "paper"
        with pytest.raises(ValidationError, match="paper") as err:
            color.Tokens.model_validate(bad)
        assert f"roles.{context} must not define 'paper'" in str(err.value)


def test_info_fits_out_of_gamut_colours():
    i = color.info("oklch(0.7 0.4 30)")
    fitted = color.Color("oklch(0.7 0.4 30)").convert("srgb").fit("srgb")
    assert all(0 <= v <= 255 for v in i["rgb"]) and all(0 <= v <= 100 for v in i["cmyk"])
    assert i["hex"] == fitted.to_string(hex=True, alpha=False).lower() == "#{:02x}{:02x}{:02x}".format(*i["rgb"])


def test_bad_tokens_file_is_a_clean_cli_error(tmp_path):
    tokens = tmp_path / "tokens.json"
    for content, error in ((b"{}", "is invalid: colors: "), (b"not json", "is invalid: root: "), (b"\xff\xfe", "is not valid JSON: ")):
        tokens.write_bytes(content)
        result = CliRunner().invoke(main, ["color", "check", str(tokens)])
        payload = json.loads(result.stdout)
        assert result.exit_code == 2 and not payload["ok"] and "traceback" not in payload
        assert payload["errors"][0].startswith(f"{tokens} {error}")


def test_ramp_needs_at_least_one_step():
    result = CliRunner().invoke(main, ["color", "ramp", "#1a5fb4", "--steps", "0"])
    assert result.exit_code == 2 and not json.loads(result.stdout)["ok"]
