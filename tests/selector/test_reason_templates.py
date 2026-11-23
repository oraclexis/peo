"""Texts of `reason` and `detail` follow the templates of spec 13 section 8.3 (FR-018)."""

import re

from peo import selector

from .conftest import NO_BACKBONE, golden, make_catalog_doc, profile, rule, tool


def test_every_text_of_the_split_stack_selection_follows_a_template(real_catalog):
    out = selector.select(real_catalog, golden("fx-split-stack"), {}, {})
    for item in out["selected"]:
        assert re.fullmatch(r"covers [a-z0-9., -]+|required by \S+|prerequisite of \S+", item["reason"]), item
    for item in out["rejected"]:
        assert item["detail"] and "/Users/" not in item["detail"] and "\\" not in item["detail"]
        assert {"STATUS": r"status \w[\w-]*", "BACKBONE_EXCLUSIVE": "alternative backbone",
                "NOT_REQUIRED": r"[a-z0-9., -]+ not required|not required by a selected tool",
                "CONDITION_FALSE": r".+ is false", "CONTRAINDICATED": r".+ is true"}[item["code"]] \
            and re.fullmatch({"STATUS": r"status \w[\w-]*", "BACKBONE_EXCLUSIVE": "alternative backbone",
                              "NOT_REQUIRED": r"[a-z0-9., -]+ not required|not required by a selected tool",
                              "CONDITION_FALSE": r".+ is false",
                              "CONTRAINDICATED": r".+ is true"}[item["code"]], item["detail"]), item


def test_conflict_cost_redundant_and_prereq_texts_name_what_they_cite():
    a = tool("cli:a", ["x.one"], conflicts=["cli:b"])
    b = tool("cli:b", ["x.two"])
    cheap, dear = tool("cli:cheap", ["x.three"]), tool("cli:dear", ["x.three"], tokens=3000)
    catalog = make_catalog_doc([tool("peo:gates", ["process.gates"]), a, b, cheap, dear],
                               [rule("r1", "x.one", "hard"), rule("r2", "x.two"), rule("r3", "x.three")],
                               exclusive=["x.three"])
    out = selector.select(catalog, profile(), {}, {}, backbone="none", backbones=NO_BACKBONE)
    detail = {e["ref"]: e["detail"] for e in out["rejected"]}
    assert detail["cli:b"] == "conflicts with cli:a"
    assert detail["cli:dear"] == "same coverage at a higher cost than cli:cheap"
