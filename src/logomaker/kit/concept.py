"""Concept modules: META + PARAMS + TIERS + build(p) -> Mark. Loading, tier builds and build/ output."""
from __future__ import annotations

import hashlib
import json
import sys
import traceback
import types
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path

from ..output import EXIT_RULE, CliError
from ..paths import ProjectPaths
from .mark import VARIANTS, Mark

TIER_NAMES = ("full", "compact", "small", "favicon")


@dataclass
class Meta:
    slug: str
    idea: str
    logo_type: str
    motifs: list[str] = field(default_factory=list)
    territory: str | None = None
    allow_complex: bool = False
    complex_reason: str = ""

    def __post_init__(self) -> None:
        # A bare string would be read letter by letter by the cliché check.
        if not isinstance(self.motifs, (list, tuple)) or not all(isinstance(m, str) for m in self.motifs):
            raise ValueError(f"Meta.motifs must be a list of strings, e.g. motifs=['ring'], got {self.motifs!r}")


class Params(dict):
    """Named numbers with attribute access: Params(stroke=90).stroke == 90."""

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as err:
            raise AttributeError(f"no parameter {name!r}") from err

    def with_overrides(self, **changes) -> "Params":
        return Params({**self, **changes})


@dataclass
class ConceptModule:
    path: Path
    meta: Meta
    params: Params
    tiers: dict[str, dict]
    build: Callable[[Params], Mark]


def concept_folder(paths: ProjectPaths, slug: str, name: str) -> Path:
    brand = paths.brand(slug)
    if not brand.is_dir():
        raise CliError(f"Unknown brand {slug!r}")
    folder = brand / "final" if name == "final" else brand / "concepts" / name
    if not (folder / "concept.py").is_file():
        raise CliError(f"No concept.py in {folder}")
    return folder


@contextmanager
def _concept_code(failure: str) -> Iterator[None]:
    """Run concept code. Its prints go to stderr, since stdout carries only the CLI's JSON, and sys.exit() is an error,
    not an exit. A CliError it raises keeps its exit code and data (a missing font stays exit 3 with its fetch hint);
    any other exception becomes a CliError, exit 2, carrying the traceback. `failure` prefixes the message."""
    try:
        with redirect_stdout(sys.stderr):
            yield
    except SystemExit as err:
        raise CliError(f"{failure}: concept called sys.exit(); return the Mark instead", code=EXIT_RULE) from err
    except CliError as err:
        raise CliError(f"{failure}: {err}", code=err.code, data=err.data) from err
    except Exception as err:  # noqa: BLE001 - concept code can raise anything; the CLI reports it as JSON
        raise CliError(f"{failure}: {type(err).__name__}: {err}", data={"traceback": traceback.format_exc()}) from err


def load_concept(folder: Path) -> ConceptModule:
    source = folder / "concept.py"
    if not source.is_file():
        raise CliError(f"No concept.py in {folder}")
    name = f"logomaker_concept_{hashlib.sha1(str(source.resolve()).encode()).hexdigest()[:12]}"
    module = types.ModuleType(name)
    module.__file__ = str(source)
    with _concept_code(f"{source} failed to import"):
        # Compile from source on every load, never via importlib's bytecode cache: a .pyc passes as fresh while the source
        # keeps its size and whole-second mtime, so a quick same-length edit would build stale geometry. Bytes plus
        # dont_inherit=True compile it as an import does (coding cookie and BOM honoured, no __future__ flags from here).
        code = compile(source.read_bytes(), str(source), "exec", dont_inherit=True)
        sys.modules[name] = module
        exec(code, module.__dict__)  # noqa: S102 - running the concept module is the point of loading it
    for attr in ("META", "PARAMS", "TIERS", "build"):
        if not hasattr(module, attr):
            raise CliError(f"{source} must define {attr}")
    if not isinstance(module.META, Meta):
        raise CliError(f"{source}: META must be a logomaker.kit.Meta")
    if "full" not in module.TIERS:
        raise CliError(f"{source}: TIERS must include 'full'")
    params = Params(module.PARAMS)
    overrides = folder / "params.json"
    if overrides.is_file():
        params = params.with_overrides(**_read_overrides(overrides, params))
    return ConceptModule(path=source, meta=module.META, params=params, tiers=dict(module.TIERS), build=module.build)


