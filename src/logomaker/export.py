"""Export package builder (spec section 9). Each group writes files into the package and registers their manifest entries."""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
from pathlib import Path

from PIL import Image

from . import registry
from .audit import TIER_FALLBACKS
from .color import enrich_tokens, load_tokens
from .kit import concept as conceptlib
from .kit.mark import Mark
from .kit.shape import fmt
from .output import EXIT_EXTERNAL, EXIT_VERIFY, CliError
from .paths import ProjectPaths
from .raster import blank, encoded, image_size
from .render import VIEWBOX, Renderer
from .schemas import Manifest, ManifestEntry, now_iso
from .sheets import _first_present, _palettes_of, fit_size, jinja, pick_output

VARIANT_NAMES = ("primary", "horizontal", "stacked", "wordmark", "mark", "small", "favicon")
COLOURS = ("color", "reverse", "black", "white", "mono")
PNG_VARIANTS = ("primary", "horizontal", "stacked", "wordmark", "mark")
PNG_COLOURS = ("color", "reverse", "black", "white")
PNG_SIZES = (256, 512, 1024, 2048)
MASK_SAFE = 289  # centred in 512, its corners stay inside the maskable safe circle (radius 40% = 204.8 px)
REQUIRED_FINAL = ("concept.py", "params.json", "tokens.json", "rationale.md")
RASTERS = (".png", ".jpg", ".webp")  # written files that write() refuses when blank
STAGING, ASIDE = "package.tmp", "package.old.tmp"  # beside package/: the build in progress; the previous package mid-swap
# The outputs that draw each named variant, best first. primary is brand.json's primary lockup, then full-lockup.
CHAINS = {
    "horizontal": ("full-horizontal", "full-lockup"),
    "stacked": ("full-stacked", "full-lockup"),
    "wordmark": ("full-wordmark",),
    "mark": ("full-symbol", "full-lockup"),
    "small": ("small", *TIER_FALLBACKS["small"]),
    "favicon": ("favicon", *TIER_FALLBACKS["favicon"]),
}


def square_viewbox(svg: str, fraction: float) -> str:
    """Rewrite the viewBox to a square in which the artwork's longer side spans `fraction` of the side."""
    match = VIEWBOX.search(svg)
    x, y, w, h = (float(v) for v in match.group(1).replace(",", " ").split())
    side = max(w, h) / fraction
    view = (x + w / 2 - side / 2, y + h / 2 - side / 2, side, side)
    return svg.replace(match.group(0), f'viewBox="{" ".join(fmt(v) for v in view)}"', 1)


def _swap_in(staging: Path, package: Path, aside: Path) -> None:
    """Put `staging` in `package`'s place. The previous package moves to `aside` first, and back again if the new one
    cannot take its place, so neither move can lose it; `aside` is deleted once the new package is in."""
    moved_aside = False
    try:
        if package.exists():
            os.replace(package, aside)
            moved_aside = True
        os.replace(staging, package)
    except OSError as err:
        if moved_aside:
            os.replace(aside, package)
        raise CliError(f"could not move the new package into {package} ({err}); the previous package is kept",
                       code=EXIT_EXTERNAL) from err
    if moved_aside:
        shutil.rmtree(aside)


