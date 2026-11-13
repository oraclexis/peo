"""A3.1 to A3.11 and the cross-cutting Inventory tests; spec 14 §3, spec 16 F3."""

import json
import os
import pathlib
import sys
import threading
import time

import pytest

import peo.inventory as inv
from peo.runner import Result
from peo.validate import load_schema, validate
from tests.inventory.conftest import MISSING, VERSION_OK, UnexpectedMachineAccess, plugin_list

DECOY = "fixture-not-a-secret-"  # noqa: S105 - marker of every fake value planted by a test
NO_CLAUDE = {("claude", "--version"): MISSING}
PLUGIN_LIST = ("claude", "plugin", "list", "--json")
NOT_INSPECTED_FIXED = {"settings:managed-other", "settings:cli", "mcp:local", "mcp:user"}


def git(*files, tracked=(), rc=0):
    """Response of `git ls-files -z -- <files>` listing `tracked`."""
    out = b"".join(f.encode() + b"\0" for f in tracked)
    return {("git", "ls-files", "-z", "--", *files): Result(rc, out, b"")}


def check(out):
    assert validate(out, load_schema("inventory")) == []
    assert DECOY not in json.dumps(out)
    return out


def source(out, sid):
    return next(s for s in out["sources"] if s["id"] == sid)


def of(out, key, src):
    return [e for e in out[key] if e["source"] == src]


def full(fake_run, root, plugins_dir, extra=None):
    return fake_run({("claude", "--version"): VERSION_OK,
                     PLUGIN_LIST: Result(0, plugin_list(plugins_dir, root), b""), **(extra or {})})


def one_plugin(fake_run, root, plugin, extra=None):
    return fake_run({("claude", "--version"): VERSION_OK,
                     PLUGIN_LIST: Result(0, json.dumps([plugin]).encode(), b""), **(extra or {})})


# A3.1 and A3.2: plugins from `claude plugin list --json`

def test_a3_1_plugins_full_mode(project, fake_run, user_config, managed, tmp_path):
    root = project()
    run = full(fake_run, root, tmp_path / "plugins")
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    claude = of(out, "plugins", "claude")
    by_index = {p["index"]: p for p in claude}
    assert sorted(by_index) == [0, 1, 2, 4, 5, 6, 7, 8, 9, 10]
    assert all(p["confidence"] == "fact" for p in claude)
    assert by_index[0] == {"source": "claude", "index": 0, "id": "user-plugin@market", "scope": "user",
                           "enabled": True, "error_count": 0, "confidence": "fact"}
    assert by_index[1]["scope"] == "managed" and by_index[2]["scope"] == "project"
    assert source(out, "claude")["status"] == "read" and out["claude_version"] == "2.1.325"
    plugin0 = source(out, "plugin:#0")
    assert plugin0 == {"id": "plugin:#0", "scope": "user", "path": "plugin:#0/hooks/hooks.json",
                       "status": "read", "reason": None, "tracked": None, "invalid_families": []}
    assert of(out, "hooks", "plugin:#0") == [{
        "source": "plugin:#0", "event": "PreToolUse", "matcher": "Edit|Write", "type": "command",
        "on_failure": "block", "group_index": 0, "hook_index": 0}]
    servers = of(out, "mcp_servers", "claude")
    assert [(s["plugin_index"], s["index"], s["name"]) for s in servers] == [
        (6, 0, "fixture-db"), (6, 1, "serena")]
    assert servers[0]["args_hint"] == "url-userinfo" and servers[0]["tool_ref"] is None
    assert not any(s["id"] == "plugin:*" for s in out["sources"])


def test_a3_1_disabled_plugin(project, fake_run, user_config, managed, tmp_path):
    root = project()
    out = check(inv.inventory(root, run=full(fake_run, root, tmp_path / "plugins"),
                              user_config=user_config, managed=managed))
    assert source(out, "plugin:#4") == {
        "id": "plugin:#4", "scope": "user", "path": None, "status": "not_inspected",
        "reason": "disabled", "tracked": None, "invalid_families": []}
    assert of(out, "hooks", "plugin:#4") == []
    assert next(p for p in out["plugins"] if p["index"] == 4 and p["source"] == "claude")["enabled"] is False


def test_a3_1_rejected_id_keeps_source_and_hooks(project, fake_run, user_config, managed, tmp_path):
    root = project()
    out = check(inv.inventory(root, run=full(fake_run, root, tmp_path / "plugins"),
                              user_config=user_config, managed=managed))
    assert next(p for p in of(out, "plugins", "claude") if p["index"] == 7)["id"] is None
    assert source(out, "plugin:#7")["status"] == "read"
    assert len(of(out, "hooks", "plugin:#7")) == 1


def test_a3_1_scopes_other_and_synced(project, fake_run, user_config, managed, tmp_path):
    root = project()
    out = check(inv.inventory(root, run=full(fake_run, root, tmp_path / "plugins"),
                              user_config=user_config, managed=managed))
    claude = {p["index"]: p for p in of(out, "plugins", "claude")}
    assert claude[8]["scope"] == "other" and source(out, "plugin:#8")["scope"] == "other"
    assert claude[9]["scope"] == "synced" and source(out, "plugin:#9")["scope"] == "synced"


def test_a3_1_error_count(project, fake_run, user_config, managed, tmp_path):
    root = project()
    out = check(inv.inventory(root, run=full(fake_run, root, tmp_path / "plugins"),
                              user_config=user_config, managed=managed))
    claude = {p["index"]: p for p in of(out, "plugins", "claude")}
    assert claude[0]["error_count"] == 0 and claude[1]["error_count"] == 0
    assert claude[5]["error_count"] == 2


