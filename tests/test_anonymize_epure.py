"""tools/anonymize_epure.py on a synthetic repository shaped like ÉPURE (spec 16, section 2)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "anonymize_epure.py"

ENV = {**os.environ, "GIT_AUTHOR_NAME": "Real Person", "GIT_AUTHOR_EMAIL": "real@epure.studio",
       "GIT_COMMITTER_NAME": "Real Person", "GIT_COMMITTER_EMAIL": "real@epure.studio"}

FILES = {
    "package.json": '{\n  "name": "epure-site",\n  "scripts": {"test": "vitest run"}\n}\n',
    "README.md": "# ÉPURE\n\nSite epure.studio.\n\n## TODO\n\n- [ ] `BlockRenderer.vue` à faire\n"
                 "   apps/laravel/  ← backend (à venir)\n",
    "HANDOFF.md": "# Passation\n\nVoir app/components/BlockRenderer.vue et backend/app/Foo.php.\n",
    "CLAUDE.md": "# Épure\n\n- Zéro border-radius.\n- Contact: admin@epure.studio\n",
    "docker-compose.yml": "services:\n  api:\n    environment:\n"
                          "      DB_DATABASE: ${DB_DATABASE:-epure}\n"
                          "      DB_PASSWORD: ${DB_PASSWORD:-secret}\n",
    "Makefile": "admin:\n\tphp artisan make:filament-user --email=admin@epure.studio --password=Sup3rPass\n",
    "nuxt.config.ts": "export default defineNuxtConfig({ app: { head: { title: 'Épure' } } })\n",
    "app/components/BlockRenderer.vue": "<template>\n\n  <div>épure</div>\n</template>\n",
    "backend/app/Foo.php": "<?php\n\nclass Foo {}\n",
    "public/logo.png": b"\x89PNG\r\n\x1a\n\x00\x00binary",
}
BRANCHES = ["feat/A1-canvas", "feat/A2-rail", "feat/plan-credits", "fix/particles-hero"]


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, env=ENV, check=True, capture_output=True, text=True).stdout


@pytest.fixture()
def source(tmp_path):
    repo = tmp_path / "nuxt-app"
    for rel, content in FILES.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    run("git", "init", "-q", "-b", "main", cwd=repo)
    run("git", "config", "commit.gpgsign", "false", cwd=repo)
    run("git", "add", "-A", cwd=repo)
    run("git", "commit", "-q", "-m", "chore: init", cwd=repo)
    for i, branch in enumerate(BRANCHES, start=1):
        run("git", "checkout", "-q", "-b", branch, cwd=repo)
        (repo / "README.md").write_text(FILES["README.md"] + f"<!-- {i} -->\n", encoding="utf-8")
        run("git", "commit", "-q", "-am", f"feat(front): changement {i}", cwd=repo)
        run("git", "checkout", "-q", "main", cwd=repo)
        if i <= 3:
            run("git", "merge", "-q", "--no-ff", branch, "-m", f"merge: {branch}", cwd=repo)
    return repo


def anonymize(source, out):
    return subprocess.run([sys.executable, str(SCRIPT), "--source", str(source), "--out", str(out)],
                          capture_output=True, text=True)


def test_output_is_clean_and_keeps_shape(source, tmp_path):
    out = tmp_path / "fx-epure"
    result = anonymize(source, out)
    assert result.returncode == 0, result.stdout + result.stderr
    tree = out / "tree"
    everything = "".join(p.read_text("utf-8", "replace") for p in tree.rglob("*") if p.is_file())
    for forbidden in ("epure", "Épure", "ÉPURE", "secret", "Sup3rPass", "real@"):
        assert forbidden.lower() not in everything.lower(), forbidden
    assert "example.test" in everything
    # docs keep their line numbers (drift golden files reference lines)
    for doc in ("README.md", "HANDOFF.md", "CLAUDE.md"):
        assert (tree / doc).read_text().count("\n") == FILES[doc].count("\n") + (doc == "README.md")
    # code files keep their number of non-empty lines, not their content
    vue = (tree / "app/components/BlockRenderer.vue").read_text()
    assert vue == "// line 1\n// line 2\n// line 3\n"
    assert (tree / "public/logo.png").read_bytes() == b""
    assert "${DB_PASSWORD:-changeme}" in (tree / "docker-compose.yml").read_text()


def test_build_script_recreates_history_shape(source, tmp_path):
    out = tmp_path / "fx-epure"
    assert anonymize(source, out).returncode == 0
    manifest = json.loads((out / "MANIFEST.json").read_text())
    target = tmp_path / "rebuilt"
    subprocess.run(["bash", str(out / "build.sh"), str(target)], check=True, capture_output=True)
    src_commits = int(run("git", "rev-list", "--count", "HEAD", cwd=source))
    assert int(run("git", "rev-list", "--count", "HEAD", cwd=target)) == src_commits
    assert manifest["history"]["merges"] == 3
    branches = run("git", "for-each-ref", "refs/heads", "--format=%(refname:short)", cwd=target).split()
    assert sorted(b for b in branches if b != "main") == sorted(
        ["feat/A1-item-1", "feat/A2-item-2", "feat/item-3", "fix/item-4"])
    tracked = run("git", "ls-files", cwd=target).split()
    assert len(tracked) == len(FILES)
    # HANDOFF.md is never touched after the first commit; files it cites are (drift rule D4)
    assert int(run("git", "rev-list", "--count", "HEAD", "--", "HANDOFF.md", cwd=target)) == 1
    assert manifest["touched_after_handoff"] == ["app/components/BlockRenderer.vue", "backend/app/Foo.php"]


def test_refuses_output_inside_source(source):
    result = anonymize(source, source / "out")
    assert result.returncode == 2
    assert "outside the source" in result.stderr
