# Raising the ceiling: design spec

Date: 2026-10-08. Status: approved in conversation, pending written review. Builds on `2026-10-05-logo-maker-design.md` (the spec) and the code at `24fa2da`.

## 1. Purpose

The first version of logo-maker reliably produces a clean, defensible, mid-tier mark. An assessment of the Keystone example on 2026-10-07 found six shortfalls. This spec gives each one a fix, ordered so that the fixes can be measured:

| # | Shortfall | Fix | Workstream |
|---|---|---|---|
| 1 | The critic is the designer: Claude scores its own concepts with full context | A blind critic: a fresh agent scores an anonymised, shuffled sheet, and disagreements must be reconciled | WS1 |
| 2 | One example (Keystone, a gift of a name) is thin evidence | An evaluation set of three hard briefs, run headless, with a baseline and reruns | WS2 |
| 3 | The kit imposes a house style: heavy, flat, symmetrical geometric glyphs; the wordmark is typeset with tracking | Variable-width strokes, splines, node editing, repetition, free snapping, a wordmark stage | WS3 |
| 4 | Marks are safe and literal; "distinctive" is scored generously | Ideation routes with coverage rules, and an obviousness probe that caps `distinctive` | WS4 |
| 5 | The knock-out searches by description only | A knock-out by image: Google Lens, and the WIPO Global Brand Database for the final mark | WS5 |
| 6 | Too much machinery for a quick venture | An express track that keeps every gate and shrinks every phase | WS6 |

Success looks like this:

- The three evaluation briefs, rerun after WS3 and WS4, reach a critic median of 4 or more on `distinctive`, with at least one non-literal survivor on every concept sheet and no regression on the gate criteria.
- Every new kit operation has tests, a kit-api.md entry and a craft.md recipe, and the Keystone example still builds and verifies unchanged.
- An express brand goes from first question to a verified package in under fifteen minutes of agent time.

## 2. Decisions already made

| Decision | Choice | Why |
|---|---|---|
| Order | Measure, then build: WS1 and WS2 before WS3 and WS4 | Without an independent score and a baseline there is no way to tell whether the kit work helped |
| Variable-width strokes | Implemented natively on skia-python, not with beziers.py | beziers.py's last commit is June 2024 with 71 stars; the kit already flattens cubics and simplifies paths, so the missing piece is a curve fit, not a library |
| Similarity index | None; no Large Logo Dataset, no METU trademark set | LLD is licensed for academic research only; both are 700 MB to 13 GB downloads; a live reverse-image search is enough for a knock-out |
| Image knock-out | Google Lens through the Chrome extension; WIPO Global Brand Database image search for the final mark | Both are free, both take an uploaded image; no paid API (TinEye, Bing Visual Search) in this version |
| Critic model | An Opus subagent, two passes with different shuffles | The owner's standing rule: subagents on Opus or cheaper, `model` set explicitly; two orders mitigate position bias, the best-documented bias in LLM judges |
| Image generation | Still none | Unchanged from the spec; the fixes here widen the constructed-vector vocabulary instead |
| Paid services | None | Owner's constraint; every search is a web page or an existing tool |
| Express track | Shrinks phases, keeps gates | A phase skipped is a decision nobody made; a phase shortened is still a decision |

## 3. WS1: the blind critic

### 3.1 What the critic sees

A new owner-free sheet, `uv run logomaker sheet critic <slug> --concepts <a,b,c> [--seed N]`, renders `sheets/critic-N.html` and `critic-N.png` from the survivors' latest rendered critique outputs: for each concept the size ladder, the mirrored and rotated panels, the one-colour panel and the mockups, exactly as `critique.png` shows them. It withholds the slug, `META.idea`, the scores, the ideas file, the module and critique.md. Concepts are labelled A, B, C in a shuffled order. The mapping from letter to slug and the seed go to `sheets/critic-N.key.json`, which the critic is never given.

The critic subagent receives: the sheet PNG path, `brief.md`, `strategy.md`, `reference/scorecard.md`, `reference/evidence-rules.md` and `reference/trends.md`. It is told it is the second designer in the studio, seeing the work for the first time, and that the sheet's order is arbitrary.

### 3.2 What the critic returns

One JSON object per pass, written by the critic to `sheets/critic-N.pass-<1|2>.json`:

- `cards`: for each letter, the ten criteria scored 1 to 5 with a line of evidence each, in the scorecard.md rubric.
- `pairs`: for every pair of letters, which the critic would present first and why, judged with the pair named in both orders (A then B, B then A). A pair whose two orders disagree is a tie.

The skill runs the critic twice, with `--seed` values that give different orders, and then `uv run logomaker concept critic <slug> --sheet N`, which reads both passes and the key and writes `concepts/<NN-slug>/critic.json` per concept, validating as `schemas.CriticCard`:

- `scores`: the mean of the two passes per criterion, rounded to the nearest whole, halves up.
- `evidence`: both passes' lines per criterion.
- `preferred_over`: the slugs this concept beat in both passes and both orders; `tied_with` the rest.
- `sheet`, `passes`, `fingerprint`: the critique fingerprint of the concept the critic saw, so a later `concept run` makes the card stale.

### 3.3 Reconciliation and gates

The designer scores first, as now, before the critic sheet exists. After the merge, for every criterion where the designer's and the critic's scores differ by two or more, the designer writes a `reconciled` entry in `scorecard.json`: `{"<criterion>": "<one line: whose score stands and why>"}`. The designer may change the score, not the critic's.

- `sheet concepts` refuses a survivor without a fresh `critic.json`, and one with an unreconciled disagreement of two or more on any criterion. The sheet shows two totals per survivor, "designer 43 / critic 38", and the critic's preference order as a line under the preface.
- `brand advance --to refinement` applies the same rule to the chosen concept.
- The critic runs once more on `final/` before the package: `sheet critic <slug> --final` renders the final critique outputs alone (one card, no pairs), `concept critic <slug> --sheet N --final` writes `final/critic.json`, and `package build` refuses without a fresh one. The final reconciliation goes into `final/scorecard.json`.

Gate criteria stay the designer's reconciled scores; the critic informs the gate, it does not own it. Schema change: `Scorecard` gains `reconciled: dict[str, str]` (default empty). The cross-file check, that every criterion `critic.json` disagrees on by two or more has a `reconciled` entry, lives in `registry.passing_scorecard`, which reads both files; the model itself cannot see the critic card.

### 3.4 Skill changes

SKILL.md's concepts phase gains the step between scoring and `sheet concepts`; the refinement phase gains the final critic before `package build`. A new `reference/critic.md` holds the critic's brief verbatim (what it receives, the rubric reminder, the output format, the rule that it never searches the web or reads the brand folder). "Parallel concepts with subagents" is extended with the critic dispatch: `model` is `opus`, two Agent calls in one message.

## 4. WS2: the evaluation set

### 4.1 Briefs

`docs/evals/<slug>/owner.md` holds a scripted owner in the format of the Keystone walkthrough: the thirteen answers verbatim plus the conservative-option rule. Three briefs, each hard where Keystone was easy:

| Slug | Venture | Why it is hard |
|---|---|---|
| `orvane` | Orvane, an API for reliable webhook delivery, for backend developers | A coined name with no metaphor and no obvious letter quirk; the category uniform is hexagons, nodes and arrows |
| `clear-ledger` | Clear Ledger, bookkeeping for one-person businesses | Two words, both category cues; the blacklist strikes the first ten ideas, so the twist has to carry the sheet |
| `pip` | Pip, a reading app for five-to-eight-year-olds, wants a character | Warmth and a mascot test the organic vocabulary of WS3; a three-letter name tests the wordmark stage |

Each owner script picks the warmer territory, chooses the survivor the critic preferred, reacts negatively once with a size named, and approves after one colour round.

### 4.2 Runner

`scripts/eval_brand.py <slug> [--model opus] [--cycle <label>]` runs the headless harness the owner already uses: `CLAUDECODE` unset, `LOGOMAKER_ROOT` set to a scratch directory, `claude -p` with the owner script in the prompt and a turn cap, stream JSON captured. The prompt tells the agent it is in evaluation mode: the owner's answers are scripted, every artifact is still written, every decision is recorded with `brand decide --by user --note "scripted: ..."`, and the brand must reach `done`. The model is never the session's model.

After the run the script copies into `docs/evals/<slug>/<cycle>/`: `sheets/concepts.png`, `sheets/critic-*.png`, every `critic.json` and `scorecard.json`, `final/renders/round-<last>/critique.png`, `package/brand-sheet.pdf`, and writes `report.md`: the model, the wall-clock time per phase from the decision log, the designer and critic totals per survivor, the routes and probe counts (WS4), the gate results, and the turn count. It then deletes the scratch directory. The package itself is not kept; the report records whether `verify.json` was ok.

