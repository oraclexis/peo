"""Bounded `matches` patterns (spec 13 section 3, research D2) and the evaluator's inspection."""

import ast
import re
from pathlib import Path

import pytest

from peo import expr

SRC = Path(__file__).resolve().parents[1] / "src" / "peo"


@pytest.mark.parametrize("pattern", [
    "(a+)+$", "(a|aa)+$", "(a*)*", "(a)\\1", "(?=a)a", "(?<=a)a", "(?!a)b", "(a|a){1,40}", "(a+){9}",
    "a*b*c*", "(?:ab|cd)*", "(x*)+", "(?P<n>a)(?P=n)"])
def test_a_dangerous_pattern_is_refused_at_parse_time_with_its_position(pattern):
    text = f"profile.x matches '{pattern}'"
    with pytest.raises(expr.ExprError) as raised:
        expr.parse(text)
    assert raised.value.position == text.index("'")


@pytest.mark.parametrize("pattern", [
    "api-.*", "[a-z]+-[0-9]{1,3}", "^v[0-9]+$", "(foo|bar)-[0-9]+", "a?b?c?", "(ab)?c", "x{2,8}", "[^/]+/[^/]+",
    "\\bword\\b", "(a|b){2}"])
def test_a_plain_pattern_is_accepted(pattern):
    expr.parse(f"profile.x matches '{pattern}'")


def test_check_pattern_is_the_one_gate():
    assert expr.check_pattern("api-.*") is None
    assert expr.check_pattern("(a+)+$")


def test_the_private_parser_the_check_relies_on_is_still_there():
    """`re._parser` is private (research D2): this test fails if a Python upgrade moves it."""
    from re import _constants, _parser
    sub = _parser.parse("(a|b)+c")
    assert sub[0][0] is _constants.MAX_REPEAT
    assert hasattr(_constants, "MAXREPEAT") and hasattr(_constants, "BRANCH")
    for name in ("GROUPREF", "GROUPREF_EXISTS", "ASSERT", "ASSERT_NOT", "SUBPATTERN", "MIN_REPEAT"):
        assert hasattr(_constants, name), name
    assert re.compile("a")


@pytest.mark.parametrize("name", ["expr.py"])
def test_the_evaluator_never_runs_code_of_the_catalog(name):
    tree = ast.parse((SRC / name).read_text())
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not called & {"eval", "exec", "compile", "__import__"}
