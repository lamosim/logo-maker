import json

from click.testing import CliRunner

from logomaker.cli import main


def test_setup_check_reports_components(project_root):
    result = CliRunner().invoke(main, ["setup", "--check"])
    payload = json.loads(result.output)
    assert set(payload) >= {"ok", "errors", "warnings", "python", "chrome", "modules"}
    assert payload["python"].startswith("3.12")
    assert "skia" in payload["modules"]
    assert isinstance(payload["chrome"]["found"], bool)


def test_setup_creates_folders(project_root):
    (project_root / "brands").rmdir()
    result = CliRunner().invoke(main, ["setup"])
    assert result.exit_code == 0, result.output
    assert (project_root / "brands").is_dir()
    assert (project_root / "registry").is_dir()
