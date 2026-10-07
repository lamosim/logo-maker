"""Structural checks on the logo skill's knowledge base, .claude/skills/logo/reference/.

The skill reads these files phase by phase. The tests keep each one complete (its title, its "Read this when:" line, its
headings, its length and its sources), keep the two generated pages equal to their data, and keep the documented code
honest: kit-api.md's worked examples build and pass the audit, craft.md's recipes run, and the JSON blocks validate.
"""
from __future__ import annotations

import importlib.util
import json
import re

from logomaker import audit, kit, registry
from logomaker.color import Tokens, check_tokens
from logomaker.export import ADAPTIVE_RADIUS, MASK_SAFE, PackageBuilder
from logomaker.kit import Composite, Mark, Shape
from logomaker.kit import concept as conceptlib
from logomaker.paths import project
from logomaker.schemas import Brief, MinSizes, Phase, Scorecard
from tests.conftest import REPO

REF = REPO / ".claude" / "skills" / "logo" / "reference"
BUILDER = REPO / "scripts" / "build_reference.py"
MIN_WORDS, MAX_WORDS = 600, 2000

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
    "kit-api.md": ["Concept module contract", "Primitives", "Operations", "Text", "Mark and lockups", "Worked examples", "Sources"],
}
CANONICAL = "(canonical wording; SKILL.md quotes this)"


def read(name: str) -> str:
    return (REF / name).read_text(encoding="utf-8")


def sections(text: str) -> list[tuple[str, str]]:
    """Each level-two section as (heading, body). A line inside a fenced code block never starts a section."""
    out: list[tuple[str, str]] = []
    fenced = False
    for line in text.splitlines(keepends=True):
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            out.append((line[3:].strip(), ""))
        elif out:
            out[-1] = (out[-1][0], out[-1][1] + line)
    return out


def headings(text: str) -> list[str]:
    return [heading for heading, _ in sections(text)]


def section(text: str, heading: str) -> str:
    """The body of the first level-two section whose heading starts with `heading`."""
    bodies = [body for found, body in sections(text) if found.startswith(heading)]
    assert bodies, f"no section {heading!r}"
    return bodies[0]


def code_blocks(text: str, language: str) -> list[str]:
    return re.findall(rf"^```{language}\n(.*?)^```$", text, re.M | re.S)


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
            assert any(f.startswith(heading) for f in found), f"{name}: missing heading {heading!r}"
        assert found[-1] == "Sources" and section(text, "Sources").strip(), f"{name}: must end with a Sources section"
        words = len(text.split())
        assert MIN_WORDS <= words <= MAX_WORDS, f"{name}: {words} words"


def test_every_file_tags_its_sources():
    for name in REQUIRED:
        text = read(name)
        tags = re.findall(r"\[(0[1-5]|spec|code)(?:[ :§][^\]]*)?\]", text)
        assert len(tags) >= 3, f"{name}: only {len(tags)} source tags"
        stray = [t for t in re.findall(r"\[(\d\d)\b", text) if t not in ("01", "02", "03", "04", "05")]
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


def test_kit_api_worked_examples_build_and_pass_the_audit(project_root):
    blocks = code_blocks(section(read("kit-api.md"), "Worked examples"), "python")
    assert len(blocks) == 4
    paths = project()
    registry.new_brand(paths, "Examples", slug="examples")
    types = []
    for i, code in enumerate(blocks, start=1):
        assert len(code.splitlines()) < 40, f"example {i} has {len(code.splitlines())} lines"
        folder = project_root / "brands" / "examples" / "concepts" / f"0{i}-example"
        folder.mkdir()
        (folder / "concept.py").write_text(code, encoding="utf-8")
        module = conceptlib.load_concept(folder)
        outputs = conceptlib.build_outputs(conceptlib.build_tiers(module))
        assert {"full-lockup", "small", "favicon"} <= set(outputs), (i, list(outputs))
        result = audit.audit_concept(paths, "examples", folder.name)  # no renderer: the raster checks are skipped
        assert result.ok, (i, [f.message for f in result.failures])
        types.append(module.meta.logo_type)
    assert types == ["lettermark", "pictorial", "abstract", "wordmark"]


def test_craft_recipes_run(project_root):
    blocks = code_blocks(section(read("craft.md"), "Kit recipes"), "python")
    assert len(blocks) >= 5
    for code in blocks:
        namespace: dict = {}
        exec("from logomaker.kit import *\n" + code, namespace)  # noqa: S102 - running the documented recipe is the test
        made = [v for v in namespace.values() if isinstance(v, (Mark, Composite)) or (isinstance(v, Shape) and not v.is_empty)]
        assert made, code


def test_documented_json_validates():
    cards = [json.loads(block) for block in code_blocks(section(read("scorecard.md"), "scorecard.json format"), "json")]
    assert cards and any(card.get("kill") for card in cards)  # a killed card still carries all ten scores
    for card in cards:
        Scorecard.model_validate(card)
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


def test_process_md_mirrors_the_phases_and_their_checks():
    text = read("process.md")
    phases = section(text, "Phases and gates")
    for phase in Phase:
        assert f"`{phase.value}`" in phases, phase.value
    artifacts = section(text, "Artifacts each phase must contain")
    for name in ("brief.md", "brief.json", "naming.md", "strategy.md", "strategy.json", "territories/territories.json",
                 "scorecard.json", "audit.json", "final/concept.py", "final/params.json", "final/tokens.json", "verify.json",
                 "src/logomaker/schemas.py"):
        assert name in artifacts, name


def test_deliverables_md_mirrors_the_package_builder():
    text = read("deliverables.md")
    manifest = section(text, "Package manifest")
    for group in PackageBuilder.GROUPS:
        assert f"`{group}`" in manifest, group
    for readme_section in ("SVG masters", "PNG exports", "Flattened", "Favicons and web app icons", "Apple app icon", "Android",
                           "Social", "Email and commerce", "Print", "Documents and tokens", "Fonts", "Source"):
        assert readme_section in manifest, readme_section
    platforms = section(text, "Platform specs")
    assert str(MASK_SAFE) in platforms and str(ADAPTIVE_RADIUS) in platforms
    sizes = section(text, "Clear space and minimum sizes")
    for value in MinSizes().model_dump().values():
        assert f"{value:g}" in sizes, value
