"""Export package builder (spec section 9). Each group writes files into the package and registers their manifest entries;
verify() checks a built package against its manifest."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
from functools import cached_property
from pathlib import Path

from PIL import Image

from . import fonts as fontlib
from . import pdfout, registry
from .audit import TIER_FALLBACKS, text_roles
from .color import CheckResult, check_tokens, enrich_tokens, load_tokens
from .kit import concept as conceptlib
from .kit.mark import ROLES, Mark
from .kit.shape import fmt
from .kit.text import TextShape
from .output import EXIT_EXTERNAL, EXIT_VERIFY, CliError
from .paths import ProjectPaths
from .raster import blank, encoded, image_size
from .render import VIEWBOX, Renderer
from .schemas import Manifest, ManifestEntry, now_iso
from .sheets import X_RULES, _chip_text, _first_present, _palettes_of, clear_space_svg, fit_box, fit_size, jinja, size_tier

VARIANT_NAMES = ("primary", "horizontal", "stacked", "wordmark", "mark", "small", "favicon")
COLOURS = ("color", "reverse", "black", "white", "mono")
PNG_VARIANTS = ("primary", "horizontal", "stacked", "wordmark", "mark")
PNG_COLOURS = ("color", "reverse", "black", "white")
PNG_SIZES = (256, 512, 1024, 2048)
MASK_SAFE = 289  # centred in 512, its corners stay inside the maskable safe circle (radius 40% = 204.8 px)
ADAPTIVE_SAFE = 466  # of the adaptive icon's 1080 units: centred, its corners stay inside the 66 dp safe circle (660 / √2 = 466.7)
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
# The variant whose chain (CHAINS) is the one sheets.size_tier gives a size, by that chain's first output.
TIER_VARIANTS = {"full-symbol": "mark", "small": "small", "favicon": "favicon"}
FONT = re.compile(r"(.+) (\d+(?:\.\d+)?(?: italic)?)")  # a kit.text.TextShape.font: family, the weight drawn, " italic" for an italic file
# README.md's sections. The brand's own files (<prefix>-<variant>-...) go by suffix; then every other file by its name's start.
BRAND_SECTIONS = {".svg": "SVG masters", ".png": "PNG exports", ".jpg": "Flattened", ".webp": "Flattened", ".pdf": "Print", ".eps": "Print"}
PREFIX_SECTIONS = (
    (("favicon", "icon", "apple-touch", "manifest.webmanifest"), "Favicons and web app icons"),
    (("ios-", "app-icon-layers"), "Apple app icon"),
    (("android", "play-store"), "Android"),
    (("avatar", "banner", "og-image", "x-card"), "Social"),
    (("email-", "shopify-", "stripe-", "gbp-"), "Email and commerce"),
    (("fonts/",), "Fonts"),
    (("source/",), "Source"),
)


def square_viewbox(svg: str, fraction: float) -> str:
    """Rewrite the viewBox to a square in which the artwork's longer side spans `fraction` of the side."""
    match = VIEWBOX.search(svg)
    x, y, w, h = (float(v) for v in match.group(1).replace(",", " ").split())
    side = max(w, h) / fraction
    view = (x + w / 2 - side / 2, y + h / 2 - side / 2, side, side)
    return svg.replace(match.group(0), f'viewBox="{" ".join(fmt(v) for v in view)}"', 1)


def square_fill(side: int, colour: str) -> str:
    """A `side`-unit square SVG filled with `colour`, drawn as a path: every SVG in the package is paths only."""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side} {side}"><path d="M0 0H{side}V{side}H0Z" fill="{colour}"/></svg>'


