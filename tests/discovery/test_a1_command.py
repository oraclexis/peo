"""A1.1 through the command, A1.2, A1.6, A1.7; spec 16 §3."""

import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

import peo.cli
import peo.discovery
import peo.runner
from peo import cli
from peo.runner import Result
from peo.validate import load_schema, validate

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "fx-split-stack"
GOLDEN = json.loads((ROOT / "tests" / "golden" / "fx-split-stack" / "profile.json").read_text())
EXPECTED = {k: v for k, v in GOLDEN.items() if k != "generated"}
ON_PATH = {"node", "git"}
FIXTURE_SECRET = "fixture-not-a-secret"  # noqa: S105 - fake value planted by the fixture
NON_DECISION = {"docs_drift", "sensitive", "metrics", "present_tools", "gaps"}
LOCAL_GIT = {"ls-files", "log", "rev-list", "for-each-ref", "remote", "symbolic-ref", "rev-parse"}


def fake_which(name: str) -> str | None:
    return f"/usr/bin/{name}" if name in ON_PATH else None


@pytest.fixture(autouse=True)
def simulated_host(monkeypatch):
    monkeypatch.setattr(peo.cli, "which", fake_which, raising=False)


@pytest.fixture(scope="module")
def split_stack_repo(tmp_path_factory):
    target = tmp_path_factory.mktemp("fx") / "split-stack"
    subprocess.run(["bash", str(FIXTURE / "build.sh"), str(target)], check=True, capture_output=True)
    yield target
    shutil.rmtree(target, ignore_errors=True)


@pytest.fixture
def repo_copy(split_stack_repo, tmp_path):
    target = tmp_path / "copy"
    shutil.copytree(split_stack_repo, target, symlinks=True)
    return target


def run_discover(capsys, *argv):
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    env = json.loads(captured.out) if "--json" in argv else None
    return code, env, captured.out, captured.err


def decision_fields(node, top=True):
    """Every dict carrying `value`, outside the non-decision sections (spec 12 §8)."""
    if isinstance(node, dict):
        if "value" in node:
            yield node
        for key, child in node.items():
            if not (top and key in NON_DECISION):
                yield from decision_fields(child, top=False)
    elif isinstance(node, list):
        for child in node:
            yield from decision_fields(child, top=False)


def assert_decision_fields(data) -> int:
    fields = list(decision_fields(data))
    for f in fields:
        assert f.get("confidence") in {"fact", "likely", "unknown"}, f
        assert isinstance(f.get("evidence"), str) and f["evidence"], f
    return len(fields)


# --- US1: profile from the terminal or a skill ---------------------------------------------------

def test_a1_1_command_from_subdir_matches_golden(split_stack_repo, monkeypatch, capsys):
    monkeypatch.chdir(split_stack_repo / "backend")
    code, env, _, _ = run_discover(capsys, "discover", "--json")
    assert code == 0
    assert env["command"] == "discover"
    assert env["ok"] is True
    assert env["errors"] == []
    assert env["data"] == EXPECTED
    assert "generated" not in env["data"]


def test_root_from_deep_subdir(split_stack_repo, monkeypatch, capsys):
    monkeypatch.chdir(split_stack_repo / "backend/app/Http/Controllers/Api")
    _, env, _, _ = run_discover(capsys, "discover", "--json")
    assert env["data"] == EXPECTED


def test_a1_1_json_before_or_after_subcommand(split_stack_repo, monkeypatch, capsys):
    monkeypatch.chdir(split_stack_repo)
    _, _, before, _ = run_discover(capsys, "--json", "discover")
    _, _, after, _ = run_discover(capsys, "discover", "--json")
    assert before == after


def test_project_option_is_root_without_climbing(split_stack_repo, capsys):
    _, env, _, _ = run_discover(capsys, "--json", "discover", "--project",
                                str(split_stack_repo / "backend"))
    assert env["ok"] is True
    # backend/ is the root: one php component at ".", no node component from the git root.
    comps = [(c["path"], c["ecosystems"]) for c in env["data"]["components"]]
    assert comps == [(".", ["php"])]


def test_project_option_before_subcommand(split_stack_repo, capsys):
    _, env, _, _ = run_discover(capsys, "--project", str(split_stack_repo), "--json", "discover")
    assert env["data"] == EXPECTED


