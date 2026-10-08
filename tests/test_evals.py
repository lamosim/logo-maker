import importlib.util
import json
from pathlib import Path

import pytest

from tests.conftest import REPO

SCRIPT = REPO / "scripts" / "eval_brand.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("eval_brand", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OWNER = (
    "# Test: owner\n\n## Answers\n\n"
    + "\n".join(f"{i}. Answer {i}." for i in range(1, 14))
    + "\n\n## Conservative answers\n\nTake the quiet option.\n"
)


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
    for rule in ("--no-open", "brand decide", "scripted:", "DONE orvane", "never wait for the owner"):
        assert rule in prompt, rule


BRIEFS = ("orvane", "clear-ledger", "pip")


@pytest.mark.parametrize("slug", BRIEFS)
def test_each_brief_has_thirteen_answers_and_the_conservative_section(slug):
    runner = load_runner()
    text = (runner.EVALS / slug / "owner.md").read_text(encoding="utf-8")
    assert len(runner.answers(text, f"{slug}/owner.md")) == 13
    assert "## Conservative answers" in text
    assert "the critic" in runner.answers(text, f"{slug}/owner.md")[11]  # answer 12 chooses the survivor the critic preferred


def test_readme_lists_every_brief_and_the_cycles():
    text = (REPO / "docs" / "evals" / "README.md").read_text(encoding="utf-8")
    for slug in BRIEFS:
        assert f"`{slug}`" in text
    for cycle in ("baseline", "kit", "ideation", "final"):
        assert cycle in text
    assert "scripts/eval_brand.py" in text


def fake_brand(root: Path, slug: str = "orvane", with_critic: bool = True, phase: str = "done") -> Path:
    brand = root / "brands" / slug
    for sub in ("concepts/01-arc", "concepts/02-dot", "sheets", "final/renders/round-3", "package"):
        (brand / sub).mkdir(parents=True)
    decisions = [{"at": "2026-10-09T10:00:00-04:00", "phase": "intake", "by": "user", "note": "scripted: brief confirmed"},
                 {"at": "2026-10-09T10:05:00-04:00", "phase": "strategy", "by": "user", "note": "scripted: approved"},
                 {"at": "2026-10-09T10:12:00-04:00", "phase": "concepts", "by": "user", "note": "scripted: 01-arc"}]
    (brand / "brand.json").write_text(json.dumps({"slug": slug, "name": "Orvane", "phase": phase, "concept": "01-arc",
                                                  "decisions": decisions, "created": "2026-10-09T09:58:00-04:00",
                                                  "updated": "2026-10-09T10:40:00-04:00"}))
    scores = {c: 4 for c in ("appropriate", "distinctive", "simple", "legible", "adaptable", "timeless", "universal", "clear",
                             "congruent", "system")}
    (brand / "concepts" / "01-arc" / "scorecard.json").write_text(json.dumps({"scores": scores, "route": "abstraction", "kill": False}))
    (brand / "concepts" / "02-dot" / "scorecard.json").write_text(json.dumps({"scores": {**scores, "distinctive": 2}, "route": "object",
                                                                             "kill": True}))
    if with_critic:
        (brand / "concepts" / "01-arc" / "critic.json").write_text(json.dumps({"scores": {**scores, "distinctive": 5}, "sheet": 1,
                                                                                "passes": 2, "fingerprint": "x"}))
    (brand / "sheets" / "concepts.png").write_bytes(b"png")
    (brand / "sheets" / "critic-1.png").write_bytes(b"png")
    (brand / "final" / "renders" / "round-3" / "critique.png").write_bytes(b"png")
    (brand / "final" / "scorecard.json").write_text(json.dumps({"scores": scores}))
    (brand / "final" / "critic.json").write_text(json.dumps({"scores": scores, "sheet": 2, "passes": 2, "fingerprint": "y"}))
    (brand / "package" / "verify.json").write_text(json.dumps({"ok": phase == "done"}))
    (brand / "package" / "brand-sheet.pdf").write_bytes(b"%PDF")
    return brand


def transcript(path: Path, turns: int = 3, compact: bool = False, result: dict | None = None) -> Path:
    """A stream-json transcript; `compact` writes it the way claude does (no spaces), `result` replaces the result event
    ({} leaves it out)."""
    seps = (",", ":") if compact else None
    events = [{"type": "assistant", "message": {"content": []}} for _ in range(turns)]
    end = {"type": "result", "result": "DONE orvane", "num_turns": turns} if result is None else result
    if end:
        events.append(end)
    path.write_text("\n".join(json.dumps(e, separators=seps) for e in events) + "\n")
    return path


