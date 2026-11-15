"""Exposure audit, spec 16 F14 (R3): A14.1 to A14.3, A14.7 to A14.25; spec 15 §7.

Tests that expect `covered` pass platform "Darwin" and a fake runner answering 2.1.325
(research R5). Each test that produces an output checks it against status.schema.json.
"""

import builtins
import io
import json
import pathlib
import re
import secrets
import shutil
import subprocess
import time
from pathlib import Path

import pytest

import peo.exposure as ex
import peo.runner
import peo.status as st
from peo import cli
from tests.fxlarge import build_large
from tests.status.conftest import (
    DECOY,
    ROOT,
    FakeRunner,
    check,
    codes,
    findings,
    git,
    make_repo,
    settings,
    write,
)

GITHUB = ROOT / "tests" / "fixtures" / "fx-ci-github"
GITLAB = ROOT / "tests" / "fixtures" / "fx-ci-gitlab"
HOSTILE = ROOT / "tests" / "fixtures" / "fx-hostile"
CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]")
PROTECTED = re.compile(r"protect|protégé", re.IGNORECASE)


def one(data, code):
    found = findings(data, code)
    assert len(found) == 1, found
    return found[0]


def audited(data, path):
    return next(a for a in data["exposure"]["audited"] if a["path"] == path)


def env_repo(tmp_path, files=None, track=()):
    return make_repo(tmp_path / "project", {"backend/.env": "APP_KEY=x\n", **(files or {})},
                     track=track)


def cli_run(capsys, monkeypatch, *argv, runner=None):
    monkeypatch.setattr(peo.runner, "run", runner or FakeRunner())
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --- A14.3 and A14.24: fx-split-stack in its four states -------------------------------------

def test_a14_3_no_settings(split_stack, run_status):
    out = run_status(split_stack)
    readable = one(out, "X-SECRET-READABLE")
    assert (readable["path"], readable["suggested_rule"], readable["confidence"],
            readable["severity"]) == ("backend/.env", "Read(./backend/.env)", "fact", "error")
    assert one(out, "X-NO-SECRET-SCAN")["evidence"] == ["no CI file"]
    assert one(out, "X-SANDBOX-OFF")["severity"] == "warning"
    store = one(out, "X-DATA-STORE")
    assert "db" in store["message"] and store["evidence"] == ["docker-compose.yml services.db postgres"]


def test_a14_3_rule_committed(split_stack, run_status):
    settings(split_stack, ["Read(./backend/.env)"], tracked=True, committed=True)
    out = run_status(split_stack)
    assert not codes(out) & {"X-SECRET-READABLE", "X-COVERAGE-NOT-SHARED"}
    off = one(out, "X-SANDBOX-OFF")
    assert "files covered by a deny Read rule: backend/.env" in off["message"]
    assert "effect on Bash is not verified" in off["message"]
    assert "excludedCommands" not in json.dumps(off)


def test_a14_3_rule_untracked(split_stack, run_status):
    settings(split_stack, ["Read(./backend/.env)"], tracked=False, committed=False)
    out = run_status(split_stack)
    assert "X-SECRET-READABLE" not in codes(out)
    shared = one(out, "X-COVERAGE-NOT-SHARED")
    assert (shared["path"], shared["rule"], shared["source"]) == (
        "backend/.env", "Read(./backend/.env)", "settings:project")
    assert "tracked false" in shared["evidence"]


def test_a14_3_rule_not_committed(split_stack, run_status):
    settings(split_stack, [], tracked=True, committed=True)
    settings(split_stack, ["Read(./backend/.env)"], tracked=False, committed=False)
    out = run_status(split_stack)
    project = next(s for s in out["inventory"]["sources"] if s["id"] == "settings:project")
    assert (project["tracked"], project["modified"]) == (True, True)
    assert "modified true" in one(out, "X-COVERAGE-NOT-SHARED")["evidence"]


def test_a14_5_repository_filter_never_runs(split_stack, run_status, tmp_path):
    settings(split_stack, ["Read(./backend/.env)"], tracked=True, committed=True)
    marker = tmp_path / "filter-ran"
    write(split_stack, {".gitattributes": ".claude/settings.json filter=fixture\n"})
    git(split_stack, "config", "filter.fixture.clean", f"touch {marker}; cat")
    settings(split_stack, ["Read(./backend/.env)", "Read(./x)"], tracked=False, committed=False)
    out = run_status(split_stack)
    assert not marker.exists()
    project = next(s for s in out["inventory"]["sources"] if s["id"] == "settings:project")
    assert project["modified"] is True


