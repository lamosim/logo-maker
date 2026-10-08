# Raising the Ceiling, Plan 1: Blind Critic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A second, blind designer scores every survivor from an anonymised, shuffled sheet, and the owner never sees a concept whose designer and critic scores disagree by two or more without a written reconciliation.

**Architecture:** A new `sheets.critic_sheet` renders the survivors' critique panels lettered A, B, C in a seeded shuffle and writes a key file the critic never sees. A fresh Opus subagent (dispatched by the skill, not the CLI) writes one pass file per run. A new `critic` module validates the passes, merges them by the key into `critic.json` per concept, and tells the gates whether a card is missing, stale or unreconciled. The concept sheet, the concept gate and the package build read it.

**Tech Stack:** Python 3.12, pydantic 2, click, jinja2, skia-python; Chrome through Playwright for the sheet; pytest with the repo's `StubChrome` for tests without Chrome.

**Spec:** `docs/superpowers/specs/2026-10-08-raising-the-ceiling-design.md`, section 3 (WS1), with section 9 for the file map. The first spec, `docs/superpowers/specs/2026-10-05-logo-maker-design.md`, still governs the CLI contract (its section 10) and the scorecard (8.2).

## Global Constraints

- Every CLI command prints one JSON object on stdout and nothing else; logs go to stderr. Exit codes: 0 ok, 2 rule or input violation, 3 external failure, 4 verification failure (`CLAUDE.md`).
- Chrome is the installed Google Chrome through Playwright `channel="chrome"`; never `playwright install`.
- Nothing reaches the owner that failed an audit or a gate: a sheet refuses, with the command that clears it, before Chrome starts.
- Subagents run on Opus or cheaper with `model` set explicitly, never inherited (`.claude/skills/logo/SKILL.md`, "Parallel concepts with subagents"; the test `test_skill_pins_the_review_focus_behaviours` checks the sentence).
- Reference files: a `# Title` line, then `Read this when: ...`, level-two headings, 600 to 2000 words, a closing `## Sources` section, at least three source tags such as `[spec §3.2]` or `[code]` (`tests/test_knowledge.py`).
- Every `logomaker <group> <command> --option` mentioned in any skill document must exist on the CLI (`tests/test_knowledge.py::cli_problems`).
- Ruff: line length 140, rules E, F, I, UP. Run `uv run ruff check src tests` before each commit.
- Commit after every task with a message in the repo's style (`feat:`, `fix:`, `docs:`, `test:`), ending with the attribution line from the session's system reminder.

## Review Focus

1. A critic pass that scores a letter the sheet never had, or misses one: `concept critic` must exit 2 naming the letters, never write a half set of cards. Pinned in Task 2.
2. A survivor whose module changed after the critic sheet: its `critic.json` is stale, and `sheet concepts` must refuse it with the two commands that refresh it. Pinned in Task 5.
3. A designer card that differs from the critic by two on a non-gate criterion with no `reconciled` entry: still refused, since the rule covers all ten criteria. Pinned in Task 5.
4. One pass only (an interrupted second run): the merge still works, `passes` records 1, and the sheet says so. Pinned in Task 2 and Task 5.
5. `--final` with `--concepts`, or neither: `sheet critic` exits 2 with the usage error, before touching the brand. Pinned in Task 3.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/logomaker/schemas.py` (modify) | `CriticCard`; `Scorecard.reconciled`; a shared `check_scores` helper |
| `src/logomaker/critic.py` (create) | `CriticPass`, `Pair`, `Key` models; `merge`; `write_cards`; `critic_problems`; `unreconciled` |
| `src/logomaker/sheets.py` (modify) | `critic_sheet`; the concept sheet's two totals and preference line |
| `templates/sheets/critic.html` (create) | the lettered, anonymised sheet |
| `templates/sheets/concepts.html` (modify) | critic total and preference line |
| `src/logomaker/registry.py` (modify) | `vetted_scorecard`, `require_final_critic`; `_check_concept` and `_check_final` read the critic |
| `src/logomaker/export.py` (modify) | `PackageBuilder.__init__` requires a fresh final critic |
| `src/logomaker/cli.py` (modify) | `sheet critic`, `concept critic` |
| `.claude/skills/logo/reference/critic.md` (create) | the critic's brief |
| `.claude/skills/logo/SKILL.md`, `reference/process.md`, `reference/scorecard.md` (modify) | the runbook steps |
| `tests/test_critic.py` (create), `tests/test_concepts_sheet.py`, `tests/test_registry.py`, `tests/test_knowledge.py`, `tests/test_skill_docs.py` (modify) | tests |

---

### Task 1: `CriticCard` and `Scorecard.reconciled`

**Files:**
- Modify: `src/logomaker/schemas.py` (after `Scorecard`, around line 260 to 285)
- Test: `tests/test_critic.py` (create)

**Interfaces:**
- Consumes: `schemas.CRITERIA`.
- Produces: `schemas.check_scores(scores: dict[str, int]) -> None` (raises `ValueError` as `Scorecard` does today); `schemas.CriticCard(scores, evidence: dict[str, list[str]], preferred_over: list[str], tied_with: list[str], sheet: int, passes: int, fingerprint: str)` with `.total`; `Scorecard.reconciled: dict[str, str]` (default empty).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_critic.py
import pytest
from pydantic import ValidationError

from logomaker.schemas import CRITERIA, CriticCard, Scorecard
from tests.conftest import scorecard


def critic_card(**overrides) -> dict:
    scores = {c: 4 for c in CRITERIA}
    scores.update(overrides)
    return {"scores": scores, "evidence": {"appropriate": ["reads as an arch", "an arch at once"]}, "preferred_over": ["01-k-jaw"],
            "tied_with": [], "sheet": 1, "passes": 2, "fingerprint": "abc"}


def test_critic_card_validates_like_a_scorecard():
    card = CriticCard.model_validate(critic_card())
    assert card.total == 40 and card.passes == 2 and card.preferred_over == ["01-k-jaw"]
    with pytest.raises(ValidationError, match="scores missing: distinctive"):
        CriticCard.model_validate({**critic_card(), "scores": {c: 4 for c in CRITERIA if c != "distinctive"}})
    with pytest.raises(ValidationError, match="scores must be 1..5"):
        CriticCard.model_validate(critic_card(simple=0))


def test_scorecard_takes_reconciled_entries_and_defaults_to_none():
    assert Scorecard.model_validate(scorecard()).reconciled == {}
    card = Scorecard.model_validate({**scorecard(), "reconciled": {"distinctive": "the critic saw the stock arches; 3 stands"}})
    assert card.reconciled["distinctive"].startswith("the critic")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_critic.py -q`
Expected: FAIL with `ImportError: cannot import name 'CriticCard'`.

- [ ] **Step 3: Add the helper, the field and the model**

In `src/logomaker/schemas.py`, replace the body of `Scorecard.complete_and_in_range` with a call to a shared helper, add `reconciled`, and add `CriticCard` after `Scorecard`:

```python
def check_scores(scores: dict[str, int]) -> None:
    """Raise ValueError unless `scores` holds every criterion, each a whole number 1 to 5: the rule of Scorecard and CriticCard."""
    missing = [c for c in CRITERIA if c not in scores]
    if missing:
        raise ValueError(f"scores missing: {', '.join(missing)}")
    bad = {k: v for k, v in scores.items() if not 1 <= v <= 5}
    if bad:
        raise ValueError(f"scores must be 1..5: {bad}")


class Scorecard(BaseModel):
    """<concept>/scorecard.json: Claude's ten scores (spec 8.2), each 1 to 5, with evidence, whether the concept is killed,
    and `reconciled`: for each criterion the blind critic's card disagrees on by two or more, one line saying whose score
    stands and why (spec 2026-10-08 §3.3)."""

    scores: dict[str, int]
    evidence: dict[str, str] = Field(default_factory=dict)
    kill: bool = False
    reason: str = ""
    reconciled: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def complete_and_in_range(self) -> Scorecard:
        check_scores(self.scores)
        return self

    @property
    def gate_ok(self) -> bool:
        return not self.kill and all(self.scores[c] >= GATE_MIN for c in GATE)

    @property
    def total(self) -> int:
        return sum(self.scores[c] for c in CRITERIA)


class CriticCard(BaseModel):
    """<concept>/critic.json: the blind critic's merged card (spec 2026-10-08 §3.2). `scores` are the mean of the passes,
    rounded half up; `evidence` holds every pass's line per criterion; `preferred_over` the slugs this concept beat in
    every pass and both orders, `tied_with` the rest; `fingerprint` is audit.concept_fingerprint of the concept the
    critic saw, so a later change makes the card stale."""

    scores: dict[str, int]
    evidence: dict[str, list[str]] = Field(default_factory=dict)
    preferred_over: list[str] = Field(default_factory=list)
    tied_with: list[str] = Field(default_factory=list)
    sheet: int
    passes: int
    fingerprint: str

    @model_validator(mode="after")
    def complete_and_in_range(self) -> CriticCard:
        check_scores(self.scores)
        return self

    @property
    def total(self) -> int:
        return sum(self.scores[c] for c in CRITERIA)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_critic.py tests/test_concepts_sheet.py::test_scorecard_validation_and_gate -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/schemas.py tests/test_critic.py
git commit -m "feat: CriticCard model and Scorecard.reconciled"
```

---

### Task 2: The critic module: pass files, the key and the merge

**Files:**
- Create: `src/logomaker/critic.py`
- Test: `tests/test_critic.py` (extend)

**Interfaces:**
- Consumes: `schemas.CriticCard`, `schemas.CRITERIA`, `schemas.check_scores`, `output.CliError`.
- Produces: `critic.LETTERS = "ABCDEFGH"`; `critic.DISAGREEMENT = 2`; `critic.PassCard(scores, evidence: dict[str, str])`; `critic.Pair(first, second, prefer, why="")` where `prefer` is `first`, `second` or `"tie"`; `critic.CriticPass(cards: dict[str, PassCard], pairs: list[Pair])`; `critic.Key(round, seed, letters: dict[str, str], fingerprints: dict[str, str], final: bool)`; `critic.merge(key, passes) -> dict[str, CriticCard]` keyed by slug; `critic.unreconciled(card: Scorecard, critic: CriticCard) -> list[str]`; `critic.round_half_up(value: float) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_critic.py`:

```python
from logomaker import critic
from logomaker.output import CliError


def pass_card(**overrides) -> dict:
    scores = {c: 4 for c in CRITERIA}
    scores.update(overrides)
    return {"scores": scores, "evidence": {"distinctive": "an arch, which stock sites already sell"}}


def both_orders(a: str, b: str, prefer: str) -> list[dict]:
    return [{"first": a, "second": b, "prefer": prefer}, {"first": b, "second": a, "prefer": prefer}]


KEY = {"round": 1, "seed": 1, "letters": {"A": "02-arch", "B": "01-k-jaw"}, "fingerprints": {"02-arch": "f2", "01-k-jaw": "f1"}}


def test_pair_prefers_one_of_its_letters_or_a_tie():
    assert critic.Pair(first="A", second="B", prefer="tie").prefer == "tie"
    with pytest.raises(ValidationError, match="prefer must be A, B or tie"):
        critic.Pair(first="A", second="B", prefer="C")
    with pytest.raises(ValidationError, match="a pair needs two different letters"):
        critic.Pair(first="A", second="A", prefer="A")


def test_merge_averages_scores_half_up_and_keeps_every_line():
    first = critic.CriticPass(cards={"A": pass_card(distinctive=3), "B": pass_card()}, pairs=both_orders("A", "B", "A"))
    second = critic.CriticPass(cards={"A": pass_card(distinctive=4, simple=5), "B": pass_card()}, pairs=both_orders("A", "B", "A"))
    cards = critic.merge(critic.Key.model_validate(KEY), [first, second])
    arch = cards["02-arch"]
    assert arch.scores["distinctive"] == 4 and arch.scores["simple"] == 5  # 3.5 rounds up, 4.5 rounds up
    assert arch.evidence["distinctive"] == ["an arch, which stock sites already sell"] * 2
    assert arch.passes == 2 and arch.sheet == 1 and arch.fingerprint == "f2"
    assert arch.preferred_over == ["01-k-jaw"] and arch.tied_with == []
    assert cards["01-k-jaw"].preferred_over == [] and cards["01-k-jaw"].tied_with == ["02-arch"]


def test_merge_calls_a_pair_tied_unless_every_verdict_agrees():
    pairs = both_orders("A", "B", "A")[:1] + both_orders("A", "B", "B")[1:]  # A first order, B the other
    one = critic.CriticPass(cards={"A": pass_card(), "B": pass_card()}, pairs=pairs)
    cards = critic.merge(critic.Key.model_validate(KEY), [one])
    assert cards["02-arch"].tied_with == ["01-k-jaw"] and cards["01-k-jaw"].tied_with == ["02-arch"]
    assert cards["02-arch"].passes == 1


def test_merge_refuses_a_pass_whose_letters_do_not_match_the_sheet():
    key = critic.Key.model_validate(KEY)
    with pytest.raises(CliError, match=r"pass 1 scores A, C; the sheet has A, B"):
        critic.merge(key, [critic.CriticPass(cards={"A": pass_card(), "C": pass_card()})])
    with pytest.raises(CliError, match=r"pass 1 judges A and B in one order only; judge every pair in both orders"):
        critic.merge(key, [critic.CriticPass(cards={"A": pass_card(), "B": pass_card()}, pairs=both_orders("A", "B", "A")[:1])])
    with pytest.raises(CliError, match="at least one pass"):
        critic.merge(key, [])


def test_unreconciled_lists_every_criterion_two_or_more_apart_without_an_entry():
    designer = Scorecard.model_validate({**scorecard(distinctive=5, timeless=2), "reconciled": {"timeless": "the critic saw a trend"}})
    card = CriticCard.model_validate(critic_card(distinctive=3, timeless=4, simple=3))
    assert critic.unreconciled(designer, card) == ["distinctive"]  # simple differs by 1; timeless is reconciled


def test_round_half_up():
    assert [critic.round_half_up(v) for v in (3.0, 3.49, 3.5, 4.5)] == [3, 3, 4, 5]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_critic.py -q`
