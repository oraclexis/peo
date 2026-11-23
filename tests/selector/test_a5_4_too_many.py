"""A5.4: more than 24 candidates is a catalog defect."""

import pytest

from peo import selector
from peo.selector import TooManyCandidates

from .conftest import NO_BACKBONE, make_catalog_doc, profile, rule, tool


def world(n):
    entries = [tool(f"cli:t{i:02d}", [f"x.c{i:02d}"]) for i in range(n)]
    rules = [rule(f"r{i:02d}", f"x.c{i:02d}") for i in range(n)]
    return make_catalog_doc(entries, rules)


def test_a5_4_25_candidates_raise_with_the_count():
    with pytest.raises(TooManyCandidates) as raised:
        selector.select(world(25), profile(), {}, {}, backbone="none", backbones=NO_BACKBONE)
    assert raised.value.candidates == 25 and raised.value.code == "E_TOO_MANY_CANDIDATES"
    assert "25" in str(raised.value)


def test_a5_4_24_candidates_are_searched():
    out = selector.select(world(24), profile(), {}, {}, backbone="none", backbones=NO_BACKBONE)
    assert len(out["selected"]) == 24