def test_report_tables_the_phases_scores_and_outcome(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path)
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "run.jsonl"))
    assert "| model | opus (-, claude code -) |" in text and "| turns | 3 |" in text and "| phase reached | done |" in text
    assert "| 01-arc | abstraction | 40 | 41 (2 passes) | no |" in text  # designer total, critic total, killed
    assert "| 02-dot | object | 38 | - | yes |" in text  # no critic card: a dash, not an error
    assert "| strategy | 5 |" in text  # from the last intake decision to the last strategy decision
    assert "| package verified | yes |" in text


def test_report_on_a_run_that_stopped_early(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path, with_critic=False, phase="concepts")
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "run.jsonl", turns=1))
    assert "| phase reached | concepts |" in text and "| package verified | no |" in text


def test_collect_keeps_the_sheets_cards_and_report_and_refuses_a_second_run_without_force(tmp_path, monkeypatch):
    runner = load_runner()
    monkeypatch.setattr(runner, "EVALS", tmp_path / "evals")
    fake_brand(tmp_path / "scratch")
    folder = runner.collect("orvane", tmp_path / "scratch", "baseline", "opus", transcript(tmp_path / "scratch" / "run.jsonl"))
    assert folder == tmp_path / "evals" / "orvane" / "baseline"
    kept = sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())
    assert kept == ["brand.json", "concepts/01-arc/critic.json", "concepts/01-arc/scorecard.json", "concepts/02-dot/scorecard.json",
                    "final/critic.json", "final/critique.png", "final/scorecard.json", "package/brand-sheet.pdf", "package/verify.json",
                    "report.md", "run.json", "run.jsonl", "sheets/concepts.png", "sheets/critic-1.png"]
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


def test_an_empty_numbered_line_does_not_swallow_the_next_line():
    runner = load_runner()
    text = "1.\n2. two\n" + "\n".join(f"{i}. Answer {i}." for i in range(3, 14)) + "\n"
    # "2. two" must stay answer 2: the empty "1." is not an answer, so the numbering starts at 2.
    with pytest.raises(ValueError, match="owner.md numbers its answers 2, 3, "):
        runner.answers(text, "owner.md")


def test_report_counts_turns_in_a_compact_transcript(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path)
    capped = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 7}
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "a.jsonl", turns=4, compact=True, result=capped))
    assert "| turns | 7 |" in text  # num_turns from the result event wins
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "b.jsonl", turns=4, compact=True, result={}))
    assert "| turns | 4 |" in text and "| result | - |" in text  # no result event: count the assistant events
    (tmp_path / "c.jsonl").write_text("not json\n" + (tmp_path / "b.jsonl").read_text())
    assert "| turns | 4 |" in runner.report("orvane", brand, "opus", tmp_path / "c.jsonl")


def test_report_gives_a_dash_for_a_card_without_scores(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path)
    (brand / "concepts" / "03-cut").mkdir()
    (brand / "concepts" / "03-cut" / "scorecard.json").write_text(json.dumps({"route": "letter"}))
    (brand / "concepts" / "03-cut" / "critic.json").write_text(json.dumps({"passes": 1}))
    assert "| 03-cut | letter | - | - | - |" in runner.report("orvane", brand, "opus", transcript(tmp_path / "run.jsonl"))


def test_minutes_skips_a_malformed_end_and_mixed_timezones():
    runner = load_runner()
    decisions = [{"at": "2026-10-09T10:00:00-04:00", "phase": "intake"}, {"at": "2026-10-09T10:05:00", "phase": "strategy"},
                 {"at": "2026-10-09T10:12:00", "phase": "concepts"}]
    # intake has no start, strategy runs from an aware time to a naive one, concepts ends at a malformed time
    assert runner._minutes(decisions, None, "garbage") == []
    assert runner._minutes(decisions, None, "2026-10-09T10:20:00") == [("concepts", 15)]


def capped_run(code: int, result: dict | None):
    def fake(cmd, **kwargs):
        if result:
            kwargs["stdout"].write(json.dumps({"type": "assistant", "message": {}}, separators=(",", ":")) + "\n")
            kwargs["stdout"].write(json.dumps(result, separators=(",", ":")) + "\n")

        class Done:
            returncode = code
            stderr = "boom\nmax turns\n"
        return Done()
    return fake