Expected: FAIL with `ImportError: cannot import name 'critic'`.

- [ ] **Step 3: Write the module**

```python
# src/logomaker/critic.py
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


def round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def _check_pass(number: int, run: CriticPass, letters: set[str]) -> None:
    scored = set(run.cards)
    if scored != letters:
        raise CliError(f"pass {number} scores {', '.join(sorted(scored))}; the sheet has {', '.join(sorted(letters))}")
    for pair in run.pairs:
        if pair.first not in letters or pair.second not in letters:
            raise CliError(f"pass {number} judges {pair.first} against {pair.second}; the sheet has {', '.join(sorted(letters))}")
    for a, b in combinations(sorted(letters), 2):
        orders = {(p.first, p.second) for p in run.pairs if {p.first, p.second} == {a, b}}
        if orders and orders != {(a, b), (b, a)}:
            raise CliError(f"pass {number} judges {a} and {b} in one order only; judge every pair in both orders")


def merge(key: Key, passes: list[CriticPass]) -> dict[str, CriticCard]:
    """One CriticCard per concept in `key`, from every pass: mean scores rounded half up, every evidence line, and a
    preference only where every verdict in every pass and both orders agrees. A pass that scores other letters than the
    sheet's, or judges a pair in one order only, is a CliError naming it."""
    if not passes:
        raise CliError("the merge needs at least one pass file")
    letters = set(key.letters)
    for number, run in enumerate(passes, start=1):
        _check_pass(number, run, letters)
    cards: dict[str, CriticCard] = {}
    for letter, slug in key.letters.items():
        scores = {c: round_half_up(sum(run.cards[letter].scores[c] for run in passes) / len(passes)) for c in CRITERIA}
        evidence = {c: [run.cards[letter].evidence[c] for run in passes if c in run.cards[letter].evidence] for c in CRITERIA}
        preferred, tied = [], []
        for other, other_slug in key.letters.items():
            if other == letter:
                continue
            verdicts = [p.prefer for run in passes for p in run.pairs if {p.first, p.second} == {letter, other}]
            if verdicts and all(v == letter for v in verdicts):
                preferred.append(other_slug)
            elif not (verdicts and all(v == other for v in verdicts)):
                tied.append(other_slug)
        cards[slug] = CriticCard(scores=scores, evidence={c: lines for c, lines in evidence.items() if lines},
                                 preferred_over=sorted(preferred), tied_with=sorted(tied), sheet=key.round, passes=len(passes),
                                 fingerprint=key.fingerprints[slug])
    return cards


def unreconciled(card: Scorecard, critic: CriticCard) -> list[str]:
    """The criteria the designer's `card` and the critic's card put DISAGREEMENT or more apart with no reconciled entry."""
    return [c for c in CRITERIA if abs(card.scores[c] - critic.scores[c]) >= DISAGREEMENT and c not in card.reconciled]


def _load(path: Path, model: type[BaseModel], label: str):
    if not path.is_file():
        raise CliError(f"{label} is missing")
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as err:
        first = err.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "root"
        raise CliError(f"{label} is invalid: {loc}: {first['msg']}") from err
    except ValueError as err:
        raise CliError(f"{label} is not valid JSON: {err}") from err


def key_path(brand: Path, round_n: int) -> Path:
    return brand / "sheets" / f"critic-{round_n}.key.json"


def pass_paths(brand: Path, round_n: int) -> list[Path]:
    """sheets/critic-N.pass-K.json, K ascending."""
    paths = brand.glob(f"sheets/critic-{round_n}.pass-*.json")
    numbered = [(int(p.stem.rsplit("-", 1)[1]), p) for p in paths if p.stem.rsplit("-", 1)[1].isdecimal()]
    return [p for _, p in sorted(numbered)]


def write_cards(paths: ProjectPaths, slug: str, round_n: int) -> dict:
    """Merge sheets/critic-N's passes by its key and write critic.json into each concept's folder (final/ for a final
    sheet). Nothing is written until every pass has been validated."""
    brand = paths.brand(slug)
    key = _load(key_path(brand, round_n), Key, f"sheets/critic-{round_n}.key.json")
    files = pass_paths(brand, round_n)
    if not files:
        raise CliError(f"no pass files for critic sheet {round_n}; the critic writes sheets/critic-{round_n}.pass-1.json (and pass-2)")
    passes = [_load(path, CriticPass, str(path.relative_to(brand))) for path in files]
    cards = merge(key, passes)
    written = {}
    for name, card in cards.items():
        folder = brand / "final" if name == "final" else brand / "concepts" / name
        target = folder / "critic.json"
        target.write_text(json.dumps(card.model_dump(), indent=2) + "\n", encoding="utf-8")
        written[name] = str(target)
    return {"sheet": round_n, "passes": len(passes), "cards": written}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_critic.py -q`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/critic.py tests/test_critic.py
git commit -m "feat: critic pass files, key and merge"
```

---

### Task 3: The critic sheet and `sheet critic`

**Files:**
- Modify: `src/logomaker/sheets.py` (after `concepts_sheet`), `src/logomaker/cli.py` (the `sheet` group)
- Create: `templates/sheets/critic.html`
- Test: `tests/test_critic.py` (extend)

**Interfaces:**
- Consumes: `sheets._vetted`, `sheets._strip_panels`, `sheets.mockup_context`, `mockups.render_mockup`, `registry.require_final_audit`, `audit.concept_fingerprint`, `critic.Key`, `critic.LETTERS`, `sheets.next_round`, `sheets._write_sheet`.
- Produces: `sheets.critic_sheet(paths, slug, concept_names: list[str], seed: int | None = None, final: bool = False, renderer=None) -> dict` with keys `sheet_html`, `sheet_png`, `key`, `round`, `letters` (letter to folder name). Files: `sheets/critic-N.html`, `sheets/critic-N.png`, `sheets/critic-N.key.json`. CLI: `sheet critic <slug> [--concepts a,b,c | --final] [--seed N]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_critic.py`:

```python
import json

from click.testing import CliRunner

from logomaker import sheets
from logomaker.cli import main
from logomaker.paths import project
from tests.conftest import StubChrome, install_concept, make_final_brand, write_passing_audit


def prepare(project_root, name: str, fixture: str = "good"):
    folder = install_concept(project_root, fixture, name=name)
    write_passing_audit(project(), "keystone", folder)
    (folder / "scorecard.json").write_text(json.dumps(scorecard()))
    return folder


