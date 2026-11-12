"""Discovery, conventions and repository state (spec 12, sections 4, 4.3 and 9)."""

import json
from pathlib import Path

import pytest
from peo.discovery.history import branch_names, branches, commits, read_history

from peo.discovery import discover
from peo.runner import Result


def git_fake(answers: dict):
    """Fake runner: answers[tuple(args)] -> stdout (str) or an int return code."""
    calls = []

    def run(args, cwd):
        calls.append(list(args))
        answer = answers.get(tuple(args))
        if answer is None or isinstance(answer, int):
            return Result(answer or 128, b"", b"")
        return Result(0, answer.encode(), b"")

    run.calls = calls
    return run


LS = ("git", "ls-files", "-z")
COUNT = ("git", "rev-list", "--count", "HEAD")
REFS = ("git", "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes")
LOG = ("git", "log", "-200", "--format=%P%x1f%s")
REMOTE = ("git", "remote")
ORIGIN_HEAD = ("git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
HEAD = ("git", "symbolic-ref", "--short", "HEAD")


def write(root: Path, files: dict) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content) if isinstance(content, dict) else content)


# --- branches --------------------------------------------------------------------------------

def test_branch_names_local_and_remote():
    refs = ["main", "feat/a", "origin/feat/a", "origin/HEAD", "origin", "origin/main", "fix/b"]
    assert branch_names(refs, ["origin"]) == ["feat/a", "fix/b"]


def test_branch_main_branches_excluded():
    assert branch_names(["main", "master", "develop", "HEAD", "feat/x"], []) == ["feat/x"]


def test_branch_fewer_than_five_is_null():
    assert branches(["feat/a", "feat/b", "feat/c", "fix/d"]) is None


@pytest.mark.parametrize("name, style", [("feat/20260101-120000-x", "timestamp"), ("feat/001-x", "numeric"),
                                         ("feat/A1-x", "alnum-id"), ("feat/x", "free")])
def test_branch_styles(name, style):
    b = branches([name.replace("x", f"x{i}") for i in range(5)])
    assert b["id_style"] == style
    assert "id_shares" not in b


def test_branch_mixed_shares():
    names = [f"feat/A{i}-slug" for i in range(24)] + [f"fix/slug-{i}" for i in range(22)]
    b = branches(names)
    assert b["id_style"] == "mixed"
    assert b["id_shares"] == {"alnum-id": 0.52, "free": 0.48}


@pytest.mark.parametrize("last, alphabet", [("slug", "[a-z0-9-]+"), ("Slug", "[A-Za-z0-9-]+"),
                                            ("s.lug", "[A-Za-z0-9._-]+"), ("s+lug", ".+")])
def test_branch_alphabet_ladder(last, alphabet):
    b = branches([f"feat/{last}{i}" for i in range(5)])
    assert b["pattern"] == f"^(feat)/{alphabet}$"


def test_branch_prefixes_sorted_and_pattern():
    b = branches(["fix/a", "feat/B", "feat/C", "fix/d", "feat/e"])   # 60 % lowercase
    assert b["prefixes"] == ["feat", "fix"]
    assert b["pattern"] == "^(feat|fix)/[A-Za-z0-9-]+$"
    assert b["share"] == 1.0
    assert b["confidence"] == "fact"


def test_branch_no_majority_prefix():
    b = branches(["a", "b", "c", "d", "feat/e"])
    assert b["prefixes"] == []
    assert b["pattern"] == "^[a-z0-9-]+$"


def test_branch_evidence():
    names = [f"feat/A{i}-slug" for i in range(24)] + [f"fix/slug-{i}" for i in range(22)]
    assert branches(names)["evidence"] == "46 of 46 branches outside main"


# --- commits ---------------------------------------------------------------------------------

def line(subject: str, parents: str = "a1") -> str:
    return f"{parents}\x1f{subject}"


def test_commit_merges_excluded():
    lines = [line("merge: feat/x", "a b"), line("Merge branch 'x'"), line("feat: x", "a b"),
             line("feat: ajout des pages pour les clients")]
    c = commits(lines)
    assert c["excluded_merges"] == 3
    assert c["evidence"] == "1 of 1 non-merge subjects"


