# Logo Maker Part 3: Skill, Knowledge Base and Example Brand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the engine and package into the guided experience: the knowledge base distilled from the research, the `logo` skill that runs the conversation, the project `CLAUDE.md` and README, and one complete example brand that proves the whole path works.

**Architecture:** Reference documents live under `.claude/skills/logo/reference/` and are read by phase. `SKILL.md` holds the routing, the phase runbook, the conversation rules and the subagent recipe. `CLAUDE.md` routes every logo request to the skill and states the rules the CLI relies on. The example brand under `docs/examples/` is produced by running the real workflow with scripted answers and is verified with `package verify`.

**Tech Stack:** Markdown, the `logomaker` CLI from Parts 1 and 2, pytest for structural checks.

**Spec:** `docs/superpowers/specs/2026-10-05-logo-maker-design.md` (sections 3, 4, 11, 12, 14). Sources: `docs/research/01` to `05`.

**Prerequisite:** Parts 1 and 2 are implemented and their suites pass.

## Global Constraints

- Reference documents are operational: rules, tables, checklists and worked examples, each tagged with the research report it comes from (`[01]` to `[05]`) and, for empirical rules, the confidence tag from `docs/research/02`. No essays.
- Every reference document starts with a one-line "Read this when" note and ends with a "Sources" line naming the report sections used.
- The skill never hand-writes SVG, PNG or PDF deliverables; it writes concept modules and runs the CLI. It never edits `brand.json` or `registry/` directly.
- The skill reads every critique sheet with the Read tool before deciding anything about a concept.
- Conversation rules in spec section 3.3 are reproduced in `SKILL.md` verbatim in meaning (one question per message, write-back, Collins rule 95, no blending, caps of 4 concept rounds and 3 refinement rounds, no "represents" in rationales).
- `cliches.md` is generated from `assets/cliches.json` by a script so the audit and the skill never disagree.
- Commit after every task with a `docs:` or `feat:` message ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. A session that starts with "make me a logo" and no brand folder: the skill must list brands (none), ask the first intake question, and never start drawing or searching the web for competitors before the brief is confirmed. Pinned in Task 21 (SKILL.md runbook) and exercised in Task 22.
2. A resumed session for a brand in `concepts` phase whose survivors have no `scorecard.json`: the skill must score before calling `sheet concepts`, because the CLI refuses unscored concepts. Pinned in Task 21.
3. An intake answer that names a category on the cliché blacklist as the owner's favourite motif (for example "I want a hexagon"): the skill must explain the finding from `cliches.md` once, offer a twist, and record the owner's decision, not silently comply or refuse. Pinned in Task 21.
4. A brand whose chosen font is not cached when a subagent builds a concept: the subagent must run `logomaker fonts fetch` instead of substituting another family. Pinned in Task 21 (subagent recipe).
5. A concept rationale that drifts into "the circle represents unity": the rationale rule must be checked before the package phase, and the example brand's `rationale.md` must pass it. Pinned in Task 22.

---

## File Structure (this part)

| File | Responsibility |
|---|---|
| `.claude/skills/logo/reference/*.md` (15 files) | the knowledge base, one topic per file |
| `scripts/build_cliches_md.py` | generates `reference/cliches.md` from `assets/cliches.json` |
| `.claude/skills/logo/SKILL.md` | routing, runbook, conversation rules, subagent recipe |
| `CLAUDE.md`, `README.md` | project routing, rules, where things live, tests |
| `docs/examples/keystone/` | one complete brand produced by the real workflow, plus `WALKTHROUGH.md` |
| `tests/test_knowledge.py`, `tests/test_skill_docs.py` | structural checks on the documents |
| `tests/test_example.py` | the example brand: complete, its rationale follows the rule, its package verifies (fast) and builds again (render) |

---

### Task 20: Knowledge base

**Files:**
- Create: `scripts/build_cliches_md.py` and the fifteen files under `.claude/skills/logo/reference/`: `process.md`, `evidence-rules.md`, `strategy-frameworks.md`, `questionnaire.md`, `logo-types.md`, `cliches.md` (generated), `craft.md`, `scorecard.md`, `trends.md`, `cautionary-tales.md`, `naming.md`, `fonts.md`, `color.md`, `deliverables.md`, `kit-api.md`
- Test: `tests/test_knowledge.py`

**Interfaces:**
- Consumes: `docs/research/01` to `05`, `assets/cliches.json`, the kit API from Part 1 (`src/logomaker/kit/`), the CLI reference from the spec section 10.
- Produces: the reference files below, each with exactly the level-two headings listed (the test checks them), 600 to 2,000 words each unless noted.

- [ ] **Step 1: Write the failing structural test**

`tests/test_knowledge.py`:

