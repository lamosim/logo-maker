# Raising the Ceiling, Plan 2: Evaluation Set Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three scripted, deliberately hard briefs that the logo skill runs headless end to end, a runner that keeps the sheets, the cards and a one-page report per run, and a baseline cycle recorded before the kit and ideation work begins.

**Architecture:** Each brief is a Markdown owner script in `docs/evals/<slug>/owner.md`. `scripts/eval_brand.py` builds a prompt from it, runs `claude -p` with `LOGOMAKER_ROOT` pointed at a scratch directory (the headless harness the owner already uses), then copies the artifacts worth keeping into `docs/evals/<slug>/<cycle>/` and writes `report.md`. The runner is importable so its parser, prompt and report are unit-tested; the runs themselves are by hand.

**Tech Stack:** Python 3.12 standard library (argparse, subprocess, json, shutil); the `claude` CLI; pytest for the parser, prompt and report.

**Spec:** `docs/superpowers/specs/2026-10-08-raising-the-ceiling-design.md`, section 4 (WS2) and section 11 (the cycle order). Plan 1 (`2026-10-08-ceiling-1-blind-critic.md`) must be implemented first: the report reads `critic.json`.

**Prerequisite:** Plan 1 is merged and its suites pass.

## Global Constraints

- The runner never runs on the session's model: `--model` defaults to `opus` and the report records it (`~/.claude` memory rule: subagents and nested sessions on Opus or cheaper).
- The nested `claude` starts only with `CLAUDECODE` unset, `LOGOMAKER_ROOT` set to a scratch directory, `LOGOMAKER_NO_OPEN=1`, and the repo root as its working directory, so the skill loads and the checkout stays clean.
- No file from a run lands in `brands/` or `registry/`; the scratch directory is deleted after collection.
- Kept per run: the concept sheet PNG, the critic sheet PNGs, every `scorecard.json` and `critic.json`, the final critique PNG of the last round, `brand-sheet.pdf`, the brand's `brand.json`, and `report.md`. Never the package or the `build/` folders.
- Owner scripts have exactly thirteen numbered answers in the Keystone walkthrough's order, then a "Conservative answers" section.
- Ruff clean (`uv run ruff check src tests scripts`); commit per task with the attribution line from the session's system reminder.

## Review Focus

1. A run that stops before `done` (turn cap, a crash): `collect` still writes a report that says which phase it reached and keeps whatever sheets exist. Pinned in Task 3.
2. A brand folder with no `critic.json` yet (the run stopped in concepts): the totals table shows the designer's score and a dash, never a KeyError. Pinned in Task 3.
3. An owner script with twelve answers, or two answers numbered 7: `answers` raises with the file name and the count, before any `claude` starts. Pinned in Task 1.
4. The `claude` binary missing or exiting non-zero: `run` raises with the exit code and the last stderr line; nothing is collected. Pinned in Task 3.
5. Rerunning a cycle label: the runner refuses to overwrite an existing `docs/evals/<slug>/<cycle>/` unless `--force`. Pinned in Task 3.

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/eval_brand.py` (create) | `answers`, `build_prompt`, `run`, `collect`, `report`, `main` |
| `docs/evals/README.md` (create) | what the set is, how to run a cycle, the results table |
| `docs/evals/orvane/owner.md`, `docs/evals/clear-ledger/owner.md`, `docs/evals/pip/owner.md` (create) | the scripted owners |
| `docs/evals/<slug>/<cycle>/` (created by runs) | kept artifacts and `report.md` |
| `tests/test_evals.py` (create) | parser, prompt, collect and report tests |

---

### Task 1: The owner-script parser and the prompt

**Files:**
- Create: `scripts/eval_brand.py`
- Test: `tests/test_evals.py`

**Interfaces:**
- Produces: `eval_brand.ROOT`, `eval_brand.EVALS`; `eval_brand.answers(text: str, name: str) -> list[str]` (thirteen answers, in order, each without its number); `eval_brand.build_prompt(slug: str, script: str) -> str`; `eval_brand.PROMPT` (the fixed preamble).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_evals.py
import importlib.util
from pathlib import Path

import pytest

from tests.conftest import REPO

SCRIPT = REPO / "scripts" / "eval_brand.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("eval_brand", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OWNER = "# Test: owner\n\n## Answers\n\n" + "\n".join(f"{i}. Answer {i}." for i in range(1, 14)) + "\n\n## Conservative answers\n\nTake the quiet option.\n"


def test_answers_reads_thirteen_numbered_lines_in_order():
    runner = load_runner()
    got = runner.answers(OWNER, "owner.md")
    assert len(got) == 13 and got[0] == "Answer 1." and got[12] == "Answer 13."


def test_answers_refuses_the_wrong_count_or_a_repeated_number():
    runner = load_runner()
    with pytest.raises(ValueError, match="owner.md has 12 answers, not 13"):
        runner.answers(OWNER.replace("13. Answer 13.\n", ""), "owner.md")
    with pytest.raises(ValueError, match="owner.md numbers its answers 1, 2, 3, 4, 5, 6, 7, 7"):
        runner.answers(OWNER.replace("8. Answer 8.", "7. Answer 8."), "owner.md")


def test_build_prompt_carries_the_script_and_the_rules():
    runner = load_runner()
    prompt = runner.build_prompt("orvane", OWNER)
    assert "evaluation mode" in prompt and "Answer 13." in prompt and "Take the quiet option." in prompt
    for rule in ("--no-open", 'brand decide', "scripted:", "DONE orvane", "never wait for the owner"):
        assert rule in prompt, rule
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_evals.py -q`
Expected: FAIL with `FileNotFoundError` on the script.

