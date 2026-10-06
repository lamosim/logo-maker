import json

from click.testing import CliRunner

from logomaker.cli import main
from logomaker.kit import concept as conceptlib
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
