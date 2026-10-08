"""Checks on the logo skill's runbook (.claude/skills/logo/SKILL.md), the project's CLAUDE.md and README.md, and its Claude
Code settings.

The first three tests are the floor: the headings, rules and commands each document must carry. The rest pin what the
runbook promises: it quotes the two canonical passages exactly as the reference files word them, the Review Focus
behaviours are written into it, the owner sees a sheet only after the checks and the reading that come before it, it
points at the example brand for each artifact's shape and the command order only, a named venture checks its name once
in strategy, it points at every reference file and only at files that exist, and the settings allow the CLI while still
denying .env.
tests/test_knowledge.py checks every CLI command and option these documents mention; tests/md.py holds the section helpers
both files use.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tests.md import heading_is, section, sections

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude" / "skills" / "logo" / "SKILL.md"
REF = SKILL.parent / "reference"
CANONICAL = "(canonical wording; SKILL.md quotes this)"  # the marker on each canonical passage in the reference files
# What each phase's heading must tell Claude to read: the phases the reference files' own "Read this when:" lines name.
PHASE_READS = {
    "Intake": ("questionnaire.md", "strategy-frameworks.md"),
    "Naming": ("naming.md",),
    "Strategy": ("strategy-frameworks.md", "evidence-rules.md", "logo-types.md", "cliches.md", "cautionary-tales.md", "trends.md",
                 "color.md"),
    "Territories": ("fonts.md", "color.md", "trends.md"),
    "Concepts": ("craft.md", "kit-api.md", "scorecard.md", "evidence-rules.md", "trends.md", "cliches.md", "logo-types.md",
                 "critic.md"),
    "Refinement": ("craft.md", "kit-api.md", "color.md", "fonts.md", "deliverables.md", "cautionary-tales.md", "scorecard.md",
                   "critic.md"),
    "Package": ("deliverables.md", "cautionary-tales.md"),
}


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


def flat(text: str) -> str:
    """`text` with each run of whitespace as one space, so a phrase still matches across a wrapped line."""
    return " ".join(text.split())


def in_order(text: str, *phrases: str) -> None:
    """Assert that each phrase occurs in `text`, after the one before it."""
    at = 0
    for phrase in phrases:
        found = text.find(phrase, at)
        assert found >= 0, f"{phrase!r} is missing, or comes too early"
        at = found + len(phrase)


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
    first = flat(section(text, "First move"))
    assert "Run `uv run logomaker brand list` and read the JSON." in first
    assert "If none exist, say so in one line and ask the first intake question" in first
    assert "Never draw, search the web, or propose names before the brief is confirmed." in first
    # 2. A resumed concepts phase scores every unscored concept before the concept sheet, which refuses one.
    assert ("In the `concepts` phase, score every concept that has no `scorecard.json` from its latest critique before calling "
            "`sheet concepts`, which refuses an unscored concept") in flat(section(text, "Resuming"))
    # 3. A blacklisted motif the owner asks for: the finding shown once, a twist offered, the decision recorded.
    assert ("If the owner asks for a motif on the blacklist, show the finding from `reference/cliches.md` once, offer a twist, and record "
            "their decision with `brand decide`. Do not refuse and do not silently comply.") in flat(section(text, "Conversation rules"))
    # 4. A subagent whose family is not cached fetches it and never substitutes one; its model is set, never inherited.
    recipe = flat(section(text, "Parallel concepts with subagents"))
    assert "Set `model` explicitly to `opus` or cheaper; never leave it to inherit the session's model." in recipe
    assert 'run `uv run logomaker fonts fetch "<Family>"` and never substitute another family.' in recipe


def test_skill_shows_the_owner_only_what_it_checked_and_read():
    text = SKILL.read_text(encoding="utf-8")
    assert "Before the first concept presentation, say the Collins rule 95 preface" in flat(section(text, "Conversation rules"))
    runbook = section(text, "Phase runbook")
    # Concepts: the look-alike search updates `clear`; the sheet is read, the preface said, and only then the sheet opened.
    in_order(flat(section(runbook, "Concepts", level=3)), "search the web by description for look-alikes", "update `clear`",
             "--no-open` and read `sheets/concepts.png`", "Then say the Collins rule 95 preface", "open the sheet for the owner")
    # Refinement: the critique is read, the unintended readings and the knock-out done; only then is the sheet read and opened.
    in_order(flat(section(runbook, "Refinement", level=3)), "reading `final/renders/round-N/critique.png`", "Unintended readings:",
             "Knock-out:", "Only then present the round: `uv run logomaker sheet refine <slug> --no-open`", "read `sheets/refine-N.png`",
             "open the sheet for the owner")


def test_skill_points_at_the_example_brand_for_shape_and_order_only():
    first = flat(section(SKILL.read_text(encoding="utf-8"), "First move"))
    assert ("The example brand in `docs/examples/keystone/` (its `WALKTHROUGH.md` and the artifacts beside it) is the reference for "
            "each artifact's shape and for the order of the commands, never for design ideas; never edit it.") in first
    assert (ROOT / "docs" / "examples" / "keystone" / "WALKTHROUGH.md").is_file()


def test_a_named_venture_checks_its_name_once_in_strategy():
    strategy = flat(section(section(SKILL.read_text(encoding="utf-8"), "Phase runbook"), "Strategy", level=3))
    assert ('A named venture has no naming phase, so run `uv run logomaker names check "<Name>"` once and report its domains and '
            'handles to the owner with the trademark caveat') in strategy


def test_each_phase_reads_what_the_reference_files_say():
    text = SKILL.read_text(encoding="utf-8")
    intro = flat(text.split("## First move")[0])
    process = "`reference/process.md` when you start or resume a brand, before every `brand advance` and before showing the owner anything"
    assert process in intro
    headings = [heading for heading, _ in sections(section(text, "Phase runbook"), level=3)]
    for phase, names in PHASE_READS.items():
        heading = next(heading for heading in headings if heading_is(heading, phase))
        missing = [name for name in names if f"`reference/{name}`" not in heading]
        assert not missing, (phase, missing)


def test_skill_points_at_every_reference_file_and_only_at_real_ones():
    named = set(re.findall(r"reference/([\w-]+\.md)", SKILL.read_text(encoding="utf-8")))
    assert named == {path.name for path in REF.glob("*.md")}, sorted(named ^ {path.name for path in REF.glob("*.md")})


def test_settings_allow_the_cli_and_still_deny_env():
    permissions = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]
    assert "Bash(uv run logomaker:*)" in permissions.get("allow", [])
    assert {"Read(./.env)", "Read(./.env.*)"} <= set(permissions["deny"])


def test_skill_pins_the_knockout_by_image():
    text = flat(SKILL.read_text(encoding="utf-8"))
    assert "uv run logomaker concept knockout <slug> <NN-slug>" in text and "Google Lens" in text
    assert "uv run logomaker concept knockout <slug> final" in text and "WIPO Global Brand Database" in text
    assert "knock-out skipped:" in text
    naming = (REF / "naming.md").read_text(encoding="utf-8")
    assert "## Knock-out by image" in naming and "lens.google.com" in naming and "branddb.wipo.int" in naming
