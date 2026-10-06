import json
import subprocess
import sys

import click
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


def test_unknown_option_is_a_json_failure():
    result = CliRunner().invoke(main, ["setup", "--bogus"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "--bogus" in payload["errors"][0]


def test_unknown_command_is_a_json_failure():
    result = CliRunner().invoke(main, ["nosuchcmd"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "nosuchcmd" in payload["errors"][0]


def test_help_stays_plain_text_and_exits_zero():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("Usage:")
    assert "setup" in result.stdout


def test_setup_check_fails_without_chrome_but_plain_setup_only_warns(project_root, monkeypatch):
    from logomaker import cli

    monkeypatch.setattr(cli, "chrome_status", lambda: {"found": False, "path": "/nowhere/Google Chrome.app", "version": None})
    result = CliRunner().invoke(main, ["setup", "--check"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 3 and payload["ok"] is False
    assert payload["errors"] == ["Google Chrome not found at /nowhere/Google Chrome.app; render commands will exit 3"]
    result = CliRunner().invoke(main, ["setup"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0 and payload["ok"] is True and payload["errors"] == []
    assert payload["warnings"] == ["Google Chrome not found at /nowhere/Google Chrome.app; render commands will exit 3"]


def test_setup_finds_chrome_where_the_renderer_looks(project_root, monkeypatch, tmp_path):
    monkeypatch.setattr("logomaker.render.CHROME_APP", tmp_path / "Nowhere.app")
    payload = json.loads(CliRunner().invoke(main, ["setup", "--check"]).stdout)
    assert payload["chrome"] == {"found": False, "path": str(tmp_path / "Nowhere.app"), "version": None}


def test_setup_check_runs_and_reports_a_missing_module(project_root):
    # A fresh interpreter where skia and Playwright cannot be imported: the CLI must still load and say so.
    script = (
        "import sys\n"
        "sys.modules['skia'] = sys.modules['playwright'] = None\n"
        "from click.testing import CliRunner\n"
        "from logomaker.cli import main\n"
        "result = CliRunner().invoke(main, ['setup', '--check'])\n"
        "print(result.exit_code)\n"
        "print(result.stdout)\n"
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    exit_code, _, stdout = proc.stdout.partition("\n")
    payload = json.loads(stdout)
    assert int(exit_code) == 3 and payload["ok"] is False
    assert payload["modules"]["skia"] is False and payload["modules"]["playwright"] is False and payload["modules"]["pypdf"] is True
    assert list(payload["module_errors"]) == ["skia", "playwright"] and "skia" in payload["module_errors"]["skia"]
    assert any(e.startswith("missing modules: skia, playwright") for e in payload["errors"])
    assert payload["chrome"]["path"] == "/Applications/Google Chrome.app"  # still checked without Playwright


def test_setup_check_adds_module_errors_only_when_an_import_fails(project_root):
    payload = json.loads(CliRunner().invoke(main, ["setup", "--check"]).stdout)
    assert "pypdf" in payload["modules"] and all(payload["modules"].values()) and "module_errors" not in payload


def test_concept_commands_share_their_option_definitions():
    commands = main.commands["concept"].commands

    def info(command, name):
        return json.dumps(next(p for p in commands[command].params if p.name == name).to_info_dict(), sort_keys=True, default=str)

    for name, users in (("tokens_path", ("build", "render", "run")), ("variants", ("build", "run")), ("round_n", ("render", "run"))):
        assert len({info(command, name) for command in users}) == 1, name


def test_every_command_has_a_one_line_description():
    def leaves(group, prefix=()):
        for name, cmd in group.commands.items():
            if isinstance(cmd, click.Group):
                yield from leaves(cmd, (*prefix, name))
            else:
                yield " ".join((*prefix, name)), cmd

    commands = dict(leaves(main))
    assert len(commands) == 17
    assert [name for name, cmd in commands.items() if not (cmd.help or "").strip() or "\n" in cmd.help.strip()] == []
    result = CliRunner().invoke(main, ["brand", "--help"])
    assert result.exit_code == 0 and "Move a brand to its next phase." in result.stdout
