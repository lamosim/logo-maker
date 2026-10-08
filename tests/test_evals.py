import importlib.util

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
