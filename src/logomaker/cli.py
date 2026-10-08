"""Click entry points. Every command ends in output.emit().

The heavy modules (the kit, audit, sheets, render, color, fonts) are imported inside the commands that use them, so
`setup --check` still runs, and reports, when one of their dependencies is missing. names loads with the CLI, for the
defaults its help shows, and imports httpx only when a lookup runs.
"""
from __future__ import annotations

import functools
import importlib
import platform
import subprocess
import sys
import traceback
from pathlib import Path

import click

from . import __version__, registry
from . import names as nameslib  # light: httpx is imported only when a lookup runs
from .output import EXIT_EXTERNAL, EXIT_RULE, EXIT_VERIFY, CliError, emit
from .paths import project
from .schemas import Phase

MODULES = ["skia", "fontTools", "uharfbuzz", "coloraide", "reportlab", "playwright", "PIL", "numpy", "scipy", "jinja2", "httpx", "pydantic",
           "pypdf"]


def command(fn):
    """Wrap a command so every exception becomes a JSON failure with the right exit code."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except SystemExit:
            raise
        except CliError as err:
            emit(err.data, ok=False, errors=[str(err)], code=err.code)
        except Exception as err:  # noqa: BLE001 - the CLI contract is JSON, never a traceback
            emit({"traceback": traceback.format_exc()}, ok=False, errors=[f"{type(err).__name__}: {err}"], code=EXIT_RULE)

    return wrapper


class JsonGroup(click.Group):
    """Click group whose usage errors (unknown option or command, bad value) also end in one JSON object."""

    def main(self, *args, **kwargs):
        try:
            # Non-standalone mode raises usage errors instead of printing them to stderr. --help and
            # --version return their exit code (0), which the console script's sys.exit(main()) uses.
            return super().main(*args, standalone_mode=False, **kwargs)
        except click.ClickException as err:
            emit(ok=False, errors=[err.format_message()], code=EXIT_RULE)
        except click.Abort:
            emit(ok=False, errors=["aborted"], code=EXIT_RULE)


# Options the concept commands share, declared once.
TOKENS_OPTION = click.option("--tokens", "tokens_path", default=None, type=click.Path(exists=True, dir_okay=False),
                             help="tokens.json to use instead of <concept>/tokens.json (for the colour variants, panels and checks)")
VARIANTS_OPTION = click.option("--variants", default="black,white", help="Comma-separated subset of black,white,mono,color,reverse")
ROUND_OPTION = click.option("--round", "round_n", type=click.IntRange(min=1), default=None,
                            help="Write round N (default: one past the highest existing round)")


@click.group(cls=JsonGroup)
@click.version_option(__version__)
def main() -> None:
    """logomaker: deterministic steps for the Claude Code logo skill."""


def chrome_status() -> dict:
    """render.check_chrome on render.CHROME_APP (where the Renderer looks), plus the version its binary reports."""
    from .render import CHROME_APP, check_chrome

    status = check_chrome(CHROME_APP)
    binary = CHROME_APP / "Contents" / "MacOS" / "Google Chrome"
    version = None
    if status["found"] and binary.is_file():
        try:
            out = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=20)
            version = out.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            version = None
    return {**status, "version": version}


@main.command("setup")
@click.option("--check", is_flag=True, help="Report status only; create nothing. Missing Chrome or modules exit 3.")
@command
def setup(check: bool) -> None:
    """Check Chrome and the Python modules. Without --check, also create brands/, registry/ and assets/fonts/."""
    paths = project()
    modules: dict[str, bool] = {}
    module_errors: dict[str, str] = {}
    for name in MODULES:
        try:
            importlib.import_module(name)
            modules[name] = True
        except Exception as err:  # noqa: BLE001 - ImportError, or a module that breaks while importing
            modules[name] = False
            module_errors[name] = f"{type(err).__name__}: {err}"
    chrome = chrome_status()
    created = []
    if not check:
        for folder in (paths.brands, paths.registry, paths.fonts):
            if not folder.exists():
                folder.mkdir(parents=True)
                created.append(str(folder.relative_to(paths.root)))
    problems = []
    if not chrome["found"]:
        problems.append(f"Google Chrome not found at {chrome['path']}; render commands will exit {EXIT_EXTERNAL}")
    missing = [m for m, ok in modules.items() if not ok]
    if missing:
        problems.append("missing modules: " + ", ".join(missing) + " (run uv sync)")
    payload = {"root": str(paths.root), "python": platform.python_version(), "chrome": chrome, "modules": modules, "created": created}
    if module_errors:
        payload["module_errors"] = module_errors
    if check:  # a check is a verdict: anything missing fails it
        emit(payload, ok=not problems, errors=problems, code=EXIT_EXTERNAL if problems else 0)
    emit(payload, warnings=problems)


@main.group("brand")
def brand() -> None:
    """Create, inspect and advance brands."""


def _brand_payload(state) -> dict:
    return {"brand": state.model_dump(mode="json")}


def _emit_brand(paths, state) -> None:
    """A command's JSON for the brand it saved, warning about any brand folder the registry index leaves out."""
    emit(_brand_payload(state), warnings=registry.unindexed_warnings(paths))


