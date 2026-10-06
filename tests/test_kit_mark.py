import math

import pytest

from logomaker.kit.mark import Composite, Mark, fill_for
from logomaker.kit.ops import subtract
from logomaker.kit.primitives import circle, rect
from logomaker.kit.text import text


def good_mark(project_root, **kw):
    return Mark(symbol=circle(0, 0, 100), wordmark=text("Good", "Fira Code", weight=600, cap_height=180), **kw)


def test_horizontal_layout_uses_cap_height_as_gap(project_root):
    m = good_mark(project_root)
    assert m.x_unit == 180
    placed = {p.name: p for p in m.layout()}
    assert math.isclose(placed["symbol"].shape.bounds.cx, 0, abs_tol=0.01)
    assert math.isclose(placed["wordmark"].shape.bounds.x0, 100 + 180, abs_tol=0.01)
    assert math.isclose(placed["wordmark"].shape.bounds.cy, 0, abs_tol=0.01)


def test_stacked_and_single_lockups(project_root):
    m = good_mark(project_root, lockup="stacked")
    placed = {p.name: p for p in m.layout()}
    assert math.isclose(placed["wordmark"].shape.bounds.y1, -100 - 180, abs_tol=0.01)
    assert math.isclose(placed["wordmark"].shape.bounds.cx, 0, abs_tol=0.01)
    assert [p.name for p in m.with_lockup("symbol").layout()] == ["symbol"]
    assert [p.name for p in m.with_lockup("wordmark").layout()] == ["wordmark"]
    assert m.without_wordmark().lockup == "symbol" and m.without_wordmark().wordmark is None


def test_a_notched_wordmark_keeps_its_metrics_in_the_mark(project_root):
    word = text("Good", "Fira Code", weight=600, cap_height=180)
    m = Mark(symbol=circle(0, 0, 100), wordmark=subtract(word, rect(0, 60, 40, 20)))
    assert m.x_unit == 180
    assert m.geometry()["wordmark"] == {"cap_height": 180, "x_height": round(word.x_height, 3), "advance": round(word.advance, 3), "font": word.font}


def test_x_unit_without_wordmark_is_fifth_of_symbol_height():
    assert Mark(symbol=circle(0, 0, 100)).x_unit == 40


def test_baseline_alignment(project_root):
    m = good_mark(project_root, align="baseline")
    placed = {p.name: p for p in m.layout()}
    assert math.isclose(placed["wordmark"].shape.bounds.y0, -100, abs_tol=4.0)  # round letters overshoot the baseline slightly


def test_svg_structure_and_variants(project_root):
    m = good_mark(project_root)
    svg = m.to_svg("black")
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="')
    assert ' width=' not in svg and "<text" not in svg
    assert '<g id="symbol">' in svg and '<g id="wordmark">' in svg
    assert 'fill="#000000"' in svg and 'fill-rule="nonzero"' in svg
    assert 'fill="#ffffff"' in m.to_svg("white")
    assert 'fill="currentColor"' in m.to_svg("mono")
    assert m.to_svg("black") == m.to_svg("black")  # deterministic


def test_color_variants_need_a_palette(project_root):
    m = good_mark(project_root)
    with pytest.raises(ValueError):
        m.to_svg("color")
    svg = m.to_svg("color", palette={"primary": "#e8572a", "ink": "#1f1b18"})
    assert 'fill="#e8572a"' in svg and 'fill="#1f1b18"' in svg
    dark = m.to_svg("color", palette={"primary": "#e8572a", "ink": "#1f1b18"}, dark_palette={"primary": "#ff7a45", "ink": "#ffffff"})
    assert "prefers-color-scheme: dark" in dark and ".r-primary{fill:#ff7a45}" in dark and 'class="r-ink"' in dark
    assert fill_for("accent", "mono", None) == "currentColor"


def test_padding_and_viewbox():
    m = Mark(symbol=rect(0, 0, 100, 50))
    assert 'viewBox="-50 -25 100 50"' in m.to_svg("black")
    assert 'viewBox="-60 -35 120 70"' in m.to_svg("black", padding=10)


def test_composite_roles_and_geometry():
    sym = Composite([(circle(0, 0, 100), "primary"), (rect(-20, -20, 40, 40), "secondary")])
    m = Mark(symbol=sym)
    svg = m.to_svg("color", palette={"primary": "#111111", "secondary": "#222222"})
    assert svg.count("<path") == 2 and 'fill="#222222"' in svg
    geo = m.geometry()
    assert geo["lockup"] == "horizontal" and [p["name"] for p in geo["parts"]] == ["symbol", "symbol-2"]
    assert geo["parts"][1]["anchors"] == 4 and len(geo["parts"][1]["straight_segments"]) == 4
    assert geo["parts"][1]["straight_segments"][0]["angle"] in (0.0, 90.0)
    assert geo["roles"] == ["primary", "secondary"]


def test_paper_is_not_a_part_role():
    message = "'paper' is the background role; knock shapes out with subtract() instead"
    with pytest.raises(ValueError) as err:
        Composite([(circle(0, 0, 100), "primary"), (circle(0, 0, 50), "paper")])
    assert str(err.value) == message
    for roles in ({"symbol": "paper"}, {"wordmark": "paper"}):
        with pytest.raises(ValueError) as err:
            Mark(symbol=circle(0, 0, 100), roles=roles)
        assert str(err.value) == message


def test_empty_symbol_is_rejected():
    from logomaker.kit.shape import Shape

    with pytest.raises(ValueError):
        Mark(symbol=Shape.empty())
    with pytest.raises(ValueError):
        Mark()
    with pytest.raises(ValueError, match="empty"):
        Composite([(circle(0, 0, 100), "primary"), (Shape.empty(), "secondary")])
    with pytest.raises(ValueError, match="empty"):
        Mark(symbol=circle(0, 0, 100), tagline=Shape.empty())


def test_tagline_follows_the_wordmark(project_root):
    m = good_mark(project_root, tagline=text("tag", "Fira Code", cap_height=60))
    placed = {p.name: p.shape.bounds for p in m.layout()}
    assert math.isclose(placed["tagline"].x0, placed["wordmark"].x0, abs_tol=0.01)
    assert math.isclose(placed["tagline"].y1, placed["wordmark"].y0 - 180 / 2, abs_tol=0.01)  # gap defaults to x_unit, the cap height
    stacked = {p.name: p.shape.bounds for p in m.with_lockup("stacked").layout()}
    assert math.isclose(stacked["tagline"].cx, stacked["wordmark"].cx, abs_tol=0.01)


def test_reverse_fills_from_the_given_palette(project_root):
    svg = good_mark(project_root).to_svg("reverse", palette={"primary": "#ff7a45", "ink": "#f5efe6"})
    assert 'fill="#ff7a45"' in svg and 'fill="#f5efe6"' in svg


def test_palette_missing_a_role_names_it(project_root):
    with pytest.raises(ValueError, match="ink"):
        good_mark(project_root).to_svg("color", palette={"primary": "#111111"})
