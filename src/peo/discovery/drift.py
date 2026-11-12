"""Documentation drift, rules D1 to D4 (spec 12, section 6). Hypotheses, never corrected."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable
from importlib import resources
from pathlib import Path, PurePosixPath

from peo import runner
from peo.discovery.commands import makefile_targets

MARKERS = ("- [ ]", "TODO", "WIP", "à venir", "pas encore", "coming soon", "not yet")
MARKER_PATTERNS = [(m, re.compile(re.escape(m) if m == "- [ ]" else rf"(?<!\w){re.escape(m)}(?!\w)",
                                  re.I)) for m in MARKERS]
_STACKS = resources.files("peo.discovery").joinpath("stacks.toml").read_text()
_LANGUAGES = tomllib.loads(_STACKS)["language"]
EXTENSIONS = [e for lang in _LANGUAGES for e in lang["extensions"]]
EXTENSIONS += ["md", "json", "toml", "yml", "yaml"]
NAME = re.compile(rf"(?<![\w./-])([\w.-]+\.(?:{'|'.join(EXTENSIONS)}))(?![\w-])")
PATH = re.compile(r"(?<![\w/:.-])([\w.-]+(?:/[\w.-]+)+/?)")
URL = re.compile(r"\S+://\S+")
HEADING = re.compile(r"^(#{1,6})\s+(.*)")
INLINE_CODE = re.compile(r"`([^`]+)`")
D2_COMMANDS = (
    (re.compile(r"(?<![\w-])((?:npm|pnpm) run ([\w:.-]+))"), "package.json", ()),
    (re.compile(r"(?<![\w-])(yarn (?:run )?([\w:.-]+))"), "package.json",
     ("install", "add", "remove", "upgrade", "init", "dlx", "why", "info")),
    (re.compile(r"(?<![\w-])(make ([\w.-]+))"), "Makefile", ()),
    (re.compile(r"(?<![\w-])(composer ([\w:.-]+))"), "composer.json",
     ("install", "require", "update", "remove", "show", "outdated", "dump-autoload",
      "create-project")),
)
D4_THRESHOLD = 20

Reader = Callable[[str], str | None]


def _marker(text: str) -> str | None:
    return next((m for m, regex in MARKER_PATTERNS if regex.search(text)), None)


class Tree:
    """What exists in the repository: tracked files, directories by prefix, component paths."""

    def __init__(self, files: list[str], components: list[str]):
        self.files = set(files)
        self.dirs = {PurePosixPath(f).parents[i].as_posix() for f in files
                     for i in range(len(PurePosixPath(f).parents) - 1)}
        self.by_name: dict[str, str] = {}
        for f in sorted(files):
            self.by_name.setdefault(PurePosixPath(f).name, f)
        self.components = [re.compile(rf"(?<![\w/.-])({re.escape(c)})(?![\w/.-])")
                           for c in components if c != "."]

    def path_exists(self, token: str) -> bool:
        path = token.rstrip("/")
        return path in self.files or path in self.dirs

    def citations(self, line: str) -> list[tuple[int, str, str]]:
        """(position, token, resolved path) of every existing thing the line cites."""
        line = URL.sub(" ", line)
        found = [(m.start(), m.group(1), m.group(1)) for m in PATH.finditer(line)
                 if self.path_exists(m.group(1))]
        found += [(m.start(), m.group(1), self.by_name[m.group(1)]) for m in NAME.finditer(line)
                  if m.group(1) in self.by_name]
        found += [(m.start(), m.group(1), m.group(1))
                  for regex in self.components for m in regex.finditer(line)]
        return sorted(found)

    def missing_paths(self, line: str) -> list[str]:
        tokens = [m.group(1) for m in PATH.finditer(URL.sub(" ", line))]
        return list(dict.fromkeys(t for t in tokens if not self.path_exists(t)))


def _finding(rule: str, file: str, line: int | None, message: str) -> dict:
    entry = {"rule": rule, "file": file}
    if line is not None:
        entry["line"] = line
    return entry | {"confidence": "likely", "message": message}


def _scan(rel: str, text: str, tree: Tree, defined: dict[str, set[str]]) -> list[dict]:
    findings = []
    sections: list[tuple[int, str | None]] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        heading = None if fenced else HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            sections = [s for s in sections if s[0] < level] + [(level, _marker(heading.group(2)))]
        marker = _marker(line) or next((m for _, m in reversed(sections) if m), None)
        if marker:
            cited = tree.citations(line)
            if cited:
                _, token, path = cited[0]
                message = f"Line marked '{marker}' cites {token}, which exists ({path})"
                findings.append(_finding("D1", rel, number, message))
        code = [line] if fenced else INLINE_CODE.findall(line)
        for snippet in code:
            for regex, manifest, builtins in D2_COMMANDS:
                for match in regex.finditer(snippet):
                    command, name = match.group(1), match.group(2)
                    if name not in builtins and name not in defined[manifest]:
                        message = f"Command '{command}' is documented but not defined in {manifest}"
                        findings.append(_finding("D2", rel, number, message))
        for token in tree.missing_paths(line):
            findings.append(_finding("D3", rel, number, f"Path {token} does not exist"))
    return findings


def handoff_drift(root: Path, handoff: str, text: str, files: list[str],
                  run: runner.Runner) -> dict | None:
    """D4: the handoff document was last changed more than 20 commits before a file it cites."""
    def out(*args: str) -> str | None:
        result = run(list(args), root)
        return result.stdout.decode("utf-8", "replace").strip() if result.returncode == 0 else None

    last = out("git", "log", "-1", "--format=%H", "--", handoff)
    if not last:
        return None
    tree = Tree(files, [])
    cited = [path for line in text.splitlines() for _, _, path in tree.citations(line)]
    for path in dict.fromkeys(p for p in cited if p in tree.files and p != handoff):
        changed = out("git", "log", "-1", "--format=%H", "--", path)
        count = out("git", "rev-list", "--count", f"{last}..{changed}") if changed else None
        if count and count.isdigit() and int(count) > D4_THRESHOLD:
            behind = out("git", "rev-list", "--count", f"{last}..HEAD")
            if behind and behind.isdigit():
                return _finding("D4", handoff, None, f"Last changed {behind} commits before HEAD "
                                                     "while files it cites changed since")
            return None
    return None


def find_drift(root: Path, files: list[str], doc_files: list[str], read: Reader,
               components: list[str], root_manifests, handoff: str | None, run: runner.Runner,
               is_git: bool) -> list[dict]:
    """D1 to D4 sorted by rule, file, line."""
    tree = Tree(files, components)
    scripts: dict[str, set[str]] = {"package.json": set(), "composer.json": set()}
    for manifest in root_manifests:
        if manifest.path in scripts:
            scripts[manifest.path] |= set(manifest.scripts)
    defined = scripts | {"Makefile": set(makefile_targets(read("Makefile") or ""))}
    findings = []
    for rel in doc_files:
        text = read(rel)
        if text is not None:
            findings += _scan(rel, text, tree, defined)
    if is_git and handoff:
        d4 = handoff_drift(root, handoff, read(handoff) or "", files, run)
        if d4:
            findings.append(d4)
    return sorted(findings, key=lambda f: (f["rule"], f["file"], f.get("line", 0)))
