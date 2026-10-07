import io
import json
import re

import pytest
from click.testing import CliRunner
from markupsafe import escape
from PIL import Image
from pypdf import PdfReader

from logomaker import export, export_docs, registry, sheets
from logomaker import fonts as fontlib
from logomaker.cli import main
from logomaker.color import check_tokens, chip_text
from logomaker.kit import Mark, rect_centered, ring
from logomaker.output import CliError
from logomaker.paths import project
from logomaker.schemas import Phase
from tests.conftest import StubRenderer, make_final_brand, requires_chrome, write_passing_audit
from tests.test_export_core import FAVICONS, build
from tests.test_export_platforms import use_concept

DOCS = ["masters", "favicons", "print_files", "tokens_file", "fonts", "docs", "readme"]  # a package without the big raster groups
SOURCES = {"concept.py": "final/concept.py", "params.json": "final/params.json", "tokens.json": "final/tokens.json",
           "rationale.md": "final/rationale.md", "brand.json": "brand.json", "strategy.json": "strategy.json"}  # source/ <- brand folder
FONT_FILES = ["fonts/firacode/FiraCode[wght].ttf", "fonts/firacode/OFL.txt", "fonts/FONT-NOTICE.md"]
SOURCE_FILES = [f"source/{name}" for name in SOURCES]
DOC_FILES = ["tokens.json", *FONT_FILES, "BRAND.md", "rationale.md", *SOURCE_FILES, "brand-sheet.pdf", "README.md"]


def verify_cli(slug: str = "keystone") -> tuple[int, dict]:
    """`package verify <slug>`: the exit code and the JSON payload."""
    result = CliRunner().invoke(main, ["package", "verify", slug])
    return result.exit_code, json.loads(result.stdout)


def sections(readme: str) -> dict[str, list[str]]:
    """README.md's `## ` sections in order, each with the files its table lists."""
    listed = {}
    for block in readme.split("\n## ")[1:]:
        heading, _, body = block.partition("\n")
        listed[heading] = re.findall(r"^\| `([^`]+)` \|", body, flags=re.M)
    return listed


@requires_chrome
@pytest.mark.render
def test_full_build_verify_and_done(project_root, renderer):
    make_final_brand(project_root, phase=Phase.package)
    builder = export.PackageBuilder(project(), "keystone")
    manifest = builder.build(renderer)
    pkg = project_root / "brands" / "keystone" / "package"
    assert len(manifest.files) >= 170
    tokens = json.loads((pkg / "tokens.json").read_text())
    assert tokens["colors"]["ember"]["oklch"] and tokens["contrast"] and tokens["palettes"]["light"]["primary"] == "#e8572a"
    assert (pkg / "fonts" / "firacode" / "FiraCode[wght].ttf").is_file() and (pkg / "fonts" / "firacode" / "OFL.txt").is_file()
    assert "Fira Code" in (pkg / "fonts" / "FONT-NOTICE.md").read_text()
    brand_md = (pkg / "BRAND.md").read_text()
    for needle in ("#e8572a", "120 px", "Don't", "currentColor", "apple-touch-icon", "holds the arch"):
        assert needle in brand_md, needle
    assert len(PdfReader(str(pkg / "brand-sheet.pdf")).pages) == 1
    assert all((pkg / "source" / name).is_file() for name in ("concept.py", "brand.json", "strategy.json"))
    assert "holds the arch" in (pkg / "rationale.md").read_text()
    readme = (pkg / "README.md").read_text()
    for entry in manifest.files:
        assert f"`{entry.path}`" in readme, entry.path
    assert "dark background" in readme and "confirm with your printer" in readme

    result = export_docs.verify(project(), "keystone")
    assert result["ok"], result["problems"]
    assert json.loads((pkg / "verify.json").read_text())["ok"]
    cli = CliRunner().invoke(main, ["brand", "advance", "keystone", "--to", "done"])
    assert cli.exit_code == 0 and json.loads(cli.stdout)["brand"]["phase"] == "done"

    (pkg / "avatar-400.png").unlink()
    code, payload = verify_cli()
    assert code == 4 and not payload["ok"] and any("avatar-400.png" in p for p in payload["problems"])


