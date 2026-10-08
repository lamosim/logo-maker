#!/usr/bin/env python3
"""Run one evaluation brief through the logo skill headless and keep its results (spec 2026-10-08 §4).

    uv run python scripts/eval_brand.py <slug> --cycle <label> [--model opus] [--max-turns 400] [--force]
    uv run python scripts/eval_brand.py <slug> --cycle <label> --report-only

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

from logomaker.schemas import GATE

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
    """The transcript's JSON events; a line that does not parse is skipped, a missing transcript has none."""
    events = []
    if not transcript.is_file():
        return events
    for line in transcript.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _results(events: list[dict]) -> list[dict]:
    """Every result event, in order: a session that background subagents wake again ends one segment per wake-up."""
    return [e for e in events if e.get("type") == "result"]


def run(slug: str, prompt: str, scratch: Path, model: str, max_turns: int) -> Path:
    """Start the nested claude and return the JSONL transcript it wrote. RuntimeError when claude is missing, or when it
    exits non-zero without a result event (with the exit code and the last stderr line)."""
    transcript = scratch / "run.jsonl"
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    env.update({"LOGOMAKER_ROOT": str(scratch), "LOGOMAKER_NO_OPEN": "1"})
    # --strict-mcp-config with no --mcp-config loads no MCP server: the skill uses none, and the owner's would vary runs.
    cmd = ["claude", "-p", prompt, "--model", model, "--max-turns", str(max_turns), "--output-format", "stream-json", "--verbose",
           "--dangerously-skip-permissions", "--strict-mcp-config", "--add-dir", str(scratch)]
    try:
        with transcript.open("w", encoding="utf-8") as out:
            done = subprocess.run(cmd, cwd=ROOT, env=env, stdout=out, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as err:
        raise RuntimeError("claude not found on PATH") from err
    # A run that ended with a result event (turn cap, error) still gets collected and reported.
    if done.returncode != 0 and not _results(_events(transcript)):
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


def _span(start: datetime | None, end: datetime | None) -> int | None:
    """Whole minutes from `start` to `end`; None when either is missing or they do not compare (naive against aware)."""
    try:
        return round((end - start).total_seconds() / 60)
    except TypeError:
        return None


def _minutes(decisions: list[dict], started: str | None, finished: str | None) -> list[tuple[str, int]]:
    """Minutes per phase, in PHASES order: a phase's first decision is usually its approval at its end, so each phase runs
    from the previous phase's last decision (intake from `started`) to its own last decision, and the last phase to
    `finished`. A phase whose start or end is missing, malformed or not comparable is left out."""
    last: dict[str, datetime] = {}
    for d in decisions:
        when = _when(d.get("at"))
        if d.get("phase") in PHASES and when:
            last[d["phase"]] = when
    ordered = [(phase, last[phase]) for phase in PHASES if phase in last]
    out = []
    start = _when(started)
    for i, (phase, end) in enumerate(ordered):
        span = _span(start, end if i + 1 < len(ordered) else _when(finished))
        if span is not None:
            out.append((phase, span))
        start = end
    return out


def _passes(card: dict) -> str:
    n = card.get("passes", "?")
    return f"{n} pass" if n == 1 else f"{n} passes"


def _gate_row(name: str, card: dict, critic: dict) -> str:
    designer = [str(card.get("scores", {}).get(c, "-")) for c in GATE]
    blind = [str(critic.get("scores", {}).get(c, "-")) for c in GATE]
    kill = {True: "yes", False: "no"}.get(card.get("kill"), "-")
    return f"| {name} | {' | '.join(designer + blind)} | {kill} |"


def _outcome(events: list[dict]) -> dict:
    """The run's figures across its result segments: turns summed (assistant events counted when there is no result),
    the subtypes that are not success, an error when any segment had one, the cumulative cost from the last event, the
    segments' durations summed, and the init event's model and Claude Code version."""
    results = _results(events)
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    failed = [r.get("subtype") or "?" for r in results if r.get("subtype") != "success"]
    cost = results[-1].get("total_cost_usd") if results else None
    durations = [r["duration_ms"] for r in results if isinstance(r.get("duration_ms"), int | float)]
    return {"turns": sum(r.get("num_turns", 0) for r in results) if results else sum(1 for e in events if e.get("type") == "assistant"),
            "segments": len(results), "result": (", ".join(failed) or "success") if results else "-",
            "error": "yes" if any(r.get("is_error") for r in results) else "no",
            "cost": f"{cost:.2f}" if isinstance(cost, int | float) else "-",
            "duration_minutes": round(sum(durations) / 60000) if durations else None,
            "model": init.get("model") or "-", "version": init.get("claude_code_version") or "-"}


def report(slug: str, brand: Path, model: str, transcript: Path, *, started: str | None = None,
           finished: str | None = None) -> str:
    """The cycle's report.md. `started` and `finished` are the run's own times (aware ISO); without them the phases run
    from brand.json's `created` to its `updated`, and the wall clock is the segments' summed durations, else that span."""
    state = _read_json(brand / "brand.json") or {}
    run = _outcome(_events(transcript))
    start, end = started or state.get("created"), finished or state.get("updated")
    if started and finished:
        wall = _span(_when(started), _when(finished))
    else:
        wall = run["duration_minutes"] if run["duration_minutes"] is not None else _span(_when(start), _when(end))
    verify = _read_json(brand / "package" / "verify.json")
    if verify is not None:
        verified = "yes" if verify.get("ok") else "no"
    else:
        verified = "yes (brand-sheet.pdf present)" if (brand / "package" / "brand-sheet.pdf").is_file() else "no"
    began = _when(start)
    lines = [f"# {slug}: evaluation run", "", f"Run on {began.isoformat(timespec='minutes') if began else 'an unknown date'}.", "",
             "| | |", "|---|---|", f"| model | {model} ({run['model']}, claude code {run['version']}) |",
             f"| turns | {run['turns']} |", f"| segments | {run['segments']} |", f"| result | {run['result']} |",
             f"| error | {run['error']} |", f"| cost usd | {run['cost']} |",
             f"| wall clock minutes | {wall if wall is not None else '-'} |", f"| phase reached | {state.get('phase', '?')} |",
             f"| chosen concept | {state.get('concept') or '-'} |", f"| package verified | {verified} |"]
    final_card = _read_json(brand / "final" / "scorecard.json")
    final_critic = _read_json(brand / "final" / "critic.json")
    if final_critic and final_critic.get("scores"):
        scores = final_critic["scores"]
        lines.append(f"| final critic | distinctive {scores.get('distinctive', '-')}, total {sum(scores.values())} "
                     f"({_passes(final_critic)}) |")
    lines += ["", "## Minutes per phase", "", "| phase | minutes |", "|---|---|"]
    lines += [f"| {phase} | {minutes} |" for phase, minutes in _minutes(state.get("decisions", []), start, end)]
    lines += ["", "## Concepts", "", "| concept | route | designer | critic | killed |", "|---|---|---|---|---|"]
    gates = []
    for folder in sorted(p for p in (brand / "concepts").glob("*") if p.is_dir()):
        card = _read_json(folder / "scorecard.json")
        if not card:
            continue
        critic = _read_json(folder / "critic.json") or {}
        designer = sum(card["scores"].values()) if card.get("scores") else "-"
        critic_cell = f"{sum(critic['scores'].values())} ({_passes(critic)})" if critic.get("scores") else "-"
        killed = {True: "yes", False: "no"}.get(card.get("kill"), "-")
        lines.append(f"| {folder.name} | {card.get('route') or '-'} | {designer} | {critic_cell} | {killed} |")
        gates.append(_gate_row(folder.name, card, critic))
    if final_card or final_critic:
        gates.append(_gate_row("final", final_card or {}, final_critic or {}))
    header = [f"designer {c}" for c in GATE] + [f"critic {c}" for c in GATE]
    lines += ["", "## Gates", "", f"| card | {' | '.join(header)} | kill |", "|---" * (len(header) + 2) + "|", *gates]
    return "\n".join(lines) + "\n"


KEEP_GLOBS = ("sheets/concepts.png", "sheets/critic-*.png", "concepts/*/scorecard.json", "concepts/*/critic.json",
              "final/scorecard.json", "final/critic.json",
              "package/brand-sheet.pdf", "package/verify.json", "brand.json")


def collect(slug: str, scratch: Path, cycle: str, model: str, transcript: Path, force: bool = False, *,
            started: str | None = None, finished: str | None = None) -> Path:
    """Copy the kept artifacts, the report and run.json (the model and the run's times, which --report-only reads back)
    into docs/evals/<slug>/<cycle>/ and delete `scratch`. An existing cycle folder is a FileExistsError unless `force`."""
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
    (folder / "report.md").write_text(report(slug, brand, model, transcript, started=started, finished=finished), encoding="utf-8")
    (folder / "run.json").write_text(json.dumps({"model": model, "started": started, "finished": finished}, indent=2) + "\n",
                                     encoding="utf-8")
    shutil.copy2(transcript, folder / "run.jsonl")
    shutil.rmtree(scratch)
    return folder


def _now() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def report_only(slug: str, cycle: str, model: str) -> int:
    """Rewrite a cycle's report.md from the kept files and run.jsonl, with the model and times run.json recorded (a cycle
    collected before run.json existed falls back to `model` and to brand.json's times)."""
    folder = EVALS / slug / cycle
    if not (folder / "brand.json").is_file():
        print(f"{folder} holds no brand.json; nothing to report", file=sys.stderr)
        return 1
    meta = _read_json(folder / "run.json") or {}
    text = report(slug, folder, meta.get("model") or model, folder / "run.jsonl", started=meta.get("started"),
                  finished=meta.get("finished"))
    (folder / "report.md").write_text(text, encoding="utf-8")
    print(folder / "report.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug")
    parser.add_argument("--cycle", required=True)
    parser.add_argument("--model", default="opus")
    parser.add_argument("--max-turns", type=int, default=400)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report-only", action="store_true",
                        help="rewrite docs/evals/<slug>/<cycle>/report.md from the cycle folder and its run.jsonl; run nothing")
    args = parser.parse_args(argv)
    if args.report_only:
        return report_only(args.slug, args.cycle, args.model)
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
    started = _now()
    try:
        transcript = run(args.slug, build_prompt(args.slug, script, scratch), scratch, args.model, args.max_turns)
    except RuntimeError as err:
        print(f"{err}; scratch kept at {scratch}", file=sys.stderr)
        return 1
    finished = _now()
    if leak.exists():
        print(f"the run wrote {leak} in the repository instead of the scratch; nothing collected, scratch kept at {scratch}",
              file=sys.stderr)
        return 1
    try:
        folder = collect(args.slug, scratch, args.cycle, args.model, transcript, args.force, started=started, finished=finished)
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
