"""Injectable command runner (spec 14, section 4.1).

The only module of src/peo that imports subprocess. Callers receive a Runner and tests
replace it with a fake.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NamedTuple


class Result(NamedTuple):
    returncode: int
    stdout: bytes
    stderr: bytes


Runner = Callable[[Sequence[str], Path], Result]


def run(args: Sequence[str], cwd: Path, timeout: float = 30) -> Result:
    """Run one command; a missing command or a timeout gives returncode 127, never an exception."""
    try:
        # Argument list, never a shell: nothing in args is interpreted.
        done = subprocess.run(list(args), cwd=cwd, capture_output=True, check=False,  # noqa: S603
                              timeout=timeout)
    except FileNotFoundError:
        return Result(127, b"", f"command not found: {args[0]}".encode())
    except subprocess.TimeoutExpired:
        return Result(127, b"", f"timed out after {timeout}s: {args[0]}".encode())
    return Result(done.returncode, done.stdout, done.stderr)
