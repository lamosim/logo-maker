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


SCRATCH_LINE = """
The project root for this run is {scratch}: every brand file lives under {scratch}/brands/{slug}/ and the CLI prints
those paths; never write under the repository's own brands/ folder.
"""


def build_prompt(slug: str, script: str, scratch: Path | None = None) -> str:
    prompt = PROMPT.format(slug=slug, script=script.strip())
    return prompt + SCRATCH_LINE.format(scratch=scratch, slug=slug) if scratch else prompt


def seed(scratch: Path) -> None:
    """Link the repo's templates/ and assets/ into the scratch root, which the CLI resolves them under; the font cache
    under assets/fonts/*/ is gitignored, so fetches through the link share it."""
    for name in ("templates", "assets"):
        (scratch / name).symlink_to(ROOT / name, target_is_directory=True)


def _events(transcript: Path) -> list[dict]:
    """The transcript's JSON events; a line that does not parse is skipped."""
    events = []
    for line in transcript.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _result(events: list[dict]) -> dict | None:
    return next((e for e in reversed(events) if e.get("type") == "result"), None)


def run(slug: str, prompt: str, scratch: Path, model: str, max_turns: int) -> Path:
    """Start the nested claude and return the JSONL transcript it wrote. RuntimeError when claude is missing, or when it
    exits non-zero without a result event (with the exit code and the last stderr line)."""
    transcript = scratch / "run.jsonl"
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    env.update({"LOGOMAKER_ROOT": str(scratch), "LOGOMAKER_NO_OPEN": "1"})
    cmd = ["claude", "-p", prompt, "--model", model, "--max-turns", str(max_turns), "--output-format", "stream-json", "--verbose",
           "--dangerously-skip-permissions", "--add-dir", str(scratch)]
    try:
        with transcript.open("w", encoding="utf-8") as out:
            done = subprocess.run(cmd, cwd=ROOT, env=env, stdout=out, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as err:
        raise RuntimeError("claude not found on PATH") from err
    # A run that ended with a result event (turn cap, error) still gets collected and reported.
    if done.returncode != 0 and _result(_events(transcript)) is None:
        last = (done.stderr or "").strip().splitlines()
        raise RuntimeError(f"claude exited {done.returncode}: {last[-1] if last else 'no stderr'}")
    return transcript


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _when(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _minutes(decisions: list[dict], updated: str | None) -> list[tuple[str, int]]:
    """Minutes per phase: from the first decision of each phase to the first of the next, the last to `updated`. A phase
    whose end is missing, malformed or not comparable (naive against aware) is left out."""
    starts: dict[str, datetime] = {}
    for d in decisions:
        when = _when(d.get("at"))
        if d.get("phase") in PHASES and d.get("phase") not in starts and when:
            starts[d["phase"]] = when
    ordered = [(phase, starts[phase]) for phase in PHASES if phase in starts]
    out = []
    for i, (phase, start) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else _when(updated)
        try:
            out.append((phase, round((end - start).total_seconds() / 60)))
        except TypeError:
            continue
    return out


def report(slug: str, brand: Path, model: str, transcript: Path) -> str:
    state = _read_json(brand / "brand.json") or {}
    events = _events(transcript)
    result = _result(events) or {}
    turns = result.get("num_turns", sum(1 for e in events if e.get("type") == "assistant"))
    verify = _read_json(brand / "package" / "verify.json") or {}
    lines = [f"# {slug}: evaluation run", "", f"Run on {datetime.now(UTC).astimezone().isoformat(timespec='minutes')}.", "",
             "| | |", "|---|---|", f"| model | {model} |", f"| turns | {turns} |", f"| result | {result.get('subtype') or '-'} |",
             f"| error | {'yes' if result.get('is_error') else 'no'} |", f"| phase reached | {state.get('phase', '?')} |",
             f"| chosen concept | {state.get('concept') or '-'} |", f"| package verified | {'yes' if verify.get('ok') else 'no'} |", "",
             "## Minutes per phase", "", "| phase | minutes |", "|---|---|"]
    lines += [f"| {phase} | {minutes} |" for phase, minutes in _minutes(state.get("decisions", []), state.get("updated"))]
    lines += ["", "## Concepts", "", "| concept | route | designer | critic |", "|---|---|---|---|"]
    for folder in sorted(p for p in (brand / "concepts").glob("*") if p.is_dir()):
        card = _read_json(folder / "scorecard.json")
        if not card:
            continue
        critic = _read_json(folder / "critic.json") or {}
        designer = sum(card["scores"].values()) if card.get("scores") else "-"
        critic_cell = f"{sum(critic['scores'].values())} ({critic.get('passes', '?')} passes)" if critic.get("scores") else "-"
        lines.append(f"| {folder.name} | {card.get('route') or '-'} | {designer} | {critic_cell} |")
    return "\n".join(lines) + "\n"


KEEP_GLOBS = ("sheets/concepts.png", "sheets/critic-*.png", "concepts/*/scorecard.json", "concepts/*/critic.json",
              "final/scorecard.json", "final/critic.json",
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
    folder = EVALS / args.slug / args.cycle
    if folder.exists() and not args.force:  # refuse before the run, not after it
        print(f"{folder} exists; pass --force to replace the {args.cycle} run", file=sys.stderr)
        return 1
    leak = ROOT / "brands" / args.slug
    if leak.exists():
        print(f"{leak} exists; the run could not tell its own files from it", file=sys.stderr)
        return 1
    scratch = Path(tempfile.mkdtemp(prefix=f"logomaker-eval-{args.slug}-"))
    seed(scratch)
    try:
        transcript = run(args.slug, build_prompt(args.slug, script, scratch), scratch, args.model, args.max_turns)
    except RuntimeError as err:
        print(f"{err}; scratch kept at {scratch}", file=sys.stderr)
        return 1
    if leak.exists():
        print(f"the run wrote {leak} in the repository instead of the scratch; nothing collected, scratch kept at {scratch}",
              file=sys.stderr)
        return 1
    try:
        folder = collect(args.slug, scratch, args.cycle, args.model, transcript, args.force)
    except FileExistsError as err:
        print(f"{err}; scratch kept at {scratch}", file=sys.stderr)
        return 1
    except Exception:
        print(f"collection failed; scratch kept at {scratch}", file=sys.stderr)
        raise
    print(folder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
