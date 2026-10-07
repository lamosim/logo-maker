"""Export package builder (spec section 9). Each group writes files into the package and registers their manifest entries.
The artwork groups live here; the document groups, and verify(), which checks a built package, live in export_docs."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import shutil
from collections.abc import Callable
from pathlib import Path

from PIL import Image

from . import pdfout, registry
from .color import enrich_tokens, load_tokens, palettes_of
from .export_docs import DocumentGroups, inputs_fingerprint
from .kit import concept as conceptlib
from .kit.mark import ROLES, Mark
from .kit.shape import fmt
from .output import EXIT_EXTERNAL, EXIT_VERIFY, CliError
from .paths import ProjectPaths
from .raster import blank, encoded, image_size
from .render import VIEWBOX, Renderer, fit_size
from .schemas import Manifest, ManifestEntry, Phase, now_iso
from .sheets import jinja

VARIANT_NAMES = ("primary", "horizontal", "stacked", "wordmark", "mark", "small", "favicon")
COLOURS = ("color", "reverse", "black", "white", "mono")
PNG_VARIANTS = ("primary", "horizontal", "stacked", "wordmark", "mark")
PNG_COLOURS = ("color", "reverse", "black", "white")
PNG_SIZES = (256, 512, 1024, 2048)
MASK_SAFE = 289  # centred in 512, its corners stay inside the maskable safe circle (radius 40% = 204.8 px)
ADAPTIVE_RADIUS = 330  # of the adaptive icon's 1080 units (108 dp): the radius of its 66 dp safe circle
REQUIRED_FINAL = ("concept.py", "params.json", "tokens.json", "rationale.md")
RASTERS = (".png", ".jpg", ".webp")  # written files that write() refuses when blank
STAGING, ASIDE = "package.tmp", "package.old.tmp"  # beside package/: the build in progress; the previous package mid-swap
# The outputs that draw each named variant, best first. primary is brand.json's primary lockup, then full-lockup.
CHAINS = {
    "horizontal": ("full-horizontal", "full-lockup"),
    "stacked": ("full-stacked", "full-lockup"),
    "wordmark": ("full-wordmark",),
    "mark": conceptlib.tier_chain("full-symbol"),
    "small": conceptlib.tier_chain("small"),
    "favicon": conceptlib.tier_chain("favicon"),
}
# The variant whose chain (CHAINS) is the one kit.concept.size_tier gives a size, by that chain's first output.
TIER_VARIANTS = {"full-symbol": "mark", "small": "small", "favicon": "favicon"}


def _square_view(svg: str, side_of: Callable[[float, float], float]) -> str:
    """Rewrite the viewBox to a square centred on the artwork, `side_of(w, h)` across for an artwork w x h."""
    match = VIEWBOX.search(svg)
    x, y, w, h = (float(v) for v in match.group(1).replace(",", " ").split())
    side = side_of(w, h)
    view = (x + w / 2 - side / 2, y + h / 2 - side / 2, side, side)
    return svg.replace(match.group(0), f'viewBox="{" ".join(fmt(v) for v in view)}"', 1)


def square_viewbox(svg: str, fraction: float) -> str:
    """Rewrite the viewBox to a square in which the artwork's longer side spans `fraction` of the side."""
    return _square_view(svg, lambda w, h: max(w, h) / fraction)


def circle_viewbox(svg: str, radius: float) -> str:
    """Rewrite the viewBox to a square in which the artwork's box, centred, has its corners on a circle `radius` of the
    side across: the box's own half-diagonal sets the size, so a wide or tall mark grows as far as the circle allows
    where a square one cannot. The side is rounded up to the viewBox's two decimals, never shrinking the circle."""
    return _square_view(svg, lambda w, h: math.ceil(math.hypot(w, h) / 2 / radius * 100) / 100)