def test_a14_24_covered_path_is_audited(split_stack, run_status):
    settings(split_stack, ["Read(./backend/.env)"], tracked=True, committed=True)
    out = run_status(split_stack)
    assert out["exposure"]["audited"] == [{"path": "backend/.env", "kind": "secret_file",
                                           "verdict": "covered", "reason": None,
                                           "rule": "Read(./backend/.env)",
                                           "source": "settings:project"}]
    assert not [f for f in findings(out) if f.get("path") == "backend/.env"]


def test_a14_24_one_entry_per_sensitive_path(tmp_path, run_status):
    root = env_repo(tmp_path, {"b.sql": "x", "a/.env": "A=1\n", "storage/logs/x.log": "x"})
    paths = [a["path"] for a in run_status(root)["exposure"]["audited"]]
    assert paths == ["a/.env", "b.sql", "backend/.env", "storage/logs"]


# --- verdicts other than covered -------------------------------------------------------------

def test_a14_11_case_only_is_likely(tmp_path, run_status):
    root = env_repo(tmp_path)
    settings(root, ["Read(./backend/.ENV)"], tracked=True, committed=True)
    f = one(run_status(root), "X-SECRET-READABLE")
    assert (f["status"], f["confidence"], f["reason"], f["rule"]) == (
        "applied", "likely", "case-only", "Read(./backend/.ENV)")


def test_a14_14_rule_on_the_link_is_undecidable(tmp_path, run_status):
    root = make_repo(tmp_path / "project", {"backend/real.env": "A=1\n"})
    (root / "backend" / ".env").symlink_to("real.env")
    settings(root, ["Read(./backend/.env)"], tracked=True, committed=True)
    f = one(run_status(root), "X-SECRET-READABLE")
    assert (f["path"], f["reason"], f["confidence"]) == ("backend/.env", "symlink", "likely")
    assert f["suggested_rule"] == "Read(./backend/real.env)"   # the target, compared alone


def test_a14_14_rule_on_the_target_covers(tmp_path, run_status):
    root = make_repo(tmp_path / "project", {"backend/real.env": "A=1\n"})
    (root / "backend" / ".env").symlink_to("real.env")
    settings(root, ["Read(./backend/real.env)"], tracked=True, committed=True)
    out = run_status(root)
    assert "X-SECRET-READABLE" not in codes(out)
    assert audited(out, "backend/.env")["verdict"] == "covered"


def test_a14_15_bracket_path_has_no_suggested_rule(tmp_path, run_status):
    root = make_repo(tmp_path / "project", {"pages/[id]/.env": "A=1\n"})
    f = one(run_status(root), "X-SECRET-READABLE")
    assert f["path"] == "pages/[id]/.env" and "suggested_rule" not in f
    assert "by hand" in f["message"]


def test_a14_16_older_claude_version(tmp_path, run_status):
    root = env_repo(tmp_path)
    settings(root, ["Read(./backend/.env)"], tracked=True, committed=True)
    f = one(run_status(root, FakeRunner(version=b"2.1.300 (Claude Code)\n")), "X-SECRET-READABLE")
    assert (f["confidence"], f["reason"]) == ("likely", "untested-version")


def test_a14_17_link_outside_verdict(tmp_path, run_status):
    outside = write(tmp_path / "elsewhere", {"secret.env": f"OUTSIDE={DECOY}x\n"})
    root = make_repo(tmp_path / "project", {"backend/app.php": "<?php\n"})
    (root / "backend" / ".env").symlink_to(outside / "secret.env")
    settings(root, ["Read(./backend/.env)"], tracked=True, committed=True)
    out = run_status(root)
    f = one(out, "X-SECRET-READABLE")
    assert (f["path"], f["reason"], f["confidence"]) == ("backend/.env", "symlink-outside", "likely")
    assert str(outside) not in json.dumps(out) and "secret.env" not in json.dumps(out)