class PackageBuilder:
    GROUPS: list[str] = ["masters", "pngs", "flattened", "favicons"]

    def __init__(self, paths: ProjectPaths, slug: str, paper: str = "letter"):
        """Check final/ before anything renders: its four files, then an audit.json that vouches for the final mark as it
        is now (registry.audit_problems). Either refusal is a CliError, exit 2."""
        self.paths, self.slug, self.paper = paths, slug, paper
        self.state = registry.load_state(paths, slug)
        self.brand_dir = paths.brand(slug)
        self.final = self.brand_dir / "final"
        self.pkg = self.brand_dir / "package"
        for name in REQUIRED_FINAL:
            if not (self.final / name).is_file():
                raise CliError(f"final/{name} is missing; finish refinement (and write final/rationale.md) before packaging")
        problems = registry.audit_problems(paths, slug, self.final, "final/audit.json")
        if problems:
            raise CliError(f"packaging needs a passing audit of the final mark: {'; '.join(problems)} "
                           f"(run: logomaker concept run {slug} final)")
        self.outputs = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(self.final)))
        self.tokens = enrich_tokens(load_tokens(self.final / "tokens.json"))
        self.light, self.dark = _palettes_of(self.tokens)
        try:
            self.name = registry.slugify(self.state.name)  # the file prefix follows the brand's name
        except CliError:  # a name with no ASCII letters or digits to keep
            self.name = slug
        self.entries: list[ManifestEntry] = []
        self.warnings: list[str] = []
        self.skipped: dict[str, str] = {}
        self.renderer: Renderer | None = None

    # ---- helpers -------------------------------------------------------
    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def skip(self, group: str, reason: str) -> None:
        """Record that `group` could not run, and why; package build reports it as a warning."""
        self.skipped[group] = reason

    def mark(self, variant: str) -> Mark | None:
        """The output that draws `variant` (one of VARIANT_NAMES): the first in its chain that was built
        (sheets._first_present), with a warning when that is a fallback. None, with a warning, when the chain has nothing
        built; only the wordmark's can, since every other chain ends at full-lockup."""
        chain = (f"full-{self.state.primary_lockup}", "full-lockup") if variant == "primary" else CHAINS[variant]
        name = _first_present(self.outputs, chain)
        if name not in chain:  # _first_present's own fallback, full-lockup, which the wordmark's chain leaves out
            self.warn(f"{variant} skipped: the concept has no {chain[0]}")
            return None
        if name != chain[0]:
            advice = "draw a dedicated tier for better small sizes" if variant in TIER_FALLBACKS else f"the concept has no {chain[0]}"
            self.warn(f"{variant} falls back to {name} ({advice})")
        return self.outputs[name]

    def mark_at(self, size: int) -> Mark:
        """The output that draws the mark `size` px across, as sheets.pick_output picks it: full-symbol from 96 px, small
        down to 33 px, favicon below, each falling back to the next larger build."""
        return self.outputs[pick_output(self.outputs, size)]

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

    def _refuse_blank(self, name: str, raster: bytes) -> None:
        """Stop the build with exit 4, naming `name`, when `raster` shows nothing (raster.blank)."""
        if blank(raster):
            raise CliError(f"{name} came out blank: its render drew nothing", code=EXIT_VERIFY)

    def write(self, relpath: str, data: bytes | str, purpose: str, width: int | None = None, height: int | None = None) -> Path:
        """Write `data` to `relpath` in the package and add its manifest entry. A raster (RASTERS) that came out blank
        stops the build with exit 4 instead."""
        raw = data.encode("utf-8") if isinstance(data, str) else data
        if Path(relpath).suffix in RASTERS:
            self._refuse_blank(relpath, raw)
        target = self.pkg / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        self.entries.append(self._entry(relpath, raw, purpose, width, height))
        return target

    def render_fit(self, svg: str, box_w: int, box_h: int, background: str | None = None) -> bytes:
        """`svg` rendered as large as fits a `box_w` x `box_h` box, keeping its aspect (sheets.fit_size)."""
        return self.renderer.svg_to_png(svg, *fit_size(svg, box_w, box_h), background=background)

    def png_bytes(self, svg: str, long_edge: int) -> bytes:
        """`svg` rendered on transparent with its longer side `long_edge` px."""
        return self.render_fit(svg, long_edge, long_edge)

    @staticmethod
    def compose(width: int, height: int, background: str | None, art: bytes | None = None,
                box: tuple[int, int, int, int] | None = None) -> bytes:
        """A `width` x `height` PNG on `background` (transparent when None) with `art`, a PNG, centred in `box` (x, y, w,
        h; the whole canvas by default) and shrunk to fit it if it is larger."""
        canvas = Image.new("RGBA", (width, height), background or (0, 0, 0, 0))
        if art is not None:
            with Image.open(io.BytesIO(art)) as opened:
                image = opened.convert("RGBA")
            bx, by, bw, bh = box or (0, 0, width, height)
            scale = min(bw / image.width, bh / image.height, 1.0)
            if scale < 1.0:
                image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
            canvas.alpha_composite(image, (bx + (bw - image.width) // 2, by + (bh - image.height) // 2))
        return encoded(canvas, "PNG")

    @staticmethod
    def _centered(size_w: int, size_h: int, art_w: int, art_h: int) -> tuple[int, int, int, int]:
        """The (x, y, w, h) box of an `art_w` x `art_h` area centred on a `size_w` x `size_h` canvas."""
        return (size_w - art_w) // 2, (size_h - art_h) // 2, art_w, art_h

    def _tile(self, relpath: str, size: int, art_svg: str, fraction: float, purpose: str, background: str | None) -> None:
        """Write a `size` px square PNG on `background`: `art_svg` rendered to `fraction` of the side, centred."""
        side = round(size * fraction)
        art = self.render_fit(art_svg, side, side)
        self.write(relpath, self.compose(size, size, background, art, self._centered(size, size, side, side)), purpose, size, size)

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
        svg = self.svg("primary", "color")
        if svg is None:
            self.skip("flattened", "the concept has no primary lockup")
            return
        with Image.open(io.BytesIO(self.png_bytes(svg, 2048))) as opened:
            image = opened.convert("RGBA")
        white = Image.alpha_composite(Image.new("RGBA", image.size, "#ffffff"), image).convert("RGB")
        self.write(f"{self.name}-primary-color-white-bg-2048.jpg", encoded(white, "JPEG", quality=92),
                   "primary on a white background, flattened JPEG", *image.size)
        self.write(f"{self.name}-primary-color-2048.webp", encoded(image, "WEBP", quality=90), "primary colour transparent WebP",
                   *image.size)

    def favicons(self) -> None:
        frames = []
        for size in (48, 32, 16):  # each frame drawn by the tier for its own size, and checked before the ICO packs it
            png = self.render_fit(square_viewbox(self.mark_at(size).to_svg("color", palette=self.light), 0.9), size, size)
            self._refuse_blank(f"favicon.ico ({size} px frame)", png)
            with Image.open(io.BytesIO(png)) as frame:
                frames.append(frame.convert("RGBA"))
        self.write("favicon.ico", encoded(frames[0], "ICO", sizes=[(48, 48), (32, 32), (16, 16)], append_images=frames[1:]),
                   "legacy favicon, 16/32/48", 48, 48)
        favicon = self.mark("favicon")  # the favicon master, plus a style that switches to the dark roles
        self.write("icon.svg", square_viewbox(favicon.to_svg("color", palette=self.light, dark_palette=self.dark), 0.9),
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

    # ---- driver --------------------------------------------------------
    def build(self, renderer: Renderer) -> Manifest:
        """Run every group in GROUPS into package.tmp/ beside package/, write manifest.json, then swap it in for package/
        (_swap_in), so a failure anywhere leaves the previous package as it was. First it tidies what a killed build left
        behind. self.pkg names package/ again afterwards."""
        package, staging, aside = self.brand_dir / "package", self.brand_dir / STAGING, self.brand_dir / ASIDE
        if aside.exists():  # a swap that was killed: the previous package comes back unless the new one made it in
            if package.exists():
                shutil.rmtree(aside)
            else:
                os.replace(aside, package)
        if staging.exists():  # a build that was killed
            shutil.rmtree(staging)
        staging.mkdir()
        self.renderer, self.pkg = renderer, staging
        self.entries, self.warnings, self.skipped = [], [], {}
        try:
            for group in self.GROUPS:
                getattr(self, group)()
            manifest = Manifest(brand=self.state.name, slug=self.slug, built=now_iso(), files=self.entries, warnings=self.warnings,
                                skipped=self.skipped)
            (staging / "manifest.json").write_text(json.dumps(manifest.model_dump(), indent=2) + "\n", encoding="utf-8")
            _swap_in(staging, package, aside)
        finally:
            self.pkg = package
            if staging.exists():
                shutil.rmtree(staging)
        return manifest
