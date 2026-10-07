import hashlib
import math
import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from logomaker import export
from logomaker.kit.concept import pick_output, size_tier
from logomaker.kit.mark import ROLES
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.render import fit_size, svg_size
from tests.conftest import FIXTURES, StubRenderer, make_final_brand, requires_chrome, write_passing_audit
from tests.test_export_core import build, opened

PLATFORM = ["apple", "android", "social", "banners", "previews", "commerce"]
LAYERS = ["app-icon-layers/background.svg", "app-icon-layers/foreground.svg", "android/ic_launcher_foreground.svg",
          "android/ic_launcher_background.svg", "android/ic_launcher_monochrome.svg"]
# Each raster the six groups write, in order: its size (None: the art's own, for the Stripe logo), the output that draws its
# art, the art's palette ("tile": every role in light paper, for the primary tile; "light") and the box the art is fitted to:
# 60% of an app icon, 56% of an avatar, 62% of the Stripe and GBP icons, 60% of a banner's or preview's safe area, the
# whole email and Shopify canvas, and 1024 px wide at any height for the Stripe logo.
RASTERS = [
    ("ios-app-icon-1024.png", (1024, 1024), "full-symbol", "tile", (614, 614)),
    ("android/mipmap-mdpi/ic_launcher.png", (48, 48), "small", "tile", (29, 29)),
    ("android/mipmap-hdpi/ic_launcher.png", (72, 72), "small", "tile", (43, 43)),
    ("android/mipmap-xhdpi/ic_launcher.png", (96, 96), "full-symbol", "tile", (58, 58)),
    ("android/mipmap-xxhdpi/ic_launcher.png", (144, 144), "full-symbol", "tile", (86, 86)),
    ("android/mipmap-xxxhdpi/ic_launcher.png", (192, 192), "full-symbol", "tile", (115, 115)),
    ("play-store-icon-512.png", (512, 512), "full-symbol", "tile", (307, 307)),
    ("avatar-320.png", (320, 320), "compact", "light", (179, 179)),
    ("avatar-400.png", (400, 400), "compact", "light", (224, 224)),
    ("avatar-512.png", (512, 512), "compact", "light", (287, 287)),
    ("avatar-720.png", (720, 720), "compact", "light", (403, 403)),
    ("avatar-800.png", (800, 800), "compact", "light", (448, 448)),
    ("banner-x-1500x500.png", (1500, 500), "full-horizontal", "light", (900, 228)),
    ("banner-linkedin-personal-1584x396.png", (1584, 396), "full-horizontal", "light", (950, 238)),
    ("banner-linkedin-page-1512x256.png", (1512, 256), "full-horizontal", "light", (907, 154)),
    ("banner-youtube-2560x1440.png", (2560, 1440), "full-horizontal", "light", (741, 203)),
    ("banner-facebook-851x315.png", (851, 315), "full-horizontal", "light", (511, 189)),
    ("banner-bluesky-1500x500.png", (1500, 500), "full-horizontal", "light", (900, 300)),
    ("og-image-1200x630.png", (1200, 630), "full-horizontal", "light", (720, 378)),
    ("x-card-1200x600.png", (1200, 600), "full-horizontal", "light", (720, 360)),
    ("stripe-icon-512.png", (512, 512), "full-symbol", "light", (317, 317)),
    ("gbp-logo-720.png", (720, 720), "full-symbol", "light", (446, 446)),
    ("email-signature-logo@2x.png", (400, 100), "full-horizontal", "light", (400, 100)),
    ("shopify-header-logo@2x.png", (800, 200), "full-horizontal", "light", (800, 200)),
    ("stripe-logo.png", None, "full-horizontal", "light", (1024, math.inf)),
]
PLATFORM_FILES = [RASTERS[0][0], *LAYERS, *(name for name, *_ in RASTERS[1:])]


def use_concept(final: Path, fixture: str) -> None:
    """final/ drawn by tests/fixtures/concepts/<fixture>, with a passing audit."""
    shutil.copy(FIXTURES / "concepts" / fixture / "concept.py", final / "concept.py")
    write_passing_audit(project(), "keystone", final)


def on_tile(light: dict[str, str]) -> dict[str, str]:
    """The palette of art on the primary tile: every role, paper too, in the light paper colour."""
    return {role: light["paper"] for role in (*ROLES, "paper")}