def test_a14_19_log_dir_suggested_rule(tmp_path, run_status):
    root = make_repo(tmp_path / "project", {"storage/logs/app.log": "x"})
    f = one(run_status(root), "X-DATA-READABLE")
    assert (f["path"], f["suggested_rule"], f["severity"]) == (
        "storage/logs", "Read(./storage/logs/**)", "warning")


def test_a14_21_nested_settings(tmp_path, run_status):
    root = env_repo(tmp_path, {"backend/.claude/settings.json": {"permissions": {
        "deny": ["Read(./.env)"]}}})
    out = run_status(root)
    f = one(out, "X-SECRET-READABLE")
    assert (f["confidence"], f["reason"]) == ("likely", "nested-settings")
    assert "backend/.claude/settings.json: nested settings not read" in f["evidence"]
    assert "L-NESTED-SETTINGS" in out["limits"]


def test_linux_without_table_untested_platform(tmp_path, run_status):
    assert ex.load_table("Linux") is None
    assert ex.load_table("Windows") is None and ex.load_table("Darwin") is not None
    root = env_repo(tmp_path)
    settings(root, ["Read(./backend/.env)"], tracked=True, committed=True)
    out = run_status(root, platform="Linux")
    assert audited(out, "backend/.env")["verdict"] == "undecidable"
    assert one(out, "X-SECRET-READABLE")["reason"] == "untested-platform"


# --- A14.1: one test per X-* code of R3 not covered above -------------------------------------

def test_a14_1_secret_tracked(tmp_path, run_status):
    root = env_repo(tmp_path, track=["backend/.env"])
    f = one(run_status(root), "X-SECRET-TRACKED")
    assert (f["path"], f["severity"], f["status"]) == ("backend/.env", "error", "applied")


def test_a14_25_tracked_link_outside_is_a_warning(tmp_path, run_status):
    outside = write(tmp_path / "elsewhere", {"secret.env": "A=1\n"})
    root = make_repo(tmp_path / "project", {"README.md": "x\n"})
    (root / "backend").mkdir()
    (root / "backend" / ".env").symlink_to(outside / "secret.env")
    git(root, "add", "-f", "backend/.env")
    git(root, "commit", "-q", "-m", "link")
    linked = one(run_status(root), "X-SECRET-TRACKED")
    assert linked["severity"] == "warning" and "symbolic link" in linked["message"]
    plain = one(run_status(env_repo(tmp_path / "other", track=["backend/.env"])),
                "X-SECRET-TRACKED")
    assert plain["message"] != linked["message"]


def test_a14_1_data_readable(tmp_path, run_status):
    root = make_repo(tmp_path / "project", {"dump.sql": "x"})
    f = one(run_status(root), "X-DATA-READABLE")
    assert (f["path"], f["suggested_rule"]) == ("dump.sql", "Read(./dump.sql)")


def test_a14_1_sandbox_fallback(tmp_path, run_status):
    root = env_repo(tmp_path, {".claude/settings.json": {"sandbox": {"enabled": True}}},
                    track=[".claude/settings.json"])
    out = run_status(root)
    assert "X-SANDBOX-OFF" not in codes(out)
    f = one(out, "X-SANDBOX-FALLBACK")
    assert (f["severity"], f["confidence"], f["source"]) == ("warning", "fact", "settings:project")
    assert "failIfUnavailable is absent" in f["message"]


def test_a14_1_sandbox_closed_has_no_finding(tmp_path, run_status):
    sandbox = {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False}
    root = env_repo(tmp_path, {".claude/settings.json": {"sandbox": sandbox}},
                    track=[".claude/settings.json"])
    assert not codes(run_status(root)) & {"X-SANDBOX-OFF", "X-SANDBOX-FALLBACK"}


def test_a14_1_sandbox_off_info_with_docker_and_no_secret(tmp_path, run_status):
    compose = "services:\n  api:\n    build: ./backend\n  db:\n    image: postgres:16\n"
    root = make_repo(tmp_path / "project", {"docker-compose.yml": compose,
                                            "backend/composer.json": {"require": {"laravel/framework": "^11.0"}}},
                     track=["docker-compose.yml", "backend/composer.json"])
    out = run_status(root)
    assert one(out, "X-SANDBOX-OFF")["severity"] == "info"


