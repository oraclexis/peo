"""A5.5: a NestJS profile does not get the tools of the split-stack one."""

from peo import selector

from .conftest import golden


def test_a5_5_nestjs_gets_no_php_design_or_symbol_tool(real_catalog):
    out = selector.select(real_catalog, golden("fx-nestjs"), {}, {})
    chosen = {e["ref"] for e in out["selected"]}
    rejected = {e["ref"]: e["code"] for e in out["rejected"]}
    for ref in ("claude-plugin:php-lsp", "vendored-skill:ui-ux-pro-max", "mcp:serena"):
        assert ref not in chosen, ref
        assert ref in rejected, ref
    assert rejected["claude-plugin:php-lsp"] in ("NOT_REQUIRED", "CONDITION_FALSE")
    assert rejected["mcp:serena"] in ("CONDITION_FALSE", "NOT_REQUIRED")
    assert chosen != {e["ref"] for e in selector.select(real_catalog, golden("fx-split-stack"), {}, {})["selected"]}
    assert out["ok"] is True and "claude-plugin:typescript-lsp" in chosen
