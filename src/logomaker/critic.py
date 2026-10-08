"""The blind critic (spec 2026-10-08 §3): the pass files a fresh agent writes from the lettered sheet, the key that maps
letters back to concepts, the merge into <concept>/critic.json, and the checks the gates ask of a card."""
from __future__ import annotations

import json
import math
from itertools import combinations
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, model_validator

from .output import CliError
from .paths import ProjectPaths
from .schemas import CRITERIA, CriticCard, Scorecard, check_scores

LETTERS = "ABCDEFGH"  # the concept sheet shows three to five survivors; eight is the most directions a brand builds
DISAGREEMENT = 2  # a designer and critic score this far apart needs a reconciled entry


class PassCard(BaseModel):
    scores: dict[str, int]
    evidence: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def complete_and_in_range(self) -> PassCard:
        check_scores(self.scores)
        return self


class Pair(BaseModel):
    first: str
    second: str
    prefer: str
    why: str = ""

    @model_validator(mode="after")
    def prefers_one_of_its_letters(self) -> Pair:
        if self.first == self.second:
            raise ValueError("a pair needs two different letters")
        if self.prefer not in (self.first, self.second, "tie"):
            raise ValueError(f"prefer must be {self.first}, {self.second} or tie, got {self.prefer!r}")
        return self


class CriticPass(BaseModel):
    """sheets/critic-N.pass-K.json: one critic run over the lettered sheet."""

    cards: dict[str, PassCard]
    pairs: list[Pair] = Field(default_factory=list)


class Key(BaseModel):
    """sheets/critic-N.key.json: what the critic was not told. Letter to concept folder name (`final` for the final sheet)
    and each concept's fingerprint when the sheet was made."""

    round: int
    seed: int
    letters: dict[str, str]
    fingerprints: dict[str, str]
    final: bool = False

    @model_validator(mode="after")
    def fingerprints_every_concept(self) -> Key:
        missing = sorted(set(self.letters.values()) - set(self.fingerprints))
        if missing:
            raise ValueError(f"fingerprints missing for {', '.join(missing)}")
        return self


def round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def _check_pass(label: str, run: CriticPass, letters: set[str]) -> None:
    scored = set(run.cards)
    if scored != letters:
        raise CliError(f"{label} scores {', '.join(sorted(scored))}; the sheet has {', '.join(sorted(letters))}")
    for pair in run.pairs:
        if pair.first not in letters or pair.second not in letters:
            raise CliError(f"{label} judges {pair.first} against {pair.second}; the sheet has {', '.join(sorted(letters))}")
    for a, b in combinations(sorted(letters), 2):
        orders = {(p.first, p.second) for p in run.pairs if {p.first, p.second} == {a, b}}
        if orders and orders != {(a, b), (b, a)}:
            raise CliError(f"{label} judges {a} and {b} in one order only; judge every pair in both orders")


def _check_keys(keys: list[Key]) -> None:
    """Every critic sheet merged together (one key each) letters the same concepts, each with the same fingerprint."""
    first = keys[0]
    for key in keys[1:]:
        ours, theirs = set(first.letters.values()), set(key.letters.values())
        if ours != theirs:
            raise CliError(f"sheet {key.round} keys different concepts from sheet {first.round}: "
                           f"{', '.join(sorted(theirs))} against {', '.join(sorted(ours))}")
        for slug in sorted(ours):
            if key.fingerprints[slug] != first.fingerprints[slug]:
                raise CliError(f"{slug} changed between sheet {first.round} and sheet {key.round}; run sheet critic again")


def merge(runs: list[tuple[Key, CriticPass]]) -> dict[str, CriticCard]:
    """One CriticCard per concept, from every pass of every critic sheet in `runs` (each pass with its own sheet's key):
    each pass is checked against its key, then translated from letters to concepts, and the passes merged: mean scores
    rounded half up, every evidence line, and a preference only where every verdict in every pass and both orders
    agrees. The sheets must letter the same concepts with the same fingerprints. `sheet` is the highest round merged.
    A pass that scores other letters than its sheet's, or judges a pair in one order only, is a CliError naming it."""
    if not runs:
        raise CliError("the merge needs at least one pass file")
    keys = list({key.round: key for key, _ in runs}.values())  # one per sheet, in the order given
    _check_keys(keys)
    several = len(keys) > 1
    counts: dict[int, int] = {}
    named: list[tuple[dict[str, PassCard], list[tuple[str, str, str]]]] = []  # each pass's cards and verdicts by concept
    for key, run in runs:
        counts[key.round] = counts.get(key.round, 0) + 1
        label = f"sheet {key.round} pass {counts[key.round]}" if several else f"pass {counts[key.round]}"
        _check_pass(label, run, set(key.letters))
        to = key.letters
        verdicts = [(to[p.first], to[p.second], "tie" if p.prefer == "tie" else to[p.prefer]) for p in run.pairs]
        named.append(({to[letter]: card for letter, card in run.cards.items()}, verdicts))
    first = runs[0][0]
    sheet = max(key.round for key, _ in runs)
    cards: dict[str, CriticCard] = {}
    for slug in first.letters.values():
        scores = {c: round_half_up(sum(pass_cards[slug].scores[c] for pass_cards, _ in named) / len(named)) for c in CRITERIA}
        evidence = {c: [pass_cards[slug].evidence[c] for pass_cards, _ in named if c in pass_cards[slug].evidence] for c in CRITERIA}
        preferred, tied = [], []
        for other in first.letters.values():
            if other == slug:
                continue
            said = [prefer for _, verdicts in named for a, b, prefer in verdicts if {a, b} == {slug, other}]
            if said and all(v == slug for v in said):
                preferred.append(other)
            else:  # `tied_with` is the rest (spec §3.2), so a concept the other beat is listed here too
                tied.append(other)
        cards[slug] = CriticCard(scores=scores, evidence={c: lines for c, lines in evidence.items() if lines},
                                 preferred_over=sorted(preferred), tied_with=sorted(tied), sheet=sheet, passes=len(named),
                                 fingerprint=first.fingerprints[slug])
    return cards