MCP = {"mcpServers": {"github": {"command": "npx", "args": ["-y", "server-github"],
                                 "env": {"GITHUB_TOKEN": f"{DECOY}token"}},
                      "db": {"command": "npx",
                             "args": ["-y", "pg", f"postgresql://u:{DECOY}pw@h/db"]},
                      "plain": {"command": "npx", "env": {"NODE_ENV": "production"}}}}


def test_a14_1_literal_in_agent_config(tmp_path, run_status):
    root = make_repo(tmp_path / "project", {".mcp.json": MCP}, track=[".mcp.json"])
    found = findings(run_status(root), "X-LITERAL-IN-AGENT-CONFIG")
    assert [(f["source"], f["index"], f["name"], f["status"]) for f in found] == [
        ("mcp:project", 0, "github", "applied"), ("mcp:project", 1, "db", "applied")]
    assert all(f["severity"] == "error" for f in found)


def test_a14_1_literal_untracked_is_not_evaluated(tmp_path, run_status):
    root = make_repo(tmp_path / "project", {".mcp.json": MCP})
    assert "X-LITERAL-IN-AGENT-CONFIG" not in codes(run_status(root))


def test_a14_1_literal_tracked_null_is_skipped(tmp_path, run_status):
    root = write(tmp_path / "not-git", {".mcp.json": MCP})
    f = one(run_status(root), "X-LITERAL-IN-AGENT-CONFIG")
    assert (f["status"], f["source"]) == ("skipped", "mcp:project") and "path" not in f


def test_a14_1_literal_args_kept_when_values_invalid(tmp_path, run_status):
    mcp = {"mcpServers": {"a": {"command": "x", "args": [f"postgres://u:{DECOY}pw@h/db"],
                                "env": "not an object"}}}
    root = make_repo(tmp_path / "project", {".mcp.json": mcp}, track=[".mcp.json"])
    found = findings(run_status(root), "X-LITERAL-IN-AGENT-CONFIG")
    assert sorted(f["status"] for f in found) == ["applied", "skipped"]
    assert next(f for f in found if f["status"] == "applied")["index"] == 0


def test_a14_1_mcp_unevaluated(tmp_path, run_status):
    root = make_repo(tmp_path / "project", {".mcp.json": MCP}, track=[".mcp.json"])
    found = findings(run_status(root), "X-MCP-UNEVALUATED")
    assert [(f["name"], f["index"], f["plugin_index"], f["severity"]) for f in found] == [
        ("github", 0, None, "info"), ("db", 1, None, "info"), ("plain", 2, None, "info")]


# --- A14.9: X-NO-SECRET-SCAN on hand-written CI files ----------------------------------------

@pytest.mark.parametrize(("folder", "case", "dest", "found"), [
    (GITHUB, "run.yml", ".github/workflows/run.yml", False),
    (GITHUB, "uses.yml", ".github/workflows/uses.yml", False),
    (GITHUB, "precommit.yaml", ".pre-commit-config.yaml", False),
    (GITLAB, "script.yml", ".gitlab-ci.yml", False),
    (GITLAB, "image.yml", ".gitlab-ci.yml", False),
    (GITLAB, "image-name.yml", ".gitlab-ci.yml", False),
    (GITLAB, "template.yml", ".gitlab-ci.yml", False),
    (GITHUB, "name-only.yml", ".github/workflows/name-only.yml", True),
    (GITHUB, "comment.yml", ".github/workflows/comment.yml", True),
    (GITLAB, "comment.yml", ".gitlab-ci.yml", True)])
def test_a14_9_secret_scan_tokens(tmp_path, run_status, folder, case, dest, found):
    root = make_repo(tmp_path / "project", {dest: (folder / case).read_text()}, track=[dest])
    out = run_status(root)
    assert ("X-NO-SECRET-SCAN" in codes(out)) is found
    if found:
        assert one(out, "X-NO-SECRET-SCAN")["evidence"] == [dest]


