"""Click entry points. Every command ends in output.emit()."""
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
from . import color as colorlib
from . import fonts as fontlib
from .kit import concept as conceptlib
from .output import EXIT_EXTERNAL, EXIT_RULE, CliError, emit
from .paths import project
from .schemas import Phase

CHROME_APP = "/Applications/Google Chrome.app"
CHROME_BIN = CHROME_APP + "/Contents/MacOS/Google Chrome"
MODULES = ["skia", "fontTools", "uharfbuzz", "coloraide", "reportlab", "playwright", "PIL", "numpy", "scipy", "jinja2", "httpx", "pydantic"]


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


@click.group(cls=JsonGroup)
@click.version_option(__version__)
def main() -> None:
    """logomaker: deterministic steps for the Claude Code logo skill."""


def chrome_status() -> dict:
    import os

    found = os.path.isfile(CHROME_BIN)
    version = None
    if found:
        try:
            out = subprocess.run([CHROME_BIN, "--version"], capture_output=True, text=True, timeout=20)
            version = out.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            version = None
    return {"found": found, "path": CHROME_APP, "version": version}


@main.command("setup")
@click.option("--check", is_flag=True, help="Report status only; create nothing.")
@command
def setup(check: bool) -> None:
    paths = project()
    modules = {}
    for name in MODULES:
        try:
            importlib.import_module(name)
            modules[name] = True
        except Exception:  # noqa: BLE001
            modules[name] = False
    chrome = chrome_status()
    created = []
    if not check:
        for folder in (paths.brands, paths.registry, paths.fonts):
            if not folder.exists():
                folder.mkdir(parents=True)
                created.append(str(folder.relative_to(paths.root)))
    warnings = []
    if not chrome["found"]:
        warnings.append(f"Google Chrome not found at {CHROME_APP}; render commands will exit {EXIT_EXTERNAL}")
    missing = [m for m, ok in modules.items() if not ok]
    if missing:
        warnings.append("missing modules: " + ", ".join(missing) + " (run uv sync)")
    emit(
        {
            "root": str(paths.root),
            "python": platform.python_version(),
            "chrome": chrome,
            "modules": modules,
            "created": created,
        },
        warnings=warnings,
    )


@main.group("brand")
def brand() -> None:
    """Create, inspect and advance brands."""


def _brand_payload(state) -> dict:
    return {"brand": state.model_dump(mode="json")}


@brand.command("new")
@click.argument("name")
@click.option("--slug", default=None, help="Override the generated slug.")
@click.option("--unnamed", is_flag=True, help="NAME is a working title; a naming phase will run.")
@command
def brand_new(name: str, slug: str | None, unnamed: bool) -> None:
    emit(_brand_payload(registry.new_brand(project(), name, slug, unnamed)))


@brand.command("list")
@command
def brand_list() -> None:
    emit({"brands": registry.list_brands(project())})


@brand.command("status")
@click.argument("slug")
@command
def brand_status(slug: str) -> None:
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
    emit(_brand_payload(registry.advance(project(), slug, Phase(target))))


@brand.command("decide")
@click.argument("slug")
@click.option("--phase", required=True, type=click.Choice([p.value for p in Phase]))
@click.option("--by", default="user", type=click.Choice(["user", "claude"]))
@click.option("--note", required=True)
@command
def brand_decide(slug: str, phase: str, by: str, note: str) -> None:
    emit(_brand_payload(registry.decide(project(), slug, Phase(phase), by, note)))


@brand.command("rename")
@click.argument("slug")
@click.option("--name", required=True)
@command
def brand_rename(slug: str, name: str) -> None:
    emit(_brand_payload(registry.rename(project(), slug, name)))


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
    emit(_brand_payload(registry.set_fields(
        project(), slug, territory=territory, concept=concept, primary_lockup=primary_lockup,
        industry=industry, surfaces=surfaces, fonts=fonts,
    )))


@main.group("fonts")
def fonts_group() -> None:
    """Font catalogue and cache."""


@fonts_group.command("list")
@click.option("--category", default=None)
@click.option("--personality", default=None)
@command
def fonts_list(category: str | None, personality: str | None) -> None:
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
    emit({"manifest": fontlib.fetch(project(), family)})


@main.group("color")
def color_group() -> None:
    """Colour conversions and token checks."""


@color_group.command("info")
@click.argument("value")
@command
def color_info(value: str) -> None:
    emit(colorlib.info(value))


@color_group.command("ramp")
@click.argument("value")
@click.option("--steps", default=9, type=click.IntRange(min=1))
@command
def color_ramp(value: str, steps: int) -> None:
    emit({"ramp": colorlib.ramp(value, steps)})


@color_group.command("check")
@click.argument("tokens_path", type=click.Path(exists=True, dir_okay=False))
@command
def color_check(tokens_path: str) -> None:
    result = colorlib.check_tokens(colorlib.load_tokens(Path(tokens_path)))
    emit(result.model_dump(), ok=result.ok, errors=result.failures, warnings=result.warnings, code=0 if result.ok else EXIT_RULE)


@main.group("concept")
def concept_group() -> None:
    """Build, audit and render concept modules."""


@concept_group.command("build")
@click.argument("slug")
@click.argument("concept")
@click.option("--variants", default="black,white", help="Comma-separated subset of black,white,mono,color,reverse")
@click.option("--tokens", "tokens_path", default=None, type=click.Path(exists=True, dir_okay=False), help="tokens.json for color/reverse (defaults to <concept>/tokens.json when present)")
@command
def concept_build(slug: str, concept: str, variants: str, tokens_path: str | None) -> None:
    paths = project()
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
    report = conceptlib.write_build(folder, outputs, variants=wanted, palette=palette, dark_palette=dark_palette)
    emit({"concept": str(folder.relative_to(paths.root)), "build": report}, warnings=report["warnings"])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
