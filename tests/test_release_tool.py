"""tools/release.py: version consistency and release notes used by the release workflow."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "release.py"

CHANGELOG = """# Changelog

## Unreleased

- Next thing.

## 0.2.0 — 2026-12-01

- Discovery (F1).
- Catalog validation (F2).

## 0.1.0 — 2026-11-20

- First release.
"""


def make_repo(tmp_path, version="0.2.0", init_version=None, changelog=CHANGELOG):
    (tmp_path / "src" / "peo").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "peo"\nversion = "{version}"\n')
    (tmp_path / "src" / "peo" / "__init__.py").write_text(
        f'__version__ = "{init_version or version}"\n')
    (tmp_path / "CHANGELOG.md").write_text(changelog)
    return tmp_path


def run(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args],
                          capture_output=True, text=True)


def test_repository_itself_is_consistent():
    result = run(ROOT, "check-version")
    assert result.returncode == 0, result.stderr


def test_matching_tag_passes(tmp_path):
    assert run(make_repo(tmp_path), "check-version", "--tag", "v0.2.0").returncode == 0


@pytest.mark.parametrize("tag", ["v0.3.0", "0.2.0", "v0.2"])
def test_tag_must_match_pyproject(tmp_path, tag):
    result = run(make_repo(tmp_path), "check-version", "--tag", tag)
    assert result.returncode == 1
    assert "tag" in result.stderr


def test_package_version_must_match_pyproject(tmp_path):
    result = run(make_repo(tmp_path, init_version="0.1.9"), "check-version")
    assert result.returncode == 1
    assert "__version__" in result.stderr


def test_release_needs_a_changelog_section(tmp_path):
    result = run(make_repo(tmp_path, version="0.3.0"), "check-version", "--tag", "v0.3.0")
    assert result.returncode == 1
    assert "CHANGELOG" in result.stderr


def test_notes_are_the_version_section(tmp_path):
    result = run(make_repo(tmp_path), "notes", "--tag", "v0.2.0")
    assert result.returncode == 0
    assert result.stdout == "- Discovery (F1).\n- Catalog validation (F2).\n"
