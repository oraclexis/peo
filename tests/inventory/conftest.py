"""Machine guard and fakes for the Inventory tests (R2, spec 16 F3).

Every test in this folder runs with peo.runner.run, Path.home and sockets raising
UnexpectedMachineAccess, and HOME pointing to a missing folder: an Inventory test never
reads the real machine.
"""

import json
import pathlib
import socket
from pathlib import Path

import pytest

import peo.runner
from peo.runner import Result

DATA = Path(__file__).parent / "data"
VERSION_OK = Result(0, b"2.1.325 (Claude Code)\n", b"")
MISSING = Result(127, b"", b"")
PLUGIN_HOOKS = {"hooks": {"PreToolUse": [{"matcher": "Edit|Write", "hooks": [{
    "type": "command",
    "command": "FIXTURE_NOT_A_SECRET_HOOK=fixture-not-a-secret-plugin-hook ./run.sh",
    "onFailure": "block"}]}]}}


class UnexpectedMachineAccess(AssertionError):
    """A test reached the real machine (runner, home folder or network)."""


def _raise(*args, **kwargs):
    raise UnexpectedMachineAccess("unexpected access to the real machine")


@pytest.fixture(autouse=True)
def no_machine(monkeypatch):
    monkeypatch.setattr(peo.runner, "run", _raise)
    monkeypatch.setenv("HOME", "/nonexistent-peo-home")
    monkeypatch.setattr(pathlib.Path, "home", _raise)
    monkeypatch.setattr(socket.socket, "connect", _raise)
    monkeypatch.setattr(socket.socket, "connect_ex", _raise)
    monkeypatch.setattr(socket, "create_connection", _raise)


class FakeRunner:
    """Answers commands from a dict keyed by tuple(args); records (args, cwd)."""

    def __init__(self, responses):
        self.responses = dict(responses)
        self.calls: list[tuple[tuple[str, ...], Path]] = []

    def __call__(self, args, cwd, timeout=30):
        key = tuple(args)
        self.calls.append((key, cwd))
        if key not in self.responses:
            raise UnexpectedMachineAccess(f"unexpected command: {key}")
        answer = self.responses[key]
        if isinstance(answer, BaseException):
            raise answer
        return answer


@pytest.fixture
def fake_run():
    return FakeRunner


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()

    def write(files=None) -> Path:
        for rel, content in (files or {}).items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            elif isinstance(content, str):
                path.write_text(content)
            else:
                path.write_text(json.dumps(content))
        return root

    return write


@pytest.fixture
def user_config(tmp_path):
    path = tmp_path / "user-config"
    path.mkdir()
    return path


@pytest.fixture
def managed(tmp_path):
    path = tmp_path / "Claude Code managed"
    path.mkdir()
    return path


def plugin_list(plugins_dir: Path, root: Path) -> bytes:
    """Hand-written `claude plugin list --json` output, with hooks.json of enabled plugins."""
    text = (DATA / "plugin-list.json").read_text()
    text = text.replace("{plugins}", json.dumps(str(plugins_dir))[1:-1])
    text = text.replace("{root}", json.dumps(str(root))[1:-1])
    for n, plugin in enumerate(json.loads(text)):
        if plugin["enabled"]:
            hooks = plugins_dir / "fixture-not-a-secret-install" / f"p{n}" / "hooks" / "hooks.json"
            hooks.parent.mkdir(parents=True, exist_ok=True)
            hooks.write_text(json.dumps(PLUGIN_HOOKS))
    return text.encode()