### 4.3 Cycles

- `baseline`: after WS1, before WS3 and WS4.
- `kit`: after WS3. `ideation`: after WS4. `final`: after WS6.
- `docs/evals/README.md` carries one table, a row per brief and cycle: critic `distinctive`, critic total of the chosen concept, non-literal survivors on the sheet, gate regressions, minutes. Every cycle runs each brief once; single runs are noisy, so the table reports direction, and a change under one point on a single criterion is not a finding.

The evaluation set is not pytest. `tests/test_evals.py` checks only that each `owner.md` has thirteen answers and that the runner's prompt builds.

## 5. WS3: the kit vocabulary and the wordmark stage

Every operation below returns a `Shape`, takes `free=False` where it snaps, keeps a `TextShape` first operand's metrics, and gets unit tests in `tests/test_kit_*.py`, an entry in `reference/kit-api.md` and a recipe in `reference/craft.md`. Anchor rules are unchanged: the symbol warns above 100 and fails above 150 unless `allow_complex`.

### 5.1 `brush(points, widths, cap="round", free=False)`

A variable-width stroke along a cubic chain (`points` as for `bezier`: 1 + 3k points). `widths` is a list of one width per on-curve point, interpolated linearly by arc length between them; a single number is a constant width (then `bezier(points, width)` is the same thing). Construction: flatten each segment with `shape._cubic_points`, compute unit normals, offset left and right by half the local width, cap the ends (`round`, `butt`, `square`), close, then fit each side back to cubic Béziers with Schneider's algorithm at a tolerance of 0.5 units, simplify with skia and re-wind. The fit keeps the anchor count near twice the centreline's on-curve nodes plus the caps; a test asserts that a five-node brush stays under 24 anchors. Self-overlap where the width exceeds the local radius of curvature is resolved by the simplify step; a test covers a tight hook.

### 5.2 `spline(points, tension=0.5, closed=True, width=None, free=False)`

A Catmull-Rom curve through `points`, converted to cubic segments; filled when `width` is None, otherwise stroked through `bezier`. `tension` 0 is the uniform Catmull-Rom spline, 1 is straight segments. This gives an organic silhouette without hand-placed control points.

### 5.3 Node editing

- `shape.nodes()` returns the on-curve nodes as a list of `Node(index, x, y, subpath, smooth)`, in path order; `TextShape` includes them for the whole string.
- `move_node(shape, index, dx, dy)` moves one node and the two handles attached to it; `delete_node(shape, index)` removes a node and joins its neighbours with one cubic through the removed node's handles.
- `cut(shape, x1, y1, x2, y2)` splits a shape along the straight line through the two points and returns `(left, right)` as two shapes (left is the side to the left when travelling from the first point to the second); a concept keeps either or both.

These are the tools for the wordmark rule, which changes from "one owned quirk at most" to "at most two, each parametric, each surviving the Kia test"; craft.md's wordmark rules 2 and 3 are rewritten and the critic's `legible` score is the check.

### 5.4 `repeat(shape, n, mode="radial", cx=0, cy=0, cols=None, rows=None, step=None, axis=None)`

`radial` places `n` copies around (cx, cy) at equal angles; `grid` places copies on `cols` by `rows` at `step`; `mirror` unions the shape with its reflections across `axis` (`"x"`, `"y"` or `"xy"`). Returns the union. Evidence rule 1 favours one repeated element; this makes it one call.

### 5.5 Module-wide snapping

