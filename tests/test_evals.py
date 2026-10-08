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
    assert "the critic" in text  # answer 12 chooses the survivor the critic preferred


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
                                                  "decisions": decisions, "updated": "2026-10-09T10:40:00-04:00"}))
    scores = {c: 4 for c in ("appropriate", "distinctive", "simple", "legible", "adaptable", "timeless", "universal", "clear",
                             "congruent", "system")}
    (brand / "concepts" / "01-arc" / "scorecard.json").write_text(json.dumps({"scores": scores, "route": "abstraction"}))
    (brand / "concepts" / "02-dot" / "scorecard.json").write_text(json.dumps({"scores": {**scores, "distinctive": 2}, "route": "object"}))
    if with_critic:
        (brand / "concepts" / "01-arc" / "critic.json").write_text(json.dumps({"scores": {**scores, "distinctive": 5}, "sheet": 1,
                                                                                "passes": 2, "fingerprint": "x"}))
    (brand / "sheets" / "concepts.png").write_bytes(b"png")
    (brand / "sheets" / "critic-1.png").write_bytes(b"png")
    (brand / "final" / "renders" / "round-3" / "critique.png").write_bytes(b"png")
    (brand / "package" / "verify.json").write_text(json.dumps({"ok": phase == "done"}))
    (brand / "package" / "brand-sheet.pdf").write_bytes(b"%PDF")
    return brand


def transcript(path: Path, turns: int = 3) -> Path:
    lines = [json.dumps({"type": "assistant", "message": {"content": []}}) for _ in range(turns)]
    lines.append(json.dumps({"type": "result", "result": "DONE orvane", "num_turns": turns}))
    path.write_text("\n".join(lines) + "\n")
    return path


def test_report_tables_the_phases_scores_and_outcome(tmp_path):
    runner = load_runner()
    brand = fake_brand(tmp_path)
    text = runner.report("orvane", brand, "opus", transcript(tmp_path / "run.jsonl"))
    assert "| model | opus |" in text and "| turns | 3 |" in text and "| phase reached | done |" in text
    assert "| 01-arc | abstraction | 40 | 41 (2 passes) |" in text  # designer total, critic total
    assert "| 02-dot | object | 38 | - |" in text  # no critic card: a dash, not an error
    assert "| strategy | 7 |" in text  # minutes from the first strategy decision to the first concepts decision
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
                    "final/critique.png", "package/brand-sheet.pdf", "report.md", "run.jsonl", "sheets/concepts.png", "sheets/critic-1.png"]
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
