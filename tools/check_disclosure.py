#!/usr/bin/env python3
"""Disclosure guard for docs/dogfooding.md (spec 16, section 2.3; document 07, sections 7.1 and 7.1 bis).

    check_disclosure.py DOC                       versioned rule on DOC (CI)
    check_disclosure.py DOC --stdin               also check the text on stdin (a PR body, for instance)
    check_disclosure.py DOC --pre-push            git pre-push hook: also check the commits being pushed
    --denylist FILE                               local literals (default: <git dir>/info/disclosure-denylist)

Versioned rule: outside the "Withheld findings" section, a line naming an open source repository
of the document must not cite a retained code or the word "withheld".
Local rule: no denylist literal in the checked text; a failure never prints the literal.
Lexical only: a leak by inference (a severity that betrays a file) is not caught.
Standard library only.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_LINK = re.compile(r"\[([\w.-]+)/([\w.-]+)\]\(https://github\.com/")
RETAINED = re.compile(r"X-SECRET-TRACKED|X-LITERAL-IN-AGENT-CONFIG|X-SECRET-\*|\bwithheld\b", re.I)
WITHHELD_HEADING = "## withheld findings"
ZERO = "0" * 40


def repo_tokens(doc: str) -> list[re.Pattern]:
    names = set()
    for owner, name in REPO_LINK.findall(doc):
        names |= {owner, name, f"{owner}/{name}"}
    return [re.compile(rf"(?<![\w-]){re.escape(n)}(?![\w-])", re.I) for n in sorted(names)]


def retained_lines(text: str, tokens: list[re.Pattern], where: str, sections: bool) -> list[str]:
    errors, exempt = [], False
    for no, line in enumerate(text.splitlines(), 1):
        if sections and line.startswith("## "):
            exempt = line.lower().startswith(WITHHELD_HEADING)
        if exempt:
            continue
        code = RETAINED.search(line)
        repo = next((t.pattern for t in tokens if t.search(line)), None)
        if code and repo:
            errors.append(f"{where}: line {no} names an open source repository next to {code.group(0)}")
    return errors


def denylist_hits(text: str, literals: list[str], where: str) -> list[str]:
    low = text.lower()
    return [f"{where}: denylist entry #{i} found" for i, lit in enumerate(literals, 1) if lit.lower() in low]


def load_denylist(path: Path | None) -> list[str]:
    if path is None:
        r = subprocess.run(["git", "rev-parse", "--git-common-dir"], capture_output=True, text=True)
        if r.returncode != 0:
            return []
        path = Path(r.stdout.strip()) / "info" / "disclosure-denylist"
    if not path.is_file():
        return []
    return [s for s in (ln.strip() for ln in path.read_text().splitlines()) if s and not s.startswith("#")]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def pushed(hook_input: str) -> list[tuple[str, str, str]]:
    """(ref, sha, text) per pushed ref; text = commit messages and added lines of the pushed commits."""
    out = []
    for line in hook_input.splitlines():
        parts = line.split()
        if len(parts) != 4 or parts[1] == ZERO:
            continue
        ref, sha, remote_sha = parts[2], parts[1], parts[3]
        rng = [sha, "--not", "--remotes"] if remote_sha == ZERO else [f"{remote_sha}..{sha}"]
        lines = git("log", "-p", "--format=%B", *rng).splitlines()
        text = "\n".join(ln[1:] if ln.startswith("+") else ln for ln in lines
                         if not ln.startswith(("-", " ", "@@", "diff ", "index ", "+++")))
        out.append((ref, sha, text))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("doc", type=Path)
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--pre-push", action="store_true")
    ap.add_argument("--denylist", type=Path)
    a = ap.parse_args(argv)

    doc = a.doc.read_text()
    tokens, literals = repo_tokens(doc), load_denylist(a.denylist)
    errors = retained_lines(doc, tokens, str(a.doc), sections=True) + denylist_hits(doc, literals, str(a.doc))
    if a.stdin:
        text = sys.stdin.read()
        errors += retained_lines(text, tokens, "stdin", sections=False) + denylist_hits(text, literals, "stdin")
    if a.pre_push:
        for ref, sha, text in pushed(sys.stdin.read()):
            errors += denylist_hits(text, literals, f"push {ref}")
            r = subprocess.run(["git", "show", f"{sha}:{a.doc.as_posix()}"], capture_output=True, text=True)
            if r.returncode == 0:  # the pushed version of DOC
                errors += retained_lines(r.stdout, repo_tokens(r.stdout), f"push {ref} {a.doc}", sections=True)
    for e in errors:
        print(e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
