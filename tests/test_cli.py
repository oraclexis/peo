"""CLI envelope and exit codes (spec 11, section 1)."""

import json

import pytest

from peo import __version__, cli


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"peo {__version__}"


def test_no_command_is_a_usage_error():
    assert cli.main([]) == cli.EXIT_USAGE


@pytest.mark.parametrize("command", sorted(cli.COMMANDS))
def test_unimplemented_commands_answer_with_the_envelope(command, capsys):
    assert cli.main(["--json", command]) == cli.EXIT_ERROR
    out = json.loads(capsys.readouterr().out)
    assert set(out) == {"schema", "command", "ok", "data", "warnings", "errors"}
    assert out["ok"] is False
    assert out["errors"][0]["code"] == "E_NOT_IMPLEMENTED"


def test_spec_commands_are_all_declared():
    # spec 11, sections 2.1 to 2.4
    expected = {"discover", "questions", "select", "plan", "apply", "status", "tools", "catalog",
                "render-doc", "flow", "gate", "context"}
    assert set(cli.COMMANDS) == expected