def test_run_returns_a_turn_capped_transcript_and_the_report_shows_the_subtype(tmp_path, monkeypatch):
    runner = load_runner()
    capped = {"type": "result", "subtype": "error_max_turns", "is_error": True, "num_turns": 10}
    monkeypatch.setattr(runner.subprocess, "run", capped_run(1, capped))
    path = runner.run("orvane", "prompt", tmp_path, "opus", 10)
    assert path == tmp_path / "run.jsonl"
    text = runner.report("orvane", fake_brand(tmp_path), "opus", path)
    assert "| result | error_max_turns |" in text and "| error | yes |" in text and "| turns | 10 |" in text


def test_run_names_a_missing_claude(tmp_path, monkeypatch):
    runner = load_runner()

    def missing(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(runner.subprocess, "run", missing)
    with pytest.raises(RuntimeError, match="claude not found on PATH"):
        runner.run("orvane", "prompt", tmp_path, "opus", 10)


def test_seed_links_templates_and_assets_into_the_scratch(tmp_path):
    runner = load_runner()
    runner.seed(tmp_path)
    for name in ("templates", "assets"):
        assert (tmp_path / name).is_symlink() and (tmp_path / name).resolve() == (runner.ROOT / name).resolve()
    assert (tmp_path / "assets" / "cliches.json").is_file()


def test_build_prompt_names_the_scratch_root_when_given():
    runner = load_runner()
    prompt = runner.build_prompt("orvane", OWNER, scratch=Path("/tmp/scr"))
    assert "/tmp/scr/brands/orvane/" in prompt and "never write under the repository's own brands/" in prompt
    assert "/tmp/scr" not in runner.build_prompt("orvane", OWNER)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """`main` against a fake repo: EVALS and ROOT under tmp_path, mkdtemp counted, the owner script in place."""
    runner = load_runner()
    repo = tmp_path / "repo"
    for sub in ("templates", "assets", "brands"):
        (repo / sub).mkdir(parents=True)
    monkeypatch.setattr(runner, "ROOT", repo)
    monkeypatch.setattr(runner, "EVALS", tmp_path / "evals")
    (tmp_path / "evals" / "orvane").mkdir(parents=True)
    (tmp_path / "evals" / "orvane" / "owner.md").write_text(OWNER)
    made = []

    def mkdtemp(prefix=""):
        made.append(tmp_path / "scratch")
        (tmp_path / "scratch").mkdir()
        return str(tmp_path / "scratch")

    monkeypatch.setattr(runner.tempfile, "mkdtemp", mkdtemp)

    def no_claude(*args, **kwargs):
        raise AssertionError("a test reached the real claude")

    monkeypatch.setattr(runner, "run", no_claude)  # tests that get past the refusals patch `run` themselves
    monkeypatch.setattr(runner.subprocess, "run", no_claude)
    return runner, tmp_path, made


def test_main_refuses_a_bad_script_or_an_existing_cycle_before_the_scratch(harness):
    runner, tmp, made = harness
    (tmp / "evals" / "orvane" / "owner.md").write_text(OWNER.replace("13. Answer 13.\n", ""))
    with pytest.raises(ValueError, match="12 answers"):
        runner.main(["orvane", "--cycle", "baseline"])
    (tmp / "evals" / "orvane" / "owner.md").write_text(OWNER)
    (tmp / "evals" / "orvane" / "baseline").mkdir()
    assert runner.main(["orvane", "--cycle", "baseline"]) == 1
    assert made == []


def test_main_on_a_failing_run_returns_1_and_leaves_the_evals_alone(harness, monkeypatch, capsys):
    runner, tmp, made = harness

    def failing(*args):
        raise RuntimeError("claude exited 1: no credits")

    monkeypatch.setattr(runner, "run", failing)
    assert runner.main(["orvane", "--cycle", "baseline"]) == 1
    assert not (tmp / "evals" / "orvane" / "baseline").exists() and (tmp / "scratch").exists()
    assert str(tmp / "scratch") in capsys.readouterr().err


def test_main_refuses_a_run_that_wrote_into_the_repository_brands(harness, monkeypatch, capsys):
    runner, tmp, made = harness

    def leaking(slug, prompt, scratch, model, max_turns):
        fake_brand(tmp / "repo")
        return transcript(scratch / "run.jsonl")

    monkeypatch.setattr(runner, "run", leaking)
    assert runner.main(["orvane", "--cycle", "baseline"]) == 1
    err = capsys.readouterr().err
    assert str(tmp / "repo" / "brands" / "orvane") in err and str(tmp / "scratch") in err
    assert (tmp / "scratch").exists() and not (tmp / "evals" / "orvane" / "baseline").exists()


def test_main_seeds_the_scratch_runs_and_prints_the_cycle_folder(harness, monkeypatch, capsys):
    runner, tmp, made = harness
    seen = {}

    def ok(slug, prompt, scratch, model, max_turns):
        seen["links"] = all((scratch / name).is_symlink() for name in ("templates", "assets"))
        seen["prompt"] = prompt
        fake_brand(scratch)
        return transcript(scratch / "run.jsonl")

    monkeypatch.setattr(runner, "run", ok)
    assert runner.main(["orvane", "--cycle", "baseline"]) == 0
    folder = tmp / "evals" / "orvane" / "baseline"
    assert capsys.readouterr().out.strip() == str(folder) and (folder / "report.md").is_file()
    assert seen["links"] and str(tmp / "scratch") in seen["prompt"]
    assert not (tmp / "scratch").exists()


INIT = {"type": "system", "subtype": "init", "model": "claude-opus-5-5", "claude_code_version": "2.1.294"}


def events_file(path: Path, *events: dict) -> Path:
    path.write_text("\n".join(json.dumps(e, separators=(",", ":")) for e in events) + "\n")
    return path


def test_report_sums_the_result_segments_of_a_woken_session(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path)
    capped = {"type": "result", "subtype": "error_max_turns", "is_error": True, "num_turns": 10, "duration_ms": 120000,
              "total_cost_usd": 1.0}
    woken = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 5, "duration_ms": 60000,
             "total_cost_usd": 1.5}
    path = events_file(tmp_path / "run.jsonl", INIT, {"type": "assistant"}, capped, INIT, {"type": "assistant"}, woken)
    text = runner.report("orvane", brand, "opus", path)
    assert "| turns | 15 |" in text and "| segments | 2 |" in text and "| result | error_max_turns |" in text
    assert "| error | yes |" in text and "| cost usd | 1.50 |" in text  # cumulative: the last event's figure
    assert "| wall clock minutes | 3 |" in text  # no run times given: the segments' durations summed
    text = runner.report("orvane", brand, "opus", events_file(tmp_path / "b.jsonl", woken, {**woken, "num_turns": 1}))
    assert "| turns | 6 |" in text and "| result | success |" in text and "| error | no |" in text


