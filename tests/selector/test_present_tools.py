"""Present tools: the profile plus the tracked declarations recognised by [detect] (research D9)."""

from peo import selector

from .conftest import make_catalog_doc, profile, tool

CATALOG = make_catalog_doc([
    tool("cli:playwright", ["browser.e2e"], detect={"npm": ["@playwright/test"], "bin": ["playwright"]}),
    tool("claude-plugin:serena-like", ["nav.symbols"], detect={"plugin": ["serena-like"]}),
    tool("mcp:serena", ["nav.symbols"]),
    tool("claude-plugin:superpowers", ["spec.authoring"], status="backbone-alt", detect={"plugin": ["superpowers"]}),
])


def declared(plugins=(), servers=()):
    return {"plugins": [{"id": p} for p in plugins], "mcp_servers": [{"ref": s} for s in servers]}


def test_the_profile_lists_present_tools_with_their_evidence():
    prof = profile(present_tools=[{"ref": "cli:playwright", "evidence": "package.json devDependencies"}])
    assert selector.present_tools(CATALOG, prof, declared()) == {"cli:playwright": "package.json devDependencies"}


def test_a_declared_plugin_is_recognised_by_its_name_or_its_full_id():
    got = selector.present_tools(CATALOG, profile(), declared(plugins=["serena-like@market"]))
    assert list(got) == ["claude-plugin:serena-like"] and "serena-like@market" in got["claude-plugin:serena-like"]
    assert list(selector.present_tools(CATALOG, profile(), declared(plugins=["serena-like"]))) == [
        "claude-plugin:serena-like"]
    assert selector.present_tools(CATALOG, profile(), declared(plugins=["serena-like-2@m"])) == {}   # exact only


def test_a_declared_mcp_server_counts_when_identify_gave_a_catalog_reference():
    assert list(selector.present_tools(CATALOG, profile(), declared(servers=["mcp:serena"]))) == ["mcp:serena"]
    assert selector.present_tools(CATALOG, profile(), declared(servers=[None, "mcp:ghost"])) == {}


def test_a_declared_alternative_backbone_is_not_a_present_tool_but_a_conflict():
    found = declared(plugins=["superpowers@claude-plugins-official"])
    assert selector.present_tools(CATALOG, profile(), found) == {}
    assert selector.declared_backbones(CATALOG, found) == ["claude-plugin:superpowers"]


def test_a_reference_unknown_to_the_catalog_is_ignored():
    prof = profile(present_tools=[{"ref": "cli:ghost", "evidence": "x"}])
    assert selector.present_tools(CATALOG, prof, declared()) == {}
