"""Brand folders, brand.json state machine, and the registry index."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from .output import CliError
from .paths import ProjectPaths
from .schemas import PHASE_ORDER, BrandState, Brief, Decision, FontChoice, Phase, Strategy, now_iso

BRAND_SUBDIRS = ("inspiration", "territories", "concepts", "sheets", "final", "package")


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if not text:
        raise CliError(f"Cannot make a slug from {name!r}")
    return text


def state_path(paths: ProjectPaths, slug: str) -> Path:
    return paths.brand(slug) / "brand.json"


def load_state(paths: ProjectPaths, slug: str) -> BrandState:
    path = state_path(paths, slug)
    if not path.is_file():
        raise CliError(f"Unknown brand {slug!r} (no {path})")
    return BrandState.model_validate_json(path.read_text(encoding="utf-8"))


def save_state(paths: ProjectPaths, state: BrandState) -> None:
    state.updated = now_iso()
    path = state_path(paths, state.slug)
    path.write_text(json.dumps(state.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    _update_registry(paths, state)


def new_brand(paths: ProjectPaths, name: str, slug: str | None = None, unnamed: bool = False) -> BrandState:
    slug = slug or slugify(name)
    if slug != slugify(slug):
        raise CliError(f"Slug {slug!r} must be lowercase letters, digits and hyphens")
    folder = paths.brand(slug)
    if folder.exists():
        raise CliError(f"Brand {slug!r} already exists at {folder}")
    for sub in BRAND_SUBDIRS:
        (folder / sub).mkdir(parents=True)
    state = BrandState(slug=slug, name=name, needs_name=unnamed)
    save_state(paths, state)
    return state


def list_brands(paths: ProjectPaths) -> list[dict[str, Any]]:
    path = paths.registry / "brands.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("brands", [])


def _update_registry(paths: ProjectPaths, state: BrandState) -> None:
    paths.registry.mkdir(parents=True, exist_ok=True)
    entries = [e for e in list_brands(paths) if e["slug"] != state.slug]
    entries.append({"slug": state.slug, "name": state.name, "phase": state.phase.value, "updated": state.updated})
    entries.sort(key=lambda e: e["slug"])
    (paths.registry / "brands.json").write_text(json.dumps({"brands": entries}, indent=2) + "\n", encoding="utf-8")
    lines = ["# Brands", "", "| Slug | Name | Phase | Updated |", "|---|---|---|---|"]
    lines += [f"| {e['slug']} | {e['name']} | {e['phase']} | {e['updated']} |" for e in entries]
    (paths.registry / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def decide(paths: ProjectPaths, slug: str, phase: Phase, by: str, note: str) -> BrandState:
    state = load_state(paths, slug)
    state.decisions.append(Decision(phase=phase, by=by, note=note))  # type: ignore[arg-type]
    save_state(paths, state)
    return state


def rename(paths: ProjectPaths, slug: str, name: str) -> BrandState:
    state = load_state(paths, slug)
    state.name = name
    state.needs_name = False
    save_state(paths, state)
    return state


def set_fields(paths: ProjectPaths, slug: str, **fields: Any) -> BrandState:
    state = load_state(paths, slug)
    for key, value in fields.items():
        if value is None or value == ():
            continue
        if key == "fonts":
            for spec in value:
                role, _, rest = spec.partition("=")
                family, _, weight = rest.partition(":")
                if not role or not family:
                    raise CliError(f"--font must look like ROLE=FAMILY[:WEIGHT], got {spec!r}")
                state.fonts[role] = FontChoice(family=family, weight=int(weight) if weight else 400)
        elif key == "surfaces":
            state.surfaces = list(value)
        else:
            setattr(state, key, value)
    save_state(paths, state)
    return state


def allowed_next(state: BrandState) -> Phase | None:
    if state.phase == Phase.intake:
        return Phase.naming if state.needs_name else Phase.strategy
    if state.phase == Phase.done:
        return None
    return PHASE_ORDER[PHASE_ORDER.index(state.phase) + 1]


def _validate_file(path: Path, model: type[BaseModel]) -> str | None:
    """Return an error message if `path` is missing or does not validate as `model`."""
    if not path.is_file():
        return f"{path.name} is missing"
    try:
        model.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as err:
        first = err.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "root"
        return f"{path.name} is invalid: {loc}: {first['msg']}"
    except ValueError as err:
        return f"{path.name} is not valid JSON: {err}"
    return None


def prerequisites(paths: ProjectPaths, state: BrandState, target: Phase) -> list[str]:
    brand = paths.brand(state.slug)
    missing: list[str] = []
    nxt = allowed_next(state)
    if target != nxt:
        missing.append(f"phase {state.phase.value} can only advance to {nxt.value if nxt else 'nothing'}, not {target.value}")

    def need(path: Path, model: type[BaseModel] | None = None) -> None:
        if model is None:
            if not path.is_file():
                missing.append(f"{path.relative_to(brand)} is missing")
        else:
            err = _validate_file(path, model)
            if err:
                missing.append(err)

    if target in (Phase.naming, Phase.strategy):
        need(brand / "brief.md")
        need(brand / "brief.json", Brief)
    if target == Phase.strategy and state.needs_name:
        missing.append("brand still needs a name (run: logomaker brand rename <slug> --name <Name>)")
    if target == Phase.territories:
        need(brand / "strategy.md")
        need(brand / "strategy.json", Strategy)
    if target == Phase.concepts:
        spec = brand / "territories" / "territories.json"
        need(spec)
        if spec.is_file():
            try:
                slugs = [t["slug"] for t in json.loads(spec.read_text(encoding="utf-8"))["territories"]]
            except (KeyError, TypeError, ValueError):
                slugs = []
                missing.append("territories.json must contain a 'territories' list with slugs")
            if state.territory not in slugs:
                missing.append("territory not chosen (run: logomaker brand set <slug> --territory <territory-slug>)")
    if target == Phase.refinement:
        if not state.concept:
            missing.append("concept not chosen (run: logomaker brand set <slug> --concept <NN-slug>)")
        else:
            folder = brand / "concepts" / state.concept
            need(folder / "concept.py")
            audit = folder / "audit.json"
            need(audit)
            if audit.is_file() and not json.loads(audit.read_text(encoding="utf-8")).get("ok"):
                missing.append(f"{state.concept}/audit.json has failures")
    if target == Phase.package:
        for name in ("concept.py", "params.json", "tokens.json"):
            need(brand / "final" / name)
    if target == Phase.done:
        verify = brand / "package" / "verify.json"
        need(verify)
        if verify.is_file() and not json.loads(verify.read_text(encoding="utf-8")).get("ok"):
            missing.append("package/verify.json reports failures")
    return missing


def advance(paths: ProjectPaths, slug: str, target: Phase) -> BrandState:
    state = load_state(paths, slug)
    missing = prerequisites(paths, state, target)
    if missing:
        raise CliError(f"Cannot advance {slug} to {target.value}", data={"missing": missing})
    state.phase = target
    save_state(paths, state)
    return state
