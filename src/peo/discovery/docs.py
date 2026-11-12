"""Documentation files, CLAUDE.md class and tools announced by the docs (spec 12, section 5)."""

from __future__ import annotations

import fnmatch
import re
import tomllib
from collections.abc import Callable
from importlib import resources

MAX_DOCS = 200
ADR_DIRS = ("docs/adr", "docs/decisions", "adr")
LIST_ITEM = re.compile(r"^(?:[-*] |\d+\. )")
_TABLE = resources.files("peo.discovery").joinpath("intents.toml").read_text()
INTENTS = tomllib.loads(_TABLE)["tool"]
INTENT_PATTERNS = [(tool["id"], name, re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])", re.I))
                   for tool in INTENTS for name in tool["names"]]

Reader = Callable[[str], str | None]


def _root(files: list[str], pattern: str, *, nocase: bool = False) -> list[str]:
    match = (lambda f: fnmatch.fnmatch(f.upper(), pattern.upper())) if nocase else \
        (lambda f: fnmatch.fnmatchcase(f, pattern))
    return sorted(f for f in files if "/" not in f and match(f))


def readmes(files: list[str]) -> list[str]:
    return _root(files, "README*", nocase=True)


def docs_dir(files: list[str]) -> list[str]:
    """docs/**/*.md, at most 200 files in sorted order (spec 12, section 1)."""
    return sorted(f for f in files if f.startswith("docs/") and f.endswith(".md"))[:MAX_DOCS]


def doc_files(files: list[str]) -> list[str]:
    """Files read for drift: README*, CLAUDE.md, AGENTS.md, HANDOFF*.md, docs/**/*.md."""
    root = readmes(files) + [f for f in ("CLAUDE.md", "AGENTS.md") if f in files]
    return sorted(set(root + _root(files, "HANDOFF*.md") + docs_dir(files)))


def claude_md(text: str | None) -> dict:
    if text is None:
        return {"class": "absent"}
    lines = [line for line in text.splitlines() if line.strip()]
    rules = sum(1 for line in text.splitlines() if LIST_ITEM.match(line))
    has_import = any(line.startswith("@") and len(line.strip()) > 1 for line in lines)
    if rules >= 5 or len(lines) > 20:
        kind = "rich"
    else:
        kind = "pointer" if has_import else "thin"
    return {"class": kind, "lines": len(lines), "rules_count": rules}


def docs_section(files: list[str], read: Reader) -> dict:
    """spec 12, section 5."""
    handoffs = _root(files, "HANDOFF*.md")
    return {
        "readme": bool(readmes(files)),
        "claude_md": claude_md((read("CLAUDE.md") or "") if "CLAUDE.md" in files else None),
        "agents_md": "AGENTS.md" in files,
        "handoff": handoffs[0] if handoffs else None,
        "adr": next((d for d in ADR_DIRS if any(f.startswith(d + "/") for f in files)), None),
    }


def intents(files: list[str], read: Reader) -> list[dict]:
    """Tools of intents.toml cited in README* and docs/**/*.md; first citation; sorted by tool."""
    found: dict[str, dict] = {}
    for rel in readmes(files) + docs_dir(files):
        text = read(rel)
        for number, line in enumerate((text or "").splitlines(), 1):
            for tool, name, regex in INTENT_PATTERNS:
                if tool not in found and regex.search(line):
                    found[tool] = {"tool": tool, "confidence": "likely",
                                   "evidence": f"{rel}:{number} mentions {name}"}
    return [found[tool] for tool in sorted(found)]
