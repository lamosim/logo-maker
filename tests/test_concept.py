import json
import os

import pytest
from click.testing import CliRunner

from logomaker.cli import main
from logomaker.kit import concept as conceptlib
from logomaker.kit.mark import VARIANTS
from logomaker.output import CliError
from logomaker.paths import project
from tests.conftest import install_concept


def run(*args):
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, json.loads(result.stdout)


def snapshot(build):
    """Every file in a build folder as {name: bytes}."""
    return {p.name: p.read_bytes() for p in sorted(build.iterdir())}


def test_load_and_build_tiers(project_root):
    folder = install_concept(project_root, "good")
    module = conceptlib.load_concept(folder)
    assert module.meta.slug == "good" and module.params.stroke == 90 and set(module.tiers) == {"full", "compact", "small", "favicon"}
    marks = conceptlib.build_tiers(module)
    assert marks["favicon"].wordmark is None and marks["full"].wordmark is not None
    outputs = conceptlib.build_outputs(marks)
    assert set(outputs) == {"full-lockup", "full-horizontal", "full-stacked", "full-symbol", "full-wordmark", "compact", "small", "favicon"}
    assert outputs["full-stacked"].lockup == "stacked" and outputs["full-symbol"].lockup == "symbol"


def test_params_json_overrides(project_root):
    folder = install_concept(project_root, "good")
    (folder / "params.json").write_text(json.dumps({"stroke": 50}))
    module = conceptlib.load_concept(folder)
    assert module.params.stroke == 50
    assert module.params.with_overrides(stroke=10).stroke == 10 and module.params.stroke == 50


def test_concept_build_cli_writes_files(project_root):
    install_concept(project_root, "good")
    code, payload = run("concept", "build", "keystone", "01-good")
    assert code == 0, payload
    build = project_root / "brands" / "keystone" / "concepts" / "01-good" / "build"
    assert (build / "full-lockup-black.svg").is_file() and (build / "favicon-white.svg").is_file()
    assert "full-symbol" in json.loads((build / "geometry.json").read_text())
    report = json.loads((build / "build.json").read_text())
    assert report["variants"] == ["black", "white"] and "favicon-black.svg" in report["files"]
    first = snapshot(build)
    assert run("concept", "build", "keystone", "01-good")[0] == 0
    assert snapshot(build) == first  # deterministic: a rebuild reproduces every file byte for byte


def test_broken_concept_exits_2_with_traceback(project_root):
    install_concept(project_root, "raises", name="02-raises")
    code, payload = run("concept", "build", "keystone", "02-raises")
    assert code == 2 and "RuntimeError: boom" in payload["errors"][0] and "traceback" in payload


def test_a_missing_font_inside_a_concept_exits_3_with_the_fetch_hint(project_root):
    folder = install_concept(project_root, "good")
    source = (folder / "concept.py").read_text()
    in_build = source.replace('family="Fira Code"', 'family="Sora"')
    at_import = source.replace("def build(p):", 'WORD = text("Good", family="Sora")\n\n\ndef build(p):')
    for edited, where in ((in_build, "build() failed for tier 'full'"), (at_import, "failed to import")):
        (folder / "concept.py").write_text(edited)
        code, payload = run("concept", "build", "keystone", "01-good")
        assert code == 3 and "traceback" not in payload, payload
        assert where in payload["errors"][0] and "run: logomaker fonts fetch Sora" in payload["errors"][0]


def test_concept_prints_go_to_stderr_so_stdout_stays_one_json_object(project_root):
    folder = install_concept(project_root, "good")
    source = (folder / "concept.py").read_text()
    (folder / "concept.py").write_text(source.replace("def build(p):\n", "print('loading')\n\n\ndef build(p):\n    print('building', p.stroke)\n"))
    result = CliRunner().invoke(main, ["concept", "build", "keystone", "01-good"])
    assert result.exit_code == 0 and json.loads(result.stdout)["ok"]  # json.loads refuses anything beside the one object
    assert "loading" in result.stderr and "building 90" in result.stderr


def test_sys_exit_in_a_concept_is_an_error_not_an_exit(project_root):
    folder = install_concept(project_root, "good")
    source = (folder / "concept.py").read_text()
    for edited in (source.replace("def build(p):\n", "def build(p):\n    import sys\n    sys.exit(0)\n"), "import sys\nsys.exit(0)\n"):
        (folder / "concept.py").write_text(edited)
        code, payload = run("concept", "build", "keystone", "01-good")
        assert code == 2 and payload["ok"] is False and "concept called sys.exit(); return the Mark instead" in payload["errors"][0]


def test_concept_without_meta_exits_2(project_root):
    install_concept(project_root, "nometa", name="03-nometa")
    code, payload = run("concept", "build", "keystone", "03-nometa")
    assert code == 2 and "META" in payload["errors"][0]


def test_unknown_concept_folder_exits_2(project_root):
    install_concept(project_root, "good")
    code, payload = run("concept", "build", "keystone", "99-missing")
    assert code == 2 and "concept.py" in payload["errors"][0]


def test_final_folder_resolves(project_root):
    install_concept(project_root, "good")
    paths = project()
    assert conceptlib.concept_folder(paths, "keystone", "01-good").name == "01-good"
    final = project_root / "brands" / "keystone" / "final"
    (final / "concept.py").write_text((project_root / "brands" / "keystone" / "concepts" / "01-good" / "concept.py").read_text())
    assert conceptlib.concept_folder(paths, "keystone", "final") == final