@pytest.mark.parametrize("kind", ["outside-link", "too-large", "nul"])
def test_a14_9_unreadable_ci_file_is_likely(tmp_path, run_status, kind):
    dest = ".github/workflows/ci.yml"
    root = make_repo(tmp_path / "project", {"README.md": "x\n"})
    if kind == "outside-link":
        outside = write(tmp_path / "elsewhere", {"ci.yml": "run: gitleaks detect\n"})
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / dest).symlink_to(outside / "ci.yml")
    else:
        write(root, {dest: b"run: x\n" * 200_000 if kind == "too-large" else b"run: \0gitleaks\n"})
    git(root, "add", "-f", dest)
    git(root, "commit", "-q", "-m", "ci")
    f = one(run_status(root), "X-NO-SECRET-SCAN")
    assert (f["confidence"], f["reason"], f["evidence"]) == (
        "likely", "source-unreadable", [f"{dest} unreadable"])


def test_a14_9_untracked_workflow_is_ignored(tmp_path, run_status):
    root = make_repo(tmp_path / "project", {".github/workflows/run.yml": (GITHUB / "run.yml").read_text()})
    assert one(run_status(root), "X-NO-SECRET-SCAN")["evidence"] == ["no CI file"]


# --- A14.12, A14.13, A14.18, A14.20, A14.22: unreadable sources and limits --------------------

def test_a14_12_user_settings_unreadable(tmp_path, run_status, machine):
    (machine["user_config"] / "settings.json").write_text("{not json")
    f = one(run_status(env_repo(tmp_path)), "X-SECRET-READABLE")
    assert (f["status"], f["confidence"], f["reason"]) == ("applied", "likely", "source-unreadable")
    assert "settings:user invalid json: source-unreadable" in f["evidence"]


def test_a14_12_project_flags_invalid_fallback_unknown(tmp_path, run_status):
    root = env_repo(tmp_path, {".claude/settings.local.json": {"sandbox": {"enabled": True}},
                               ".claude/settings.json": {"sandbox": {"enabled": "yes"}}})
    f = one(run_status(root), "X-SANDBOX-FALLBACK")
    assert (f["confidence"], f["reason"]) == ("likely", "source-unreadable")
    assert "settings:project invalid_families flags: source-unreadable" in f["evidence"]


def limits(run_status, root, run=None):
    return set(run_status(root, run)["limits"])


def test_a14_13_launch_root(tmp_path, run_status):
    assert "L-LAUNCH-ROOT" not in limits(run_status, env_repo(tmp_path / "a"))
    root = env_repo(tmp_path / "b", {".claude/settings.local.json": {}})
    assert "L-LAUNCH-ROOT" in limits(run_status, root)


def test_a14_13_covered_limits(tmp_path, run_status):
    bare = limits(run_status, env_repo(tmp_path / "a"))
    assert not bare & {"L-GREP-GLOB", "L-CASE-SENSITIVITY", "L-CLAUDE-NEWER"}
    root = env_repo(tmp_path / "b")
    settings(root, ["Read(./backend/.env)"], tracked=True, committed=True)
    found = limits(run_status, root)
    assert {"L-GREP-GLOB", "L-CASE-SENSITIVITY"} <= found and "L-CLAUDE-NEWER" not in found
    assert "L-CLAUDE-NEWER" in limits(run_status, root, FakeRunner(version=b"2.1.400 (Claude Code)"))


def test_a14_13_nested_settings(tmp_path, run_status):
    assert "L-NESTED-SETTINGS" not in limits(run_status, env_repo(tmp_path / "a"))
    root = env_repo(tmp_path / "b", {"web/.claude/settings.local.json": {}})
    assert "L-NESTED-SETTINGS" in limits(run_status, root)


def test_a14_13_mcp_approval(tmp_path, run_status):
    assert "L-MCP-APPROVAL" not in limits(run_status, env_repo(tmp_path / "a"))
    root = env_repo(tmp_path / "b", {".mcp.json": {"mcpServers": {"x": {"command": "npx"}}}})
    assert "L-MCP-APPROVAL" in limits(run_status, root)


def test_a14_13_discovery_depth(tmp_path, run_status):
    assert "L-DISCOVERY-DEPTH" not in limits(run_status, env_repo(tmp_path / "a"))
    assert "L-DISCOVERY-DEPTH" in limits(run_status, env_repo(tmp_path / "b", {"a/b/c/d/x.txt": "x"}))