def _read_overrides(path: Path, params: Params) -> dict:
    """params.json as overrides of parameters PARAMS defines; anything else is a CliError naming the file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as err:  # malformed JSON, or bytes that are not UTF-8
        raise CliError(f"{path} is not valid JSON: {err}") from err
    if not isinstance(data, dict):
        raise CliError(f"{path} must be a JSON object mapping parameter names to values")
    unknown = [name for name in data if name not in params]
    if unknown:  # a typo here would otherwise be ignored without a word
        raise CliError(f"{path}: unknown params: {', '.join(unknown)} (known: {', '.join(params) or 'none'})")
    return data


def build_tiers(concept: ConceptModule, overrides: dict | None = None) -> dict[str, Mark]:
    marks: dict[str, Mark] = {}
    for tier, tier_overrides in concept.tiers.items():
        if tier not in TIER_NAMES:
            raise CliError(f"unknown tier {tier!r}; use {TIER_NAMES}")
        drop_wordmark = tier_overrides.get("wordmark") is False
        p = concept.params.with_overrides(**(overrides or {})).with_overrides(**{k: v for k, v in tier_overrides.items() if k != "wordmark"})
        with _concept_code(f"{concept.path} build() failed for tier {tier!r}"):
            mark = concept.build(p)
        if not isinstance(mark, Mark):
            raise CliError(f"{concept.path} build() must return a Mark, got {type(mark).__name__}")
        if drop_wordmark and mark.symbol is None:
            raise CliError(f"{concept.path}: tier {tier!r} drops the wordmark but the concept has no symbol")
        marks[tier] = mark.without_wordmark() if drop_wordmark else mark
    return marks


def build_outputs(marks: dict[str, Mark]) -> dict[str, Mark]:
    full = marks["full"]
    outputs: dict[str, Mark] = {"full-lockup": full}
    if full.symbol is not None and full.wordmark is not None:
        outputs["full-horizontal"] = full.with_lockup("horizontal")
        outputs["full-stacked"] = full.with_lockup("stacked")
    if full.symbol is not None:
        outputs["full-symbol"] = full.with_lockup("symbol")
    if full.wordmark is not None:
        outputs["full-wordmark"] = full.with_lockup("wordmark")
    for tier in ("compact", "small", "favicon"):
        if tier in marks:
            outputs[tier] = marks[tier]
    return outputs


def validate_variants(variants: Iterable[str]) -> tuple[str, ...]:
    """Deduplicate `variants` in order; raise CliError listing VARIANTS when none are given or any is unknown."""
    chosen = tuple(dict.fromkeys(variants))
    if not chosen:
        raise CliError(f"No variants to build; choose one or more of: {', '.join(VARIANTS)}")
    unknown = [v for v in chosen if v not in VARIANTS]
    if unknown:
        raise CliError(f"Unknown variant {', '.join(map(repr, unknown))}; choose one of: {', '.join(VARIANTS)}")
    return chosen


def write_build(folder: Path, outputs: dict[str, Mark], variants: tuple[str, ...] = ("black", "white"),
                palette: dict[str, str] | None = None, dark_palette: dict[str, str] | None = None) -> dict:
    variants = validate_variants(variants)
    # Render everything in memory first, so any failure (e.g. a palette missing a role) leaves the previous build intact.
    svgs: dict[str, str] = {}
    geometry: dict[str, dict] = {}
    for name, mark in outputs.items():
        geometry[name] = mark.geometry()
        for variant in variants:
            chosen = dark_palette if variant == "reverse" else palette
            svgs[f"{name}-{variant}.svg"] = mark.to_svg(variant, palette=chosen)
    warnings = [f"tier {tier!r} missing; exports fall back to the next larger build" for tier in ("small", "favicon") if tier not in outputs]
    report = {"outputs": list(outputs), "variants": list(variants), "files": list(svgs), "warnings": warnings}
    geometry_json, report_json = json.dumps(geometry, indent=2) + "\n", json.dumps(report, indent=2) + "\n"
    build_dir = folder / "build"
    build_dir.mkdir(exist_ok=True)
    for stale in build_dir.glob("*.svg"):
        stale.unlink()
    for filename, svg in svgs.items():
        (build_dir / filename).write_text(svg, encoding="utf-8")
    (build_dir / "geometry.json").write_text(geometry_json, encoding="utf-8")
    (build_dir / "build.json").write_text(report_json, encoding="utf-8")
    return report