def test_reload_sees_same_size_edit_and_writes_no_bytecode(project_root):
    folder = install_concept(project_root, "good")
    source = folder / "concept.py"
    before = conceptlib.build_tiers(conceptlib.load_concept(folder))["full"].to_svg("black")
    original, stat = source.read_text(), source.stat()
    edited = original.replace("end=330", "end=300")  # angles snap to 15 degrees, so end=331 would draw the same ring
    assert edited != original and len(edited) == len(original)
    source.write_text(edited)
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # same size and mtime second: a cached .pyc would still look fresh
    after = conceptlib.build_tiers(conceptlib.load_concept(folder))["full"].to_svg("black")
    assert after != before
    assert not (folder / "__pycache__").exists()


def test_unknown_variant_exits_2_and_keeps_previous_build(project_root):
    install_concept(project_root, "good")
    assert run("concept", "build", "keystone", "01-good")[0] == 0
    build = project_root / "brands" / "keystone" / "concepts" / "01-good" / "build"
    report = (build / "build.json").read_text()
    code, payload = run("concept", "build", "keystone", "01-good", "--variants", "blak")
    assert (build / "full-lockup-black.svg").is_file() and (build / "build.json").read_text() == report
    assert code == 2 and "traceback" not in payload
    assert "'blak'" in payload["errors"][0] and all(v in payload["errors"][0] for v in VARIANTS)


def test_import_time_errors_exit_2_with_traceback(project_root):
    folder = install_concept(project_root, "good")
    for source, error in (("def build(p:\n", "SyntaxError"), ("raise ValueError('at import')\n", "ValueError: at import")):
        (folder / "concept.py").write_text(source)
        code, payload = run("concept", "build", "keystone", "01-good")
        assert code == 2 and "failed to import" in payload["errors"][0] and error in payload["errors"][0] and "traceback" in payload


def test_empty_variants_exit_2_and_keep_previous_build(project_root):
    install_concept(project_root, "good")
    assert run("concept", "build", "keystone", "01-good")[0] == 0
    build = project_root / "brands" / "keystone" / "concepts" / "01-good" / "build"
    before = snapshot(build)
    for variants in ("", ","):
        code, payload = run("concept", "build", "keystone", "01-good", "--variants", variants)
        assert snapshot(build) == before
        assert code == 2 and all(v in payload["errors"][0] for v in VARIANTS)


def test_duplicate_variants_render_once(project_root):
    install_concept(project_root, "good")
    code, payload = run("concept", "build", "keystone", "01-good", "--variants", "black,black")
    assert code == 0, payload
    assert payload["build"]["variants"] == ["black"] and payload["build"]["files"].count("full-lockup-black.svg") == 1
    assert len(payload["build"]["files"]) == len(payload["build"]["outputs"])


def test_write_build_renders_before_touching_the_folder(project_root):
    folder = install_concept(project_root, "good")
    outputs = conceptlib.build_outputs(conceptlib.build_tiers(conceptlib.load_concept(folder)))
    conceptlib.write_build(folder, outputs)
    before = snapshot(folder / "build")
    with pytest.raises(ValueError, match="ink"):  # the wordmark's role has no colour in this palette
        conceptlib.write_build(folder, outputs, variants=("color",), palette={"primary": "#111111"})
    assert snapshot(folder / "build") == before


def test_dropping_the_wordmark_needs_a_symbol(project_root):
    folder = install_concept(project_root, "good")
    wordonly = folder.parent / "05-wordonly"
    wordonly.mkdir()
    (wordonly / "concept.py").write_text(
        "from logomaker.kit import *\n\n"
        'META = Meta(slug="wordonly", idea="the name alone", logo_type="wordmark")\n'
        "PARAMS = Params()\n"
        'TIERS = {"full": {}, "favicon": {"wordmark": False}}\n\n\n'
        "def build(p):\n"
        '    return Mark(wordmark=text("Good", family="Fira Code", weight=600, cap_height=180))\n'
    )
    code, payload = run("concept", "build", "keystone", "05-wordonly")
    assert code == 2 and "traceback" not in payload and "05-wordonly/concept.py" in payload["errors"][0]
    assert "tier 'favicon' drops the wordmark but the concept has no symbol" in payload["errors"][0]


def test_concept_build_with_tokens_writes_colour_variants(project_root):
    from tests.test_color import good_tokens

    folder = install_concept(project_root, "good")
    (folder / "tokens.json").write_text(json.dumps(good_tokens()))
    code, payload = run("concept", "build", "keystone", "01-good", "--variants", "black,white,color,reverse,mono")
    assert code == 0, payload
    build = folder / "build"
    assert 'fill="#e8572a"' in (build / "full-lockup-color.svg").read_text()
    assert 'fill="#ff9a6e"' in (build / "full-lockup-reverse.svg").read_text()
    assert 'fill="currentColor"' in (build / "full-lockup-mono.svg").read_text()


def test_validate_variants_dedupes_in_order_and_rejects_empty_or_unknown():
    assert conceptlib.validate_variants(v for v in ("white", "black", "white")) == ("white", "black")
    for bad in ((), ("blak",)):
        with pytest.raises(CliError) as err:
            conceptlib.validate_variants(bad)
        assert all(v in str(err.value) for v in VARIANTS)


def test_draft_tokens_only_matter_for_colour_variants(project_root):
    folder = install_concept(project_root, "good")
    (folder / "tokens.json").write_text('{"colors": ')
    code, payload = run("concept", "build", "keystone", "01-good")
    assert code == 0, payload
    before = snapshot(folder / "build")
    code, payload = run("concept", "build", "keystone", "01-good", "--variants", "color")
    assert code == 2 and "traceback" not in payload and "01-good/tokens.json is invalid" in payload["errors"][0]
    assert snapshot(folder / "build") == before