@pytest.mark.parametrize("conventional, style", [(80, "conventional"), (79, "free")])
def test_commit_conventional_threshold(conventional, style):
    lines = [line("feat: x")] * conventional + [line("random subject")] * (100 - conventional)
    c = commits(lines)
    assert c["style"] == style
    assert c["share"] == conventional / 100


@pytest.mark.parametrize("subjects, language", [
    (["feat: ajout des pages", "fix: correction pour les liens"], "fr"),
    (["feat: add the page", "fix: update for links"], "en"),
    (["feat: ajout the page"], "unknown"),          # 1 against 1
    (["feat: refactor"], "unknown"),                # 0 against 0
    (["feat: ajout"], "unknown"),                   # 1 against 0: at least 2 needed
    (["feat(pour les): x"], "unknown"),             # only the part after ': ' counts
])
def test_commit_language(subjects, language):
    assert commits([line(s) for s in subjects])["language"] == language


def test_commit_no_subject():
    c = commits([line("merge: x", "a b")])
    assert (c["style"], c["language"]) == ("unknown", "unknown")


def test_commit_evidence():
    lines = [line(f"feat: ajout des pages {i}") for i in range(47)] + [line("merge: x", "a b")] * 46
    c = commits(lines)
    assert c == {"style": "conventional", "language": "fr", "share": 1.0, "excluded_merges": 46,
                 "confidence": "fact", "evidence": "47 of 47 non-merge subjects"}


# --- repository ------------------------------------------------------------------------------

@pytest.mark.parametrize("count, kind", [(None, {"value": "new", "confidence": "fact", "evidence": "0 commits"}),
                                         ("1", {"value": "new", "confidence": "fact", "evidence": "1 commits"}),
                                         ("93", {"value": "existing", "confidence": "fact",
                                                 "evidence": "93 commits"})])
def test_repo_kind(tmp_path, count, kind):
    run = git_fake({COUNT: f"{count}\n" if count else 128, HEAD: "main\n"})
    assert read_history(tmp_path, run, is_git=True)["kind"] == kind


def test_repo_remote_and_default_branch(tmp_path):
    run = git_fake({REMOTE: "origin\n", ORIGIN_HEAD: "origin/trunk\n", HEAD: "feat/x\n"})
    assert read_history(tmp_path, run, is_git=True)["git"] == {"remote": True, "default_branch": "trunk"}
    run = git_fake({REMOTE: "", HEAD: "main\n"})
    assert read_history(tmp_path, run, is_git=True)["git"] == {"remote": False, "default_branch": "main"}


def test_repo_outside_git(tmp_path):
    run = git_fake({})
    h = read_history(tmp_path, run, is_git=False)
    assert run.calls == []
    assert h["kind"] == {"value": "new", "confidence": "likely", "evidence": "not a git repository"}
    assert h["git"] == {"remote": False}
    assert h["conventions"] == {"branches": None,
                                "commits": {"style": "unknown", "language": "unknown", "confidence": "unknown"}}


@pytest.mark.parametrize("files, ci", [
    ({".gitlab-ci.yml": "x"}, {"kind": "gitlab", "file": ".gitlab-ci.yml"}),
    ({".github/workflows/b.yml": "x", ".github/workflows/a.yaml": "x"},
     {"kind": "github", "file": ".github/workflows/a.yaml"}),
    ({}, {"kind": "none", "file": None}),
])
def test_repo_ci(tmp_path, files, ci):
    write(tmp_path, {"package.json": {"dependencies": {"vue": "^3.5.0"}}, **files})
    assert discover(tmp_path, run=git_fake({}), which=lambda n: None)["ci"] == ci


def test_repo_gaps_order(tmp_path):
    write(tmp_path, {"package.json": {"dependencies": {"vue": "^3.5.0"}},
                     "backend/composer.json": {"require-dev": {"laravel/pint": "^1.13"}}})
    p = discover(tmp_path, run=git_fake({}), which=lambda n: None)
    assert p["gaps"] == ["no-ci", "no-verify", "no-remote", "no-tests:root", "no-tests:backend", "no-lint:root"]


def test_repo_no_ci_gap_with_ci(tmp_path):
    write(tmp_path, {"package.json": {"dependencies": {"vue": "^3.5.0"}}, ".github/workflows/ci.yml": "x"})
    assert "no-ci" not in discover(tmp_path, run=git_fake({}), which=lambda n: None)["gaps"]