```python
import json
import re
from pathlib import Path

REF = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "logo" / "reference"

REQUIRED = {
    "process.md": ["Read this when", "Phases and gates", "Artifacts each phase must contain", "Agency rules", "Presentation protocol", "Sources"],
    "evidence-rules.md": ["Read this when", "Twenty rules", "Feature to personality table", "Boundary conditions", "What the evidence does not say", "Sources"],
    "strategy-frameworks.md": ["Read this when", "Onliness and positioning", "Archetypes to visual language", "Aaker personality", "Distinctive assets", "Adjective ladder", "Name to letterform", "Sources"],
    "questionnaire.md": ["Read this when", "Core questions", "Optional questions", "Inference guidance", "Write-back template", "Sources"],
    "logo-types.md": ["Read this when", "Taxonomy", "Decision guide", "App icon behaviour", "Sources"],
    "cliches.md": ["Read this when", "Any category", "By industry", "How to twist a justified motif", "Sources"],
    "craft.md": ["Read this when", "Optical corrections", "Small-size redraw", "Wordmark rules", "Construction checklist", "Kit recipes", "Sources"],
    "scorecard.md": ["Read this when", "Ten criteria", "Scoring rubric", "Gate", "scorecard.json format", "Sources"],
    "trends.md": ["Read this when", "Use", "Use carefully", "Avoid", "The AI-era cliche", "Sources"],
    "cautionary-tales.md": ["Read this when", "Cases", "Rules", "Sources"],
    "naming.md": ["Read this when", "Name types", "Sound symbolism", "Letterform scoring", "Checks", "Trademark caveat", "Sources"],
    "fonts.md": ["Read this when", "Catalogue by category", "Pairing", "Licensing", "Sources"],
    "color.md": ["Read this when", "Hue, saturation and lightness", "Cross-cultural notes", "Thresholds", "Building a palette in OKLCH", "Designing the reverse", "tokens.json format", "Sources"],
    "deliverables.md": ["Read this when", "Package manifest", "Platform specs", "Clear space and minimum sizes", "BRAND.md template", "Sources"],
    "kit-api.md": ["Read this when", "Concept module contract", "Primitives", "Operations", "Text", "Mark and lockups", "Worked examples", "Sources"],
}


def headings(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^## (.+)$", text, re.M)]


def test_reference_files_exist_with_required_headings():
    for name, required in REQUIRED.items():
        path = REF / name
        assert path.is_file(), name
        found = headings(path.read_text(encoding="utf-8"))
        for h in required:
            assert any(f.startswith(h) for f in found), f"{name}: missing heading {h!r}"
        words = len(path.read_text(encoding="utf-8").split())
        assert words >= 400, f"{name}: only {words} words"


def test_cliches_md_matches_json():
    data = json.loads((REF.parent.parent.parent.parent / "assets" / "cliches.json").read_text())
    text = (REF / "cliches.md").read_text(encoding="utf-8")
    for key, entry in data["industries"].items():
        assert f"### {key}" in text, key
        for motif in entry["motifs"]:
            assert motif in text, (key, motif)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_knowledge.py -q`
Expected: FAIL with `AssertionError: process.md`.

- [ ] **Step 3: Write the cliché generator and run it**

`scripts/build_cliches_md.py`:

```python
"""Generate .claude/skills/logo/reference/cliches.md from assets/cliches.json (single source for audit and skill)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "cliches.json"
OUT = ROOT / ".claude" / "skills" / "logo" / "reference" / "cliches.md"

INTRO = """# Cliché blacklist

Read this when: striking ideas in phase 4 (concepts), checking a motif the owner asked for, or justifying a twisted motif. Generated from `assets/cliches.json` by `scripts/build_cliches_md.py`; the audit uses the same data, so edit the JSON, not this file.

A motif on this list is famous but not unique: it identifies the category, not the brand [05 section 5.5, 03 section 5]. Use one only when the brief makes it the strategy, and then twist it until it scores as unique against the five nearest competitors.

"""

TWIST = """## How to twist a justified motif

1. Name the category cue in one sentence and the one idea it must carry instead.
2. Change its construction logic, not its decoration: cut it from the name's letterform, build it from the product's real geometry, or make it the negative space of something ownable.
3. Remove every neighbour it usually comes with (the hexagon's sparkle, the leaf's globe, the arrow's upward slant).
4. Check it against the five nearest competitors by description; if two of them could own it, kill it.
5. Record the decision with `logomaker brand decide` so the rationale can defend it.

## Sources

05 section 5.5 (industry cliché blacklist, LogoLounge saturation lists), 04 section 2 (the AI logo aesthetic), 03 section 5 (distinctiveness spectrum).
"""


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    lines = [INTRO, "## Any category", "", "Motifs: " + ", ".join(data["any"]["motifs"]), "", "Styles: " + ", ".join(data["any"]["styles"]), "", "## By industry", ""]
    for key, entry in data["industries"].items():
        lines += [f"### {key}", "", "Aliases: " + ", ".join(entry.get("aliases", [])), "", "Motifs: " + ", ".join(entry["motifs"]), ""]
        if entry.get("styles"):
            lines += ["Styles: " + ", ".join(entry["styles"]), ""]
    lines.append(TWIST)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
```