def test_outside_git_uses_cwd(tmp_path, monkeypatch, capsys):
    (tmp_path / "package.json").write_text('{"name": "x"}\n')
    monkeypatch.chdir(tmp_path)
    code, env, _, _ = run_discover(capsys, "--json", "discover")
    assert code == 0
    assert env["data"]["metrics"]["commits"] == 0


def test_manifest_unreadable_is_a_warning(tmp_path, monkeypatch, capsys):
    (tmp_path / "package.json").write_text("{")
    monkeypatch.chdir(tmp_path)
    code, env, _, err = run_discover(capsys, "--json", "discover")
    assert code == 0
    assert env["ok"] is True
    assert any(w["code"] == "W_MANIFEST_UNREADABLE" and w["path"] == "package.json"
               for w in env["warnings"])
    assert "W_MANIFEST_UNREADABLE package.json:" in err


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_project_not_found_exit_2(kind, tmp_path, capsys):
    target = tmp_path / "nope"
    if kind == "file":
        target.write_text("x")
    code, env, _, _ = run_discover(capsys, "--json", "discover", "--project", str(target))
    assert code == 2
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "E_PROJECT_NOT_FOUND"
    assert env["data"] == {}
    assert not list(tmp_path.rglob(".peo"))


def test_project_not_found_human_exit_2(tmp_path, capsys):
    code, _, out, err = run_discover(capsys, "discover", "--project", str(tmp_path / "nope"))
    assert code == 2
    assert out == ""
    assert "E_PROJECT_NOT_FOUND" in err


def test_unknown_option_exit_2(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["discover", "--bogus"])
    assert exc.value.code == 2


def test_a1_2_decision_fields_have_confidence_and_evidence(split_stack_repo, capsys):
    _, env, _, _ = run_discover(capsys, "--json", "discover", "--project", str(split_stack_repo))
    assert assert_decision_fields(env["data"]) == 15


def test_human_summary(split_stack_repo, monkeypatch, capsys):
    monkeypatch.chdir(split_stack_repo)
    code, _, out, _ = run_discover(capsys, "discover")
    assert code == 0
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)
    assert GOLDEN["kind"]["value"] in out
    lines = out.splitlines()
    for c in GOLDEN["components"]:
        assert any(c["id"] in line and c["path"] in line and c["runtime"]["value"] in line
                   for line in lines), c["id"]
    assert str(len(GOLDEN["docs_drift"])) in out
    assert "warning" in out


def test_stdout_deterministic(split_stack_repo, capsys):
    _, _, first, _ = run_discover(capsys, "--json", "discover", "--project", str(split_stack_repo))
    _, _, second, _ = run_discover(capsys, "--json", "discover", "--project", str(split_stack_repo))
    assert first == second


@pytest.mark.parametrize("command", ["discover", "status"])
def test_envelope_keys_sorted(command, split_stack_repo, monkeypatch, capsys):
    monkeypatch.chdir(split_stack_repo)
    cli.main(["--json", command])
    out = capsys.readouterr().out
    assert out == json.dumps(json.loads(out), sort_keys=True) + "\n"


@pytest.mark.parametrize("json_flag", [True, False])
def test_nf14_no_secret_in_outputs(json_flag, split_stack_repo, capsys):
    argv = ["discover", "--project", str(split_stack_repo)] + (["--json"] if json_flag else [])
    _, _, out, err = run_discover(capsys, *argv)
    assert FIXTURE_SECRET not in out
    assert FIXTURE_SECRET not in err


# --- US2: write the profile ----------------------------------------------------------------------

def written(root: Path) -> Path:
    return root / ".peo" / "profile.json"


def test_write_creates_profile(repo_copy, capsys):
    assert not (repo_copy / ".peo").exists()
    code, env, _, _ = run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    assert code == 0
    path = written(repo_copy)
    text = path.read_text()
    obj = json.loads(text)
    assert validate(obj, load_schema("profile")) == []
    assert text == json.dumps(obj, sort_keys=True, indent=2) + "\n"
    assert path.read_bytes().isascii()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", obj["generated"])
    umask = os.umask(0)
    os.umask(umask)
    assert stat.S_IMODE(path.stat().st_mode) == 0o666 & ~umask
    assert "generated" not in env["data"]
    assert env["data"] == {k: v for k, v in obj.items() if k != "generated"}


