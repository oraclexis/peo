"""Machine guard and fakes for the status tests (R3, spec 16 F11 and F14).

Every test here runs with sockets refused, peo.runner.run raising, HOME and CLAUDE_CONFIG_DIR
pointing to empty temporary folders, Path.home() equal to that HOME, the managed folder empty
and platform.system() == "Darwin". Only cli.py reads these (research R5); the proof that no
other module reads the machine is the grep of quickstart.md, not this guard.
"""

import json
import os
import pathlib
import platform
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

import peo.inventory
import peo.runner
from peo.runner import Result
from peo.validate import load_schema, validate
from tests.gitcmd import GIT

REAL_RUN = peo.runner.run   # kept before any monkeypatch: fixture repositories answer git
ROOT = Path(__file__).resolve().parents[2]
SPLIT_STACK = ROOT / "tests" / "fixtures" / "fx-split-stack"
DECOY = "fixture-not-a-secret-"  # noqa: S105 - marker of every fake value planted by a test
VERSION = b"2.1.325 (Claude Code)\n"
PLUGIN_LIST = ("claude", "plugin", "list", "--json")
# A14.5: git subcommands of Discovery, of the Inventory and of cli.py
ALLOWED_GIT = {"ls-files", "log", "rev-list", "for-each-ref", "remote", "symbolic-ref", "rev-parse",
               "diff"}
GIT_ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "Fixture Author", "GIT_AUTHOR_EMAIL": "author@example.test",
           "GIT_COMMITTER_NAME": "Fixture Author", "GIT_COMMITTER_EMAIL": "author@example.test",
           "GIT_AUTHOR_DATE": "@1772438400 +0000", "GIT_COMMITTER_DATE": "@1772438400 +0000"}


class UnexpectedMachineAccess(AssertionError):
    """A test reached the real machine (runner, network) or ran a command off the list."""


def _raise(*args, **kwargs):
    raise UnexpectedMachineAccess("unexpected access to the real machine")


@pytest.fixture(autouse=True)
def no_machine(monkeypatch, tmp_path):
    home, config, managed = tmp_path / "home", tmp_path / "claude-config", tmp_path / "managed"
    for folder in (home, config, managed):
        folder.mkdir()
    monkeypatch.setattr(peo.runner, "run", _raise)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    monkeypatch.setattr(pathlib.Path, "home", lambda *args: home)
    monkeypatch.setattr(peo.inventory, "default_managed", lambda: managed)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(socket.socket, "connect", _raise)
    monkeypatch.setattr(socket.socket, "connect_ex", _raise)
    monkeypatch.setattr(socket, "create_connection", _raise)


@pytest.fixture
def machine(tmp_path):
    """The folders the guard points the machine to: home, user config, managed."""
    return {"home": tmp_path / "home", "user_config": tmp_path / "claude-config",
            "managed": tmp_path / "managed"}


class FakeRunner:
    """Allow-list of A14.5: prefixed git (passed to the real git), and two claude commands."""

    def __init__(self, version=VERSION, version_rc=0, plugins=b"[]", plugins_rc=0):
        self.version, self.version_rc = version, version_rc
        self.plugins, self.plugins_rc = plugins, plugins_rc
        self.calls: list[tuple[tuple[str, ...], Path, float | None]] = []

    def __call__(self, args, cwd, timeout=None):
        args = tuple(args)
        self.calls.append((args, cwd, timeout))
        if args[:1] == ("git",):
            if args[:5] != GIT or args[5] not in ALLOWED_GIT:
                raise UnexpectedMachineAccess(f"git command off the list: {args}")
            if args[5] == "diff" and args[5:] != ("diff", "--quiet", "HEAD", "--",
                                                  ".claude/settings.json"):
                raise UnexpectedMachineAccess(f"git diff off the list: {args}")
            return REAL_RUN(list(args), cwd)
        if args == ("claude", "--version"):
            if timeout != 10:
                raise UnexpectedMachineAccess(f"claude --version without a 10 s timeout: {timeout}")
            return Result(self.version_rc, self.version, b"")
        if args == PLUGIN_LIST:
            if timeout != 10:
                raise UnexpectedMachineAccess(f"claude plugin list without a 10 s timeout: {timeout}")
            return Result(self.plugins_rc, self.plugins, b"")
        raise UnexpectedMachineAccess(f"command off the list: {args}")


def git(root: Path, *args: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")} | GIT_ENV
    subprocess.run(["git", "-C", str(root), "-c", "commit.gpgsign=false",
                    "-c", "core.hooksPath=/dev/null", *args], check=True, capture_output=True, env=env)


def write(root: Path, files: dict) -> Path:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        elif isinstance(content, str):
            path.write_text(content)
        else:
            path.write_text(json.dumps(content))
    return root


def make_repo(root: Path, files: dict, *, track=()) -> Path:
    """A git repository with `files` written and only `track` committed."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    write(root, files)
    if track:
        git(root, "add", "-f", "--", *track)
    git(root, "commit", "-q", "--allow-empty", "-m", "init")
    return root


def settings(root: Path, rules: list[str], *, tracked: bool, committed: bool,
             path: str = ".claude/settings.json") -> None:
    """Deny rules in a settings file; tracked adds it to the index, committed commits it."""
    write(root, {path: {"permissions": {"deny": rules}}})
    if tracked:
        git(root, "add", "-f", "--", path)
        if committed:
            git(root, "commit", "-q", "-m", "chore: deny rules")


@pytest.fixture(scope="session")
def split_stack_built(tmp_path_factory):
    target = tmp_path_factory.mktemp("fx") / "split-stack"
    subprocess.run(["bash", str(SPLIT_STACK / "build.sh"), str(target)], check=True,
                   capture_output=True)
    yield target
    shutil.rmtree(target, ignore_errors=True)


@pytest.fixture
def split_stack(split_stack_built, tmp_path):
    """A fresh copy of fx-split-stack built by its build.sh."""
    target = tmp_path / "split-stack"
    shutil.copytree(split_stack_built, target, symlinks=True)
    return target


@pytest.fixture
def run_status(machine):
    """peo.status.status() with the guarded machine; the output is checked against the schemas."""
    import peo.status as st

    def call(root, run=None, *, exposure=True, platform="Darwin", **overrides):
        args = {"user_config": machine["user_config"], "managed": machine["managed"],
                "home": machine["home"], "platform": platform} | overrides
        out = st.status(Path(os.path.realpath(root)), exposure=exposure,
                        run=run if run is not None else FakeRunner(), **args)
        check(out)
        return out
    return call


def check(data: dict) -> dict:
    assert validate(data, load_schema("status")) == []
    assert validate(data["inventory"], load_schema("inventory")) == []
    assert DECOY not in json.dumps(data)
    return data


def findings(data: dict, code: str | None = None) -> list[dict]:
    found = data["findings"] + data.get("exposure", {}).get("findings", [])
    return [f for f in found if code is None or f["code"] == code]


def codes(data: dict) -> set[str]:
    return {f["code"] for f in findings(data)}
