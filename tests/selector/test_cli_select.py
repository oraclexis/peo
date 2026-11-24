"""`peo select` (contract in specs/011-selector/contracts/select.md)."""

import io
import json
import shutil

from jsonschema import Draft202012Validator

from peo import cli

from .conftest import GOLDEN, ROOT

SCHEMA = json.loads((ROOT / "docs/design/spec/schemas/selection.schema.json").read_text())
PROFILE = str(GOLDEN / "fx-split-stack" / "profile.json")
CATALOG = str(ROOT / "catalog")


def run(capsys, monkeypatch, *argv, stdin=""):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = cli.main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_a_complete_selection_exits_0_with_a_valid_envelope(capsys, monkeypatch):
    code, out, err = run(capsys, monkeypatch, "--json", "--catalog", CATALOG, "select", "--profile", PROFILE)
    env = json.loads(out)
    assert code == 0 and env["command"] == "select" and env["ok"] is True and err == ""
    assert list(Draft202012Validator(SCHEMA).iter_errors(env["data"])) == []
    assert out.strip() == json.dumps(env, sort_keys=True) and str(ROOT) not in out


def test_two_runs_give_the_same_bytes(capsys, monkeypatch):
    argv = ("--json", "--catalog", CATALOG, "select", "--profile", PROFILE)
    assert run(capsys, monkeypatch, *argv) == run(capsys, monkeypatch, *argv)


def test_answers_come_from_standard_input(capsys, monkeypatch):
    argv = ("--json", "--catalog", CATALOG, "select", "--profile", PROFILE, "--answers", "-")
    code, out, _ = run(capsys, monkeypatch, *argv, stdin='{"q.refactoring": true}')
    selected = {e["ref"] for e in json.loads(out)["data"]["selected"]}
    assert code == 0 and "mcp:serena" in selected


def test_answers_that_are_not_an_object_exit_2(capsys, monkeypatch):
    for text in ("[1]", "not json", '"x"'):
        code, out, _ = run(capsys, monkeypatch, "--json", "--catalog", CATALOG, "select", "--profile", PROFILE,
                           "--answers", "-", stdin=text)
        assert code == 2 and json.loads(out)["errors"][0]["code"] == "E_USAGE"


def test_a_remote_catalog_exits_2(capsys, monkeypatch):
    code, out, _ = run(capsys, monkeypatch, "--json", "--catalog", "https://example.test/c@v1", "select",
                       "--profile", PROFILE)
    assert code == 2 and json.loads(out)["ok"] is False


def test_an_absent_profile_exits_2(capsys, monkeypatch, tmp_path):
    code, out, _ = run(capsys, monkeypatch, "--json", "--catalog", CATALOG, "select", "--profile",
                       str(tmp_path / "none.json"))
    assert code == 2 and json.loads(out)["errors"][0]["code"] == "E_PROFILE_NOT_FOUND"
    assert str(tmp_path) not in out


def test_an_invalid_catalog_exits_1_with_the_loader_error(capsys, monkeypatch, tmp_path):
    (tmp_path / "tools").mkdir()
    code, out, _ = run(capsys, monkeypatch, "--json", "--catalog", str(tmp_path), "select", "--profile", PROFILE)
    assert code == 1 and json.loads(out)["errors"][0]["code"] == "E_CATALOG_INVALID"


def test_a_backbone_conflict_exits_6(capsys, monkeypatch, tmp_path):
    root = tmp_path / "proj"
    (root / ".peo").mkdir(parents=True)
    (root / ".claude").mkdir()
    (root / ".peo" / "profile.json").write_text((GOLDEN / "fx-conflict" / "profile.json").read_text())
    code, out, _ = run(capsys, monkeypatch, "--json", "--catalog", CATALOG, "select",
                       "--profile", str(root / ".peo" / "profile.json"), "--declared",
                       str(GOLDEN / "fx-conflict" / "declared.json"))
    assert code == 6 and json.loads(out)["errors"][0]["code"] == "E_BACKBONE_CONFLICT"


def test_an_unknown_backbone_answer_exits_2(capsys, monkeypatch):
    code, out, _ = run(capsys, monkeypatch, "--json", "--catalog", CATALOG, "select", "--profile", PROFILE,
                       "--answers", "-", stdin='{"q.backbone_conflict": "other"}')
    assert code == 2 and json.loads(out)["errors"][0]["code"] == "E_BACKBONE_UNKNOWN"


def test_an_uncovered_hard_requirement_exits_6_and_keeps_the_selection(capsys, monkeypatch, tmp_path):
    shutil.copytree(CATALOG, tmp_path / "catalog")
    (tmp_path / "catalog" / "tools" / "peo" / "gates.toml").unlink()
    code, out, _ = run(capsys, monkeypatch, "--json", "--catalog", str(tmp_path / "catalog"), "select",
                       "--profile", PROFILE)
    env = json.loads(out)
    assert code == 6 and env["errors"][0]["code"] == "E_REQUIREMENT_UNCOVERED"
    assert env["data"]["ok"] is False and {"capability": "process.gates", "strength": "hard"} in env["data"]["uncovered"]


def test_select_is_no_longer_reported_as_not_implemented(capsys, monkeypatch):
    code, _, err = run(capsys, monkeypatch, "--catalog", CATALOG, "select", "--profile", PROFILE)
    assert code == 0 and "E_NOT_IMPLEMENTED" not in err


def test_a_wrong_shape_inside_the_inputs_exits_2_without_a_traceback(capsys, monkeypatch, tmp_path):
    bad_declared = tmp_path / "d.json"
    bad_declared.write_text('{"plugins": ["superpowers"]}')
    code, out, _ = run(capsys, monkeypatch, "--json", "--catalog", CATALOG, "select", "--profile", PROFILE,
                       "--declared", str(bad_declared))
    assert code == 2 and json.loads(out)["errors"][0]["code"] == "E_USAGE"
    bad_profile = tmp_path / "p.json"
    bad_profile.write_text('{"present_tools": "x"}')
    code, out, _ = run(capsys, monkeypatch, "--json", "--catalog", CATALOG, "select", "--profile", str(bad_profile))
    assert code == 2 and json.loads(out)["errors"][0]["code"] == "E_USAGE"