Run: `uv run python scripts/build_cliches_md.py`
Expected: `wrote .../reference/cliches.md`.

- [ ] **Step 4: Write the fourteen hand-written reference files**

Each file uses this frame:

```markdown
# <Title>

Read this when: <the phase or moment, one line>.

## <Heading from the table below>
...

## Sources

<report numbers and sections>
```

Write them from the research reports as follows. The headings must match `tests/test_knowledge.py` exactly (a heading may carry a suffix after the required words).

1. `process.md` from `docs/research/01` sections 1, 3 and 4 and the spec sections 3 and 4. Headings: **Phases and gates** (the six phases with their gate, artifact and CLI command in a table); **Artifacts each phase must contain** (bullet lists for brief.md, naming.md, strategy.md, territories.json, concept folders, final/, package/); **Agency rules** (numbered: strategy before style; silhouette before colour; knock-out before presenting; never a blank page; test recognition, not likability; do not over-explain; explore wide then converge; design the system; change the logo last; never launch into a vacuum, each with the case that proves it); **Presentation protocol** (the Collins rule 95 preface word for word, the Armani Exchange lesson, how to ask "what do you like in each", how to separate unfamiliarity from a flaw with one probing question).
2. `evidence-rules.md` from `docs/research/02` sections K and L. Headings: **Twenty rules** (the numbered list with confidence tags and the study behind each); **Feature to personality table** (the Aaker table reproduced); **Boundary conditions** (when each rule flips: negative categories, familiar brands, conservative audiences, cluttered contexts, luxury and AI disclosure); **What the evidence does not say** (gaps: AI-generated logos, memorability models, small sizes).
3. `strategy-frameworks.md` from `docs/research/05` section 3 and `01` section 4. Headings: **Onliness and positioning** (both templates with one filled example); **Archetypes to visual language** (the twelve-row table); **Aaker personality** (five dimensions, how to score 0 to 1 from the brief); **Distinctive assets** (fame and uniqueness grid; for a new brand choose for uniqueness); **Adjective ladder** (adjective, principle, test; three examples); **Name to letterform** (length, initial class, double letters, ligatures, L-flourish warning, case decisions).
4. `questionnaire.md` from the spec section 4.1 and `05` section 3.7. Headings: **Core questions** (the eleven, each with a one-line "why" and what a good answer looks like); **Optional questions**; **Inference guidance** (archetype from persona and admired brands; personality scores from adjectives; industry tag from the business line; surfaces ranking); **Write-back template** (the brief.md skeleton and the brief.json field list from `schemas.Brief`).
5. `logo-types.md` from `05` section 4. Headings: **Taxonomy** (eight types with right-when, wrong-when); **Decision guide** (the seven steps; symbol-only is never a launch state); **App icon behaviour** (per type, and the 37/6/56 split with its date).
6. `craft.md` from `05` section 5 and `04` section 1.2. Headings: **Optical corrections** (overshoot 1.5 percent, horizontals 92 percent, curves 105 percent, optical centre above true centre; which kit helper does each); **Small-size redraw** (thicken strokes, open counters, drop detail, 15 to 19 unit grids, tiers are parameter overrides); **Wordmark rules** (real fonts only, one owned quirk, letter identity survives, tracking tighter at display and looser at small, the Kia test); **Construction checklist** (the fourteen-item craft checklist); **Kit recipes** (monogram from a glyph counter, ring with a gap, keyline grid, negative-space cut, badge with inner clear space, each as a short code snippet using the kit).
7. `scorecard.md` from the spec section 8.2 and `01` section 4. Headings: **Ten criteria** (each with the question to ask and what evidence counts); **Scoring rubric** (1, 3 and 5 described per criterion); **Gate** (appropriate, simple, legible at 4 or more; no hard audit failures); **scorecard.json format** (the exact JSON with all ten keys, evidence, kill, reason).
8. `trends.md` from `05` sections 1.2 to 1.4. Headings: **Use**, **Use carefully**, **Avoid** (each a list with the reason and the date of the source), **The AI-era cliche** (hexagons 4.6 times, concentric apertures, sparkles, blue-violet gradients; what to reach for instead).
9. `cautionary-tales.md` from `05` section 2 and `01` section 2. Headings: **Cases** (the table with what happened, what went wrong, the rule), **Rules** (the six generalisable rules).
10. `naming.md` from `05` sections 3.6 and 3.7, `02` section G, `03` section 5. Headings: **Name types** (descriptive, evocative, invented with trade-offs); **Sound symbolism** (front and back vowels, stops and fricatives, with the congruence rule); **Letterform scoring** (how to score a candidate 1 to 5 on wordmark potential); **Checks** (`logomaker names analyze`, `names check`, what each status means); **Trademark caveat** (the exact sentence to say: knock-out only, not legal clearance, and where to search).
11. `fonts.md` from `03` section 4. Headings: **Catalogue by category** (the ten categories with their families and personality notes, matching `assets/fonts/catalog.json`); **Pairing** (one family for the wordmark, at most one companion; contrast in class not in mood); **Licensing** (OFL permits logo use, reserved font names, ship the licence file, convert to outlines).
12. `color.md` from `02` section F, `03` section 3. Headings: **Hue, saturation and lightness** (the personality mapping with confidence); **Cross-cultural notes**; **Thresholds** (WCAG and APCA numbers used by the audit); **Building a palette in OKLCH** (start from the feature targets, `logomaker color ramp`, at most two colours plus ink); **Designing the reverse** (lighten the primary, never auto-invert, re-check contrast); **tokens.json format** (the exact JSON for `color.Tokens`).
13. `deliverables.md` from `03` sections 1, 2, 6 and 7. Headings: **Package manifest** (the file groups the builder writes); **Platform specs** (the numbers with their source); **Clear space and minimum sizes** (the x unit and the defaults in `brand.json`); **BRAND.md template** (the section list the builder renders).
14. `kit-api.md` from the spec section 6 and the implemented kit. Headings: **Concept module contract** (META, PARAMS, TIERS, build; params.json; tokens.json; what the CLI writes to build/); **Primitives** (every function with its signature and a one-line note); **Operations** (booleans, stroke, offset, transforms, align, center, fit, optical helpers); **Text** (`text`, `glyph`, metrics, tracking and kern units); **Mark and lockups** (roles, Composite, x unit, lockups, variants); **Worked examples** (four complete concept modules: a monogram cut from a glyph counter, a pictorial mark from primitives, an abstract mark on a grid, a wordmark with one ligature quirk; each under 40 lines and known to build).

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_knowledge.py -q`
Expected: 2 passed.

- [ ] **Step 6: Check the worked examples really build**

Create a brand in a scratch folder, copy each of the four `kit-api.md` examples into `brands/scratch/concepts/0N-example/concept.py`, run `uv run logomaker concept run scratch 0N-example --no-render` for each, confirm `"ok": true` in each audit, then delete `brands/scratch`.

- [ ] **Step 7: Commit**

```bash
git add scripts/build_cliches_md.py .claude/skills/logo/reference tests/test_knowledge.py
git commit -m "docs: knowledge base for the logo skill

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 21: `SKILL.md`, `CLAUDE.md`, `README.md`