def run(*args):
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, json.loads(result.stdout)


def test_critic_sheet_letters_the_survivors_in_a_seeded_shuffle_and_writes_the_key(project_root):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    info = sheets.critic_sheet(project(), "keystone", ["01-good", "02-dots"], seed=7, renderer=StubChrome())
    assert info["round"] == 1 and set(info["letters"]) == {"A", "B"} and set(info["letters"].values()) == {"01-good", "02-dots"}
    brand = project_root / "brands" / "keystone"
    key = json.loads((brand / "sheets" / "critic-1.key.json").read_text())
    assert key["letters"] == info["letters"] and key["seed"] == 7 and key["final"] is False
    assert set(key["fingerprints"]) == {"01-good", "02-dots"}
    html = (brand / "sheets" / "critic-1.html").read_text()
    assert "Concept A" in html and "Concept B" in html
    assert "01-good" not in html and "02-dots" not in html and "A ring with a gap" not in html  # no slug, no idea
    assert "/ 50" not in html  # no scores
    other = sheets.critic_sheet(project(), "keystone", ["01-good", "02-dots"], seed=8, renderer=StubChrome())
    assert other["round"] == 2
    assert sorted(other["letters"].values()) == sorted(info["letters"].values())


def test_critic_sheet_refuses_an_unvetted_concept_before_chrome(project_root, no_chrome):
    folder = prepare(project_root, "01-good")
    (folder / "scorecard.json").unlink()
    with pytest.raises(CliError, match="scorecard.json is missing"):
        sheets.critic_sheet(project(), "keystone", ["01-good"])
    assert not list((project_root / "brands" / "keystone" / "sheets").glob("critic-*"))


def test_critic_sheet_for_final_letters_the_final_mark_alone(project_root):
    make_final_brand(project_root)
    info = sheets.critic_sheet(project(), "keystone", [], final=True, renderer=StubChrome())
    assert info["letters"] == {"A": "final"}
    key = json.loads((project_root / "brands" / "keystone" / "sheets" / "critic-1.key.json").read_text())
    assert key["final"] is True and list(key["fingerprints"]) == ["final"]


