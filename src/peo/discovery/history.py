"""Branch and commit conventions, kind and git state (spec 12, sections 4.1 to 4.3).

Git is read only through the injectable runner; a failing call gives the unknown value.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from peo import runner

MAIN_BRANCHES = {"main", "master", "develop", "HEAD"}
STYLES = (("timestamp", re.compile(r"^[0-9]{8}-[0-9]{6}-")),
          ("numeric", re.compile(r"^[0-9]{3,}-")),
          ("alnum-id", re.compile(r"^[A-Za-z]+[0-9]+-")))
ALPHABETS = ("[a-z0-9-]+", "[A-Za-z0-9-]+", "[A-Za-z0-9._-]+", ".+")
CONVENTIONAL = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?: ")
MERGE = re.compile(r"^[Mm]erge\b")
FR_WORDS = {"le", "la", "les", "des", "du", "pour", "avec", "ajout"}
EN_WORDS = {"the", "for", "with", "add", "update"}
THRESHOLD = 0.8
UNKNOWN_COMMITS = {"style": "unknown", "language": "unknown", "confidence": "unknown"}


def branch_names(refs: list[str], remotes: list[str]) -> list[str]:
    names = set()
    for ref in (r.strip() for r in refs):
        if not ref or ref in remotes:
            continue
        for remote in remotes:
            if ref.startswith(remote + "/"):
                ref = ref[len(remote) + 1:]
                break
        if ref not in MAIN_BRANCHES:
            names.add(ref)
    return sorted(names)


def _style(segment: str) -> str:
    return next((name for name, regex in STYLES if regex.match(segment)), "free")


def branches(names: list[str]) -> dict | None:
    total = len(names)
    if total < 5:
        return None
    lasts = [n.rsplit("/", 1)[-1] for n in names]
    styles = Counter(_style(s) for s in lasts)
    top, count = max(sorted(styles.items()), key=lambda item: item[1])
    id_style = top if count / total >= THRESHOLD else "mixed"
    with_prefix = [n.split("/", 1)[0] for n in names if "/" in n]
    prefixes = sorted(set(with_prefix))
    alphabet = next(a for a in ALPHABETS
                    if sum(bool(re.fullmatch(a, s)) for s in lasts) / total >= THRESHOLD)
    if len(with_prefix) / total >= THRESHOLD and len(prefixes) <= 5:
        pattern = f"^({'|'.join(prefixes)})/{alphabet}$"
    else:
        prefixes, pattern = [], f"^{alphabet}$"
    matching = sum(bool(re.search(pattern, n)) for n in names)
    result: dict = {"prefixes": prefixes, "id_style": id_style}
    if id_style == "mixed":
        result["id_shares"] = {s: round(c / total, 2) for s, c in sorted(styles.items())}
    return result | {"pattern": pattern, "share": round(matching / total, 2), "confidence": "fact",
                     "evidence": f"{matching} of {total} branches outside main"}


def _language(subjects: list[str]) -> str:
    words: list[str] = []
    for subject in subjects:
        text = subject.split(": ", 1)[1] if CONVENTIONAL.match(subject) else subject
        words += re.findall(r"\w+", text.lower())
    fr = sum(w in FR_WORDS for w in words)
    en = sum(w in EN_WORDS for w in words)
    if fr >= 2 and fr >= 2 * en:
        return "fr"
    if en >= 2 and en >= 2 * fr:
        return "en"
    return "unknown"


def commits(lines: list[str]) -> dict:
    """lines: '<parents>\\x1f<subject>' as printed by git log --format=%P%x1f%s."""
    subjects, merges = [], 0
    for line in lines:
        parents, _, subject = line.partition("\x1f")
        if len(parents.split()) > 1 or MERGE.match(subject):
            merges += 1
        else:
            subjects.append(subject)
    if not subjects:
        return dict(UNKNOWN_COMMITS)
    conventional = sum(bool(CONVENTIONAL.match(s)) for s in subjects)
    share = conventional / len(subjects)
    return {"style": "conventional" if share >= THRESHOLD else "free",
            "language": _language(subjects), "share": round(share, 2),
            "excluded_merges": merges, "confidence": "fact",
            "evidence": f"{conventional} of {len(subjects)} non-merge subjects"}


def read_history(root: Path, run: runner.Runner, is_git: bool) -> dict:
    """kind, git and conventions; outside git, no git call at all."""
    if not is_git:
        kind = {"value": "new", "confidence": "likely", "evidence": "not a git repository"}
        return {"kind": kind, "counts": {"commits": 0, "contributors": 0},
                "git": {"remote": False},
                "conventions": {"branches": None, "commits": dict(UNKNOWN_COMMITS)}}

    def out(*args: str) -> str | None:
        result = run(list(args), root)
        return result.stdout.decode("utf-8", "replace") if result.returncode == 0 else None

    count = (out("git", "rev-list", "--count", "HEAD") or "").strip()
    n = int(count) if count.isdigit() else 0
    kind = {"value": "new" if n <= 1 else "existing", "confidence": "fact",
            "evidence": f"{n} commits"}
    refs = (out("git", "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes")
            or "").splitlines()
    log = (out("git", "log", "-200", "--format=%P%x1f%s") or "").splitlines()
    remotes = (out("git", "remote") or "").split()
    origin_head = out("git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if origin_head:
        default = origin_head.strip().split("/", 1)[-1]
    else:
        default = (out("git", "symbolic-ref", "--short", "HEAD") or "").strip() or None
    authors = (out("git", "log", "--format=%ae") or "").split()
    git: dict = {"remote": bool(remotes)}
    if default:
        git["default_branch"] = default
    return {"kind": kind, "git": git, "counts": {"commits": n, "contributors": len(set(authors))},
            "conventions": {"branches": branches(branch_names(refs, remotes)),
                            "commits": commits(log)}}
