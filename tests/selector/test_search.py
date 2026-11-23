"""Candidates, search and justification codes (spec 13 sections 8.1 to 8.3), on in-memory catalogs."""

import pytest

from peo import selector
from peo.selector import TooManyCandidates

from .conftest import NO_BACKBONE, make_catalog_doc, profile, rule, tool


def run(entries, rules=(), exclusive=(), prof=None, answers=None, declared=None):
    catalog = make_catalog_doc(entries, rules, exclusive=exclusive)
    return selector.select(catalog, prof or profile(), answers or {}, declared or {},
                           backbone="none", backbones=NO_BACKBONE)


def refs(section):
    return [e["ref"] for e in section]


def rejected(out):
    return {e["ref"]: (e["code"], e["detail"]) for e in out["rejected"]}


GATES = tool("peo:gates", ["process.gates"])


def test_a_required_capability_selects_its_tool():
    out = run([GATES, tool("cli:a", ["x.one"])], [rule("r", "x.one")])
    assert refs(out["selected"]) == ["cli:a", "peo:gates"] or refs(out["selected"]) == ["peo:gates", "cli:a"]
    assert out["ok"] is True and out["uncovered"] == []


def test_a_hard_requirement_without_a_candidate_gives_ok_false_and_is_cited():
    out = run([GATES], [rule("r", "x.one", "hard")], )
    assert out["ok"] is False and out["uncovered"] == [{"capability": "x.one", "strength": "hard"}]


def test_a_soft_requirement_without_a_candidate_keeps_ok_true():
    out = run([GATES], [rule("r", "x.one", "soft")])
    assert out["ok"] is True and out["uncovered"] == [{"capability": "x.one", "strength": "soft"}]


def test_a_pair_in_conflicts_never_comes_together():
    a = tool("cli:a", ["x.one"], conflicts=["cli:b"])
    b = tool("cli:b", ["x.two"])
    out = run([GATES, a, b], [rule("r1", "x.one"), rule("r2", "x.two")])
    chosen = {e["ref"] for e in out["selected"]}
    assert not {"cli:a", "cli:b"} <= chosen
    loser = ({"cli:a", "cli:b"} - chosen).pop()
    assert rejected(out)[loser][0] == "CONFLICT" and ({"cli:a", "cli:b"} - {loser}).pop() in rejected(out)[loser][1]


def test_a_hard_requirement_beats_a_soft_one_in_a_conflict():
    a = tool("cli:a", ["x.one"], conflicts=["cli:b"])
    b = tool("cli:b", ["x.two"])
    out = run([GATES, a, b], [rule("r1", "x.one", "hard"), rule("r2", "x.two", "soft")])
    assert "cli:a" in refs(out["selected"]) and "cli:b" not in refs(out["selected"])


def test_an_exclusive_capability_has_one_provider():
    a, b = tool("cli:a", ["x.one"], tokens=2000), tool("cli:b", ["x.one"])
    out = run([GATES, a, b], [rule("r", "x.one")], exclusive=["x.one"])
    assert refs(out["selected"]).count("cli:b") == 1 and "cli:a" not in refs(out["selected"])
    assert rejected(out)["cli:a"][0] == "COST"


def test_equal_cost_ties_break_on_the_sorted_identifiers():
    a, b = tool("cli:a", ["x.one"]), tool("cli:b", ["x.one"])
    out = run([GATES, b, a], [rule("r", "x.one")], exclusive=["x.one"])
    assert "cli:a" in refs(out["selected"]) and rejected(out)["cli:b"][0] == "COST"


def test_requires_are_pulled_in_with_their_cost():
    a = tool("cli:a", ["x.one"], requires=["cli:dep"])
    out = run([GATES, a, tool("cli:dep", [])], [rule("r", "x.one")])
    dep = next(e for e in out["selected"] if e["ref"] == "cli:dep")
    assert dep["covers"] == [] and dep["rule"] == "requires (cli:a)" and dep["cost"] == 1
    assert out["cost_total"] == sum(e["cost"] for e in out["selected"]) == 3


def test_a_tool_that_nothing_requires_and_that_covers_nothing_is_not_required():
    out = run([GATES, tool("cli:idle", ["x.two"])], [rule("r", "x.one")])
    assert rejected(out)["cli:idle"][0] == "NOT_REQUIRED"


def test_a_helper_with_no_dependent_is_not_required():
    out = run([GATES, tool("cli:helper", [])], [])
    assert rejected(out)["cli:helper"][0] == "NOT_REQUIRED"


def test_a_present_tool_covers_and_is_reused_at_no_cost():
    present = profile(present_tools=[{"ref": "cli:p", "evidence": "dev dependency"}])
    out = run([GATES, tool("cli:p", ["x.one"])], [rule("r", "x.one", "hard")], prof=present)
    assert out["reused"] == [{"ref": "cli:p", "covers": ["x.one"], "evidence": "dev dependency"}]
    assert out["ok"] is True and out["requirements"][-1]["covered_by"] == "cli:p"


