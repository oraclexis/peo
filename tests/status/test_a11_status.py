"""peo status, spec 16 F11 (R3): A11.1, A11.2, A11.4 to A11.11; A14.5; spec 15 §6, §7.3."""

import builtins
import io
import json
import pathlib
import re

import pytest

import peo.discovery
import peo.runner
import peo.status as st
from peo import cli
from tests.gitcmd import GIT
from tests.status.conftest import (
    ROOT,
    FakeRunner,
    check,
    codes,
    findings,
    make_repo,
    settings,
    write,
)

FLOW = ROOT / "docs" / "design" / "spec" / "15-flow-and-gates.md"


def r3_codes(prefix: str) -> list[str]:
    """Codes whose Livraison column is R3 in spec 15 §6 and §7.1 (A11.4)."""
    rows = re.findall(r"^\| `([SX]-[A-Z-]+)` \| [^|]+ \| ([^|]+) \|", FLOW.read_text(), re.MULTILINE)
    return sorted(code for code, delivery in rows if delivery.strip() == "R3" and code.startswith(prefix))


def one(data, code):
    found = findings(data, code)
    assert len(found) == 1, found
    return found[0]


def plugins(*entries) -> bytes:
    return json.dumps([{"id": "a@m", "scope": "user", "enabled": False} | e for e in entries]).encode()


def cli_run(capsys, monkeypatch, *argv, runner=None):
    monkeypatch.setattr(peo.runner, "run", runner or FakeRunner())
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --- A11.1: one test per S-* code of R3 ------------------------------------------------------

def test_a11_1_plugin_error(tmp_path, run_status):
    out = run_status(make_repo(tmp_path / "p", {}), FakeRunner(plugins=plugins({"errors": ["x"]})),
                     exposure=False)
    f = one(out, "S-PLUGIN-ERROR")
    assert (f["severity"], f["status"], f["source"]) == ("error", "applied", "claude")
    assert "x" not in f["message"].split() and f["evidence"] == ["claude plugin 0 errors 1"]


def test_a11_1_no_plugin_error_without_errors(tmp_path, run_status):
    out = run_status(make_repo(tmp_path / "p", {}), FakeRunner(plugins=plugins({})), exposure=False)
    assert "S-PLUGIN-ERROR" not in codes(out)


def test_a11_1_degraded_inventory(tmp_path, run_status):
    out = run_status(make_repo(tmp_path / "p", {}), FakeRunner(version=b"2.1.200 (Claude Code)"),
                     exposure=False)
    f = one(out, "S-DEGRADED-INVENTORY")
    assert (f["severity"], f["source"]) == ("warning", "claude")
    assert "unavailable claude-too-old" in f["message"]


def test_a11_9_hook_in_project_settings(tmp_path, run_status):
    hooks = {"hooks": {"PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command",
                                                                      "command": "./x.sh"}]}]}}
    root = make_repo(tmp_path / "p", {".claude/settings.json": hooks})
    f = one(run_status(root, exposure=False), "S-HOOK-FOREIGN")
    assert (f["severity"], f["status"], f["source"]) == ("info", "applied", "settings:project")
    assert "owner settings:project" in f["message"] and "./x.sh" not in json.dumps(f)


def test_a11_9_plugin_hook_owner_is_the_plugin(tmp_path, run_status):
    install = tmp_path / "install"
    write(install, {"hooks/hooks.json": {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                                                        "command": "x"}]}]}}})
    listing = plugins({"id": "egm@egm", "enabled": True, "installPath": str(install)})
    f = one(run_status(make_repo(tmp_path / "p", {}), FakeRunner(plugins=listing), exposure=False),
            "S-HOOK-FOREIGN")
    assert f["source"] == "plugin:#0" and "plugin egm@egm" in f["message"]


def test_a11_1_hook_made_inert_by_disable_all_hooks(tmp_path, run_status):
    files = {".claude/settings.json": {"hooks": {"Stop": [{"hooks": [{"type": "command"}]}]}},
             ".claude/settings.local.json": {"disableAllHooks": True}}
    f = one(run_status(make_repo(tmp_path / "p", files), exposure=False), "S-HOOK-FOREIGN")
    assert "inert: disableAllHooks is true in settings:local" in f["message"]