@brand.command("new")
@click.argument("name")
@click.option("--slug", default=None, help="Override the generated slug.")
@click.option("--unnamed", is_flag=True, help="NAME is a working title; a naming phase will run.")
@command
def brand_new(name: str, slug: str | None, unnamed: bool) -> None:
    """Create a brand folder and its brand.json. The registry index gets an entry."""
    paths = project()
    registry.list_brands(paths)  # rebuild a missing index, or stop on a malformed one, before the brand folder exists
    _emit_brand(paths, registry.new_brand(paths, name, slug, unnamed))


@brand.command("list")
@command
def brand_list() -> None:
    """List the brands in the registry. A missing index is rebuilt from the brand folders."""
    paths = project()
    emit({"brands": registry.list_brands(paths)}, warnings=registry.unindexed_warnings(paths))


@brand.command("status")
@click.argument("slug")
@command
def brand_status(slug: str) -> None:
    """Show a brand's state and what it needs next."""
    paths = project()
    state = registry.load_state(paths, slug)
    nxt = registry.allowed_next(state)
    payload = _brand_payload(state)
    payload["next"] = nxt.value if nxt else None
    payload["missing"] = registry.prerequisites(paths, state, nxt) if nxt else []
    emit(payload)


@brand.command("advance")
@click.argument("slug")
@click.option("--to", "target", required=True, type=click.Choice([p.value for p in Phase]))
@command
def brand_advance(slug: str, target: str) -> None:
    """Move a brand to its next phase. Every earlier phase's artifacts must check out."""
    paths = project()
    _emit_brand(paths, registry.advance(paths, slug, Phase(target)))


@brand.command("decide")
@click.argument("slug")
@click.option("--phase", required=True, type=click.Choice([p.value for p in Phase]))
@click.option("--by", default="user", type=click.Choice(["user", "claude"]))
@click.option("--note", required=True)
@command
def brand_decide(slug: str, phase: str, by: str, note: str) -> None:
    """Append a decision to the brand's log."""
    paths = project()
    _emit_brand(paths, registry.decide(paths, slug, Phase(phase), by, note))


@brand.command("rename")
@click.argument("slug")
@click.option("--name", required=True)
@command
def brand_rename(slug: str, name: str) -> None:
    """Set the brand's chosen name. The slug never changes."""
    paths = project()
    _emit_brand(paths, registry.rename(paths, slug, name))


@brand.command("set")
@click.argument("slug")
@click.option("--territory", default=None)
@click.option("--concept", default=None, help="Concept folder name, e.g. 03-keystone")
@click.option("--primary-lockup", "primary_lockup", default=None, type=click.Choice(["horizontal", "stacked"]))
@click.option("--industry", default=None)
@click.option("--surface", "surfaces", multiple=True, help="Ranked surfaces; repeat the flag.")
@click.option("--font", "fonts", multiple=True, help="ROLE=FAMILY[:WEIGHT], e.g. wordmark=Sora:650")
@command
def brand_set(slug: str, territory, concept, primary_lockup, industry, surfaces, fonts) -> None:
    """Record choices in brand.json. Territory, concept, primary lockup, industry, surfaces, fonts."""
    paths = project()
    _emit_brand(paths, registry.set_fields(paths, slug, territory=territory, concept=concept, primary_lockup=primary_lockup,
                                           industry=industry, surfaces=surfaces, fonts=fonts))


@main.group("fonts")
def fonts_group() -> None:
    """Font catalogue and cache."""


