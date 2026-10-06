"""Click entry points. Every command ends in output.emit()."""
from __future__ import annotations

import functools
import importlib
import platform
import subprocess
import sys
import traceback

import click

from . import __version__
from .output import EXIT_EXTERNAL, EXIT_RULE, CliError, emit
from .paths import project

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


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