def test_verify_without_manifest_exits_4(project_root):
    registry.new_brand(project(), "Keystone")
    code, payload = verify_cli()
    assert code == 4 and "manifest.json" in payload["errors"][0] and "package build" in payload["errors"][0]
    code, payload = verify_cli("nosuch")
    assert code == 2 and payload["errors"][0].startswith("Unknown brand 'nosuch'")


def test_document_groups_index_and_verify_without_chrome(project_root):
    make_final_brand(project_root, phase=Phase.package)
    registry.rename(project(), "keystone", "Icon Works")  # a file prefix that starts like the platform files icon.svg and icon-192.png
    _, manifest = build(DOCS)
    brand, pkg = project_root / "brands" / "keystone", project_root / "brands" / "keystone" / "package"
    paths = [e.path for e in manifest.files]
    assert paths[-len(DOC_FILES):] == DOC_FILES and manifest.warnings == [] and manifest.skipped == {}
    for name, origin in SOURCES.items():
        assert (pkg / "source" / name).read_bytes() == (brand / origin).read_bytes(), name
    assert (pkg / "fonts" / "firacode" / "OFL.txt").read_bytes() == (project_root / "assets/fonts/firacode/OFL.txt").read_bytes()
    assert "- Fira Code: OFL." in (pkg / "fonts" / "FONT-NOTICE.md").read_text()
    brand_md = (pkg / "BRAND.md").read_text()
    assert "`icon-works-wordmark-color.svg`" in brand_md and "- Fira Code 600 (OFL); files in `fonts/firacode/`" in brand_md
    assert "primary: Ember, ink: Coal, paper: Paper" in brand_md and "primary: Ember Light, ink: Paper, paper: Coal" in brand_md
    snippet = (pkg / "favicon-head.html").read_text()
    assert f"```html\n{snippet}" in brand_md and "Replace `https://example.com` in the two preview image URLs" in brand_md
    assert PdfReader(str(pkg / "brand-sheet.pdf")).pages

    readme = (pkg / "README.md").read_text()
    listed = sections(readme)
    assert list(listed) == ["SVG masters", "Favicons and web app icons", "Print", "Documents and tokens", "Fonts", "Source",
                            "Package files"]
    assert listed["SVG masters"] == [p for p in paths if p.endswith(".svg") and p.startswith("icon-works-")]
    assert listed["Favicons and web app icons"] == FAVICONS
    assert listed["Print"] == [p for p in paths if p.startswith("icon-works-") and p.endswith((".pdf", ".eps"))]
    assert listed["Documents and tokens"] == ["tokens.json", "BRAND.md", "rationale.md", "brand-sheet.pdf"]
    assert listed["Fonts"] == FONT_FILES and listed["Source"] == SOURCE_FILES
    assert listed["Package files"] == ["README.md", "manifest.json"]
    assert "| `favicon.ico` | legacy favicon, 16/32/48 | 48x48 |" in readme
    assert "outlines only" in readme.split("\n## Print\n")[1].split("\n## ")[0]  # the print note sits in the print section
    assert "into `brands/keystone/final/`" in readme and "`uv run logomaker package build keystone`" in readme
    # The fonts go back into the cache before concept run sets the name in them again.
    assert ("run `uv run logomaker fonts fetch 'Fira Code'`, or copy each folder in this package's `fonts/` into "
            "`assets/fonts/`. Then run `uv run logomaker concept run keystone final`") in readme
    assert "\n\n\n" not in readme and readme.endswith(" |\n") and f"Built {manifest.built} by logo-maker." in readme

    assert export_docs.verify(project(), "keystone")["ok"]
    code, payload = verify_cli()
    assert code == 0 and payload["ok"] and payload["errors"] == [] and payload["files"] == len(paths)
    cli = CliRunner().invoke(main, ["brand", "advance", "keystone", "--to", "done"])
    assert cli.exit_code == 0 and json.loads(cli.stdout)["brand"]["phase"] == "done"