@fonts_group.command("list")
@click.option("--category", default=None)
@click.option("--personality", default=None)
@command
def fonts_list(category: str | None, personality: str | None) -> None:
    """List the font catalogue. Filter by category or personality; each family says whether it is cached."""
    from . import fonts as fontlib

    paths = project()
    if category:
        categories = list(dict.fromkeys(f.category for f in fontlib.load_catalog(paths)))
        if category not in categories:
            raise CliError(f"Unknown category {category!r}; choose one of: {', '.join(categories)}")
    families = fontlib.list_fonts(paths, category, personality)
    emit({"families": [
        {**fontlib.family_to_dict(f), "cached": bool(fontlib.cached_files(paths, f.family))} for f in families
    ]})


@fonts_group.command("fetch")
@click.argument("family")
@command
def fonts_fetch(family: str) -> None:
    """Download a family from google/fonts. Its TTF files and licence go into assets/fonts/<family>/."""
    from . import fonts as fontlib

    emit({"manifest": fontlib.fetch(project(), family)})


@main.group("color")
def color_group() -> None:
    """Colour conversions and token checks."""


@color_group.command("info")
@click.argument("value")
@command
def color_info(value: str) -> None:
    """Show a colour in every notation. Hex, RGB, HSL, OKLCH and CMYK, with its luminance."""
    from . import color as colorlib

    emit(colorlib.info(value))


@color_group.command("ramp")
@click.argument("value")
@click.option("--steps", default=9, type=click.IntRange(min=1))
@command
def color_ramp(value: str, steps: int) -> None:
    """Make an OKLCH lightness ramp from a colour."""
    from . import color as colorlib

    emit({"ramp": colorlib.ramp(value, steps)})


@color_group.command("check")
@click.argument("tokens_path", type=click.Path(exists=True, dir_okay=False))
@command
def color_check(tokens_path: str) -> None:
    """Check a tokens file for contrast and CVD. Contrast on light and dark paper; grayscale and colour-vision pairs."""
    from . import color as colorlib

    result = colorlib.check_tokens(colorlib.load_tokens(Path(tokens_path)))
    emit(result.model_dump(), ok=result.ok, errors=result.failures, warnings=result.warnings, code=0 if result.ok else EXIT_RULE)


@main.group("concept")
def concept_group() -> None:
    """Build, audit and render concept modules."""


def _build_concept(paths, slug: str, concept: str, variants: str, tokens_path: str | None):
    from . import color as colorlib
    from .kit import concept as conceptlib

    folder = conceptlib.concept_folder(paths, slug, concept)
    # Variants are checked before tokens are read, the concept is loaded or the build folder is touched.
    wanted = conceptlib.validate_variants(v.strip() for v in variants.split(",") if v.strip())
    palette = dark_palette = None
    if any(v in ("color", "reverse") for v in wanted):  # only colour variants read tokens, so a draft never blocks the rest
        tokens_file = Path(tokens_path) if tokens_path else folder / "tokens.json"
        if not tokens_file.is_file():
            raise CliError("color and reverse variants need --tokens or a tokens.json in the concept folder")
        tokens = colorlib.load_tokens(tokens_file)
        palette, dark_palette = tokens.palette("light"), tokens.palette("dark")
    module = conceptlib.load_concept(folder)
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
    return folder, outputs, conceptlib.write_build(folder, outputs, variants=wanted, palette=palette, dark_palette=dark_palette)


@concept_group.command("build")
@click.argument("slug")
@click.argument("concept")
@VARIANTS_OPTION
@TOKENS_OPTION
@command
def concept_build(slug: str, concept: str, variants: str, tokens_path: str | None) -> None:
    """Build a concept's tiers into build/. SVGs per output and variant, plus geometry.json and build.json."""
    paths = project()
    folder, _, report = _build_concept(paths, slug, concept, variants, tokens_path)
    emit({"concept": str(folder.relative_to(paths.root)), "build": report}, warnings=report["warnings"])


def _emit_audit(payload: dict, result, warnings: list[str] | None = None) -> None:
    """Emit `payload` with the audit's verdict on top, as `color check` does: failures are errors and exit 2."""
    emit(payload, ok=result.ok, errors=[f.message for f in result.failures],
         warnings=(warnings or []) + [f.message for f in result.warnings], code=0 if result.ok else EXIT_RULE)