def test_sheet_critic_cli_needs_concepts_or_final_but_not_both(project_root):
    make_final_brand(project_root)
    code, payload = run("sheet", "critic", "keystone")
    assert code == 2 and payload["errors"] == ["give --concepts <a,b,c> for survivors, or --final for the final mark"]
    code, payload = run("sheet", "critic", "keystone", "--concepts", "01-good", "--final")
    assert code == 2 and payload["errors"] == ["--final takes no --concepts"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_critic.py -q -k critic_sheet`
Expected: FAIL with `AttributeError: module 'logomaker.sheets' has no attribute 'critic_sheet'`.

- [ ] **Step 3: Write the template**

`templates/sheets/critic.html`:

```html
<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body{margin:0;width:{{ width }}px;font:14px/1.4 -apple-system,Helvetica,Arial,sans-serif;background:#f3f3f3;color:#222;padding:24px;box-sizing:border-box}
  h1{font-size:22px;margin:0 0 6px} .intro{color:#555;margin-bottom:18px;max-width:900px}
  .concept{background:#fff;border:1px solid #ddd;border-radius:8px;padding:20px;margin-bottom:24px}
  .concept h2{margin:0 0 12px;font-size:20px}
  .strip{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px}
  .panel{background:#fff;border:1px solid #ddd;display:flex;align-items:center;justify-content:center;position:relative;margin:0;padding:16px 0 20px;box-sizing:border-box}
  .panel.dark{background:#000} .panel figcaption{position:absolute;left:4px;bottom:2px;font-size:10px;color:#888}
  .panel.dark figcaption{color:#aaa}
  .mirror svg{transform:scaleX(-1)} .rotate svg{transform:rotate(90deg)}
  .mirror,.rotate{min-height:{{ mirror_px + 16 + 20 + 2 }}px}
  .mockups{display:grid;grid-template-columns:300px 520px 360px;gap:16px;align-items:start}
  .mockups [data-mockup="phone-home"]{grid-column:1;grid-row:1 / span 4}
  .mockups [data-mockup="browser-tab"]{grid-column:2;grid-row:1}
  .mockups [data-mockup="site-header-light"]{grid-column:2;grid-row:2}
  .mockups [data-mockup="site-header-dark"]{grid-column:2;grid-row:3}
  .mockups [data-mockup="sign-one-colour"]{grid-column:2;grid-row:4}
  .mockups [data-mockup="avatar"]{grid-column:3;grid-row:1 / span 2}
  .mockups [data-mockup="card"]{grid-column:3;grid-row:3 / span 2}
</style></head>
<body>
<h1>{{ brand }} &mdash; critic sheet {{ round_n }}</h1>
<div class="intro">{{ count }} concept{{ 's' if count != 1 else '' }}, lettered in an arbitrary order. Score each on the ten criteria of scorecard.md from what is drawn here: the lockups, the ladder down to 16 px, the mirrored and rotated readings, the one-colour panels and the mockups.</div>
{% for c in concepts %}
<section class="concept">
  <h2>Concept {{ c.letter }}</h2>
  <div class="strip">
    <figure class="panel" style="width:{{ lockup_px + 16 }}px">{{ c.strip.black|safe }}<figcaption>black</figcaption></figure>
    <figure class="panel dark" style="width:{{ lockup_px + 16 }}px">{{ c.strip.white|safe }}<figcaption>reversed</figcaption></figure>
    {% for step in c.strip.ladder %}<figure class="panel" style="width:{{ [step.size, 48]|max + 16 }}px">{{ step.svg|safe }}<figcaption>{{ step.size }}</figcaption></figure>{% endfor %}
    <figure class="panel mirror" style="width:{{ mirror_px + 16 }}px">{{ c.strip.mirror|safe }}<figcaption>mirrored</figcaption></figure>
    <figure class="panel rotate" style="width:{{ mirror_px + 16 }}px">{{ c.strip.rotate|safe }}<figcaption>rotated 90</figcaption></figure>
    {% for step in c.one_colour %}<figure class="panel" style="width:150px">{{ step.svg|safe }}<figcaption>one colour {{ step.size }}</figcaption></figure>{% endfor %}
  </div>
  <div class="mockups">{% for m in c.mockups %}{{ m|safe }}{% endfor %}</div>
</section>
{% endfor %}
</body></html>
```

- [ ] **Step 4: Write `critic_sheet`**

Add to `src/logomaker/sheets.py`, after `concepts_sheet`:

```python
def critic_sheet(paths: ProjectPaths, slug: str, concept_names: list[str], seed: int | None = None, final: bool = False,
                 renderer: Renderer | None = None) -> dict:
    """Write sheets/critic-N.{html,png} for the blind critic and sheets/critic-N.key.json for the merge (spec 2026-10-08
    §3.1). Each survivor (or final/, with `final`) shows the critique strip, the one-colour panels and the mockups under
    a letter, in the order a Random seeded with `seed` (default N) shuffles them; no slug, idea or score is written. Every
    survivor must be vetted (_vetted: a fresh, rendered, passing audit and a gate-passing scorecard), and final/ must
    pass registry.require_final_audit, before Chrome starts. The key maps letters to folder names and records each
    concept's fingerprint now."""
    import random

    from . import critic as criticlib

    if final and concept_names:
        raise CliError("--final takes no --concepts")
    if not final and not concept_names:
        raise CliError("give --concepts <a,b,c> for survivors, or --final for the final mark")
    if len(concept_names) > len(criticlib.LETTERS):
        raise CliError(f"at most {len(criticlib.LETTERS)} concepts on one critic sheet")
    state = registry.load_state(paths, slug)
    brand = paths.brand(slug)
    if final:
        registry.require_final_audit(paths, slug, "the critic sheet")
        folders = [("final", brand / "final")]
    else:
        folders = [(name, _vetted(paths, slug, name)[0]) for name in concept_names]
    round_n = next_round(brand, "sheets/critic-*.key.json")
    seed = round_n if seed is None else seed
    order = list(folders)
    random.Random(seed).shuffle(order)
    env = jinja(paths)
    cards, letters, fingerprints = [], {}, {}
    for letter, (name, folder) in zip(criticlib.LETTERS, order, strict=False):
        module = conceptlib.load_concept(folder)
        outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
        light, dark = _palettes(folder)
        ctx = mockup_context(state, outputs, light, dark)
        cards.append({"letter": letter, "strip": _strip_panels(outputs, CONCEPT_LOCKUP, CONCEPT_MIRROR),
                      "one_colour": [{"size": s, "svg": fit_box(outputs[o].to_svg("black"), s, s)} for s, o in _one_colour_outputs(outputs)],
                      "mockups": [mockuplib.render_mockup(env, kind, ctx) for kind in mockuplib.MOCKUPS]})
        letters[letter] = name
        fingerprints[name] = concept_fingerprint(paths, slug, folder)
    html = env.get_template("sheets/critic.html").render(brand=state.name, round_n=round_n, count=len(cards), concepts=cards,
                                                         width=CONCEPTS_W, lockup_px=CONCEPT_LOCKUP, mirror_px=CONCEPT_MIRROR)
    html_path, png_path = _write_sheet(renderer, html, brand / "sheets", f"critic-{round_n}", CONCEPTS_W)
    key = criticlib.Key(round=round_n, seed=seed, letters=letters, fingerprints=fingerprints, final=final)
    key_file = criticlib.key_path(brand, round_n)
    key_file.write_text(json.dumps(key.model_dump(), indent=2) + "\n", encoding="utf-8")
    return {"sheet_html": str(html_path), "sheet_png": str(png_path), "key": str(key_file), "round": round_n, "letters": letters}
```

Add `import json` to the module's imports (it has none today).

- [ ] **Step 5: Add the CLI command**

In `src/logomaker/cli.py`, after `sheet_refine`:

```python
@sheet_group.command("critic")
@click.argument("slug")
@click.option("--concepts", "concepts", default=None, help="Comma-separated survivors to letter, e.g. 01-arch,03-keystone")
@click.option("--final", is_flag=True, help="Letter the final mark alone (final/), for the critic's last pass.")
@click.option("--seed", type=int, default=None, help="Shuffle seed (default: the sheet's round number); use another for the second pass.")
@command
def sheet_critic(slug: str, concepts: str | None, final: bool, seed: int | None) -> None:
    """Render the blind critic's lettered sheet into sheets/critic-N.{html,png} and its key into sheets/critic-N.key.json.
    Never opened: the critic subagent reads the PNG; the key stays with the designer."""
    from . import sheets as sheetlib

    names = [c.strip() for c in (concepts or "").split(",") if c.strip()]
    emit(sheetlib.critic_sheet(project(), slug, names, seed=seed, final=final))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_critic.py -q`
Expected: all passed.

- [ ] **Step 7: Commit**

```bash
git add src/logomaker/sheets.py src/logomaker/cli.py templates/sheets/critic.html tests/test_critic.py
git commit -m "feat: sheet critic renders the lettered, shuffled critic sheet and its key"
```

---

### Task 4: `concept critic` writes the cards

**Files:**
- Modify: `src/logomaker/cli.py` (the `concept` group)
- Test: `tests/test_critic.py` (extend)

**Interfaces:**
- Consumes: `critic.write_cards`.
- Produces: CLI `concept critic <slug> --sheet N`, printing `{"sheet": N, "passes": K, "cards": {name: path}}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_critic.py`:

```python
def write_pass(brand, round_n: int, number: int, letters: dict[str, str], prefer: str | None = None, **scores):
    cards = {letter: pass_card(**scores) for letter in letters}
    pairs = []
    if prefer and len(letters) == 2:
        a, b = sorted(letters)
        pairs = both_orders(a, b, prefer)
    (brand / "sheets" / f"critic-{round_n}.pass-{number}.json").write_text(json.dumps({"cards": cards, "pairs": pairs}))


def test_concept_critic_merges_the_passes_into_each_concept_folder(project_root):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    info = sheets.critic_sheet(project(), "keystone", ["01-good", "02-dots"], renderer=StubChrome())
    brand = project_root / "brands" / "keystone"
    winner = next(letter for letter, name in info["letters"].items() if name == "01-good")
    write_pass(brand, 1, 1, info["letters"], prefer=winner, distinctive=3)
    write_pass(brand, 1, 2, info["letters"], prefer=winner, distinctive=4)
    code, payload = run("concept", "critic", "keystone", "--sheet", "1")
    assert code == 0 and payload["passes"] == 2 and set(payload["cards"]) == {"01-good", "02-dots"}
    good = json.loads((brand / "concepts" / "01-good" / "critic.json").read_text())
    assert good["scores"]["distinctive"] == 4 and good["preferred_over"] == ["02-dots"] and good["sheet"] == 1
    dots = json.loads((brand / "concepts" / "02-dots" / "critic.json").read_text())
    assert dots["preferred_over"] == [] and dots["tied_with"] == ["01-good"]


def test_concept_critic_refuses_without_passes_and_names_the_file(project_root):
    prepare(project_root, "01-good")
    sheets.critic_sheet(project(), "keystone", ["01-good"], renderer=StubChrome())
    code, payload = run("concept", "critic", "keystone", "--sheet", "1")
    assert code == 2 and "sheets/critic-1.pass-1.json" in payload["errors"][0]
    assert not (project_root / "brands" / "keystone" / "concepts" / "01-good" / "critic.json").exists()
    code, payload = run("concept", "critic", "keystone", "--sheet", "9")
    assert code == 2 and payload["errors"] == ["sheets/critic-9.key.json is missing"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_critic.py -q -k concept_critic`
Expected: FAIL with `assert 2 == 0` (click: no such command).

- [ ] **Step 3: Add the command**

In `src/logomaker/cli.py`, after `concept_run`:

```python
@concept_group.command("critic")
@click.argument("slug")
@click.option("--sheet", "round_n", type=click.IntRange(min=1), required=True, help="The critic sheet whose passes to merge.")
@command
def concept_critic(slug: str, round_n: int) -> None:
    """Merge sheets/critic-N.pass-*.json by the sheet's key into critic.json in each concept folder (final/ for a final sheet)."""
    from . import critic as criticlib

    emit(criticlib.write_cards(project(), slug, round_n))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_critic.py -q`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/cli.py tests/test_critic.py
git commit -m "feat: concept critic merges the passes into critic.json"
```

---

### Task 5: Gates and the concept sheet read the critic

**Files:**
- Modify: `src/logomaker/critic.py` (add `critic_problems`), `src/logomaker/registry.py` (`vetted_scorecard`, `require_final_critic`, `_check_concept`, `_check_final`), `src/logomaker/sheets.py` (`concepts_sheet`), `templates/sheets/concepts.html`, `src/logomaker/export.py` (`PackageBuilder.__init__`)
- Test: `tests/test_critic.py` (extend), `tests/test_registry.py`, `tests/test_concepts_sheet.py` (existing tests gain a critic card in their setup)

**Interfaces:**
- Consumes: `audit.concept_fingerprint`, `registry.passing_scorecard`, `critic.unreconciled`.
- Produces: `critic.critic_problems(paths, slug, folder, label=None) -> list[str]`; `registry.vetted_scorecard(paths, slug, folder, label) -> tuple[Scorecard, CriticCard]` (passing scorecard, fresh critic, nothing unreconciled, else `CliError`); `registry.require_final_critic(paths, slug, needs: str) -> None`; `critic.preference_line(cards: dict[str, CriticCard]) -> str` such as `"02-arch > 01-k-jaw = 05-ring-gap"`. The concept sheet's card dict gains `critic_total` and `critic_passes`; the template gains the preference line under the preface.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_critic.py`:

```python
from logomaker import registry


def critic_run(project_root, names: list[str], prefer: str | None = None, **scores) -> dict:
    """A critic sheet over `names`, one pass scoring 4s but `scores`, merged: the letters used."""
    info = sheets.critic_sheet(project(), "keystone", names, renderer=StubChrome())
    brand = project_root / "brands" / "keystone"
    winner = next((letter for letter, name in info["letters"].items() if name == prefer), None)
    write_pass(brand, info["round"], 1, info["letters"], prefer=winner, **scores)
    critic.write_cards(project(), "keystone", info["round"])
    return info["letters"]


def test_critic_problems_name_what_is_missing_stale_or_invalid(project_root):
    folder = prepare(project_root, "01-good")
    paths = project()
    assert critic.critic_problems(paths, "keystone", folder) == [
        "01-good/critic.json is missing (run: logomaker sheet critic keystone --concepts 01-good, dispatch the critic, "
        "then logomaker concept critic keystone --sheet N)"]
    critic_run(project_root, ["01-good"])
    assert critic.critic_problems(paths, "keystone", folder) == []
    (folder / "concept.py").write_text((folder / "concept.py").read_text() + "\n# changed\n")
    assert critic.critic_problems(paths, "keystone", folder) == [
        "01-good/critic.json is stale (the concept changed since the critic saw it); re-run: logomaker sheet critic keystone "
        "--concepts 01-good, dispatch the critic, then logomaker concept critic keystone --sheet N"]
    (folder / "critic.json").write_text("{")
    assert critic.critic_problems(paths, "keystone", folder)[0].startswith("01-good/critic.json is not valid JSON")


def test_vetted_scorecard_needs_a_fresh_critic_and_every_disagreement_reconciled(project_root):
    folder = prepare(project_root, "01-good")
    paths = project()
    with pytest.raises(CliError, match="critic.json is missing"):
        registry.vetted_scorecard(paths, "keystone", folder, "01-good/scorecard.json")
    critic_run(project_root, ["01-good"], distinctive=2, timeless=2)
    with pytest.raises(CliError, match=r"designer and critic disagree by 2 or more on distinctive, timeless; add a reconciled entry "
                                       r"for each to 01-good/scorecard.json"):
        registry.vetted_scorecard(paths, "keystone", folder, "01-good/scorecard.json")
    (folder / "scorecard.json").write_text(json.dumps({**scorecard(), "reconciled": {"distinctive": "stock arches: 2 stands",
                                                                                      "timeless": "no trend shape: 4 stands"}}))
    card, crit = registry.vetted_scorecard(paths, "keystone", folder, "01-good/scorecard.json")
    assert card.total == 40 and crit.total == 36


def test_concept_sheet_refuses_without_the_critic_and_shows_both_totals_with_it(project_root, no_chrome):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    with pytest.raises(CliError, match="concept 01-good: 01-good/critic.json is missing"):
        sheets.concepts_sheet(project(), "keystone", ["01-good", "02-dots"], open_after=False)


def test_concept_sheet_prints_the_critic_total_and_preference(project_root):
    prepare(project_root, "01-good")
    prepare(project_root, "02-dots", "two_dots")
    critic_run(project_root, ["01-good", "02-dots"], prefer="01-good", distinctive=5)
    sheets.concepts_sheet(project(), "keystone", ["01-good", "02-dots"], renderer=StubChrome(), open_after=False)
    html = (project_root / "brands" / "keystone" / "sheets" / "concepts.html").read_text()
    assert "designer 40 / critic 41 (1 pass)" in html
    assert "critic's order: 01-good &gt; 02-dots" in html or "critic's order: 01-good > 02-dots" in html


def test_preference_line_groups_by_wins():
    cards = {"a": CriticCard.model_validate({**critic_card(), "preferred_over": ["b", "c"]}),
             "b": CriticCard.model_validate({**critic_card(), "preferred_over": [], "tied_with": ["c"]}),
             "c": CriticCard.model_validate({**critic_card(), "preferred_over": [], "tied_with": ["b"]})}
    assert critic.preference_line(cards) == "a > b = c"


def test_advance_to_refinement_and_package_build_read_the_critic(project_root):
    final = make_final_brand(project_root, phase=None)
    paths = project()
    brand = final.parent
    # Step 7 below teaches make_final_brand to run the critic itself; this test checks the gates, so start without the cards.
    for stale in (brand / "concepts" / "01-good" / "critic.json", final / "critic.json", final / "scorecard.json"):
        stale.unlink(missing_ok=True)
    state = registry.load_state(paths, "keystone")
    while state.phase.value != "concepts":
        state = registry.advance(paths, "keystone", registry.allowed_next(state))
    with pytest.raises(CliError) as err:
        registry.advance(paths, "keystone", registry.allowed_next(state))
    assert any("01-good/critic.json is missing" in m for m in err.value.data["missing"])
    critic_run(project_root, ["01-good"])
    state = registry.advance(paths, "keystone", registry.allowed_next(state))
    assert state.phase.value == "refinement"
    with pytest.raises(CliError) as err:
        registry.advance(paths, "keystone", registry.allowed_next(state))
    assert any("final/critic.json is missing" in m for m in err.value.data["missing"])
    info = sheets.critic_sheet(paths, "keystone", [], final=True, renderer=StubChrome())
    write_pass(brand, info["round"], 1, info["letters"])
    critic.write_cards(paths, "keystone", info["round"])
    with pytest.raises(CliError) as err:
        registry.advance(paths, "keystone", registry.allowed_next(state))
    assert any("final/scorecard.json is missing" in m for m in err.value.data["missing"])
    (final / "scorecard.json").write_text(json.dumps(scorecard()))
    assert registry.advance(paths, "keystone", registry.allowed_next(state)).phase.value == "package"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_critic.py -q -k "problems or vetted or concept_sheet or preference or advance"`
Expected: FAIL with `AttributeError: module 'logomaker.critic' has no attribute 'critic_problems'`.

- [ ] **Step 3: Add `critic_problems` and `preference_line` to `critic.py`**

```python
def refresh_command(slug: str, folder: Path) -> str:
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


def preference_line(cards: dict[str, CriticCard]) -> str:
    """The critic's order as one line: concepts grouped by how many they beat, best first, `>` between groups, `=` within."""
    groups: dict[int, list[str]] = {}
    for name, card in cards.items():
        groups.setdefault(len(card.preferred_over), []).append(name)
    return " > ".join(" = ".join(sorted(groups[wins])) for wins in sorted(groups, reverse=True))
```

`_load` is the helper Task 2 wrote; `critic_problems` reuses it, so a malformed file's message starts with the label and "is not valid JSON" or "is invalid".

- [ ] **Step 4: Add the gates to `registry.py`**

After `passing_scorecard`:

```python
def vetted_scorecard(paths: ProjectPaths, slug: str, folder: Path, label: str) -> tuple[Scorecard, CriticCard]:
    """The designer's passing scorecard (passing_scorecard) and the critic's fresh card for `folder`, with every criterion
    they put two or more apart reconciled in the scorecard; otherwise a CliError saying what to do (spec 2026-10-08 §3.3)."""
    from . import critic as criticlib  # imported here: critic imports schemas only, but keeps registry's imports light

    card = passing_scorecard(folder, label)
    problems = criticlib.critic_problems(paths, slug, folder, label.replace("scorecard.json", "critic.json"))
    if problems:
        raise CliError("; ".join(problems))
    critic_card = load_model(folder / "critic.json", CriticCard, label.replace("scorecard.json", "critic.json"))
    open_ = criticlib.unreconciled(card, critic_card)
    if open_:
        raise CliError(f"designer and critic disagree by {criticlib.DISAGREEMENT} or more on {', '.join(open_)}; "
                       f"add a reconciled entry for each to {label}")
    return card, critic_card


def require_final_critic(paths: ProjectPaths, slug: str, needs: str) -> None:
    """A CliError (exit 2) unless final/critic.json vouches for the final mark as it is now and final/scorecard.json exists
    with every disagreement reconciled, saying what `needs` it ("packaging", "the package phase")."""
    problems = final_critic_problems(paths, slug)
    if problems:
        raise CliError(f"{needs} needs the critic's pass on the final mark: {'; '.join(problems)}")


def final_critic_problems(paths: ProjectPaths, slug: str) -> list[str]:
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
```

Import `CriticCard` from `.schemas` at the top of `registry.py`. Then change `_check_concept` so that, when `current` is true, it uses `vetted_scorecard` instead of `passing_scorecard`:

```python
    try:
        if current:
            vetted_scorecard(paths, state.slug, folder, f"{state.concept}/scorecard.json")
        else:
            passing_scorecard(folder, f"{state.concept}/scorecard.json")
    except CliError as err:
        missing.append(str(err))
```

And append to `_check_final`'s return: `+ final_critic_problems(paths, state.slug)` after the audit problems (only when the audit problems list is empty, so the owner sees the audit first):

```python
    problems = missing + audit_problems(paths, state.slug, final, "final/audit.json")
    return problems if problems else final_critic_problems(paths, state.slug)
```

- [ ] **Step 5: Make the concept sheet read the critic**

In `sheets.concepts_sheet`, replace the `_vetted` list comprehension and the card building:

```python
    vetted = [(name, *_vetted(paths, slug, name)) for name in concept_names]
    critics = {}
    for name, folder, _ in vetted:
        try:
            critics[name] = registry.vetted_scorecard(paths, slug, folder, f"{name}/scorecard.json")[1]
        except CliError as err:
            raise CliError(f"concept {name}: {err}") from err
```

and in the card dict add `"critic_total": critics[name].total, "critic_passes": critics[name].passes`. Pass `preference=criticlib.preference_line(critics)` to the template (import `critic as criticlib` at the top of `sheets.py`; `critic` imports nothing from `sheets`). In `templates/sheets/concepts.html` change the score badge and add the line:

```html
<div class="intro">New ideas can be fragile ... not what you like today.</div>
<div class="intro">critic's order: {{ preference }}</div>
...
  <h2>{{ c.name }}<span class="score">designer {{ c.total }} / critic {{ c.critic_total }} ({{ c.critic_passes }} pass{{ 'es' if c.critic_passes != 1 else '' }})</span></h2>
```

Keep the preface sentence byte for byte (the test `test_the_sheet_prints_the_collins_preface_as_process_md_words_it` compares it with process.md).

- [ ] **Step 6: Make the package build require the final critic**

In `src/logomaker/export.py`, give `PackageBuilder.__init__` a keyword `critic_required: bool = True` and, after `registry.require_final_audit(paths, slug, "packaging")`, add:

```python
        if critic_required:
            registry.require_final_critic(paths, slug, "packaging")
```

The CLI never passes the keyword, so every real build requires the critic. The Keystone example predates the critic (spec 2026-10-08 §10): in `tests/test_example.py::test_example_package_builds_again_and_verifies` build with `export.PackageBuilder(project(), "keystone", critic_required=False)` and a comment saying why. In `docs/examples/keystone/WALKTHROUGH.md`, under "Refreshing this example", add to step 2: "`package build` now also needs `final/critic.json` and a reconciled `final/scorecard.json`: run `uv run logomaker sheet critic keystone --final`, dispatch one critic pass, `uv run logomaker concept critic keystone --sheet N`, and add any `reconciled` entries, before the build; copy both files back with `final/` in step 3." That edits the walkthrough's procedure only, never the example's design artifacts.

- [ ] **Step 7: Update the existing tests' setup**

Existing tests that render the concept sheet or advance through concepts now need a critic card. In `tests/test_concepts_sheet.py`, extend `prepare` to run a one-pass critic when `critic=True` (default): after writing the scorecard, call the `critic_run` helper (move `write_pass`, `pass_card`, `both_orders` and `critic_run` from `tests/test_critic.py` into `tests/conftest.py` so both files share them, and import them in both). Tests that assert a refusal for a missing scorecard or a stale audit keep passing because `_vetted` runs first; a test that asserts the sheet renders now passes once `prepare` adds the card. In `tests/conftest.py`'s `make_final_brand`, after `write_passing_audit(paths, "keystone", concept)` add a one-pass critic run for `01-good`, and after the final audit a one-pass final critic run plus `final/scorecard.json` with `scorecard()`, so the brand still advances to `refinement` and `package`. Run the whole fast suite and fix every setup that the new gates refuse, in the test, never by loosening the gate.

- [ ] **Step 8: Run the suites**

Run: `uv run pytest -m "not render and not live" -q`
Expected: all passed. Then `uv run ruff check src tests`.

- [ ] **Step 9: Commit**

```bash
git add src/logomaker tests templates
git commit -m "feat: the concept sheet, the gates and the package build read the critic's card"
```

---

### Task 6: The critic's brief and the runbook

**Files:**
- Create: `.claude/skills/logo/reference/critic.md`
- Modify: `.claude/skills/logo/SKILL.md`, `.claude/skills/logo/reference/process.md`, `.claude/skills/logo/reference/scorecard.md`, `tests/test_knowledge.py` (`REQUIRED`), `tests/test_skill_docs.py` (`PHASE_READS`)
- Test: `tests/test_knowledge.py`, `tests/test_skill_docs.py`

**Interfaces:**
- Consumes: the commands from Tasks 3 and 4.
- Produces: `reference/critic.md` with headings `What the critic sees`, `What the critic returns`, `Reconciliation`, `Dispatch`, `Sources`; the runbook steps below.

- [ ] **Step 1: Register the file in the tests**

In `tests/test_knowledge.py` add to `REQUIRED`:

```python
    "critic.md": ["What the critic sees", "What the critic returns", "Reconciliation", "Dispatch", "Sources"],
```

In `tests/test_skill_docs.py` add `"critic.md"` to the `Concepts` and `Refinement` tuples of `PHASE_READS`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_knowledge.py tests/test_skill_docs.py -q`
Expected: FAIL: `critic.md` is missing, and the phase headings do not name it.

- [ ] **Step 3: Write `reference/critic.md`**

600 to 2000 words, this frame:

```markdown
# Critic

Read this when: dispatching the blind critic after scoring the survivors (phase 4), reconciling its card with yours, and running its last pass on `final/` before `package build` (phase 5).

The critic is a second designer who sees the work for the first time. LLM judges prefer what they wrote and what comes first on the page [spec 2026-10-08 §2], so the critic sees neither your scores nor your reasons, and the sheet it reads is lettered in a shuffled order, twice [spec 2026-10-08 §3.1].

## What the critic sees

- `sheets/critic-N.png` from `uv run logomaker sheet critic <slug> --concepts <a,b,c>`: each survivor's lockups, ladder, mirrored and rotated panels, one-colour panels and mockups under a letter. No slug, no idea, no score [code].
- `brief.md`, `strategy.md`, `reference/scorecard.md`, `reference/evidence-rules.md` and `reference/trends.md`.
- Nothing else: not `ideas.md`, not a `concept.py`, not `critique.md`, not the key. It never searches the web.

## What the critic returns

`sheets/critic-N.pass-K.json`, validating as `critic.CriticPass` [code]:
(the JSON shape, one example with two letters, the both-orders rule for pairs, "tie")

## Reconciliation

(the DISAGREEMENT rule, the `reconciled` entry format, the designer may change their own score and never the critic's, what `sheet concepts` refuses, the final pass before `package build` and `final/scorecard.json`)

## Dispatch

(the Agent call: `model: "opus"`, two calls in one message with `--seed` values that differ, the prompt text to give the subagent verbatim, where it writes, then `uv run logomaker concept critic <slug> --sheet N`)

## Sources

spec 2026-10-08 §2, §3.1 to §3.4; code: `critic.py`, `sheets.critic_sheet`, `registry.vetted_scorecard`, `registry.require_final_critic`.
```

Fill every parenthesised line with the real content from the code written in Tasks 2 to 5. Tag sources as `[spec 2026-10-08 §3.2]` and `[code]`.

- [ ] **Step 4: Update SKILL.md**

In the Concepts phase heading's read list add `reference/critic.md`; after the look-alike step and before the `sheet concepts` step insert:

```markdown
- Then the blind critic (read `reference/critic.md`): `uv run logomaker sheet critic <slug> --concepts <NN-slug,...>` twice with different `--seed` values, one Opus subagent per sheet given only the PNG path, the brief, the strategy and the three reference files it names, each writing `sheets/critic-N.pass-K.json`; then `uv run logomaker concept critic <slug> --sheet N`. For every criterion where your score and the critic's differ by two or more, add a `reconciled` entry to `scorecard.json`; `sheet concepts` refuses a survivor without a fresh `critic.json` or with a disagreement left open.
```

In the Refinement phase heading's read list add `reference/critic.md`; after the re-score step:

```markdown
- Then the critic's last pass: `uv run logomaker sheet critic <slug> --final`, one subagent, one pass, `uv run logomaker concept critic <slug> --sheet N`, and reconcile into `final/scorecard.json`; `brand advance --to package` and `package build` refuse without a fresh `final/critic.json`.
```

In "Parallel concepts with subagents" append a paragraph on the critic dispatch that repeats the sentence `Set `model` explicitly to `opus` or cheaper; never leave it to inherit the session's model.` (the test needs it once; keep the original too).

- [ ] **Step 5: Update process.md and scorecard.md**

process.md: in the phases table, the `concepts` row's "Claude does" gains "the blind critic's two passes, reconciled"; the `refinement` row gains "the critic's last pass"; under "Artifacts each phase must contain", `concepts` gains "its `critic.json`, fresh, with every disagreement reconciled" and `refinement` gains "`final/critic.json`, fresh, and `final/scorecard.json` reconciled". scorecard.md: under "Gate" add the two critic rules, and under "scorecard.json format" show a card with a `reconciled` entry.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_knowledge.py tests/test_skill_docs.py -q`
Expected: all passed, including `cli_problems` on the new commands and options.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/logo tests/test_knowledge.py tests/test_skill_docs.py
git commit -m "docs: the critic's brief and the runbook steps for the blind critic"
```

---

## Plan 1 is done when

- `uv run pytest -m "not render and not live" -q` passes, and `uv run pytest -m render -q` renders the critic sheet through Chrome.
- `uv run ruff check src tests` is clean.
- A brand cannot reach `sheet concepts`, `refinement` or `package build` without a fresh, reconciled critic card.
- `docs/examples/keystone` is untouched and `tests/test_example.py` still passes.
