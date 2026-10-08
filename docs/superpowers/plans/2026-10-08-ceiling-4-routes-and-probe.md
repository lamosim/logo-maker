# Raising the Ceiling, Plan 4: Ideation Routes and the Obviousness Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every concept declares which of seven ideation routes it takes and how many first-page image results already show its construction, the schema caps `distinctive` from that count, and the concept sheet refuses a set of survivors that are all literal.

**Architecture:** Two new fields on `Scorecard` (`route`, `probe`) with a validator that enforces the cap; the gate (`registry.passing_scorecard`) requires both; `sheets.concepts_sheet` applies the non-literal rule across survivors. The ideation rules themselves live in the skill's documents. No new module.

**Tech Stack:** pydantic 2, pytest; the skill's Markdown.

**Spec:** `docs/superpowers/specs/2026-10-08-raising-the-ceiling-design.md`, section 6 (WS4).

**Prerequisite:** Plan 1 is merged and the `baseline` evaluation cycle (Plan 2, Task 4) is recorded.

## Global Constraints

- Scores stay whole numbers 1 to 5; the gate criteria stay `appropriate`, `simple`, `legible` at 4 or more.
- A card that breaks the cap is invalid, not merely failing: the file is rejected on read, so nothing downstream can show it.
- The Keystone example is not edited; its committed scorecards have no `route` or `probe`, and no test gates them (the example test runs `verify` and the package build only).
- Ruff clean; commit per task with the attribution line from the session's system reminder.

## Review Focus

1. A probe with `hits` of 3 and `distinctive` of 3: valid (the cap is inclusive). With 2 hits and 5: valid. With 3 hits and 4: invalid. Pinned in Task 1.
2. A route spelled with a different case or an underscore (`Negative_space`): rejected naming the seven routes. Pinned in Task 1.
3. A sheet where one survivor's route is `letterform` and the rest `object`: allowed, since `letterform` is non-literal. Pinned in Task 2.
4. A card missing `probe` but carrying `route`: the gate names the missing field, not a generic validation error. Pinned in Task 2.
5. The conftest `scorecard()` helper used by dozens of tests: it gains a default route and probe, so every existing gate test still passes. Pinned in Task 2.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/logomaker/schemas.py` (modify) | `ROUTES`, `LITERAL_ROUTE`, `Probe`, `distinctive_cap`, `Scorecard.route` and `.probe` with the cap validator |
| `src/logomaker/registry.py` (modify) | `passing_scorecard` requires route and probe |
| `src/logomaker/sheets.py` (modify) | the non-literal survivor rule |
| `.claude/skills/logo/reference/scorecard.md`, `craft.md`, `process.md`, `SKILL.md` (modify) | the rules |
| `tests/conftest.py`, `tests/test_concepts_sheet.py`, `tests/test_registry.py`, `tests/test_skill_docs.py`, `tests/test_knowledge.py` (modify) | tests |

---

### Task 1: `route`, `probe` and the cap

**Files:**
- Modify: `src/logomaker/schemas.py`
- Test: `tests/test_concepts_sheet.py` (extend `test_scorecard_validation_and_gate`'s neighbourhood)

**Interfaces:**
- Produces: `schemas.ROUTES = ("object", "abstraction", "letterform", "negative-space", "type-quirk", "system", "metaphor-2")`; `schemas.LITERAL_ROUTE = "object"`; `schemas.PROBE_CAPS = ((8, 2), (3, 3))`; `schemas.Probe(query: str, hits: int, date: str)`; `schemas.distinctive_cap(hits: int) -> int`; `Scorecard.route: str | None`, `Scorecard.probe: Probe | None`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_concepts_sheet.py`:

```python
from logomaker.schemas import ROUTES, Probe, distinctive_cap


def test_distinctive_cap_steps_with_the_probe_hits():
    assert [distinctive_cap(h) for h in (0, 2, 3, 7, 8, 20)] == [5, 5, 3, 3, 2, 2]


def test_scorecard_route_and_probe():
    probe = {"query": "arch keystone logo", "hits": 3, "date": "2026-10-09"}
    card = Scorecard.model_validate({**scorecard(distinctive=3), "route": "object", "probe": probe})
    assert card.route == "object" and card.probe == Probe(**probe)
    with pytest.raises(ValidationError, match=r"distinctive is capped at 3 by the probe \(3 of 20 first-page results show the construction\)"):
        Scorecard.model_validate({**scorecard(distinctive=4), "route": "object", "probe": probe})
    with pytest.raises(ValidationError, match="distinctive is capped at 2"):
        Scorecard.model_validate({**scorecard(distinctive=3), "route": "object", "probe": {**probe, "hits": 8}})
    assert Scorecard.model_validate({**scorecard(distinctive=5), "route": "abstraction", "probe": {**probe, "hits": 2}}).scores["distinctive"] == 5
    with pytest.raises(ValidationError, match="route must be one of object, abstraction, letterform, negative-space, type-quirk, system, metaphor-2"):
        Scorecard.model_validate({**scorecard(), "route": "Negative_space", "probe": probe})
    with pytest.raises(ValidationError, match="hits"):
        Scorecard.model_validate({**scorecard(), "route": "object", "probe": {**probe, "hits": 21}})
    assert Scorecard.model_validate(scorecard()).route is None  # legacy cards still load; the gate decides
    assert len(ROUTES) == 7
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_concepts_sheet.py -q -k "cap or route"`
Expected: FAIL with `ImportError: cannot import name 'ROUTES'`.

- [ ] **Step 3: Add the fields**

In `src/logomaker/schemas.py`, before `Scorecard`:

```python
ROUTES = ("object", "abstraction", "letterform", "negative-space", "type-quirk", "system", "metaphor-2")  # spec 2026-10-08 §6.1
LITERAL_ROUTE = "object"
PROBE_CAPS = ((8, 2), (3, 3))  # first-page hits at or above the threshold cap `distinctive` at the value


def distinctive_cap(hits: int) -> int:
    """The most `distinctive` may score after an obviousness probe found `hits` of twenty first-page results showing the
    construction: 2 from 8 hits, 3 from 3, else 5."""
    for threshold, cap in PROBE_CAPS:
        if hits >= threshold:
            return cap
    return 5


class Probe(BaseModel):
    """The obviousness probe: an image search for "<motif> logo", and how many of its first twenty results show the
    same construction (spec 2026-10-08 §6.2)."""

    query: str
    hits: int = Field(ge=0, le=20)
    date: str
```

In `Scorecard` add the fields and extend the validator:

```python
    route: str | None = None
    probe: Probe | None = None

    @model_validator(mode="after")
    def complete_and_in_range(self) -> Scorecard:
        check_scores(self.scores)
        if self.route is not None and self.route not in ROUTES:
            raise ValueError(f"route must be one of {', '.join(ROUTES)}, got {self.route!r}")
        if self.probe is not None:
            cap = distinctive_cap(self.probe.hits)
            if self.scores["distinctive"] > cap:
                raise ValueError(f"distinctive is capped at {cap} by the probe ({self.probe.hits} of 20 first-page results "
                                 "show the construction)")
        return self
```

Update the class docstring to name both fields.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_concepts_sheet.py tests/test_critic.py -q`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker/schemas.py tests/test_concepts_sheet.py
git commit -m "feat: scorecard route and obviousness probe with the distinctive cap"
```

---

### Task 2: The gate and the non-literal survivor rule

**Files:**
- Modify: `src/logomaker/registry.py` (`passing_scorecard`), `src/logomaker/sheets.py` (`concepts_sheet`), `tests/conftest.py` (`scorecard()`)
- Test: `tests/test_concepts_sheet.py`, `tests/test_registry.py` (extend)

**Interfaces:**
- Consumes: `schemas.LITERAL_ROUTE`.
- Produces: `passing_scorecard` raises `CliError("<label> needs route and probe (scorecard.md)")` when either is missing; `concepts_sheet` raises `CliError("every survivor takes the object route; the sheet needs at least one non-literal survivor (routes in scorecard.md)")`.

- [ ] **Step 1: Give the test helper a default route and probe**

In `tests/conftest.py`, `scorecard()` returns:

```python
    return {"scores": scores, "evidence": {"appropriate": "arch = holds the invoice together"}, "route": "abstraction",
            "probe": {"query": "ring gap logo", "hits": 0, "date": "2026-10-09"}}
```

Run `uv run pytest -m "not render and not live" -q`; everything still passes (the fields are optional on the model so far).

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_concepts_sheet.py`:

```python
def test_the_gate_needs_a_route_and_a_probe(project_root):
    folder = prepare(project_root, "01-good")
    legacy = scorecard()
    del legacy["route"], legacy["probe"]
    (folder / "scorecard.json").write_text(json.dumps(legacy))
    with pytest.raises(CliError, match=r"01-good/scorecard.json needs route and probe \(scorecard.md\)"):
        registry.passing_scorecard(folder, "01-good/scorecard.json")
    (folder / "scorecard.json").write_text(json.dumps({**scorecard(), "probe": None}))
    with pytest.raises(CliError, match="needs route and probe"):
        registry.passing_scorecard(folder, "01-good/scorecard.json")


def test_the_sheet_needs_one_non_literal_survivor(project_root, no_chrome):
    for name, fixture in (("01-good", "good"), ("02-dots", "two_dots")):
        folder = prepare(project_root, name, fixture)  # Plan 1's prepare already runs the critic; the card is not fingerprinted
        (folder / "scorecard.json").write_text(json.dumps({**scorecard(), "route": "object"}))
    assert refusal("01-good", "02-dots") == ("every survivor takes the object route; the sheet needs at least one non-literal "
                                             "survivor (routes in scorecard.md)")
    assert no_sheet(project_root)
    folder = project_root / "brands" / "keystone" / "concepts" / "02-dots"
    (folder / "scorecard.json").write_text(json.dumps({**scorecard(), "route": "letterform"}))
    with pytest.raises(AssertionError, match="Chrome started"):  # the rule passes; the render is the next step
        sheets.concepts_sheet(project(), "keystone", ["01-good", "02-dots"], open_after=False)
```

`prepare`, `refusal`, `no_sheet` are the file's existing helpers (after Plan 1, `prepare` also runs the critic, and after Plan 5 it records the knock-out). The second test asserts the refusal is the route rule, then that changing one route lets the sheet reach Chrome (the `no_chrome` fixture makes Chrome's start an `AssertionError`).

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_concepts_sheet.py -q -k "needs_a_route or non_literal"`
Expected: FAIL: no error raised in the first, and a different refusal in the second.

- [ ] **Step 4: Add the gate and the rule**

In `registry.passing_scorecard`, after loading the card and before the gate check:

```python
    if card.route is None or card.probe is None:
        raise CliError(f"{label} needs route and probe (scorecard.md)")
```

In `sheets.concepts_sheet`, after `vetted` and the critic loop, before building cards:

```python
    if all(card.route == LITERAL_ROUTE for _, _, card in vetted):
        raise CliError("every survivor takes the object route; the sheet needs at least one non-literal survivor (routes in scorecard.md)")
```

Import `LITERAL_ROUTE` from `.schemas` in `sheets.py`.

- [ ] **Step 5: Run the suites**

Run: `uv run pytest -m "not render and not live" -q && uv run ruff check src tests`
Expected: all passed, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/logomaker tests
git commit -m "feat: the gate needs a route and a probe; the sheet needs a non-literal survivor"
```

---

### Task 3: The rules in the skill

**Files:**
- Modify: `.claude/skills/logo/reference/scorecard.md`, `.claude/skills/logo/reference/craft.md`, `.claude/skills/logo/reference/process.md`, `.claude/skills/logo/SKILL.md`, `tests/test_skill_docs.py`
- Test: `tests/test_skill_docs.py`, `tests/test_knowledge.py`

**Interfaces:**
- Produces: scorecard.md gains `## Routes and the probe` (before `## Gate`); the JSON example gains `route` and `probe`; SKILL.md's concepts phase carries the three rules; craft.md's checklist gains the routes line; process.md's `concepts` row names them.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_skill_docs.py`:

```python
def test_skill_pins_the_routes_and_the_probe():
    concepts = flat(section(SKILL.read_text(encoding="utf-8"), "Phase runbook"))
    assert "tagged with its route" in concepts and "at least five routes" in concepts
    assert "at least one survivor on the sheet is non-literal" in concepts
    assert '"<motif> logo"' in concepts and "first twenty image results" in concepts and "`probe`" in concepts
    card = (REF / "scorecard.md").read_text(encoding="utf-8")
    assert "## Routes and the probe" in card and "metaphor-2" in card and "capped at 3" in card and "capped at 2" in card
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_skill_docs.py -q -k routes`
Expected: FAIL on `"tagged with its route"`.

- [ ] **Step 3: Write the rules**

scorecard.md, a new section before `## Gate`:

```markdown
## Routes and the probe

Seven routes name how a concept gets from the one idea to a drawing [spec 2026-10-08 §6.1]: `object` (the thing itself), `abstraction` (the thing reduced past recognition), `letterform` (a letter of the name), `negative-space` (a second figure in a counter or gap), `type-quirk` (the wordmark with one or two owned moves), `system` (a repeated element or a rule that makes the mark), `metaphor-2` (two steps from the idea, not its obvious object). `object` is the literal route; the other six are non-literal. Every line of `concepts/ideas.md` carries its route in brackets, the ideas cover at least five routes, the directions built cover at least three, and at least one survivor on the concept sheet is non-literal: `sheet concepts` refuses a sheet whose survivors all take `object` [code].

The obviousness probe keeps criterion 2 honest [spec 2026-10-08 §6.2]. Before building a direction, image-search "<motif> logo" (the construction's plain noun: "arch keystone logo") and count, among the first twenty results, those showing the same construction. Record it in the card as `probe` with the query, the count and the date; the evidence line for `distinctive` cites it. The schema caps `distinctive`: 3 or more hits cap it at 3, 8 or more at 2, and a card scoring above its cap is rejected with the cap in the message [code]. The critic is never told the probe.
```

Add `"route": "object"` and `"probe": {"query": "socket O logo", "hits": 1, "date": "2026-10-09"}` to the passing card example under "scorecard.json format", and `"route"` and `"probe"` to the killed card too (a killed card keeps every field).

SKILL.md, concepts phase, replace the first two bullets with:

```markdown
- Write 12 to 20 one-line ideas in `concepts/ideas.md`, each tagged with its motifs and with its route in brackets (the seven routes are in `reference/scorecard.md`); the ideas cover at least five routes. Strike any on the blacklist unless the brief made it the strategy; then twist it and justify it.
- Pick five to eight directions covering at least three routes, at least three structurally different (another logo type or construction logic, not a variation), so that at least one survivor on the sheet is non-literal. Before building each, run the obviousness probe: image-search "<motif> logo" and count, in the first twenty image results, those showing the same construction; the count goes into the card's `probe` and caps `distinctive` (`reference/scorecard.md`). Create `concepts/NN-slug/concept.py` for each (see "Writing concept modules"). Black only: no `tokens.json` in a concept folder.
```

craft.md's construction checklist, after the thumbnails line: `- [ ] Ideas tagged by route, five or more routes covered, one non-literal survivor on the sheet (scorecard.md, "Routes and the probe")`. process.md's `concepts` row: "12 to 20 ideas tagged by route; the obviousness probe per direction; 5 to 8 directions ...".

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_skill_docs.py tests/test_knowledge.py -q`
Expected: all passed (the knowledge test validates the JSON blocks in scorecard.md as `Scorecard`, so the examples must carry a valid probe and a `distinctive` within its cap).

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/logo tests/test_skill_docs.py
git commit -m "docs: ideation routes and the obviousness probe in the runbook"
```

---

## Plan 4 is done when

- Fast suite and ruff pass.
- A scorecard above its probe cap cannot be read; a sheet of literal survivors cannot be rendered.
- The `ideation` evaluation cycle is run (Plan 2, Task 4's procedure with `--cycle ideation`) and its rows added to `docs/evals/README.md`, now with the non-literal survivor count filled from the routes.