`Meta` gains `snap="grid"` (today's behaviour) or `"free"`: with `free`, every primitive and op in the module behaves as if `free=True`, and the audit reports `free_segments` as info instead of a warning. `near_miss_angles` still runs; a free module justifies it in critique.md as now.

### 5.6 The wordmark stage

`uv run logomaker sheet wordmark <slug> [--concept <NN-slug>|final] [--no-open]` renders `sheets/wordmark-N.html` and `.png`: the wordmark at the 32 px header size, at the 120 px horizontal minimum and at 400 px; under each a row of bars showing the gap between adjacent glyph boxes (from `TextShape.glyph_bounds`) with its value in units, and the median gap. A new audit line, `spacing_rhythm`, lists the gaps as info and warns when any gap exceeds 1.8 times the median or falls under half of it, naming the pair. Kerning stays a judgment through `kern={"Ke": -20}`; the sheet makes it a visible one. The refinement runbook's wordmark step reads: set the family, run the wordmark sheet, read it, fix pairs, re-run.

### 5.7 Documentation and example

kit-api.md gains a section per operation with a worked example that `tests/test_knowledge.py` runs; craft.md gains four recipes (a brushed stroke with a swelling terminal, a spline leaf, a node-cut glyph, a radial repeat). The Keystone example is not changed; the evaluation briefs show the new vocabulary instead.

## 6. WS4: ideation routes and the obviousness probe

### 6.1 Routes

Seven routes, each a short slug: `object` (the thing itself), `abstraction` (the thing reduced past recognition), `letterform` (a letter of the name), `negative-space` (a second figure in the counter or gap), `type-quirk` (the wordmark with one or two owned moves), `system` (a repeated element or a rule that makes the mark), `metaphor-2` (two steps from the one idea, not the obvious object). `object` is the literal route; the other six are non-literal.

Rules, in SKILL.md's concepts phase and craft.md's checklist:

- Every line in `concepts/ideas.md` is tagged with its route; the twelve to twenty ideas cover at least five routes.
- The five to eight directions cover at least three routes, and at least one survivor on the concept sheet is non-literal.
- `Scorecard` gains `route` (required, one of the seven). `sheet concepts` refuses when every survivor's route is `object`, with the message naming the rule.

### 6.2 The obviousness probe

Before building a direction, the designer runs an image search for "<motif> logo" (the construction's plain noun, such as "arch keystone logo") and counts, among the first twenty image results, those that show the same construction. `Scorecard` gains `probe: {"query": str, "hits": int (0 to 20), "date": str}` (required). The validator caps `distinctive`: hits of 3 or more cap it at 3, hits of 8 or more at 2, and a card scoring above its cap is rejected with the cap in the message. The `distinctive` evidence line cites the probe. The critic is not told the probe; its `distinctive` is its own.

The search runs through the web search tools available in the session (Firecrawl image search, or Chrome); the query and date make it reproducible, the count is the designer's reading of the results page.

## 7. WS5: the knock-out by image

`uv run logomaker concept knockout <slug> <NN-slug|final>` writes `knockout/<round>/mark-512.png` (the full symbol, black on white) and `lockup-1024.png` (the horizontal lockup) into the concept folder, and prints their absolute paths. It also creates `knockout.json` beside them if missing, with empty `description_queries`, `image_matches`, `wipo` and `caveat` fields.

The skill then:

1. Opens Google Lens in the Chrome extension, uploads `mark-512.png`, reads the visual matches, and records the ten nearest with URL, owner where visible and a one-line note on what matches (silhouette, construction, both). For survivors this happens before `sheet concepts`, replacing nothing: the description searches stay.
2. For `final/` only, uploads the same image to the WIPO Global Brand Database image search and records the nearest registered marks the same way, plus the class and status shown.
3. Writes the findings into `knockout.json` (validating as `schemas.Knockout`) and the prose into `knockout.md` as today, with the trademark caveat word for word.

Gates: `sheet concepts` refuses a survivor whose `knockout.json` has no `image_matches` entry (an empty list with `searched: true` counts); `brand advance --to package` refuses without `final/knockout.json` carrying both the Lens and the WIPO entries. When the Chrome extension is unavailable, the skill records `skipped: "<reason>"` in the entry and the gate accepts it only with a matching `brand decide` note by the owner. `final/knockout.json` is covered by the package fingerprint, so a changed mark means a new knock-out.

## 8. WS6: the express track

`uv run logomaker brand new "<Name>" --express` sets `track: "express"` in brand.json (`BrandState.track`, default `"full"`). `--express` with `--unnamed` exits 2: express brands are named. `brand set <slug> --track full` upgrades at any gate; a downgrade after `concepts` is refused.

| Phase | Full | Express |
|---|---|---|
| Intake | eleven questions, one per message | five questions (business, onliness, adjectives, surfaces, how the name is written); the rest inferred and shown in the write-back for correction |
| Strategy | nine sections, approved | nine sections, each one to three sentences, written and approved in one message |
| Territories | two or three | one allowed (`TerritoriesSpec` minimum is checked by the gate against the track, not by the model) |
| Concepts | twelve to twenty ideas, five to eight directions, three to five survivors, four revise rounds | eight to twelve ideas, three directions, two survivors, two revise rounds; the critic runs one pass |
| Refinement | up to three refine sheets | one refine sheet |
| Package | unchanged | unchanged |

Every gate, every audit, the critic, the probe and the knock-out still run. `reference/process.md` gains the table; SKILL.md names the express counts beside the full ones. The `pip` evaluation brief runs on the express track in the `final` cycle as its timing check.

## 9. Changes by file

| Area | Files |
|---|---|
| Schemas | `schemas.py`: `CriticCard`, `Knockout`, `Scorecard.reconciled`, `.route`, `.probe` and the cap validator, `BrandState.track`, `Meta.snap` in `kit/concept.py` |
| Kit | `kit/primitives.py` (`brush`, `spline`), `kit/ops.py` (`move_node`, `delete_node`, `cut`, `repeat`), `kit/shape.py` (`nodes`, the Schneider fit in a new `kit/fit.py`), `kit/__init__.py` exports |
| Audit | `audit.py`: `spacing_rhythm`, `free_segments` severity by `snap`, critic and knockout freshness fingerprints |
| CLI | `cli.py`: `sheet critic`, `sheet wordmark`, `concept critic`, `concept knockout`, `brand new --express`, `brand set --track` |
| Sheets | `sheets.py` and `templates/`: the critic sheet, the wordmark sheet, two totals and the preference line on the concept sheet |
| Registry | `registry.py`: gates for the critic, the route rule, the knock-out, the territory minimum by track |
| Skill | `SKILL.md`, `reference/process.md`, `craft.md`, `kit-api.md`, `scorecard.md`, new `critic.md`; `cliches.md` and `fonts.md` stay generated |
| Evals | `docs/evals/`, `scripts/eval_brand.py`, `tests/test_evals.py` |
| Tests | `test_kit_primitives.py`, `test_kit_ops.py`, `test_kit_shape.py`, `test_audit.py`, `test_registry.py`, `test_sheets.py`, `test_concepts_sheet.py`, `test_skill_docs.py`, `test_knowledge.py`, `test_example.py` (unchanged and still green) |

## 10. Testing

- Fast suite: every new op has geometry tests (area, bounds, anchor count, winding, metrics preserved for a `TextShape`), every schema change has a validator test, every gate has a refusal test with the message checked.
- Render suite: the critic sheet and the wordmark sheet render and are non-blank; `spacing_rhythm` is exercised on a real wordmark.
- Knowledge tests: every kit-api.md example and craft.md recipe runs with Fira Code cached.
- The Keystone example: `tests/test_example.py` stays green. Its committed scorecards predate `route`, `probe` and `reconciled`; the schema treats a card without them as valid-but-legacy only inside `docs/examples/`, by a flag the example test sets, never for a brand under `brands/`.
- Evaluation cycles are run by hand with the runner and recorded in `docs/evals/README.md`; they are not CI.

## 11. Sequence

| Step | Workstream | Size | Depends on |
|---|---|---|---|
| 1 | WS1 blind critic | small | nothing |
| 2 | WS2 evaluation set, `baseline` cycle | medium | WS1 |
| 3 | WS3 kit vocabulary and wordmark stage | large | the `baseline` cycle; runs in parallel with 4 and 5 |
| 4 | WS5 knock-out by image | small | the `baseline` cycle |
| 5 | WS4 routes and probe | small | the `baseline` cycle |
| 6 | `kit` and `ideation` cycles | medium | 3, 5 |
| 7 | WS6 express track | small | 1 to 5 |
| 8 | `final` cycle and the README table | small | 7 |

WS3, WS4 and WS5 touch different files and can be split across subagents on Opus. Each workstream is one implementation plan.

## 12. Out of scope

Image-generation APIs, paid search APIs, downloaded logo datasets, dynamic identities, rebrands, and any change to the package's file set.

## 13. Risks

- The Schneider fit is the one piece of real numerical work; if it proves unreliable, `brush` ships with flattened sides and `allow_complex` required, and the fit becomes a follow-up.
- Google Lens and the WIPO search are web pages driven through Chrome, so they can change under the skill; the `skipped` path with an owner decision keeps a run from blocking.
- The critic doubles the agent cost of the concepts phase; the express track's one pass is the mitigation for small ventures.
- Single evaluation runs are noisy; the README table reports direction across cycles, not significance.
