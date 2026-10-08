# Evaluation set

Three scripted owners, each hard where the Keystone example was easy (spec 2026-10-08 §4): `orvane` (a coined name with no metaphor), `clear-ledger` (two category cues in a blacklisted category) and `pip` (a character and a three-letter wordmark). Each `owner.md` has the thirteen answers in the walkthrough's order and the conservative option for everything else.

The three briefs are frozen as run: later cycles use them unchanged, so the results compare. One known departure from the spec: `orvane`'s answer 12 picks the quieter territory, where the spec says the warmer; it stays as run.

## Running a cycle

One run per brief, by hand, never in CI:

    uv run python scripts/eval_brand.py orvane --cycle baseline
    uv run python scripts/eval_brand.py clear-ledger --cycle baseline
    uv run python scripts/eval_brand.py pip --cycle baseline

The runner starts a nested `claude -p` on Opus with the skill loaded, `LOGOMAKER_ROOT` in a scratch directory, permissions skipped and `--strict-mcp-config` (no MCP server loads; the skill uses no MCP tool). It copies these files under `docs/evals/<slug>/<cycle>/`: `brand.json`, `sheets/concepts.png`, `sheets/critic-*.png`, `concepts/*/scorecard.json`, `concepts/*/critic.json`, `final/scorecard.json`, `final/critic.json`, the last refinement round's `final/critique.png`, `package/brand-sheet.pdf` and `package/verify.json`. Beside them it writes `report.md`, `run.json` (the model and the run's start and finish) and the transcript `run.jsonl`, which stays in the cycle folder and is gitignored; it then deletes the scratch directory. A run takes about 10 to 15 minutes on Opus.

The baseline ran the three briefs in parallel; run later cycles the same way so the minutes compare. The baseline also ran before `--strict-mcp-config` was added; since the skill uses no MCP tool, that does not change its results.

`--report-only` rewrites a cycle's `report.md` from its folder and `run.jsonl` without running anything:

    uv run python scripts/eval_brand.py orvane --cycle baseline --report-only

Cycles: `baseline` (after the blind critic, before the kit and ideation work), `kit`, `ideation`, `final` (after the express track; `pip` runs with `--express`).

The runner's prompt tells the skill to create the brand with `brand new "<Name>"`; `--express` changes that one sentence to `brand new "<Name>" --express` and nothing else. In the `final` cycle `pip` is created on the express track, as its timing check:

    uv run python scripts/eval_brand.py pip --cycle final --express

## Reading a report

- `turns` sums every result segment of the transcript (background critic subagents wake the session again, and each wake-up ends a segment); `segments` counts them; `result` is `success` or the subtypes that were not; `cost usd` is the last segment's cumulative figure.
- `wall clock minutes` is the run's own start to finish; a cycle without them in `run.json` (the baseline) uses the segments' summed durations, else `brand.json`'s `created` to `updated`.
- Each phase's minutes run from the previous phase's last decision (intake from the start) to its own last decision; the last phase runs to the finish.
- `package verified` reads `package/verify.json`; without it (the baseline), `yes (brand-sheet.pdf present)` stands for a package that built its brand sheet.
- The concepts table's `killed` column comes from each scorecard's `kill` field (a dash when the card has none). The Gates table gives the three gate criteria for the designer and the critic per card, and `final` when it exists.

## Results

A row per brief and cycle. Single runs are noisy: read the direction across cycles, and treat a change under one point on one criterion as no finding. The "Critic distinctive/total (chosen)" columns come from the concept-stage `critic.json` of the chosen concept, not from `final/critic.json` (which the report's `final critic` row gives). "Non-literal survivors" counts the concepts on `sheets/concepts.png` whose scorecard `route` is not `object`, read from the kept `concepts/*/scorecard.json` of the concepts shown on the sheet. Minutes are the report's wall clock.

| Brief | Cycle | Critic `distinctive` (chosen) | Critic total (chosen) | Non-literal survivors | Gate regressions | Minutes |
|---|---|---|---|---|---|---|
| orvane | baseline | 4 | 40 | - | none | 12 |
| clear-ledger | baseline | 3 | 39 | - | none | 13 |
| pip | baseline | 4 | 39 | - | none | 9 |
| orvane | ideation | 4 | 40 | 3 | none | 11 |
| clear-ledger | ideation | 3 | 41 | 3 | none | 12 |
| pip | ideation | 3 | 42 | 2 | none | 14 |

Cycle order as run: `baseline`, then `ideation` (after the routes, the probe and the image knock-out landed), then `kit` (after the kit vocabulary), then `final`. The spec's sequence table named `kit` before `ideation`; the plans ran in the other order on one branch, so `ideation` minus `baseline` measures the routes, probe and knock-out work, and `kit` minus `ideation` measures the kit work. The `ideation` rows ran with `--strict-mcp-config`, in parallel, on claude-opus-5-5 with Claude Code 2.1.294.
| orvane | kit | 4 | 39 | 2 | none | 15 |
| clear-ledger | kit | 3 | 43 | 3 | none | 15 |
| pip | kit | 3 | 38 | 2 | none | 16 |
