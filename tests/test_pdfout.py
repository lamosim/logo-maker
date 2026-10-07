import hashlib
import re
import time
from pathlib import Path

import pytest
from pypdf import PdfReader

from logomaker import export, pdfout
from logomaker.kit.mark import Composite, Mark
from logomaker.kit.primitives import circle, rect
from logomaker.paths import project
from tests.conftest import make_final_brand
from tests.test_export_platforms import use_concept

PALETTE = {"primary": "#e8572a", "secondary": "#1f1b18", "ink": "#1f1b18", "paper": "#ffffff"}
PRINT_FILES = [*(f"keystone-{variant}-{suffix}.pdf" for variant in export.PNG_VARIANTS for suffix in ("rgb", "cmyk", "black")),
               "keystone-primary-cmyk.eps", "keystone-mark-cmyk.eps"]
EMBER_RGB, COAL_RGB = b".909804 .341176 .164706 rg", b".121569 .105882 .094118 rg"  # #e8572a and #1f1b18
EMBER_CMYK, COAL_CMYK = b"0 .62 .82 .09 k", b"0 .13 .23 .88 k"  # the same two, naive CMYK


def sample_mark() -> Mark:
    return Mark(symbol=Composite([(circle(0, 0, 200), "primary"), (rect(-40, -40, 80, 80), "secondary")]))


def colour_ops(pdf: Path) -> list[bytes]:
    """The colours the one page of the PDF at `pdf` fills with, in order: each `... rg` (RGB) and `... k` (CMYK) operation."""
    content = PdfReader(str(pdf)).pages[0].get_contents().get_data()
    return [line for line in content.splitlines() if line.endswith((b" rg", b" k"))]


def print_builder() -> export.PackageBuilder:
    builder = export.PackageBuilder(project(), "keystone")
    builder.GROUPS = ["print_files"]
    return builder


@pytest.fixture
def next_day(monkeypatch):
    """Call it between two builds to move the clock on a day: outside its invariant mode reportlab would stamp the new
    date, and a document ID derived from it, into each PDF. SOURCE_DATE_EPOCH, which reportlab reads instead, is unset."""
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    later = time.time() + 86400
    return lambda: monkeypatch.setattr(time, "time", lambda: later)


def test_pdf_rgb_cmyk_and_black(tmp_path):
    rgb = pdfout.mark_to_pdf(sample_mark(), tmp_path / "rgb.pdf", "color", PALETTE, "rgb")
    reader = PdfReader(str(rgb))
    page = reader.pages[0]
    assert len(reader.pages) == 1 and float(page.mediabox.width) == 100 and float(page.mediabox.height) == 100
    assert reader.metadata["/Producer"] == "logomaker"  # fixed, not reportlab's own string, which an upgrade could change
    content = page.get_contents().get_data()
    assert b" c" in content and b" rg" in content
    assert [op for op in content.split() if op in (b"f", b"f*")] == [b"f", b"f"]  # each part filled once, by the non-zero rule
    cmyk = PdfReader(str(pdfout.mark_to_pdf(sample_mark(), tmp_path / "cmyk.pdf", "color", PALETTE, "cmyk"))).pages[0]
    assert b" k" in cmyk.get_contents().get_data()
    black = PdfReader(str(pdfout.mark_to_pdf(sample_mark(), tmp_path / "black.pdf", "black", None, "cmyk"))).pages[0]
    assert b"0 0 0 1 k" in black.get_contents().get_data()
    assert colour_ops(rgb) == [EMBER_RGB, COAL_RGB] and colour_ops(tmp_path / "cmyk.pdf") == [EMBER_CMYK, COAL_CMYK]
    assert set(colour_ops(tmp_path / "black.pdf")) == {b"0 0 0 1 k"}
    with pytest.raises(ValueError, match="the mono variant cannot be printed"):
        pdfout.mark_to_pdf(sample_mark(), tmp_path / "mono.pdf", "mono")
    assert not (tmp_path / "mono.pdf").exists()  # refused before anything is written


