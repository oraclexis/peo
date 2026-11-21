"""`peo catalog validate` (spec 11, contract in specs/010-catalog-loader/contracts/catalog-validate.md)."""

import json

from peo import cli

from .conftest import demo_tool


def run(capsys, *argv):
    code = cli.main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_a_valid_catalog_exits_0_with_a_summary(make_catalog, capsys):
    code, out, err = run(capsys, "catalog", "validate", str(make_catalog()))
    assert code == 0 and err == "" and "1 entries" in out


def test_json_envelope_has_sorted_keys_and_a_relative_root(make_catalog, capsys):
    root = make_catalog()
    code, out, _ = run(capsys, "--json", "catalog", "validate", str(root))
    env = json.loads(out)
    assert code == 0 and env["command"] == "catalog validate" and env["ok"] is True
    assert env["data"] == {"counts": {"capabilities": 2, "entries": 1, "opaque": 0, "questions": 0, "rules": 1},
                           "root": "catalog"}
    assert out.strip() == json.dumps(env, sort_keys=True)
    assert str(root.parent) not in out


def test_an_invalid_catalog_exits_1_with_e_catalog_invalid(make_catalog, capsys):
    root = make_catalog(tools={"demo": demo_tool().replace('data_path   = "none"\n', "")})
    code, out, err = run(capsys, "--json", "catalog", "validate", str(root))
    env = json.loads(out)
    assert code == 1 and env["ok"] is False
    assert {e["code"] for e in env["errors"]} == {"E_CATALOG_INVALID"}
    assert "tools/cli/demo.toml" in env["errors"][0]["message"] and "data_path" in out
    assert "E_CATALOG_INVALID" in err and str(root.parent) not in out + err


def test_two_runs_give_the_same_bytes(make_catalog, capsys):
    root = make_catalog(tools={"demo": demo_tool().replace('data_path   = "none"\n', "")})
    first = run(capsys, "--json", "catalog", "validate", str(root))
    assert first == run(capsys, "--json", "catalog", "validate", str(root))


def test_an_absent_folder_exits_2_with_e_catalog_not_found(tmp_path, capsys):
    code, out, _ = run(capsys, "--json", "catalog", "validate", str(tmp_path / "nowhere"))
    assert code == 2 and json.loads(out)["errors"][0]["code"] == "E_CATALOG_NOT_FOUND"
    assert str(tmp_path) not in out


def test_a_remote_catalog_exits_2(capsys):
    code, out, _ = run(capsys, "--json", "--catalog", "https://example.test/c@v1", "catalog", "validate")
    assert code == 2 and json.loads(out)["ok"] is False


def test_the_default_path_is_the_local_catalog_option(make_catalog, capsys):
    root = make_catalog()
    code, out, _ = run(capsys, "--json", "--catalog", str(root), "catalog", "validate")
    assert code == 0 and json.loads(out)["data"]["root"] == "catalog"


def test_catalog_show_stays_not_implemented(capsys):
    code, out, err = run(capsys, "catalog", "show", "cli:demo")
    assert code == 1 and "E_NOT_IMPLEMENTED" in err