def viewbox(svg: str) -> list[float]:
    return [float(v) for v in svg.split('viewBox="')[1].split('"')[0].split()]


def ink_box(path: Path, ink: tuple[int, int, int] | None = None) -> tuple[int, int, int, int]:
    """(x0, y0, x1, y1) around the pixels of the image at `path` that are `ink`, or by default that are not white paper."""
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"))
    ys, xs = np.nonzero((rgb == ink).all(axis=2) if ink else (rgb != 255).any(axis=2))
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def test_platform_groups_without_chrome(project_root):
    make_final_brand(project_root)
    stub = StubRenderer()
    builder, manifest = build(PLATFORM, stub)
    pkg = project_root / "brands" / "keystone" / "package"
    assert [e.path for e in manifest.files] == PLATFORM_FILES and len(PLATFORM_FILES) == 30
    assert sorted(p.relative_to(pkg).as_posix() for p in pkg.rglob("*") if p.is_file()) == sorted([*PLATFORM_FILES, "manifest.json"])
    assert manifest.warnings == [] and manifest.skipped == {}
    entries = {e.path: e for e in manifest.files}
    for entry in manifest.files:
        raw = (pkg / entry.path).read_bytes()
        assert (entry.sha256, entry.bytes) == (hashlib.sha256(raw).hexdigest(), len(raw))
    palettes = {"tile": on_tile(builder.light), "light": builder.light}
    for (name, size, output, palette, box), (svg, width, height, background) in zip(RASTERS, stub.calls, strict=True):
        assert svg == builder.outputs[output].to_svg("color", palette=palettes[palette]), name
        assert (width, height) == fit_size(svg, *box) and background is None, name
        image = opened(pkg / name)
        assert (entries[name].width, entries[name].height) == (size or (width, height)) == image.size, name
        x0, y0, x1, y1 = ink_box(pkg / name, stub.ink[:3])  # the stub inks the middle half of the art: the art is centred
        assert abs(x0 + x1 - image.width) <= 3 and abs(y0 + y1 - image.height) <= 3, name
    assert opened(pkg / "ios-app-icon-1024.png").mode == "RGB"  # the App Store refuses an icon with an alpha channel
    assert {opened(pkg / name).mode for name, *_ in RASTERS[1:]} == {"RGBA"}
    primary = builder.light["primary"]
    for name, side in (("app-icon-layers/background.svg", 1024), ("android/ic_launcher_background.svg", 1080)):
        assert (pkg / name).read_text() == (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side} {side}">'
                                            f'<path d="M0 0H{side}V{side}H0Z" fill="{primary}"/></svg>')  # paths only
    symbol = builder.outputs["full-symbol"]  # the tier for 1024 px (Apple) and 108 px (Android)
    art = symbol.to_svg("color", palette=palettes["tile"])
    assert (pkg / "app-icon-layers/foreground.svg").read_text() == export.square_viewbox(art, 0.6)
    assert (pkg / "android/ic_launcher_foreground.svg").read_text() == export.circle_viewbox(art, 330 / 1080)
    assert (pkg / "android/ic_launcher_monochrome.svg").read_text() == export.circle_viewbox(symbol.to_svg("black"), 330 / 1080)
    _, _, art_w, art_h = viewbox(art)
    for name in ("android/ic_launcher_foreground.svg", "android/ic_launcher_monochrome.svg"):
        side = viewbox((pkg / name).read_text())[2]  # the adaptive icon's 108 dp, as 1080 units
        assert math.hypot(art_w, art_h) / 2 * 1080 / side <= 330 + 1e-9, name  # the art's corners inside the 66 dp safe circle
        assert "inside the 66 dp safe circle" in entries[name].purpose and "1080" not in entries[name].purpose, name


def test_adaptive_icon_art_fits_the_safe_circle_even_when_square():
    square = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M0 0H100V100H0Z"/></svg>'  # the worst case
    side = viewbox(export.circle_viewbox(square, export.ADAPTIVE_RADIUS / 1080))[2]
    assert math.hypot(100, 100) / 2 * 1080 / side <= 330 + 1e-9  # its corners inside the 66 dp (660-unit) circle of 108 dp (1080)
    assert 100 * 1080 / side == pytest.approx(466.7, abs=0.05)  # a square box can span only 660 / √2 of the 1080