@concept_group.command("audit")
@click.argument("slug")
@click.argument("concept")
@click.option("--no-render", is_flag=True, help="Skip the raster checks (no Chrome needed).")
@TOKENS_OPTION
@command
def concept_audit(slug: str, concept: str, no_render: bool, tokens_path: str | None) -> None:
    """Audit a concept and write audit.json. The raster checks need Chrome unless --no-render; a failing audit exits 2."""
    from . import audit as auditlib
    from .render import Renderer

    paths = project()
    if no_render:
        result = auditlib.audit_concept(paths, slug, concept, tokens_path=tokens_path)
    else:
        with Renderer() as renderer:
            result = auditlib.audit_concept(paths, slug, concept, renderer=renderer, tokens_path=tokens_path)
    _emit_audit({"audit": result.model_dump()}, result)


@concept_group.command("render")
@click.argument("slug")
@click.argument("concept")
@ROUND_OPTION
@TOKENS_OPTION
@command
def concept_render(slug: str, concept: str, round_n: int | None, tokens_path: str | None) -> None:
    """Render the concept's critique sheet. It goes into <concept>/renders/round-N/."""
    from . import sheets as sheetlib

    # No renderer passed: the sheet launches Chrome itself, only once the concept has loaded and built.
    emit(sheetlib.critique_sheet(project(), slug, concept, round_n, tokens_path=tokens_path))


@concept_group.command("run")
@click.argument("slug")
@click.argument("concept")
@ROUND_OPTION
@VARIANTS_OPTION
@TOKENS_OPTION
@click.option("--no-render", is_flag=True, help="Build and audit only (no Chrome).")
@command
def concept_run(slug: str, concept: str, round_n: int | None, variants: str, tokens_path: str | None, no_render: bool) -> None:
    """Build, audit and render a concept. Everything is written first; a failing audit then exits 2."""
    from . import audit as auditlib
    from . import sheets as sheetlib
    from .render import Renderer

    paths = project()
    folder, outputs, report = _build_concept(paths, slug, concept, variants, tokens_path)
    critique = None
    if no_render:
        result = auditlib.audit_concept(paths, slug, concept, tokens_path=tokens_path)
    else:
        with Renderer() as renderer:
            result = auditlib.audit_concept(paths, slug, concept, renderer=renderer, tokens_path=tokens_path)
            critique = sheetlib.critique_sheet(paths, slug, concept, round_n, renderer, audit=result, tokens_path=tokens_path,
                                               outputs=outputs)
    # Everything is written before the verdict: a failing audit still leaves the build, audit.json and the sheet.
    _emit_audit({"concept": str(folder.relative_to(paths.root)), "build": report, "audit": result.model_dump(), "critique": critique},
                result, warnings=report["warnings"])


@concept_group.command("critic")
@click.argument("slug")
@click.option("--sheet", "rounds", type=click.IntRange(min=1), multiple=True, required=True,
              help="A critic sheet whose passes to merge; repeat it to merge two sheets, e.g. --sheet 3 --sheet 4.")
@command
def concept_critic(slug: str, rounds: tuple[int, ...]) -> None:
    """Merge each --sheet's critic-N.pass-*.json, by its own key, into critic.json per concept folder (final/ for a final sheet)."""
    from . import critic as criticlib

    emit(criticlib.write_cards(project(), slug, list(rounds)))


@main.group("sheet")
def sheet_group() -> None:
    """Owner-facing sheets (opened in the browser)."""


@sheet_group.command("territories")
@click.argument("slug")
@click.option("--no-open", is_flag=True, help="Write the board without opening it in the browser.")
@command
def sheet_territories(slug: str, no_open: bool) -> None:
    """Render the territories board from territories.json. It goes into territories/board.{html,png} and opens in the browser."""
    from . import sheets as sheetlib

    # No renderer passed: the board launches Chrome itself, only once the brand, the spec and its fonts check out.
    info = sheetlib.territories_board(project(), slug, open_after=not no_open)
    emit(info, warnings=info.pop("warnings"))


@sheet_group.command("concepts")
@click.argument("slug")
@click.option("--concepts", "concepts", required=True, help="Comma-separated concept folder names, e.g. 01-arch,03-keystone")
@click.option("--no-open", is_flag=True, help="Write the sheet without opening it in the browser.")
@command
def sheet_concepts(slug: str, concepts: str, no_open: bool) -> None:
    """Render the concept sheet for vetted concepts. It goes into sheets/concepts.{html,png} and opens in the browser."""
    from . import sheets as sheetlib

    names = [c.strip() for c in concepts.split(",") if c.strip()]
    # No renderer passed: the sheet launches Chrome itself, only once every concept is vetted and built.
    info = sheetlib.concepts_sheet(project(), slug, names, open_after=not no_open)
    emit(info, warnings=info.pop("warnings"))


