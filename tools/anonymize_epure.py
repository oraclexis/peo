#!/usr/bin/env python3
"""Build the anonymized `fx-epure` fixture from the real project (spec 16, section 2).

Run ONCE on the machine that holds the project. Reads the source repository, never writes to it.

    python3 tools/anonymize_epure.py --source ~/Documents/amirouche/nuxt-app --out tools/out/fx-epure

Output (to review, then copy to tests/fixtures/fx-epure/):
    tree/          tracked files, anonymized: manifests and docs kept as text, code files emptied
                   (same name, same number of non-empty lines), binaries emptied
    build.sh       recreates a fake git history with the same shape (commit count, merges,
                   branch naming styles, conventional French subjects)
    MANIFEST.json  what was done to each file, and the audit result

Exit code 0 when the audit is clean, 1 when it found something to check by hand.
Compatible with Python 3.9+ (system python3 on macOS); standard library only.
"""

import argparse
import json
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------- configuration

CODE_EXTENSIONS = {".vue", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".jsx", ".php", ".css", ".scss"}

# Code-like files kept as text because discovery reads them (spec 16, section 2).
KEEP_AS_TEXT = {
    "nuxt.config.ts", "vitest.config.ts", "vitest.config.js", "playwright.config.ts",
    "tailwind.config.ts", "tailwind.config.js", "vite.config.ts", "tsconfig.json",
}

DOMAIN_REPLACEMENTS = [("epure.studio", "example.test")]