def test_a_package_built_before_final_or_the_name_changed_is_out_of_date(project_root):
    final = make_final_brand(project_root, phase=Phase.package)
    stale = "package is out of date (final/ or the brand changed since the build); run: logomaker package build keystone"

    def advance_done() -> tuple[int, dict]:
        result = CliRunner().invoke(main, ["brand", "advance", "keystone", "--to", "done"])
        return result.exit_code, json.loads(result.stdout)

    build(DOCS)
    assert verify_cli()[0] == 0
    tokens = json.loads((final / "tokens.json").read_text())
    tokens["colors"]["ember"]["hex"] = "#c2410c"  # a new primary, and the final mark audited again: the final gate passes
    (final / "tokens.json").write_text(json.dumps(tokens))
    write_passing_audit(project(), "keystone", final)
    code, payload = advance_done()  # package/verify.json still says ok, for the package of the old colour
    assert code == 2 and payload["missing"] == [stale]
    code, payload = verify_cli()
    assert code == 4 and payload["problems"] == [stale]
    build(DOCS)
    assert verify_cli()[0] == 0
    registry.rename(project(), "keystone", "Keystone Labs")  # the file names and the documents carry the name
    code, payload = advance_done()
    assert code == 2 and payload["missing"] == [stale]
    code, payload = verify_cli()
    assert code == 4 and payload["problems"] == [stale]
    build(DOCS)
    assert verify_cli()[0] == 0
    registry.decide(project(), "keystone", Phase.package, "user", "approved")  # brand.json changes, but nothing the build reads
    code, payload = advance_done()
    assert code == 0 and payload["brand"]["phase"] == "done"


def test_verify_names_every_problem_and_exits_4(project_root):
    make_final_brand(project_root)
    build(DOCS)
    pkg = project_root / "brands" / "keystone" / "package"
    data = json.loads((pkg / "manifest.json").read_text())
    ico = next(f for f in data["files"] if f["path"] == "favicon.ico")
    ico["width"] = ico["height"] = 64  # the ICO's largest frame is 48 px
    (pkg / "manifest.json").write_text(json.dumps(data))
    (pkg / "icon.svg").unlink()
    (pkg / "icon-192.png").write_bytes(b"not a png")
    (pkg / "tokens.json").write_text((pkg / "tokens.json").read_text() + " ")
    (pkg / "BRAND.md").write_text("")
    (pkg / "README.md").write_text((pkg / "README.md").read_text().replace("| `rationale.md` |", "| rationale |"))
    code, payload = verify_cli()
    assert code == 4 and not payload["ok"]
    assert payload["problems"] == ["favicon.ico is 48x48, expected 64x64", "icon.svg is missing", "icon-192.png changed since the build",
                                   "icon-192.png is not a readable image", "tokens.json changed since the build", "BRAND.md is empty",
                                   "README.md does not list rationale.md", "README.md changed since the build"]
    assert payload["errors"] == payload["problems"] and json.loads((pkg / "verify.json").read_text())["problems"] == payload["problems"]
    (pkg / "README.md").write_bytes("| `rationale.md` | Café |".encode("latin-1"))  # not UTF-8: a problem, never a traceback
    code, payload = verify_cli()
    assert code == 4 and "traceback" not in payload
    assert payload["problems"][0] == "README.md is not UTF-8 text, so the files it lists cannot be checked"
    assert "README.md changed since the build" in payload["problems"]
    (pkg / "manifest.json").write_text("{")
    code, payload = verify_cli()
    assert code == 4 and payload["errors"][0].startswith("package/manifest.json is invalid")


