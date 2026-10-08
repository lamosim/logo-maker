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
from .schemas import (
    GATE,
    GATE_MIN,
    PHASE_ORDER,
    BrandState,
    Brief,
    CriticCard,
    Decision,
    FontChoice,
    Phase,
    Scorecard,
    Strategy,
    TerritoriesSpec,
    now_iso,
)

BRAND_SUBDIRS = ("inspiration", "territories", "concepts", "sheets", "final", "package")
# What to do about each of final/'s files when it is missing: the final gate and package build both say it.
FINAL_REMEDIES = {
    "concept.py": "copy the chosen concept's concept.py into final/",
    "params.json": "write final/params.json ({} if the concept has no parameters)",
    "tokens.json": "write final/tokens.json (the approved colours)",
    "rationale.md": "write final/rationale.md (one paragraph on why this mark)",
}


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


def brand_name(name: str) -> str:
    """`name` without the spaces around it. An empty name, or one of spaces only, is a CliError: the sheets draw its first
    letter or digit, and the package's files are named after it."""
    stripped = name.strip()
    if not stripped:
        raise CliError(f"A brand name cannot be empty or only spaces, got {name!r}")
    return stripped


def new_brand(paths: ProjectPaths, name: str, slug: str | None = None, unnamed: bool = False) -> BrandState:
    name = brand_name(name)
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
    name = brand_name(name)  # before the brand is read, so a refused name changes nothing
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


def _need(brand: Path, path: Path, model: type[BaseModel] | None = None, remedy: str = "") -> list[str]:
    """Return a message if `path` is missing (followed by `remedy`, when given) or, when `model` is given, does not
    validate as it."""
    label = str(path.relative_to(brand))
    if not path.is_file():
        return [f"{label} is missing; {remedy}" if remedy else f"{label} is missing"]
    err = _validate_file(path, model, label) if model is not None else None
    return [err] if err else []


def _read_json(brand: Path, path: Path, label: str | None = None) -> tuple[dict[str, Any], str | None]:
    """`path` parsed as a JSON object, or ({}, a message calling it `label`, else naming it relative to `brand`)."""
    label = label or str(path.relative_to(brand))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as err:  # malformed JSON, or bytes that are not UTF-8
        return {}, f"{label} is not valid JSON: {err}"
    return (data, None) if isinstance(data, dict) else ({}, f"{label} is not a JSON object")


# Each phase check takes the brand folder, its state and `current`: whether the brand is in that check's phase (the
# phase it is leaving) rather than past it. Only the concept check reads `current`.
def _check_brief(brand: Path, state: BrandState, current: bool = True) -> list[str]:
    return _need(brand, brand / "brief.md") + _need(brand, brand / "brief.json", Brief)


def _check_naming(brand: Path, state: BrandState, current: bool = True) -> list[str]:
    # Only a brand leaving the naming phase owes naming.md; one that never needed a name went intake -> strategy.
    if state.phase != Phase.naming:
        return []
    return _need(brand, brand / "naming.md")


def _check_strategy(brand: Path, state: BrandState, current: bool = True) -> list[str]:
    return _need(brand, brand / "strategy.md") + _need(brand, brand / "strategy.json", Strategy)


def _check_territories(brand: Path, state: BrandState, current: bool = True) -> list[str]:
    """territories.json must be a valid TerritoriesSpec (its slugs are slugs, and unique) that holds the chosen territory."""
    path = brand / "territories" / "territories.json"
    try:
        spec = load_model(path, TerritoriesSpec, str(path.relative_to(brand)))
    except CliError as err:  # missing, malformed or invalid, named as the gate names it
        return [str(err)]
    if state.territory not in [t.slug for t in spec.territories]:
        return [f"territory not chosen (run: logomaker brand set {state.slug} --territory <territory-slug>)"]
    return []