# --- A11.2: exit codes -----------------------------------------------------------------------

def test_a11_2_ci_exit_3_on_error(tmp_path, capsys, monkeypatch):
    root = make_repo(tmp_path / "p", {})
    runner = FakeRunner(plugins=plugins({"errors": ["x"]}))
    assert cli_run(capsys, monkeypatch, "--project", str(root), "status", "--ci",
                   runner=runner)[0] == cli.EXIT_STATUS_FINDINGS
    assert cli_run(capsys, monkeypatch, "--project", str(root), "status", runner=runner)[0] == 0


def test_a11_2_skipped_alone_exit_0(tmp_path, capsys, monkeypatch):
    root = make_repo(tmp_path / "p", {})
    runner = FakeRunner(version_rc=127, version=b"")
    code, out, _ = cli_run(capsys, monkeypatch, "--json", "--project", str(root), "status",
                           "--exposure", "--ci", runner=runner)
    errors = [f for f in findings(json.loads(out)["data"]) if f["severity"] == "error"]
    assert errors and all(f["status"] == "skipped" for f in errors)
    assert code == 0


def test_a11_2_likely_error_exit_3(tmp_path, capsys, monkeypatch, machine):
    (machine["user_config"] / "settings.json").write_text("{not json")
    root = make_repo(tmp_path / "p", {"backend/.env": "A=1\n"})
    code, out, _ = cli_run(capsys, monkeypatch, "--json", "--project", str(root), "status",
                           "--exposure", "--ci")
    f = one(json.loads(out)["data"], "X-SECRET-READABLE")
    assert (f["status"], f["confidence"], f["severity"]) == ("applied", "likely", "error")
    assert code == cli.EXIT_STATUS_FINDINGS


def test_a11_canary_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["status", "--canary"])
    assert exc.value.code == cli.EXIT_USAGE == 2


def test_a11_project_not_found_exit_1(tmp_path, capsys):
    assert cli.main(["--json", "--project", str(tmp_path / "missing"), "status"]) == cli.EXIT_ERROR
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "E_PROJECT_NOT_FOUND"


def test_a11_options_before_or_after_the_command(tmp_path, capsys, monkeypatch):
    root = make_repo(tmp_path / "p", {})
    _, before, _ = cli_run(capsys, monkeypatch, "--json", "--project", str(root), "status")
    _, after, _ = cli_run(capsys, monkeypatch, "status", "--project", str(root), "--json")
    assert json.loads(before) == json.loads(after)
    assert json.loads(before)["command"] == "status" and json.loads(before)["ok"] is True


# --- A11.4, A11.5: rules_evaluated, schema and total order -----------------------------------

def test_a11_4_rules_evaluated(tmp_path, run_status):
    root = make_repo(tmp_path / "p", {"backend/.env": "A=1\n"})
    plain, full = run_status(root, exposure=False), run_status(root)
    assert plain["rules_evaluated"] == r3_codes("S-") == list(st.S_CODES)
    assert full["rules_evaluated"] == sorted(r3_codes("S-") + r3_codes("X-"))
    assert len(r3_codes("X-")) == 10
    assert codes(full) <= set(full["rules_evaluated"])


def test_a11_5_total_order(tmp_path, run_status, machine):
    hook = {"hooks": [{"type": "command"}, {"type": "http", "url": "https://h.example.test"}]}
    (machine["user_config"] / "settings.json").write_text(json.dumps({"hooks": {"Stop": [hook]}}))
    files = {".claude/settings.json": {"hooks": {"Stop": [hook], "PreToolUse": [hook]}},
             ".claude/settings.local.json": {"hooks": {"Bad Event": []}},
             "b/.env": "A=1\n", "a/.env": "A=1\n", "a.sql": "x"}
    out = run_status(make_repo(tmp_path / "p", files, track=["a/.env"]))

    def key(f):
        return tuple((v is not None, v if v is not None else "") for v in (
            f.get("path"), f.get("source"), f.get("plugin_index"), f.get("index"))) + (f["evidence"],)
    for part in (out["findings"], out["exposure"]["findings"]):
        assert part == sorted(part, key=lambda f: (f["code"], key(f)))
    assert len(findings(out, "S-HOOK-FOREIGN")) >= 5
    assert out["limits"] == sorted(out["limits"])
    check(out)