def test_font_weights_come_from_brand_json_else_from_the_type_as_set(project_root):
    make_final_brand(project_root)  # brand.json names wordmark=Fira Code:600; the concept sets its name in Fira Code 600

    def faces() -> tuple[list[str], list[tuple[str, str]]]:
        builder = export.PackageBuilder(project(), "keystone")
        return builder.font_families(), [(f["family"], f["weight"]) for f in builder.doc_context()["fonts"]]

    registry.set_fields(project(), "keystone", fonts=["wordmark=Fira Code:500", "body=Inter:400"])
    assert faces() == (["Fira Code", "Inter"], [("Fira Code", "500"), ("Inter", "400")])
    state = registry.load_state(project(), "keystone")
    state.fonts = {}
    registry.save_state(project(), state)
    assert faces() == (["Fira Code"], [("Fira Code", "600")])  # read from the wordmark's TextShape.font


def test_font_style_reads_multi_word_and_italic_families():
    assert export_docs.font_style("Fira Code 600") == ("Fira Code", "600")
    assert export_docs.font_style("Playfair Display SC 700 italic") == ("Playfair Display SC", "700 italic")
    assert export_docs.font_style("Noto Sans 650.5") == ("Noto Sans", "650.5")


def test_an_uncached_font_and_a_missing_source_file_are_left_out_with_warnings(project_root):
    make_final_brand(project_root)
    registry.set_fields(project(), "keystone", fonts=["body=Inter:400"])
    (project_root / "brands" / "keystone" / "strategy.json").unlink()
    _, manifest = build(DOCS)
    assert manifest.warnings == ["font Inter is not cached and was not copied; run: logomaker fonts fetch Inter",
                                 "source/strategy.json left out: brands/keystone/strategy.json is missing"]
    paths = [e.path for e in manifest.files]
    assert "source/strategy.json" not in paths and not any(p.startswith("fonts/inter/") for p in paths)
    pkg = project_root / "brands" / "keystone" / "package"
    assert "Inter" not in (pkg / "fonts" / "FONT-NOTICE.md").read_text()
    assert "- Inter 400 (OFL); not in this package (run `logomaker fonts fetch Inter` and rebuild)" in (pkg / "BRAND.md").read_text()


@pytest.mark.parametrize(("fixture", "source"), [("good", "cap-height"), ("tall_frame", "symbol-fifth"), ("drawn", "symbol-fifth")])
def test_documents_take_the_x_rule_and_chip_colours_from_the_sheets(project_root, fixture, source):
    final = make_final_brand(project_root)
    if fixture == "tall_frame":
        use_concept(final, fixture)
    builder = export.PackageBuilder(project(), "keystone")
    if fixture == "drawn":  # a wordmark drawn as shapes, not set with text(): x is a fifth of the symbol, not a cap height
        builder.outputs = {"full-lockup": Mark(symbol=ring(0, 0, 400, 90), wordmark=rect_centered(0, 0, 600, 180))}
    ctx = builder.doc_context()
    assert ctx["x_rule"] == sheets.X_RULES[source] and ctx["has_wordmark"] == (fixture == "good")
    hexes = ("#e8572a", "#1f1b18", "#ffffff", "#ff9a6e")
    assert [(c["hex"], c["text"]) for c in ctx["colours"]] == [(h, chip_text(h)) for h in hexes]


def test_the_token_checks_and_each_licence_are_computed_once(project_root, monkeypatch):
    make_final_brand(project_root)
    calls = []
    find_family = fontlib.find_family
    monkeypatch.setattr(export_docs, "check_tokens", lambda *args, **kwargs: calls.append("check_tokens") or check_tokens(*args, **kwargs))
    monkeypatch.setattr(fontlib, "find_family", lambda paths, family: calls.append(family) or find_family(paths, family))
    _, manifest = build(["tokens_file", "fonts", "docs"])
    assert calls == ["check_tokens", "Fira Code"]
    assert manifest.warnings == ["BRAND.md and the brand sheet have no web head snippet: favicon-head.html is not in the package"]
    brand_md = (project_root / "brands" / "keystone" / "package" / "BRAND.md").read_text()
    assert "## Web head snippet" not in brand_md and "```html" not in brand_md and "\n\n## Files" in brand_md  # no empty block


