"""The `when` language of the catalog (spec 13 section 3), parse only. Tests of A2.3 use it through the loader."""

import ast
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from peo.expr import ExprError, parse, reads

SOURCE = Path(__file__).resolve().parents[1] / "src" / "peo" / "expr.py"

SPEC_EXAMPLES = [
    "profile.metrics.loc_total > 50000 or answers['q.refactoring'] == true",
    "any(profile.components, 'php' in it.languages)",
    "not profile.signals.design_rules_in_instructions.value",
    "profile.sensitive.secret_files != []",
]


@pytest.mark.parametrize("text", SPEC_EXAMPLES + [
    "profile.signals.auth.confidence == 'fact'",
    "profile.kind.value == 'new'",
    "profile.a == null and (profile.b in ['x', 'y'] or not profile.c)",
    "profile.name matches 'api-.*'",
    "profile['odd key'].value contains 'x'",
    "profile.metrics.loc_total >= 20000 and profile.metrics.loc_total < 50000",
])
def test_a2_3_valid_expressions_parse(text):
    assert parse(text) is not None


@pytest.mark.parametrize("text", [
    "",
    "profile.metrics.loc_total >",
    "(profile.x == 1",
    "profile.x == 1)",
    "profile.x === 1",
    "profile.x <> 1",
    "profile.x == 1 profile.y",
    "foo.bar == 1",
    "it.languages",                                   # `it` exists only under any(...)
    "any(profile.components)",
    "any(profile.components, 'php' in it.languages",
    "profile.x == 'unterminated",
    "profile.x matches profile.y",                    # the pattern must be a literal
    "profile.x matches '('",                          # not a regular expression
    "profile.x matches '" + "a" * 201 + "'",          # 200 characters at most
    "profile.x == eval('1')",
    "__import__('os')",
])
def test_a2_3_invalid_expressions_are_rejected_with_a_position(text):
    with pytest.raises(ExprError) as info:
        parse(text)
    assert isinstance(info.value.position, int) and 0 <= info.value.position <= len(text)


def test_a2_3_it_is_allowed_at_the_top_level_when_the_caller_says_so():
    assert reads(parse("'php' in it.languages", it=True)) == frozenset()
    with pytest.raises(ExprError):
        parse("'php' in it.languages")


def test_a2_3_a_pattern_of_exactly_200_characters_is_accepted():
    assert parse("profile.x matches '" + "a" * 200 + "'") is not None


def test_a2_3_reads_gives_normalized_paths():
    assert reads(parse(SPEC_EXAMPLES[0])) == {"profile.metrics.loc_total", "answers['q.refactoring']"}
    assert reads(parse("profile['odd key'].value")) == {"profile['odd key'].value"}


def test_a2_3_reads_of_any_names_the_list_and_not_the_element():
    assert reads(parse(SPEC_EXAMPLES[1])) == {"profile.components"}


def test_a2_3_literals_read_nothing():
    assert reads(parse("true or 1 == 1 or 'a' in ['a']")) == frozenset()


def test_a2_3_a_deep_nesting_is_an_error_not_a_crash():
    with pytest.raises(ExprError):
        parse("(" * 5000 + "profile.x" + ")" * 5000)


@settings(max_examples=300, deadline=None)
@given(st.text(max_size=80))
def test_a2_3_parse_never_raises_anything_but_expr_error(text):
    try:
        parse(text)
    except ExprError:
        pass


def test_a2_3_expr_calls_no_eval_and_imports_only_the_standard_library():
    tree = ast.parse(SOURCE.read_text())
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not called & {"eval", "exec", "compile", "__import__"}
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert imported <= set(sys.stdlib_module_names)