def font_style(font: str) -> tuple[str, str]:
    """The family and the style of a kit.text.TextShape.font such as "Fira Code 600" or "Playfair Display 700 italic":
    the family is everything before the weight, the style the weight and " italic" for an italic file."""
    match = FONT.fullmatch(font)
    return (match[1], match[2]) if match else (font, "")


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
    GROUPS: list[str] = ["masters", "pngs", "flattened", "favicons", "apple", "android", "social", "banners", "previews", "commerce",
                         "print_files", "tokens_file", "fonts", "docs", "readme"]

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
        """The output that draws the mark `size` px across: the first built in sheets.size_tier(size), the chain
        sheets.pick_output follows (full-symbol from 96 px, small down to 33 px, favicon below). It resolves through
        mark(), so a fallback warns. Never None: mark() returns None only for a chain with nothing built, and each of
        these ends at full-lockup, which every build has."""
        mark = self.mark(TIER_VARIANTS[size_tier(size)[0]])
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

    def _refuse_blank(self, name: str, raster: bytes, *, opaque: bool) -> None:
        """Stop the build with exit 4, naming `name`, when `raster` shows nothing (raster.blank): a render on transparent
        when no pixel is drawn, an `opaque` one, composed onto a background, when it is one flat colour."""
        if blank(raster, opaque=opaque):
            raise CliError(f"{name} came out blank: its render drew nothing", code=EXIT_VERIFY)

    def write(self, relpath: str, data: bytes | str, purpose: str, width: int | None = None, height: int | None = None, *,
              opaque: bool = False) -> Path:
        """Write `data` to `relpath` in the package and add its manifest entry. A raster (RASTERS) that came out blank
        stops the build with exit 4 instead: `opaque` when it was composed onto a background, else a render on
        transparent (_refuse_blank)."""
        raw = data.encode("utf-8") if isinstance(data, str) else data
        if Path(relpath).suffix in RASTERS:
            self._refuse_blank(relpath, raw, opaque=opaque)
        target = self.pkg / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        self.entries.append(self._entry(relpath, raw, purpose, width, height))
        return target

    def register(self, relpath: str, purpose: str, width: int | None = None, height: int | None = None) -> None:
        """Add the manifest entry of `relpath`, a file already in the package that write() did not write (pdfout's)."""
        self.entries.append(self._entry(relpath, (self.pkg / relpath).read_bytes(), purpose, width, height))

    def render_fit(self, svg: str, box_w: int, box_h: int, background: str | None = None) -> bytes:
        """`svg` rendered as large as fits a `box_w` x `box_h` box, keeping its aspect (sheets.fit_size)."""
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
        (exit 4) before it is composed: on one flat colour the composite would be refused too, on a surface of several
        colours it would not. alpha=False writes the PNG without an alpha channel (compose)."""
        bx, by, bw, bh = safe or (0, 0, width, height)
        art_w, art_h = round(bw * fraction), round(bh * fraction)
        art = self.render_fit(art_svg, art_w, art_h)
        self._refuse_blank(f"{relpath} (art)", art, opaque=False)
        x, y, _, _ = self._centered(bw, bh, art_w, art_h)
        self.write(relpath, self.compose(width, height, background, art, (bx + x, by + y, art_w, art_h), alpha), purpose, width, height,
                   opaque=background is not None)

    def _on_primary(self) -> dict[str, str]:
        """The palette of art on a primary-colour tile: every role, paper too, in the light paper colour (as the concept
        sheet draws its app icon)."""
        return {role: self.light["paper"] for role in (*ROLES, "paper")}

    @cached_property
    def checks(self) -> CheckResult:
        """The tokens' contrast and colour-vision checks, type held to the text thresholds as the audit holds it; computed
        once, for tokens.json and the documents."""
        return check_tokens(self.tokens, text_roles=text_roles(self.outputs))

    @cached_property
    def typefaces(self) -> list[dict]:
        """Each font family the brand uses, once (by fonts.family_slug), sorted by name: those brand.json's fonts name and
        those its type is set in (the wordmark's and tagline's TextShape.font in every output). Each carries its weights
        (brand.json's when it names the family, else those the type was set in), its licence from the font catalogue
        (looked up here, once, for the fonts group and the documents), its cache slug and whether it is cached."""
        names: dict[str, str] = {}  # slug -> the family as first named
        chosen: dict[str, list[str]] = {}
        drawn: dict[str, list[str]] = {}
        for choice in self.state.fonts.values():
            slug = fontlib.family_slug(choice.family)
            names.setdefault(slug, choice.family)
            chosen.setdefault(slug, []).append(f"{choice.weight}{' italic' if choice.italic else ''}")
        for part in (p for mark in self.outputs.values() for p in (mark.wordmark, mark.tagline) if isinstance(p, TextShape)):
            family, style = font_style(part.font)
            slug = fontlib.family_slug(family)
            names.setdefault(slug, family)
            drawn.setdefault(slug, []).append(style)
        faces = []
        for slug, family in names.items():
            entry = fontlib.find_family(self.paths, family)
            weights = dict.fromkeys(chosen.get(slug) or drawn[slug])
            faces.append({"family": entry.family if entry else family, "slug": slug, "weight": "/".join(weights),
                          "license": entry.license if entry else "see licence file",
                          "cached": bool(fontlib.cached_files(self.paths, family))})
        return sorted(faces, key=lambda face: face["family"])

    def font_families(self) -> list[str]:
        """The font families the brand uses, sorted (typefaces)."""
        return [face["family"] for face in self.typefaces]

    def _roles(self, context: str) -> str:
        """Each role of `context`, paper last, with its colour's name: "primary: Ember, ink: Coal, paper: Paper"."""
        roles = {**self.tokens.roles[context], "paper": self.tokens.paper[context]}
        return ", ".join(f"{role}: {self.tokens.colors[key].name}" for role, key in roles.items())

    def doc_context(self) -> dict:
        """What BRAND.md and the brand sheet say: the x rule as Mark.x_unit_source names it (sheets.X_RULES), each colour
        with the label colour the sheets give its chip, the roles, the contrast rows (checks), the typefaces, the web head
        snippet from favicon-head.html (a warning when the package has none), the rationale and the logo system's SVGs
        sized for the sheet."""
        lockup = self.outputs["full-lockup"]
        head = self.pkg / "favicon-head.html"
        if not head.is_file():
            self.warn("BRAND.md has no web head snippet: favicon-head.html is not in the package")

        def fitted(variant: str, colour: str, box_w: int, box_h: int) -> str:
            svg = self.svg(variant, colour)
            return fit_box(svg, box_w, box_h) if svg else ""

        return {
            "brand": self.state.name, "slug": self.slug, "prefix": self.name, "primary_lockup": self.state.primary_lockup,
            "has_wordmark": "full-wordmark" in self.outputs, "x_unit": round(lockup.x_unit, 1), "x_rule": X_RULES[lockup.x_unit_source],
            "ms": self.state.min_sizes, "roles_light": self._roles("light"), "roles_dark": self._roles("dark"),
            "colours": [{"key": key, **c.model_dump(), "text": _chip_text(c.hex)} for key, c in self.tokens.colors.items()],
            "contrast": [row.model_dump() for row in self.checks.contrast], "fonts": self.typefaces,
            "head_snippet": head.read_text(encoding="utf-8") if head.is_file() else "",
            "rationale": (self.final / "rationale.md").read_text(encoding="utf-8").strip(),
            "sheet": {"primary": fitted("primary", "color", 240, 100), "reverse": fitted("primary", "reverse", 240, 100),
                      "stacked": fitted("stacked", "color", 100, 100), "mark": fitted("mark", "color", 70, 100),
                      "small": fitted("small", "color", 44, 100), "favicon": fitted("favicon", "color", 32, 100),
                      "clear_space": fit_box(clear_space_svg(self.mark("primary"), lockup.x_unit), 300, 110)},
            "paper_light": self.light["paper"], "paper_dark": self.dark["paper"],
        }

    def _section(self, path: str) -> str:
        """The README.md section of package file `path`. The brand's own files, named <prefix>-<variant>-..., go by suffix
        (BRAND_SECTIONS), so brand-sheet.pdf is no print file and a brand named like a platform file (Icon Works) keeps its
        own; then every other file by its name's start (PREFIX_SECTIONS); the rest are documents."""
        suffix = Path(path).suffix
        if path.startswith(tuple(f"{self.name}-{variant}-" for variant in VARIANT_NAMES)) and suffix in BRAND_SECTIONS:
            return BRAND_SECTIONS[suffix]
        return next((section for starts, section in PREFIX_SECTIONS if path.startswith(starts)), "Documents and tokens")

    def _groups(self) -> list[tuple[str, list[ManifestEntry]]]:
        """The entries written so far by README.md section (_section), the sections in the order their first file came."""
        groups: dict[str, list[ManifestEntry]] = {}
        for entry in self.entries:
            groups.setdefault(self._section(entry.path), []).append(entry)
        return list(groups.items())

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
                   "primary on a white background, flattened JPEG", *image.size, opaque=True)
        self.write(f"{self.name}-primary-color-2048.webp", encoded(image, "WEBP", quality=90), "primary colour transparent WebP",
                   *image.size)

    def favicons(self) -> None:
        frames = []
        for size in (48, 32, 16):  # each frame drawn by the tier for its own size, and checked before the ICO packs it
            png = self.render_fit(square_viewbox(self.mark_at(size).to_svg("color", palette=self.light), 0.9), size, size)
            self._refuse_blank(f"favicon.ico ({size} px frame)", png, opaque=False)
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
        self.write("android/ic_launcher_foreground.svg", square_viewbox(layer.to_svg("color", palette=on_primary), ADAPTIVE_SAFE / 1080),
                   "adaptive icon foreground: art fitted inside the 66 dp safe circle of the 108 dp canvas")
        self.write("android/ic_launcher_background.svg", square_fill(1080, primary), "adaptive icon background layer, 1080-unit canvas")
        self.write("android/ic_launcher_monochrome.svg", square_viewbox(layer.to_svg("black"), ADAPTIVE_SAFE / 1080),
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
        svg = self.svg("horizontal", "color")
        if svg is None:
            self.skip("banners", "the concept has no horizontal lockup")
            return
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
        if svg is None:
            self.skip("previews", "the concept has no horizontal lockup")
            return
        for relpath, width, height, purpose in (("og-image-1200x630.png", 1200, 630, "Open Graph link preview"),
                                                ("x-card-1200x600.png", 1200, 600, "X summary_large_image card")):
            self._place(relpath, width, height, svg, 0.6, purpose, self.light["paper"])

    def commerce(self) -> None:
        for relpath, size, purpose in (("stripe-icon-512.png", 512, "Stripe branding icon"),
                                       ("gbp-logo-720.png", 720, "Google Business Profile logo")):
            self._tile(relpath, size, self.mark_at(size).to_svg("color", palette=self.light), 0.62, purpose, self.light["paper"])
        svg = self.svg("horizontal", "color")
        if svg is None:
            self.skip("commerce", "the concept has no horizontal lockup for the email, Shopify and Stripe logos")
            return
        for relpath, width, height, purpose in (("email-signature-logo@2x.png", 400, 100, "email signature logo, shown at 200x50"),
                                                ("shopify-header-logo@2x.png", 800, 200, "Shopify header logo, shown at 400x100")):
            self._place(relpath, width, height, svg, 1.0, purpose, None)  # transparent, the logo as large as the canvas allows
        png = self.renderer.svg_to_png(svg, 1024)  # 1024 wide whatever the lockup's shape, as tall as its aspect makes it
        self.write("stripe-logo.png", png, "Stripe branding logo, 1024 wide", *image_size(png))

    def print_files(self) -> None:
        """Vector print files drawn from the kit's paths (pdfout), never through Chrome: an RGB, a CMYK and a black PDF of
        each named lockup, and a CMYK EPS of the primary lockup and of the mark. A lockup the concept cannot draw is left
        out (mark() warns); when it can draw none, the group is skipped."""
        printed = False
        for variant in PNG_VARIANTS:
            mark = self.mark(variant)
            if mark is None:
                continue
            for suffix, colour, palette, mode in (("rgb", "color", self.light, "rgb"), ("cmyk", "color", self.light, "cmyk"),
                                                  ("black", "black", None, "cmyk")):
                relpath = f"{self.name}-{variant}-{suffix}.pdf"
                pdfout.mark_to_pdf(mark, self.pkg / relpath, colour, palette, mode)
                self.register(relpath, f"{variant} vector PDF, {suffix} (CMYK values are naive; confirm with the printer)")
            printed = True
        for variant in ("primary", "mark"):
            mark = self.mark(variant)
            if mark is None:
                continue
            relpath = f"{self.name}-{variant}-cmyk.eps"
            pdfout.mark_to_eps(mark, self.pkg / relpath, "color", self.light, "cmyk")
            self.register(relpath, f"{variant} legacy EPS for old print vendors")
            printed = True
        if not printed:
            self.skip("print_files", "the concept has no lockup to print")

    def tokens_file(self) -> None:
        """tokens.json: final/'s tokens in every notation (enrich_tokens), with the contrast rows, colour-vision pairs and
        palettes of checks."""
        data = {**self.tokens.model_dump(), "contrast": [row.model_dump() for row in self.checks.contrast],
                "cvd": [row.model_dump() for row in self.checks.cvd], "palettes": self.checks.palettes}
        self.write("tokens.json", json.dumps(data, indent=2) + "\n",
                   "design tokens: every colour in HEX, RGB, HSL, OKLCH and CMYK, role maps, contrast and colour-vision results")

    def fonts(self) -> None:
        """Each family the brand uses (typefaces): its TTFs and licence file copied from the font cache into fonts/<slug>/,
        and its line in fonts/FONT-NOTICE.md. A family that is not cached is left out with a `fonts fetch` warning."""
        notice = ["# Fonts", "", "Deliverable SVGs and PDFs are outlined, so they need no fonts. These files are for new material.", ""]
        for face in self.typefaces:
            family = face["family"]
            if not face["cached"]:
                self.warn(f'font {family} is not cached and was not copied; run logomaker fonts fetch "{family}"')
                continue
            for path in sorted(fontlib.family_dir(self.paths, family).iterdir()):
                if path.suffix == ".ttf" or path.name in fontlib.LICENCE_FILES:
                    kind = "font file" if path.suffix == ".ttf" else "licence"
                    self.write(f"fonts/{face['slug']}/{path.name}", path.read_bytes(), f"{family} {kind}")
            notice.append(f"- {family}: {face['license']}. Logo use is permitted; keep the licence file with the font.")
        self.write("fonts/FONT-NOTICE.md", "\n".join(notice) + "\n", "font licences and usage note")

    def docs(self) -> None:
        """BRAND.md, rationale.md, source/ and brand-sheet.pdf, the one-page sheet printed through Chrome. source/ holds what
        rebuilds the package (README.md says how): final/'s four files, brand.json and strategy.json; one that is missing
        is left out with a warning naming it."""
        env = jinja(self.paths)
        ctx = self.doc_context()
        self.write("BRAND.md", env.get_template("brand.md.j2").render(**ctx), "brand guidelines")
        self.write("rationale.md", ctx["rationale"] + "\n", "one-paragraph rationale")
        for origin in (*(f"final/{name}" for name in REQUIRED_FINAL), "brand.json", "strategy.json"):
            source = self.brand_dir / origin
            if source.is_file():
                self.write(f"source/{source.name}", source.read_bytes(), f"regenerable source, from brands/{self.slug}/{origin}")
            else:
                self.warn(f"source/{source.name} left out: brands/{self.slug}/{origin} is missing")
        html = env.get_template("brand-sheet.html").render(**ctx)
        self.write("brand-sheet.pdf", self.renderer.html_to_pdf(html, self.paper), "one-page brand sheet")

    def readme(self) -> None:
        """README.md, the package's index by section (_groups). It runs last, so it lists every file but itself and
        manifest.json, which its template lists."""
        index = jinja(self.paths).get_template("readme.md.j2").render(brand=self.state.name, slug=self.slug, built=now_iso(),
                                                                      groups=self._groups())
        self.write("README.md", index, "file index")

    # ---- driver --------------------------------------------------------
    def build(self, renderer: Renderer | None = None) -> Manifest:
        """Run every group in GROUPS into package.tmp/ beside package/, write manifest.json, then swap it in for package/
        (_swap_in), so a failure anywhere leaves the previous package as it was. First it tidies what a killed build left
        behind. self.pkg names package/ again afterwards. `renderer` draws the groups that render; a build of groups that
        never do (print_files) can go without one (the renderer property)."""
        package, staging, aside = self.brand_dir / "package", self.brand_dir / STAGING, self.brand_dir / ASIDE
        if aside.exists():  # a swap that was killed: the previous package comes back unless the new one made it in
            if package.exists():
                shutil.rmtree(aside)
            else:
                os.replace(aside, package)
        if staging.exists():  # a build that was killed
            shutil.rmtree(staging)
        staging.mkdir()
        self._renderer, self.pkg = renderer, staging
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


def verify(paths: ProjectPaths, slug: str) -> dict:
    """Check brands/<slug>/package/ against its manifest.json and write the result to package/verify.json, which the done
    gate reads: each file is there, not empty and unchanged (its sha256), each raster is the size the manifest gives (an
    ICO by its largest frame, which Pillow opens), and README.md lists each in a table row. The result holds ok, problems
    (in manifest order), files and checked_at. An unknown brand is a CliError (exit 2), a missing or invalid manifest
    exit 4."""
    registry.load_state(paths, slug)  # an unknown brand stops here, not at the manifest it lacks
    pkg = paths.brand(slug) / "package"
    if not (pkg / "manifest.json").is_file():
        raise CliError("package/manifest.json is missing; run logomaker package build first", code=EXIT_VERIFY)
    manifest = registry.load_model(pkg / "manifest.json", Manifest, "package/manifest.json", code=EXIT_VERIFY)
    readme = pkg / "README.md"
    index = readme.read_text(encoding="utf-8") if readme.is_file() else None  # a missing one is reported by its own entry
    problems: list[str] = []
    for entry in manifest.files:
        path = pkg / entry.path
        if not path.is_file():
            problems.append(f"{entry.path} is missing")
            continue
        raw = path.read_bytes()
        if not raw:
            problems.append(f"{entry.path} is empty")
            continue
        if hashlib.sha256(raw).hexdigest() != entry.sha256:
            problems.append(f"{entry.path} changed since the build")
        if entry.width and path.suffix in (*RASTERS, ".ico"):
            try:
                width, height = image_size(raw)
            except OSError:  # Pillow cannot read it as an image
                problems.append(f"{entry.path} is not a readable image")
            else:
                if (width, height) != (entry.width, entry.height):
                    problems.append(f"{entry.path} is {width}x{height}, expected {entry.width}x{entry.height}")
        if index is not None and f"| `{entry.path}` |" not in index:
            problems.append(f"README.md does not list {entry.path}")
    result = {"ok": not problems, "problems": problems, "files": len(manifest.files), "checked_at": now_iso()}
    (pkg / "verify.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