- [ ] **Step 3: Write the parser and the prompt**

```python
#!/usr/bin/env python3
"""Run one evaluation brief through the logo skill headless and keep its results (spec 2026-10-08 §4).

    uv run python scripts/eval_brand.py <slug> --cycle <label> [--model opus] [--max-turns 400] [--force]

The brief is docs/evals/<slug>/owner.md, a scripted owner in the Keystone walkthrough's format. The nested `claude`
runs with CLAUDECODE unset, LOGOMAKER_ROOT in a scratch directory and the repo root as its working directory, so the
skill loads and the checkout stays clean. What is worth keeping is copied into docs/evals/<slug>/<cycle>/ with a
report.md; the scratch directory is then deleted.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "docs" / "evals"
ANSWERS = 13
NUMBERED = re.compile(r"^(\d+)\.\s+(.*\S)\s*$", re.M)
PHASES = ("intake", "naming", "strategy", "territories", "concepts", "refinement", "package", "done")

PROMPT = """You are running the logo skill in evaluation mode for the venture below. The owner's side of the conversation
is scripted: when the runbook asks the owner a question the script answers, take the script's answer as the owner's
reply and continue; never wait for the owner. When it asks something the script does not answer, take the most
conservative option the script's last section describes and record it with
`uv run logomaker brand decide <slug> --phase <phase> --by user --note "scripted: <what you took and why>"`.
Follow the skill exactly otherwise: write every artifact, read every sheet with the Read tool, run every sheet command
with --no-open, dispatch the critic as the runbook says, and never draw before the brief is confirmed. The venture is
named, so create it with `uv run logomaker brand new "<Name>"` (no --unnamed). Stop when `uv run logomaker brand status
<slug>` reports the phase done, then print one line: DONE {slug}.

The owner's script:

{script}
"""


def answers(text: str, name: str) -> list[str]:
    """The thirteen numbered answers of an owner script, in order, without their numbers; ValueError naming `name`
    when the count or the numbering is off."""
    found = NUMBERED.findall(text)
    numbers = [int(n) for n, _ in found]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(f"{name} numbers its answers {', '.join(map(str, numbers))}; they must run 1 to {ANSWERS}")
    if len(found) != ANSWERS:
        raise ValueError(f"{name} has {len(found)} answers, not {ANSWERS}")
    return [answer for _, answer in found]


def build_prompt(slug: str, script: str) -> str:
    return PROMPT.format(slug=slug, script=script.strip())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_evals.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/eval_brand.py tests/test_evals.py
git commit -m "feat: eval runner parses an owner script and builds the headless prompt"
```

---

### Task 2: The three owner scripts and the README

**Files:**
- Create: `docs/evals/README.md`, `docs/evals/orvane/owner.md`, `docs/evals/clear-ledger/owner.md`, `docs/evals/pip/owner.md`
- Test: `tests/test_evals.py` (extend)

**Interfaces:**
- Produces: three owner scripts the runner accepts; a README whose "Results" table the `final` cycle fills.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_evals.py`:

```python
BRIEFS = ("orvane", "clear-ledger", "pip")


