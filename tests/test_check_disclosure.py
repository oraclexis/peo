"""tools/check_disclosure.py: no retained finding named next to an open source repository (spec 16, section 2.3)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "check_disclosure.py"

DOC = """# Dogfooding

## Repositories

| Repository | Stack |
|---|---|
| [acme/widget](https://github.com/acme/widget) (MIT) | NestJS |

{body}

## Withheld findings (open source repositories)

| Repository | Code | Count |
|---|---|---|
{withheld}
"""


def run(tmp_path, body="", withheld="", args=(), stdin=None, denylist=None):
    doc = tmp_path / "dogfooding.md"
    doc.write_text(DOC.format(body=body, withheld=withheld))
    cmd = [sys.executable, str(SCRIPT), str(doc), *args]
    if denylist is not None:
        (tmp_path / "deny").write_text(denylist)
        cmd += ["--denylist", str(tmp_path / "deny")]
    return subprocess.run(cmd, capture_output=True, text=True, input=stdin)


def test_clean_document_passes(tmp_path):
    r = run(tmp_path, body="| widget | `X-DATA-STORE` | compose | `already-known` |")
    assert r.returncode == 0, r.stderr


def test_retained_code_next_to_repository_fails(tmp_path):
    r = run(tmp_path, body="| widget | `X-SECRET-TRACKED` | — | pending |")
    assert r.returncode == 1
    assert "line" in r.stderr and "X-SECRET-TRACKED" in r.stderr


def test_owner_name_and_withheld_word_fail(tmp_path):
    for line in ("for acme, expectations are withheld", "| acme/widget | `X-SECRET-*` | x |",
                 "acme: `X-LITERAL-IN-AGENT-CONFIG` kept locally"):
        assert run(tmp_path, body=line).returncode == 1, line


def test_withheld_section_may_name_repository(tmp_path):
    r = run(tmp_path, withheld="| acme/widget | `X-SECRET-TRACKED` | 1 |")
    assert r.returncode == 0, r.stderr


def test_code_without_repository_passes(tmp_path):
    r = run(tmp_path, body="- `X-SECRET-TRACKED` on an open source repository: counts per code only.")
    assert r.returncode == 0, r.stderr


def test_denylist_literal_in_stdin_fails_without_echoing_it(tmp_path):
    r = run(tmp_path, args=["--stdin"], stdin="PR body mentions secret/path.env here\n",
            denylist="# local only\nsecret/path.env\n")
    assert r.returncode == 1
    assert "secret/path.env" not in r.stderr + r.stdout


def test_denylist_absent_entries_pass(tmp_path):
    r = run(tmp_path, args=["--stdin"], stdin="nothing sensitive\n", denylist="secret/path.env\n")
    assert r.returncode == 0, r.stderr


def test_pre_push_checks_pushed_messages_and_document(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    g = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run([*g[:3], "init", "-q"], check=True)
    doc = repo / "dogfooding.md"
    doc.write_text(DOC.format(body="", withheld=""))
    subprocess.run([*g, "add", "."], check=True)
    subprocess.run([*g, "commit", "-qm", "mentions secret/path.env"], check=True)
    sha = subprocess.run([*g[:3], "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (tmp_path / "deny").write_text("secret/path.env\n")
    hook = f"refs/heads/x {sha} refs/heads/x {'0' * 40}\n"
    cmd = [sys.executable, str(SCRIPT), "dogfooding.md", "--pre-push", "--denylist", str(tmp_path / "deny")]
    r = subprocess.run(cmd, cwd=repo, input=hook, capture_output=True, text=True)
    assert r.returncode == 1 and "denylist entry #1" in r.stderr
    assert "secret/path.env" not in r.stderr

    doc.write_text(DOC.format(body="| widget | `X-SECRET-TRACKED` | — |", withheld=""))
    subprocess.run([*g, "commit", "-qam", "clean message"], check=True)
    sha2 = subprocess.run([*g[:3], "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    hook = f"refs/heads/x {sha2} refs/heads/x {sha}\n"
    r = subprocess.run(cmd, cwd=repo, input=hook, capture_output=True, text=True)
    assert r.returncode == 1 and "X-SECRET-TRACKED" in r.stderr and "denylist" not in r.stderr
