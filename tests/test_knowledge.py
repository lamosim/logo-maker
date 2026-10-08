"""Structural checks on the logo skill's knowledge base, .claude/skills/logo/reference/.

The skill reads these files phase by phase. The tests keep each one complete (its title, its "Read this when:" line, its
headings, its length and its sources), keep the two generated pages equal to their data, keep every CLI command and option
the skill's documents and the example's WALKTHROUGH.md mention real, in code or in prose, and keep the documented code
honest: kit-api.md's worked examples build and pass the audit (its raster checks too, in the render suite), craft.md's
recipes make what they say, and the JSON blocks validate.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path

import click
import pytest

from logomaker import audit, kit, registry
from logomaker.cli import main as cli_main
from logomaker.color import Tokens, check_tokens
from logomaker.export import ADAPTIVE_RADIUS, MASK_SAFE, PackageBuilder
from logomaker.export_docs import BRAND_SECTIONS, DEFAULT_SECTION, PREFIX_SECTIONS
from logomaker.kit import Composite, Mark, Shape
from logomaker.kit import concept as conceptlib
from logomaker.paths import project
from logomaker.schemas import Brief, MinSizes, Phase, Scorecard
from tests.conftest import REPO
from tests.md import heading_is, headings, section

SKILL = REPO / ".claude" / "skills" / "logo"
REF = SKILL / "reference"
BUILDER = REPO / "scripts" / "build_reference.py"
GENERATED = ("cliches.md", "fonts.md")  # rendered from data by BUILDER, so the data sets their length: the floor applies, not the ceiling
MIN_WORDS, MAX_WORDS = 600, 2000
MAX_WORDS_BY_FILE = {"kit-api.md": 3000}  # the kit's API reference grows a row with every public name

REQUIRED = {
    "process.md": ["Phases and gates", "Artifacts each phase must contain", "Agency rules", "Presentation protocol", "Sources"],
    "evidence-rules.md": ["Twenty rules", "Feature to personality table", "Boundary conditions", "What the evidence does not say",
                          "Sources"],
    "strategy-frameworks.md": ["Onliness and positioning", "Archetypes to visual language", "Aaker personality", "Distinctive assets",
                               "Adjective ladder", "Name to letterform", "Sources"],
    "questionnaire.md": ["Core questions", "Optional questions", "Inference guidance", "Write-back template", "Sources"],
    "logo-types.md": ["Taxonomy", "Decision guide", "App icon behaviour", "Sources"],
    "cliches.md": ["Any category", "By industry", "How to twist a justified motif", "Sources"],
    "craft.md": ["Optical corrections", "Small-size redraw", "Wordmark rules", "Construction checklist", "Kit recipes", "Sources"],
    "scorecard.md": ["Ten criteria", "Scoring rubric", "Gate", "scorecard.json format", "Sources"],
    "trends.md": ["Use", "Use carefully", "Avoid", "The AI-era cliche", "Sources"],
    "cautionary-tales.md": ["Cases", "Rules", "Sources"],
    "naming.md": ["Name types", "Sound symbolism", "Letterform scoring", "Checks", "Trademark caveat", "Sources"],
    "fonts.md": ["Catalogue by category", "Pairing", "Licensing", "Sources"],
    "color.md": ["Hue, saturation and lightness", "Cross-cultural notes", "Thresholds", "Building a palette in OKLCH",
                 "Designing the reverse", "tokens.json format", "Sources"],
    "deliverables.md": ["Package manifest", "Platform specs", "Clear space and minimum sizes", "BRAND.md template", "Sources"],
    "critic.md": ["What the critic sees", "What the critic returns", "Reconciliation", "Dispatch", "Sources"],
    "kit-api.md": ["Concept module contract", "Primitives", "Operations", "Text", "Mark and lockups", "Worked examples", "Sources"],
}
CANONICAL = "(canonical wording; SKILL.md quotes this)"
# The audit warnings each worked example gives, in order: none, but example 4's two from the cut atop Fira Code's t and
# example 5's "Ve" pair, tight by its boxes under the V's diagonal (an optical gap, judged on the wordmark sheet).
EXAMPLE_WARNINGS = [[], [], [], ["near_miss_angles", "near_miss_angles"], ["spacing_rhythm"], []]

COMMANDS = dict(cli_main.commands)  # group (or command) name -> click object
# A CLI mention in code: an optional "logomaker", a group name standing as a word, and the word after it (its command).
MENTION = re.compile(r"(?<![^\s(`\"'])(?:logomaker[ \t]+)?(?P<group>" + "|".join(map(re.escape, COMMANDS)) + r")(?=[\s`\"')]|$)"
                     r"(?:[ \t]+(?P<command>[a-z][\w-]*))?")
# A CLI mention in prose, outside backticks: "logomaker", then a group, then the word after it.
PROSE_MENTION = re.compile(r"(?<![\w.-])logomaker[ \t]+(?P<group>[a-z][\w-]*)(?:[ \t]+(?P<command>[a-z][\w-]*))?")


def read(name: str) -> str:
    return (REF / name).read_text(encoding="utf-8")


def code_blocks(text: str, language: str) -> list[str]:
    return re.findall(rf"^```{language}\n(.*?)^```$", text, re.M | re.S)


def code_units(text: str) -> list[str]:
    """The code in Markdown `text`: each line of a fenced block, and each inline code span outside one. A fenced line
    that ends in a backslash is joined to the lines it continues, as one command; a comment line in a Python block is
    prose about the code and left out."""
    units: list[str] = []
    fence: str | None = None  # the open block's language ("" when it names none); None outside a block
    held = ""  # a backslash-continued command, so far
    for line in text.splitlines():
        if line.startswith("```"):
            if fence is not None and held:
                units.append(held)
            fence, held = (line[3:].strip() if fence is None else None), ""
        elif fence is not None:
            if fence == "python" and line.lstrip().startswith("#"):
                continue
            if line.endswith("\\"):
                held += line[:-1] + " "
            else:
                units.append(held + line)
                held = ""
        else:
            units += re.findall(r"`([^`]+)`", line)
    return units


def prose_lines(text: str) -> list[str]:
    """The prose in Markdown `text`: each line outside a fenced block, with its inline code spans taken out."""
    lines: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced:
            lines.append(re.sub(r"`[^`]*`", " ", line))
    return lines


def cli_problems(text: str) -> list[str]:
    """Each CLI mention in `text` that cli.main lacks. In code, where a mention starts a span or a fenced line or follows
    "logomaker": a group after "logomaker", a `<group> <command>`, or a `--option` written after a command, or after a
    group named without one (up to the next mention), that it does not take. In prose, outside backticks: a
    `logomaker <group> [<command>]` naming a group or command that does not exist."""
    problems: list[str] = []
    for unit in code_units(text):
        for word in re.findall(r"(?<![\w.])logomaker[ \t]+([a-z][\w-]*)", unit):
            if word not in COMMANDS:
                problems.append(f"no group `logomaker {word}` (in `{unit.strip()}`)")
        # A mention starts the span (or the fenced line) or follows "logomaker": a group named further in is an option's
        # value (`--phase package`) or a word in code, so the options after it still belong to the command before it.
        mentions = [m for m in MENTION.finditer(unit) if m[0].startswith("logomaker") or not unit[:m.start()].strip()]
        for i, mention in enumerate(mentions):
            name, word = mention["group"], mention["command"]
            target = COMMANDS[name]
            if isinstance(target, click.Group) and word is not None:  # a group named alone takes only its own options
                if word not in target.commands:
                    problems.append(f"no command `{name} {word}` (in `{unit.strip()}`)")
                    continue
                target = target.commands[word]
            known = {opt for param in target.params for opt in getattr(param, "opts", ()) if opt.startswith("--")} | {"--help"}
            rest = unit[mention.end(): mentions[i + 1].start() if i + 1 < len(mentions) else len(unit)]
            problems += [f"`{target.name}` takes no {opt} (in `{unit.strip()}`)"
                         for opt in re.findall(r"(?<![\w-])--[a-z][\w-]*", rest) if opt not in known]
    for line in prose_lines(text):
        for mention in PROSE_MENTION.finditer(line):
            name, word = mention["group"], mention["command"]
            target = COMMANDS.get(name)
            if target is None:
                problems.append(f"no group `logomaker {name}` (in prose: {line.strip()})")
            elif isinstance(target, click.Group) and word is not None and word not in target.commands:
                problems.append(f"no command `{name} {word}` (in prose: {line.strip()})")
    return problems


def skill_documents() -> list[Path]:
    """Every Markdown file of the logo skill; the project's CLAUDE.md and README.md when they exist; and the example
    brand's WALKTHROUGH.md, which SKILL.md makes the reference for the order of the commands."""
    others = (REPO / "CLAUDE.md", REPO / "README.md", REPO / "docs" / "examples" / "keystone" / "WALKTHROUGH.md")
    return sorted(SKILL.rglob("*.md")) + [path for path in others if path.is_file()]


