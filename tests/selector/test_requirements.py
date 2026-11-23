"""Requirements (spec 13 section 8.1 step 2, section 6)."""

import pytest

from peo import selector
from peo.selector import BackboneUnknown

from .conftest import make_catalog_doc, profile, rule, tool

BB = ("framework:a", "claude-plugin:b")


def catalog(rules=(), exclusive=()):
    return make_catalog_doc([tool("framework:a", ["spec.authoring", "plan.tasks"]),
                             tool("claude-plugin:b", ["review.code"]),
                             tool("peo:gates", ["process.gates"])], rules, exclusive=exclusive,
                            extra_capabilities=["nav.symbols", "nav.lsp.php", "exposure.native"])


def reqs(rules=(), prof=None, answers=None, backbone=BB):
    return selector.requirements(catalog(rules), prof or profile(), answers or {}, backbone, {})


def as_tuples(found):
    return [(r.capability, r.strength, r.source) for r in found]


def test_backbone_capabilities_are_hard_and_gates_are_always_hard():
    got = as_tuples(reqs())
    assert ("spec.authoring", "hard", "backbone") in got and ("review.code", "hard", "backbone") in got
    assert ("process.gates", "hard", "always") in got
    assert all(s == "hard" for _, s, _ in got)


def test_a_rule_with_a_true_when_adds_a_soft_requirement():
    rules = [rule("big", "nav.symbols", when="profile.metrics.loc_total > 50")]
    assert ("nav.symbols", "soft", "big") in as_tuples(reqs(rules))
    assert "nav.symbols" not in {r.capability for r in reqs(rules, profile(metrics={"loc_total": 10}))}


def test_a_rule_without_when_always_applies():
    assert ("nav.symbols", "soft", "all") in as_tuples(reqs([rule("all", "nav.symbols")]))


def test_for_each_gives_one_requirement_per_matching_element():
    comps = [{"id": "root", "languages": ["typescript"]}, {"id": "backend", "languages": ["php"]},
             {"id": "tools", "languages": ["php"]}]
    rules = [rule("lsp", "nav.lsp.php", when="'php' in it.languages", for_each="profile.components")]
    got = [r for r in reqs(rules, profile(components=comps)) if r.capability == "nav.lsp.php"]
    assert len(got) == 1 and got[0].source == "lsp (backend)"          # one per capability, first element


def test_two_rules_on_one_capability_keep_the_strongest():
    rules = [rule("soft-one", "exposure.native", "soft"), rule("hard-one", "exposure.native", "hard")]
    got = [r for r in reqs(rules) if r.capability == "exposure.native"]
    assert as_tuples(got) == [("exposure.native", "hard", "hard-one")]


def test_the_backbone_wins_over_a_soft_rule_on_the_same_capability():
    got = [r for r in reqs([rule("soft", "review.code", "soft")]) if r.capability == "review.code"]
    assert as_tuples(got) == [("review.code", "hard", "backbone")]


def test_order_follows_the_vocabulary_of_the_catalog():
    found = [r.capability for r in reqs([rule("n", "nav.symbols"), rule("e", "exposure.native", "hard")])]
    assert found == [c for c in catalog().capabilities if c in found] and len(found) == 6


def test_an_unknown_backbone_id_is_refused():
    with pytest.raises(BackboneUnknown):
        selector.select(catalog(), profile(), {"q.backbone_conflict": "nope"}, {})
    with pytest.raises(BackboneUnknown):
        selector.select(catalog(), profile(), {}, {}, backbone="nope")