def test_the_manifest_and_the_readme_share_one_build_time(project_root, monkeypatch):
    make_final_brand(project_root)
    ticks = iter(f"2026-10-07T12:00:{second:02d}+00:00" for second in range(60))
    monkeypatch.setattr(export, "now_iso", lambda: next(ticks))
    monkeypatch.setattr(export_docs, "now_iso", lambda: next(ticks))
    _, manifest = build(["masters", "readme"])
    readme = (project_root / "brands" / "keystone" / "package" / "README.md").read_text()
    assert readme.startswith(f"# Keystone logo package\n\nBuilt {manifest.built} by logo-maker.")


def test_a_cached_font_without_a_licence_file_is_copied_with_a_warning(project_root):
    make_final_brand(project_root)
    (project_root / "assets" / "fonts" / "firacode" / "OFL.txt").unlink()
    _, manifest = build(["fonts"])
    assert manifest.warnings == ["font Fira Code has no licence file in assets/fonts/firacode/; confirm its licence before "
                                 "sending the fonts"]
    assert [e.path for e in manifest.files] == ["fonts/firacode/FiraCode[wght].ttf", "fonts/FONT-NOTICE.md"]
    notice = (project_root / "brands" / "keystone" / "package" / "fonts" / "FONT-NOTICE.md").read_text()
    assert "- Fira Code: OFL, but no licence file came with the cached font: confirm the licence" in notice
    assert "Logo use is permitted" not in notice


def test_brand_md_for_a_concept_without_a_wordmark(project_root):
    use_concept(make_final_brand(project_root), "tall_frame")  # a symbol alone, with a favicon tier
    _, manifest = build(DOCS)
    brand_md = (project_root / "brands" / "keystone" / "package" / "BRAND.md").read_text()
    assert "| Wordmark |" not in brand_md and "-wordmark-" not in brand_md  # no wordmark to point at
    assert "| Primary (horizontal) | `keystone-primary-color.svg` |" in brand_md and "| Mark | `keystone-mark-color.svg` |" in brand_md
    assert "where x is one fifth of the symbol height (64.0 units" in brand_md
    assert "- Fira Code 600 (OFL); files in `fonts/firacode/`" in brand_md  # brand.json's font, though no type is set in it
    assert "wordmark skipped: the concept has no full-wordmark" in manifest.warnings


def test_brand_md_leaves_the_placements_to_the_horizontal_and_stacked_rows(project_root):
    make_final_brand(project_root)
    registry.set_fields(project(), "keystone", primary_lockup="stacked")
    builder = export.PackageBuilder(project(), "keystone")
    brand_md = sheets.jinja(project()).get_template("brand.md.j2").render(**builder.doc_context())
    rows = {row.split(" | ")[0].removeprefix("| "): row for row in brand_md.splitlines() if row.startswith("| ")}
    # A stacked primary is no website header: the Primary row is the default, and the header is the horizontal's place.
    assert rows["Primary (stacked)"].endswith(" | the default lockup: use it wherever the layout allows |")
    assert rows["Horizontal"].endswith(" | website headers, nav bars, email signatures, banners |")
    assert rows["Stacked"].endswith(" | square placements, packaging, social posts |")


def brand_sheet_html(builder: export.PackageBuilder) -> str:
    """The brand sheet's HTML for `builder`, as the docs group prints it."""
    return sheets.jinja(project()).get_template("brand-sheet.html").render(**builder.doc_context())