def test_a3_1_project_enabled_is_ignored(project, fake_run, user_config, managed, tmp_path):
    root = project()
    out = check(inv.inventory(root, run=full(fake_run, root, tmp_path / "plugins"),
                              user_config=user_config, managed=managed))
    claude = {p["index"]: p for p in of(out, "plugins", "claude")}
    assert claude[10]["enabled"] is True and claude[10]["scope"] == "local"


def test_a3_1_user_plugin_without_user_config(project, fake_run, managed, tmp_path):
    root = project()
    out = check(inv.inventory(root, run=full(fake_run, root, tmp_path / "plugins"),
                              user_config=None, managed=managed))
    assert any(p["scope"] == "user" for p in of(out, "plugins", "claude"))
    assert source(out, "settings:user")["reason"] == "not-provided"


def test_a3_1_claude_commands_run_at_root(project, fake_run, user_config, managed, tmp_path):
    root = project()
    run = full(fake_run, root, tmp_path / "plugins")
    check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert run.calls == [(("claude", "--version"), root), (PLUGIN_LIST, root)]


def test_a3_2_other_project_plugin_absent(project, fake_run, user_config, managed, tmp_path):
    root = project()
    out = check(inv.inventory(root, run=full(fake_run, root, tmp_path / "plugins"),
                              user_config=user_config, managed=managed))
    assert all(p["index"] != 3 for p in of(out, "plugins", "claude"))
    assert not any(s["id"] == "plugin:#3" for s in out["sources"])
    assert "other-project" not in json.dumps(out)


# A3.3: hooks

