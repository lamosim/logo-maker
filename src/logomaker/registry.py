"""Brand folders, brand.json state machine, and the registry index."""
from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from .output import EXIT_RULE, CliError
from .paths import CONCEPT_NAME, SLUG, ProjectPaths
from .schemas import PHASE_ORDER, BrandState, Brief, Decision, FontChoice, Phase, Scorecard, Strategy, TerritoriesSpec, now_iso

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
    """brands/<slug>/brand.json. A missing, malformed or invalid file is a CliError naming it."""
    path = state_path(paths, slug)
    if not path.is_file():
        raise CliError(f"Unknown brand {slug!r} (no {path})")
    try:
        return BrandState.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as err:  # malformed JSON or the wrong fields
        first = err.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "root"
        raise CliError(f"{path} is invalid: {loc}: {first['msg']}") from err
    except ValueError as err:  # bytes that are not UTF-8
        raise CliError(f"{path} is not valid JSON: {err}") from err


def save_state(paths: ProjectPaths, state: BrandState) -> None:
    state.updated = now_iso()
    path = state_path(paths, state.slug)
    path.write_text(json.dumps(state.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    _update_registry(paths, state)


def new_brand(paths: ProjectPaths, name: str, slug: str | None = None, unnamed: bool = False) -> BrandState:
    slug = slug or slugify(name)
    folder = paths.brand(slug)  # refuses anything but a slug
    if folder.exists():
        raise CliError(f"Brand {slug!r} already exists at {folder}")
    for sub in BRAND_SUBDIRS:
        (folder / sub).mkdir(parents=True)
    state = BrandState(slug=slug, name=name, needs_name=unnamed)
    save_state(paths, state)
    return state


def _entry(state: BrandState) -> dict[str, Any]:
    return {"slug": state.slug, "name": state.name, "phase": state.phase.value, "updated": state.updated}


def _indexable(paths: ProjectPaths, state_file: Path) -> tuple[BrandState | None, str]:
    """The brand in `state_file` (brands/<folder>/brand.json), or None and why the index cannot list it: the folder is
    not a slug, the file cannot be read or does not validate, or it belongs to another slug. Each reason names the file."""
    folder = state_file.parent.name
    if not SLUG.fullmatch(folder):
        return None, f"{state_file} is in a folder whose name is not a slug"
    try:
        state = load_state(paths, folder)
    except (CliError, OSError) as err:  # load_state's messages, and OSError's, name the file
        return None, str(err)
    if state.slug != folder:
        return None, f"{state_file} belongs to brand {state.slug!r}, not {folder!r}"
    return state, ""


def list_brands(paths: ProjectPaths) -> list[dict[str, Any]]:
    """The registry index, registry/brands.json. A missing index is rebuilt from every brand folder it can list (see
    unindexed_warnings for the rest) and written back; a malformed one is a CliError naming it."""
    path = paths.registry / "brands.json"
    if not path.is_file():
        states = (_indexable(paths, state_file)[0] for state_file in sorted(paths.brands.glob("*/brand.json")))
        entries = [_entry(state) for state in states if state is not None]
        _write_registry(paths, entries)
        return entries
    rebuild = "; delete it and run `logomaker brand list` to rebuild it from the brand folders"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as err:  # malformed JSON, or bytes that are not UTF-8
        raise CliError(f"{path} is not valid JSON: {err}{rebuild}") from err
    entries = data.get("brands") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not all(isinstance(e, dict) and "slug" in e for e in entries):
        raise CliError(f'{path} must hold {{"brands": [...]}} with a slug in every entry{rebuild}')
    return entries


def unindexed_warnings(paths: ProjectPaths) -> list[str]:
    """A warning for each brands/*/brand.json the registry index leaves out, with the reason, so a brand a rebuild had
    to skip (or one the index never heard of) is never out of sight. Brand commands that save, and `brand list`, emit
    them."""
    indexed = {entry["slug"] for entry in list_brands(paths)}
    warnings = []
    for state_file in sorted(paths.brands.glob("*/brand.json")):
        if state_file.parent.name in indexed:
            continue
        _, problem = _indexable(paths, state_file)
        reason = problem or f"{state_file} is a valid brand missing from the index; delete registry/brands.json to rebuild it"
        warnings.append(f"left out of the registry index: {reason}")
    return warnings


def _write_registry(paths: ProjectPaths, entries: list[dict[str, Any]]) -> None:
    paths.registry.mkdir(parents=True, exist_ok=True)
    entries = sorted(entries, key=lambda e: e["slug"])
    (paths.registry / "brands.json").write_text(json.dumps({"brands": entries}, indent=2) + "\n", encoding="utf-8")
    lines = ["# Brands", "", "| Slug | Name | Phase | Updated |", "|---|---|---|---|"]
    lines += [f"| {e['slug']} | {e['name']} | {e['phase']} | {e['updated']} |" for e in entries]
    (paths.registry / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_registry(paths: ProjectPaths, state: BrandState) -> None:
    _write_registry(paths, [e for e in list_brands(paths) if e["slug"] != state.slug] + [_entry(state)])


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
                if weight and not weight.isdecimal():
                    raise CliError(f"--font weight must be a whole number, got {weight!r} in {spec!r}")
                state.fonts[role] = FontChoice(family=family, weight=int(weight) if weight else 400)
        elif key == "surfaces":
            state.surfaces = list(value)
        else:
            # Both name folders the gates read (concepts/<concept>, the territories.json slug), so neither may be a path.
            if key == "concept" and not CONCEPT_NAME.fullmatch(value):
                raise CliError(f"--concept must be a concept folder name like 03-keystone (two digits, a hyphen, a slug), got {value!r}")
            if key == "territory" and not SLUG.fullmatch(value):
                raise CliError(f"--territory must be a territory slug (lowercase letters, digits and hyphens), got {value!r}")
            setattr(state, key, value)
    save_state(paths, state)
    return state


def allowed_next(state: BrandState) -> Phase | None:
    if state.phase == Phase.intake:
        return Phase.naming if state.needs_name else Phase.strategy
    if state.phase == Phase.done:
        return None
    return PHASE_ORDER[PHASE_ORDER.index(state.phase) + 1]


def load_model[M: BaseModel](path: Path, model: type[M], label: str, code: int = EXIT_RULE) -> M:
    """`path` read and validated as `model`. A missing, malformed or invalid file is a CliError (exit `code`) calling it `label`."""
    if not path.is_file():
        raise CliError(f"{label} is missing", code)
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as err:  # malformed JSON or the wrong fields
        first = err.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "root"
        raise CliError(f"{label} is invalid: {loc}: {first['msg']}", code) from err
    except ValueError as err:  # bytes that are not UTF-8
        raise CliError(f"{label} is not valid JSON: {err}", code) from err


def _validate_file(path: Path, model: type[BaseModel], label: str | None = None) -> str | None:
    """Return an error message if `path` is missing or does not validate as `model`; messages call it `label` (default: its name)."""
    try:
        load_model(path, model, label or path.name)
    except CliError as err:
        return str(err)
    return None


def _need(brand: Path, path: Path, model: type[BaseModel] | None = None) -> list[str]:
    """Return a message if `path` is missing or, when `model` is given, does not validate as it."""
    label = str(path.relative_to(brand))
    if model is None:
        return [] if path.is_file() else [f"{label} is missing"]
    err = _validate_file(path, model, label)
    return [err] if err else []


def _read_json(brand: Path, path: Path) -> tuple[dict[str, Any], str | None]:
    """`path` parsed as a JSON object, or ({}, a message naming it relative to `brand`)."""
    label = path.relative_to(brand)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as err:  # malformed JSON, or bytes that are not UTF-8
        return {}, f"{label} is not valid JSON: {err}"
    return (data, None) if isinstance(data, dict) else ({}, f"{label} is not a JSON object")


def _check_brief(brand: Path, state: BrandState) -> list[str]:
    return _need(brand, brand / "brief.md") + _need(brand, brand / "brief.json", Brief)


def _check_naming(brand: Path, state: BrandState) -> list[str]:
    # Only a brand leaving the naming phase owes naming.md; one that never needed a name went intake -> strategy.
    if state.phase != Phase.naming:
        return []
    return _need(brand, brand / "naming.md")


def _check_strategy(brand: Path, state: BrandState) -> list[str]:
    return _need(brand, brand / "strategy.md") + _need(brand, brand / "strategy.json", Strategy)


def _check_territories(brand: Path, state: BrandState) -> list[str]:
    """territories.json must be a valid TerritoriesSpec (its slugs are slugs, and unique) that holds the chosen territory."""
    spec = brand / "territories" / "territories.json"
    missing = _need(brand, spec, TerritoriesSpec)
    if not missing:
        slugs = [t.slug for t in TerritoriesSpec.model_validate_json(spec.read_text(encoding="utf-8")).territories]
        if state.territory not in slugs:
            missing.append("territory not chosen (run: logomaker brand set <slug> --territory <territory-slug>)")
    return missing


def audit_problems(paths: ProjectPaths, slug: str, folder: Path) -> list[str]:
    """Why <folder>/audit.json does not vouch for the concept as it is now, or [] when it does: it is missing or not a
    JSON object, stale (its fingerprint is not audit.concept_fingerprint of the concept now), made with --no-render, or
    failing. The concept gate and the concept sheet both ask this."""
    from .audit import concept_fingerprint  # imported here: audit imports registry

    brand = paths.brand(slug)
    path = folder / "audit.json"
    missing = _need(brand, path)
    if missing:
        return missing
    result, error = _read_json(brand, path)
    if error:
        return [error]
    problems = []
    if result.get("fingerprint") != concept_fingerprint(paths, slug, folder):
        problems.append(f"{folder.name}/audit.json is stale (concept.py, params.json, tokens.json, the brand's industry or "
                        "minimum sizes, or cliches.json changed); re-run concept audit")
    if not result.get("rendered"):
        problems.append(f"{folder.name}/audit.json was made with --no-render; re-run concept audit without it")
    if not result.get("ok"):
        problems.append(f"{folder.name}/audit.json has failures")
    return problems


def passing_scorecard(folder: Path, label: str) -> Scorecard:
    """<folder>/scorecard.json if it validates and passes the gate (Scorecard.gate_ok); else a CliError calling it `label`."""
    card = load_model(folder / "scorecard.json", Scorecard, label)
    if not card.gate_ok:
        raise CliError(f"{label} fails the gate (appropriate, simple and legible must be 4 or more, and not killed)")
    return card


def _check_concept(brand: Path, state: BrandState) -> list[str]:
    """The chosen concept needs a passing, rendered audit of what it is now (audit_problems) and a scorecard that passes
    the gate (passing_scorecard)."""
    if not state.concept:
        return ["concept not chosen (run: logomaker brand set <slug> --concept <NN-slug>)"]
    folder = brand / "concepts" / state.concept
    paths = ProjectPaths(brand.parent.parent)  # brand is brands/<slug> under the project root
    missing = _need(brand, folder / "concept.py") + audit_problems(paths, state.slug, folder)
    try:
        passing_scorecard(folder, f"{state.concept}/scorecard.json")
    except CliError as err:
        missing.append(str(err))
    return missing


def _check_final(brand: Path, state: BrandState) -> list[str]:
    from .color import Tokens  # imported here to keep registry import-light

    missing: list[str] = []
    for name in ("concept.py", "params.json"):
        missing += _need(brand, brand / "final" / name)
    return missing + _need(brand, brand / "final" / "tokens.json", model=Tokens)


def _check_verify(brand: Path, state: BrandState) -> list[str]:
    verify = brand / "package" / "verify.json"
    missing = _need(brand, verify)
    if verify.is_file():
        result, error = _read_json(brand, verify)
        if error or not result.get("ok"):
            missing.append(error or "package/verify.json reports failures")
    return missing


# The artifacts each phase leaves behind. Advancing to a phase re-runs the checks of every phase before it.
PHASE_CHECKS: dict[Phase, Callable[[Path, BrandState], list[str]]] = {
    Phase.intake: _check_brief,
    Phase.naming: _check_naming,
    Phase.strategy: _check_strategy,
    Phase.territories: _check_territories,
    Phase.concepts: _check_concept,
    Phase.refinement: _check_final,
    Phase.package: _check_verify,
}


def prerequisites(paths: ProjectPaths, state: BrandState, target: Phase) -> list[str]:
    brand = paths.brand(state.slug)
    missing: list[str] = []
    nxt = allowed_next(state)
    if target != nxt:
        missing.append(f"phase {state.phase.value} can only advance to {nxt.value if nxt else 'nothing'}, not {target.value}")
    for phase in PHASE_ORDER[: PHASE_ORDER.index(target)]:
        missing += PHASE_CHECKS[phase](brand, state)
    if target == Phase.strategy and state.needs_name:
        missing.append("brand still needs a name (run: logomaker brand rename <slug> --name <Name>)")
    return missing


def advance(paths: ProjectPaths, slug: str, target: Phase) -> BrandState:
    state = load_state(paths, slug)
    missing = prerequisites(paths, state, target)
    if missing:
        raise CliError(f"Cannot advance {slug} to {target.value}", data={"missing": missing})
    state.phase = target
    save_state(paths, state)
    return state