def test_a14_13_symlink_dir_listed_in_human_output(tmp_path, run_status):
    assert "L-SYMLINK-DIR" not in limits(run_status, env_repo(tmp_path / "a"))
    root = env_repo(tmp_path / "b")
    (root / "linked").symlink_to("backend")
    out = run_status(root)
    assert "L-SYMLINK-DIR" in out["limits"] and out["exposure"]["linked_dirs"] == ["linked"]
    lines = st.render(out).splitlines()
    i = lines.index("limit L-SYMLINK-DIR: " + st.LIMITS["L-SYMLINK-DIR"])
    assert lines[i + 1] == "  linked"


def test_a14_13_http_hook(tmp_path, run_status):
    assert "L-HTTP-HOOK" not in limits(run_status, env_repo(tmp_path / "a"))
    hooks = {"hooks": {"PostToolUse": [{"hooks": [{"type": "http", "url": "https://h.example.test"}]}]}}
    root = env_repo(tmp_path / "b", {".claude/settings.json": hooks})
    assert "L-HTTP-HOOK" in limits(run_status, root)


def test_a14_18_server_managed_always(tmp_path, run_status):
    root = env_repo(tmp_path)
    assert "L-SERVER-MANAGED" in run_status(root)["limits"]
    assert "L-SERVER-MANAGED" in run_status(root, exposure=False)["limits"]


def test_a14_20_claude_absent_skips_plugin_codes(tmp_path, run_status):
    out = run_status(env_repo(tmp_path), FakeRunner(version_rc=127, version=b""))
    skipped = sorted((f["code"], f["source"]) for f in findings(out) if f["status"] == "skipped")
    assert ("S-PLUGIN-ERROR", "claude") in skipped and ("X-MCP-UNEVALUATED", "claude") in skipped
    assert [f for f in findings(out, "X-MCP-UNEVALUATED") if f["source"] == "claude"][0].get(
        "path") is None


def test_a14_22_tracked_secret_at_any_depth(tmp_path, run_status):
    files = {"a/b/c/d/.env": "A=1\n", "build/.env": "B=1\n", "x/y/z/w/.env.local": "C=1\n"}
    root = make_repo(tmp_path / "project", files, track=["a/b/c/d/.env", "build/.env"])
    out = run_status(root)
    assert sorted(f["path"] for f in findings(out, "X-SECRET-TRACKED")) == ["a/b/c/d/.env", "build/.env"]
    assert not [f for f in findings(out) if f.get("path") == "x/y/z/w/.env.local"]
    assert "L-DISCOVERY-DEPTH" in out["limits"]
    assert out["limits"] == sorted(out["limits"])


# --- A14.2, A14.8, A14.17, A14.23: no value, no "protected", no escape ------------------------

def decoyed_split_stack(split_stack):
    decoys = [f"{DECOY}{secrets.token_hex(8)}" for _ in range(5)]
    write(split_stack, {"backend/.env": f"APP_KEY={decoys[0]}\nexport DB_PASSWORD='{decoys[1]}'\n",
                        ".mcp.json": {"mcpServers": {"remote": {
                            "type": "http", "url": f"https://u:{decoys[2]}@h.example.test/x",
                            "headers": {"Authorization": f"Bearer {decoys[3]}"}},
                            "local": {"command": "npx", "args": ["-y", decoys[4]],
                                      "env": {"API_TOKEN": decoys[0]}}}}})
    git(split_stack, "add", "-f", ".mcp.json")
    git(split_stack, "commit", "-q", "-m", "mcp")
    return decoys


def snapshot(root: Path) -> dict:
    return {p: p.lstat().st_mtime_ns for p in root.rglob("*") if ".git" not in p.parts}


def test_a14_2_no_value_in_any_output(split_stack, capsys, monkeypatch):
    decoys = decoyed_split_stack(split_stack)
    outputs = []
    for argv in (["--json", "--project", str(split_stack), "discover", "--write"],
                 ["--json", "--project", str(split_stack), "status", "--exposure"],
                 ["--project", str(split_stack), "status", "--exposure"]):
        before = snapshot(split_stack) if "status" in argv else None
        code, out, err = cli_run(capsys, monkeypatch, *argv)
        assert code == 0
        outputs += [out, err]
        if before is not None:
            assert snapshot(split_stack) == before   # status writes nothing
    outputs += [p.read_text() for p in (split_stack / ".peo").rglob("*") if p.is_file()]
    assert len(outputs) > 6
    text = "\n".join(outputs)
    assert [d for d in decoys if d in text] == []
    assert DECOY not in text


