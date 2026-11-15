"""Rule comparator covers(), spec 14 §3.5: A3.12, A3.13 (comparator), A3.14, A3.15.

Outside the machine guard of tests/status: hypothesis runs here. covers() is pure, so no
file, command or home folder is needed: paths are plain strings.
"""

import copy
import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from peo.inventory import claude_rules
from tests.test_effective import imports

SPEC = Path(__file__).resolve().parents[1] / "docs" / "design" / "spec" / "conformance"
DARWIN = json.loads((SPEC / "claude-rules.json").read_text())
LINUX_PATH = SPEC / "claude-rules.linux.json"
HOME = "/fixture-home"
ROOT = f"{HOME}/proj"
LIT = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._@+-"
# Expected verdict of every off-list case (spec 14 §3.5, table « Verdict attendu »).
OFF_LIST = {
    "symlink": ("covered", None), "symlink-dir": ("covered", None),
    "symlink-deny-link-read-link": ("undecidable", "symlink"),
    "symlink-deny-link-read-target": ("not_covered", None),
    "symlink-dir-deny-linkdir": ("not_covered", None),
    "dir-star-direct": ("undecidable", "untested-form"),
    "dir-star-nested": ("undecidable", "untested-form"),
    "question-mark": ("undecidable", "untested-form"),
    "brackets": ("undecidable", "untested-form"),
    "case-differs": ("undecidable", "case-only"),
    "bare-tool": ("undecidable", "bare-tool"), "bare-tool-deny-only": ("undecidable", "bare-tool"),
    "slash-anchor-claude-dir": ("not_covered", None),
    "allow-specific-vs-deny": ("covered", None), "bypass-mode": ("covered", None),
}


def tables():
    found = [pytest.param(DARWIN, id="darwin")]
    linux = pytest.mark.skipif(not LINUX_PATH.exists(), reason="claude-rules.linux.json not played yet")
    data = json.loads(LINUX_PATH.read_text()) if LINUX_PATH.exists() else None
    return found + [pytest.param(data, id="linux", marks=linux)]


def source(sid, **extra):
    scope = {"settings:project": "project", "settings:local": "local", "settings:user": "user",
             "settings:managed": "managed"}[sid]
    return {"id": sid, "scope": scope, "tracked": True, "modified": False} | extra


def replay(case, table):
    """covers() on one spike case: the case's deny rules in its scope, on its target."""
    sid = "settings:local" if case["options"].get("scope") == "local" else "settings:project"
    rules = [{"source": sid, "list": "deny",
              "rule": r.replace("<root>", ROOT).replace("<home>", HOME).replace("<root-name>", "proj")}
             for r in case["settings"].get("permissions", {}).get("deny", [])]
    target = case["target"]
    link = ("backend/.env" if target == "link.env" else
            "backend/" + target.removeprefix("linkdir/") if target.startswith("linkdir/") else False)
    return claude_rules.covers(target, False, link, rules, [source(sid)], None,
                               table["versions_tested"][0], table["platform"], table, ROOT, HOME)


def verdict(rule, path="backend/.env", sid="settings:project", *, is_dir=False, link=False,
            version="2.1.325", table=DARWIN, mro=None, sources=None):
    rules = [{"source": sid, "list": "deny", "rule": rule}]
    return claude_rules.covers(path, is_dir, link, rules, sources or [source(sid)], mro, version,
                               "Darwin", table, ROOT, HOME)


# A3.12: the table replayed

@pytest.mark.parametrize("table", tables())
def test_a3_12_reference_cases_covered(table):
    refs = [c for c in table["cases"] if c["role"] == "reference"]
    assert refs
    assert {c["id"]: replay(c, table)["verdict"] for c in refs} == {c["id"]: "covered" for c in refs}


@pytest.mark.parametrize("table", tables())
def test_a3_12_off_list_expected_verdicts(table):
    cases = {c["id"]: c for c in table["cases"] if c["role"] == "off-list"}
    assert set(cases) == set(OFF_LIST)
    got = {i: (replay(c, table)["verdict"], replay(c, table)["reason"]) for i, c in cases.items()}
    assert got == OFF_LIST


@pytest.mark.parametrize("table", tables())
def test_a3_12_observed_read_never_covered(table):
    read = [c for c in table["cases"] if c["observed"] == "read" and not c["id"].startswith("cwd-")]
    assert read
    assert [c["id"] for c in read if replay(c, table)["verdict"] == "covered"] == []


def test_a3_12_reference_case_ids_of_spec_table():
    by_pair = {(c["form"], c["relation"], c["scope"]) for c in DARWIN["cases"] if c["role"] == "reference"}
    assert ("dot", "under", "local") not in by_pair and ("dot", "exact", "project") in by_pair


# A3.14: admitted grammar

@pytest.mark.parametrize("rule", [
    "Read(./backend/.[^e]nv)", "Read(./backend/*)", "Read(./backend/.en?)", "Read(./{a,b}/.env)",
    "Read(./backend/!x)", "Read(./backend/#x)", "Read(./back end/.env)", "Read(./backend/é.env)",
    "Read(backend)", "Read(backend/**)", "Read(./${HOME}/.env)", "Read(./backend/../backend/.env)"])