def test_a_tool_providing_a_needed_capability_and_an_exclusive_one_already_covered_is_redundant():
    present = profile(present_tools=[{"ref": "cli:p", "evidence": "x"}])
    both = tool("cli:both", ["x.one", "x.two"])
    out = run([GATES, tool("cli:p", ["x.one"]), both], [rule("r1", "x.one"), rule("r2", "x.two")],
              exclusive=["x.one"], prof=present)
    assert rejected(out)["cli:both"][0] == "REDUNDANT" and "cli:p" in rejected(out)["cli:both"][1]


def test_statuses_and_the_backbone_codes_come_first():
    out = run([GATES, tool("cli:w", ["x.one"], status="watch"), tool("cli:r", ["x.one"], status="rejected"),
               tool("cli:alt", ["x.one"], status="backbone-alt")], [rule("r", "x.one")])
    assert rejected(out)["cli:w"] == ("STATUS", "status watch")
    assert rejected(out)["cli:r"] == ("STATUS", "status rejected")
    assert rejected(out)["cli:alt"] == ("BACKBONE_EXCLUSIVE", "alternative backbone")


def test_a_false_when_cites_the_expression_and_a_contraindication_wins_over_a_true_when():
    out = run([GATES, tool("cli:big", ["x.one"], any_=["profile.metrics.loc_total > 50000"]),
               tool("cli:no", ["x.two"], any_=["profile.metrics.loc_total < 50000"],
                    not_=["profile.metrics.loc_total > 5"])],
              [rule("r1", "x.one"), rule("r2", "x.two")])
    assert rejected(out)["cli:big"] == ("CONDITION_FALSE", "profile.metrics.loc_total > 50000 is false")
    assert rejected(out)["cli:no"] == ("CONTRAINDICATED", "profile.metrics.loc_total > 5 is true")


def test_when_all_needs_every_expression():
    a = tool("cli:a", ["x.one"], all_=["profile.metrics.loc_total > 5", "profile.metrics.loc_total > 5000"])
    out = run([GATES, a], [rule("r", "x.one")])
    assert rejected(out)["cli:a"] == ("CONDITION_FALSE", "profile.metrics.loc_total > 5000 is false")


def test_a_blocking_prerequisite_without_a_fix_rejects_the_tool():
    a = tool("cli:a", ["x.one"], prerequisites=[{"check": "bin:nothing", "blocking": True}])
    out = run([GATES, a], [rule("r", "x.one")])
    assert rejected(out)["cli:a"] == ("PREREQ_UNMET", "bin:nothing unmet and no fix")


def test_an_unmet_prerequisite_with_a_fix_adds_the_fix_tool_and_one_to_the_cost():
    a = tool("cli:a", ["x.one"], prerequisites=[{"check": "bin:fixme", "fix": "cli:fixer", "blocking": True}])
    out = run([GATES, a, tool("cli:fixer", [])], [rule("r", "x.one")])
    chosen = {e["ref"]: e for e in out["selected"]}
    assert chosen["cli:a"]["cost"] == 2 and chosen["cli:fixer"]["rule"] == "prerequisite (cli:a)"
    assert chosen["cli:a"]["prerequisites"] == [
        {"check": "bin:fixme", "status": "unmet", "action": "fix", "fix": "cli:fixer"}]


@pytest.mark.parametrize("tokens, hooks, network, expected", [
    (0, [], "none", 1), (1, [], "none", 2), (500, [], "none", 2), (501, [], "none", 3),
    (0, ["PreToolUse"], "none", 4), (0, [], "runtime", 3), (1200, ["a", "b"], "runtime", 1 + 3 + 6 + 2)])
def test_the_cost_formula(tokens, hooks, network, expected):
    entry = tool("cli:a", ["x.one"], tokens=tokens, hooks=hooks, network=network)[1]
    assert selector.cost(entry, []) == expected


def test_the_search_prefers_fewer_hard_then_soft_then_cost():
    cheap = tool("cli:cheap", ["x.soft"])
    big = tool("cli:big", ["x.hard", "x.soft"], tokens=5000)
    out = run([GATES, cheap, big], [rule("h", "x.hard", "hard"), rule("s", "x.soft", "soft")])
    assert "cli:big" in refs(out["selected"]) and out["uncovered"] == []


def test_more_than_24_candidates_is_a_catalog_defect():
    entries = [GATES] + [tool(f"cli:t{i:02d}", [f"x.c{i:02d}"]) for i in range(24)]
    rules = [rule(f"r{i:02d}", f"x.c{i:02d}") for i in range(24)]
    with pytest.raises(TooManyCandidates) as raised:
        run(entries, rules)
    assert raised.value.candidates == 25


def test_exactly_24_candidates_is_searched():
    entries = [GATES] + [tool(f"cli:t{i:02d}", [f"x.c{i:02d}"]) for i in range(23)]
    rules = [rule(f"r{i:02d}", f"x.c{i:02d}") for i in range(23)]
    assert len(run(entries, rules)["selected"]) == 24
