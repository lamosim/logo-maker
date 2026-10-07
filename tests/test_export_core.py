import hashlib
import io
import json
import os
import re
import shutil
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner
from PIL import Image

from logomaker import export, registry, render
from logomaker.cli import main
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.schemas import Manifest, Phase
from tests.conftest import FIXTURES, StubRenderer, make_final_brand, requires_chrome, write_passing_audit

SQ = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-50 -25 100 50"><path d="M0 0"/></svg>'
CORE = ["masters", "pngs", "flattened", "favicons"]
FLATTENED = ["keystone-primary-color-white-bg-2048.jpg", "keystone-primary-color-2048.webp"]
FAVICONS = ["favicon.ico", "icon.svg", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-mask-512.png", "manifest.webmanifest",
            "favicon-head.html"]
LIGHT_BLUE = (59, 154, 225, 255)  # #3b9ae1: passes check_tokens on white paper (WCAG 3.05, Lc 57), yet lighter than ink_mask's cut
FAINT = (31, 27, 24, 100)  # under half opaque everywhere, as a long name can be in the 16 px favicon frame


def opened(path: Path) -> Image.Image:
    """The image at `path`, read in full and closed."""
    with Image.open(path) as image:
        image.load()
        return image


def build(groups: list[str], renderer=None) -> tuple[export.PackageBuilder, Manifest]:
    """Brand keystone's package built from `groups`, through `renderer` (a StubRenderer by default)."""
    builder = export.PackageBuilder(project(), "keystone")
    builder.GROUPS = groups
    return builder, builder.build(renderer or StubRenderer())


def package_build(*args: str) -> tuple[int, dict]:
    """`package build keystone` with `args`: the exit code and the JSON payload."""
    result = CliRunner().invoke(main, ["package", "build", "keystone", *args])
    return result.exit_code, json.loads(result.stdout)


def test_square_viewbox():
    assert 'viewBox="-62.5 -62.5 125 125"' in export.square_viewbox(SQ, 0.8)


def test_missing_final_files_exit_2_before_chrome_naming_what_to_write(project_root, no_chrome):
    final = make_final_brand(project_root)  # in refinement
    (final / "rationale.md").unlink()
    code, payload = package_build()
    assert code == 2 and payload["errors"] == ["final/rationale.md is missing; finish refinement and write final/rationale.md "
                                               "(one paragraph on why this mark) before packaging"]
    (final / "rationale.md").write_text("Why.\n")
    registry.advance(project(), "keystone", Phase.package)  # past refinement: no refinement left to finish
    (final / "params.json").unlink()
    code, payload = package_build()
    assert code == 2 and payload["errors"] == ["final/params.json is missing; write final/params.json "
                                               "({} if the concept has no parameters) before packaging"]


def test_a_final_audit_that_no_longer_vouches_for_the_mark_exits_2_before_chrome(project_root, no_chrome):
    final = make_final_brand(project_root)
    (final / "params.json").write_text('{"stroke": 100}\n')
    code, payload = package_build()
    assert code == 2 and "final/audit.json is stale" in payload["errors"][0]
    (final / "audit.json").unlink()
    code, payload = package_build()
    assert code == 2 and "final/audit.json is missing" in payload["errors"][0]


def test_core_groups_without_chrome(project_root):
    make_final_brand(project_root)
    stub = StubRenderer()
    builder, manifest = build(CORE, stub)
    pkg = project_root / "brands" / "keystone" / "package"
    assert builder.pkg == pkg and not (pkg.parent / "package.tmp").exists()
    paths = [e.path for e in manifest.files]
    svgs = [p for p in paths if p.startswith("keystone-") and p.endswith(".svg")]
    pngs = [p for p in paths if p.startswith("keystone-") and p.endswith(".png")]
    assert len(svgs) == 35 and "keystone-favicon-mono.svg" in svgs and len(pngs) == 80 and "keystone-mark-black-2048.png" in pngs
    assert paths == svgs + pngs + FLATTENED + FAVICONS
    assert sorted(p.name for p in pkg.iterdir()) == sorted([*paths, "manifest.json"])
    for entry in manifest.files:
        raw = (pkg / entry.path).read_bytes()
        assert (entry.sha256, entry.bytes) == (hashlib.sha256(raw).hexdigest(), len(raw))
        if entry.width:
            assert opened(pkg / entry.path).size == (entry.width, entry.height), entry.path
    sizes = {e.path: (e.width, e.height) for e in manifest.files}
    assert sizes["keystone-primary-color-1024.png"][0] == 1024 and sizes["keystone-stacked-color-1024.png"][1] == 1024
    assert sizes["favicon.ico"] == (48, 48) and sizes["apple-touch-icon.png"] == (180, 180) and sizes["icon.svg"] == (None, None)
    assert json.loads((pkg / "manifest.json").read_text()) == manifest.model_dump()
    assert manifest.warnings == [] and manifest.skipped == {}
    assert len(stub.calls) == 80 + 1 + 7  # the PNG matrix, the 2048 px primary flattened, the favicon set's frames and tiles


