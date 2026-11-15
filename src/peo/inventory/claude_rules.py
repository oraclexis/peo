"""Rule comparator: does a deny Read rule cover a project path? (spec 14 §3.5).

`covered` comes only from a closed positive list: the admitted grammar (forms and relations),
the reference cases of the platform conformance table and its tested version range. Anything
else gives `undecidable` with a reason, or `not_covered` when no rule matches. Pure function:
no file, no command, no fnmatch, no import outside typing; the caller passes the machine facts.
"""

from typing import Any

# Closed order: when several reasons apply, the first is kept and the others go to evidence.
REASONS = ("symlink-outside", "symlink", "untested-platform", "untested-version",
           "contradictory-observations", "untested-scope", "untested-form", "case-only",
           "bare-tool", "source-unreadable")
_LITERAL = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._@+-")
_PREFIXES = (("//", "absolute"), ("/", "root"), ("~/", "home"), ("./", "dot"), ("**/", "any-depth"))
_ANCHORED = ("dot", "relative", "root", "absolute", "home")


def _literal(segment: str) -> bool:
    """A literal segment: [A-Za-z0-9._@+-] only (so no leading #), neither . nor .."""
    return bool(segment) and segment not in (".", "..") and all(c in _LITERAL for c in segment)


def _split(pattern: str) -> tuple[str, list[str], bool]:
    """(form, segments, folder suffix) by syntax alone; segments may be outside the grammar."""
    folder = False
    if pattern.endswith("/**"):
        pattern, folder = pattern[:-3], True
    elif pattern.endswith("/") and pattern not in ("/", "//", "~/", "./"):
        pattern, folder = pattern[:-1], True
    for prefix, form in _PREFIXES:
        if pattern.startswith(prefix):
            return form, pattern[len(prefix):].split("/"), folder
    return ("relative" if "/" in pattern else "name"), pattern.split("/"), folder


def _parts(path: str) -> list[str]:
    return [p for p in str(path).split("/") if p]


def _anchor(form: str, path: list[str], project_root: str, home: str) -> list[str] | None:
    """Segments the pattern is compared with, from its first segment."""
    if form in ("dot", "relative", "root"):
        return path
    absolute = _parts(project_root) + path
    if form == "absolute":
        return absolute
    base = _parts(home)
    return absolute[len(base):] if absolute[:len(base)] == base else None


def _relation(form: str, pattern: list[str], folder: bool, path: list[str], is_dir: bool,
              project_root: str, home: str, fold: bool) -> str | None:
    """exact, under or folder when the pattern matches the path, else None."""
    def same(a: list[str], b: list[str]) -> bool:
        return len(a) == len(b) and all(
            (x.casefold() == y.casefold()) if fold else x == y for x, y in zip(a, b, strict=True))

    n = len(pattern)
    whole = below = False
    if form in _ANCHORED:
        anchor = _anchor(form, path, project_root, home)
        if anchor is None or len(anchor) < n or not same(anchor[:n], pattern):
            return None
        whole, below = len(anchor) == n, len(anchor) > n
    else:   # name (one segment) and any-depth: L aligned on the end, or on a parent folder
        whole = len(path) >= n and same(path[-n:], pattern)
        below = any(same(path[i:i + n], pattern) for i in range(len(path) - n))
    if whole:
        if folder:
            return "folder" if is_dir else None
        return "under" if is_dir else "exact"
    if below:
        return "folder" if folder else "under"
    return None


def _may_match(form: str, segments: list[str], path: list[str], project_root: str,
               home: str) -> bool:
    """An out-of-grammar pattern: same first literal segment, or not analysable at all."""
    first = segments[0]
    if not _literal(first):
        return True
    if form in _ANCHORED:
        anchor = _anchor(form, path, project_root, home)
        return bool(anchor) and anchor[0].casefold() == first.casefold()
    return first.casefold() in {p.casefold() for p in path}


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(n) for n in text.split("."))


def _lookup(form: str, relation: str, scope: str | None, claude_version: str | None,
            table: dict | None) -> tuple[list[str], bool]:
    """Pass 5: (reasons, newer) for a matching rule."""
    if table is None:
        return ["untested-platform"], False
    reasons = []
    refs = [c for c in table["cases"] if c.get("role") == "reference"]
    pair = [c for c in refs if (c["form"], c["relation"]) == (form, relation)]
    triplet = [c for c in pair if c["scope"] == scope]
    if not triplet:
        reasons.append("untested-scope" if pair else "untested-form")
    elif any(c["observed"] != "denied" for c in triplet):
        reasons.append("contradictory-observations")
    tested = sorted(_version(v) for v in table["versions_tested"])
    newer = False
    if claude_version is None or _version(claude_version) < tested[0]:
        reasons.append("untested-version")
    else:
        newer = _version(claude_version) > tested[-1]
    return reasons, newer


