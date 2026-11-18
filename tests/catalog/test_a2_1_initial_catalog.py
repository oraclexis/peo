"""A2.1: the catalog of the repository loads, with exactly the 21 entries of spec 13 section 5."""

from datetime import date
from pathlib import Path

from peo.catalog import validate

CATALOG = Path(__file__).resolve().parents[2] / "catalog"
EXPECTED = {
    "framework:spec-kit", "cli:specify-cli", "claude-plugin:egm", "claude-plugin:mattpocock-skills",
    "peo:gates", "peo:native-controls", "ci-check:gitleaks", "claude-plugin:typescript-lsp",
    "claude-plugin:php-lsp", "cli:intelephense", "claude-plugin:pyright-lsp", "mcp:serena",
    "cli:graphify", "ci-check:semgrep", "claude-plugin:security-guidance",
    "vendored-skill:ui-ux-pro-max", "cli:playwright", "claude-plugin:context7",
    "claude-plugin:superpowers", "claude-plugin:compound-engineering",
    "claude-plugin:everything-claude-code",
}


def test_a2_1_the_initial_catalog_is_valid():
    report = validate(CATALOG, today=date(2026, 11, 18))
    assert report.errors == []
    assert report.warnings == []


def test_a2_1_the_catalog_holds_the_21_entries_of_section_5():
    found = {f"{p.parent.name}:{p.stem}" for p in (CATALOG / "tools").glob("*/*.toml")}
    assert found == EXPECTED and len(EXPECTED) == 21
