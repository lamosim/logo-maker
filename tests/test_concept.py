import json
import os

from click.testing import CliRunner

from logomaker.cli import main
from logomaker.kit import concept as conceptlib
from logomaker.kit.mark import VARIANTS
from logomaker.paths import project
from tests.conftest import install_concept


def run(*args):
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, json.loads(result.stdout)


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
    assert (build / "full-lockup-black.svg").read_text() == (build / "full-lockup-black.svg").read_text()


def test_broken_concept_exits_2_with_traceback(project_root):
    install_concept(project_root, "raises", name="02-raises")
    code, payload = run("concept", "build", "keystone", "02-raises")
    assert code == 2 and "RuntimeError: boom" in payload["errors"][0] and "traceback" in payload


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
