"""Discovery, documentation for agents and tools announced by the docs (spec 12, section 5)."""

import json
from pathlib import Path

import pytest

from peo.discovery import discover
from peo.runner import Result


def no_git(args, cwd):
    return Result(128, b"", b"")


def write(root: Path, files: dict) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content) if isinstance(content, dict) else content)


def disc(root: Path) -> dict:
    return discover(root, run=no_git, which=lambda name: None)


def docs(root: Path) -> dict:
    return disc(root)["docs"]


def text(n: int, extra: str = "") -> str:
    return "".join(f"line {i}\n" for i in range(n)) + extra


# --- docs (US1) ------------------------------------------------------------------------------

@pytest.mark.parametrize("name, present", [("README.md", True), ("readme.rst", True), ("NOTES.md", False)])
def test_doc_readme(tmp_path, name, present):
    write(tmp_path, {name: "x\n"})
    assert docs(tmp_path)["readme"] is present


def test_doc_claude_md_absent(tmp_path):
    write(tmp_path, {"README.md": "x\n"})
    assert docs(tmp_path)["claude_md"] == {"class": "absent"}


def test_doc_claude_md_pointer_20_lines_with_import(tmp_path):
    write(tmp_path, {"CLAUDE.md": "@AGENTS.md\n" + text(19)})
    assert docs(tmp_path)["claude_md"] == {"class": "pointer", "lines": 20, "rules_count": 0}


def test_doc_claude_md_thin_20_lines(tmp_path):
    write(tmp_path, {"CLAUDE.md": text(20, "\n\n")})
    assert docs(tmp_path)["claude_md"]["class"] == "thin"


def test_doc_claude_md_rich_21_lines(tmp_path):
    write(tmp_path, {"CLAUDE.md": "@AGENTS.md\n" + text(20)})
    assert docs(tmp_path)["claude_md"]["class"] == "rich"


def test_doc_claude_md_rich_5_rules_short(tmp_path):
    write(tmp_path, {"CLAUDE.md": "# Rules\n" + "".join(f"- rule {i}\n" for i in range(5))})
    assert docs(tmp_path)["claude_md"] == {"class": "rich", "lines": 6, "rules_count": 5}


def test_doc_claude_md_rules_count_top_level_only(tmp_path):
    write(tmp_path, {"CLAUDE.md": "- a\n* b\n1. c\n  - d\nTODO (x): y\n"})
    assert docs(tmp_path)["claude_md"]["rules_count"] == 3


def test_doc_agents_md(tmp_path):
    write(tmp_path, {"AGENTS.md": "x\n"})
    assert docs(tmp_path)["agents_md"] is True


def test_doc_handoff_first_sorted(tmp_path):
    write(tmp_path, {"HANDOFF.md": "x\n", "HANDOFF-2.md": "y\n"})
    assert docs(tmp_path)["handoff"] == "HANDOFF-2.md"


def test_doc_adr_order(tmp_path):
    write(tmp_path, {"adr/x.md": "x\n", "docs/decisions/y.md": "y\n"})
    (tmp_path / "docs" / "adr").mkdir(parents=True)   # empty: does not count
    assert docs(tmp_path)["adr"] == "docs/decisions"


def test_doc_adr_none(tmp_path):
    write(tmp_path, {"README.md": "x\n"})
    assert docs(tmp_path)["adr"] is None and docs(tmp_path)["handoff"] is None


def test_doc_gaps(tmp_path):
    write(tmp_path, {"package.json": {"dependencies": {"vue": "^3.5.0"}}})
    gaps = disc(tmp_path)["gaps"]
    assert gaps[:5] == ["no-ci", "no-verify", "no-remote", "no-agents-md", "no-adr"]
    write(tmp_path, {"AGENTS.md": "x\n", "docs/adr/0001.md": "x\n"})
    assert "no-agents-md" not in disc(tmp_path)["gaps"] and "no-adr" not in disc(tmp_path)["gaps"]


# --- intent_from_docs (US2) ------------------------------------------------------------------

def intents(root: Path) -> list:
    return disc(root)["intent_from_docs"]


def test_intent_spec_kit_line(tmp_path):
    write(tmp_path, {"README.md": "# X\n\nLes specs seront écrites avec Spec Kit.\n"})
    assert intents(tmp_path) == [{"tool": "spec-kit", "confidence": "likely",
                                  "evidence": "README.md:3 mentions Spec Kit"}]


@pytest.mark.parametrize("line, found", [("we use speckit", True), ("SPEC KIT", True),
                                         ("myspeckitx", False)])
def test_intent_whole_word_case_insensitive(tmp_path, line, found):
    write(tmp_path, {"README.md": line + "\n"})
    assert bool(intents(tmp_path)) is found


def test_intent_first_mention_only(tmp_path):
    write(tmp_path, {"README.md": "x\nSpec Kit\nx\nspeckit\n"})
    assert intents(tmp_path) == [{"tool": "spec-kit", "confidence": "likely",
                                  "evidence": "README.md:2 mentions Spec Kit"}]


def test_intent_docs_dir_scanned(tmp_path):
    write(tmp_path, {"docs/a.md": "Serena helps\n"})
    assert intents(tmp_path)[0]["evidence"] == "docs/a.md:1 mentions Serena"


def test_intent_claude_md_not_scanned(tmp_path):
    write(tmp_path, {"CLAUDE.md": "Use Serena\n"})
    assert intents(tmp_path) == []


def test_intent_sorted_by_tool(tmp_path):
    write(tmp_path, {"README.md": "Serena\nGitleaks\n"})
    assert [i["tool"] for i in intents(tmp_path)] == ["gitleaks", "serena"]


def test_intent_none(tmp_path):
    write(tmp_path, {"README.md": "Nothing to see\n"})
    assert intents(tmp_path) == []


def test_intent_docs_files_limit_200(tmp_path):
    write(tmp_path, {f"docs/f{i:03}.md": "x\n" for i in range(200)})
    write(tmp_path, {"docs/f200.md": "Serena\n"})          # 201st in sorted order
    assert intents(tmp_path) == []


def test_intent_doc_over_1_mb_ignored(tmp_path):
    write(tmp_path, {"docs/big.md": "Serena\n" + "x" * (1024 * 1024)})
    assert intents(tmp_path) == []
