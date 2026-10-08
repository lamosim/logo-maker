# Raising the Ceiling, Plan 6: Express Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A brand can be created on an express track that keeps every gate, audit, critic, probe and knock-out, and shrinks every phase: five intake questions, one territory, three directions, two survivors, one refinement round.

**Architecture:** One new field on `BrandState` (`track`), set by `brand new --express` and changed by `brand set --track`. The only count the CLI enforces that differs between tracks is the territory minimum, so `TerritoriesSpec`'s minimum drops to one and the territories gate checks the full track's minimum of two. Everything else is runbook text.

**Tech Stack:** pydantic 2, click, pytest.

**Spec:** `docs/superpowers/specs/2026-10-08-raising-the-ceiling-design.md`, section 8 (WS6).

**Prerequisite:** Plans 1 to 5 are merged.

## Global Constraints

- An express brand is named: `--express` with `--unnamed` exits 2.
- A brand can move to the full track at any gate; it cannot move to express from `concepts` on.
- Every gate from Plans 1, 4 and 5 applies unchanged on the express track; the critic runs one pass there (the merge accepts one).
- Ruff clean; commit per task with the attribution line from the session's system reminder.

## Review Focus

1. A full-track brand whose `territories.json` has one territory: refused by the gate with the two ways out (add a territory, or switch tracks). Pinned in Task 2.
2. An express brand with three territories: allowed (the model's maximum is unchanged). Pinned in Task 2.
3. `brand set --track express` on a brand in `concepts`: refused naming the phase. Pinned in Task 1.
4. A brand.json written before this plan (no `track`): loads as `full`. Pinned in Task 1.
5. The territories board (`sheet territories`) on an express brand with one territory: renders one card, no error. Pinned in Task 2.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/logomaker/schemas.py` (modify) | `BrandState.track`; `TerritoriesSpec` minimum of one; `FULL_TERRITORIES_MIN` |
| `src/logomaker/registry.py` (modify) | `new_brand(track)`, `set_fields` track rule, `_check_territories` by track |
| `src/logomaker/cli.py` (modify) | `brand new --express`, `brand set --track` |
| `.claude/skills/logo/reference/process.md`, `questionnaire.md`, `SKILL.md` (modify) | the express counts |
| `tests/test_registry.py`, `tests/test_territories.py`, `tests/test_skill_docs.py` (modify) | tests |

---

### Task 1: `track` on the brand

**Files:**
- Modify: `src/logomaker/schemas.py`, `src/logomaker/registry.py`, `src/logomaker/cli.py`
- Test: `tests/test_registry.py` (extend)

**Interfaces:**
- Produces: `BrandState.track: Literal["full", "express"] = "full"`; `registry.new_brand(paths, name, slug=None, unnamed=False, track="full")`; `registry.set_fields(..., track=...)`; CLI `brand new <name> [--express]`, `brand set <slug> --track full|express`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_registry.py`:

```python
def test_express_brands_are_named_and_carry_their_track(project_root):
    code, payload = run("brand", "new", "Pip", "--express")
    assert code == 0 and payload["brand"]["track"] == "express"
    code, payload = run("brand", "new", "Working Title", "--express", "--unnamed")
    assert code == 2 and payload["errors"] == ["an express brand is named; drop --unnamed or --express"]
    assert not (project_root / "brands" / "working-title").exists()
    code, payload = run("brand", "new", "Keystone")
    assert payload["brand"]["track"] == "full"


def test_a_brand_json_without_a_track_is_full(project_root):
    run("brand", "new", "Keystone")
    path = project_root / "brands" / "keystone" / "brand.json"
    data = json.loads(path.read_text())
    del data["track"]
    path.write_text(json.dumps(data))
    assert registry.load_state(project(), "keystone").track == "full"


def test_track_can_go_to_full_any_time_but_to_express_only_before_concepts(project_root, brief_payload, strategy_payload):
    run("brand", "new", "Keystone", "--express")
    code, payload = run("brand", "set", "keystone", "--track", "full")
    assert code == 0 and payload["brand"]["track"] == "full"
    code, payload = run("brand", "set", "keystone", "--track", "express")
    assert code == 0 and payload["brand"]["track"] == "express"
    code, payload = run("brand", "set", "keystone", "--track", "fast")
    assert code == 2 and "--track" in payload["errors"][0]
    assert run("brand", "set", "keystone", "--track", "full")[0] == 0
    make_final_brand(project_root, phase=Phase.concepts)  # reuses the brand and advances it to concepts
    code, payload = run("brand", "set", "keystone", "--track", "express")
    assert code == 2 and payload["errors"] == ["cannot move to the express track from concepts on; the earlier phases' counts are spent"]
    assert registry.load_state(project(), "keystone").track == "full"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_registry.py -q -k "express or track"`
Expected: FAIL: `--express` is not a known option.

- [ ] **Step 3: Add the field, the option and the rule**

`schemas.BrandState`: `track: Literal["full", "express"] = "full"` after `needs_name`.

`registry.new_brand`:

```python
def new_brand(paths: ProjectPaths, name: str, slug: str | None = None, unnamed: bool = False, track: str = "full") -> BrandState:
    if track == "express" and unnamed:
        raise CliError("an express brand is named; drop --unnamed or --express")
    ...
    state = BrandState(slug=slug, name=name, needs_name=unnamed, track=track)  # type: ignore[arg-type]
```

`registry.set_fields`, a new branch before the generic `setattr`:

```python
        elif key == "track":
            if value == "express" and PHASE_ORDER.index(state.phase) >= PHASE_ORDER.index(Phase.concepts):
                raise CliError("cannot move to the express track from concepts on; the earlier phases' counts are spent")
            state.track = value
```

`cli.brand_new` gains `@click.option("--express", is_flag=True, help="The express track: five intake questions, one territory, three directions, one refinement round; every gate kept.")` and passes `track="express" if express else "full"`. `cli.brand_set` gains `@click.option("--track", default=None, type=click.Choice(["full", "express"]))` and passes `track=track`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_registry.py -q`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker tests/test_registry.py
git commit -m "feat: brand new --express and brand set --track"
```

---

### Task 2: The territories minimum by track

**Files:**
- Modify: `src/logomaker/schemas.py` (`TerritoriesSpec`), `src/logomaker/registry.py` (`_check_territories`)
- Test: `tests/test_territories.py` (extend)

**Interfaces:**
- Produces: `schemas.FULL_TERRITORIES_MIN = 2`; `TerritoriesSpec.territories` with `min_length=1, max_length=3`; the gate message `territories/territories.json has 1 territory; the full track needs 2 or 3 (add one, or run: logomaker brand set <slug> --track express)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_territories.py`:

```python
def one_territory(payload: dict) -> dict:
    return {"territories": payload["territories"][:1]}


def test_one_territory_validates_but_the_full_track_gate_wants_two(project_root, territories_payload, brief_payload, strategy_payload):
    spec = TerritoriesSpec.model_validate(one_territory(territories_payload))
    assert len(spec.territories) == 1
    run("brand", "new", "Keystone")
    brand = project_root / "brands" / "keystone"
    write_brief(project_root, "keystone", brief_payload)
    (brand / "strategy.md").write_text("# Strategy\n")
    (brand / "strategy.json").write_text(json.dumps(strategy_payload))
    assert run("brand", "advance", "keystone", "--to", "strategy")[0] == 0
    assert run("brand", "advance", "keystone", "--to", "territories")[0] == 0
    (brand / "territories" / "territories.json").write_text(json.dumps(one_territory(territories_payload)))
    run("brand", "set", "keystone", "--territory", "forge")
    code, payload = run("brand", "advance", "keystone", "--to", "concepts")
    assert code == 2 and ("territories/territories.json has 1 territory; the full track needs 2 or 3 (add one, or run: logomaker "
                          "brand set keystone --track express)") in payload["missing"]
    assert run("brand", "set", "keystone", "--track", "express")[0] == 0
    code, payload = run("brand", "advance", "keystone", "--to", "concepts")
    assert code == 0 and payload["brand"]["phase"] == "concepts"


def test_the_board_renders_one_territory_on_the_express_track(project_root, territories_payload, monkeypatch):
    from logomaker import sheets
    from tests.conftest import StubChrome

    run("brand", "new", "Pip", "--express")
    brand = project_root / "brands" / "pip"
    (brand / "territories" / "territories.json").write_text(json.dumps(one_territory(territories_payload)))
    info = sheets.territories_board(project(), "pip", renderer=StubChrome(), open_after=False)
    assert info["territories"] == ["forge"]
```

`run` and `write_brief` are helpers in `tests/test_registry.py`; import them, or copy `run` into this file if it has its own.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_territories.py -q -k "one_territory or express"`
Expected: FAIL with a `ValidationError` on `min_length`.

- [ ] **Step 3: Move the minimum into the gate**

`schemas.py`: `FULL_TERRITORIES_MIN = 2` and `territories: list[Territory] = Field(min_length=1, max_length=3)`.

`registry._check_territories`, after loading the spec:

```python
    if state.track == "full" and len(spec.territories) < FULL_TERRITORIES_MIN:
        count = len(spec.territories)
        return [f"{path.relative_to(brand)} has {count} territor{'y' if count == 1 else 'ies'}; the full track needs 2 or 3 "
                f"(add one, or run: logomaker brand set {state.slug} --track express)"]
```

Import `FULL_TERRITORIES_MIN` from `.schemas`.

- [ ] **Step 4: Run the suites**

Run: `uv run pytest -m "not render and not live" -q && uv run ruff check src tests`
Expected: all passed. A test elsewhere that asserted `min_length=2` on the model (search `tests/` for `"at least 2"` or `min_length`) moves to asserting the gate message instead.

- [ ] **Step 5: Commit**

```bash
git add src/logomaker tests
git commit -m "feat: the territories minimum follows the brand's track"
```

---

### Task 3: The express runbook

**Files:**
- Modify: `.claude/skills/logo/reference/process.md`, `.claude/skills/logo/reference/questionnaire.md`, `.claude/skills/logo/SKILL.md`, `docs/evals/README.md`
- Test: `tests/test_skill_docs.py` (extend), `tests/test_knowledge.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_skill_docs.py`:

```python
def test_skill_pins_the_express_track():
    text = SKILL.read_text(encoding="utf-8")
    first = flat(section(text, "First move"))
    assert 'uv run logomaker brand new "<Name>" --express' in first and "express" in first
    runbook = flat(section(text, "Phase runbook"))
    for phrase in ("express: five questions", "express: one territory", "express: eight to twelve ideas, three directions, two survivors",
                   "express: one refine sheet", "the critic runs one pass"):
        assert phrase in runbook, phrase
    process = (REF / "process.md").read_text(encoding="utf-8")
    assert "## Express track" in process and "--track full" in process
    questionnaire = (REF / "questionnaire.md").read_text(encoding="utf-8")
    assert "## Express intake" in questionnaire and "questions 1, 3, 4, 7 and 11" in questionnaire
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_skill_docs.py -q -k express`
Expected: FAIL on the first assertion.

- [ ] **Step 3: Write the runbook changes**

SKILL.md, "First move" step 4: "... `uv run logomaker brand new "<Name>"`, `uv run logomaker brand new "<Name>" --express` for the express track (a named venture that wants a package in under fifteen minutes: every gate kept, every phase shrunk, counts in each phase below), or `uv run logomaker brand new "<Working title>" --unnamed`, the only way a brand gets a naming phase; `--express` and `--unnamed` do not combine."

Phase runbook, one clause per phase, in these words:

- Intake: "(express: five questions, numbers 1, 3, 4, 7 and 11 of `reference/questionnaire.md`; infer the rest and show it in the write-back)".
- Strategy: "(express: all nine sections, one to three sentences each, written and approved in one message)".
- Territories: "(express: one territory is allowed; the full track needs two or three)".
- Concepts: "(express: eight to twelve ideas, three directions, two survivors, two revise rounds; the critic runs one pass)".
- Refinement: "(express: one refine sheet)".

process.md, a new section `## Express track` before `## Sources` holding the spec's table (section 8) and the two rules: `brand set <slug> --track full` upgrades at any gate; a downgrade from `concepts` on is refused.

questionnaire.md, a new section `## Express intake` after "Core questions": "On the express track ask questions 1, 3, 4, 7 and 11 only, in that order; infer `one_idea` from 3, `persona` and the archetype from 4, `harshest` from 7's first surface (an app icon or favicon means the 16 px tier), `colours_*` and `off_limits` from the category's uniform in cliches.md, and show every inference in the write-back for correction."

`docs/evals/README.md`: in "Running a cycle", note that in the `final` cycle `pip` is created with `--express`: the runner's prompt tells the skill to create the brand with `brand new "<Name>"`; add a `--express` flag to `scripts/eval_brand.py` that changes that sentence to `brand new "<Name>" --express` (one line in `build_prompt`, one test in `tests/test_evals.py` asserting the flag changes the prompt).

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_skill_docs.py tests/test_knowledge.py tests/test_evals.py -q`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/logo docs/evals scripts/eval_brand.py tests
git commit -m "docs: the express track in the runbook, the process and the questionnaire"
```

---

### Task 4: The `final` evaluation cycle

Run by hand, after Tasks 1 to 3:

- [ ] **Step 1: Run the three briefs**

```bash
uv run python scripts/eval_brand.py orvane --cycle final
uv run python scripts/eval_brand.py clear-ledger --cycle final
uv run python scripts/eval_brand.py pip --cycle final --express
```

- [ ] **Step 2: Fill the README rows and compare with the baseline**

Add the three rows. In the README under the table, write three to five sentences on the direction across cycles: critic `distinctive` on the chosen concept, non-literal survivors per sheet, gate regressions, and `pip`'s minutes on the express track against the fifteen-minute target.

- [ ] **Step 3: Commit**

```bash
git add docs/evals
git commit -m "docs: final evaluation cycle and the comparison with the baseline"
```

---

## Plan 6 is done when

- Fast suite and ruff pass.
- An express brand reaches `done` through every gate with one territory, and `pip`'s `final` report records its minutes.
- `docs/evals/README.md` carries all four cycles for all three briefs with the closing comparison.
