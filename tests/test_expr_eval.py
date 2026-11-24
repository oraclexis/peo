"""`evaluate` (spec 13, section 3): no code of the catalog runs, nothing raises."""

import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from peo import expr

PROFILE = {
    "metrics": {"loc_total": 4717},
    "components": [{"id": "root", "kind": "frontend", "languages": ["typescript", "css"]},
                   {"id": "backend", "kind": "backend", "languages": ["php"]}],
    "signals": {"auth": {"value": True, "confidence": "likely"},
                "design_rules_in_instructions": {"value": True, "confidence": "fact"}},
    "sensitive": {"secret_files": [{"path": "backend/.env"}], "data_dumps": []},
    "name": "split-stack",
}
CTX = {"profile": PROFILE, "answers": {"q.refactoring": True}, "selection": {"selected": ["cli:a"], "covered": ["x.y"]}}


def holds(text, ctx=CTX, it=False):
    return expr.holds(expr.parse(text, it=it), ctx)


@pytest.mark.parametrize("text, expected", [
    ("profile.metrics.loc_total > 50000 or answers['q.refactoring'] == true", True),     # 13 section 3
    ("any(profile.components, 'php' in it.languages)", True),
    ("not profile.signals.design_rules_in_instructions.value", False),
    ("profile.sensitive.secret_files != []", True),
    ("profile.metrics.loc_total > 50000", False),
    ("profile.metrics.loc_total >= 4717 and profile.metrics.loc_total <= 4717", True),
    ("profile.signals.auth.confidence == 'fact'", False),
    ("profile.signals.auth.confidence == 'likely'", True),
    ("profile.sensitive.data_dumps != [] or profile.sensitive.data_dumps == []", True),
])
def test_the_examples_of_section_3(text, expected):
    assert holds(text) is expected


def test_a_missing_path_is_null_and_never_an_error():
    assert holds("profile.nothing.here == null") and holds("answers['q.none'] == null")
    assert not holds("profile.nothing.here > 5") and not holds("5 > profile.nothing")
    assert not holds("profile.nothing < 5") and not holds("profile.nothing >= profile.nothing2")
    assert holds("profile.name.deeper == null")          # a string has no field


def test_types_do_not_mix():
    assert not holds("profile.name > 5") and not holds("'a' > 5") and not holds("true > 0")
    assert not holds("true == 1") and holds("true != 1") and holds("1 == 1.0")
    assert holds("'b' > 'a'")


def test_lists_keep_booleans_apart_from_numbers():
    ctx = {"profile": {"f": [True], "n": [[1], [True]]}, "answers": {}, "selection": {}}
    assert not expr.holds(expr.parse("profile.f == [1]"), ctx)
    assert expr.holds(expr.parse("profile.f != [1]"), ctx) and expr.holds(expr.parse("profile.f == [true]"), ctx)
    assert not expr.holds(expr.parse("profile.n == [[1], [1]]"), ctx)
    assert not expr.holds(expr.parse("1 in profile.f"), ctx)


def test_in_and_contains():
    assert holds("'php' in ['php', 'ts']") and not holds("'go' in ['php']")
    assert holds("'ph' in 'php'") and holds("profile.name contains 'split'")
    assert holds("['a', 'b'] contains 'a'") and not holds("profile.nothing contains 'a'")
    assert not holds("1 in 'php'") and not holds("'a' in null")


def test_any_with_it_and_on_a_value_that_is_not_a_list():
    assert holds("any(profile.components, it.kind == 'backend' and 'php' in it.languages)")
    assert not holds("any(profile.components, it.kind == 'mobile')")
    assert not holds("any(profile.name, it == 'x')") and not holds("any(profile.nothing, true)")


def test_it_at_the_root_of_a_for_each_rule():
    root = {**CTX, "it": PROFILE["components"][1]}
    assert holds("'php' in it.languages", root, it=True)
    assert not holds("it.kind == 'frontend'", root, it=True)


def test_selection_exposes_selected_and_covered_only():
    assert holds("'cli:a' in selection.selected") and holds("'x.y' in selection.covered")
    assert holds("selection.other == null") and holds("selection.selected.first == null")


def test_matches_is_anchored_at_both_ends():
    ctx = {**CTX, "profile": {"id": "api-v1"}}
    assert holds("profile.id matches 'api-.*'", ctx) and holds("profile.id matches 'api-v[0-9]'", ctx)
    assert not holds("profile.id matches 'api'", ctx) and not holds("profile.id matches 'v1'", ctx)
    assert not holds("profile.missing matches 'x'", ctx) and not holds("5 matches '5'", ctx)


def test_matches_input_over_512_characters_is_false_without_error():
    long = {"profile": {"id": "a" * 513}, "answers": {}, "selection": {}}
    assert not expr.holds(expr.parse("profile.id matches 'a*'"), long)
    exact = {"profile": {"id": "a" * 512}, "answers": {}, "selection": {}}
    assert expr.holds(expr.parse("profile.id matches 'a*'"), exact)


def test_a_huge_input_is_evaluated_fast():
    ctx = {"profile": {"id": "a" * 100_000}, "answers": {}, "selection": {}}
    start = time.perf_counter()
    assert not expr.holds(expr.parse("profile.id matches '[a-z]+-[0-9]+'"), ctx)
    assert time.perf_counter() - start < 1


def test_logic_operators_return_booleans_and_short_circuit_safely():
    assert expr.evaluate(expr.parse("1 == 1 and 2 == 2"), CTX) is True
    assert expr.evaluate(expr.parse("1 == 2 or 2 == 3"), CTX) is False
    assert expr.evaluate(expr.parse("not null"), CTX) is True
    assert expr.evaluate(expr.parse("profile.name"), CTX) == "split-stack"


TEXTS = st.one_of(
    st.sampled_from([
        "profile.a > 1", "any(profile.components, it.x == 1)", "not profile.a", "[1, 2] contains 1",
        "profile.a matches 'a+'", "answers['x'] in [1, 'a', null]", "(profile.a)", "null == null"]),
    st.text(alphabet="profile.answers[]'()<>=! 01 andornotinany,it", max_size=40))


@settings(max_examples=300, deadline=None)
@given(TEXTS, st.dictionaries(st.text(max_size=3), st.one_of(st.none(), st.integers(), st.text(max_size=3),
                                                            st.lists(st.integers(), max_size=3)), max_size=3))
def test_evaluate_never_raises_on_an_accepted_text(text, profile):
    try:
        node = expr.parse(text)
    except expr.ExprError:
        return
    expr.evaluate(node, {"profile": profile, "answers": {}, "selection": {}})