@pytest.mark.parametrize(("variant", "mode", "message"), [
    ("colour", "rgb", "unknown variant 'colour'; use color, reverse, black or white"),
    ("color", "CMYK", "mode must be rgb or cmyk, got 'CMYK'"),  # it wrote RGB without a word
    ("mono", "cmyk", "the mono variant cannot be printed; use color, reverse, black or white"),
])
def test_an_unknown_variant_or_mode_is_refused_before_a_file_is_written(tmp_path, variant, mode, message):
    for write, suffix in ((pdfout.mark_to_pdf, "pdf"), (pdfout.mark_to_eps, "eps")):
        with pytest.raises(ValueError) as err:
            write(sample_mark(), tmp_path / f"out.{suffix}", variant, PALETTE, mode)
        assert str(err.value) == message and not (tmp_path / f"out.{suffix}").exists()


def test_the_art_stands_upright(tmp_path):
    # A T: the bar, in primary, across the top 40 of its 200 units; the stem, in secondary, below it.
    tee = Mark(symbol=Composite([(rect(-100, 60, 200, 40), "primary"), (rect(-20, -100, 40, 160), "secondary")]))
    content = PdfReader(str(pdfout.mark_to_pdf(tee, tmp_path / "t.pdf", "color", PALETTE))).pages[0].get_contents().get_data()
    matrices = [[float(v) for v in m.split()] for m in re.findall(rb"((?:-?[\d.]+ ){6})cm\b", content)]
    # Every transform keeps y pointing up, as the kit's does: the page is the art's box scaled by a quarter, its lower-left
    # corner (-100, -100) moved to the origin, never flipped.
    assert [.25, 0, 0, .25, 25, 25] in matrices and all(m[3] > 0 for m in matrices), matrices
    eps = pdfout.mark_to_eps(tee, tmp_path / "t.eps", "color", PALETTE).read_text()
    assert "%%BoundingBox: 0 0 50 50" in eps.splitlines()
    blocks = {colour: re.findall(r"^[\d.]+ ([\d.]+) [ml]$", body, flags=re.M)
              for colour, body in re.findall(r"^gsave\n([^\n]+) setcmykcolor\n(.*?)^grestore", eps, flags=re.M | re.S)}
    bar, stem = ([float(y) for y in blocks[colour]] for colour in ("0 .62 .82 .09", "0 .13 .23 .88"))
    assert (min(bar), max(bar)) == (40, 50) and (min(stem), max(stem)) == (0, 40)  # the bar at the top of the box


def test_eps(tmp_path):
    eps = pdfout.mark_to_eps(sample_mark(), tmp_path / "mark.eps", "color", PALETTE, "cmyk")
    text = eps.read_text(errors="ignore")
    assert text.startswith("%!PS-Adobe") and "curveto" in text and ("setcmykcolor" in text or "setrgbcolor" in text)
    # reportlab's prologue defines curveto whatever the art; these needles are the art: its box, its curves, and each of
    # its two parts filled once (by the non-zero rule, never eofill) in its own CMYK colour
    lines = text.splitlines()
    assert "%%BoundingBox: 0 0 100 100" in lines and any(line.endswith(" c") for line in lines)
    assert [line for line in lines if line.endswith("fill")] == ["fill", "fill"]
    assert {line for line in lines if line.endswith(" setcmykcolor")} == {"0 .62 .82 .09 setcmykcolor", "0 .13 .23 .88 setcmykcolor"}


def test_the_eps_bounding_box_takes_in_the_whole_art(tmp_path):
    # renderPS writes the box in whole points, dropping any fraction: this 100.5 pt circle needs 101, or a program placing
    # the EPS would clip half a point off its right and top edges
    eps = pdfout.mark_to_eps(Mark(symbol=circle(0, 0, 201)), tmp_path / "odd.eps", "color", PALETTE)
    assert "%%BoundingBox: 0 0 101 101" in eps.read_text().splitlines()


def test_pdf_and_eps_bytes_are_the_same_every_build(tmp_path, next_day):
    def write(stem: str) -> list[bytes]:
        return [pdfout.mark_to_pdf(sample_mark(), tmp_path / f"{stem}.pdf", "color", PALETTE, "cmyk").read_bytes(),
                pdfout.mark_to_eps(sample_mark(), tmp_path / f"{stem}.eps", "color", PALETTE).read_bytes()]

    first = write("first")
    next_day()
    assert write("second") == first