def audit_problems(paths: ProjectPaths, slug: str, folder: Path, label: str | None = None, strict: bool = True) -> list[str]:
    """Why <folder>/audit.json does not vouch for the concept as it is now, or [] when it does: it is missing or not a
    JSON object, stale (its fingerprint is not audit.concept_fingerprint of the concept now), made with --no-render, or
    failing. With strict=False only the first two count: an audit on record, what a phase past concepts asks of the
    chosen concept, since final/ is what ships. Each message ends with the command that clears it, a `concept audit`
    of the folder (`final` for final/). The concept and final gates, the concept and refine sheets and package build
    all ask this. Every message calls the file `label`; without one, they name it as the gate always has: from the
    brand folder when it is missing or malformed, else <concept>/audit.json."""
    from .audit import concept_fingerprint  # imported here: audit imports registry

    brand = paths.brand(slug)
    path = folder / "audit.json"
    audit = f"logomaker concept audit {slug} {folder.name}"  # final/ is the concept named final
    if not path.is_file():
        return [f"{label or path.relative_to(brand)} is missing (run: {audit})"]
    result, error = _read_json(brand, path, label)
    if error:
        return [f"{error} (run: {audit})"]
    if not strict:
        return []
    label = label or f"{folder.name}/audit.json"
    problems = []
    if result.get("fingerprint") != concept_fingerprint(paths, slug, folder):
        problems.append(f"{label} is stale (concept.py, params.json, tokens.json, the brand's industry or "
                        f"minimum sizes, or cliches.json changed); re-run: {audit}")
    if not result.get("rendered"):
        problems.append(f"{label} was made with --no-render; re-run without it: {audit}")
    if not result.get("ok"):
        problems.append(f"{label} has failures; fix them, then re-run: {audit}")
    return problems


def require_final_audit(paths: ProjectPaths, slug: str, needs: str) -> None:
    """A CliError (exit 2) unless final/audit.json vouches for the final mark as it is now (audit_problems), saying what
    `needs` it ("packaging", "the refine sheet") and listing each problem with the command that clears it."""
    problems = audit_problems(paths, slug, paths.brand(slug) / "final", "final/audit.json")
    if problems:
        raise CliError(f"{needs} needs a passing audit of the final mark: {'; '.join(problems)}")


def passing_scorecard(folder: Path, label: str) -> Scorecard:
    """<folder>/scorecard.json if it validates, records its route and probe, and passes the gate (Scorecard.gate_ok); else a
    CliError calling it `label`."""
    card = load_model(folder / "scorecard.json", Scorecard, label)
    if card.route is None or card.probe is None:
        raise CliError(f"{label} needs route and probe (scorecard.md)")
    if not card.gate_ok:
        criteria = f"{', '.join(GATE[:-1])} and {GATE[-1]}"
        raise CliError(f"{label} fails the gate ({criteria} must be {GATE_MIN} or more, and not killed)")
    return card


def vetted_scorecard(paths: ProjectPaths, slug: str, folder: Path, label: str) -> tuple[Scorecard, CriticCard]:
    """The designer's passing scorecard (passing_scorecard) and the critic's fresh card for `folder`, with every criterion
    they put two or more apart reconciled in the scorecard; otherwise a CliError saying what to do (spec 2026-10-08 §3.3)."""
    from . import critic as criticlib  # imported here to keep registry import-light

    card = passing_scorecard(folder, label)
    critic_label = label.replace("scorecard.json", "critic.json")
    problems = criticlib.critic_problems(paths, slug, folder, critic_label)
    if problems:
        raise CliError("; ".join(problems))
    critic_card = load_model(folder / "critic.json", CriticCard, critic_label)
    open_ = criticlib.unreconciled(card, critic_card)
    if open_:
        raise CliError(f"designer and critic disagree by {criticlib.DISAGREEMENT} or more on {', '.join(open_)}; "
                       f"add a reconciled entry for each to {label}")
    return card, critic_card


def require_final_critic(paths: ProjectPaths, slug: str, needs: str) -> None:
    """A CliError (exit 2) unless final/critic.json vouches for the final mark as it is now and final/scorecard.json exists
    with every disagreement reconciled (final_critic_problems), saying what `needs` it ("packaging")."""
    problems = final_critic_problems(paths, slug)
    if problems:
        raise CliError(f"{needs} needs the critic's pass on the final mark: {'; '.join(problems)}")


def final_critic_problems(paths: ProjectPaths, slug: str) -> list[str]:
    """Why final/critic.json and final/scorecard.json do not vouch for the final mark as it is now, or []: the critic's
    card is missing, malformed or stale (critic.critic_problems), the scorecard is missing or malformed, or the two put a
    criterion two or more apart with no reconciled entry."""
    from . import critic as criticlib

    final = paths.brand(slug) / "final"
    problems = criticlib.critic_problems(paths, slug, final, "final/critic.json")
    if problems:
        return problems
    if not (final / "scorecard.json").is_file():
        return ["final/scorecard.json is missing; re-score final/ after the last refinement round (scorecard.md)"]
    try:
        card = load_model(final / "scorecard.json", Scorecard, "final/scorecard.json")
    except CliError as err:
        return [str(err)]
    critic_card = load_model(final / "critic.json", CriticCard, "final/critic.json")
    open_ = criticlib.unreconciled(card, critic_card)
    if open_:
        return [f"designer and critic disagree by {criticlib.DISAGREEMENT} or more on {', '.join(open_)}; "
                "add a reconciled entry for each to final/scorecard.json"]
    return []


