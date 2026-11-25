"""In-memory catalogs and hand-written profiles for the Selector tests (spec 16 section 2)."""

import json
from pathlib import Path

import pytest

from peo.catalog import Catalog

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "golden"
EXAMPLES = ROOT / "docs" / "design" / "spec" / "schemas" / "examples"


def tool(ref: str, provides=(), requires=(), conflicts=(), status="conditional", any_=(), all_=(),
         not_=(), tokens=0, hooks=(), network="none", prerequisites=(), detect=None) -> tuple[str, dict]:
    """One catalog entry as `catalog.load` would give it; only the fields the Selector reads."""
    kind, _, name = ref.partition(":")
    doc: dict = {"id": name, "kind": kind, "status": status, "capabilities": {"provides": list(provides)},
                 "relations": {"requires": list(requires), "conflicts": list(conflicts)},
                 "selection": {"when": {"any": list(any_), "all": list(all_), "not": list(not_)}},
                 "prerequisites": [dict(p) for p in prerequisites],
                 "surface": {"hooks": list(hooks), "network": network},
                 "cost": {"context_static_tokens": tokens}}
    if detect:
        doc["detect"] = detect
    return ref, doc


def make_catalog_doc(entries, rules=(), exclusive=(), extra_capabilities=()) -> Catalog:
    """A `Catalog` without a disk; every provided or required capability is known."""
    docs = dict(sorted(entries))
    names = {c for d in docs.values() for c in d["capabilities"]["provides"]}
    names |= {r["require"]["capability"] for r in rules} | set(extra_capabilities) | set(exclusive)
    return Catalog(capabilities={n: n in set(exclusive) for n in sorted(names)}, rules=tuple(rules),
                   entries=docs, questions=())


def rule(rid: str, capability: str, strength: str = "soft", when: str | None = None, for_each=None) -> dict:
    out: dict = {"id": rid, "require": {"capability": capability, "strength": strength}}
    if when is not None:
        out["when"] = when
    if for_each is not None:
        out["for_each"] = for_each
    return out


def profile(**changes) -> dict:
    base = {"components": [], "present_tools": [], "metrics": {"loc_total": 100},
            "signals": {}, "sensitive": {"secret_files": [], "data_dumps": [], "log_dirs": []}}
    return base | changes


def golden(name: str, file: str = "profile.json") -> dict:
    return json.loads((GOLDEN / name / file).read_text())


NO_BACKBONE = {"none": ()}


@pytest.fixture
def real_catalog():
    from datetime import date

    from peo.catalog import load
    return load(ROOT / "catalog", today=date(2026, 11, 23))
