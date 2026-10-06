import math
import shutil

import pytest
import skia

from logomaker.kit.ops import intersect, mirror_x, offset, rotate, scale, stroke, subtract, translate, union, xor
from logomaker.kit.primitives import rect
from logomaker.kit.text import TextShape, glyph, text
from logomaker.output import CliError

FIRA_CAP = 1374  # OS/2 sCapHeight of the fixture font
FIRA_UPEM = 1950
FIRA_ADVANCE = 1200  # monospace advance in font units


def test_cap_height_scales_the_glyphs(project_root):
    h = text("H", "Fira Code", cap_height=200)
    assert isinstance(h, TextShape)
    assert math.isclose(h.bounds.h, 200, abs_tol=1.0)
    assert math.isclose(h.bounds.y0, 0, abs_tol=1.0)  # baseline at y = 0
    assert math.isclose(h.cap_height, 200) and math.isclose(h.x_height, 1050 / FIRA_CAP * 200, rel_tol=0.01)


def test_advance_tracking_and_kern_overrides(project_root):
    # 300 is the fixture's default instance: OS/2 sCapHeight (1374) equals the drawn H, so these constants stay exact
    scale = 200 / FIRA_CAP
    plain = text("ABC", "Fira Code", weight=300, cap_height=200)
    assert math.isclose(plain.advance, 3 * FIRA_ADVANCE * scale, rel_tol=1e-3)
    assert len(plain.glyph_bounds) == 3
    tracked = text("AB", "Fira Code", weight=300, cap_height=200, tracking=100)
    base = text("AB", "Fira Code", weight=300, cap_height=200)
    assert math.isclose(tracked.advance - base.advance, 100 / 1000 * FIRA_UPEM * scale, rel_tol=1e-3)
    kerned = text("AB", "Fira Code", weight=300, cap_height=200, kern={"AB": -200})
    assert math.isclose(base.advance - kerned.advance, 200 / 1000 * FIRA_UPEM * scale, rel_tol=1e-3)
    assert kerned.glyph_bounds[1].x0 < base.glyph_bounds[1].x0


def test_features_change_shapes(project_root):
    with_calt = text("->", "Fira Code", features=("calt",))
    without = text("->", "Fira Code", features=())
    assert with_calt.to_path_data() != without.to_path_data()


def test_variable_weight_changes_stem_width(project_root):
    light = glyph("H", "Fira Code", weight=300, cap_height=200)
    bold = glyph("H", "Fira Code", weight=700, cap_height=200)
    assert bold.area > light.area * 1.3
    assert math.isclose(bold.bounds.h, 200, abs_tol=0.05)  # cap height measured on the drawn instance
    x_height = text("x", "Fira Code", weight=700).x_height
    assert math.isclose(glyph("x", "Fira Code", weight=700).bounds.y1, x_height, abs_tol=1e-3)  # and so is the x-height


def test_missing_family_exits_3(project_root):
    with pytest.raises(CliError) as exc:
        text("Sora", "Sora")
    assert exc.value.code == 3 and "run: logomaker fonts fetch Sora" in str(exc.value)


def test_transform_keeps_geometry(project_root):
    t = text("Go", "Fira Code", cap_height=100)
    moved = translate(t, 50, 0)
    assert math.isclose(moved.bounds.x0, t.bounds.x0 + 50, abs_tol=1e-3)  # skia stores points as float32


def test_booleans_keep_the_first_operands_text_metrics(project_root):
    word = text("Good", "Fira Code", weight=600, cap_height=180)
    notch = rect(0, 60, 40, 20)
    for result in (subtract(word, notch), union(word, notch), intersect(word, notch), xor(word, notch), offset(word, 4), stroke(word, 4)):
        assert isinstance(result, TextShape), result
        assert (result.cap_height, result.x_height, result.advance, result.font) == (word.cap_height, word.x_height, word.advance, word.font)
    notched = subtract(word, notch)
    assert notched.area < word.area and notched.glyph_bounds == word.glyph_bounds  # a notch does not move the letters
    assert not isinstance(subtract(notch, word), TextShape)  # only the first operand carries its metrics