def _reasons(rule: str, path: list[str], is_dir: bool, scope: str | None,
             claude_version: str | None, table: dict | None, project_root: str,
             home: str) -> tuple[list[str], bool] | None:
    """(reasons, newer) when the rule may cover the path, None when it is ignored."""
    if rule == "Read":
        return ["bare-tool"], False
    if not (rule.startswith("Read(") and rule.endswith(")")):
        return None   # another tool
    form, segments, folder = _split(rule[5:-1])
    if not all(_literal(s) for s in segments):
        return (["untested-form"], False) if _may_match(form, segments, path, project_root,
                                                         home) else None
    reasons = []
    relation = _relation(form, segments, folder, path, is_dir, project_root, home, fold=False)
    if relation is None:
        relation = _relation(form, segments, folder, path, is_dir, project_root, home, fold=True)
        if relation is None:
            return None
        reasons.append("case-only")
    found, newer = _lookup(form, relation, scope, claude_version, table)
    return reasons + found, newer


def _verdict(verdict: str, reason: str | None = None, rule: str | None = None,
             source: str | None = None, newer: bool = False,
             evidence: list[str] | None = None) -> dict[str, Any]:
    return {"verdict": verdict, "reason": reason, "rule": rule, "source": source, "newer": newer,
            "evidence": evidence or []}


def covers(path: str, is_dir: bool, link_target: str | None | bool, rules: list[dict],
           sources: list[dict], managed_rules_only: bool | str | None,
           claude_version: str | None, platform: str, table: dict | None,
           project_root: str, home: str) -> dict[str, Any]:
    """Verdict of spec 14 §3.5 for one path of `sensitive`.

    link_target: False for an ordinary path, the target relative to the root for a link inside
    the project, None for a link that leaves it. rules: the deny entries of permission_rules.
    managed_rules_only: effective value (True, False, None or "unknown"). platform only names
    the table the caller chose. The verdict also carries `evidence`: the reasons not retained.
    """
    if link_target is None:
        return _verdict("undecidable", "symlink-outside")
    by_id = {s["id"]: s for s in sources}
    target = _parts(path if link_target is False else link_target)
    root, home_dir = str(project_root), str(home)
    covering, undecided = [], []
    for index, entry in enumerate(rules):
        if entry.get("list", "deny") != "deny":
            continue
        src = by_id.get(entry["source"], {})
        managed = src.get("scope") == "managed"
        if managed_rules_only is True and not managed:
            continue
        args = (src.get("scope"), claude_version, table, root, home_dir)
        found = _reasons(entry["rule"], target, is_dir, *args)
        if found is None and link_target is not False:
            if _reasons(entry["rule"], _parts(path), is_dir, *args) is not None:
                found = (["symlink"], False)
        if found is None:
            continue
        reasons, newer = found
        if managed_rules_only == "unknown" and not managed:
            reasons = [*reasons, "source-unreadable"]
        reasons = sorted(set(reasons), key=REASONS.index)
        (undecided if reasons else covering).append((index, entry, reasons, newer))
    if covering:
        def shared(item: tuple) -> bool:
            src = by_id.get(item[1]["source"], {})
            return (src.get("id") == "settings:project" and src.get("tracked") is True
                    and src.get("modified") is False)
        _, entry, _, newer = next((c for c in covering if shared(c)), covering[0])
        return _verdict("covered", None, entry["rule"], entry["source"], newer)
    if undecided:
        undecided.sort(key=lambda u: (REASONS.index(u[2][0]), u[0]))
        _, entry, reasons, _ = undecided[0]
        evidence = [f"{entry['source']} deny {entry['rule']}: {r}" for r in reasons[1:]]
        evidence += [f"{e['source']} deny {e['rule']}: {r}" for _, e, rs, _ in undecided[1:]
                     for r in rs]
        return _verdict("undecidable", reasons[0], entry["rule"], entry["source"],
                        evidence=evidence)
    return _verdict("not_covered")