def test_a_wide_adaptive_icon_layer_grows_to_its_own_half_diagonal():
    wide = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-150 -50 300 100"><path d="M-150 -50H150V50H-150Z"/></svg>'
    x, y, side, _ = viewbox(export.circle_viewbox(wide, export.ADAPTIVE_RADIUS / 1080))
    assert math.hypot(300, 100) / 2 * 1080 / side == pytest.approx(330, abs=0.01)  # its corners on the safe circle
    assert 300 * 1080 / side > 600 > 466  # far wider than the square worst case would allow it
    assert (x + side / 2, y + side / 2) == pytest.approx((0, 0), abs=0.01)  # centred, to the viewBox's two decimals


@pytest.mark.parametrize(("fixture", "drawn", "warnings"), [
    ("good", "compact", []),
    ("tall_frame", "full-symbol", []),  # no compact tier: the tier for each avatar's size
    ("wordmark_only", "full-lockup", ["mark falls back to full-lockup (the concept has no full-symbol)"]),
])
def test_avatars_draw_the_compact_tier_else_the_tier_for_their_size(project_root, fixture, drawn, warnings):
    use_concept(make_final_brand(project_root), fixture)
    stub = StubRenderer()
    builder, manifest = build(["social"], stub)
    art = builder.outputs[drawn].to_svg("color", palette=builder.light)
    assert [call[0] for call in stub.calls] == [art] * 5
    assert manifest.warnings == warnings and len(manifest.files) == 5


def test_a_wordmark_only_brand_builds_every_platform_file_from_its_lockup_with_warnings(project_root):
    make_final_brand(project_root, wordmark_only=True)
    stub = StubRenderer()
    builder, manifest = build(PLATFORM, stub)
    assert [e.path for e in manifest.files] == PLATFORM_FILES and manifest.skipped == {}
    assert manifest.warnings == ["mark falls back to full-lockup (the concept has no full-symbol)",
                                 "small falls back to full-lockup (draw a dedicated tier for better small sizes)",
                                 "horizontal falls back to full-lockup (the concept has no full-horizontal)"]
    assert stub.calls[0][0] == builder.outputs["full-lockup"].to_svg("color", palette=on_tile(builder.light))  # the iOS icon


@pytest.mark.parametrize("fixture", ["good", "tall_frame", "wordmark_only"])
def test_mark_at_picks_the_output_pick_output_does(project_root, fixture):
    use_concept(make_final_brand(project_root), fixture)
    builder = export.PackageBuilder(project(), "keystone")
    for size in (16, 32, 33, 48, 95, 96, 108, 1024):
        assert export.CHAINS[export.TIER_VARIANTS[size_tier(size)[0]]] == size_tier(size), size  # mark() follows the same chain
        assert builder.mark_at(size) is builder.outputs[pick_output(builder.outputs, size)], size


@pytest.mark.parametrize("fixture", ["good", "tall_frame"])  # tall_frame's lockup is its symbol alone, twice as tall as wide
def test_the_stripe_logo_is_1024_wide_whatever_the_lockup_shape(project_root, fixture):
    use_concept(make_final_brand(project_root), fixture)
    builder, manifest = build(["commerce"])
    entry = next(e for e in manifest.files if e.path == "stripe-logo.png")
    size = opened(project_root / "brands" / "keystone" / "package" / "stripe-logo.png").size
    assert entry.width == 1024 and (entry.width, entry.height) == size == svg_size(builder.svg("horizontal", "color"), 1024)



def test_a_render_that_fills_its_canvas_is_not_blank(project_root):
    # A solid mark with no holes fills its own viewBox, so its render on transparent is opaque edge to edge in one colour, as
    # a square small tier is on the primary tile; the flattened JPEG lays it edge to edge on white. Only a raster that is
    # all its background colour is blank, so none of these is.
    make_final_brand(project_root)
    _, manifest = build(["pngs", "flattened", "favicons", *PLATFORM], StubRenderer(bleed=True))
    assert len(manifest.files) == 80 + 2 + 8 + 30


