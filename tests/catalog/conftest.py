"""Hand-written catalogs for the loader tests (spec 16, section 2: no file of a real project)."""

import re
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "design" / "spec" / "schemas" / "examples"

CAPABILITIES = """[[capabilities]]
id = "nav.symbols"
exclusive = false

[[capabilities]]
id = "spec.authoring"
exclusive = true
"""

REQUIREMENTS = """[[rules]]
id = "symbols-for-large-code"
when = "profile.metrics.loc_total > 50000 or answers['q.refactoring'] == true"
require = { capability = "nav.symbols", strength = "soft" }
"""


def demo_tool(**changes) -> str:
    """The `serena` example of the schema, as a catalog entry named demo; `changes` swap lines."""
    text = (EXAMPLES / "tool.serena.toml").read_text()
    text = re.sub(r'^id\s*=\s*"serena"', 'id = "demo"', text, flags=re.M)
    text = re.sub(r'^kind\s*=\s*"mcp"', 'kind = "cli"', text, flags=re.M)
    for old, new in changes.items():
        assert old in text, old
        text = text.replace(old, new)
    return text


@pytest.fixture
def make_catalog(tmp_path):
    def build(tools=None, capabilities=CAPABILITIES, requirements=REQUIREMENTS, extra=None) -> Path:
        root = tmp_path / "catalog"
        (root / "tools" / "cli").mkdir(parents=True)
        (root / "capabilities.toml").write_text(capabilities)
        (root / "requirements.toml").write_text(requirements)
        for name, text in (tools if tools is not None else {"demo": demo_tool()}).items():
            (root / "tools" / "cli" / f"{name}.toml").write_text(text)
        for rel, text in (extra or {}).items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return root
    return build
