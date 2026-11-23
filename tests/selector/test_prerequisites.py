"""Prerequisite status from the profile alone (research D10)."""

from peo import selector

from .conftest import golden, make_catalog_doc, profile, tool

PHP = tool("claude-plugin:php-lsp", ["nav.lsp.php"], prerequisites=[
    {"check": "bin:intelephense", "fix": "cli:intelephense", "blocking": True},
    {"check": "path:{component:php}/vendor", "hint": "composer install", "blocking": False}])
NODE = tool("cli:intelephense", [], detect={"bin": ["intelephense"]})
CATALOG = make_catalog_doc([PHP, NODE, tool("peo:host-only", [], prerequisites=[
    {"check": "runtime:host", "blocking": True}])])


def status(ref, prof, present=()):
    return selector.prerequisites(CATALOG, CATALOG.entries[ref], prof, set(present))


def test_the_example_split_stack_prerequisites_are_unmet_with_their_actions():
    got = status("claude-plugin:php-lsp", golden("fx-split-stack"))
    assert [(p.check, p.status, p.action, p.fix) for p in got] == [
        ("bin:intelephense", "unmet", "fix", "cli:intelephense"),
        ("path:backend/vendor", "unmet", "hint", None)]
    assert [p.blocking for p in got] == [True, False]


def test_a_bin_is_met_when_a_present_tool_has_that_binary():
    got = status("claude-plugin:php-lsp", golden("fx-split-stack"), present=["cli:intelephense"])
    assert (got[0].status, got[0].action) == ("met", "none")


def test_a_path_is_met_when_a_component_has_that_path():
    prof = golden("fx-split-stack")
    prof["components"].append({"id": "vendor", "path": "backend/vendor", "languages": []})   # listed
    assert status("claude-plugin:php-lsp", prof)[1].status == "met"


def test_runtime_host_is_met_when_a_component_runs_on_the_host():
    assert status("peo:host-only", golden("fx-split-stack"))[0].status == "met"
    assert status("peo:host-only", profile(components=[]))[0].status == "unmet"


def test_an_unresolvable_component_placeholder_stays_unmet():
    got = status("claude-plugin:php-lsp", profile(components=[{"id": "root", "path": ".", "languages": ["ts"]}]))
    assert got[1].check == "path:{component:php}/vendor" and got[1].status == "unmet"


def test_the_cost_counts_one_per_unmet_fix():
    entry = CATALOG.entries["claude-plugin:php-lsp"]
    unmet = status("claude-plugin:php-lsp", golden("fx-split-stack"))
    met = status("claude-plugin:php-lsp", golden("fx-split-stack"), present=["cli:intelephense"])
    assert selector.cost(entry, unmet) == 2 and selector.cost(entry, met) == 1