def test_a14_8_wording(split_stack, tmp_path, run_status):
    texts = []
    for rules, tracked, committed in ((None, False, False), (["Read(./backend/.env)"], True, True),
                                      (["Read(./backend/.env)"], False, False)):
        root = tmp_path / f"copy{len(texts)}"
        shutil.copytree(split_stack, root, symlinks=True)
        if rules:
            settings(root, rules, tracked=tracked, committed=committed)
        out = run_status(root)
        texts += [json.dumps(out), st.render(out)]
    decoyed_split_stack(split_stack)
    out = run_status(split_stack)
    texts += [json.dumps(out), st.render(out)]
    assert [t for t in texts if PROTECTED.search(t)] == []
    assert [line for line in st.LIMITS.values() if PROTECTED.search(line)] == []


@pytest.fixture
def opened(monkeypatch):
    seen: list[str] = []
    for owner, name in ((builtins, "open"), (io, "open"), (pathlib.Path, "open")):
        real = getattr(owner, name)

        def spy(file, *args, _real=real, **kwargs):
            seen.append(str(file))
            return _real(file, *args, **kwargs)
        monkeypatch.setattr(owner, name, spy)
    return seen


def test_a14_17_outside_target_never_opened(tmp_path, run_status, opened):
    outside = write(tmp_path / "elsewhere", {"secret.env": f"OUTSIDE_NAME={DECOY}x\n"})
    root = make_repo(tmp_path / "project", {"backend/app.php": "<?php\n"})
    (root / "backend" / ".env").symlink_to(outside / "secret.env")
    opened.clear()
    out = run_status(root)
    text = json.dumps(out) + st.render(out)
    link = str(root.resolve() / "backend" / ".env")
    assert [p for p in opened if p.startswith(str(outside)) or p in (link, str(root / "backend/.env"))] == []
    assert str(outside) not in text and "OUTSIDE_NAME" not in text and DECOY not in text


@pytest.fixture
def hostile(tmp_path):
    target = tmp_path / "hostile"
    subprocess.run(["bash", str(HOSTILE / "build.sh"), str(target)], check=True, capture_output=True)
    return target


def test_a14_23_hostile_names_escaped(hostile, capsys, monkeypatch):
    code, human, err = cli_run(capsys, monkeypatch, "--project", str(hostile), "status", "--exposure")
    assert code == 0
    assert CONTROL.findall(human) == [] and CONTROL.findall(err) == []
    assert "bad\\x0a\\x1bdir/.env" in human
    code, out, _ = cli_run(capsys, monkeypatch, "--json", "--project", str(hostile), "status",
                           "--exposure")
    data = check(json.loads(out)["data"])
    bad = "bad\n\x1bdir/.env"
    assert bad in [a["path"] for a in data["exposure"]["audited"]]
    assert [f for f in findings(data) if f.get("path") == bad and "suggested_rule" in f] == []
    project = next(s for s in data["inventory"]["sources"] if s["id"] == "settings:project")
    assert (project["status"], project["reason"]) == ("invalid", "json")


# --- A14.7, A14.10: CI exit code and duration -------------------------------------------------

def test_a14_7_ci_exit_3_on_tracked_secret(tmp_path, capsys, monkeypatch):
    root = env_repo(tmp_path, track=["backend/.env"])
    code, _, _ = cli_run(capsys, monkeypatch, "--project", str(root), "status", "--exposure", "--ci")
    assert code == cli.EXIT_STATUS_FINDINGS == 3
    code, _, _ = cli_run(capsys, monkeypatch, "--project", str(root), "status", "--exposure")
    assert code == 0


@pytest.fixture(scope="module")
def large(tmp_path_factory):
    target = build_large(tmp_path_factory.mktemp("fx-large"))
    yield target
    shutil.rmtree(target, ignore_errors=True)


def test_a14_10_fx_large_under_5s(large, capsys, monkeypatch):
    start = time.perf_counter()
    code, out, _ = cli_run(capsys, monkeypatch, "--json", "--project", str(large), "status",
                           "--exposure")
    elapsed = time.perf_counter() - start
    assert code == 0 and elapsed < 5, elapsed
    data = check(json.loads(out)["data"])
    assert audited(data, "backend/.env")["verdict"] == "covered"
