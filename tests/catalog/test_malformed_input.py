"""Malformed but valid TOML must give catalog errors, never a traceback (found by the PR review)."""

import os
from datetime import date

import pytest

from peo.catalog import validate
from peo.expr import ExprError, parse

from .conftest import REQUIREMENTS, demo_tool

TODAY = date(2026, 11, 18)


def test_a2_3_a_huge_integer_literal_is_an_expression_error():
    with pytest.raises(ExprError):
        parse("profile.x == " + "9" * 5000)


def test_a2_3_list_nesting_is_capped_like_parentheses():
    with pytest.raises(ExprError):
        parse("profile.x in " + "[" * 5000 + "]" * 5000)


@pytest.mark.parametrize("requirements", [
    '[[rules]]\nid = "r"\nrequire = { capability = ["nav.symbols"], strength = "soft" }\n',
    '[[rules]]\nid = "r"\nrequire = { capability = "nav.symbols", strength = ["soft"] }\n',
    "rules = [1]\n", "rules = 3\n", "[rules]\na = 1\n",
])
def test_malformed_rules_are_errors(make_catalog, requirements):
    report = validate(make_catalog(requirements=requirements), today=TODAY)
    assert report.errors and all(e.file == "requirements.toml" for e in report.errors)


@pytest.mark.parametrize("text", ["questions = [1]\n", "questions = 3\n",
                                  '[[questions]]\nid = "q"\noptions = 3\n'])
def test_malformed_questions_are_errors(make_catalog, text):
    report = validate(make_catalog(extra={"questions.toml": text}), today=TODAY)
    assert report.errors and all(e.file == "questions.toml" for e in report.errors)


def test_malformed_capabilities_are_errors(make_catalog):
    assert validate(make_catalog(capabilities="capabilities = [1]\n"), today=TODAY).errors


@pytest.mark.parametrize("bad", ['relations = "x"', 'prerequisites = ["a"]'])
def test_an_entry_failing_the_schema_does_not_reach_the_reference_check(make_catalog, bad):
    entry = demo_tool().replace("[surface]", f"{bad}\n[surface]", 1) if bad.startswith("rel") \
        else bad + "\n" + demo_tool()
    report = validate(make_catalog(tools={"demo": entry}), today=TODAY)
    assert report.errors and all(e.code in {"schema", "toml"} for e in report.errors)


def test_a2_5_an_escaped_control_character_is_caught_after_decoding(make_catalog):
    entry = demo_tool().replace('name        = "Serena"', 'name        = "Ser\\u202Eena"')
    report = validate(make_catalog(tools={"demo": entry}), today=TODAY)
    assert [e.file for e in report.errors] == ["tools/cli/demo.toml"]
    assert "U+202E" in report.errors[0].message


def test_a2_5_an_escaped_control_character_in_an_expression_is_caught(make_catalog):
    rule = REQUIREMENTS.replace("profile.metrics", "\\u2066profile.metrics")
    assert any("U+2066" in e.message for e in validate(make_catalog(requirements=rule), today=TODAY).errors)


@pytest.mark.parametrize("read", ["answers['x.y'].value", "answers['x.y']", "answers.x"])
def test_a2_4_an_answer_read_with_a_longer_path_still_counts(make_catalog, read):
    feed = "x" if read == "answers.x" else "x.y"
    rule = ('[[rules]]\nid = "r"\n' f'when = "{read} == true"\n'
            'require = { capability = "nav.symbols", strength = "soft" }\n')
    question = ('[[questions]]\nid = "q.x"\nround = 1\nkind = "confirm"\ntext = "t"\n'
                f'feeds = ["{feed}"]\n')
    assert validate(make_catalog(requirements=rule, extra={"questions.toml": question}),
                    today=TODAY).errors == []


def test_a_symbolic_questions_file_is_ignored(make_catalog, tmp_path):
    root = make_catalog()
    outside = tmp_path / "outside.toml"
    outside.write_text('[[questions]]\nid = "q"\n')
    os.symlink(outside, root / "questions.toml")
    report = validate(root, today=TODAY)
    assert report.errors == [] and report.counts["questions"] == 0


@pytest.mark.parametrize("text", ["a = " + "[" * 200000 + "]" * 200000 + "\n",
                                  "x = " + "{a=" * 100000 + "1" + "}" * 100000 + "\n"])
def test_a_deeply_nested_toml_file_is_an_error_not_a_crash(make_catalog, text):
    report = validate(make_catalog(extra={"tools/cli/deep.toml": text}), today=TODAY)
    assert [e.file for e in report.errors] == ["tools/cli/deep.toml"]
    assert "nested" in report.errors[0].message


def test_an_unreadable_capabilities_file_gives_one_error_not_a_cascade(make_catalog):
    report = validate(make_catalog(capabilities="id = \n"), today=TODAY)
    assert [e.file for e in report.errors] == ["capabilities.toml"]


def test_a_question_does_not_satisfy_s5_by_reading_its_own_feed(make_catalog):
    text = ('[[questions]]\nid = "q.x"\nround = 1\nkind = "confirm"\ntext = "t"\n'
            'feeds = ["x.y"]\nask_if = "answers[\'x.y\'] == true"\n')
    report = validate(make_catalog(extra={"questions.toml": text}), today=TODAY)
    assert any(e.code == "unconsumed" for e in report.errors)


def test_a_question_option_does_not_satisfy_s5_either(make_catalog):
    text = ('[[questions]]\nid = "q.x"\nround = 1\nkind = "choice"\ntext = "t"\nfeeds = ["x.y"]\n'
            '[[questions.options]]\nvalue = "a"\nlabel = "A"\nrecommend_if = "answers[\'x.y\'] == 1"\n')
    report = validate(make_catalog(extra={"questions.toml": text}), today=TODAY)
    assert any(e.code == "unconsumed" for e in report.errors)


@pytest.mark.parametrize("where", ["tools/cli/linked.toml", "recipes/linked.toml", "questions.toml"])
def test_an_ignored_symbolic_link_is_a_warning(make_catalog, tmp_path, where):
    root = make_catalog(extra={"recipes/ok.toml": "a = 1\n"})
    outside = tmp_path / "outside.toml"
    outside.write_text("a = 1\n")
    os.symlink(outside, root / where)
    report = validate(root, today=TODAY)
    assert report.errors == []
    assert [(w.code, w.file) for w in report.warnings] == [("W_SYMLINK_IGNORED", where)]