def square_fill(side: int, colour: str) -> str:
    """A `side`-unit square SVG filled with `colour`, drawn as a path: every SVG in the package is paths only."""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side} {side}"><path d="M0 0H{side}V{side}H0Z" fill="{colour}"/></svg>'


def _swap_in(staging: Path, package: Path, aside: Path) -> None:
    """Put `staging` in `package`'s place. The previous package moves to `aside` first, and back again if the new one
    cannot take its place, so neither move can lose it; `aside` is deleted once the new package is in. A move or the
    deletion that fails is a CliError (exit 3) that says where each package is: a previous package that cannot be
    moved back, or deleted, stays in `aside`, which the next build puts back or deletes."""
    moved_aside = False
    try:
        if package.exists():
            os.replace(package, aside)
            moved_aside = True
        os.replace(staging, package)
    except OSError as err:
        if not moved_aside:
            raise CliError(f"could not move the new package into {package} ({err}); there was no previous package",
                           code=EXIT_EXTERNAL) from err
        try:
            os.replace(aside, package)
        except OSError as again:
            raise CliError(f"could not move the new package into {package} ({err}), nor the previous one back ({again}); "
                           f"the previous package is in {aside}, and the next package build puts it back",
                           code=EXIT_EXTERNAL) from again
        raise CliError(f"could not move the new package into {package} ({err}); the previous package is kept",
                       code=EXIT_EXTERNAL) from err
    if moved_aside:
        try:
            shutil.rmtree(aside)
        except OSError as err:
            raise CliError(f"the new package is in {package}, but the previous one could not be deleted from {aside} ({err}); "
                           "delete it, or the next package build will", code=EXIT_EXTERNAL) from err


