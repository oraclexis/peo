"""Injectable command runner (spec 14, section 4.1)."""

import sys
from pathlib import Path

from peo.runner import Result, run

SRC = Path(__file__).resolve().parents[1] / "src" / "peo"


def test_run_captures_output(tmp_path):
    assert run([sys.executable, "-c", "print('ok')"], tmp_path) == Result(0, b"ok\n", b"")


def test_run_uses_cwd(tmp_path):
    result = run([sys.executable, "-c", "import os; print(os.getcwd())"], tmp_path)
    assert Path(result.stdout.decode().strip()).resolve() == tmp_path.resolve()


def test_missing_command_returns_127(tmp_path):
    result = run(["peo-no-such-command-for-tests"], tmp_path)
    assert result.returncode == 127
    assert result.stdout == b""


def test_timeout_returns_127(tmp_path):
    result = run([sys.executable, "-c", "import time; time.sleep(5)"], tmp_path, timeout=0.2)
    assert result.returncode == 127


def test_subprocess_only_in_runner():
    offenders = [p.relative_to(SRC).as_posix() for p in SRC.rglob("*.py")
                 if p.name != "runner.py" and ("import subprocess" in p.read_text()
                                               or "from subprocess" in p.read_text())]
    assert offenders == []
