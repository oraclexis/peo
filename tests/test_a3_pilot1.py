"""A3 traits on the local clone of pilot n°1 (spec 16 §2.2); skipped without PEO_PILOT1_PATH.

Outside tests/inventory/: it uses the real Runner on purpose. Assertions are booleans only, so
pytest never prints real data.
"""

import json
import os
from pathlib import Path

import pytest

import peo.inventory as inv
from peo.validate import load_schema, validate

PILOT = os.environ.get("PEO_PILOT1_PATH")


def _env_values(*paths):
    found = []
    for path in paths:
        try:
            env = json.loads(path.read_text()).get("env", {})
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(env, dict):
            found += [v for v in env.values() if isinstance(v, str) and len(v) >= 8]
    return found


@pytest.mark.skipif(not PILOT, reason="PEO_PILOT1_PATH not set")
def test_a3_pilot1_traits():
    root = Path(PILOT)
    user_config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    out = inv.inventory(root, user_config=user_config, managed=inv.default_managed())
    text = json.dumps(out)
    secrets = _env_values(root / ".claude" / "settings.json", root / ".claude" / "settings.local.json",
                          user_config / "settings.json")
    ok = validate(out, load_schema("inventory")) == []
    assert ok
    ok = any(s["status"] == "read" for s in out["sources"])
    assert ok
    ok = not any(v in text for v in secrets)
    assert ok