def test_the_head_snippet_links_icons_from_the_site_root_and_previews_absolutely(project_root):
    make_final_brand(project_root)
    build(["favicons"])
    head = (project_root / "brands" / "keystone" / "package" / "favicon-head.html").read_text()
    assert re.findall(r'href="([^"]+)"', head) == ["/favicon.ico", "/icon.svg", "/apple-touch-icon.png", "/manifest.webmanifest"]
    # Link previews fetch their image from another site, so a root-relative URL means nothing to them.
    lines = head.splitlines()
    note = next(i for i, line in enumerate(lines) if line.startswith("<!--"))
    assert "replace https://example.com with your site's origin" in lines[note]
    assert lines[note + 1:note + 3] == ['<meta name="twitter:image" content="https://example.com/x-card-1200x600.png">',
                                        '<meta property="og:image" content="https://example.com/og-image-1200x630.png">']
    assert lines[note + 3:] == ['<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">']


def test_raster_icons_draw_the_tier_for_their_size(project_root):
    make_final_brand(project_root)
    stub = StubRenderer()
    builder, _ = build(["favicons"], stub)

    def colour(name: str) -> str:
        return builder.outputs[name].to_svg("color", palette=builder.light)

    renders = {max(width, height): svg for svg, width, height, _ in stub.calls}
    assert len(stub.calls) == 7 and sorted(renders) == [16, 32, 48, 140, 154, 289, 410]  # ICO frames, then tile art (apple, PWA, mask)
    assert renders[48] == export.square_viewbox(colour("small"), 0.9)
    assert renders[32] == renders[16] == export.square_viewbox(colour("favicon"), 0.9)
    assert {renders[side] for side in (140, 154, 289, 410)} == {colour("full-symbol")}
    with Image.open(project_root / "brands" / "keystone" / "package" / "favicon.ico") as ico:
        for size in (16, 32, 48):  # each frame is the render made for its size, never the 48 px one scaled down
            call = next(c for c in stub.calls if c[1:3] == (size, size))
            with Image.open(io.BytesIO(stub.svg_to_png(*call))) as rendered:
                assert ico.ico.getimage((size, size)).convert("RGBA").tobytes() == rendered.convert("RGBA").tobytes(), size


def test_named_masters_follow_the_fallback_chains(project_root):
    final = make_final_brand(project_root)

    def resolved(builder: export.PackageBuilder) -> dict[str, str | None]:
        names = {id(mark): name for name, mark in builder.outputs.items()}
        return {variant: names.get(id(builder.mark(variant))) for variant in export.VARIANT_NAMES}

    builder = export.PackageBuilder(project(), "keystone")
    assert resolved(builder) == {"primary": "full-horizontal", "horizontal": "full-horizontal", "stacked": "full-stacked",
                                 "wordmark": "full-wordmark", "mark": "full-symbol", "small": "small", "favicon": "favicon"}
    assert builder.warnings == []
    registry.set_fields(project(), "keystone", primary_lockup="stacked")
    assert resolved(export.PackageBuilder(project(), "keystone"))["primary"] == "full-stacked"
    shutil.copy(FIXTURES / "concepts" / "tall_frame" / "concept.py", final / "concept.py")  # a symbol alone, with a favicon tier
    write_passing_audit(project(), "keystone", final)
    builder = export.PackageBuilder(project(), "keystone")
    assert resolved(builder) == {"primary": "full-lockup", "horizontal": "full-lockup", "stacked": "full-lockup", "wordmark": None,
                                 "mark": "full-symbol", "small": "full-symbol", "favicon": "favicon"}
    assert builder.svg("wordmark", "color") is None
    assert builder.warnings == ["primary falls back to full-lockup (the concept has no full-stacked)",
                                "horizontal falls back to full-lockup (the concept has no full-horizontal)",
                                "stacked falls back to full-lockup (the concept has no full-stacked)",
                                "wordmark skipped: the concept has no full-wordmark",
                                "small falls back to full-symbol (draw a dedicated tier for better small sizes)"]