def test_the_brand_sheet_carries_every_colour_value_and_the_head_snippet(project_root):
    make_final_brand(project_root)
    registry.set_fields(project(), "keystone", fonts=["body=Inter:400"])  # Inter is not cached
    builder, _ = build(["favicons"])  # the head snippet comes from the package's favicon-head.html
    html = brand_sheet_html(builder)
    for colour in builder.tokens.colors.values():  # each colour in all five notations, small type beside its swatch
        values = (colour.hex, *(" ".join(map(str, v)) for v in (colour.rgb, colour.hsl, colour.oklch, colour.cmyk)))
        assert all(value in html for value in values), colour.name
    assert re.search(r"\.colour\{[^}]*border:1px solid", html)  # the white Paper swatch keeps an edge
    snippet = (project_root / "brands" / "keystone" / "package" / "favicon-head.html").read_text()
    assert f"<pre>{escape(snippet)}</pre>" in html  # shown as code, not read as tags
    assert "horizontal 120 px / 25 mm" in html and "25.0 mm" not in html and "mark 24 px / 6 mm" in html
    assert "Fira Code 600 (OFL), files in <code>fonts/firacode/</code>" in html and "Inter 400 (OFL), not in this package" in html
    (project_root / "brands" / "keystone" / "package" / "favicon-head.html").unlink()
    assert "Web head snippet" not in brand_sheet_html(export.PackageBuilder(project(), "keystone"))


@pytest.mark.parametrize(("primary", "other"), [("horizontal", "stacked"), ("stacked", "horizontal")])
def test_the_brand_sheet_shows_each_lockup_once_labelled(project_root, primary, other):
    make_final_brand(project_root)
    registry.set_fields(project(), "keystone", primary_lockup=primary)
    builder = export.PackageBuilder(project(), "keystone")
    system = brand_sheet_html(builder).split("<h2>Logo system</h2>")[1].split("<h2>")[0]
    # The primary on light and dark paper, then the lockup that is not the primary, then the mark and its two small tiers.
    assert re.findall(r"<figcaption>(.*?)</figcaption>", system) == [f"primary ({primary})", "reverse", other, "mark", "small", "favicon"]
    unsized = re.sub(r'<svg width="\d+" height="\d+" ', "<svg ", system)
    for lockup in ("horizontal", "stacked"):  # each in colour exactly once: as the primary, or in the third panel
        assert unsized.count(builder.svg(lockup, "color")) == 1, lockup


class TwoPagePdf(StubRenderer):
    def html_to_pdf(self, html: str, paper: str = "letter") -> bytes:
        out = io.BytesIO()
        Image.new("RGB", (8, 8), "#ffffff").save(out, format="PDF", save_all=True, append_images=[Image.new("RGB", (8, 8))])
        return out.getvalue()


class NoPdf(StubRenderer):
    def html_to_pdf(self, html: str, paper: str = "letter") -> bytes:
        return b"not a pdf"


def test_a_brand_sheet_past_one_page_is_kept_with_a_warning(project_root):
    make_final_brand(project_root)
    _, manifest = build(["favicons", "docs"], TwoPagePdf())
    assert manifest.warnings == ["brand-sheet.pdf runs to 2 pages, not one; shorten final/rationale.md or the palette"]
    assert "brand-sheet.pdf" in [e.path for e in manifest.files]
    with pytest.raises(CliError) as err:  # what Chrome printed is no PDF: external, never a traceback
        build(["docs"], NoPdf())
    assert err.value.code == 3 and str(err.value).startswith("brand-sheet.pdf from Chrome is not a readable PDF (")


@requires_chrome
@pytest.mark.render
@pytest.mark.parametrize("paper", ["letter", "a4"])
def test_the_brand_sheet_prints_on_one_page(project_root, renderer, paper):
    make_final_brand(project_root)
    builder = export.PackageBuilder(project(), "keystone", paper)
    builder.GROUPS = ["masters", "favicons", "docs"]
    manifest = builder.build(renderer)
    pdf = PdfReader(str(project_root / "brands" / "keystone" / "package" / "brand-sheet.pdf"))
    assert len(pdf.pages) == 1 and manifest.warnings == []
    assert "https://example.com/og-image-1200x630.png" in pdf.pages[0].extract_text()
