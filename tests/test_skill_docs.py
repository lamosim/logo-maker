"""Checks on the logo skill's runbook (.claude/skills/logo/SKILL.md), the project's CLAUDE.md and README.md, and its Claude
Code settings.

The first three tests are the floor: the headings, rules and commands each document must carry. The rest pin what the
runbook promises: it quotes the two canonical passages exactly as the reference files word them, the Review Focus
behaviours are written into it, it points at every reference file and only at files that exist, and the settings allow
the CLI while still denying .env. tests/test_knowledge.py checks every CLI command and option these documents mention.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude" / "skills" / "logo" / "SKILL.md"
REF = SKILL.parent / "reference"
CANONICAL = "(canonical wording; SKILL.md quotes this)"  # the marker on each canonical passage in the reference files


def test_skill_frontmatter_and_sections():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: logo\n")
    for heading in ("## First move", "## Phase runbook", "## Conversation rules", "## Reading renders", "## Writing concept modules",
                    "## Parallel concepts with subagents", "## Resuming", "## When the CLI fails", "## Done checklist"):
        assert heading in text, heading
    for rule in ("one question", "Collins", "blend", "represents", "knock-out only, not legal clearance", "logomaker fonts fetch",
                 "scorecard.json"):
        assert rule in text, rule
    for cmd in ("brand list", "brand new", "brand advance", "names check", "sheet territories", "concept run", "sheet concepts",
                "sheet refine", "package build", "package verify"):
        assert f"logomaker {cmd}" in text, cmd


def test_claude_md_routes_and_rules():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for heading in ("## Routing", "## Rules", "## Where things live", "## Tests"):
        assert heading in text
    assert "`logo` skill" in text and "playwright install" in text and ".env" in text and "300000" in text


def test_readme_mentions_setup():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "uv run logomaker setup --check" in text and "brands/<slug>" in text


def section(text: str, heading: str) -> str:
    """The body of the level-two section `## <heading>`, up to the next level-two heading outside a fenced block."""
    body: list[str] | None = None
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            if body is not None:
                break
            if line[3:].strip() == heading:
                body = []
        elif body is not None:
            body.append(line)
    assert body is not None, f"no section {heading!r}"
    return "\n".join(body)


def items(body: str) -> list[str]:
    """The list items and paragraphs of a section body, each on one line: an indented or wrapped line (a quotation inside
    an item, say) joins the item above it; a blank line or a new bullet starts the next."""
    out: list[str] = [""]
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or re.match(r"(?:[-*]|\d+\.) ", stripped):
            out.append(stripped)
        else:
            out[-1] = f"{out[-1]} {stripped}".strip()
    return [item for item in out if item]


def canonical(name: str) -> str:
    """The passage reference file `name` marks as canonical: the first double-quoted text after the marker."""
    text = (REF / name).read_text(encoding="utf-8")
    assert CANONICAL in text, f"{name} marks no canonical passage"
    return re.search(r'"([^"]+)"', text.split(CANONICAL, 1)[1]).group(1)


def quotations(text: str, passage: str) -> list[str]:
    """Each double-quoted text in `text` that opens with `passage`'s first three words: every place `text` quotes it."""
    opening = " ".join(passage.split()[:3])
    return re.findall(rf'"({re.escape(opening)}[^"]*)"', text)


def test_skill_quotes_the_canonical_passages_word_for_word():
    text = SKILL.read_text(encoding="utf-8")
    for name, passage in (("process.md", "the Collins rule 95 preface"), ("naming.md", "the trademark caveat")):
        wording = canonical(name)
        quoted = quotations(text, wording)
        assert quoted, f"SKILL.md does not quote {passage} from reference/{name}"
        for quote in quoted:
            assert quote == wording, passage


def test_skill_pins_the_review_focus_behaviours():
    text = SKILL.read_text(encoding="utf-8")
    # 1. A first session lists the brands, asks the first intake question, and does nothing else before the brief.
    first = section(text, "First move")
    assert "`uv run logomaker brand list`" in first and "first intake question" in first
    assert re.search(r"Never draw, search the web,? or propose names before the brief is confirmed", first)
    # 2. A resumed concepts phase scores every unscored concept before the concept sheet, which refuses one.
    unscored = next(item for item in items(section(text, "Resuming")) if "`scorecard.json`" in item)
    assert re.search(r"\bscore\b.*\bbefore\b.*sheet concepts", unscored), unscored
    # 3. A blacklisted motif the owner asks for: the finding shown once, a twist offered, the decision recorded.
    motif = next(item for item in items(section(text, "Conversation rules")) if "blacklist" in item)
    for words in ("`reference/cliches.md`", "once", "twist", "brand decide", "refuse", "silently"):
        assert words in motif, (words, motif)
    # 4. A subagent whose family is not cached fetches it, never substitutes one; its model is set, not inherited.
    recipe = section(text, "Parallel concepts with subagents")
    assert "logomaker fonts fetch" in recipe and "never substitute" in recipe and "`model`" in recipe


def test_skill_points_at_every_reference_file_and_only_at_real_ones():
    named = set(re.findall(r"reference/([\w-]+\.md)", SKILL.read_text(encoding="utf-8")))
    assert named == {path.name for path in REF.glob("*.md")}, sorted(named ^ {path.name for path in REF.glob("*.md")})


def test_settings_allow_the_cli_and_still_deny_env():
    permissions = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]
    assert "Bash(uv run logomaker:*)" in permissions.get("allow", [])
    assert {"Read(./.env)", "Read(./.env.*)"} <= set(permissions["deny"])