def test_file_names_follow_the_brand_name_and_the_web_manifest_escapes_it(project_root):
    make_final_brand(project_root)
    registry.rename(project(), "keystone", 'Key "Stone" & Co')
    _, manifest = build(["masters", "favicons"])
    assert manifest.files[0].path == "key-stone-co-primary-color.svg"
    webmanifest = json.loads((project_root / "brands" / "keystone" / "package" / "manifest.webmanifest").read_text())
    assert (webmanifest["name"], webmanifest["theme_color"], webmanifest["background_color"]) == ('Key "Stone" & Co', "#e8572a", "#ffffff")
    registry.rename(project(), "keystone", "東京")  # no ASCII letters or digits to slugify: the brand's slug stands in
    _, manifest = build(["masters"])
    assert manifest.files[0].path == "keystone-primary-color.svg"


@pytest.mark.parametrize(("group", "named"), [("pngs", "keystone-primary-color-256.png"),
                                              ("flattened", "keystone-primary-color-white-bg-2048.jpg"), ("favicons", "favicon.ico")])
def test_a_blank_render_fails_the_build_naming_the_file(project_root, group, named):
    make_final_brand(project_root)
    with pytest.raises(CliError) as err:
        build([group], StubRenderer(ink=None))
    assert err.value.code == 4 and str(err.value).startswith(named)


@pytest.mark.parametrize("ink", [LIGHT_BLUE, FAINT], ids=["light-mark-on-paper", "faint"])
def test_a_drawn_render_is_never_taken_for_a_blank_one(project_root, ink):
    # raster.ink_mask would call both blank: on the opaque files (the JPEG, the apple-touch and maskable icons) it counts
    # only pixels darker than 128, which LIGHT_BLUE is not; on the transparent ones only pixels over half opaque.
    make_final_brand(project_root)
    _, manifest = build(CORE, StubRenderer(ink=ink))
    assert len(manifest.files) == 125


def test_a_failed_build_leaves_the_previous_package(project_root):
    make_final_brand(project_root)
    brand = project_root / "brands" / "keystone"
    pkg, staging = brand / "package", brand / "package.tmp"
    (pkg / "marker.txt").write_text("the previous build")
    builder = export.PackageBuilder(project(), "keystone")
    builder.GROUPS = ["masters", "pngs"]
    with pytest.raises(CliError):
        builder.build(StubRenderer(ink=None))  # every master is written, then the first PNG comes out blank
    assert [p.name for p in pkg.iterdir()] == ["marker.txt"] and not staging.exists() and builder.pkg == pkg
    staging.mkdir()
    (staging / "half.svg").write_text("<svg/>")  # left by a build that was killed
    builder.GROUPS = ["masters"]
    builder.build(StubRenderer())
    assert not staging.exists() and not (pkg / "marker.txt").exists() and len(list(pkg.glob("keystone-*.svg"))) == 35


def test_the_previous_package_survives_a_swap_that_fails_or_was_killed(project_root, monkeypatch):
    make_final_brand(project_root)
    brand = project_root / "brands" / "keystone"
    pkg, aside = brand / "package", brand / "package.old.tmp"

    def folders() -> list[str]:
        return sorted(p.name for p in brand.iterdir() if p.name.startswith("package"))

    (pkg / "marker.txt").write_text("the previous build")
    pkg.rename(aside)  # a build killed after moving package/ aside, before the new one took its place
    real_replace = os.replace

    def replace(src, dst):
        if Path(src).name == "package.tmp":
            raise OSError(28, "No space left on device")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(CliError) as err:
        build(["masters"])
    assert err.value.code == 3 and str(err.value).endswith("the previous package is kept")
    assert folders() == ["package"] and [p.name for p in pkg.iterdir()] == ["marker.txt"]
    monkeypatch.setattr(os, "replace", real_replace)
    shutil.copytree(pkg, aside)  # a build killed after the new package took its place, before the old one was deleted
    build(["masters"])
    assert folders() == ["package"] and not (pkg / "marker.txt").exists() and (pkg / "manifest.json").is_file()


def test_a_build_given_no_renderer_stops_at_the_first_group_that_renders(project_root):
    make_final_brand(project_root)
    builder = export.PackageBuilder(project(), "keystone")
    builder.GROUPS = ["masters", "pngs"]  # the masters are written from the kit's paths, the PNGs rendered through Chrome
    with pytest.raises(CliError, match="given no renderer") as err:
        builder.build()
    assert err.value.code == 2


