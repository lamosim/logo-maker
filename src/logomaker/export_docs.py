"""The package's documents (spec section 9): tokens.json, the fonts, BRAND.md, rationale.md, source/, the brand sheet and
the README index, written by DocumentGroups, which PackageBuilder mixes in; and verify(), which checks a built package
against its manifest and against the brand's inputs now (inputs_fingerprint).

export imports this module to mix DocumentGroups in, so what this one needs from export it imports where it uses it."""
from __future__ import annotations

import hashlib
import json
import re
from functools import cached_property
from pathlib import Path

from . import fonts as fontlib
from . import registry
from .audit import digest, text_roles
from .color import CheckResult, check_tokens, chip_text
from .kit.text import TextShape
from .output import EXIT_VERIFY, CliError
from .paths import ProjectPaths
from .raster import image_size
from .render import fit_box
from .schemas import Manifest, ManifestEntry, now_iso
from .sheets import X_RULES, clear_space_svg, jinja

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
# What source/ holds, from the brand folder: what rebuilds the package (README.md says how).
SOURCE_FILES = ("final/concept.py", "final/params.json", "final/tokens.json", "final/rationale.md", "brand.json", "strategy.json")


def font_style(font: str) -> tuple[str, str]:
    """The family and the style of a kit.text.TextShape.font such as "Fira Code 600" or "Playfair Display 700 italic":
    the family is everything before the weight, the style the weight and " italic" for an italic file."""
    match = FONT.fullmatch(font)
    return (match[1], match[2]) if match else (font, "")


def readme_row(path: str, *cells: str) -> str:
    """A row of README.md's file tables: the file's path in code, then `cells`. README.md writes every row with it, and
    verify finds a file listed by readme_row(path), the start of its row."""
    return "| " + " | ".join((f"`{path}`", *cells)) + " |"


class DocumentGroups:
    """PackageBuilder's document groups (tokens_file, fonts, docs, readme) and what they share. A mixin: it reads the
    builder's paths, slug, state, brand_dir, final, pkg, paper, outputs, tokens, light, dark, name and entries, and
    works through its write(), warn(), mark(), svg() and renderer."""

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
            "colours": [{"key": key, **c.model_dump(), "text": chip_text(c.hex)} for key, c in self.tokens.colors.items()],
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
        from .export import VARIANT_NAMES  # imported here: export imports this module

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
        rebuilds the package (SOURCE_FILES; README.md says how); a file that is missing is left out with a warning naming
        it."""
        env = jinja(self.paths)
        ctx = self.doc_context()
        self.write("BRAND.md", env.get_template("brand.md.j2").render(**ctx), "brand guidelines")
        self.write("rationale.md", ctx["rationale"] + "\n", "one-paragraph rationale")
        for origin in SOURCE_FILES:
            source = self.brand_dir / origin
            if source.is_file():
                self.write(f"source/{source.name}", source.read_bytes(), f"regenerable source, from brands/{self.slug}/{origin}")
            else:
                self.warn(f"source/{source.name} left out: brands/{self.slug}/{origin} is missing")
        html = env.get_template("brand-sheet.html").render(**ctx)
        self.write("brand-sheet.pdf", self.renderer.html_to_pdf(html, self.paper), "one-page brand sheet")

    def readme(self) -> None:
        """README.md, the package's index by section (_groups), each file in a readme_row. It runs last, so it lists
        every file but itself and manifest.json, which its template lists."""
        index = jinja(self.paths).get_template("readme.md.j2").render(brand=self.state.name, slug=self.slug, built=now_iso(),
                                                                      groups=self._groups(), row=readme_row)
        self.write("README.md", index, "file index")


def inputs_fingerprint(paths: ProjectPaths, slug: str) -> str:
    """sha256 (hex) of what a package build reads (audit.digest): the SOURCE_FILES (final/'s concept.py, params.json,
    tokens.json and rationale.md and the brand's strategy.json), each when present, but brand.json, of which only name,
    primary_lockup, min_sizes and fonts enter, as canonical JSON (its other fields, such as phase or updated, change
    without changing the package). The manifest records it; verify and the done gate compare it with the current one."""
    state = registry.load_state(paths, slug)
    brand = paths.brand(slug)
    settings = state.model_dump(mode="json", include={"name", "primary_lockup", "min_sizes", "fonts"})
    files = [name for name in SOURCE_FILES if name != "brand.json"]
    entries = [(name, (brand / name).read_bytes()) for name in files if (brand / name).is_file()]
    return digest([*entries, ("brand settings", json.dumps(settings, sort_keys=True).encode())])


def out_of_date(slug: str) -> str:
    """The problem verify and the done gate report when the package was built from other inputs than the brand's now."""
    return f"package is out of date (final/ or the brand changed since the build); run: logomaker package build {slug}"


def verify(paths: ProjectPaths, slug: str) -> dict:
    """Check brands/<slug>/package/ against its manifest.json and write the result to package/verify.json, which the done
    gate reads: the package was built from final/ and the brand as they are now (the manifest's inputs fingerprint is
    inputs_fingerprint's), each file is there, not empty and unchanged (its sha256), each raster is the size the manifest
    gives (an ICO by its largest frame, which Pillow opens), and README.md lists each in a table row (a README.md that
    is not UTF-8 is a problem of its own). The result holds
    ok, problems (the out-of-date one first, then the files' in manifest order), files, the manifest's inputs and
    checked_at. An unknown brand is a CliError (exit 2), a missing or invalid manifest exit 4."""
    from .export import RASTERS  # imported here: export imports this module

    registry.load_state(paths, slug)  # an unknown brand stops here, not at the manifest it lacks
    pkg = paths.brand(slug) / "package"
    if not (pkg / "manifest.json").is_file():
        raise CliError(f"package/manifest.json is missing (run: logomaker package build {slug})", code=EXIT_VERIFY)
    manifest = registry.load_model(pkg / "manifest.json", Manifest, "package/manifest.json", code=EXIT_VERIFY)
    problems: list[str] = []
    if manifest.inputs != inputs_fingerprint(paths, slug):
        problems.append(out_of_date(slug))
    readme, index = pkg / "README.md", None  # a missing README.md is reported by its own entry
    if readme.is_file():
        try:
            index = readme.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append("README.md is not UTF-8 text, so the files it lists cannot be checked")
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
        if index is not None and readme_row(entry.path) not in index:
            problems.append(f"README.md does not list {entry.path}")
    result = {"ok": not problems, "problems": problems, "files": len(manifest.files), "inputs": manifest.inputs,
              "checked_at": now_iso()}
    (pkg / "verify.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
