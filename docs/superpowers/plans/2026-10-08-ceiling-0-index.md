# Raising the Ceiling: the six plans

Spec: `docs/superpowers/specs/2026-10-08-raising-the-ceiling-design.md`. One plan per workstream, each self-contained: an executor reads the spec and its plan, nothing else.

| # | Plan | Size | Runs after | Can run beside |
|---|---|---|---|---|
| 1 | `2026-10-08-ceiling-1-blind-critic.md` | small | nothing | nothing (it fixes the interfaces the rest use) |
| 2 | `2026-10-08-ceiling-2-evaluation-set.md` | medium | 1 | nothing; its Task 4 is the `baseline` cycle, run by hand |
| 3 | `2026-10-08-ceiling-3-kit-vocabulary.md` | large | 2 (the baseline) | 4, 5 |
| 4 | `2026-10-08-ceiling-4-routes-and-probe.md` | small | 2 (the baseline) | 3, 5 |
| 5 | `2026-10-08-ceiling-5-image-knockout.md` | small | 2 (the baseline) | 3, 4 |
| 6 | `2026-10-08-ceiling-6-express-track.md` | small | 3, 4, 5 | nothing; its Task 4 is the `final` cycle |

## Running them with Opus subagents

- Each task goes to a fresh subagent with `model: "opus"` set explicitly (never inherited), the plan path, the task number, and the instruction to follow `superpowers:subagent-driven-development`: write the failing test, run it, implement, run it, commit. A fresh reviewer checks each task before the next starts.
- Plans 3, 4 and 5 touch different files (`kit/`, `schemas.py` and `sheets.py` for the route rule, `knockout.py` and the gates). Run them in separate worktrees (`superpowers:using-git-worktrees`) and merge in the order 5, 4, 3, since 3 is the largest and the merge of 4 and 5 into `registry.py` and `sheets.py` is small. The three shared files are `schemas.py`, `registry.py`, `sheets.py`, `conftest.py` and `test_concepts_sheet.py`; expect to resolve conflicts there by keeping both sides.
- The evaluation cycles (Plan 2 Task 4, the `kit` and `ideation` cycles at the end of Plans 3 and 4, Plan 6 Task 4) run `claude -p` on Opus for thirty to sixty minutes per brief. They are run by hand from the session, not by a subagent, and their results are committed under `docs/evals/`.
- After every plan: `uv run pytest -m "not render and not live" -q`, `uv run pytest -m render -q`, `uv run ruff check src tests scripts`, and `tests/test_example.py` green.