**Files:**
- Create: `.claude/skills/logo/SKILL.md`, `CLAUDE.md`
- Modify: `README.md` (replace the Part 1 stub)
- Test: `tests/test_skill_docs.py`

**Interfaces:**
- Consumes: every CLI command from Parts 1 and 2; the reference files from Task 20.
- Produces: the three documents below. `SKILL.md` is read by Claude Code when the skill triggers; `CLAUDE.md` is read at session start.

- [ ] **Step 1: Write the failing test**

`tests/test_skill_docs.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude" / "skills" / "logo" / "SKILL.md"


def test_skill_frontmatter_and_sections():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: logo\n")
    for heading in ("## First move", "## Phase runbook", "## Conversation rules", "## Reading renders", "## Writing concept modules",
                    "## Parallel concepts with subagents", "## Resuming", "## When the CLI fails", "## Done checklist"):
        assert heading in text, heading
    for rule in ("one question", "Collins", "blend", "represents", "knock-out only, not legal clearance", "logomaker fonts fetch", "scorecard.json"):
        assert rule in text, rule
    for cmd in ("brand list", "brand new", "brand advance", "names check", "sheet territories", "concept run", "sheet concepts", "sheet refine", "package build", "package verify"):
        assert f"logomaker {cmd}" in text, cmd


def test_claude_md_routes_and_rules():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for heading in ("## Routing", "## Rules", "## Where things live", "## Tests"):
        assert heading in text
    assert "`logo` skill" in text and "playwright install" in text and ".env" in text and "300000" in text


def test_readme_mentions_setup():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "uv run logomaker setup --check" in text and "brands/<slug>" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_skill_docs.py -q`
Expected: FAIL with `FileNotFoundError` for `SKILL.md`.

- [ ] **Step 3: Write `SKILL.md`**

`.claude/skills/logo/SKILL.md`:

```markdown
---
name: logo
description: Guided logo and brand identity creation for the owner's ventures, from intake and naming through strategy, territories, vetted concepts, refinement and a verified export package. Use for any request about a logo, mark, wordmark, brand identity, naming a venture, favicons, app icons or brand assets in this folder.
---

# Logo skill

You are the designer. The `logomaker` CLI does every deterministic step; you do the judgment. The research this
skill is built on lives in `reference/`; read the files named for each phase before working in that phase.

## First move

1. Run `uv run logomaker brand list` and read the JSON.
2. If brands exist, say which exist and their phase, then ask whether to continue one or start a new venture.
3. If none exist, say so in one line and ask the first intake question.
4. Never draw, search the web, or propose names before a brief is confirmed.

## Phase runbook

Every command prints one JSON object; read `ok`, `errors`, `warnings` and act on them. Phases advance with
`uv run logomaker brand advance <slug> --to <phase>`, which refuses until the phase's artifacts exist.

### Intake (read `reference/questionnaire.md`, `reference/strategy-frameworks.md`)
- Start: `uv run logomaker brand new "<Name>"` or, without a name, `uv run logomaker brand new "<Working title>" --unnamed`.
- Ask the eleven core questions one per message, skipping any already answered. Prefer a short multiple choice where it helps.
- Infer archetype, personality scores (0 to 1 on the five Aaker dimensions), the industry tag and the ranked surfaces.
- Write `brands/<slug>/brief.md` (readable write-back) and `brief.json` (fields of `schemas.Brief`). Show the write-back and wait for the owner's correction or confirmation.
- Record what the owner changed with `uv run logomaker brand decide <slug> --phase intake --by user --note "..."`.
- Gate: owner confirms the brief. Then advance to `naming` (if `needs_name`) or `strategy`.

### Naming (read `reference/naming.md`; only when the venture is unnamed)
- Generate 15 to 25 candidates across descriptive, evocative and invented, each with meaning, sound profile, letterform note and fit score.
- Run `uv run logomaker names analyze <name>` for the shortlist and `uv run logomaker names check <name>` for the top five.
- Run a web knock-out for the top five (trademark registries, app stores, general web). Say, in these words: "knock-out only, not legal clearance".
- Write `naming.md` with the shortlist, checks and knock-out notes. Owner picks. Then `uv run logomaker brand rename <slug> --name "<Name>"` and advance to `strategy`.

### Strategy (read `reference/evidence-rules.md`, `reference/logo-types.md`, `reference/cliches.md`, `reference/cautionary-tales.md`, `reference/trends.md`)
- Look at `brands/<slug>/inspiration/` if it has images; say what you take from them.
- Search the web for the five nearest competitors and describe the category's visual uniform.
- Write `strategy.md` with the nine sections in `reference/process.md` and `strategy.json` (fields of `schemas.Strategy`).
- Set the industry and surfaces: `uv run logomaker brand set <slug> --industry "<tag>" --surface "<first>" --surface "<second>" --surface "<third>"`.
- Gate: owner approves. Advance to `territories`.

### Territories (read `reference/fonts.md`, `reference/color.md`)
- Define two or three territories in `territories/territories.json` (fields of `schemas.TerritoriesSpec`); each names one to three catalogue families (`uv run logomaker fonts list --category ...`).
- `uv run logomaker sheet territories <slug>` renders and opens the board. Read `territories/board.png` yourself first.
- Owner picks one. `uv run logomaker brand set <slug> --territory <territory-slug>` and `--font wordmark=<Family>:<weight>`. Advance to `concepts`.

### Concepts (read `reference/craft.md`, `reference/kit-api.md`, `reference/scorecard.md`, `reference/cliches.md`)
- Write 12 to 20 one-line ideas in `concepts/ideas.md`, each tagged with motifs. Strike any on the blacklist unless the brief made it the strategy; then twist it and justify it.
- Pick 5 to 8 structurally different directions. Create `concepts/NN-slug/concept.py` for each (see "Writing concept modules"). Black only; no `tokens.json` in this phase.
- For each: `uv run logomaker concept run <slug> NN-slug`. Read `renders/round-N/critique.png`. Score the ten criteria into `scorecard.json` with evidence, and write your notes in `critique.md`.
- Revise the module and rerun, at most four rounds per concept. Kill a concept that cannot pass by setting `"kill": true` with a reason.
- Present 3 to 5 survivors: `uv run logomaker sheet concepts <slug> --concepts a,b,c`. The CLI refuses a concept without a passing audit and a gate-passing scorecard; fix that before presenting, never argue with it.
- Before the sheet, say the Collins rule 95 preface (in "Conversation rules"). Ask what the owner likes in each before asking which to choose.
- Owner picks one. `uv run logomaker brand set <slug> --concept NN-slug` and `brand decide` with the notes. Advance to `refinement`.

### Refinement (read `reference/craft.md`, `reference/color.md`, `reference/deliverables.md`)
- Copy the chosen `concept.py` to `final/concept.py`; write `final/params.json` (`{}` to start).
- Work in this order, running `uv run logomaker concept run <slug> final` after each step and reading the critique: optical corrections; `small` and `favicon` tiers redrawn through overrides; wordmark set in the chosen family with at most one parametric quirk; lockups and the primary lockup (`brand set --primary-lockup`); then colour.
- Colour: write `final/tokens.json` (format in `reference/color.md`), run `uv run logomaker color check brands/<slug>/final/tokens.json`, fix until it passes.
- `uv run logomaker sheet refine <slug>` renders and opens the round. Read it yourself first. Do the unintended-readings pass on the mirrored and rotated panels.
- Knock-out: search the web for look-alikes by description and conflicting marks; write `final/knockout.md` with the caveat.
- At most three rounds. Gate: owner approves. Advance to `package`.

### Package (read `reference/deliverables.md`)
- Write `final/rationale.md`: one paragraph, for the owner, no "represents", no construction diagrams, ratios or golden ratio.
- `uv run logomaker package build <slug>` with the Bash timeout set to 300000, then `uv run logomaker package verify <slug>`.
- Open `brands/<slug>/package/` in Finder and `package/brand-sheet.pdf` in the browser; read the brand sheet yourself.
- `uv run logomaker brand advance <slug> --to done`. Summarise what was delivered and where.

## Conversation rules

- Strategy before any drawing. Silhouette in black before any colour. Knock-out before presenting.
- Ask one question per message. Write back your understanding at the end of intake and wait.
- Never present a concept that failed an audit or scored below 4 on appropriate, simple or legible.
- Never show a mark alone on a blank page; always through a sheet with mockups.
- Collins rule 95 preface, before the first concept sheet: "New ideas are fragile because they are unfamiliar. You may not like something you see here, but before saying so, find something you like in every direction."
- Never blend concepts. Pick one; a detail from another may be noted as a steal and recorded with `brand decide`.
- Caps: four revise rounds per concept, three refinement rounds. If stuck, say so and offer to go back to concepts.
- On a negative first reaction, ask one probing question (what reads wrong, at what size, in which mockup) before changing anything. Unfamiliarity fades; a legibility or equity problem does not.
- If the owner asks for a motif on the blacklist, show the finding from `reference/cliches.md` once, offer a twist, and record their decision. Do not refuse and do not silently comply.
- Rationales are one paragraph, written for the owner, without the word "represents".
- Trademark and look-alike checks are web searches and are always labelled "knock-out only, not legal clearance".

## Reading renders

After every `concept run`, `sheet territories`, `sheet concepts` and `sheet refine`, read the PNG with the Read tool before
deciding or showing anything. Look for: the silhouette at 16 px, merged counters at 32 px, a wobble in the mirrored
panel, an unintended reading in the rotated panel, and whether the one-colour panel still has a hierarchy.

## Writing concept modules

- Follow `reference/kit-api.md`. Build on the 1000-unit grid with primitives, booleans and `stroke`; keep symbols under 100 anchors.
- Set type with `text(...)` and `glyph(...)` from a cached family. If the family is not cached, run `uv run logomaker fonts fetch "<Family>"`; never substitute a different family silently.
- Never write SVG by hand and never edit files under `build/` or `renders/`; the CLI owns them.
- Tiers are parameter overrides in `TIERS`; redraw small sizes by thickening strokes and opening counters, not by scaling.
- Name motifs honestly in `META.motifs`; the audit checks them against the blacklist.

## Parallel concepts with subagents

For four or more directions, dispatch one subagent per direction with the Agent tool. Give each: the full `brief.md`,
`strategy.md`, the chosen territory entry, the one-line idea it owns, `reference/kit-api.md` and `reference/craft.md`,
the cached font families, and the instruction to write only `concepts/NN-slug/concept.py` and run
`uv run logomaker concept run <slug> NN-slug --no-render`, fixing until the audit's `ok` is true. Subagents do not
score or present; you read every critique sheet and score each concept yourself.

## Resuming

`uv run logomaker brand status <slug>` reports the phase, the next phase and what is missing. Read the phase's
artifacts before asking anything, then continue the runbook from that phase. If a concept in `concepts` phase has no
`scorecard.json`, score it from its latest critique before calling `sheet concepts`.

## When the CLI fails

- Exit 2 with `errors`: a rule or input problem. Fix the module, the JSON or the command; never retry verbatim.
- Exit 3: Chrome, network or a missing font. Say what is missing and what command fixes it.
- Exit 4: a verification failure in `package verify`; read `package/verify.json`, fix, rebuild.
- A traceback in the payload means the concept module raised; read it and fix the module.

## Done checklist

- `package/verify.json` has `ok: true` and `brand.json` phase is `done`.
- `BRAND.md`, `brand-sheet.pdf`, `README.md` and `rationale.md` are in `package/`.
- The owner has seen the brand sheet and knows where the files are.
```

