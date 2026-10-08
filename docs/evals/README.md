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
| orvane | baseline | 4 | 40 | - | none | 12 |
| clear-ledger | baseline | 3 | 39 | - | none | 13 |
| pip | baseline | 4 | 39 | - | none | 10 |