@pytest.mark.parametrize("slug", BRIEFS)
def test_each_brief_has_thirteen_answers_and_the_conservative_section(slug):
    runner = load_runner()
    text = (runner.EVALS / slug / "owner.md").read_text(encoding="utf-8")
    assert len(runner.answers(text, f"{slug}/owner.md")) == 13
    assert "## Conservative answers" in text
    assert "the critic" in text  # answer 12 chooses the survivor the critic preferred


def test_readme_lists_every_brief_and_the_cycles():
    text = (REPO / "docs" / "evals" / "README.md").read_text(encoding="utf-8")
    for slug in BRIEFS:
        assert f"`{slug}`" in text
    for cycle in ("baseline", "kit", "ideation", "final"):
        assert cycle in text
    assert "scripts/eval_brand.py" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_evals.py -q`
Expected: FAIL with `FileNotFoundError` on `docs/evals/orvane/owner.md`.

- [ ] **Step 3: Write the owner scripts**

`docs/evals/orvane/owner.md`:

```markdown
# Orvane: scripted owner

A coined name with no metaphor and no obvious letter quirk, in a category whose uniform is hexagons, nodes and arrows (spec 2026-10-08 §4.1).

## Answers

1. Business: Orvane delivers webhooks reliably, for backend developers at small SaaS companies, solving lost and duplicated events.
2. One idea: nothing gets dropped.
3. Onliness: the only webhook service that proves delivery to both sides.
4. Adjectives: precise but not cold; quiet but not timid; dependable but not dull.
5. Persona: a night-shift air-traffic controller who never raises their voice.
6. Admired: Linear (discipline), Vercel (restraint). Disliked: hexagons and node-graph logos. Nothing existing carries over.
7. Surfaces: website header, GitHub avatar, docs favicon.
8. Harshest: the 16 px favicon in a dark terminal theme, and a one-colour laptop sticker.
9. Colours: wants something warm against the category; forbids neon green; the category has claimed purple, black and electric blue.
10. Off limits: arrows, lightning bolts, hexagons, nodes and edges. No cultural constraints; English only.
11. Name: Orvane, written "Orvane", said OR-vain; a coined word with no story; no tagline.
12. Territory choice: the quieter of the boards. Concept choice: the survivor the critic preferred (the concept sheet's critic's order). First reaction to the concept sheet: "the symbol disappears in the dark header at 32 px"; expect the probing question and answer "the site header dark mockup".
13. Refinement approval after the colour round. Any extra question: answer with the most conservative option.

## Conservative answers

Where the runbook asks what the script does not answer: confirm the write-back as written; approve the strategy as written; name no specific likes on the concept sheet; keep the name and send any conflict to an attorney; take the top-ranked surface's lockup as primary; approve the package handover.
```

`docs/evals/clear-ledger/owner.md`:

```markdown
# Clear Ledger: scripted owner

Two words, both category cues, in a category whose blacklist strikes the first ten ideas (spec 2026-10-08 §4.1).

## Answers

1. Business: Clear Ledger does the bookkeeping for one-person businesses, for sole traders who do their own books at midnight, solving the dread of tax time.
2. One idea: you can see where you stand.
3. Onliness: the only bookkeeping service that shows a sole trader one honest number every week.
4. Adjectives: plain but not cheap; calm but not passive; honest but not blunt.
5. Persona: a retired bank teller who keeps the village shop's books for the love of it.
6. Admired: Monzo (plainness), the Hemingway editor (clarity). Disliked: coins, piggy banks, charts going up. Nothing existing carries over.
7. Surfaces: app icon, website header, printed invoices.
8. Harshest: the 16 px favicon and a black-and-white receipt printer.
9. Colours: wants a green that is not money green; forbids navy; the category has claimed blue, green and teal.
10. Off limits: coins, piggy banks, shields, upward charts, calculators. No cultural constraints; English only.
11. Name: Clear Ledger, written "Clear Ledger" as two words, no tagline; story: the ledger you can actually read.
12. Territory choice: the warmer of the boards. Concept choice: the survivor the critic preferred. First reaction to the concept sheet: "the two words run together at the invoice size"; expect the probing question and answer "the card mockup".
13. Refinement approval after the colour round. Any extra question: answer with the most conservative option.

## Conservative answers

Where the runbook asks what the script does not answer: confirm the write-back as written; approve the strategy as written; name no specific likes on the concept sheet; keep the name and send any conflict to an attorney; take the top-ranked surface's lockup as primary; approve the package handover.
```

`docs/evals/pip/owner.md`:

```markdown
# Pip: scripted owner