def unreconciled(card: Scorecard, critic: CriticCard) -> list[str]:
    """The criteria the designer's `card` and the critic's card put DISAGREEMENT or more apart with no reconciled entry."""
    return [c for c in CRITERIA if abs(card.scores[c] - critic.scores[c]) >= DISAGREEMENT and c not in card.reconciled]


def _load(path: Path, model: type[BaseModel], label: str):
    if not path.is_file():
        raise CliError(f"{label} is missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as err:
        raise CliError(f"{label} is not valid JSON: {err}") from err
    try:
        return model.model_validate(data)
    except ValidationError as err:
        first = err.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "root"
        raise CliError(f"{label} is invalid: {loc}: {first['msg']}") from err


def key_path(brand: Path, round_n: int) -> Path:
    return brand / "sheets" / f"critic-{round_n}.key.json"


def pass_paths(brand: Path, round_n: int) -> list[Path]:
    """sheets/critic-N.pass-K.json, K ascending."""
    paths = brand.glob(f"sheets/critic-{round_n}.pass-*.json")
    numbered = [(int(p.stem.rsplit("-", 1)[1]), p) for p in paths if p.stem.rsplit("-", 1)[1].isdecimal()]
    return [p for _, p in sorted(numbered)]


def write_cards(paths: ProjectPaths, slug: str, rounds: list[int]) -> dict:
    """Merge the passes of every critic sheet in `rounds`, each by its own key, and write critic.json into each concept's
    folder (final/ for a final sheet). Each sheet needs a pass file, and the sheets must letter the same concepts with
    the same fingerprints. Nothing is written until every pass has been validated."""
    if not rounds:
        raise CliError("give at least one critic sheet (--sheet N)")
    twice = sorted({n for n in rounds if rounds.count(n) > 1})
    if twice:
        raise CliError(f"sheet {', '.join(map(str, twice))} is named twice; give each critic sheet once")
    brand = paths.brand(slug)
    runs: list[tuple[Key, CriticPass]] = []
    for round_n in rounds:
        key = _load(key_path(brand, round_n), Key, f"sheets/critic-{round_n}.key.json")
        files = pass_paths(brand, round_n)
        if not files:
            raise CliError(f"no pass files for critic sheet {round_n}; the critic writes sheets/critic-{round_n}.pass-1.json")
        runs += [(key, _load(path, CriticPass, str(path.relative_to(brand)))) for path in files]
    cards = merge(runs)
    sheets = " and ".join(map(str, rounds))
    folders = {name: brand / "final" if name == "final" else brand / "concepts" / name for name in cards}
    for folder in folders.values():
        if not folder.is_dir():
            raise CliError(f"{folder.relative_to(brand)} is missing; critic sheet {sheets} lettered it")
    written = {}
    for name, card in cards.items():
        target = folders[name] / "critic.json"
        target.write_text(json.dumps(card.model_dump(), indent=2) + "\n", encoding="utf-8")
        written[name] = str(target)
    return {"sheets": list(rounds), "passes": len(runs), "cards": written}


def refresh_command(slug: str, folder: Path) -> str:
    """How to give `folder` a fresh critic card: its critic sheet, the critic run, and the merge."""
    target = "--final" if folder.name == "final" else f"--concepts {folder.name}"
    return f"logomaker sheet critic {slug} {target}, dispatch the critic, then logomaker concept critic {slug} --sheet N"


def critic_problems(paths: ProjectPaths, slug: str, folder: Path, label: str | None = None) -> list[str]:
    """Why <folder>/critic.json does not vouch for the concept as it is now, or []: missing, not valid JSON, invalid, or
    stale (its fingerprint is not audit.concept_fingerprint of the concept now). Each message ends with how to refresh it."""
    from .audit import concept_fingerprint  # imported here: audit imports registry, which imports this module

    label = label or f"{folder.name}/critic.json"
    path = folder / "critic.json"
    how = refresh_command(slug, folder)
    if not path.is_file():
        return [f"{label} is missing (run: {how})"]
    try:
        card = _load(path, CriticCard, label)
    except CliError as err:
        return [f"{err} (run: {how})"]
    if card.fingerprint != concept_fingerprint(paths, slug, folder):
        return [f"{label} is stale (the concept changed since the critic saw it); re-run: {how}"]
    return []


def preference_line(cards: dict[str, CriticCard], slug: str = "<slug>") -> str:
    """The critic's order as one line: concepts grouped by how many they beat, best first, `>` between groups, `=` within.
    A card's wins count only the concepts on its own critic sheet, so when the cards come from different sheets there is
    no one order: the line says so and names the critic sheet of brand `slug` that would give one."""
    if len({card.sheet for card in cards.values()}) > 1:
        return (f"not comparable; the cards come from different critic sheets (one order: logomaker sheet critic {slug} "
                f"--concepts {','.join(cards)})")
    groups: dict[int, list[str]] = {}
    for name, card in cards.items():
        groups.setdefault(len(card.preferred_over), []).append(name)
    return " > ".join(" = ".join(sorted(groups[wins])) for wins in sorted(groups, reverse=True))
