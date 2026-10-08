#!/usr/bin/env python3
"""Run one evaluation brief through the logo skill headless and keep its results (spec 2026-10-08 §4).

    uv run python scripts/eval_brand.py <slug> --cycle <label> [--model opus] [--max-turns 400] [--force]

The brief is docs/evals/<slug>/owner.md, a scripted owner in the Keystone walkthrough's format. The nested `claude`
runs with CLAUDECODE unset, LOGOMAKER_ROOT in a scratch directory and the repo root as its working directory, so the
skill loads and the checkout stays clean. What is worth keeping is copied into docs/evals/<slug>/<cycle>/ with a
report.md; the scratch directory is then deleted.
"""
from __future__ import annotations

import re
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