def test_a3_3_hooks_entries(project, fake_run, user_config, managed):
    root = project({".claude/settings.json": {"hooks": {
        "PreToolUse": [
            {"matcher": "Edit|Write", "hooks": [
                {"type": "command", "command": "fixture-not-a-secret-a", "onFailure": "block"},
                {"type": "http", "url": "https://h/fixture-not-a-secret-b", "onFailure": "continue"}]},
            {"hooks": [{"type": "command", "command": "x", "onFailure": None}]}],
        "Stop": [{"matcher": "fixture-not-a-secret-=x", "hooks": [
            {"type": "fixture-not-a-secret-kind"}, {"type": "prompt", "prompt": "p", "onFailure": "fail"}]}],
    }}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    hooks = of(out, "hooks", "settings:project")
    assert [(h["event"], h["group_index"], h["hook_index"], h["matcher"], h["type"], h["on_failure"])
            for h in hooks] == [
        ("PreToolUse", 0, 0, "Edit|Write", "command", "block"),
        ("PreToolUse", 0, 1, "Edit|Write", "http", "continue"),
        ("PreToolUse", 1, 0, None, "command", "other"),
        ("Stop", 0, 0, "other", "other", None),
        ("Stop", 0, 1, "other", "prompt", "other"),
    ]


def test_a3_3_hooks_cuj3_local_hook(project, fake_run, user_config, managed):
    root = project({".claude/settings.local.json": {"hooks": {"PreToolUse": [{"hooks": [
        {"type": "command", "command": "API_KEY=fixture-not-a-secret-cuj3 ./check.sh"}]}]}}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.local.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert out["hooks"] == [{"source": "settings:local", "event": "PreToolUse", "matcher": None,
                             "type": "command", "on_failure": None, "group_index": 0, "hook_index": 0}]
    assert "check.sh" not in json.dumps(out)


# A3.5: states and reasons of the claude source

@pytest.mark.parametrize("version, status, reason, emitted", [
    (Result(127, b"", b""), "absent", None, None),
    (Result(0, b"2.1.284 (Claude Code)\n", b""), "unavailable", "claude-too-old", "2.1.284"),
    (Result(0, b"fixture-not-a-secret-version\n", b""), "unavailable", "version-unparsed", None),
    (Result(1, b"fixture-not-a-secret-out", b"fixture-not-a-secret-err"), "unavailable",
     "command-failed", None),
])
def test_a3_5_claude_version_states(project, fake_run, user_config, managed, version, status,
                                     reason, emitted):
    root = project()
    out = check(inv.inventory(root, run=fake_run({("claude", "--version"): version}),
                              user_config=user_config, managed=managed))
    assert (source(out, "claude")["status"], source(out, "claude")["reason"]) == (status, reason)
    assert out["claude_version"] == emitted
    assert source(out, "plugin:*") == {"id": "plugin:*", "scope": None, "path": None,
                                       "status": "not_inspected", "reason": "degraded",
                                       "tracked": None, "invalid_families": []}
    assert not any(s["id"].startswith("plugin:#") for s in out["sources"])


def test_a3_5_claude_minimum_version_is_full_mode(project, fake_run, user_config, managed):
    root = project()
    run = fake_run({("claude", "--version"): Result(0, b"2.1.285 (Claude Code)\n", b""),
                    PLUGIN_LIST: Result(0, b"[]", b"")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert source(out, "claude")["status"] == "read" and out["claude_version"] == "2.1.285"
    assert not any(s["id"] == "plugin:*" for s in out["sources"])


@pytest.mark.parametrize("listing, reason", [
    (Result(1, b"fixture-not-a-secret-out", b"fixture-not-a-secret-err"), "command-failed"),
    (Result(127, b"", b""), "timeout-or-missing"),
    (Result(0, b"fixture-not-a-secret-not-json", b""), "output-unparsed"),
    (Result(0, b'[{"id": "a@b", "scope": "user", "installPath": "/x"}]', b""), "output-unparsed"),
])
def test_a3_5_plugin_list_states(project, fake_run, user_config, managed, listing, reason):
    root = project()
    run = fake_run({("claude", "--version"): VERSION_OK, PLUGIN_LIST: listing})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert (source(out, "claude")["status"], source(out, "claude")["reason"]) == ("unavailable", reason)
    assert out["claude_version"] == "2.1.325"
    assert source(out, "plugin:*")["reason"] == "degraded"
    assert of(out, "plugins", "claude") == []


@pytest.mark.parametrize("responses", [
    {("claude", "--version"): OSError("fixture-not-a-secret-oserror")},
    {("claude", "--version"): VERSION_OK, PLUGIN_LIST: OSError("fixture-not-a-secret-oserror")},
])
def test_a3_5_claude_oserror(project, fake_run, user_config, managed, responses):
    root = project()
    out = check(inv.inventory(root, run=fake_run(responses), user_config=user_config, managed=managed))
    assert (source(out, "claude")["status"], source(out, "claude")["reason"]) == (
        "unavailable", "command-failed")
    assert source(out, "plugin:*")["reason"] == "degraded"


# A3.5: states and reasons of files

def _user_state(fake_run, root, user_config, managed):
    out = check(inv.inventory(root, run=fake_run(NO_CLAUDE), user_config=user_config, managed=managed))
    s = source(out, "settings:user")
    return s["status"], s["reason"]


def test_a3_5_file_too_large(project, fake_run, user_config, managed, monkeypatch):
    (user_config / "settings.json").write_bytes(b'{"a": "' + b"x" * (4 * 1024 * 1024) + b'"}')
    read = []
    real_open = pathlib.Path.open

    class Spy:
        def __init__(self, f):
            self.f = f

        def read(self, n=-1):
            data = self.f.read(n)
            read.append(len(data))
            return data

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.f.close()

    monkeypatch.setattr(pathlib.Path, "open", lambda self, *a, **k: Spy(real_open(self, *a, **k)))
    assert _user_state(fake_run, project(), user_config, managed) == ("invalid", "too-large")
    assert sum(read) <= 1_048_577


@pytest.mark.parametrize("content", [b'{"a": "\x00"}', b'{"a": "\xff\xfe"}'])
def test_a3_5_file_binary(project, fake_run, user_config, managed, content):
    (user_config / "settings.json").write_bytes(content)
    assert _user_state(fake_run, project(), user_config, managed) == ("invalid", "binary")


@pytest.mark.parametrize("content", [b"fixture-not-a-secret-json {", b"[" * 100_000])
def test_a3_5_file_json(project, fake_run, user_config, managed, content):
    (user_config / "settings.json").write_bytes(content)
    assert _user_state(fake_run, project(), user_config, managed) == ("invalid", "json")


def test_a3_5_file_not_object(project, fake_run, user_config, managed):
    (user_config / "settings.json").write_text("[1, 2]")
    assert _user_state(fake_run, project(), user_config, managed) == ("invalid", "not-object")


@pytest.mark.parametrize("target", ["/dev/zero", "directory"])
def test_a3_5_file_not_regular(project, fake_run, user_config, managed, tmp_path, target):
    if target == "directory":
        (tmp_path / "a-directory").mkdir()
        target = tmp_path / "a-directory"
    (user_config / "settings.json").symlink_to(target)
    root = project()
    inventory = inv.inventory  # looked up here: an error in the thread would be lost
    result = []
    thread = threading.Thread(daemon=True, target=lambda: result.append(
        inventory(root, run=fake_run(NO_CLAUDE), user_config=user_config, managed=managed)))
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    s = source(check(result[0]), "settings:user")
    assert (s["status"], s["reason"]) == ("invalid", "not-regular")


def test_a3_5_project_file_outside_root(project, fake_run, user_config, managed, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text('{"mcpServers": {}}')
    root = project()
    (root / ".mcp.json").symlink_to(outside)
    run = fake_run({**NO_CLAUDE, **git(".mcp.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    s = source(out, "mcp:project")
    assert (s["status"], s["reason"], s["path"]) == ("invalid", "not-regular", ".mcp.json")


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_a3_5_file_permission_denied(project, fake_run, user_config, managed):
    path = user_config / "settings.json"
    path.write_text("{}")
    path.chmod(0)
    try:
        assert _user_state(fake_run, project(), user_config, managed) == (
            "unavailable", "permission-denied")
    finally:
        path.chmod(0o600)


def test_a3_5_not_inspected_out_of_scope(project, fake_run, user_config, managed):
    root = project()
    out = check(inv.inventory(root, run=fake_run(NO_CLAUDE), user_config=user_config, managed=managed))
    for sid in NOT_INSPECTED_FIXED:
        s = source(out, sid)
        assert (s["status"], s["reason"], s["path"]) == ("not_inspected", "out-of-scope", None)
    assert [s["id"] for s in out["sources"]] == [
        "settings:managed", "settings:managed.d", "settings:managed-other", "settings:cli",
        "settings:local", "settings:project", "settings:user", "mcp:managed", "mcp:local",
        "mcp:project", "mcp:user", "claude", "plugin:*"]


def test_a3_5_not_provided(project, fake_run):
    root = project()
    out = check(inv.inventory(root, run=fake_run(NO_CLAUDE), user_config=None, managed=None))
    for sid in ("settings:managed", "settings:managed.d", "settings:user", "mcp:managed"):
        s = source(out, sid)
        assert (s["status"], s["reason"], s["path"]) == ("not_inspected", "not-provided", None)
    assert sum(s["id"].startswith("settings:managed.d") for s in out["sources"]) == 1


def test_a3_5_empty_user_config_is_absent(project, fake_run, user_config, managed):
    assert _user_state(fake_run, project(), user_config, managed) == ("absent", None)


def test_a3_5_cuj2_ci_without_claude(project, fake_run, user_config):
    root = project({".claude/settings.json": {"enabledPlugins": {"egm@egm": True}},
                    ".mcp.json": {"mcpServers": {"github": {"command": "npx", "args": ["x"]}}}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.json", ".mcp.json",
                                       tracked=[".claude/settings.json", ".mcp.json"])})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=None))
    assert source(out, "settings:project")["status"] == "read"
    assert source(out, "mcp:project")["status"] == "read"
    assert source(out, "settings:user")["status"] == "absent"
    assert source(out, "claude")["status"] == "absent"
    assert source(out, "plugin:*")["reason"] == "degraded"
    assert out["plugins"] == [{"source": "settings:project", "index": 0, "id": "egm@egm", "scope": None,
                               "enabled": True, "error_count": None, "confidence": "likely"}]


def test_a3_5_managed_d_absent(project, fake_run, user_config, managed):
    out = check(inv.inventory(project(), run=fake_run(NO_CLAUDE), user_config=user_config,
                              managed=managed))
    s = source(out, "settings:managed.d")
    assert (s["status"], s["reason"], s["path"]) == ("absent", None, None)


def test_a3_5_managed_d_empty(project, fake_run, user_config, managed):
    (managed / "managed-settings.d").mkdir()
    (managed / "managed-settings.d" / "README").write_text("not json")
    out = check(inv.inventory(project(), run=fake_run(NO_CLAUDE), user_config=user_config,
                              managed=managed))
    assert [s for s in out["sources"] if s["id"].startswith("settings:managed.d")] == [{
        "id": "settings:managed.d", "scope": "managed", "status": "read", "reason": None,
        "path": str(managed / "managed-settings.d"), "tracked": None, "invalid_families": []}]


def test_a3_5_managed_d_files(project, fake_run, user_config, managed):
    folder = managed / "managed-settings.d"
    folder.mkdir()
    (folder / "10-base.json").write_text('{"disableAllHooks": true}')
    (folder / "20-fixture-not-a-secret-name.json").write_text('{"sandbox": {"enabled": true}}')
    (folder / "30-ignored.txt").write_text('{"disableAllHooks": false}')
    out = check(inv.inventory(project(), run=fake_run(NO_CLAUDE), user_config=user_config,
                              managed=managed))
    d = [s for s in out["sources"] if s["id"].startswith("settings:managed.d")]
    assert [(s["id"], s["path"], s["status"]) for s in d] == [
        ("settings:managed.d/#0", str(folder / "#0"), "read"),
        ("settings:managed.d/#1", str(folder / "#1"), "read")]
    assert out["flags"] == [
        {"source": "settings:managed.d/#0", "key": "disableAllHooks", "value": True},
        {"source": "settings:managed.d/#1", "key": "sandbox.enabled", "value": True}]


# A3.6: rules, flags, invalid families

def test_a3_6_rules_kept_and_ignored(project, fake_run, user_config, managed):
    root = project({".claude/settings.json": {"permissions": {
        "allow": ["WebFetch(domain:docs.example.test)", "WebFetch(domain:localhost:3000)"],
        "ask": ["Edit(./src/**)", "Bash(curl -H 'Authorization: fixture-not-a-secret-bash')"],
        "deny": ["Read(./a)", "Read", "Write(./b)", "mcp__x__y"]}}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert [(r["list"], r["rule"]) for r in out["permission_rules"]] == [
        ("allow", "WebFetch(domain:docs.example.test)"), ("allow", "WebFetch(domain:localhost:3000)"),
        ("ask", "Edit(./src/**)"), ("deny", "Read(./a)"), ("deny", "Read"), ("deny", "Write(./b)")]
    assert "Bash" not in json.dumps(out)


def test_a3_6_flags_by_scope(project, fake_run, user_config, managed):
    flags = {"sandbox": {"enabled": True, "failIfUnavailable": False,
                         "allowUnsandboxedCommands": True}, "disableAllHooks": False}
    (managed / "managed-settings.json").write_text(json.dumps({**flags, "allowManagedHooksOnly": True}))
    (user_config / "settings.json").write_text(json.dumps({"disableAllHooks": True}))
    root = project({".claude/settings.local.json": {"sandbox": {"enabled": False}},
                    ".claude/settings.json": {"allowManagedHooksOnly": True,
                                              "sandbox": {"failIfUnavailable": True}}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.local.json", ".claude/settings.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert [(f["source"], f["key"], f["value"]) for f in out["flags"]] == [
        ("settings:managed", "allowManagedHooksOnly", True),
        ("settings:managed", "disableAllHooks", False),
        ("settings:managed", "sandbox.allowUnsandboxedCommands", True),
        ("settings:managed", "sandbox.enabled", True),
        ("settings:managed", "sandbox.failIfUnavailable", False),
        ("settings:local", "sandbox.enabled", False),
        ("settings:project", "sandbox.failIfUnavailable", True),
        ("settings:user", "disableAllHooks", True)]
    assert source(out, "settings:managed")["path"] == str(managed / "managed-settings.json")


def test_a3_6_flags_allow_managed_hooks_only_ignored_in_project(project, fake_run, user_config, managed):
    root = project({".claude/settings.json": {"allowManagedHooksOnly": True}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert out["flags"] == []
    assert source(out, "settings:project")["invalid_families"] == []


SETTINGS_ALL_FAMILIES = {
    "permissions": {"deny": ["Read(./x)"]},
    "sandbox": {"enabled": True},
    "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]},
    "enabledPlugins": {"egm@egm": True},
    "env": {"NODE_ENV": "test"},
}


@pytest.mark.parametrize("family, broken", [
    ("permissions", {"permissions": {"deny": ["Read(./x)", "Read(\nfixture-not-a-secret-rule"]}}),
    ("flags", {"sandbox": {"enabled": "true"}}),
    ("plugins", {"enabledPlugins": {"egm@egm": True, "b@c": "yes"}}),
    ("values", {"env": ["fixture-not-a-secret-env"]}),
])
def test_a3_6_invalid_family_settings(project, fake_run, user_config, managed, family, broken):
    root = project({".claude/settings.json": {**SETTINGS_ALL_FAMILIES, **broken}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert source(out, "settings:project")["invalid_families"] == [family]
    counts = {"permissions": len(of(out, "permission_rules", "settings:project")),
              "flags": len(of(out, "flags", "settings:project")),
              "hooks": len(of(out, "hooks", "settings:project")),
              "plugins": len(of(out, "plugins", "settings:project")),
              "values": len(of(out, "values", "settings:project"))}
    assert counts == {k: 0 if k == family else 1 for k in counts}


def test_a3_6_invalid_family_hooks(project, fake_run, user_config, managed):
    root = project({".claude/settings.json": {
        "env": {"NODE_ENV": "test"},
        "hooks": {
            "PostToolUse": [{"hooks": [{"type": "http", "url": "https://h/fixture-not-a-secret-u",
                                        "headers": {"Authorization": "fixture-not-a-secret-h"}}]}],
            "fixture-not-a-secret:event": [{"hooks": [{"type": "command", "command": "x"}]}]}}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert source(out, "settings:project")["invalid_families"] == ["hooks"]
    assert out["hooks"] == []
    assert [v["location"] for v in out["values"]] == ["env"]


def test_a3_6_invalid_family_mcp_file(project, fake_run, user_config, managed):
    root = project({".mcp.json": {"mcpServers": ["fixture-not-a-secret-server"]}})
    run = fake_run({**NO_CLAUDE, **git(".mcp.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert source(out, "mcp:project")["invalid_families"] == ["mcp"]
    assert out["mcp_servers"] == []


def test_a3_6_invalid_family_mcp_plugin(project, fake_run, user_config, managed, tmp_path):
    root = project()
    hooks = tmp_path / "p" / "hooks" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    hooks.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}}))
    run = one_plugin(fake_run, root, {"id": "a@b", "scope": "user", "enabled": True,
                                      "installPath": str(tmp_path / "p"),
                                      "mcpServers": "fixture-not-a-secret-mcp"})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert source(out, "claude")["invalid_families"] == ["mcp"]
    assert source(out, "claude")["status"] == "read"
    assert out["mcp_servers"] == []
    assert source(out, "plugin:#0")["status"] == "read"
    assert len(of(out, "hooks", "plugin:#0")) == 1
    assert len(of(out, "plugins", "claude")) == 1


# A3.7: value forms

def test_a3_7_value_forms(project, fake_run, user_config, managed):
    root = project({".mcp.json": {"mcpServers": {"github": {
        "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"A_EMPTY": "", "B_REF": "${GH}", "C_REF_EMPTY_DEFAULT": "${GH:-}",
                "D_DEFAULT": "${GH:-fixture-not-a-secret-default}", "E_INTERP": "Bearer ${GH}",
                "F_LIT": "fixture-not-a-secret-literal", "G_INT": 5,
                "GITHUB_TOKEN": "fixture-not-a-secret-ghp"},
        "headers": {"Authorization": "Bearer fixture-not-a-secret-auth",
                    "Cookie": "session=fixture-not-a-secret-cookie"}}}}})
    run = fake_run({**NO_CLAUDE, **git(".mcp.json", tracked=[".mcp.json"])})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    forms = {(v["location"], v["key"]): (v["form"], v["sensitive_name"]) for v in out["values"]}
    assert forms == {
        ("mcp#0.env", "A_EMPTY"): ("empty", False),
        ("mcp#0.env", "B_REF"): ("reference", False),
        ("mcp#0.env", "C_REF_EMPTY_DEFAULT"): ("reference", False),
        ("mcp#0.env", "D_DEFAULT"): ("literal", False),
        ("mcp#0.env", "E_INTERP"): ("interpolated", False),
        ("mcp#0.env", "F_LIT"): ("literal", False),
        ("mcp#0.env", "G_INT"): ("literal", False),
        ("mcp#0.env", "GITHUB_TOKEN"): ("literal", True),
        ("mcp#0.headers", "Authorization"): ("literal", True),
        ("mcp#0.headers", "Cookie"): ("literal", True),
    }
    assert source(out, "mcp:project")["tracked"] is True
    assert all(v["source"] == "mcp:project" for v in out["values"])


# A3.8: tracked

PROJECT_FILES = {".claude/settings.local.json": {}, ".claude/settings.json": {}, ".mcp.json": {}}
GIT_KEY = ("git", "ls-files", "-z", "--", ".claude/settings.local.json", ".claude/settings.json",
           ".mcp.json")


def test_a3_8_tracked_true_and_false(project, fake_run, user_config, managed):
    root = project(PROJECT_FILES)
    run = fake_run({**NO_CLAUDE, GIT_KEY: Result(0, b".claude/settings.json\0.mcp.json\0", b"")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert [source(out, s)["tracked"] for s in ("settings:local", "settings:project", "mcp:project")] == [
        False, True, True]
    assert source(out, "settings:user")["tracked"] is None


@pytest.mark.parametrize("answer", [Result(128, b"", b"fatal"), Result(1, b".mcp.json\0", b""),
                                    OSError("fixture-not-a-secret-git")])
def test_a3_8_tracked_null_when_git_fails(project, fake_run, user_config, managed, answer):
    root = project(PROJECT_FILES)
    out = check(inv.inventory(root, run=fake_run({**NO_CLAUDE, GIT_KEY: answer}),
                              user_config=user_config, managed=managed))
    assert [source(out, s)["tracked"] for s in ("settings:local", "settings:project", "mcp:project")] == [
        None, None, None]


def test_a3_8_tracked_null_for_absent_source(project, fake_run, user_config, managed):
    root = project({".mcp.json": {}})
    run = fake_run({**NO_CLAUDE, **git(".mcp.json", tracked=[".mcp.json"])})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert source(out, "settings:project")["status"] == "absent"
    assert source(out, "settings:project")["tracked"] is None
    assert source(out, "mcp:project")["tracked"] is True


def test_a3_8_no_git_call_without_project_source(project, fake_run, user_config, managed):
    root = project()
    run = fake_run(NO_CLAUDE)
    check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert [c[0][0] for c in run.calls] == ["claude"]


# A3.9: decoys never leave the Inventory

def test_a3_9_mcp_decoys(project, fake_run, user_config, managed):
    root = project({".mcp.json": {"mcpServers": {
        "local": {"command": "npx", "args": ["-y", "fixture-not-a-secret-pkg",
                                             "postgresql://u:fixture-not-a-secret-pw@h/db"],
                  "env": {"API_TOKEN": "fixture-not-a-secret-env"}},
        "remote": {"type": "http", "url": "https://u:fixture-not-a-secret-url@h.example.test/x",
                   "headers": {"X-Api-Key": "fixture-not-a-secret-header"},
                   "headersHelper": "fixture-not-a-secret-helper.sh"},
        "fixture-not-a-secret/name": {"command": "x"}}}})
    run = fake_run({**NO_CLAUDE, **git(".mcp.json", tracked=[".mcp.json"])})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    servers = out["mcp_servers"]
    assert [(s["name"], s["transport"], s["args_hint"]) for s in servers] == [
        ("local", "stdio", "url-userinfo"), ("remote", "http", None), (None, "stdio", None)]
    entry = next(v for v in out["values"] if v["key"] == "API_TOKEN")
    assert (entry["form"], entry["sensitive_name"]) == ("literal", True)
    url = next(v for v in out["values"] if v["key"] == "url")
    assert (url["location"], url["value_hint"]) == ("mcp#1.url", "url-userinfo")
    assert "h.example.test" not in json.dumps(out)


def test_a3_9_hook_decoys(project, fake_run, user_config, managed):
    root = project({".claude/settings.json": {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
        {"type": "command", "command": "fixture-not-a-secret-cmd", "args": ["fixture-not-a-secret-arg"]},
        {"type": "prompt", "prompt": "fixture-not-a-secret-prompt", "model": "x"},
        {"type": "agent", "prompt": "fixture-not-a-secret-agent"},
        {"type": "mcp_tool", "server": "s", "tool": "t", "input": {"q": "fixture-not-a-secret-input"}},
        {"type": "http", "url": "https://fixture-not-a-secret-host.test/h",
         "headers": {"Authorization": "fixture-not-a-secret-bearer"}}]}]}}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert [h["type"] for h in out["hooks"]] == ["command", "prompt", "agent", "mcp_tool", "http"]
    assert [(v["location"], v["key"]) for v in out["values"]] == [
        ("hook:PreToolUse#0.4.headers", "Authorization"), ("hook:PreToolUse#0.4.url", "url")]


def test_a3_9_plugin_decoys(project, fake_run, user_config, managed, tmp_path):
    root = project()
    out = check(inv.inventory(root, run=full(fake_run, root, tmp_path / "plugins"),
                              user_config=user_config, managed=managed))
    text = json.dumps(out)
    assert str(tmp_path / "plugins") not in text
    assert "postgresql" not in text and "DB_TOKEN" in text


def test_a3_9_bash_rule_decoy(project, fake_run, user_config, managed):
    root = project({".claude/settings.json": {"permissions": {"allow": [
        'Bash(curl -H "Authorization: Bearer fixture-not-a-secret-token" *)']}}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert out["permission_rules"] == []


def test_a3_9_out_of_grammar_names(project, fake_run, user_config, managed):
    (managed / "managed-settings.d").mkdir()
    (managed / "managed-settings.d" / "fixture-not-a-secret-file=x.json").write_text("{}")
    root = project({
        ".claude/settings.json": {
            "env": {"fixture-not-a-secret=key": "x"},
            "enabledPlugins": {"fixture-not-a-secret:plugin@m": True},
            "hooks": {"Stop": [{"matcher": "fixture-not-a-secret/matcher",
                                "hooks": [{"type": "command", "command": "x"}]}]}},
        ".claude/settings.local.json": {"hooks": {"fixture-not-a-secret:event": []}},
        ".mcp.json": {"mcpServers": {"fixture-not-a-secret:server": {"command": "x"}}}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.local.json", ".claude/settings.json",
                                       ".mcp.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert out["values"][0]["key"] is None
    assert out["plugins"][0]["id"] is None
    assert out["hooks"][0]["matcher"] == "other"
    assert out["mcp_servers"][0]["name"] is None
    assert source(out, "settings:local")["invalid_families"] == ["hooks"]
    assert source(out, "settings:managed.d/#0")["status"] == "read"


def test_a3_9_invalid_json_and_command_outputs(project, fake_run, user_config, managed):
    (user_config / "settings.json").write_text('{"env": {"A": "fixture-not-a-secret-json"')
    for listing in (Result(1, b"fixture-not-a-secret-stdout", b"fixture-not-a-secret-stderr"),
                    Result(0, b"[fixture-not-a-secret-listing", b"")):
        run = fake_run({("claude", "--version"): VERSION_OK, PLUGIN_LIST: listing})
        check(inv.inventory(project(), run=run, user_config=user_config, managed=managed))
    run = fake_run({("claude", "--version"): Result(0, b"fixture-not-a-secret-v 2.1.300", b"")})
    check(inv.inventory(project(), run=run, user_config=user_config, managed=managed))


# A3.10: identify

def test_a3_10_identify_projection_and_answer(project, fake_run, user_config, managed, tmp_path):
    root = project({".mcp.json": {"mcpServers": {"serena": {"command": "serena", "args": ["x"]},
                                                 "other": {"command": "npx", "args": ["pkg"]}}}})
    seen = []

    def identify(projection):
        seen.append(projection)
        return "mcp:serena" if projection["command_name"] == "serena" else None

    run = full(fake_run, root, tmp_path / "plugins", git(".mcp.json"))
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed,
                              identify=identify))
    assert all(set(p) == {"transport", "launcher", "package", "command_name", "url_host"} for p in seen)
    assert len(seen) == 4
    refs = {(s["source"], s["plugin_index"], s["name"]): s["tool_ref"] for s in out["mcp_servers"]}
    assert refs == {("mcp:project", None, "serena"): "mcp:serena", ("mcp:project", None, "other"): None,
                    ("claude", 6, "fixture-db"): None, ("claude", 6, "serena"): "mcp:serena"}


def test_a3_10_identify_absent_or_bad_answer(project, fake_run, user_config, managed):
    root = project({".mcp.json": {"mcpServers": {"serena": {"command": "serena"}}}})
    run = fake_run({**NO_CLAUDE, **git(".mcp.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert out["mcp_servers"][0]["tool_ref"] is None
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed,
                              identify=lambda p: "mcp:fixture-not-a-secret-ref\n"))
    assert out["mcp_servers"][0]["tool_ref"] is None


def test_a3_10_identify_exception_propagates(project, fake_run, user_config, managed):
    root = project({".mcp.json": {"mcpServers": {"serena": {"command": "serena"}}}})
    run = fake_run({**NO_CLAUDE, **git(".mcp.json")})

    def identify(projection):
        raise ValueError("caller bug")

    with pytest.raises(ValueError):
        inv.inventory(root, run=run, user_config=user_config, managed=managed, identify=identify)


# A3.11: declared()

def test_a3_11_declared(project, fake_run, user_config, managed, tmp_path):
    (user_config / "settings.json").write_text('{"enabledPlugins": {"user@m": true}}')
    root = project({".claude/settings.json": {"enabledPlugins": {"a@m": True, "x@y": False}},
                    ".claude/settings.local.json": {"enabledPlugins": {"local@m": True}},
                    ".mcp.json": {"mcpServers": {"github": {"command": "npx", "args": ["x"]}}}})
    run = full(fake_run, root, tmp_path / "plugins", git(
        ".claude/settings.local.json", ".claude/settings.json", ".mcp.json",
        tracked=[".claude/settings.local.json", ".claude/settings.json", ".mcp.json"]))
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    declared = inv.declared(out)
    assert declared == {"plugins": of(out, "plugins", "settings:project"),
                        "mcp_servers": of(out, "mcp_servers", "mcp:project")}
    assert [(p["id"], p["enabled"]) for p in declared["plugins"]] == [("a@m", True), ("x@y", False)]
    assert [s["name"] for s in declared["mcp_servers"]] == ["github"]


@pytest.mark.parametrize("answer", [Result(0, b"", b""), Result(128, b"", b"")])
def test_a3_11_declared_requires_tracked_true(project, fake_run, user_config, managed, answer):
    root = project({".claude/settings.json": {"enabledPlugins": {"a@m": True}},
                    ".mcp.json": {"mcpServers": {"github": {"command": "npx"}}}})
    run = fake_run({**NO_CLAUDE, ("git", "ls-files", "-z", "--", ".claude/settings.json",
                                  ".mcp.json"): answer})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert inv.declared(out) == {"plugins": [], "mcp_servers": []}


# Cross-cutting tests (spec 16 F3)

def _rich(project, user_config, managed, fake_run, tmp_path):
    (user_config / "settings.json").write_text(json.dumps({
        "env": {"Z": "1", "A": "${X}"}, "permissions": {"deny": ["Read(./u)"]},
        "enabledPlugins": {"u@m": True}}))
    (managed / "managed-settings.json").write_text(json.dumps({
        "permissions": {"deny": ["Read(./m)"], "allow": ["Read(./m2)"]}, "sandbox": {"enabled": True}}))
    (managed / "managed-mcp.json").write_text(json.dumps({"mcpServers": {
        "m": {"type": "sse", "url": "https://m.test/"}}}))
    root = project({
        ".claude/settings.json": {
            "permissions": {"deny": ["Read(./b)", "Read(./a)"], "ask": ["Edit(./c)"]},
            "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}],
                      "PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "y"}]}]},
            "enabledPlugins": {"p@m": True, "q@m": False}, "env": {"B": "", "A": "lit"},
            "sandbox": {"enabled": False}, "disableAllHooks": False},
        ".claude/settings.local.json": {"hooks": {"Stop": [{"hooks": [{"type": "prompt"}]}]},
                                        "env": {"L": "x"}},
        ".mcp.json": {"mcpServers": {"b": {"command": "npx", "args": ["b"], "env": {"K": "v"}},
                                     "a": {"url": "https://a.test/"}}}})
    run = full(fake_run, root, tmp_path / "plugins", git(
        ".claude/settings.local.json", ".claude/settings.json", ".mcp.json", tracked=[".mcp.json"]))
    return root, run


def test_hygiene_deterministic(project, fake_run, user_config, managed, tmp_path):
    root, run = _rich(project, user_config, managed, fake_run, tmp_path)
    first = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    second = inv.inventory(root, run=run, user_config=user_config, managed=managed)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_hygiene_sort_order(project, fake_run, user_config, managed, tmp_path):
    root, run = _rich(project, user_config, managed, fake_run, tmp_path)
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    rank = {s["id"]: i for i, s in enumerate(out["sources"])}
    assert [(r["source"], r["list"], r["rule"]) for r in out["permission_rules"]] == [
        ("settings:managed", "allow", "Read(./m2)"), ("settings:managed", "deny", "Read(./m)"),
        ("settings:project", "ask", "Edit(./c)"), ("settings:project", "deny", "Read(./b)"),
        ("settings:project", "deny", "Read(./a)"), ("settings:user", "deny", "Read(./u)")]
    hooks = [(h["event"], h["source"]) for h in out["hooks"]]
    assert hooks == sorted(hooks, key=lambda h: (h[0], rank[h[1]]))
    assert hooks[0][0] == "PreToolUse"
    plugins = [(p["source"], p["index"]) for p in out["plugins"]]
    assert plugins[0][0] == "claude" and plugins == sorted(
        plugins, key=lambda p: (-1 if p[0] == "claude" else rank[p[0]], p[1]))
    servers = [(s["source"], s["plugin_index"], s["index"], s["name"]) for s in out["mcp_servers"]]
    assert servers == [("mcp:managed", None, 0, "m"), ("mcp:project", None, 0, "b"),
                       ("mcp:project", None, 1, "a"), ("claude", 6, 0, "fixture-db"),
                       ("claude", 6, 1, "serena")]
    vals = [(v["source"], v["location"], v["key"]) for v in out["values"]]
    assert vals == sorted(vals, key=lambda v: (rank[v[0]], v[1], v[2]))
    assert [k for s, loc, k in vals if s == "settings:project"] == ["A", "B"]
    flags = [(f["source"], f["key"]) for f in out["flags"]]
    assert flags == sorted(flags, key=lambda f: (rank[f[0]], f[1]))


def test_hygiene_sort_null_first(project, fake_run, user_config, managed):
    root = project({".claude/settings.json": {"env": {"B": "1", "bad=key": "2", "A": "3"}}})
    run = fake_run({**NO_CLAUDE, **git(".claude/settings.json")})
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert [v["key"] for v in out["values"]] == [None, "A", "B"]


def test_hygiene_commands(project, fake_run, user_config, managed, tmp_path):
    root, run = _rich(project, user_config, managed, fake_run, tmp_path)
    check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert run.calls == [
        (("claude", "--version"), root), (PLUGIN_LIST, root),
        (("git", "ls-files", "-z", "--", ".claude/settings.local.json", ".claude/settings.json",
          ".mcp.json"), root)]


def test_hygiene_s17_default_runner_resolved_at_call(project, user_config, managed):
    with pytest.raises(UnexpectedMachineAccess):
        inv.inventory(project(), user_config=user_config, managed=managed)


def test_hygiene_s17_required_args(project, fake_run, user_config, managed):
    with pytest.raises(TypeError):
        inv.inventory(project(), run=fake_run(NO_CLAUDE), managed=managed)
    with pytest.raises(TypeError):
        inv.inventory(project(), run=fake_run(NO_CLAUDE), user_config=user_config)


def test_hygiene_s16_no_user_config_path(project, fake_run, user_config, managed, tmp_path):
    root, run = _rich(project, user_config, managed, fake_run, tmp_path)
    out = check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    text = json.dumps(out)
    assert str(user_config) not in text and str(user_config.resolve()) not in text
    assert source(out, "settings:user")["path"] == "<user-config>/settings.json"
    rest = dict(out, sources=[s for s in out["sources"]
                              if not (s["path"] or "").startswith(str(managed))])
    text = json.dumps(rest)
    assert str(managed) not in text and str(managed.resolve()) not in text


def _snapshot(*folders):
    return {(str(f), str(p.relative_to(f))): (p.read_bytes() if p.is_file() else None)
            for f in folders for p in sorted(f.rglob("*"))}


def test_hygiene_s18_read_only(project, fake_run, user_config, managed, tmp_path):
    root, run = _rich(project, user_config, managed, fake_run, tmp_path)
    before = _snapshot(root, user_config, managed)
    check(inv.inventory(root, run=run, user_config=user_config, managed=managed))
    assert _snapshot(root, user_config, managed) == before


@pytest.mark.parametrize("platform, expected", [
    ("darwin", pathlib.Path("/Library/Application Support/ClaudeCode")),
    ("linux", pathlib.Path("/etc/claude-code")),
    ("win32", None),
])
def test_hygiene_default_managed(monkeypatch, platform, expected):
    monkeypatch.setattr(sys, "platform", platform)
    assert inv.default_managed() == expected


def test_hygiene_duration(project, fake_run, user_config, managed, tmp_path):
    root, run = _rich(project, user_config, managed, fake_run, tmp_path)
    start = time.perf_counter()
    out = inv.inventory(root, run=run, user_config=user_config, managed=managed)
    assert time.perf_counter() - start < 1
    check(out)
