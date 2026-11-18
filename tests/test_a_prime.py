"""Milestone A′, local test (spec 16 §2.3): invariants of `peo status --exposure` on real clones.

Opt-in only: PEO_AUDIT_PATHS lists local clones separated by ':'; PEO_CLAUDE_VERSION is the
Claude Code version pinned for the milestone; PEO_PILOT1_PATH names the pilot, audited with the
real configuration of this machine (the others get an empty CLAUDE_CONFIG_DIR). Never run in
CI. Checks invariants only, writes nothing in the audited repositories, and on failure prints
variable names, never values.
"""

import json
import os
import re
import socket
import time
from pathlib import Path

import pytest

import peo.runner
from peo import cli
from peo.discovery.sensitive import ENV_EXAMPLE_SUFFIXES

PATHS = [p for p in os.environ.get("PEO_AUDIT_PATHS", "").split(":") if p]
PROTECTED = re.compile(r"protect|protégé", re.IGNORECASE)
SKIPPED_DIRS = {".git", "node_modules", "vendor", ".venv", "dist", "build"}

pytestmark = pytest.mark.skipif(not PATHS, reason="PEO_AUDIT_PATHS not set")


def _files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIPPED_DIRS]
        for name in filenames:
            yield Path(dirpath) / name


def snapshot(root: Path) -> dict:
    return {p: p.lstat().st_mtime_ns for p in _files(root)}


def env_values(root: Path) -> list[tuple[str, str]]:
    """(name, value) of every .env* line, kept in memory only."""
    found = []
    for path in _files(root):
        if not path.name.startswith(".env") or path.name.endswith(ENV_EXAMPLE_SUFFIXES) or path.is_symlink():
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            name, sep, value = line.removeprefix("export ").partition("=")
            value = value.strip().strip("'\"")
            if sep and len(value) >= 6:
                found.append((name.strip(), value))
    return found


def without_paths(root: Path, text: str) -> str:
    """`text` minus the repository's own paths: a value that is a piece of a file name is no leak."""
    for rel in sorted((p.relative_to(root).as_posix() for p in _files(root)), key=len, reverse=True):
        text = text.replace(rel, "")
    return text


def leaked_names(values: list[tuple[str, str]], text: str) -> list[str]:
    """Names whose value appears in text as a whole word (bounds: start, end, or not [A-Za-z0-9_-])."""
    return sorted({name for name, value in values
                   if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(value)}(?![A-Za-z0-9_-])", text)})


@pytest.mark.parametrize("path", PATHS)
def test_a_prime_invariants(path, monkeypatch, capsys, tmp_path):
    pinned = os.environ.get("PEO_CLAUDE_VERSION")
    if not pinned:
        pytest.fail("set PEO_CLAUDE_VERSION to the Claude Code version pinned for the milestone")
    root = Path(path).resolve()
    if str(root) != os.environ.get("PEO_PILOT1_PATH", ""):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "empty-config"))
        (tmp_path / "empty-config").mkdir()
    real, claude_time = peo.runner.run, [0.0]

    def timed(args, cwd, *rest, **kwargs):
        start = time.perf_counter()
        try:
            return real(args, cwd, *rest, **kwargs)
        finally:
            if args[0] == "claude":
                claude_time[0] += time.perf_counter() - start

    def refuse(*args, **kwargs):
        raise AssertionError("network access from the PEO process")
    monkeypatch.setattr(peo.runner, "run", timed)
    for owner, name in ((socket.socket, "connect"), (socket.socket, "connect_ex"),
                        (socket, "create_connection")):
        monkeypatch.setattr(owner, name, refuse)

    before = snapshot(root)
    start = time.perf_counter()
    code = cli.main(["--json", "--project", str(root), "status", "--exposure"])
    total = time.perf_counter() - start
    out, err = capsys.readouterr()
    with capsys.disabled():
        print(f"\n{root.name}: {total - claude_time[0]:.2f} s without claude, "
              f"{claude_time[0]:.2f} s in claude")
    assert code == 0
    assert snapshot(root) == before
    data = json.loads(out)["data"]
    assert data["inventory"]["claude_version"] == pinned
    assert total - claude_time[0] < 5
    assert not PROTECTED.search(out + err)
    leaked = leaked_names(env_values(root), without_paths(root, out + "\n" + err))
    assert leaked == [], f"values of these variables are in the output: {leaked}"
