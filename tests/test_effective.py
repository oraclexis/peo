"""Effective value of a scalar setting, spec 14 §3.6; A3.13 (effective value)."""

import ast
from pathlib import Path

import pytest

from peo.inventory import effective

IDS = ("settings:managed", "settings:managed.d", "settings:managed-other", "settings:cli",
       "settings:local", "settings:project", "settings:user")
OUT_OF_SCOPE = {"settings:managed-other", "settings:cli"}


def sources(**states):
    """Every settings source, `read` unless named: states={"settings_user": ("invalid", "json")}."""
    out = []
    for sid in IDS:
        status, reason = ("not_inspected", "out-of-scope") if sid in OUT_OF_SCOPE else ("read", None)
        status, reason = states.get(sid.replace(":", "_").replace("-", "_").replace(".", "_"),
                                    (status, reason))
        out.append({"id": sid, "scope": sid.split(":")[1].split("-")[0].split(".")[0],
                    "status": status, "reason": reason, "invalid_families": [], "tracked": None,
                    "path": None})
    return out


def flag(source, key, value):
    return {"source": source, "key": key, "value": value}


def value(key, srcs, flags, **kw):
    return effective.effective(key, srcs, flags, **kw)


def test_precedence_managed_first():
    flags = [flag("settings:managed", "sandbox.enabled", True),
             flag("settings:project", "sandbox.enabled", False)]
    assert value("sandbox.enabled", sources(), flags) == {
        "value": True, "source": "settings:managed", "unreadable": []}


def test_rule_1_local_over_project_over_user():
    flags = [flag("settings:user", "k", True), flag("settings:project", "k", False),
             flag("settings:local", "k", True)]
    assert value("k", sources(), flags)["source"] == "settings:local"
    assert value("k", sources(), flags[:2])["source"] == "settings:project"


def test_rule_2_out_of_scope_is_skipped():
    out = value("k", sources(), [flag("settings:user", "k", False)])
    assert out == {"value": False, "source": "settings:user", "unreadable": []}


@pytest.mark.parametrize("state", [("invalid", "json"), ("unavailable", "permission-denied"),
                                   ("not_inspected", "not-provided")])
def test_rule_3_stronger_unreadable_gives_unknown(state):
    out = value("k", sources(settings_local=state), [flag("settings:project", "k", True)])
    assert out == {"value": "unknown", "source": "settings:project", "unreadable": ["settings:local"]}


def test_rule_3_invalid_flags_family_gives_unknown():
    srcs = sources()
    next(s for s in srcs if s["id"] == "settings:project")["invalid_families"] = ["flags"]
    assert value("k", srcs, [])["value"] == "unknown"
    assert value("k", srcs, [])["unreadable"] == ["settings:project"]


def test_rule_3_weaker_unreadable_does_not_matter():
    out = value("k", sources(settings_user=("invalid", "json")), [flag("settings:local", "k", True)])
    assert out == {"value": True, "source": "settings:local", "unreadable": []}


def test_rule_4_absent_everywhere():
    assert value("k", sources(settings_user=("absent", None)), []) == {
        "value": None, "source": None, "unreadable": []}


def test_a3_13_managed_only_ignores_other_scopes():
    flags = [flag("settings:project", "allowManagedPermissionRulesOnly", True)]
    srcs = sources(settings_user=("invalid", "json"))
    assert value("allowManagedPermissionRulesOnly", srcs, flags, managed_only=True)["value"] is None


@pytest.mark.parametrize("broken", ["status", "flags"])
def test_a3_13_managed_unreadable_gives_unknown(broken):
    srcs = sources(settings_managed=("invalid", "json")) if broken == "status" else sources()
    if broken == "flags":
        srcs[0]["invalid_families"] = ["flags"]
    out = value("allowManagedPermissionRulesOnly", srcs, [], managed_only=True)
    assert out["value"] == "unknown" and out["unreadable"] == ["settings:managed"]


def test_a3_13_managed_other_out_of_scope_is_not_unknown():
    out = value("allowManagedPermissionRulesOnly", sources(), [], managed_only=True)
    assert out["value"] is None


def test_managed_d_files_keep_their_order():
    srcs = [s for s in sources() if s["id"] != "settings:managed.d"]
    for n in (0, 1):
        srcs.insert(1 + n, {**srcs[0], "id": f"settings:managed.d/#{n}"})
    flags = [flag("settings:managed.d/#1", "k", False), flag("settings:managed.d/#0", "k", True)]
    assert value("k", srcs, flags)["source"] == "settings:managed.d/#0"


def imports(module: str) -> set[str]:
    path = Path(__file__).resolve().parents[1] / "src" / "peo" / "inventory" / f"{module}.py"
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            found.add((node.module or "").split(".")[0])
    return found


def test_effective_imports():
    assert imports("effective") <= {"typing", "__future__"}
