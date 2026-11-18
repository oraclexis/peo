"""A2.3: an expression outside the `when` grammar makes the catalog invalid, wherever it appears."""

import ast
import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

from peo.catalog import validate

from .conftest import CAPABILITIES, demo_tool

TODAY = date(2026, 11, 18)
SRC = Path(__file__).resolve().parents[2] / "src" / "peo"
GOOD = "profile.metrics.loc_total > 50000 or answers['q.refactoring'] == true"
BAD = "profile.metrics.loc_total >"


def rule(**fields):
    body = "\n".join(f"{k} = {json.dumps(v)}" for k, v in fields.items())
    return f'[[rules]]\nid = "r"\n{body}\nrequire = {{ capability = "nav.symbols", strength = "soft" }}\n'


def question(**fields):
    body = "\n".join(f"{k} = {json.dumps(v)}" for k, v in fields.items())
    return ('[[questions]]\nid = "q.x"\nround = 1\nkind = "confirm"\nfeeds = ["project.mission"]\n'
            f'text = "t"\n{body}\n')


def text_of(report):
    return " | ".join(f"{e.file} {e.location} {e.message}" for e in report.errors)


def test_a2_3_an_invalid_expression_in_a_tool_entry_is_rejected_with_the_expression(make_catalog):
    entry = demo_tool().replace('"profile.metrics.loc_total > 50000"', f'"{BAD}"')
    text = text_of(validate(make_catalog(tools={"demo": entry}), today=TODAY))
    assert "tools/cli/demo.toml" in text and "selection" in text and BAD in text


@pytest.mark.parametrize("key", ["all", "not"])
def test_a2_3_every_selection_branch_is_checked(make_catalog, key):
    entry = re.sub(r"^when = \{.*$", f'when = {{ {key} = ["{BAD}"] }}', demo_tool(), flags=re.M)
    assert BAD in text_of(validate(make_catalog(tools={"demo": entry}), today=TODAY))


@pytest.mark.parametrize("field", ["when", "for_each"])
def test_a2_3_an_invalid_expression_in_a_rule_is_rejected(make_catalog, field):
    text = text_of(validate(make_catalog(requirements=rule(**{field: BAD})), today=TODAY))
    assert "requirements.toml" in text and field in text and BAD in text


@pytest.mark.parametrize("field", ["ask_if", "recommend_if"])
def test_a2_3_an_invalid_expression_in_a_question_is_rejected(make_catalog, field):
    body = question(ask_if=GOOD) if field == "recommend_if" else question(ask_if=BAD)
    if field == "recommend_if":
        body += f'[[questions.options]]\nvalue = "a"\nlabel = "A"\nrecommend_if = "{BAD}"\n'
    extra = {"questions.toml": body}
    text = text_of(validate(make_catalog(extra=extra), today=TODAY))
    assert "questions.toml" in text and BAD in text


def test_a2_3_the_examples_of_spec_13_pass(make_catalog):
    reqs = (rule(when=GOOD) + rule(when="any(profile.components, 'php' in it.languages)").replace('"r"', '"r2"')
            + rule(when="not profile.signals.design_rules_in_instructions.value").replace('"r"', '"r3"'))
    assert validate(make_catalog(requirements=reqs), today=TODAY).errors == []


def test_a2_3_a_pattern_over_200_characters_is_rejected(make_catalog):
    long = "profile.x matches '" + "a" * 201 + "'"
    assert validate(make_catalog(requirements=rule(when=long)), today=TODAY).errors


def test_a2_3_the_expression_in_a_message_is_cut_at_200_characters(make_catalog):
    report = validate(make_catalog(requirements=rule(when="profile.x == '" + "b" * 500)), today=TODAY)
    assert report.errors and all(len(e.message) < 400 for e in report.errors)


@pytest.mark.parametrize("name", ["catalog.py", "expr.py"])
def test_a2_3_no_dynamic_code_no_process_no_network(name):
    tree = ast.parse((SRC / name).read_text())
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not called & {"eval", "exec", "compile", "__import__"}
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert imported <= set(sys.stdlib_module_names) | {"peo"}
    assert not imported & {"subprocess", "socket", "urllib", "http", "ssl"}
    assert "shell=True" not in (SRC / name).read_text()


def test_a2_3_the_demo_capabilities_are_what_the_helpers_assume():
    assert "nav.symbols" in CAPABILITIES
