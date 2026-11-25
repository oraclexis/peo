"""SC-006: the Selector runs no code of the catalog, no process, no network; the hooks do not import it."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "peo"
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_MODULES = {"subprocess", "socket", "urllib", "http", "ssl", "os"}


def tree(name):
    return ast.parse((SRC / name).read_text())


@pytest.mark.parametrize("name", ["selector.py", "expr.py"])
def test_no_dynamic_code_no_process_no_network(name):
    found = tree(name)
    calls = {n.func.id for n in ast.walk(found) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls & FORBIDDEN_CALLS
    imported = {a.name.split(".")[0] for n in ast.walk(found) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(found) if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & FORBIDDEN_MODULES
    assert "shell=True" not in (SRC / name).read_text()


@pytest.mark.parametrize("name", ["gate.py", "context.py"])
def test_the_hooks_do_not_import_the_selector_or_the_catalog(name):
    path = SRC / name
    if not path.exists():
        pytest.skip(f"{name} is not written yet")
    text = path.read_text()
    assert "selector" not in text and "catalog" not in text