class PackageBuilder(DocumentGroups):
    """Builds brands/<slug>/package/ from final/: the vocabulary of named variants, staging and the swap, the shared
    writing and rendering helpers, the artwork groups and build(); DocumentGroups adds the document groups."""

    GROUPS: list[str] = ["masters", "pngs", "flattened", "favicons", "apple", "android", "social", "banners", "previews", "commerce",
                         "print_files", "tokens_file", "fonts", "docs", "readme"]

    def __init__(self, paths: ProjectPaths, slug: str, paper: str = "letter"):
        """Check final/ before anything renders: its four files (a missing one is named with what to write, and "finish
        refinement" while the brand is still in refinement), then an audit.json that vouches for the final mark as it is
        now (registry.require_final_audit). Either refusal is a CliError, exit 2."""
        self.paths, self.slug, self.paper = paths, slug, paper
        self.state = registry.load_state(paths, slug)
        self.brand_dir = paths.brand(slug)
        self.final = self.brand_dir / "final"
        self.pkg = self.brand_dir / "package"
        for name in REQUIRED_FINAL:
            if not (self.final / name).is_file():
                remedy = registry.FINAL_REMEDIES[name]
                if self.state.phase == Phase.refinement:
                    remedy = f"finish refinement and {remedy}"
                raise CliError(f"final/{name} is missing; {remedy} before packaging")
        registry.require_final_audit(paths, slug, "packaging")
        self.inputs = inputs_fingerprint(paths, slug)  # what this build reads, as the manifest records it
        self.outputs = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(self.final)))
        self.tokens = enrich_tokens(load_tokens(self.final / "tokens.json"))
        self.light, self.dark = palettes_of(self.tokens)
        try:
            self.name = registry.slugify(self.state.name)  # the file prefix follows the brand's name
        except CliError:  # a name with no ASCII letters or digits to keep
            self.name = slug
        self.entries: list[ManifestEntry] = []
        self.warnings: list[str] = []
        self.skipped: dict[str, str] = {}
        self.built = now_iso()  # build() sets it again: the one timestamp of the manifest and README.md
        self._renderer: Renderer | None = None  # set by build(); groups read it through the renderer property

    # ---- helpers -------------------------------------------------------
    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def skip(self, group: str, reason: str) -> None:
        """Record that `group` could not run, and why; package build reports it as a warning."""
        self.skipped[group] = reason

    @property
    def renderer(self) -> Renderer:
        """The renderer build() was given. Only a group that renders reaches for it, so a build of groups that never render
        (print_files) can go without Chrome; one that does stops with a CliError rather than failing on None."""
        if self._renderer is None:
            raise CliError("this package group renders through Chrome, but build() was given no renderer")
        return self._renderer

    def mark(self, variant: str) -> Mark | None:
        """The output that draws `variant` (one of VARIANT_NAMES): the first in its chain that was built
        (kit.concept.first_present), with a warning when that is a fallback. None, with a warning, when the chain has
        nothing built; only the wordmark's can, since every other chain ends at full-lockup."""
        chain = (f"full-{self.state.primary_lockup}", "full-lockup") if variant == "primary" else CHAINS[variant]
        name = conceptlib.first_present(self.outputs, chain)
        if name not in chain:  # first_present's own fallback, full-lockup, which the wordmark's chain leaves out
            self.warn(f"{variant} skipped: the concept has no {chain[0]}")
            return None
        if name != chain[0]:
            tiered = variant in conceptlib.TIER_FALLBACKS
            advice = "draw a dedicated tier for better small sizes" if tiered else f"the concept has no {chain[0]}"
            self.warn(f"{variant} falls back to {name} ({advice})")
        return self.outputs[name]

    def mark_at(self, size: int) -> Mark:
        """The output that draws the mark `size` px across: the first built in kit.concept.size_tier(size), the chain
        kit.concept.pick_output follows (full-symbol from 96 px, small down to 33 px, favicon below). It resolves through
        mark(), so a fallback warns. Never None: mark() returns None only for a chain with nothing built, and each of
        these ends at full-lockup, which every build has."""
        mark = self.mark(TIER_VARIANTS[conceptlib.size_tier(size)[0]])
        assert mark is not None  # every size_tier chain ends at full-lockup
        return mark

    def svg(self, variant: str, colour: str) -> str | None:
        mark = self.mark(variant)
        if mark is None:
            return None
        return mark.to_svg(colour, palette=self.dark if colour == "reverse" else self.light)

    @staticmethod
    def _entry(relpath: str, raw: bytes, purpose: str, width: int | None = None, height: int | None = None) -> ManifestEntry:
        """The manifest entry of package file `relpath`, whose bytes are `raw`."""
        return ManifestEntry(path=relpath, purpose=purpose, width=width, height=height, sha256=hashlib.sha256(raw).hexdigest(),
                             bytes=len(raw))

    def _refuse_blank(self, name: str, raster: bytes, background: str | None = None) -> None:
        """Stop the build with exit 4, naming `name`, when `raster` shows nothing (raster.blank): a render on transparent
        when no pixel is drawn, a raster composed onto `background` when every pixel is that colour."""
        if blank(raster, background):
            raise CliError(f"{name} came out blank: its render drew nothing", code=EXIT_VERIFY)

    def write(self, relpath: str, data: bytes | str, purpose: str, width: int | None = None, height: int | None = None, *,
              background: str | None = None) -> Path:
        """Write `data` to `relpath` in the package and add its manifest entry. A raster (RASTERS) that came out blank
        stops the build with exit 4 instead: `background` is the colour it was composed onto, None for a render on
        transparent (_refuse_blank)."""
        raw = data.encode("utf-8") if isinstance(data, str) else data
        if Path(relpath).suffix in RASTERS:
            self._refuse_blank(relpath, raw, background)
        target = self.pkg / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        self.entries.append(self._entry(relpath, raw, purpose, width, height))
        return target

    def register(self, relpath: str, purpose: str, width: int | None = None, height: int | None = None) -> None:
        """Add the manifest entry of `relpath`, a file already in the package that write() did not write (pdfout's)."""
        self.entries.append(self._entry(relpath, (self.pkg / relpath).read_bytes(), purpose, width, height))

    def render_fit(self, svg: str, box_w: int, box_h: int, background: str | None = None) -> bytes:
        """`svg` rendered as large as fits a `box_w` x `box_h` box, keeping its aspect (render.fit_size)."""
        return self.renderer.svg_to_png(svg, *fit_size(svg, box_w, box_h), background=background)

    def png_bytes(self, svg: str, long_edge: int) -> bytes:
        """`svg` rendered on transparent with its longer side `long_edge` px."""
        return self.render_fit(svg, long_edge, long_edge)

    @staticmethod
    def compose(width: int, height: int, background: str | None, art: bytes | None = None,
                box: tuple[int, int, int, int] | None = None, alpha: bool = True) -> bytes:
        """A `width` x `height` PNG on `background` (transparent when None) with `art`, a PNG, centred in `box` (x, y, w,
        h; the whole canvas by default) and shrunk to fit it if it is larger. alpha=False saves it without an alpha
        channel (RGB), for an opaque background."""
        canvas = Image.new("RGBA", (width, height), background or (0, 0, 0, 0))
        if art is not None:
            with Image.open(io.BytesIO(art)) as opened:
                image = opened.convert("RGBA")
            bx, by, bw, bh = box or (0, 0, width, height)
            scale = min(bw / image.width, bh / image.height, 1.0)
            if scale < 1.0:
                image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
            canvas.alpha_composite(image, (bx + (bw - image.width) // 2, by + (bh - image.height) // 2))
        return encoded(canvas if alpha else canvas.convert("RGB"), "PNG")

    @staticmethod
    def _centered(size_w: int, size_h: int, art_w: int, art_h: int) -> tuple[int, int, int, int]:
        """The (x, y, w, h) box of an `art_w` x `art_h` area centred on a `size_w` x `size_h` canvas."""
        return (size_w - art_w) // 2, (size_h - art_h) // 2, art_w, art_h

    def _tile(self, relpath: str, size: int, art_svg: str, fraction: float, purpose: str, background: str | None,
              alpha: bool = True) -> None:
        """Write a `size` px square PNG on `background`: `art_svg` rendered to `fraction` of the side, centred (_place)."""
        self._place(relpath, size, size, art_svg, fraction, purpose, background, alpha=alpha)

    def _place(self, relpath: str, width: int, height: int, art_svg: str, fraction: float, purpose: str, background: str | None,
               safe: tuple[int, int, int, int] | None = None, alpha: bool = True) -> None:
        """Write a `width` x `height` PNG on `background` (transparent when None): `art_svg` rendered as large as fits
        `fraction` of the `safe` box (x, y, w, h; the whole canvas by default), centred in it. Blank art stops the build
        (exit 4) before it is composed, naming the art; then the composite is checked against `background` as it is
        written. alpha=False writes the PNG without an alpha channel (compose)."""
        bx, by, bw, bh = safe or (0, 0, width, height)
        art_w, art_h = round(bw * fraction), round(bh * fraction)
        art = self.render_fit(art_svg, art_w, art_h)
        self._refuse_blank(f"{relpath} (art)", art)
        x, y, _, _ = self._centered(bw, bh, art_w, art_h)
        self.write(relpath, self.compose(width, height, background, art, (bx + x, by + y, art_w, art_h), alpha), purpose, width, height,
                   background=background)

    def _on_primary(self) -> dict[str, str]:
        """The palette of art on a primary-colour tile: every role, paper too, in the light paper colour (as the concept
        sheet draws its app icon)."""
        return {role: self.light["paper"] for role in (*ROLES, "paper")}

    # ---- groups --------------------------------------------------------
    def masters(self) -> None:
        for variant in VARIANT_NAMES:
            for colour in COLOURS:
                svg = self.svg(variant, colour)
                if svg is not None:
                    self.write(f"{self.name}-{variant}-{colour}.svg", svg, f"{variant} lockup, {colour} variant, vector master")

    def pngs(self) -> None:
        for variant in PNG_VARIANTS:
            for colour in PNG_COLOURS:
                svg = self.svg(variant, colour)
                if svg is None:
                    continue
                for size in PNG_SIZES:
                    png = self.png_bytes(svg, size)
                    self.write(f"{self.name}-{variant}-{colour}-{size}.png", png, f"{variant} {colour} transparent PNG, long edge {size}",
                               *image_size(png))

    def flattened(self) -> None:
        svg = self.svg("primary", "color")  # never None: the primary chain ends at full-lockup
        with Image.open(io.BytesIO(self.png_bytes(svg, 2048))) as opened:
            image = opened.convert("RGBA")
        white = Image.alpha_composite(Image.new("RGBA", image.size, "#ffffff"), image).convert("RGB")
        self.write(f"{self.name}-primary-color-white-bg-2048.jpg", encoded(white, "JPEG", quality=92),
                   "primary on a white background, flattened JPEG", *image.size, background="#ffffff")
        self.write(f"{self.name}-primary-color-2048.webp", encoded(image, "WEBP", quality=90), "primary colour transparent WebP",
                   *image.size)

    def favicons(self) -> None:
        """favicon.ico's frames and icon.svg fill their square, with no inset, as the audit measures each tier (the
        favicon tier across all 16 px, the small tier across 32): any margin is drawn into the tier itself. Then the
        tiles, the web app manifest and the head snippet."""
        frames = []
        for size in (48, 32, 16):  # each frame drawn by the tier for its own size, and checked before the ICO packs it
            png = self.render_fit(square_viewbox(self.mark_at(size).to_svg("color", palette=self.light), 1.0), size, size)
            self._refuse_blank(f"favicon.ico ({size} px frame)", png)
            with Image.open(io.BytesIO(png)) as frame:
                frames.append(frame.convert("RGBA"))
        self.write("favicon.ico", encoded(frames[0], "ICO", sizes=[(48, 48), (32, 32), (16, 16)], append_images=frames[1:]),
                   "legacy favicon, 16/32/48", 48, 48)
        favicon = self.mark("favicon")  # the favicon master, plus a style that switches to the dark roles
        self.write("icon.svg", square_viewbox(favicon.to_svg("color", palette=self.light, dark_palette=self.dark), 1.0),
                   "SVG favicon with dark-mode style")
        paper = self.light["paper"]
        for relpath, size, fraction, background, purpose in (
            ("apple-touch-icon.png", 180, 140 / 180, paper, "iOS bookmark icon, opaque"),
            ("icon-192.png", 192, 0.8, None, "PWA icon 192, transparent"),
            ("icon-512.png", 512, 0.8, None, "PWA icon 512, transparent"),
            ("icon-mask-512.png", 512, MASK_SAFE / 512, paper, "maskable PWA icon, art inside the safe circle"),
        ):
            self._tile(relpath, size, self.mark_at(size).to_svg("color", palette=self.light), fraction, purpose, background)
        env = jinja(self.paths)
        ctx = {"brand": self.state.name, "primary": self.light["primary"], "paper": paper}
        self.write("manifest.webmanifest", env.get_template("manifest.webmanifest.j2").render(**ctx), "web app manifest")
        self.write("favicon-head.html", env.get_template("favicon-head.html.j2").render(**ctx),
                   "HTML head snippet for favicons and link previews")

    def apple(self) -> None:
        art = self.mark_at(1024).to_svg("color", palette=self._on_primary())
        primary = self.light["primary"]
        self._tile("ios-app-icon-1024.png", 1024, art, 0.6, "iOS, iPadOS and macOS app icon: opaque, unmasked square", primary,
                   alpha=False)  # App Store Connect refuses an icon with an alpha channel
        self.write("app-icon-layers/background.svg", square_fill(1024, primary), "Icon Composer background layer")
        self.write("app-icon-layers/foreground.svg", square_viewbox(art, 0.6), "Icon Composer foreground layer, mark at 60% of the canvas")

    def android(self) -> None:
        on_primary, primary = self._on_primary(), self.light["primary"]
        layer = self.mark_at(108)  # the tier for the adaptive icon's 108 dp canvas
        safe = ADAPTIVE_RADIUS / 1080  # each layer's art box fitted by its own half-diagonal: a wide mark grows past a square one
        self.write("android/ic_launcher_foreground.svg", circle_viewbox(layer.to_svg("color", palette=on_primary), safe),
                   "adaptive icon foreground: art fitted inside the 66 dp safe circle of the 108 dp canvas")
        self.write("android/ic_launcher_background.svg", square_fill(1080, primary), "adaptive icon background layer, 1080-unit canvas")
        self.write("android/ic_launcher_monochrome.svg", circle_viewbox(layer.to_svg("black"), safe),
                   "adaptive icon monochrome layer (themed icons): art fitted inside the 66 dp safe circle of the 108 dp canvas")
        for density, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
            art = self.mark_at(px).to_svg("color", palette=on_primary)
            self._tile(f"android/mipmap-{density}/ic_launcher.png", px, art, 0.6, f"legacy launcher icon, {density}", primary)
        art = self.mark_at(512).to_svg("color", palette=on_primary)
        self._tile("play-store-icon-512.png", 512, art, 0.6, "Google Play listing icon: full square, no corners, no shadow", primary)

    def social(self) -> None:
        compact = self.outputs.get("compact")  # spec section 6.4 draws avatars with it, when the concept built one
        for size in (320, 400, 512, 720, 800):
            art = (compact or self.mark_at(size)).to_svg("color", palette=self.light)
            self._tile(f"avatar-{size}.png", size, art, 0.56, f"profile avatar {size}: art inside the 80% circle crop", self.light["paper"])

    def banners(self) -> None:
        svg = self.svg("horizontal", "color")  # never None: the horizontal chain ends at full-lockup
        for relpath, width, height, safe, purpose in (  # safe: the box (x, y, w, h) the logo stays inside; None, the whole banner
            ("banner-x-1500x500.png", 1500, 500, (0, 60, 1500, 380), "X header; top and bottom 60 px kept clear"),
            ("banner-linkedin-personal-1584x396.png", 1584, 396, None, "LinkedIn personal banner"),
            ("banner-linkedin-page-1512x256.png", 1512, 256, None, "LinkedIn page cover"),
            ("banner-youtube-2560x1440.png", 2560, 1440, (662, 551, 1235, 338), "YouTube channel art; logo inside the 1235x338 safe area"),
            ("banner-facebook-851x315.png", 851, 315, None, "Facebook page cover"),
            ("banner-bluesky-1500x500.png", 1500, 500, None, "Bluesky banner"),
        ):
            self._place(relpath, width, height, svg, 0.6, purpose, self.light["paper"], safe)

    def previews(self) -> None:
        svg = self.svg("horizontal", "color")
        for relpath, width, height, purpose in (("og-image-1200x630.png", 1200, 630, "Open Graph link preview"),
                                                ("x-card-1200x600.png", 1200, 600, "X summary_large_image card")):
            self._place(relpath, width, height, svg, 0.6, purpose, self.light["paper"])

    def commerce(self) -> None:
        for relpath, size, purpose in (("stripe-icon-512.png", 512, "Stripe branding icon"),
                                       ("gbp-logo-720.png", 720, "Google Business Profile logo")):
            self._tile(relpath, size, self.mark_at(size).to_svg("color", palette=self.light), 0.62, purpose, self.light["paper"])
        svg = self.svg("horizontal", "color")
        for relpath, width, height, purpose in (("email-signature-logo@2x.png", 400, 100, "email signature logo, shown at 200x50"),
                                                ("shopify-header-logo@2x.png", 800, 200, "Shopify header logo, shown at 400x100")):
            self._place(relpath, width, height, svg, 1.0, purpose, None)  # transparent, the logo as large as the canvas allows
        png = self.renderer.svg_to_png(svg, 1024)  # 1024 wide whatever the lockup's shape, as tall as its aspect makes it
        self.write("stripe-logo.png", png, "Stripe branding logo, 1024 wide", *image_size(png))

    def print_files(self) -> None:
        """Vector print files drawn from the kit's paths (pdfout), never through Chrome: an RGB, a CMYK and a black PDF of
        each named lockup, and a CMYK EPS of the primary lockup and of the mark. A wordmark the concept cannot draw is left
        out (mark() warns); every other lockup's chain ends at full-lockup."""
        naive = "naive values; confirm with the printer"
        for variant in PNG_VARIANTS:
            mark = self.mark(variant)
            if mark is None:
                continue
            for suffix, colour, palette, mode, about in (("rgb", "color", self.light, "rgb", "RGB, for screens and digital print"),
                                                         ("cmyk", "color", self.light, "cmyk", f"CMYK ({naive})"),
                                                         ("black", "black", None, "cmyk", "black only (100% K)")):
                relpath = f"{self.name}-{variant}-{suffix}.pdf"
                pdfout.mark_to_pdf(mark, self.pkg / relpath, colour, palette, mode, title=f"{self.state.name} logo, {variant}, {suffix}",
                                   author=self.state.name)
                self.register(relpath, f"{variant} vector PDF, {about}")
        for variant in ("primary", "mark"):
            relpath = f"{self.name}-{variant}-cmyk.eps"
            pdfout.mark_to_eps(self.mark(variant), self.pkg / relpath, "color", self.light, "cmyk")
            self.register(relpath, f"{variant} legacy CMYK EPS for old print vendors ({naive})")

    # ---- driver --------------------------------------------------------
    def build(self, renderer: Renderer | None = None) -> Manifest:
        """Run every group in GROUPS into package.tmp/ beside package/, write manifest.json, then swap it in for package/
        (_swap_in), so a failure anywhere leaves the previous package as it was. First it tidies what a killed build left
        behind. A file that cannot be written (an OSError) stops the build with a CliError, exit 3. self.pkg names
        package/ again afterwards. `renderer` draws the groups that render; a build of groups that never do (print_files)
        can go without one (the renderer property)."""
        package, staging, aside = self.brand_dir / "package", self.brand_dir / STAGING, self.brand_dir / ASIDE
        try:
            if aside.exists():  # a swap that was killed: the previous package comes back unless the new one made it in
                if package.exists():
                    shutil.rmtree(aside)
                else:
                    os.replace(aside, package)
            if staging.exists():  # a build that was killed
                shutil.rmtree(staging)
            staging.mkdir()
        except OSError as err:
            raise CliError(f"could not tidy or make {staging} for the build ({err})", code=EXIT_EXTERNAL) from err
        self._renderer, self.pkg = renderer, staging
        self.entries, self.warnings, self.skipped, self.built = [], [], {}, now_iso()
        try:
            for group in self.GROUPS:
                getattr(self, group)()
            manifest = Manifest(brand=self.state.name, slug=self.slug, built=self.built, inputs=self.inputs, files=self.entries,
                                warnings=self.warnings, skipped=self.skipped)
            (staging / "manifest.json").write_text(json.dumps(manifest.model_dump(), indent=2) + "\n", encoding="utf-8")
            _swap_in(staging, package, aside)
        except OSError as err:  # a file the groups or the manifest could not write (or read); _swap_in reports its own
            raise CliError(f"could not build the package ({err}); the previous package is kept", code=EXIT_EXTERNAL) from err
        finally:
            self.pkg = package
            shutil.rmtree(staging, ignore_errors=True)  # gone already after a swap; else the next build tidies what is left
        return manifest
