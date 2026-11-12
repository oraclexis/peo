"""F0 acceptance tests on the fx-split-stack fixture (spec 16, section 2.1; A0.1, A0.2)."""

import os
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "tests" / "fixtures" / "fx-split-stack" / "build.sh"
CODE_SUFFIXES = {".vue": "vue", ".ts": "ts", ".php": "php", ".css": "css"}
ID_STYLES = [("numeric", r"^[0-9]{3,}-"), ("timestamp", r"^[0-9]{8}-[0-9]{6}-"),
             ("alnum-id", r"^[A-Za-z]+[0-9]+-")]


def build(target: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(BUILD), str(target)], capture_output=True, text=True,
                          env=env, check=False)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    target = tmp_path_factory.mktemp("fx") / "split-stack"  # does not exist yet, as in A1
    result = build(target)
    assert result.returncode == 0, result.stderr
    yield target
    shutil.rmtree(target, ignore_errors=True)


def test_a0_1_commits_and_merges(repo):
    assert git(repo, "rev-list", "--count", "HEAD") == "93"
    assert git(repo, "rev-list", "--merges", "--count", "HEAD") == "46"
    merges = git(repo, "log", "--merges", "--format=%s").splitlines()
    assert all(s.startswith("merge: ") for s in merges)


def test_a0_1_branches(repo):
    branches = [b for b in git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()
                if b != "main"]
    assert len(branches) == 46
    assert all(re.fullmatch(r"(feat|fix)/[A-Za-z0-9-]+", b) for b in branches)
    assert sum(bool(re.match(r"feat/[A-Z][0-9]+-", b)) for b in branches) == 24
    assert Counter(b.split("/")[0] for b in branches) == {"feat": 38, "fix": 8}

    def style(branch: str) -> str:
        last = branch.rsplit("/", 1)[-1]
        return next((name for name, pattern in ID_STYLES if re.match(pattern, last)), "free")

    assert Counter(style(b) for b in branches) == {"alnum-id": 24, "free": 22}


def test_a0_1_tracked_files(repo):
    assert len(git(repo, "ls-files").splitlines()) == 99


def test_a0_1_loc_per_language(repo):
    loc = Counter()
    for name in git(repo, "ls-files").splitlines():
        lang = CODE_SUFFIXES.get(Path(name).suffix)
        if lang:
            loc[lang] += sum(1 for line in (repo / name).read_text().splitlines() if line.strip())
    assert loc == {"vue": 2351, "ts": 1129, "php": 1114, "css": 123}


def test_a0_1_single_author_no_remote(repo):
    assert len(set(git(repo, "log", "--format=%ae").splitlines())) == 1
    assert git(repo, "remote") == ""
    assert git(repo, "branch", "--show-current") == "main"


def test_a0_1_build_rejects_non_empty_target(tmp_path):
    (tmp_path / "keep.txt").write_text("x")
    assert build(tmp_path).returncode != 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep.txt"]


def test_a0_2_two_builds_same_head(repo, tmp_path):
    assert build(tmp_path / "again").returncode == 0
    assert git(tmp_path / "again", "rev-parse", "HEAD") == git(repo, "rev-parse", "HEAD")


def test_a0_2_ignores_machine_git_config(repo, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text("[commit]\n\tgpgsign = true\n[init]\n\tdefaultBranch = master\n"
                                     "[core]\n\tautocrlf = true\n[user]\n\tname = Someone Else\n")
    env = {"PATH": os.environ["PATH"], "HOME": str(home)}
    result = build(tmp_path / "hostile", env)
    assert result.returncode == 0, result.stderr
    assert git(tmp_path / "hostile", "rev-parse", "HEAD") == git(repo, "rev-parse", "HEAD")
