"""Concept modules: META + PARAMS + TIERS + build(p) -> Mark. Loading, tier builds and build/ output."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..output import CliError
from ..paths import ProjectPaths
from .mark import Mark

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


def load_concept(folder: Path) -> ConceptModule:
    source = folder / "concept.py"
    if not source.is_file():
        raise CliError(f"No concept.py in {folder}")
    name = f"logomaker_concept_{hashlib.sha1(str(source.resolve()).encode()).hexdigest()[:12]}"
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as err:  # noqa: BLE001
        raise CliError(f"{source} failed to import: {type(err).__name__}: {err}", data={"traceback": traceback.format_exc()}) from err
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
        params = params.with_overrides(**json.loads(overrides.read_text(encoding="utf-8")))
    return ConceptModule(path=source, meta=module.META, params=params, tiers=dict(module.TIERS), build=module.build)


def build_tiers(concept: ConceptModule, overrides: dict | None = None) -> dict[str, Mark]:
    marks: dict[str, Mark] = {}
    for tier, tier_overrides in concept.tiers.items():
        if tier not in TIER_NAMES:
            raise CliError(f"unknown tier {tier!r}; use {TIER_NAMES}")
        drop_wordmark = tier_overrides.get("wordmark") is False
        p = concept.params.with_overrides(**(overrides or {})).with_overrides(**{k: v for k, v in tier_overrides.items() if k != "wordmark"})
        try:
            mark = concept.build(p)
        except Exception as err:  # noqa: BLE001
            raise CliError(f"{concept.path} build() failed for tier {tier!r}: {type(err).__name__}: {err}",
                           data={"traceback": traceback.format_exc()}) from err
        if not isinstance(mark, Mark):
            raise CliError(f"{concept.path} build() must return a Mark, got {type(mark).__name__}")
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


def write_build(folder: Path, outputs: dict[str, Mark], variants: tuple[str, ...] = ("black", "white"),
                palette: dict[str, str] | None = None, dark_palette: dict[str, str] | None = None) -> dict:
    build_dir = folder / "build"
    build_dir.mkdir(exist_ok=True)
    for stale in build_dir.glob("*.svg"):
        stale.unlink()
    files: list[str] = []
    geometry: dict[str, dict] = {}
    warnings: list[str] = []
    for tier in ("small", "favicon"):
        if tier not in outputs:
            warnings.append(f"tier {tier!r} missing; exports fall back to the next larger build")
    for name, mark in outputs.items():
        geometry[name] = mark.geometry()
        for variant in variants:
            chosen = dark_palette if variant == "reverse" else palette
            svg = mark.to_svg(variant, palette=chosen)
            filename = f"{name}-{variant}.svg"
            (build_dir / filename).write_text(svg, encoding="utf-8")
            files.append(filename)
    (build_dir / "geometry.json").write_text(json.dumps(geometry, indent=2) + "\n", encoding="utf-8")
    report = {"outputs": list(outputs), "variants": list(variants), "files": files, "warnings": warnings}
    (build_dir / "build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