- [ ] **Step 4: Write `CLAUDE.md`**

`CLAUDE.md`:

```markdown
# logo-maker

This folder turns a venture into a production-ready logo package. The `logomaker` CLI (Python, run with uv) does every
deterministic step: brand state, geometry, fonts, rendering, audits, sheets, exports. The `logo` skill in
`.claude/skills/logo/` runs the conversation and makes every design judgment.

## Routing

- Always use the `logo` skill for any request about a logo, mark, wordmark, brand identity, naming a venture, favicons,
  app icons, brand assets, or continuing a brand in `brands/`.

## Rules

- Never hand-write SVG, PNG, PDF or ICO deliverables. Write concept modules (`concept.py`) and run the CLI.
- Never edit `registry/` or any `brand.json` directly; use `uv run logomaker brand ...` commands.
- Never read `.env` if one appears; `.claude/settings.json` denies it.
- Every CLI command prints one JSON object on stdout; read it instead of parsing logs. Logs go to stderr.
  Exit codes: 0 ok, 2 rule or input violation, 3 external failure (Chrome, network, missing font), 4 verification failure.
- Run `uv run logomaker package build` with the Bash timeout set to 300000; every other command finishes within 60 s
  (font fetches depend on the network).
- Never run `playwright install`; rendering uses the installed Google Chrome.
- Read every critique sheet and owner sheet PNG with the Read tool before deciding about a concept.

## Where things live

- Brands: `brands/<slug>/` with `brand.json`, `brief.*`, `naming.md`, `strategy.*`, `territories/`, `concepts/`,
  `sheets/`, `final/`, `package/`, and `inspiration/` for reference images the owner drops in.
- Registry: `registry/brands.json` and the generated `registry/INDEX.md`.
- Knowledge base: `.claude/skills/logo/reference/`; full research reports in `docs/research/`.
- Code: `src/logomaker/`; templates: `templates/`; fonts cache and catalogue: `assets/fonts/`; cliché data: `assets/cliches.json`.
- Example brand: `docs/examples/keystone/`.

## Tests

- Fast suite, no Chrome and no network: `uv run pytest -m "not render and not live"`
- Render suite, uses the installed Chrome: `uv run pytest -m render`
- Live suite, needs the network: `uv run pytest -m live`
```

