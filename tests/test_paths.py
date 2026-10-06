import pytest

from logomaker.output import CliError
from logomaker.paths import find_root, project


def test_find_root_uses_env_and_marker(project_root):
    assert find_root() == project_root
    assert project().brands == project_root / "brands"
    assert project().brand("acme") == project_root / "brands" / "acme"
    assert project().cliches == project_root / "assets" / "cliches.json"


def test_find_root_walks_up_without_env(project_root, monkeypatch):
    monkeypatch.delenv("LOGOMAKER_ROOT")
    nested = project_root / "brands" / "deep"
    nested.mkdir(parents=True)
    assert find_root(nested) == project_root


def test_find_root_fails_outside_project(tmp_path, monkeypatch):
    monkeypatch.delenv("LOGOMAKER_ROOT", raising=False)
    with pytest.raises(CliError) as exc:
        find_root(tmp_path)
    assert exc.value.code == 2