# --- A11.6 to A11.11: sources ----------------------------------------------------------------

OUT_OF_SCOPE = ("settings:cli", "settings:managed-other", "mcp:local", "mcp:user")


def test_a11_6_out_of_scope_sources(tmp_path, run_status):
    root = make_repo(tmp_path / "p", {"backend/.env": "A=1\n"})
    for exposure in (False, True):
        out = run_status(root, exposure=exposure)
        cited = [f for f in findings(out) if f["status"] == "skipped" or f["confidence"] == "likely"]
        assert [f for f in cited if f.get("source") in OUT_OF_SCOPE
                or set(OUT_OF_SCOPE) & set(" ".join(f["evidence"]).split())] == []
        assert {"L-SETTINGS-CLI", "L-SETTINGS-MANAGED-OTHER", "L-SERVER-MANAGED"} <= set(out["limits"])
        assert ("L-MCP-LOCAL-USER" in out["limits"]) is exposure
    assert one(run_status(root), "X-SECRET-READABLE")["confidence"] == "fact"


def test_a11_7_profile_file_is_never_read(tmp_path, run_status, monkeypatch):
    root = make_repo(tmp_path / "p", {"backend/.env": "A=1\n"})
    reference = run_status(root)
    write(root, {".peo/profile.json": {"sensitive": {"secret_files": [{"path": "fake/.env"}]}}})
    seen = []
    for owner, name in ((builtins, "open"), (io, "open"), (pathlib.Path, "open")):
        real = getattr(owner, name)

        def spy(file, *args, _real=real, **kwargs):
            seen.append(str(file))
            return _real(file, *args, **kwargs)
        monkeypatch.setattr(owner, name, spy)
    again = run_status(root)
    assert json.dumps(again["exposure"], sort_keys=True) == json.dumps(reference["exposure"], sort_keys=True)
    assert again["findings"] == reference["findings"]
    assert [p for p in seen if p.endswith("profile.json")] == []

    def refuse(*args, **kwargs):
        raise AssertionError("Discovery ran without --exposure")
    monkeypatch.setattr(peo.discovery, "discover", refuse)
    assert "exposure" not in run_status(root, exposure=False)


def test_a11_8_hooks_family_invalid_is_skipped(tmp_path, run_status):
    root = make_repo(tmp_path / "p", {".claude/settings.local.json": {"hooks": {"Bad Event": []}}})
    f = one(run_status(root, exposure=False), "S-HOOK-FOREIGN")
    assert (f["status"], f["source"]) == ("skipped", "settings:local") and "path" not in f
    assert f["evidence"] == ["settings:local invalid_families hooks"]


def test_a11_10_claude_absent_degraded_without_ci_detection(tmp_path, run_status, monkeypatch):
    root = make_repo(tmp_path / "p", {})
    absent = FakeRunner(version_rc=127, version=b"")
    plain = run_status(root, absent, exposure=False)
    f = one(plain, "S-DEGRADED-INVENTORY")
    assert "claude absent" in f["message"]
    for name in ("CI", "GITHUB_ACTIONS", "GITLAB_CI"):
        monkeypatch.setenv(name, "true")
    assert run_status(root, FakeRunner(version_rc=127, version=b""), exposure=False) == plain


def test_a11_11_flags_invalid_hook_still_applied(tmp_path, run_status):
    files = {".claude/settings.json": {"sandbox": {"enabled": "yes"},
                                       "hooks": {"Stop": [{"hooks": [{"type": "command"}]}]}}}
    out = run_status(make_repo(tmp_path / "p", files), exposure=False)
    f = one(out, "S-HOOK-FOREIGN")
    assert (f["status"], f["source"]) == ("applied", "settings:project")
    assert "settings:project invalid_families flags: disableAllHooks unknown, hook may be inert" in f["evidence"]
    assert "unknown" in f["message"]
    assert [g for g in findings(out) if g["status"] == "skipped" and g.get("source") == "settings:project"] == []