def test_write_twice_differs_only_by_generated(repo_copy, capsys):
    run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    first = written(repo_copy).read_text().splitlines()
    time.sleep(1.1)
    run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    second = written(repo_copy).read_text().splitlines()
    assert [line for line in first if '"generated"' not in line] == \
        [line for line in second if '"generated"' not in line]


def test_write_replaces_existing(repo_copy, capsys):
    (repo_copy / ".peo").mkdir()
    written(repo_copy).write_text('{"stale": 1}\n')
    code, _, _, _ = run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    assert code == 0
    assert "stale" not in json.loads(written(repo_copy).read_text())


def test_write_symlink_outside_root_exit_1(repo_copy, tmp_path, capsys):
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo_copy / ".peo").symlink_to(outside)
    code, env, _, _ = run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    assert code == 1
    assert env["errors"][0]["code"] == "E_WRITE_FAILED"
    assert env["data"] == {}
    assert list(outside.iterdir()) == []


def test_write_peo_is_a_file_exit_1(repo_copy, capsys):
    (repo_copy / ".peo").write_text("not a dir\n")
    before = set(repo_copy.rglob("*"))
    code, env, _, _ = run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    assert code == 1
    assert env["errors"][0]["code"] == "E_WRITE_FAILED"
    assert (repo_copy / ".peo").read_text() == "not a dir\n"
    assert set(repo_copy.rglob("*")) == before


def test_write_respects_umask(repo_copy, capsys):
    previous = os.umask(0o027)
    try:
        code, _, _, _ = run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    finally:
        os.umask(previous)
    assert code == 0
    assert stat.S_IMODE(written(repo_copy).stat().st_mode) == 0o640


def test_write_fsyncs_before_replace(repo_copy, monkeypatch, capsys):
    events = []
    fsync, replace = os.fsync, os.replace
    monkeypatch.setattr(os, "fsync", lambda fd: (events.append("fsync"), fsync(fd))[1])
    monkeypatch.setattr(os, "replace", lambda a, b: (events.append("replace"), replace(a, b))[1])
    code, _, _, _ = run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    assert code == 0
    assert events == ["fsync", "replace", "fsync"]   # file, rename, then .peo directory


def test_write_interrupted_leaves_no_temp_file(repo_copy, monkeypatch, capsys):
    def interrupt(*args):
        raise KeyboardInterrupt
    monkeypatch.setattr(os, "replace", interrupt)
    with pytest.raises(KeyboardInterrupt):
        cli.main(["--json", "discover", "--write", "--project", str(repo_copy)])
    assert list((repo_copy / ".peo").iterdir()) == []


def test_write_then_discover_outside_git_is_stable(tmp_path, capsys):
    (tmp_path / "package.json").write_text('{"name": "x"}\n')
    _, first, _, _ = run_discover(capsys, "--json", "discover", "--project", str(tmp_path))
    run_discover(capsys, "--json", "discover", "--write", "--project", str(tmp_path))
    _, second, _, _ = run_discover(capsys, "--json", "discover", "--project", str(tmp_path))
    assert (tmp_path / ".peo" / "profile.json").exists()
    assert second["data"] == first["data"]


def test_write_non_utf8_name_is_lossless(tmp_path):
    # A tracked file name that is not UTF-8 comes back from git as a lone surrogate.
    path = cli._write_profile(tmp_path, {"x": "caf\udce9"})
    assert path.read_bytes().isascii()
    assert json.loads(path.read_text())["x"] == "caf\udce9"


def test_write_leaves_the_umask_alone(repo_copy, monkeypatch, capsys):
    def no_umask(mask):
        raise AssertionError("process-wide umask changed")
    current = os.umask(0)
    os.umask(current)
    monkeypatch.setattr(os, "umask", no_umask)
    code, _, _, _ = run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    assert code == 0
    assert stat.S_IMODE(written(repo_copy).stat().st_mode) == 0o666 & ~current


def fake_discover(profile, warnings_out):
    def run(root, *, run, which, warnings):
        warnings += warnings_out
        return profile
    return run


MINIMAL = {"kind": {"value": "new"}, "components": [], "docs_drift": []}


def test_human_summary_survives_non_utf8_path(tmp_path, monkeypatch, capsys):
    profile = MINIMAL | {"components": [{"id": "x", "path": "caf\udce9", "runtime": {"value": "host"}}]}
    monkeypatch.setattr(peo.discovery, "discover", fake_discover(profile, []))
    assert cli.main(["discover", "--project", str(tmp_path)]) == 0
    assert "caf\\udce9" in capsys.readouterr().out