def test_package_build_reports_the_package_and_every_warning(project_root, monkeypatch):
    make_final_brand(project_root, wordmark_only=True)
    monkeypatch.setattr(render, "Renderer", StubRenderer)
    monkeypatch.setattr(export.PackageBuilder, "GROUPS", ["masters", "idle"])
    monkeypatch.setattr(export.PackageBuilder, "idle", lambda self: self.skip("idle", "nothing to do"), raising=False)
    code, payload = package_build("--paper", "a4")
    assert code == 0, payload
    pkg = project_root / "brands" / "keystone" / "package"
    assert (payload["package"], payload["files"], payload["manifest"]) == (str(pkg), 35, str(pkg / "manifest.json"))
    assert payload["brand_sheet"] is None  # the docs group, which prints it, did not run
    assert payload["warnings"] == ["primary falls back to full-lockup (the concept has no full-horizontal)",
                                   "horizontal falls back to full-lockup (the concept has no full-horizontal)",
                                   "stacked falls back to full-lockup (the concept has no full-stacked)",
                                   "mark falls back to full-lockup (the concept has no full-symbol)",
                                   "small falls back to full-lockup (draw a dedicated tier for better small sizes)",
                                   "favicon falls back to full-lockup (draw a dedicated tier for better small sizes)",
                                   "idle skipped: nothing to do"]
    saved = json.loads((project_root / "brands" / "keystone" / "package" / "manifest.json").read_text())
    assert saved["skipped"] == {"idle": "nothing to do"}


def test_package_build_gives_the_brand_sheet_s_absolute_path(project_root, monkeypatch):
    make_final_brand(project_root)
    monkeypatch.setattr(render, "Renderer", StubRenderer)
    monkeypatch.setattr(export.PackageBuilder, "GROUPS", ["docs"])
    code, payload = package_build()
    assert code == 0 and payload["brand_sheet"] == str(project_root / "brands" / "keystone" / "package" / "brand-sheet.pdf")
    assert Path(payload["brand_sheet"]).is_file() and Path(payload["manifest"]).is_file()


@requires_chrome
@pytest.mark.render
def test_core_groups_write_expected_files(project_root, renderer):
    make_final_brand(project_root)
    builder = export.PackageBuilder(project(), "keystone")
    builder.GROUPS = ["masters", "pngs", "flattened", "favicons"]
    manifest = builder.build(renderer)
    pkg = project_root / "brands" / "keystone" / "package"
    svgs = sorted(p.name for p in pkg.glob("keystone-*.svg"))
    assert len(svgs) == 35 and "keystone-favicon-mono.svg" in svgs
    assert "currentColor" in (pkg / "keystone-mark-mono.svg").read_text()
    assert len(list(pkg.glob("keystone-*-*-*.png"))) == 80
    big = opened(pkg / "keystone-primary-color-1024.png")
    assert big.size[0] == 1024 and big.mode == "RGBA" and big.getpixel((0, 0))[3] == 0
    reverse = opened(pkg / "keystone-primary-reverse-512.png")
    assert reverse.getpixel((0, 0))[3] == 0  # real alpha, not a white box
    assert opened(pkg / "keystone-primary-color-white-bg-2048.jpg").mode == "RGB"
    assert (pkg / "keystone-primary-color-2048.webp").stat().st_size > 0
    with Image.open(pkg / "favicon.ico") as ico:
        assert {(16, 16), (32, 32), (48, 48)} <= set(ico.ico.sizes())
    icon_svg = (pkg / "icon.svg").read_text()
    assert "prefers-color-scheme" in icon_svg
    vb = [float(v) for v in icon_svg.split('viewBox="')[1].split('"')[0].split()]
    assert vb[2] == vb[3]
    apple = opened(pkg / "apple-touch-icon.png")
    assert apple.size == (180, 180) and apple.getpixel((2, 2))[3] == 255
    mask = opened(pkg / "icon-mask-512.png")
    assert mask.size == (512, 512)
    ys, xs = np.nonzero((np.asarray(mask.convert("RGB")) != 255).any(axis=2))  # the art: every pixel that is not white paper
    assert len(xs) and np.hypot(xs + 0.5 - 256, ys + 0.5 - 256).max() <= 0.4 * 512  # inside the maskable safe circle
    assert opened(pkg / "icon-192.png").getpixel((0, 0))[3] == 0
    assert json.loads((pkg / "manifest.webmanifest").read_text())["icons"][2]["purpose"] == "maskable"
    assert "apple-touch-icon" in (pkg / "favicon-head.html").read_text()
    data = json.loads((pkg / "manifest.json").read_text())
    assert data["slug"] == "keystone" and len(data["files"]) == len(manifest.files)
    entry = next(f for f in data["files"] if f["path"] == "keystone-primary-color-1024.png")
    assert entry["width"] == 1024 and len(entry["sha256"]) == 64


@requires_chrome
@pytest.mark.render
def test_wordmark_only_brand_falls_back_with_warnings(project_root, renderer):
    make_final_brand(project_root, wordmark_only=True)
    builder = export.PackageBuilder(project(), "keystone")
    builder.GROUPS = ["masters", "favicons"]
    manifest = builder.build(renderer)
    assert any("falls back" in w for w in manifest.warnings)
    assert (project_root / "brands" / "keystone" / "package" / "favicon.ico").is_file()