NAME_REPLACEMENTS = [  # order matters: accented and upper forms first
    ("ÉPURE", "SAMPLE"), ("Épure", "Sample"), ("épure", "sample"),
    ("EPURE", "SAMPLE"), ("Epure", "Sample"), ("epure", "sample"),
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# ${DB_PASSWORD:-secret} -> ${DB_PASSWORD:-changeme}
ENV_DEFAULT_RE = re.compile(r"(\$\{[A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|KEY)[A-Z0-9_]*:-)([^}]*)(\})")
# password=..., PASSWORD: ..., --password=... -> changeme
ASSIGN_RE = re.compile(
    r"(?i)((?:password|passwd|secret|token|api[_-]?key)[A-Za-z0-9_]*[\"']?\s*(?::-|[:=])\s*[\"']?)"
    r"([^\s\"'}]+)"
)

AUDIT_PATTERNS = [
    ("name", re.compile(r"(?i)[ée]pure")),
    ("secret-word", re.compile(r"(?i)\bsecret\b")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.test)[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
]
AUDIT_SKIP_SUFFIXES = {".lock"}
AUDIT_SKIP_NAMES = {"package-lock.json", "composer.lock"}

MERGE_SUBJECT_RE = re.compile(r"^(merge\b|Merge\b)")
DEFAULT_BRANCHES = {"main", "master", "develop", "HEAD"}

# ---------------------------------------------------------------- helpers


def git(source, *args):
    out = subprocess.run(["git", "-C", str(source), *args], check=True,
                         capture_output=True)
    return out.stdout.decode("utf-8", "replace")


def is_binary(data):
    return b"\x00" in data[:8192]


def anonymize_text(text):
    counts = {"domain": 0, "name": 0, "email": 0, "secret": 0}
    for old, new in DOMAIN_REPLACEMENTS:
        counts["domain"] += text.count(old)
        text = text.replace(old, new)
    for old, new in NAME_REPLACEMENTS:
        counts["name"] += text.count(old)
        text = text.replace(old, new)

    def email_sub(m):
        if m.group(0).endswith("@example.test"):
            return m.group(0)
        counts["email"] += 1
        return "user@example.test"

    text = EMAIL_RE.sub(email_sub, text)

    def env_sub(m):
        counts["secret"] += 1
        return m.group(1) + "changeme" + m.group(3)

    text = ENV_DEFAULT_RE.sub(env_sub, text)

    def assign_sub(m):
        if m.group(2) in ("changeme", "null", "", "${"):
            return m.group(0)
        if m.group(2).startswith("${") or m.group(2).startswith("$"):
            return m.group(0)  # reference to another variable, not a value
        counts["secret"] += 1
        return m.group(1) + "changeme"

    text = ASSIGN_RE.sub(assign_sub, text)
    text = re.sub(r"(?i)\bsecret\b", lambda m: "changeme", text)
    return text, {k: v for k, v in counts.items() if v}


def anonymize_path(rel):
    out = rel
    for old, new in DOMAIN_REPLACEMENTS + NAME_REPLACEMENTS:
        out = out.replace(old, new)
    return out


def emptied_code(text):
    non_empty = sum(1 for line in text.splitlines() if line.strip())
    return "".join("// line %d\n" % (i + 1) for i in range(non_empty))


# ---------------------------------------------------------------- history shape


def branch_style(name):
    last = name.split("/")[-1]
    if re.match(r"^[0-9]{8}-[0-9]{6}-", last):
        return "timestamp"
    if re.match(r"^[0-9]{3,}-", last):
        return "numeric"
    if re.match(r"^[A-Za-z]+[0-9]+-", last):
        return "alnum-id"
    return "free"


def history_shape(source):
    subjects = git(source, "log", "--format=%P%x09%s").splitlines()
    total = len(subjects)
    merges = sum(1 for line in subjects
                 if len(line.split("\t", 1)[0].split()) > 1
                 or MERGE_SUBJECT_RE.match(line.split("\t", 1)[-1]))
    branches = [b for b in git(source, "for-each-ref", "refs/heads",
                               "--format=%(refname:short)").split()
                if b not in DEFAULT_BRANCHES]
    fake = []
    for k, name in enumerate(sorted(branches), start=1):
        prefix = name.split("/")[0] if "/" in name else None
        style = branch_style(name)
        if style == "alnum-id":
            token = re.match(r"^([A-Za-z]+[0-9]+)-", name.split("/")[-1]).group(1)
            last = "%s-item-%d" % (token, k)
        elif style == "numeric":
            last = "%03d-item-%d" % (k, k)
        else:
            last = "item-%d" % k
        fake.append((prefix + "/" + last) if prefix else last)
    return {"commits": total, "merges": merges, "branches": fake}


def cited_files(tree, handoff_rel):
    """Files cited by the handoff document: they must change after it (drift rule D4)."""
    handoff = tree / handoff_rel
    if not handoff.exists():
        return []
    names = set(re.findall(r"[\w./-]+\.[A-Za-z]{1,5}", handoff.read_text("utf-8", "replace")))
    hits = []
    for path in sorted(p for p in tree.rglob("*") if p.is_file()):
        rel = path.relative_to(tree).as_posix()
        if rel == handoff_rel:
            continue
        if rel in names or path.name in names:
            hits.append(rel)
    return hits


BUILD_TEMPLATE = """#!/usr/bin/env bash
# Generated by tools/anonymize_epure.py. Recreates a fake history with the shape of the source:
# {commits} commits ({merges} merges), {nbranches} branches outside main.
# Usage: build.sh TARGET_DIR   (TARGET_DIR must not exist)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET="$1"
[ ! -e "$TARGET" ] || {{ echo "target exists: $TARGET" >&2; exit 1; }}
cp -R "$HERE/tree" "$TARGET"
cd "$TARGET"
export GIT_AUTHOR_NAME="Sample Dev" GIT_AUTHOR_EMAIL="dev@example.test"
export GIT_COMMITTER_NAME="Sample Dev" GIT_COMMITTER_EMAIL="dev@example.test"
n=0
tick() {{ n=$((n+1)); export GIT_AUTHOR_DATE="$((1772319600 + n*3600)) +0100" GIT_COMMITTER_DATE="$((1772319600 + n*3600)) +0100"; }}
git init -q -b main 2>/dev/null || {{ git init -q && git checkout -q -b main; }}
git config commit.gpgsign false
tick; git add -A; git commit -q -m "chore: initialisation du dépôt"
TOUCH=({touch})
touch_one() {{ if [ ${{#TOUCH[@]}} -gt 0 ]; then printf '\\n' >> "${{TOUCH[$(( $1 % ${{#TOUCH[@]}} ))]}}"; else git commit -q --allow-empty -m "$2"; return 1; fi; }}
{extra}
i=0
for b in {branches}; do
  i=$((i+1))
  git checkout -q -b "$b"
  tick
  case "$b" in fix/*) msg="fix: correction $i" ;; *) msg="feat: changement $i" ;; esac
  if touch_one "$i" "$msg"; then git add -A; git commit -q -m "$msg"; fi
  git checkout -q main
  if [ "$i" -le {merges} ]; then tick; git merge -q --no-ff "$b" -m "merge: branche $i"; fi
done
echo "built $(git rev-list --count HEAD) commits, $(git for-each-ref refs/heads | wc -l | tr -d ' ') branches in $TARGET"
"""


def write_build_script(out, shape, touch):
    branches = shape["branches"]
    non_merge_needed = shape["commits"] - shape["merges"]
    merges = min(shape["merges"], len(branches))
    extra_direct = max(0, non_merge_needed - 1 - len(branches))
    extra = ""
    if extra_direct:
        extra = ('for j in $(seq 1 %d); do tick; msg="docs: mise à jour $j"; '
                 'if touch_one "$j" "$msg"; then git add -A; git commit -q -m "$msg"; fi; done'
                 % extra_direct)
    script = BUILD_TEMPLATE.format(
        commits=shape["commits"], merges=merges, nbranches=len(branches),
        touch=" ".join(shlex.quote(t) for t in touch),
        branches=" ".join(shlex.quote(b) for b in branches) or "''",
        extra=extra,
    )
    path = out / "build.sh"
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------- audit


def audit(tree):
    findings = []
    for path in sorted(p for p in tree.rglob("*") if p.is_file()):
        rel = path.relative_to(tree).as_posix()
        if path.name in AUDIT_SKIP_NAMES or path.suffix in AUDIT_SKIP_SUFFIXES:
            continue
        for kind, pattern in AUDIT_PATTERNS:
            if pattern.search(rel):
                findings.append({"file": rel, "line": 0, "kind": kind, "text": "(file name)"})
        try:
            text = path.read_text("utf-8")
        except UnicodeDecodeError:
            continue
        for no, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in AUDIT_PATTERNS:
                if pattern.search(line):
                    findings.append({"file": rel, "line": no, "kind": kind, "text": line.strip()[:120]})
    return findings


# ---------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, type=Path, help="real project (git repository)")
    ap.add_argument("--out", required=True, type=Path, help="output directory (must not exist)")
    ap.add_argument("--handoff", default="HANDOFF.md", help="handoff document used for drift rule D4")
    args = ap.parse_args(argv)

    source = args.source.expanduser().resolve()
    out = args.out.expanduser().resolve()
    if out == source or source in out.parents:
        ap.error("--out must be outside the source repository")
    if out.exists():
        ap.error("--out already exists: %s" % out)
    git(source, "rev-parse", "--git-dir")

    tree = out / "tree"
    tree.mkdir(parents=True)
    manifest = {"source_files": 0, "files": {}}
    for rel in git(source, "ls-files", "-z").split("\0"):
        if not rel:
            continue
        src = source / rel
        if src.is_symlink() or not src.is_file():
            manifest["files"][rel] = {"action": "skipped", "reason": "not a regular file"}
            continue
        manifest["source_files"] += 1
        dest_rel = anonymize_path(rel)
        dest = tree / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        entry = {"to": dest_rel} if dest_rel != rel else {}
        if is_binary(data):
            dest.write_bytes(b"")
            entry["action"] = "emptied-binary"
        else:
            text = data.decode("utf-8", "replace")
            if Path(rel).suffix in CODE_EXTENSIONS and Path(rel).name not in KEEP_AS_TEXT:
                dest.write_text(emptied_code(text), encoding="utf-8")
                entry["action"] = "emptied-code"
            else:
                new, counts = anonymize_text(text)
                if new.count("\n") != text.count("\n"):
                    raise SystemExit("line count changed in %s: refusing to continue" % rel)
                dest.write_text(new, encoding="utf-8")
                entry["action"] = "text"
                if counts:
                    entry["replacements"] = counts
        manifest["files"][rel] = entry

    shape = history_shape(source)
    touch = cited_files(tree, args.handoff)
    write_build_script(out, shape, touch)
    findings = audit(tree)
    manifest.update({"history": {"commits": shape["commits"], "merges": shape["merges"],
                                 "branches": len(shape["branches"])},
                     "touched_after_handoff": touch, "audit": findings})
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
    print("files: %d  commits: %d (merges %d)  branches: %d"
          % (manifest["source_files"], shape["commits"], shape["merges"], len(shape["branches"])))
    if findings:
        print("AUDIT: %d finding(s) to check by hand, see MANIFEST.json:" % len(findings))
        for f in findings[:20]:
            print("  %s:%s [%s] %s" % (f["file"], f["line"], f["kind"], f["text"]))
        return 1
    print("audit clean; review tree/ and MANIFEST.json, then copy to tests/fixtures/fx-epure/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
