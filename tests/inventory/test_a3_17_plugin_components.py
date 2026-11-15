"""A3.17: components of an enabled plugin read from its install folder (spec 14 §3.1, 2026-11-16)."""

import json

import pytest

import peo.inventory as inv
from tests.inventory.test_a3_inventory import DECOY, check, of, one_plugin, source

STOP = {"Stop": [{"hooks": [{"type": "command", "command": "a"}]}]}


def plugin_dir(tmp_path, files):
    root = tmp_path / f"{DECOY}install" / "p"
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if isinstance(content, str) else json.dumps(content))
    return root


def run_with(project, fake_run, user_config, managed, install, **entry):
    root = project()
    plugin = {"id": "a@b", "scope": "user", "enabled": True, "installPath": str(install), **entry}
    return check(inv.inventory(root, run=one_plugin(fake_run, root, plugin),
                               user_config=user_config, managed=managed))


def servers(out):
    return [(s["plugin_index"], s["index"], s["name"]) for s in of(out, "mcp_servers", "claude")]


def test_a3_17_mcp_from_default_file_wrapped(project, fake_run, user_config, managed, tmp_path):
    install = plugin_dir(tmp_path, {".mcp.json": {"mcpServers": {"x": {"command": "x"}}}})
    out = run_with(project, fake_run, user_config, managed, install)
    assert servers(out) == [(0, 0, "x")]
    assert source(out, "claude")["invalid_families"] == []


def test_a3_17_mcp_from_default_file_flat(project, fake_run, user_config, managed, tmp_path):
    install = plugin_dir(tmp_path, {".mcp.json": {"x": {"command": "x"}, "y": {"url": "https://h.test"}}})
    out = run_with(project, fake_run, user_config, managed, install)
    assert servers(out) == [(0, 0, "x"), (0, 1, "y")]


def test_a3_17_mcp_merged_with_manifest_by_name(project, fake_run, user_config, managed, tmp_path):
    install = plugin_dir(tmp_path, {
        ".mcp.json": {"mcpServers": {"a": {"command": "old"}, "b": {"command": "b"}}},
        "mcp/more.json": {"mcpServers": {"c": {"command": "c"}}},
        ".claude-plugin/plugin.json": {"name": "p", "mcpServers": [
            {"a": {"url": "https://new.test"}}, "./mcp/more.json"]}})
    out = run_with(project, fake_run, user_config, managed, install)
    assert servers(out) == [(0, 0, "a"), (0, 1, "b"), (0, 2, "c")]
    assert of(out, "mcp_servers", "claude")[0]["transport"] != "stdio"


def test_a3_17_mcp_from_listing_wins(project, fake_run, user_config, managed, tmp_path):
    install = plugin_dir(tmp_path, {".mcp.json": {"mcpServers": {"file": {"command": "f"}}}})
    out = run_with(project, fake_run, user_config, managed, install,
                   mcpServers={"listed": {"command": "l"}})
    assert servers(out) == [(0, 0, "listed")]


def test_a3_17_hooks_from_manifest_appended(project, fake_run, user_config, managed, tmp_path):
    install = plugin_dir(tmp_path, {
        "hooks/hooks.json": {"hooks": STOP},
        "config/extra.json": {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "c"}]}]}},
        ".claude-plugin/plugin.json": {"name": "p", "hooks": [
            "./config/extra.json", {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command",
                                                                                 "command": "b"}]}]}]}})
    out = run_with(project, fake_run, user_config, managed, install)
    hooks = [(h["event"], h["group_index"], h["matcher"]) for h in of(out, "hooks", "plugin:#0")]
    assert hooks == [("PreToolUse", 0, "Bash"), ("Stop", 0, None), ("Stop", 1, None)]
    assert source(out, "plugin:#0")["invalid_families"] == []


def test_a3_17_hooks_only_in_manifest_make_source_read(project, fake_run, user_config, managed,
                                                       tmp_path):
    install = plugin_dir(tmp_path, {".claude-plugin/plugin.json": {"name": "p", "hooks": STOP}})
    out = run_with(project, fake_run, user_config, managed, install)
    assert source(out, "plugin:#0")["status"] == "read"
    assert len(of(out, "hooks", "plugin:#0")) == 1


def test_a3_17_no_component_files(project, fake_run, user_config, managed, tmp_path):
    out = run_with(project, fake_run, user_config, managed, plugin_dir(tmp_path, {}))
    assert source(out, "plugin:#0")["status"] == "absent"
    assert servers(out) == [] and source(out, "claude")["invalid_families"] == []


def test_a3_17_unreadable_manifest_invalidates_both(project, fake_run, user_config, managed, tmp_path):
    install = plugin_dir(tmp_path, {"hooks/hooks.json": {"hooks": STOP},
                                    ".mcp.json": {"mcpServers": {"x": {"command": "x"}}},
                                    ".claude-plugin/plugin.json": "{not json"})
    out = run_with(project, fake_run, user_config, managed, install)
    assert source(out, "plugin:#0")["invalid_families"] == ["hooks"]
    assert of(out, "hooks", "plugin:#0") == []
    assert source(out, "claude")["invalid_families"] == ["mcp"] and servers(out) == []


@pytest.mark.parametrize("decl", [
    "./bundle.mcpb", "./bundle.dxt", "https://example.test/s.mcpb", "mcp/x.json", "./../x.json",
    f"./{DECOY}missing.json", 3, [3]])
def test_a3_17_unreadable_mcp_declaration(project, fake_run, user_config, managed, tmp_path, decl):
    install = plugin_dir(tmp_path, {".mcp.json": {"mcpServers": {"x": {"command": "x"}}},
                                    "mcp/x.json": {"y": {"command": "y"}},
                                    ".claude-plugin/plugin.json": {"name": "p", "mcpServers": decl}})
    (install.parent / "x.json").write_text(json.dumps({"z": {"command": "z"}}))
    out = run_with(project, fake_run, user_config, managed, install)
    assert source(out, "claude")["invalid_families"] == ["mcp"] and servers(out) == []


@pytest.mark.parametrize("decl", ["hooks/extra.json", f"./{DECOY}missing.json", "./link.json", 3])
def test_a3_17_unreadable_hooks_declaration(project, fake_run, user_config, managed, tmp_path, decl):
    install = plugin_dir(tmp_path, {"hooks/hooks.json": {"hooks": STOP},
                                    "hooks/extra.json": {"hooks": STOP},
                                    ".claude-plugin/plugin.json": {"name": "p", "hooks": decl}})
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"hooks": STOP}))
    (install / "link.json").symlink_to(outside)
    out = run_with(project, fake_run, user_config, managed, install)
    assert source(out, "plugin:#0")["invalid_families"] == ["hooks"]
    assert of(out, "hooks", "plugin:#0") == []