@sheet_group.command("refine")
@click.argument("slug")
@ROUND_OPTION
@click.option("--no-open", is_flag=True, help="Write the sheet without opening it in the browser.")
@command
def sheet_refine(slug: str, round_n: int | None, no_open: bool) -> None:
    """Render the refine sheet from final/. It goes into sheets/refine-N.{html,png} and opens in the browser."""
    from . import sheets as sheetlib

    # No renderer passed: the sheet launches Chrome itself, only once final/ has loaded and built.
    info = sheetlib.refine_sheet(project(), slug, open_after=not no_open, round_n=round_n)
    emit(info, warnings=info.pop("warnings"))


@sheet_group.command("critic")
@click.argument("slug")
@click.option("--concepts", "concepts", default=None, help="Comma-separated survivors to letter, e.g. 01-arch,03-keystone")
@click.option("--final", is_flag=True, help="Letter the final mark alone (final/), for the critic's last pass.")
@click.option("--seed", type=int, default=None,
              help="Shuffle seed, to reproduce an earlier sheet (default: the round number, re-shuffled until the lettering "
                   "differs from the last sheet of the same concepts); leave it out for a critic pass.")
@command
def sheet_critic(slug: str, concepts: str | None, final: bool, seed: int | None) -> None:
    """Render the blind critic's lettered sheet to sheets/critic-N.{html,png} and its key to critic-N.key.json; never opened."""
    from . import sheets as sheetlib

    names = [c.strip() for c in (concepts or "").split(",") if c.strip()]
    emit(sheetlib.critic_sheet(project(), slug, names, seed=seed, final=final))


@main.group("package")
def package_group() -> None:
    """Build and verify the export package."""


@package_group.command("build")
@click.argument("slug")
@click.option("--paper", default="letter", type=click.Choice(["letter", "a4"]), help="Paper size of the brand sheet PDF.")
@command
def package_build(slug: str, paper: str) -> None:
    """Build brands/<slug>/package/ from final/ (rationale.md and a passing audit needed); a failed build keeps the previous package."""
    from . import export as exportlib
    from .render import Renderer

    builder = exportlib.PackageBuilder(project(), slug, paper)  # refuses an unfinished final/ before Chrome starts
    with Renderer() as renderer:
        manifest = builder.build(renderer)
    skipped = [f"{group} skipped: {reason}" for group, reason in manifest.skipped.items()]
    sheet = builder.pkg / "brand-sheet.pdf"  # absolute paths, as the sheets give theirs: the skill opens them
    emit({"package": str(builder.pkg), "files": len(manifest.files), "manifest": str(builder.pkg / "manifest.json"),
          "brand_sheet": str(sheet) if sheet.is_file() else None}, warnings=manifest.warnings + skipped)


@package_group.command("verify")
@click.argument("slug")
@command
def package_verify(slug: str) -> None:
    """Check package/ against its manifest and write package/verify.json, which the done phase needs; problems exit 4."""
    from . import export_docs

    result = export_docs.verify(project(), slug)
    emit(result, ok=result["ok"], errors=result["problems"], code=0 if result["ok"] else EXIT_VERIFY)


@main.group("names")
def names_group() -> None:
    """Name analysis and availability checks."""


@names_group.command("analyze")
@click.argument("name")
@command
def names_analyze(name: str) -> None:
    """Show a name's sound and letterform features: syllables, vowels, initial letter, pronounceability."""
    emit(nameslib.analyze(name))


@names_group.command("check")
@click.argument("name")
@click.option("--tlds", default=None, help=f"Comma-separated top-level domains to check (default: {','.join(nameslib.TLDS)})")
@click.option("--handles", default=None, help="Comma-separated handle services to check, or empty for none "
                                              f"(default: {','.join(nameslib.HANDLES)})")
@command
def names_check(name: str, tlds: str | None, handles: str | None) -> None:
    """Check domains over RDAP (then whois) and GitHub handles; a failed or late lookup is unknown, with a warning."""

    def listed(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
        return default if value is None else tuple(v.strip() for v in value.split(",") if v.strip())

    result = nameslib.check(name, listed(tlds, nameslib.TLDS), listed(handles, nameslib.HANDLES))
    emit(result, warnings=result.pop("warnings"))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