def test_warning_with_ref_goes_to_stderr(tmp_path, monkeypatch, capsys):
    warning = {"code": "W_CATALOG_EXPIRED", "ref": "mcp:serena", "message": "expired"}
    monkeypatch.setattr(peo.discovery, "discover", fake_discover(MINIMAL, [warning]))
    assert cli.main(["--json", "discover", "--project", str(tmp_path)]) == 0
    assert "W_CATALOG_EXPIRED mcp:serena: expired" in capsys.readouterr().err


def test_errors_on_stderr_with_json(tmp_path, capsys):
    code, _, _, err = run_discover(capsys, "--json", "discover", "--project", str(tmp_path / "nope"))
    assert code == 2
    assert re.search(r"^E_PROJECT_NOT_FOUND: ", err, re.M)


def test_git_root_keeps_trailing_space(monkeypatch):
    monkeypatch.setattr(peo.runner, "run", lambda args, cwd: Result(0, b"/work/proj \n", b""))
    assert cli._project_root(None) == Path("/work/proj ")


def test_cli_import_does_not_load_discovery():
    # NF4: peo gate and peo context go through cli.main; Discovery costs 30-60 ms to import.
    code = "import sys, peo.cli; print('peo.discovery' in sys.modules)"
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "False"


def test_symlink_loop_is_ignored(tmp_path, monkeypatch, capsys):
    # Python 3.11 and 3.12 raise RuntimeError from resolve() on a loop; 3.13 does not.
    (tmp_path / "package.json").write_text('{"name": "x"}\n')
    (tmp_path / "a").write_text("x\n")
    real = Path.resolve

    def loop(self, *args, **kwargs):
        if self.name == "a":
            raise RuntimeError(f"Symlink loop from {str(self)!r}")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", loop)
    code, env, _, _ = run_discover(capsys, "--json", "discover", "--project", str(tmp_path))
    assert code == 0
    assert env["data"]["metrics"]["tracked_files"] == 1


@pytest.mark.parametrize("target", ["docs", ".peo"])
def test_write_peo_symlink_refused(target, repo_copy, capsys):
    (repo_copy / "docs").mkdir(exist_ok=True)
    (repo_copy / ".peo").symlink_to(target)
    code, env, _, _ = run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    assert code == 1
    assert env["errors"][0]["code"] == "E_WRITE_FAILED"
    assert not (repo_copy / "docs" / "profile.json").exists()


def test_write_ignores_a_stale_temp_file(repo_copy, capsys):
    stale = repo_copy / ".peo" / f".profile.{os.getpid()}.tmp"
    stale.parent.mkdir()
    stale.write_text("other run\n")
    code, _, _, _ = run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    assert code == 0
    assert stale.read_text() == "other run\n"
    assert written(repo_copy).exists()


def test_write_directory_sync_is_best_effort(repo_copy, monkeypatch, capsys):
    calls = []
    fsync = os.fsync

    def flaky(fd):
        calls.append(fd)
        if len(calls) == 2:   # the .peo directory
            raise OSError(22, "Invalid argument")
        fsync(fd)

    monkeypatch.setattr(os, "fsync", flaky)
    code, _, _, _ = run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    assert code == 0
    assert len(calls) == 2
    assert json.loads(written(repo_copy).read_text())["kind"]


def test_stderr_escapes_control_characters(tmp_path, monkeypatch, capsys):
    warning = {"code": "W_MANIFEST_UNREADABLE", "path": "pkg\nE_FAKE: ok\x1b[31m/package.json",
               "message": "bad\nline"}
    monkeypatch.setattr(peo.discovery, "discover", fake_discover(MINIMAL, [warning]))
    assert cli.main(["--json", "discover", "--project", str(tmp_path)]) == 0
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert "\x1b" not in err
    assert err.startswith("W_MANIFEST_UNREADABLE pkg\\nE_FAKE: ok\\u001b[31m/package.json: bad\\nline")


def test_warning_without_path_or_ref(tmp_path, monkeypatch, capsys):
    warning = {"code": "W_X", "message": "m"}
    monkeypatch.setattr(peo.discovery, "discover", fake_discover(MINIMAL, [warning]))
    assert cli.main(["--json", "discover", "--project", str(tmp_path)]) == 0
    assert "None" not in capsys.readouterr().err