def test_transforms_scale_text_metrics(project_root):
    word = text("Good", "Fira Code", weight=600, cap_height=180)
    doubled = scale(word, 2)
    assert isinstance(doubled, TextShape) and doubled.font == word.font
    assert math.isclose(doubled.cap_height, 360) and math.isclose(doubled.x_height, 2 * word.x_height) and math.isclose(doubled.advance, 2 * word.advance)
    first, scaled = word.glyph_bounds[0], doubled.glyph_bounds[0]
    assert all(math.isclose(s, 2 * v, abs_tol=1e-3) for s, v in zip((scaled.x0, scaled.y0, scaled.x1, scaled.y1), (first.x0, first.y0, first.x1, first.y1)))
    turned = rotate(mirror_x(translate(word, 10, 5)), 30)  # moves, reflections and rotations keep the size
    assert isinstance(turned, TextShape)  # skia matrices are float32, so a rotation's determinant is 1 to about 1e-8
    assert math.isclose(turned.cap_height, 180, rel_tol=1e-6) and math.isclose(turned.x_height, word.x_height, rel_tol=1e-6)


def test_counters_stay_open_under_nonzero_fill(project_root):
    # The fixture's zero has a slash that splits its counter in two; pathops winds one half like the outline.
    zero = glyph("0", "Fira Code", cap_height=200)
    nonzero, even_odd = skia.Path(zero.path), skia.Path(zero.path)
    nonzero.setFillType(skia.PathFillType.kWinding)  # the SVG's fill-rule="nonzero"
    even_odd.setFillType(skia.PathFillType.kEvenOdd)  # how pathops means its overlap-free output
    b = zero.bounds

    def at(i, j):  # point (i, j) of a 51 x 51 probe grid over the glyph's bounds
        return b.x0 + b.w * i / 50, b.y0 + b.h * j / 50

    grid = [at(i, j) for i in range(51) for j in range(51)]
    assert [nonzero.contains(x, y) for x, y in grid] == [even_odd.contains(x, y) for x, y in grid]
    assert not nonzero.contains(*at(31, 16))  # deep inside the half-counter pathops wound like the outline
    assert nonzero.contains(*at(36, 42))  # where the slash's end overlaps the ring


def test_out_of_range_weights_take_the_nearest_axis_weight(project_root):
    # the fixture's wght axis spans 300-700
    assert glyph("H", "Fira Code", weight=100).to_path_data() == glyph("H", "Fira Code", weight=300).to_path_data()
    assert glyph("H", "Fira Code", weight=900).to_path_data() == glyph("H", "Fira Code", weight=700).to_path_data()
    assert glyph("H", "Fira Code", weight=900).font == "Fira Code 700"
    assert glyph("H", "Fira Code", weight=100).font == "Fira Code 300"


def test_empty_string_gives_an_empty_shape(project_root):
    empty = text("", "Fira Code")
    assert empty.is_empty and empty.advance == 0 and empty.glyph_bounds == []


def test_tracking_stays_out_of_clusters(project_root):
    plain = text("n\u0308", "Fira Code")  # n + combining diaeresis: one cluster, the mark positioned over the n
    tracked = text("n\u0308", "Fira Code", tracking=200)
    assert tracked.advance == plain.advance and tracked.glyph_bounds[1] == plain.glyph_bounds[1]


def test_missing_glyphs_are_an_error(project_root):
    with pytest.raises(CliError) as exc:
        text("A中", "Fira Code")
    assert exc.value.code == 2 and "中" in str(exc.value)


def test_static_file_uses_os2_metrics_and_its_own_weight(project_root):
    fonts = project_root / "assets" / "fonts"
    (fonts / "fakestatic").mkdir()
    # A static file name: font_path reports static Bold 700, although the file itself still has an fvar.
    shutil.copy(fonts / "firacode" / "FiraCode[wght].ttf", fonts / "fakestatic" / "FakeStatic-Bold.ttf")
    h = text("H", "Fake Static", weight=650)
    assert h.font == "Fake Static 700" and math.isclose(h.bounds.h, 200, abs_tol=1.0)
