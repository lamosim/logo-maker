"""The example brand in docs/examples/keystone, made by following the logo skill's runbook by hand (plan 3, Task 22).

The first two tests are the plan's: the copy is complete, and its rationale follows the rule. The committed verify.json
is not taken on trust: a fast test re-runs the package check (export_docs.verify) on a copy in a tmp project, so a file
changed after the build, or final/ and brand.json drifting from what the package was built from, fails here; and the
render test copies the example into a tmp project, installs the package's own fonts into its assets/fonts, builds the
package again with no warnings, finds every file made without Chrome's rasteriser byte for byte as committed, and
verifies it (spec section 14). WALKTHROUGH.md says how to refresh the example when either breaks.
"""
import json
import shutil
from pathlib import Path

import pytest

from logomaker import export, export_docs
from logomaker.paths import project

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "examples" / "keystone"


def test_example_brand_is_complete():
    assert (EXAMPLE / "WALKTHROUGH.md").is_file()
    state = json.loads((EXAMPLE / "brand.json").read_text())
    assert state["phase"] == "done" and state["concept"] and state["territory"]
    assert json.loads((EXAMPLE / "package" / "verify.json").read_text())["ok"]
    for name in ("brief.md", "brief.json", "strategy.md", "strategy.json", "territories/territories.json", "concepts/ideas.md",
                 "final/concept.py", "final/tokens.json", "final/rationale.md", "final/knockout.md",
                 "package/BRAND.md", "package/brand-sheet.pdf", "package/README.md", "package/tokens.json", "sheets/concepts.html"):
        assert (EXAMPLE / name).is_file(), name
    concepts = [p for p in (EXAMPLE / "concepts").iterdir() if p.is_dir()]
    assert len(concepts) >= 5
    assert sum(1 for c in concepts if (c / "scorecard.json").is_file()) >= 3


def test_example_rationale_follows_the_rule():
    text = (EXAMPLE / "final" / "rationale.md").read_text()
    assert "represent" not in text.lower() and "golden ratio" not in text.lower()
    assert len(text.split()) <= 180 and text.count("\n\n") <= 1


def made_without_chrome(path: str) -> bool:
    """Whether package file `path` comes out of a build byte for byte the same: the vectors the kit draws (every SVG) and
    reportlab writes (the print PDFs and EPS), the copies (fonts/, and source/ but brand.json, which the brand moves on
    from after a build) and the documents written from templates and tokens. The rest are Chrome's: its renders, and the
    brand sheet it prints; README.md carries the build's time."""
    if path in ("brand-sheet.pdf", "README.md", "source/brand.json"):
        return False
    return (path.endswith((".svg", ".pdf", ".eps")) or path.startswith(("fonts/", "source/"))
            or path in ("tokens.json", "favicon-head.html", "manifest.webmanifest", "BRAND.md", "rationale.md"))


def install_example(project_root: Path) -> Path:
    """Copy the example into the tmp project as brands/keystone, the folder the skill built it in; return that folder."""
    brand = project_root / "brands" / "keystone"
    shutil.copytree(EXAMPLE, brand)
    return brand


def test_example_package_matches_its_manifest_and_the_brand_now(project_root):
    install_example(project_root)
    result = export_docs.verify(project(), "keystone")
    assert result["ok"], result["problems"]
    assert not json.loads((EXAMPLE / "package" / "manifest.json").read_text())["skipped"]


@pytest.mark.render
def test_example_package_builds_again_and_verifies(project_root, renderer):
    brand = install_example(project_root)
    for family in (p for p in (brand / "package" / "fonts").iterdir() if p.is_dir()):  # the package's own copies of its fonts
        shutil.copytree(family, project_root / "assets" / "fonts" / family.name, dirs_exist_ok=True)
    committed = json.loads((brand / "package" / "manifest.json").read_text())
    manifest = export.PackageBuilder(project(), "keystone").build(renderer)
    assert sorted(entry.path for entry in manifest.files) == sorted(entry["path"] for entry in committed["files"])
    assert manifest.skipped == {} and manifest.warnings == []
    hashes = {entry["path"]: entry["sha256"] for entry in committed["files"]}
    same = [entry for entry in manifest.files if made_without_chrome(entry.path)]
    assert {"BRAND.md", "icon.svg", "keystone-mark-cmyk.eps", "tokens.json", "fonts/FONT-NOTICE.md"} <= {e.path for e in same}
    assert not [entry.path for entry in same if entry.sha256 != hashes[entry.path]]  # else rebuild the example (WALKTHROUGH.md)
    result = export_docs.verify(project(), "keystone")
    assert result["ok"], result["problems"]