def test_git_root_not_utf8(monkeypatch):
    raw = b"/tmp/caf\xe9"
    monkeypatch.setattr(peo.runner, "run", lambda args, cwd: Result(0, raw + b"\n", b""))
    assert cli._project_root(None) == Path(os.fsdecode(raw))


def test_write_human_output_names_path(repo_copy, capsys):
    code, _, out, _ = run_discover(capsys, "discover", "--write", "--project", str(repo_copy))
    assert code == 0
    assert str(Path(".peo") / "profile.json") in out


def test_write_on_new_repo_is_valid(tmp_path, capsys):
    # fx-new (spec 16 §2): empty repository, one commit; spec 12 rule 11 gives one bare root.
    env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "PATH": os.environ["PATH"],
           "GIT_AUTHOR_NAME": "A", "GIT_AUTHOR_EMAIL": "a@example.test",
           "GIT_COMMITTER_NAME": "A", "GIT_COMMITTER_EMAIL": "a@example.test"}
    git = ["git", "-C", str(tmp_path), "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
    for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(git + args, check=True, capture_output=True, env=env)
    code, out, _, _ = run_discover(capsys, "--json", "discover", "--write", "--project", str(tmp_path))
    assert code == 0
    root = out["data"]["components"]
    assert [(c["id"], c["ecosystems"], c["paths"]["code"]) for c in root] == [("root", [], [])]
    assert validate(json.loads(written(tmp_path).read_text()), load_schema("profile")) == []


def test_nf14_no_secret_in_written_file(repo_copy, capsys):
    run_discover(capsys, "--json", "discover", "--write", "--project", str(repo_copy))
    assert FIXTURE_SECRET not in written(repo_copy).read_text()


# --- US3: offline and fast -----------------------------------------------------------------------

def test_a1_6_no_socket(split_stack_repo, monkeypatch, capsys):
    def refuse(*args, **kwargs):
        raise AssertionError("network access")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    code, _, _, _ = run_discover(capsys, "--json", "--project", str(split_stack_repo), "discover")
    assert code == 0


def test_a1_6_only_local_git_commands(split_stack_repo, monkeypatch, capsys):
    calls = []
    original = peo.runner.run

    def recorder(args, cwd, *rest, **kwargs):
        calls.append(list(args))
        return original(args, cwd, *rest, **kwargs)

    monkeypatch.setattr(peo.runner, "run", recorder)
    monkeypatch.chdir(split_stack_repo)
    code, _, _, _ = run_discover(capsys, "--json", "discover")
    assert code == 0
    assert calls
    for args in calls:
        assert args[0] == "git" and args[1] in LOCAL_GIT, args
    assert ["git", "rev-parse", "--show-toplevel"] in calls


@pytest.fixture(scope="module")
def large_repo(tmp_path_factory):
    target = tmp_path_factory.mktemp("fx-large")
    (target / "package.json").write_text('{"name": "fx-large", "version": "1.0.0"}\n')
    body = "".join(f"// line {n}\n" for n in range(100))
    exts = ("ts", "vue", "php", "py")
    for i in range(1000):
        d = target / "src" / f"m{i // 100}"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"f{i}.{exts[i % 4]}").write_text(body)
    env = {k: v for k, v in os.environ.items()
           if k not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG_COUNT",
                        "GIT_CONFIG_PARAMETERS"}}
    env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="Fixture Author", GIT_COMMITTER_NAME="Fixture Author",
               GIT_AUTHOR_EMAIL="author@example.test", GIT_COMMITTER_EMAIL="author@example.test",
               GIT_AUTHOR_DATE="@1772438400 +0000", GIT_COMMITTER_DATE="@1772438400 +0000")
    git = ["git", "-C", str(target), "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "feat: large"]):
        subprocess.run(git + args, check=True, capture_output=True, env=env)
    yield target
    shutil.rmtree(target, ignore_errors=True)


def test_a1_7_fx_large_under_5s(large_repo, capsys):
    start = time.perf_counter()
    code = cli.main(["--json", "--project", str(large_repo), "discover"])
    elapsed = time.perf_counter() - start
    env = json.loads(capsys.readouterr().out)
    assert code == 0
    assert elapsed < 5
    assert env["data"]["metrics"]["loc_total"] == 100000


def test_a1_2_on_fx_large(large_repo, capsys):
    _, env, _, _ = run_discover(capsys, "--json", "--project", str(large_repo), "discover")
    assert_decision_fields(env["data"])