@pytest.mark.parametrize(("group", "named"), [
    ("apple", "ios-app-icon-1024.png"), ("android", "android/mipmap-mdpi/ic_launcher.png"), ("social", "avatar-320.png"),
    ("banners", "banner-x-1500x500.png"), ("previews", "og-image-1200x630.png"), ("commerce", "stripe-icon-512.png"),
])
def test_blank_art_stops_the_build_before_it_is_composed(project_root, group, named):
    # Composed onto one flat colour, blank art leaves a composite the blank rule refuses too; on a surface of several
    # colours it would not. So the art itself is refused first, by the file it was drawn for.
    make_final_brand(project_root)
    with pytest.raises(CliError) as err:
        build([group], StubRenderer(ink=None))
    assert err.value.code == 4 and str(err.value) == f"{named} (art) came out blank: its render drew nothing"


@requires_chrome
@pytest.mark.render
def test_platform_groups_write_expected_sizes(project_root, renderer):
    make_final_brand(project_root)
    builder = export.PackageBuilder(project(), "keystone")
    builder.GROUPS = ["apple", "android", "social", "banners", "previews", "commerce"]
    builder.build(renderer)
    pkg = project_root / "brands" / "keystone" / "package"

    def size(name):
        with Image.open(pkg / name) as image:
            return image.size

    with Image.open(pkg / "ios-app-icon-1024.png") as ios:
        assert ios.mode == "RGB" and ios.size == (1024, 1024) and ios.getpixel((5, 5)) == (0xE8, 0x57, 0x2A)  # opaque primary
    assert "viewBox" in (pkg / "app-icon-layers/foreground.svg").read_text()
    assert 'fill="#e8572a"' in (pkg / "app-icon-layers/background.svg").read_text()
    fg = (pkg / "android/ic_launcher_foreground.svg").read_text()
    vb = [float(v) for v in fg.split('viewBox="')[1].split('"')[0].split()]
    assert vb[2] == vb[3]
    assert (pkg / "android/ic_launcher_monochrome.svg").is_file()
    for density, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        assert size(f"android/mipmap-{density}/ic_launcher.png") == (px, px)
    assert size("play-store-icon-512.png") == (512, 512)
    for s in (320, 400, 512, 720, 800):
        with Image.open(pkg / f"avatar-{s}.png") as avatar:
            assert avatar.size == (s, s) and avatar.getpixel((1, 1))[3] == 255
            ys, xs = np.nonzero((np.asarray(avatar.convert("RGB")) != 255).any(axis=2))  # the art: every pixel not paper
        assert len(xs) and np.hypot(xs + 0.5 - s / 2, ys + 0.5 - s / 2).max() <= 0.4 * s  # inside the 80% circle
    for name, dims in (
        ("banner-x-1500x500.png", (1500, 500)), ("banner-linkedin-personal-1584x396.png", (1584, 396)),
        ("banner-linkedin-page-1512x256.png", (1512, 256)), ("banner-youtube-2560x1440.png", (2560, 1440)),
        ("banner-facebook-851x315.png", (851, 315)), ("banner-bluesky-1500x500.png", (1500, 500)),
        ("og-image-1200x630.png", (1200, 630)), ("x-card-1200x600.png", (1200, 600)),
        ("email-signature-logo@2x.png", (400, 100)), ("shopify-header-logo@2x.png", (800, 200)),
        ("stripe-icon-512.png", (512, 512)), ("gbp-logo-720.png", (720, 720)),
    ):
        assert size(name) == dims, name
    assert size("stripe-logo.png")[0] == 1024
    with Image.open(pkg / "email-signature-logo@2x.png") as email:
        assert email.getpixel((0, 0))[3] == 0
    with Image.open(pkg / "banner-youtube-2560x1440.png") as banner:
        youtube = banner.convert("RGBA")
    assert youtube.getpixel((100, 100))[:3] == (255, 255, 255)  # paper outside the safe area
    x0, y0, x1, y1 = ink_box(pkg / "banner-youtube-2560x1440.png")
    assert 662 <= x0 and 551 <= y0 and x1 <= 662 + 1235 and y1 <= 551 + 338  # the logo inside the central 1235x338
    _, y0, _, y1 = ink_box(pkg / "banner-x-1500x500.png")
    assert y0 >= 60 and y1 <= 500 - 60  # top and bottom 60 px kept clear