def test_a3_14_untested_form(rule):
    out = verdict(rule)
    assert (out["verdict"], out["reason"]) == ("undecidable", "untested-form")


def test_a3_14_unrelated_pattern_outside_grammar_is_ignored():
    assert verdict("Read(./frontend/*.ts)")["verdict"] == "not_covered"


def test_a3_14_dot_under_in_local_scope_is_untested_scope():
    out = verdict("Read(./backend)", sid="settings:local")
    assert (out["verdict"], out["reason"]) == ("undecidable", "untested-scope")


def test_a3_14_dir_forms_cover_a_log_dir():
    for rule in ("Read(./storage/logs/**)", "Read(./storage/logs)", "Read(./storage/logs/)"):
        assert verdict(rule, "storage/logs", is_dir=True)["verdict"] == "covered", rule


BAD = " *?[]{}!\\#:()é\n\x1b"


def _core(pattern: str) -> str:
    pattern = pattern[:-3] if pattern.endswith("/**") else pattern
    return pattern[3:] if pattern.startswith("**/") else pattern


@given(prefix=st.sampled_from(["", "./", "/", "//", "~/", "**/"]),
       middle=st.text(alphabet=LIT + "/" + BAD, min_size=1, max_size=20),
       suffix=st.sampled_from(["", "/", "/**"]),
       path=st.sampled_from(["backend/.env", ".env", "a/b/c/d/.env"]))
def test_a3_14_property_outside_literal_set_never_covered(prefix, middle, suffix, path):
    pattern = prefix + middle + suffix
    if not any(c in BAD for c in _core(pattern)):
        return
    for target in (path, middle.strip("/") or "x"):
        assert verdict(f"Read({pattern})", target)["verdict"] != "covered"


# A3.15: table lookup

def test_a3_15_no_table_untested_platform():
    out = verdict("Read(./backend/.env)", table=None)
    assert (out["verdict"], out["reason"]) == ("undecidable", "untested-platform")


@pytest.mark.parametrize("version", ["2.1.300", None])
def test_a3_15_older_or_unknown_version(version):
    out = verdict("Read(./backend/.env)", version=version)
    assert (out["verdict"], out["reason"]) == ("undecidable", "untested-version")


def test_a3_15_newer_version_covered_and_newer():
    out = verdict("Read(./backend/.env)", version="2.1.400")
    assert (out["verdict"], out["newer"]) == ("covered", True)
    assert verdict("Read(./backend/.env)")["newer"] is False


def test_a3_15_user_scope_untested_scope():
    out = verdict("Read(./backend/.env)", sid="settings:user")
    assert (out["verdict"], out["reason"]) == ("undecidable", "untested-scope")


def test_a3_15_contradictory_observations():
    table = copy.deepcopy(DARWIN)
    next(c for c in table["cases"] if c["id"] == "dot-exact")["observed"] = "read"
    out = verdict("Read(./backend/.env)", table=table)
    assert (out["verdict"], out["reason"]) == ("undecidable", "contradictory-observations")


# A3.13: allowManagedPermissionRulesOnly, comparator side

def test_a3_13_covers_managed_only_ignores_project_rule():
    out = verdict("Read(./backend/.env)", mro=True)
    assert (out["verdict"], out["reason"]) == ("not_covered", None)


def test_a3_13_covers_managed_only_unknown_is_undecidable():
    out = verdict("Read(./backend/.env)", mro="unknown")
    assert (out["verdict"], out["reason"]) == ("undecidable", "source-unreadable")


# passes 2 and 6

def test_symlink_outside_never_compared():
    out = verdict("Read(./backend/.env)", link=None)
    assert out == {"verdict": "undecidable", "reason": "symlink-outside", "rule": None,
                   "source": None, "newer": False, "evidence": []}


def test_decisive_rule_prefers_shared_project_rule():
    rules = [{"source": "settings:local", "list": "deny", "rule": "Read(./backend/.env)"},
             {"source": "settings:project", "list": "deny", "rule": "Read(./backend/**)"}]
    sources = [source("settings:local"), source("settings:project")]
    out = claude_rules.covers("backend/.env", False, False, rules, sources, None, "2.1.325",
                              "Darwin", DARWIN, ROOT, HOME)
    assert (out["verdict"], out["rule"], out["source"]) == (
        "covered", "Read(./backend/**)", "settings:project")
    sources[1]["modified"] = None
    out = claude_rules.covers("backend/.env", False, False, rules, sources, None, "2.1.325",
                              "Darwin", DARWIN, ROOT, HOME)
    assert out["source"] == "settings:local"


def test_first_reason_kept_others_in_evidence():
    rules = [{"source": "settings:project", "list": "deny", "rule": "Read"},
             {"source": "settings:project", "list": "deny", "rule": "Read(./backend/.env)"}]
    out = claude_rules.covers("backend/.env", False, False, rules, [source("settings:project")],
                              None, "2.1.300", "Darwin", DARWIN, ROOT, HOME)
    assert (out["reason"], out["rule"]) == ("untested-version", "Read(./backend/.env)")
    assert out["evidence"] == ["settings:project deny Read: bare-tool"]


def test_claude_rules_imports():
    assert imports("claude_rules") <= {"typing", "__future__"}
