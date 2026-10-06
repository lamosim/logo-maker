import json

import pytest

from logomaker.output import EXIT_EXTERNAL, EXIT_OK, EXIT_RULE, CliError, emit


def test_emit_prints_one_json_object_and_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        emit({"value": 1}, warnings=["w"])
    assert exc.value.code == EXIT_OK
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload == {"ok": True, "errors": [], "warnings": ["w"], "value": 1}
    assert out.count("\n{") == 0  # a single object


def test_emit_failure_code(capsys):
    with pytest.raises(SystemExit) as exc:
        emit(ok=False, errors=["bad"], code=EXIT_RULE)
    assert exc.value.code == EXIT_RULE
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_error_defaults():
    err = CliError("nope")
    assert err.code == EXIT_RULE and str(err) == "nope" and err.data == {}
    assert CliError("down", code=EXIT_EXTERNAL).code == EXIT_EXTERNAL