def last_binding(code: str) -> str:
    """The last name a recipe's top level binds: what the recipe makes."""
    names = [node.id for statement in ast.parse(code).body if isinstance(statement, ast.Assign)
             for target in statement.targets for node in ast.walk(target) if isinstance(node, ast.Name)]
    return names[-1]


def load_builder():
    spec = importlib.util.spec_from_file_location("build_reference", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_fifteen_files_have_their_frame_headings_and_length():
    assert sorted(p.name for p in REF.glob("*.md")) == sorted(REQUIRED)
    for name, required in REQUIRED.items():
        text = read(name)
        lines = [line for line in text.splitlines() if line.strip()]
        assert lines[0].startswith("# ") and re.match(r"Read this when: .+", lines[1]), f"{name}: needs '# Title' then 'Read this when:'"
        assert re.search(r"^Read this when: .+", text, re.M), name
        found = headings(text)
        for heading in required:
            assert any(heading_is(f, heading) for f in found), f"{name}: missing heading {heading!r}"
        assert found[-1] == "Sources" and section(text, "Sources").strip(), f"{name}: must end with a Sources section"
        words = len(text.split())
        assert words >= MIN_WORDS, f"{name}: only {words} words"
        cap = MAX_WORDS_BY_FILE.get(name, MAX_WORDS)
        assert name in GENERATED or words <= cap, f"{name}: {words} words, over {cap}"


def test_heading_match_needs_the_whole_heading():
    assert heading_is("Use", "Use") and heading_is("Use: durable", "Use") and heading_is("Use (low risk)", "Use")
    assert not heading_is("Use carefully", "Use") and not heading_is("Users", "Use")


def test_every_file_tags_its_sources():
    for name in REQUIRED:
        text = read(name)
        tags = re.findall(r"\[(0[1-5]|spec|code)(?:[ :§][^\]]*)?\]", text)
        assert len(tags) >= 3, f"{name}: only {len(tags)} source tags"
        prose = "\n".join(prose_lines(text))  # a list literal in code, such as brush widths [30, 110, 50], is no tag
        stray = [t for t in re.findall(r"\[(\d\d)\b", prose) if t not in ("01", "02", "03", "04", "05")]
        assert not stray, f"{name}: unknown report tags {stray}"


def test_generated_pages_equal_their_renders():
    builder = load_builder()
    cliches = json.loads((REPO / "assets" / "cliches.json").read_text(encoding="utf-8"))
    assert read("cliches.md") == builder.render_cliches(cliches), "cliches.md is stale: run uv run python scripts/build_reference.py"
    catalog = json.loads((REPO / "assets" / "fonts" / "catalog.json").read_text(encoding="utf-8"))
    template = builder.FONTS_TEMPLATE.read_text(encoding="utf-8")
    assert read("fonts.md") == builder.render_fonts(catalog, template), "fonts.md is stale: run uv run python scripts/build_reference.py"


def test_cliches_md_lists_every_industry_alias_and_motif():
    data = json.loads((REPO / "assets" / "cliches.json").read_text(encoding="utf-8"))
    text = read("cliches.md")
    assert all(motif in section(text, "Any category") for motif in data["any"]["motifs"])
    for key, entry in data["industries"].items():
        assert f"### {key}" in text, key
        for term in entry["motifs"] + entry.get("aliases", []) + entry.get("styles", []):
            assert term in text, (key, term)
    assert "trends.md" in text  # the pointer to the AI-era cliché


def test_fonts_md_lists_every_family_under_its_exact_category():
    catalog = json.loads((REPO / "assets" / "fonts" / "catalog.json").read_text(encoding="utf-8"))
    catalogue = section(read("fonts.md"), "Catalogue by category")
    for category in {f["category"] for f in catalog["families"]}:
        assert f'--category "{category}"' in catalogue, category
    for family in catalog["families"]:
        assert family["family"] in catalogue, family["family"]


def test_kit_api_names_every_public_kit_name():
    text = read("kit-api.md")
    missing = [name for name in kit.__all__ if not re.search(rf"`{re.escape(name)}\b", text)]
    assert not missing, f"kit-api.md does not document {missing}"


def audit_worked_examples(project_root: Path, renderer=None) -> list:
    """Each of kit-api.md's worked examples written as a concept of a throwaway brand, built and audited (the raster
    checks only with a `renderer`); the audits, in order, once each has passed with the warnings EXAMPLE_WARNINGS gives."""
    blocks = code_blocks(section(read("kit-api.md"), "Worked examples"), "python")
    assert len(blocks) == 6
    paths = project()
    registry.new_brand(paths, "Examples", slug="examples")
    types, results = [], []
    for i, code in enumerate(blocks, start=1):
        assert len(code.splitlines()) < 40, f"example {i} has {len(code.splitlines())} lines"
        folder = project_root / "brands" / "examples" / "concepts" / f"0{i}-example"
        folder.mkdir()
        (folder / "concept.py").write_text(code, encoding="utf-8")
        module = conceptlib.load_concept(folder)
        outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
        assert {"full-lockup", "small", "favicon"} <= set(outputs), (i, list(outputs))
        result = audit.audit_concept(paths, "examples", folder.name, renderer=renderer)
        assert result.ok, (i, [f.message for f in result.failures])
        assert [f.check for f in result.warnings] == EXAMPLE_WARNINGS[i - 1], (i, [f.message for f in result.warnings])
        types.append(module.meta.logo_type)
        results.append(result)
    assert types == ["lettermark", "pictorial", "abstract", "wordmark", "pictorial", "lettermark"]
    return results


def test_kit_api_worked_examples_build_and_pass_the_audit(project_root):
    assert not any(result.rendered for result in audit_worked_examples(project_root))  # no renderer: no raster checks


@pytest.mark.render
def test_kit_api_worked_examples_pass_the_rendered_audit(project_root, renderer):
    # With a renderer, min_feature and one_colour_merge run too: each size the audit checks (the full symbol when there is
    # one, small and favicon) keeps its thinnest feature, no part merges or splits at its size, and nothing new warns.
    for result in audit_worked_examples(project_root, renderer):
        checked = {"small", "favicon"} | ({"full-symbol"} & set(result.outputs))
        assert result.rendered and {f.data["output"] for f in result.info if f.check == "min_feature"} == checked


def test_craft_recipes_make_what_they_say(project_root):
    blocks = code_blocks(section(read("craft.md"), "Kit recipes"), "python")
    assert len(blocks) >= 5
    for code in blocks:
        namespace: dict = {}
        exec("from logomaker.kit import *\n" + code, namespace)  # noqa: S102 - running the documented recipe is the test
        made = namespace[last_binding(code)]
        assert isinstance(made, (Mark, Composite)) or (isinstance(made, Shape) and not made.is_empty), code


def test_documented_json_validates():
    blocks = code_blocks(section(read("scorecard.md"), "scorecard.json format"), "json")
    cards = [Scorecard.model_validate_json(block) for block in blocks]
    assert any(card.kill for card in cards) and any(not card.kill for card in cards)
    for card in cards:
        assert card.gate_ok == (not card.kill)  # the passing card passes the gate; the killed one, all ten scores kept, does not
    blocks = code_blocks(section(read("color.md"), "tokens.json format"), "json")
    assert len(blocks) == 1
    assert check_tokens(Tokens.model_validate_json(blocks[0])).ok  # it passes `color check` as documented


def test_questionnaire_write_back_lists_every_brief_field():
    template = section(read("questionnaire.md"), "Write-back template")
    missing = [field for field in Brief.model_fields if f"`{field}`" not in template]
    assert not missing, missing
    examples = code_blocks(template, "json")
    assert len(examples) == 1
    Brief.model_validate_json(examples[0])  # the minimal brief.json passes the intake gate's model


def test_canonical_wording_is_the_research_wording():
    research = (REPO / "docs" / "research" / "01-brand-methodology-and-cases.md").read_text(encoding="utf-8")
    preface = re.search(r'then say "(New ideas can be fragile.+?)"', research).group(1)
    protocol = section(read("process.md"), "Presentation protocol")
    assert preface in protocol and CANONICAL in protocol
    caveat = section(read("naming.md"), "Trademark caveat")
    assert "knock-out only, not legal clearance" in caveat and CANONICAL in caveat


def test_process_md_mirrors_the_phases_and_their_checks(project_root):
    text = read("process.md")
    phases = section(text, "Phases and gates")
    for phase in Phase:
        assert f"`{phase.value}`" in phases, phase.value
    # The files the gates ask for, from the phase checks' own messages on a brand with nothing yet but a chosen concept, in
    # the naming phase, whose check runs only then: every file any check can report missing (a concept's own files by
    # name, as process.md lists them under the concepts phase).
    paths = project()
    state = registry.new_brand(paths, "Gates", slug="gates").model_copy(update={"phase": Phase.naming, "concept": "01-idea"})
    messages = " ".join(m for check in registry.PHASE_CHECKS.values() for m in check(paths.brand("gates"), state, True))
    files = {re.sub(r"^(?:concepts/)?01-idea/", "", name) for name in re.findall(r"([\w./-]+\.(?:md|json|py)) is missing", messages)}
    assert files == {"brief.md", "brief.json", "naming.md", "strategy.md", "strategy.json", "territories/territories.json",
                     "concept.py", "audit.json", "scorecard.json", "knockout.json", "final/concept.py", "final/params.json",
                     "final/tokens.json", "final/audit.json", "package/verify.json"}
    artifacts = section(text, "Artifacts each phase must contain")
    for name in sorted(files | {"src/logomaker/schemas.py"}):  # each as a whole path in code, never inside a longer one
        assert f"`{name}`" in artifacts, name


def test_deliverables_md_mirrors_the_package_builder():
    text = read("deliverables.md")
    manifest = section(text, "Package manifest")
    for group in PackageBuilder.GROUPS:
        assert f"`{group}`" in manifest, group
    for readme_section in {*BRAND_SECTIONS.values(), *(name for _, name in PREFIX_SECTIONS), DEFAULT_SECTION}:
        assert readme_section in manifest, readme_section
    platforms = section(text, "Platform specs")
    assert f"{MASK_SAFE} px" in platforms and f"radius {ADAPTIVE_RADIUS}" in platforms
    sizes, minimum = section(text, "Clear space and minimum sizes"), MinSizes()
    for label, px, mm in (("horizontal", minimum.horizontal_px, minimum.horizontal_mm), ("stacked", minimum.stacked_px, minimum.stacked_mm),
                          ("mark", minimum.mark_px, minimum.mark_mm)):
        assert f"{label} {px} px or {mm:g} mm" in sizes, label
    assert f"favicon {minimum.favicon_px} px" in sizes


def test_every_cli_command_and_option_the_documents_mention_exists():
    documents = skill_documents()
    assert len(documents) >= len(REQUIRED) and REPO / "docs" / "examples" / "keystone" / "WALKTHROUGH.md" in documents
    problems = [f"{path.relative_to(REPO)}: {problem}" for path in documents for problem in cli_problems(path.read_text(encoding="utf-8"))]
    assert not problems, "\n".join(problems)


def test_the_cli_check_catches_what_does_not_exist():
    injected = ("Run `uv run logomaker brand frob x`, `brand frob`, `brand set <slug> --min-size 3`, `concept run a b --render` and "
                "`uv run logomaker frob x`; `uv run logomaker brand set <slug> --industry fintech` is real.\n"
                "In prose, run logomaker brand zap first, then logomaker concept run (which exists), then `sheet --wide`.\n"
                "```bash\nuv run logomaker brand set keystone --industry fintech \\\n  --surface \"app icon\" --size 3\n```\n"
                "```python\n# the CLI's `concept frob` is no command, but a comment is prose about the code\nMark(symbol=ring())\n```\n"
                "An option's value is no mention: `uv run logomaker brand decide <slug> --phase package --by user --note \"...\"`.\n")
    problems = cli_problems(injected)
    assert len(problems) == 8, problems
    for expected in ("`brand frob`", "--min-size", "--render", "`logomaker frob`", "`brand zap` (in prose", "`sheet` takes no --wide",
                     "`set` takes no --size"):
        assert any(expected in problem for problem in problems), expected
    assert not any("concept frob" in problem or "--phase package" in problem for problem in problems)