# --- escaping and human output (15 §7.3, NF13) -----------------------------------------------

@pytest.mark.parametrize(("text", "expected"), [
    ("a\nb", "a\\x0ab"), ("\x1b[31m", "\\x1b[31m"), ("\x7f", "\\x7f"), ("\x85\x9f", "\\x85\\x9f"),
    ("‮exe.txt", "\\u{202e}exe.txt"), ("a​b⁦c﻿", "a\\u{200b}b\\u{2066}c\\u{feff}"),
    ("a\u2028b\u2029c", "a\\u{2028}b\\u{2029}c"), ("a\u061cb\u00adc\u2060", "a\\u{061c}b\\u{00ad}c\\u{2060}"),
    ("\t", "\\x09"), ("backend/.env Read(./x/**) é", "backend/.env Read(./x/**) é")])
def test_escape(text, expected):
    assert st.escape(text) == expected


def test_render_escapes_repository_strings():
    data = {"findings": [st.finding("S-HOOK-FOREIGN", "info", "m‮", [], source="settings:user")],
            "limits": [], "exposure": {"findings": [st.finding(
                "X-SECRET-READABLE", "error", "bad\npath: x", [], path="bad\npath",
                rule="Read(./a\x1b)", confidence="likely", reason="case-only")], "linked_dirs": []}}
    text = st.render(data)
    assert "\x1b" not in text and "‮" not in text and len(text.splitlines()) == 2


def test_render_format(split_stack, run_status, machine):
    (machine["user_config"] / "settings.json").write_text("{not json")
    out = run_status(split_stack, FakeRunner(version_rc=127, version=b""))
    lines = st.render(out).splitlines()
    all_findings = findings(out)
    applied = [f for f in all_findings if f["status"] == "applied"]
    skipped = [f for f in all_findings if f["status"] == "skipped"]
    assert applied and skipped
    assert len(lines) == len(all_findings) + len(out["limits"])
    head = lines[:len(applied)]
    assert all(re.match(r"^(error|warning|info) [SX]-[A-Z-]+[ :]", line) for line in head)
    assert any(line.endswith("(likely: source-unreadable)") for line in head)
    assert all(line.startswith("skipped ") for line in lines[len(applied):len(all_findings)])
    assert all(line.startswith("limit L-") for line in lines[len(all_findings):])
    assert "error X-SECRET-READABLE backend/.env: no deny Read rule covers" in st.render(out)


# --- A14.5, determinism ----------------------------------------------------------------------

def test_a14_5_only_listed_commands(split_stack, capsys, monkeypatch):
    runner = FakeRunner()
    monkeypatch.chdir(split_stack / "backend")
    code, _, _ = cli_run(capsys, monkeypatch, "--json", "status", "--exposure", runner=runner)
    assert code == 0
    commands = [c[0] for c in runner.calls]
    assert (*GIT, "rev-parse", "--show-toplevel") in commands
    assert ("claude", "--version") in commands and ("claude", "plugin", "list", "--json") in commands
    assert all(c[0] == "git" and c[:5] == GIT or c[0] == "claude" for c in commands)
    assert all(t == 10 for c, _, t in runner.calls if c[0] == "claude")


def test_a14_5_head_blob_is_listed(tmp_path, run_status):
    root = make_repo(tmp_path / "p", {})
    settings(root, ["Read(./x)"], tracked=True, committed=True)
    runner = FakeRunner()
    run_status(root, runner)
    assert (*GIT, "rev-parse", "HEAD:.claude/settings.json") in [c[0] for c in runner.calls]
    assert not [c for c, _, _ in runner.calls if c[5:6] == ("diff",)]


def test_status_deterministic(split_stack, run_status):
    first, second = run_status(split_stack), run_status(split_stack)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