- [ ] **Step 5: Write `README.md`**

`README.md` (four-backtick fence because the file contains code fences):

````markdown
# logo-maker

A Claude Code driven logo generator for the owner's ventures. Open a terminal in this folder, run `claude`, and the
`logo` skill guides you from a venture (named or not) to a verified logo package: strategy, territories, vetted
concepts shown in context, refinement, and about 180 files with a one-page brand sheet.

Marks are constructed vectors: Python concept modules built on a geometry kit with real font outlines, compiled to
paths-only SVG, rendered through Google Chrome, audited automatically, and exported to every format a small company
needs. No image-generation APIs are involved.

## Setup

```
uv sync
uv run logomaker setup --check
```

Requires Google Chrome in `/Applications` and Python 3.12 (uv installs it).

## Use

Run `claude` here and ask for a logo. Outside Claude, the CLI works on its own:

```
uv run logomaker brand new "Keystone"
uv run logomaker fonts fetch Sora
uv run logomaker concept run keystone 01-arch
uv run logomaker sheet concepts keystone --concepts 01-arch,02-ring
uv run logomaker package build keystone && uv run logomaker package verify keystone
```

Every brand lives in `brands/<slug>/`; the finished package is `brands/<slug>/package/`. `docs/examples/keystone/`
is a complete example.

## Layout

`src/logomaker/` code, `templates/` sheets and documents, `assets/` fonts catalogue and cliché data,
`.claude/skills/logo/` the skill and its knowledge base, `docs/research/` the research it is built on,
`docs/superpowers/` the spec and plans.

## Tests

`uv run pytest -m "not render and not live"` (fast), `uv run pytest -m render` (Chrome), `uv run pytest -m live` (network).
````

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/test_skill_docs.py -q`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/logo/SKILL.md CLAUDE.md README.md tests/test_skill_docs.py
git commit -m "docs: logo skill runbook, CLAUDE.md routing and README

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 22: Example brand produced by the real workflow

**Files:**
- Create: `docs/examples/keystone/` (a copy of the finished brand folder), `docs/examples/keystone/WALKTHROUGH.md`
- Test: `tests/test_example.py`

**Interfaces:**
- Consumes: the whole system. The executor acts as the designer and follows `SKILL.md` exactly, with the owner's answers scripted below.

- [ ] **Step 1: Write the failing test**

`tests/test_example.py`:

```python
import json
import re
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "examples" / "keystone"