def _check_concept(brand: Path, state: BrandState, current: bool = True) -> list[str]:
    """The chosen concept needs a scorecard that passes the gate (passing_scorecard) and, when the brand is leaving the
    concepts phase (`current`), a passing, rendered audit of what it is now (audit_problems), a fresh critic card the
    scorecard is reconciled with (vetted_scorecard) and a recorded image knock-out (knockout.knockout_problems). Once
    the brand is past it, final/ is what ships and has its own gate, so the concept's audit need only be on record:
    present and valid JSON, and its knock-out is not asked for."""
    if not state.concept:
        return [f"concept not chosen (run: logomaker brand set {state.slug} --concept <NN-slug>)"]
    folder = brand / "concepts" / state.concept
    paths = ProjectPaths(brand.parent.parent)  # brand is brands/<slug> under the project root
    missing = _need(brand, folder / "concept.py") + audit_problems(paths, state.slug, folder, strict=current)
    try:
        if current:
            vetted_scorecard(paths, state.slug, folder, f"{state.concept}/scorecard.json")
        else:
            passing_scorecard(folder, f"{state.concept}/scorecard.json")
    except CliError as err:
        missing.append(str(err))
    if current:
        from .knockout import knockout_problems  # imported here: knockout imports registry

        missing += knockout_problems(paths, state.slug, folder)
    return missing


def _check_final(brand: Path, state: BrandState, current: bool = True) -> list[str]:
    """final/ needs concept.py, params.json, a valid tokens.json, and an audit.json that vouches for the final mark as it
    is now (audit_problems: present, fresh, rendered and passing); once those hold, a fresh critic card and a scorecard
    reconciled with it (final_critic_problems); once those hold, final/knockout.json with the image knock-out and the
    WIPO image search (knockout.knockout_problems)."""
    from .color import Tokens  # imported here to keep registry import-light

    final = brand / "final"
    missing: list[str] = []
    for name in ("concept.py", "params.json"):
        missing += _need(brand, final / name, remedy=FINAL_REMEDIES[name])
    missing += _need(brand, final / "tokens.json", model=Tokens, remedy=FINAL_REMEDIES["tokens.json"])
    paths = ProjectPaths(brand.parent.parent)  # brand is brands/<slug> under the project root
    problems = missing + audit_problems(paths, state.slug, final, "final/audit.json")
    if problems:
        return problems
    from .knockout import knockout_problems  # imported here: knockout imports registry

    return final_critic_problems(paths, state.slug) or knockout_problems(paths, state.slug, final, "final/knockout.json", final=True)


def _check_verify(brand: Path, state: BrandState, current: bool = True) -> list[str]:
    """package/verify.json must report ok for a package built from final/ and the brand as they are now: the inputs
    fingerprint it checked is export_docs.inputs_fingerprint's now."""
    from .export_docs import inputs_fingerprint, out_of_date  # imported here: export_docs imports registry

    verify, command = brand / "package" / "verify.json", f"logomaker package verify {state.slug}"
    if not verify.is_file():
        return [f"package/verify.json is missing (run: {command})"]
    result, error = _read_json(brand, verify)
    if error:
        return [f"{error} (run: {command})"]
    if not result.get("ok"):
        return [f"package/verify.json reports failures (run: {command} to list them)"]
    if result.get("inputs") != inputs_fingerprint(ProjectPaths(brand.parent.parent), state.slug):
        return [out_of_date(state.slug)]
    return []


# The artifacts each phase leaves behind. Advancing to a phase re-runs the checks of every phase before it, each told
# whether it is the brand's current phase.
PHASE_CHECKS: dict[Phase, Callable[[Path, BrandState, bool], list[str]]] = {
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
        missing += PHASE_CHECKS[phase](brand, state, phase == state.phase)
    if target == Phase.strategy and state.needs_name:
        missing.append(f"brand still needs a name (run: logomaker brand rename {state.slug} --name <Name>)")
    return missing


def advance(paths: ProjectPaths, slug: str, target: Phase) -> BrandState:
    state = load_state(paths, slug)
    missing = prerequisites(paths, state, target)
    if missing:
        raise CliError(f"Cannot advance {slug} to {target.value}", data={"missing": missing})
    state.phase = target
    save_state(paths, state)
    return state
