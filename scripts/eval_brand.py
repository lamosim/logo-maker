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
NUMBERED = re.compile(r"^(\d+)\.[^\S\n]+(.*\S)\s*$", re.M)
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
