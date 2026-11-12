"""Discovery, documentation drift D1 to D4 (spec 12, section 6)."""

import json
from pathlib import Path

import pytest

from peo.discovery import discover
from peo.discovery.drift import handoff_drift
from peo.runner import Result


def no_git(args, cwd):
    return Result(128, b"", b"")


def write(root: Path, files: dict) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content) if isinstance(content, dict) else content)


def drift(root: Path) -> list:
    return discover(root, run=no_git, which=lambda name: None)["docs_drift"]


def finding(rule, file, line, message):
    return {"rule": rule, "file": file, "line": line, "confidence": "likely", "message": message}


# --- D1 --------------------------------------------------------------------------------------

def test_drift_d1_unchecked_box(tmp_path):
    write(tmp_path, {"README.md": "- [ ] écrire `x.vue`\n", "src/x.vue": "x\n"})
    assert drift(tmp_path) == [finding("D1", "README.md", 1,
                                       "Line marked '- [ ]' cites x.vue, which exists (src/x.vue)")]


def test_drift_d1_marker_order(tmp_path):
    write(tmp_path, {"README.md": "- [ ] TODO : écrire x.vue\n", "src/x.vue": "x\n"})
    assert "'- [ ]'" in drift(tmp_path)[0]["message"]


@pytest.mark.parametrize("line, marker", [("todo: x.vue", "TODO"), ("x.vue À venir", "à venir"),
                                          ("x.vue coming soon", "coming soon"), ("WIP x.vue", "WIP"),
                                          ("x.vue pas encore", "pas encore"), ("x.vue not yet", "not yet")])
def test_drift_d1_markers_case_insensitive(tmp_path, line, marker):
    write(tmp_path, {"README.md": line + "\n", "src/x.vue": "x\n"})
    assert drift(tmp_path)[0]["message"].startswith(f"Line marked '{marker}'")


def test_drift_d1_section_title(tmp_path):
    write(tmp_path, {"README.md": "## À venir\n\nRefaire x.vue\n\n## Fait\n\nx.vue\n", "src/x.vue": "x\n"})
    assert drift(tmp_path) == [finding("D1", "README.md", 3,
                                       "Line marked 'à venir' cites x.vue, which exists (src/x.vue)")]


def test_drift_d1_absent_file_is_not_d1(tmp_path):
    write(tmp_path, {"README.md": "TODO: write y.vue\n"})
    assert drift(tmp_path) == []


def test_drift_d1_one_finding_per_line(tmp_path):
    write(tmp_path, {"README.md": "TODO: x.vue and z.ts\n", "src/x.vue": "x\n", "src/z.ts": "z\n"})
    assert len(drift(tmp_path)) == 1


def test_drift_d1_name_resolution_first_sorted(tmp_path):
    write(tmp_path, {"README.md": "TODO: x.vue\n", "b/x.vue": "x\n", "a/x.vue": "x\n"})
    assert drift(tmp_path)[0]["message"].endswith("(a/x.vue)")


def test_drift_d1_component_dir(tmp_path):
    write(tmp_path, {"README.md": "TODO: move backend\n",
                     "backend/composer.json": {"require": {"laravel/framework": "^11.9"}}})
    assert drift(tmp_path) == [finding("D1", "README.md", 1,
                                       "Line marked 'TODO' cites backend, which exists (backend)")]


# --- D2 --------------------------------------------------------------------------------------

def test_drift_d2_npm_run_missing(tmp_path):
    write(tmp_path, {"README.md": "Run `npm run deploy`.\n", "package.json": {"scripts": {"build": "x"}}})
    assert drift(tmp_path) == [finding("D2", "README.md", 1,
                                       "Command 'npm run deploy' is documented but not defined in package.json")]


def test_drift_d2_make_target(tmp_path):
    write(tmp_path, {"README.md": "`make up`\n`make down`\n", "Makefile": "up:\n\ttrue\n"})
    assert drift(tmp_path) == [finding("D2", "README.md", 2,
                                       "Command 'make down' is documented but not defined in Makefile")]


def test_drift_d2_builtins_ignored(tmp_path):
    write(tmp_path, {"README.md": "`yarn install`\n`composer require monolog`\n`php artisan migrate`\n",
                     "package.json": {"scripts": {}}, "composer.json": {"require": {}}})
    assert drift(tmp_path) == []


def test_drift_d2_npm_test_not_checked(tmp_path):
    write(tmp_path, {"README.md": "npm test\n", "package.json": {"scripts": {}}})
    assert drift(tmp_path) == []


# --- D3 --------------------------------------------------------------------------------------

def test_drift_d3_missing_path(tmp_path):
    write(tmp_path, {"README.md": "Moved to `apps/api/`.\n"})
    assert drift(tmp_path) == [finding("D3", "README.md", 1, "Path apps/api/ does not exist")]


def test_drift_d3_existing_dir_by_prefix(tmp_path):
    write(tmp_path, {"README.md": "See app/pages/ and app/pages/index.vue\n", "app/pages/index.vue": "x\n"})
    assert drift(tmp_path) == []


def test_drift_d3_url_and_absolute_ignored(tmp_path):
    write(tmp_path, {"README.md": "https://example.test/a/b and /usr/bin/x\n"})
    assert drift(tmp_path) == []


# --- D4 --------------------------------------------------------------------------------------

def git_fake(counts: dict):
    calls = []

    def run(args, cwd):
        calls.append(list(args))
        answers = {("git", "log", "-1", "--format=%H", "--", "HANDOFF.md"): "h\n",
                   ("git", "log", "-1", "--format=%H", "--", "src/x.vue"): "f\n"}
        answers |= {("git", "rev-list", "--count", k): f"{v}\n" for k, v in counts.items()}
        out = answers.get(tuple(args))
        return Result(0, out.encode(), b"") if out else Result(128, b"", b"")

    run.calls = calls
    return run


def test_drift_d4_over_20_commits(tmp_path):
    run = git_fake({"h..f": 21, "h..HEAD": 92})
    assert handoff_drift(tmp_path, "HANDOFF.md", "Next: `src/x.vue`\n", ["HANDOFF.md", "src/x.vue"], run) == {
        "rule": "D4", "file": "HANDOFF.md", "confidence": "likely",
        "message": "Last changed 92 commits before HEAD while files it cites changed since"}


def test_drift_d4_20_commits_is_not_drift(tmp_path):
    run = git_fake({"h..f": 20, "h..HEAD": 92})
    assert handoff_drift(tmp_path, "HANDOFF.md", "Next: `src/x.vue`\n", ["HANDOFF.md", "src/x.vue"], run) is None


def test_drift_d4_outside_git(tmp_path):
    write(tmp_path, {"HANDOFF.md": "Next: `src/x.vue`\n", "src/x.vue": "x\n"})
    calls = []

    def run(args, cwd):
        calls.append(list(args))
        return Result(128, b"", b"")

    discover(tmp_path, run=run, which=lambda name: None)
    assert all(c[:2] != ["git", "log"] or "-1" not in c for c in calls)


# --- order -----------------------------------------------------------------------------------

def test_drift_order(tmp_path):
    write(tmp_path, {"README.md": "TODO: x.vue\nSee `apps/api/`\n", "CLAUDE.md": "TODO: x.vue\n",
                     "src/x.vue": "x\n"})
    assert [(d["rule"], d["file"], d.get("line")) for d in drift(tmp_path)] == [
        ("D1", "CLAUDE.md", 1), ("D1", "README.md", 1), ("D3", "README.md", 2)]