def test_example_brand_is_complete():
    assert (EXAMPLE / "WALKTHROUGH.md").is_file()
    state = json.loads((EXAMPLE / "brand.json").read_text())
    assert state["phase"] == "done" and state["concept"] and state["territory"]
    assert json.loads((EXAMPLE / "package" / "verify.json").read_text())["ok"]
    for name in ("brief.md", "brief.json", "strategy.md", "strategy.json", "territories/territories.json", "concepts/ideas.md",
                 "final/concept.py", "final/tokens.json", "final/rationale.md", "final/knockout.md",
                 "package/BRAND.md", "package/brand-sheet.pdf", "package/README.md", "package/tokens.json", "sheets/concepts.html"):
        assert (EXAMPLE / name).is_file(), name
    concepts = [p for p in (EXAMPLE / "concepts").iterdir() if p.is_dir()]
    assert len(concepts) >= 5
    assert sum(1 for c in concepts if (c / "scorecard.json").is_file()) >= 3


def test_example_rationale_follows_the_rule():
    text = (EXAMPLE / "final" / "rationale.md").read_text()
    assert "represent" not in text.lower() and "golden ratio" not in text.lower()
    assert len(text.split()) <= 180 and text.count("\n\n") <= 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_example.py -q`
Expected: FAIL with `AssertionError` on `WALKTHROUGH.md`.

- [ ] **Step 3: Run the workflow as the designer with these scripted owner answers**

Work in a fresh Claude Code session in this folder so the skill triggers, or follow `SKILL.md` by hand. Owner answers:

1. Business: Keystone sends invoices that get paid faster, for solo consultants, solving late payments.
2. One idea: the piece that holds everything together.
3. Onliness: the only invoicing tool that nags clients so you don't have to.
4. Adjectives: steady but not boring; direct but not rude; warm but not cute.
5. Persona: a calm site foreman who is good at follow-up.
6. Admired: Stripe (restraint), Patagonia (conviction). Disliked: generic fintech blue.
7. Surfaces: app icon, website header, social avatar.
8. Harshest: 16 px favicon and one-colour embroidery.
9. Colours: wants ember orange; forbids fintech blue; category has claimed blue and green.
10. Off limits: upward arrows, shields. No cultural constraints; English only.
11. Name: Keystone, written "Keystone", no tagline; story: the stone that locks an arch.
12. Territory choice: the warmer, denser of the boards. Concept choice: the direction whose symbol derives from the K or the arch. First reaction to the concept sheet: "the ring one looks like a loading spinner"; expect the probing question and answer "at the avatar size".
13. Refinement approval after the colour round. Any extra question: answer with the most conservative option.

Steps the executor performs, in order, recording each command in `WALKTHROUGH.md`:

1. `uv run logomaker brand new "Keystone"`; intake; write `brief.md` and `brief.json`; advance to `strategy`.
2. Strategy with a real web look at five invoicing competitors; `strategy.md` and `strategy.json`; `brand set` industry and surfaces; advance to `territories`.
3. Two territories using catalogue families fetched with `uv run logomaker fonts fetch` (for example Sora and Archivo; Bricolage Grotesque and Fraunces); `sheet territories`; choose; `brand set --territory ... --font wordmark=...`; advance to `concepts`.
4. `concepts/ideas.md` with 12 or more ideas; five concept modules in five folders, at least three structurally different (a monogram from the K counter, an arch or keystone pictorial from primitives, an abstract stacked-block mark, a wordmark with one quirk, one more); `concept run` each, read every critique, score each into `scorecard.json`, kill at least one with a reason; `sheet concepts` for the survivors; choose; advance to `refinement`.
5. Refinement in the runbook order; `final/tokens.json` passing `color check`; at least one `sheet refine`; `final/knockout.md`; advance to `package`.
6. `final/rationale.md` (one paragraph, no "represents"); `package build`; `package verify`; advance to `done`.
7. Copy `brands/keystone/` to `docs/examples/keystone/`, excluding `package/*-2048.png`, `package/*-1024.png` and `concepts/*/renders/round-*/critique.png` for rounds other than the last (to keep the example under 10 MB), and note the exclusions in `WALKTHROUGH.md`. Keep `brands/keystone/` as a live brand only if the owner wants it; otherwise delete it after copying.

`WALKTHROUGH.md` contains: the scripted answers, every command run with its outcome, the decisions recorded with `brand decide`, how long each phase took, what the critique sheets caught (at least two concrete catches), and what was excluded from the copy.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_example.py -q`
Expected: 2 passed.

- [ ] **Step 5: Run everything and commit**

Run: `uv run pytest -q -m "not live"`
Expected: all tests pass.

```bash
git add docs/examples/keystone tests/test_example.py
git commit -m "docs: example brand built with the logo skill

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Part 3 is done when

- All three suites pass.
- A fresh `claude` session in this folder, asked "I want a logo for a new venture", lists no brands (or the example only) and asks the first intake question without drawing or searching first.
- `docs/examples/keystone/package/verify.json` reports `ok: true`, and the owner has opened `brand-sheet.pdf` once and said it reads correctly.