def test_report_attributes_each_phase_up_to_its_last_decision_from_explicit_times(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path)
    state = json.loads((brand / "brand.json").read_text())
    state["decisions"] = [{"at": f"2026-10-09T{at}:00-04:00", "phase": phase} for at, phase in
                          (("10:00", "intake"), ("10:05", "strategy"), ("10:08", "strategy"), ("10:12", "concepts"),
                           ("10:20", "concepts"))]
    (brand / "brand.json").write_text(json.dumps(state))
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "run.jsonl"),
                         started="2026-10-09T09:55:00-04:00", finished="2026-10-09T10:30:00-04:00")
    assert "| intake | 5 |" in text and "| strategy | 8 |" in text  # strategy: 10:00 to its last decision at 10:08
    assert "| concepts | 22 |" in text  # the last phase ends at the run's finish
    assert "| wall clock minutes | 35 |" in text and "Run on 2026-10-09T09:55-04:00." in text


def test_report_falls_back_to_the_brand_created_and_updated(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path)
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "run.jsonl"))
    assert "| intake | 2 |" in text and "| concepts | 35 |" in text  # from created at 09:58; to updated at 10:40
    assert "| wall clock minutes | 42 |" in text and "Run on 2026-10-09T09:58-04:00." in text


def test_report_tables_the_gates_and_the_final_critic(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path)
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "run.jsonl"))
    assert "## Gates" in text
    assert ("| card | designer appropriate | designer simple | designer legible | critic appropriate | critic simple "
            "| critic legible | kill |") in text
    assert "| 01-arc | 4 | 4 | 4 | 4 | 4 | 4 | no |" in text
    assert "| 02-dot | 4 | 4 | 4 | - | - | - | yes |" in text
    assert "| final | 4 | 4 | 4 | 4 | 4 | 4 | - |" in text  # the final card has no kill field: a dash
    assert "| final critic | distinctive 4, total 40 (2 passes) |" in text
    scores = json.loads((brand / "final" / "scorecard.json").read_text())["scores"]
    (brand / "final" / "critic.json").write_text(json.dumps({"scores": {**scores, "distinctive": 3}, "passes": 1}))
    assert "| final critic | distinctive 3, total 39 (1 pass) |" in runner.report("orvane", brand, "opus", tmp_path / "run.jsonl")