def test_print_group_writes_files(project_root):
    make_final_brand(project_root)
    builder = print_builder()
    manifest = builder.build()  # no renderer: print files are drawn from the kit's paths, never through Chrome
    pkg = project_root / "brands" / "keystone" / "package"
    assert len(list(pkg.glob("*.pdf"))) == 15 and len(list(pkg.glob("*.eps"))) == 2
    assert any(f.path == "keystone-mark-cmyk.pdf" for f in manifest.files)
    assert PdfReader(str(pkg / "keystone-primary-rgb.pdf")).pages[0].mediabox.width > 0
    assert [e.path for e in manifest.files] == PRINT_FILES and manifest.warnings == [] and manifest.skipped == {}
    for entry in manifest.files:
        raw = (pkg / entry.path).read_bytes()
        assert (entry.sha256, entry.bytes) == (hashlib.sha256(raw).hexdigest(), len(raw)), entry.path
    purposes = {e.path: e.purpose for e in manifest.files}
    assert purposes["keystone-primary-rgb.pdf"] == "primary vector PDF, RGB, for screens and digital print"
    assert purposes["keystone-primary-cmyk.pdf"] == "primary vector PDF, CMYK (naive values; confirm with the printer)"
    assert purposes["keystone-primary-black.pdf"] == "primary vector PDF, black only (100% K)"
    assert purposes["keystone-mark-cmyk.eps"] == "mark legacy CMYK EPS for old print vendors (naive values; confirm with the printer)"
    # Each PDF names itself and its brand, and so has an ID of its own; the producer and creator are logomaker.
    infos = {path: PdfReader(str(pkg / path)) for path in ("keystone-primary-rgb.pdf", "keystone-mark-cmyk.pdf")}
    assert {path: (r.metadata["/Title"], r.metadata["/Author"], r.metadata["/Creator"]) for path, r in infos.items()} == {
        "keystone-primary-rgb.pdf": ("Keystone logo, primary, rgb", "Keystone", "logomaker"),
        "keystone-mark-cmyk.pdf": ("Keystone logo, mark, cmyk", "Keystone", "logomaker")}
    assert len({r.trailer["/ID"][0] for r in infos.values()}) == 2
    box = builder.mark("primary").bounds()  # the page is the art: 1000 kit units print 250 pt
    page = PdfReader(str(pkg / "keystone-primary-cmyk.pdf")).pages[0]
    assert float(page.mediabox.width) == pytest.approx(box.w * pdfout.UNIT_PT, abs=1e-3)
    assert float(page.mediabox.height) == pytest.approx(box.h * pdfout.UNIT_PT, abs=1e-3)
    # the light palette: the ring in ember (primary), the name in coal (ink); the black files in pure K
    assert colour_ops(pkg / "keystone-primary-rgb.pdf") == [EMBER_RGB, COAL_RGB]
    assert colour_ops(pkg / "keystone-primary-cmyk.pdf") == [EMBER_CMYK, COAL_CMYK]
    assert colour_ops(pkg / "keystone-mark-cmyk.pdf") == [EMBER_CMYK]
    assert {op for variant in export.PNG_VARIANTS for op in colour_ops(pkg / f"keystone-{variant}-black.pdf")} == {b"0 0 0 1 k"}
    assert "0 .62 .82 .09 setcmykcolor" in (pkg / "keystone-mark-cmyk.eps").read_text().splitlines()



def test_print_files_hash_the_same_every_build(project_root, next_day):
    make_final_brand(project_root)
    first = {entry.path: entry.sha256 for entry in print_builder().build().files}
    next_day()
    assert {entry.path: entry.sha256 for entry in print_builder().build().files} == first and list(first) == PRINT_FILES


def test_print_files_leave_out_a_wordmark_the_concept_cannot_draw(project_root):
    use_concept(make_final_brand(project_root), "tall_frame")  # a symbol alone: no wordmark lockup
    manifest = print_builder().build()
    assert [e.path for e in manifest.files] == [path for path in PRINT_FILES if "-wordmark-" not in path]
    assert "wordmark skipped: the concept has no full-wordmark" in manifest.warnings and manifest.skipped == {}