A warm consumer brand that wants a character: the organic vocabulary and the mascot route, and a three-letter wordmark (spec 2026-10-08 §4.1). In the `final` cycle this brief runs on the express track.

## Answers

1. Business: Pip is a reading app for five-to-eight-year-olds, for parents who want twenty minutes of reading a day, solving the fight over screen time.
2. One idea: a small friend who reads with you.
3. Onliness: the only reading app whose character turns the page only when the child reads the line aloud.
4. Adjectives: warm but not saccharine; playful but not loud; simple but not babyish.
5. Persona: a kind librarian's hand puppet that children trust before they trust the librarian.
6. Admired: Duolingo (the owl's economy), Sesame Workshop (warmth). Disliked: stock cartoon mascots with huge eyes, rainbow gradients. Nothing existing carries over.
7. Surfaces: app icon, App Store listing, printed stickers.
8. Harshest: the 16 px favicon and a one-colour sticker.
9. Colours: wants a warm yellow or coral; forbids primary-colour rainbows; the category has claimed bright blue and rainbow.
10. Off limits: open books, owls, apples, lightbulbs. No cultural constraints; English only.
11. Name: Pip, written "Pip", said as spelled; story: a seed, and a small sound; no tagline.
12. Territory choice: the warmer of the boards. Concept choice: the survivor the critic preferred. First reaction to the concept sheet: "the character turns into a blob at the avatar size"; expect the probing question and answer "at the avatar size".
13. Refinement approval after the colour round. Any extra question: answer with the most conservative option.

## Conservative answers

Where the runbook asks what the script does not answer: confirm the write-back as written; approve the strategy as written; name no specific likes on the concept sheet; keep the name and send any conflict to an attorney; take the top-ranked surface's lockup as primary; approve the package handover.
```

- [ ] **Step 4: Write the README**

`docs/evals/README.md`:

```markdown
# Evaluation set

Three scripted owners, each hard where the Keystone example was easy (spec 2026-10-08 §4): `orvane` (a coined name with no metaphor), `clear-ledger` (two category cues in a blacklisted category) and `pip` (a character and a three-letter wordmark). Each `owner.md` has the thirteen answers in the walkthrough's order and the conservative option for everything else.

## Running a cycle

One run per brief, by hand, never in CI:

    uv run python scripts/eval_brand.py orvane --cycle baseline
    uv run python scripts/eval_brand.py clear-ledger --cycle baseline
    uv run python scripts/eval_brand.py pip --cycle baseline

The runner starts a nested `claude -p` on Opus with the skill loaded, `LOGOMAKER_ROOT` in a scratch directory and permissions skipped, keeps the sheets, the cards, the last critique, the brand sheet and `brand.json` under `docs/evals/<slug>/<cycle>/`, writes `report.md` beside them and deletes the scratch directory. A run takes thirty to sixty minutes. Cycles: `baseline` (after the blind critic, before the kit and ideation work), `kit`, `ideation`, `final` (after the express track; `pip` runs with `--express`).

## Results

A row per brief and cycle. Single runs are noisy: read the direction across cycles, and treat a change under one point on one criterion as no finding.

| Brief | Cycle | Critic `distinctive` (chosen) | Critic total (chosen) | Non-literal survivors | Gate regressions | Minutes |
|---|---|---|---|---|---|---|
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_evals.py -q`
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add docs/evals tests/test_evals.py
git commit -m "docs: three evaluation briefs and the evals README"
```

---

### Task 3: `run`, `collect`, `report` and `main`

**Files:**
- Modify: `scripts/eval_brand.py`
- Test: `tests/test_evals.py` (extend)

**Interfaces:**
- Consumes: `answers`, `build_prompt` from Task 1; `critic.json` and `scorecard.json` shapes from Plan 1.
- Produces: `eval_brand.run(slug, prompt, scratch: Path, model: str, max_turns: int) -> Path` (the JSONL transcript); `eval_brand.collect(slug, scratch: Path, cycle: str, model: str, transcript: Path, force: bool = False) -> Path` (the cycle folder); `eval_brand.report(slug, brand: Path, model: str, transcript: Path) -> str`; `eval_brand.main(argv) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_evals.py`:

```python
import json


def fake_brand(root: Path, slug: str = "orvane", with_critic: bool = True, phase: str = "done") -> Path:
    brand = root / "brands" / slug
    for sub in ("concepts/01-arc", "concepts/02-dot", "sheets", "final/renders/round-3", "package"):
        (brand / sub).mkdir(parents=True)
    decisions = [{"at": "2026-10-09T10:00:00-04:00", "phase": "intake", "by": "user", "note": "scripted: brief confirmed"},
                 {"at": "2026-10-09T10:05:00-04:00", "phase": "strategy", "by": "user", "note": "scripted: approved"},
                 {"at": "2026-10-09T10:12:00-04:00", "phase": "concepts", "by": "user", "note": "scripted: 01-arc"}]
    (brand / "brand.json").write_text(json.dumps({"slug": slug, "name": "Orvane", "phase": phase, "concept": "01-arc",
                                                  "decisions": decisions, "updated": "2026-10-09T10:40:00-04:00"}))
    scores = {c: 4 for c in ("appropriate", "distinctive", "simple", "legible", "adaptable", "timeless", "universal", "clear",
                             "congruent", "system")}
    (brand / "concepts" / "01-arc" / "scorecard.json").write_text(json.dumps({"scores": scores, "route": "abstraction"}))
    (brand / "concepts" / "02-dot" / "scorecard.json").write_text(json.dumps({"scores": {**scores, "distinctive": 2}, "route": "object"}))
    if with_critic:
        (brand / "concepts" / "01-arc" / "critic.json").write_text(json.dumps({"scores": {**scores, "distinctive": 5}, "sheet": 1,
                                                                                "passes": 2, "fingerprint": "x"}))
    (brand / "sheets" / "concepts.png").write_bytes(b"png")
    (brand / "sheets" / "critic-1.png").write_bytes(b"png")
    (brand / "final" / "renders" / "round-3" / "critique.png").write_bytes(b"png")
    (brand / "package" / "verify.json").write_text(json.dumps({"ok": phase == "done"}))
    (brand / "package" / "brand-sheet.pdf").write_bytes(b"%PDF")
    return brand


def transcript(path: Path, turns: int = 3) -> Path:
    lines = [json.dumps({"type": "assistant", "message": {"content": []}}) for _ in range(turns)]
    lines.append(json.dumps({"type": "result", "result": "DONE orvane", "num_turns": turns}))
    path.write_text("\n".join(lines) + "\n")
    return path


def test_report_tables_the_phases_scores_and_outcome(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path)
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "run.jsonl"))
    assert "| model | opus |" in text and "| turns | 3 |" in text and "| phase reached | done |" in text
    assert "| 01-arc | abstraction | 40 | 41 (2 passes) |" in text  # designer total, critic total
    assert "| 02-dot | object | 38 | - |" in text  # no critic card: a dash, not an error
    assert "| strategy | 7 |" in text  # minutes from the first strategy decision to the first concepts decision
    assert "| package verified | yes |" in text


def test_report_on_a_run_that_stopped_early(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path, with_critic=False, phase="concepts")
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "run.jsonl", turns=1))
    assert "| phase reached | concepts |" in text and "| package verified | no |" in text


def test_collect_keeps_the_sheets_cards_and_report_and_refuses_a_second_run_without_force(tmp_path, monkeypatch):
    runner = load_runner()
    monkeypatch.setattr(runner, "EVALS", tmp_path / "evals")
    brand = fake_brand(tmp_path / "scratch")
    folder = runner.collect("orvane", tmp_path / "scratch", "baseline", "opus", transcript(tmp_path / "scratch" / "run.jsonl"))
    assert folder == tmp_path / "evals" / "orvane" / "baseline"
    kept = sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())
    assert kept == ["brand.json", "concepts/01-arc/critic.json", "concepts/01-arc/scorecard.json", "concepts/02-dot/scorecard.json",
                    "final/critique.png", "package/brand-sheet.pdf", "report.md", "run.jsonl", "sheets/concepts.png", "sheets/critic-1.png"]
    assert not (tmp_path / "scratch").exists()  # the scratch directory is deleted after collection
    fake_brand(tmp_path / "scratch")
    with pytest.raises(FileExistsError, match="baseline"):
        runner.collect("orvane", tmp_path / "scratch", "baseline", "opus", transcript(tmp_path / "scratch" / "run.jsonl"))
    assert (tmp_path / "scratch").exists()  # a refused collection leaves the scratch in place
    runner.collect("orvane", tmp_path / "scratch", "baseline", "opus", transcript(tmp_path / "scratch" / "run.jsonl"), force=True)
    assert not (tmp_path / "scratch").exists()


def test_run_raises_on_a_failing_claude(tmp_path, monkeypatch):
    runner = load_runner()

    def failing(cmd, **kwargs):
        class Done:
            returncode = 1
            stderr = "boom\nno credits\n"
        return Done()

    monkeypatch.setattr(runner.subprocess, "run", failing)
    with pytest.raises(RuntimeError, match="claude exited 1: no credits"):
        runner.run("orvane", "prompt", tmp_path, "opus", 10)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_evals.py -q -k "report or collect or run_raises"`
Expected: FAIL with `AttributeError: module 'eval_brand' has no attribute 'report'`.

- [ ] **Step 3: Write `run`, `report`, `collect` and `main`**

Append to `scripts/eval_brand.py`:

```python
def run(slug: str, prompt: str, scratch: Path, model: str, max_turns: int) -> Path:
    """Start the nested claude and return the JSONL transcript it wrote; RuntimeError with the exit code and the last
    stderr line when it fails."""
    transcript = scratch / "run.jsonl"
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    env.update({"LOGOMAKER_ROOT": str(scratch), "LOGOMAKER_NO_OPEN": "1"})
    cmd = ["claude", "-p", prompt, "--model", model, "--max-turns", str(max_turns), "--output-format", "stream-json", "--verbose",
           "--dangerously-skip-permissions", "--add-dir", str(scratch)]
    with transcript.open("w", encoding="utf-8") as out:
        done = subprocess.run(cmd, cwd=ROOT, env=env, stdout=out, stderr=subprocess.PIPE, text=True)
    if done.returncode != 0:
        last = (done.stderr or "").strip().splitlines()
        raise RuntimeError(f"claude exited {done.returncode}: {last[-1] if last else 'no stderr'}")
    return transcript


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _minutes(decisions: list[dict], updated: str | None) -> list[tuple[str, int]]:
    """Minutes per phase: from the first decision of each phase to the first of the next, the last to `updated`."""
    starts: dict[str, datetime] = {}
    for d in decisions:
        if d.get("phase") in PHASES and d.get("phase") not in starts:
            try:
                starts[d["phase"]] = datetime.fromisoformat(d["at"])
            except (KeyError, ValueError):
                continue
    ordered = [(phase, starts[phase]) for phase in PHASES if phase in starts]
    out = []
    for i, (phase, start) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else (datetime.fromisoformat(updated) if updated else None)
        out.append((phase, round((end - start).total_seconds() / 60) if end else 0))
    return out


def report(slug: str, brand: Path, model: str, transcript: Path) -> str:
    state = _read_json(brand / "brand.json") or {}
    turns = sum(1 for line in transcript.read_text(encoding="utf-8").splitlines() if '"type": "assistant"' in line)
    verify = _read_json(brand / "package" / "verify.json") or {}
    lines = [f"# {slug}: evaluation run", "", f"Run on {datetime.now(UTC).astimezone().isoformat(timespec='minutes')}.", "",
             "| | |", "|---|---|", f"| model | {model} |", f"| turns | {turns} |", f"| phase reached | {state.get('phase', '?')} |",
             f"| chosen concept | {state.get('concept') or '-'} |", f"| package verified | {'yes' if verify.get('ok') else 'no'} |", "",
             "## Minutes per phase", "", "| phase | minutes |", "|---|---|"]
    lines += [f"| {phase} | {minutes} |" for phase, minutes in _minutes(state.get("decisions", []), state.get("updated"))]
    lines += ["", "## Concepts", "", "| concept | route | designer | critic |", "|---|---|---|---|"]
    for folder in sorted(p for p in (brand / "concepts").glob("*") if p.is_dir()):
        card = _read_json(folder / "scorecard.json")
        if not card:
            continue
        critic = _read_json(folder / "critic.json")
        designer = sum(card["scores"].values())
        critic_cell = f"{sum(critic['scores'].values())} ({critic.get('passes', '?')} passes)" if critic else "-"
        lines.append(f"| {folder.name} | {card.get('route') or '-'} | {designer} | {critic_cell} |")
    return "\n".join(lines) + "\n"


KEEP_GLOBS = ("sheets/concepts.png", "sheets/critic-*.png", "concepts/*/scorecard.json", "concepts/*/critic.json",
              "package/brand-sheet.pdf", "brand.json")


def collect(slug: str, scratch: Path, cycle: str, model: str, transcript: Path, force: bool = False) -> Path:
    """Copy the kept artifacts and the report into docs/evals/<slug>/<cycle>/ and delete `scratch`. An existing cycle
    folder is a FileExistsError unless `force`."""
    brand = scratch / "brands" / slug
    folder = EVALS / slug / cycle
    if folder.exists() and not force:
        raise FileExistsError(f"{folder} exists; pass --force to replace the {cycle} run")
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    for pattern in KEEP_GLOBS:
        for source in brand.glob(pattern):
            target = folder / source.relative_to(brand)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    rounds = sorted((p for p in (brand / "final" / "renders").glob("round-*") if (p / "critique.png").is_file()),
                    key=lambda p: int(p.name.split("-")[1]))
    if rounds:
        (folder / "final").mkdir(exist_ok=True)
        shutil.copy2(rounds[-1] / "critique.png", folder / "final" / "critique.png")
    (folder / "report.md").write_text(report(slug, brand, model, transcript), encoding="utf-8")
    shutil.copy2(transcript, folder / "run.jsonl")
    shutil.rmtree(scratch)
    return folder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug")
    parser.add_argument("--cycle", required=True)
    parser.add_argument("--model", default="opus")
    parser.add_argument("--max-turns", type=int, default=400)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    script = (EVALS / args.slug / "owner.md").read_text(encoding="utf-8")
    answers(script, f"{args.slug}/owner.md")  # refuse a bad script before anything starts
    scratch = Path(tempfile.mkdtemp(prefix=f"logomaker-eval-{args.slug}-"))
    try:
        transcript = run(args.slug, build_prompt(args.slug, script), scratch, args.model, args.max_turns)
    except RuntimeError as err:
        print(f"{err}; scratch kept at {scratch}", file=sys.stderr)
        return 1
    folder = collect(args.slug, scratch, args.cycle, args.model, transcript, args.force)
    print(folder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_evals.py -q && uv run ruff check scripts tests`
Expected: all passed, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add scripts/eval_brand.py tests/test_evals.py
git commit -m "feat: eval runner runs a brief headless, keeps its results and writes a report"
```

---

### Task 4: The `baseline` cycle

**Files:**
- Create (by the runs): `docs/evals/orvane/baseline/`, `docs/evals/clear-ledger/baseline/`, `docs/evals/pip/baseline/`
- Modify: `docs/evals/README.md` (three rows)

This task runs by hand with the network and the `claude` CLI, after Plan 1 is merged and before Plans 3 and 4 start (spec section 11). It is not a test.

- [ ] **Step 1: Smoke-test the harness on one brief with a low turn cap**

Run: `uv run python scripts/eval_brand.py orvane --cycle smoke --max-turns 6`
Expected: exit 0; `docs/evals/orvane/smoke/report.md` shows `phase reached | intake` (or `strategy`) and a `brand.json`. Then `rm -r docs/evals/orvane/smoke`. If `claude` refuses to start, check that `CLAUDECODE` is unset in the nested environment (the runner strips it) and that `claude` is on the PATH.

- [ ] **Step 2: Run the three briefs**

Run each in the foreground with the Bash timeout at its maximum, or in the background, one at a time:

```bash
uv run python scripts/eval_brand.py orvane --cycle baseline
uv run python scripts/eval_brand.py clear-ledger --cycle baseline
uv run python scripts/eval_brand.py pip --cycle baseline
```

Expected: each prints its cycle folder. Read each `report.md` and each `sheets/concepts.png` with the Read tool.

- [ ] **Step 3: Fill the README rows**

For each brief add a row to the Results table: the critic's `distinctive` and total for the chosen concept (from its `critic.json`), the count of survivors whose scorecard `route` is not `object` (a dash in this cycle, since routes arrive in Plan 4), gate regressions (none, in the baseline), and the minutes from the report.

- [ ] **Step 4: Commit the cycle**

```bash
git add docs/evals
git commit -m "docs: baseline evaluation cycle"
```

---

## Plan 2 is done when

- `uv run pytest tests/test_evals.py -q` passes and ruff is clean.
- `docs/evals/<slug>/baseline/report.md` exists for all three briefs and the README table has three rows.
- `brands/` and `registry/` in the checkout are untouched by the runs.