def test_report_without_final_cards_has_no_final_rows(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path, with_critic=False, phase="concepts")
    for name in ("scorecard.json", "critic.json"):
        (brand / "final" / name).unlink()
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "run.jsonl"))
    assert "| final |" not in text and "| final critic |" not in text


def test_package_verified_falls_back_to_the_brand_sheet(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path)
    (brand / "package" / "verify.json").unlink()
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "run.jsonl"))
    assert "| package verified | yes (brand-sheet.pdf present) |" in text
    (brand / "package" / "brand-sheet.pdf").unlink()
    assert "| package verified | no |" in runner.report("orvane", brand, "opus", tmp_path / "run.jsonl")


def test_report_names_the_model_and_claude_code_version(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path)
    path = events_file(tmp_path / "run.jsonl", INIT, {"type": "result", "subtype": "success", "num_turns": 1})
    assert "| model | opus (claude-opus-5-5, claude code 2.1.294) |" in runner.report("orvane", brand, "opus", path)
    assert "| model | opus (-, claude code -) |" in runner.report("orvane", brand, "opus", transcript(tmp_path / "b.jsonl"))


def test_run_starts_claude_with_the_isolated_environment_and_pinned_flags(tmp_path, monkeypatch):
    runner = load_runner()
    seen = {}

    def fake(cmd, **kwargs):
        seen["cmd"], seen["kwargs"] = cmd, kwargs

        class Done:
            returncode = 0
            stderr = ""
        return Done()

    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setattr(runner.subprocess, "run", fake)
    runner.run("orvane", "the prompt", tmp_path, "opus", 77)
    cmd, kwargs = seen["cmd"], seen["kwargs"]
    env = kwargs["env"]
    assert "CLAUDECODE" not in env and env["LOGOMAKER_ROOT"] == str(tmp_path) and env["LOGOMAKER_NO_OPEN"] == "1"
    assert kwargs["cwd"] == runner.ROOT
    assert cmd[:3] == ["claude", "-p", "the prompt"]
    for flag, value in (("--model", "opus"), ("--max-turns", "77"), ("--output-format", "stream-json"), ("--add-dir", str(tmp_path))):
        assert cmd[cmd.index(flag) + 1] == value, flag
    assert "--strict-mcp-config" in cmd


def test_main_refuses_when_the_repository_already_has_the_brand(harness):
    runner, tmp, made = harness
    (tmp / "repo" / "brands" / "orvane").mkdir()
    assert runner.main(["orvane", "--cycle", "baseline"]) == 1 and made == []


def test_main_records_the_run_times_for_the_report(harness, monkeypatch):
    runner, tmp, made = harness

    def ok(slug, prompt, scratch, model, max_turns):
        fake_brand(scratch)
        return transcript(scratch / "run.jsonl")

    monkeypatch.setattr(runner, "run", ok)
    assert runner.main(["orvane", "--cycle", "baseline"]) == 0
    folder = tmp / "evals" / "orvane" / "baseline"
    times = json.loads((folder / "run.json").read_text())
    started, finished = (runner.datetime.fromisoformat(times[k]) for k in ("started", "finished"))
    assert started.tzinfo is not None and started <= finished and times["model"] == "opus"
    assert f"Run on {started.isoformat(timespec='minutes')}." in (folder / "report.md").read_text()


def test_main_report_only_rewrites_the_report_from_the_cycle_folder(harness, capsys):
    runner, tmp, made = harness
    folder = tmp / "evals" / "orvane" / "baseline"
    fake_brand(tmp / "kept").rename(folder)
    (folder / "report.md").write_text("stale\n")
    transcript(folder / "run.jsonl", turns=4)
    assert runner.main(["orvane", "--cycle", "baseline", "--report-only"]) == 0
    text = (folder / "report.md").read_text()
    assert "| turns | 4 |" in text and "## Gates" in text and "Run on 2026-10-09T09:58-04:00." in text
    assert capsys.readouterr().out.strip() == str(folder / "report.md") and made == []
    (folder / "run.json").write_text(json.dumps({"model": "sonnet", "started": "2026-10-09T09:50:00-04:00",
                                                 "finished": "2026-10-09T10:50:00-04:00"}))
    assert runner.main(["orvane", "--cycle", "baseline", "--report-only"]) == 0
    text = (folder / "report.md").read_text()
    assert "| model | sonnet (-, claude code -) |" in text and "| wall clock minutes | 60 |" in text
    assert runner.main(["orvane", "--cycle", "kit", "--report-only"]) == 1  # no such cycle folder
