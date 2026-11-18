"""A2.4: a question whose `feeds` field nothing reads is rejected (rule S-5, spec 13 section 7.1)."""

import json
from datetime import date
from pathlib import Path

import pytest

from peo.catalog import PEO_TOML_CONSUMED, validate

TODAY = date(2026, 11, 18)
SCHEMA = Path(__file__).resolve().parents[2] / "src" / "peo" / "schemas" / "peo-config.schema.json"


def question(feeds='["x.y"]', **fields):
    values = {"id": '"q.x"', "round": "1", "kind": '"confirm"', "text": '"t"', **fields}
    body = "\n".join(f"{k} = {v}" for k, v in values.items())
    return f"[[questions]]\n{body}\nfeeds = {feeds}\n"


def rule_reading(path):
    return ('[[rules]]\nid = "r"\n' + f'when = "{path} == true"\n'
            'require = { capability = "nav.symbols", strength = "soft" }\n')


def run(make_catalog, text, **kw):
    return validate(make_catalog(extra={"questions.toml": text}, **kw), today=TODAY)


def test_a2_4_a_feed_that_nothing_reads_is_rejected_naming_question_and_field(make_catalog):
    report = run(make_catalog, question())
    assert [e.file for e in report.errors] == ["questions.toml"]
    assert "q.x" in report.errors[0].message and "x.y" in report.errors[0].message


def test_a2_4_a_feed_read_by_a_catalog_expression_is_accepted(make_catalog):
    assert run(make_catalog, question(), requirements=rule_reading("answers['x.y']")).errors == []


def test_a2_4_a_feed_read_by_an_opaque_recipe_is_accepted(make_catalog):
    recipe = '[bugfix]\nname = "x"\n[[bugfix.steps]]\nwhen = "answers[\'x.y\'] == true"\n'
    root = make_catalog(extra={"questions.toml": question(), "recipes/bugfix.toml": recipe})
    report = validate(root, today=TODAY)
    assert report.errors == [] and report.counts["opaque"] == 1


@pytest.mark.parametrize("key", ["when", "ask_if", "recommend_if", "for_each"])
def test_a2_4_an_expression_key_at_any_depth_of_an_opaque_table_counts(make_catalog, key):
    recipe = f'[a.b.c]\n{key} = "answers[\'x.y\'] == true"\n'
    root = make_catalog(extra={"questions.toml": question(), "backbones/b.toml": recipe})
    assert validate(root, today=TODAY).errors == []


def test_a2_4_an_invalid_expression_in_an_opaque_table_is_rejected(make_catalog):
    root = make_catalog(extra={"recipes/r.toml": '[a]\nwhen = "profile.x >"\n'})
    report = validate(root, today=TODAY)
    assert [e.file for e in report.errors] == ["recipes/r.toml"]


@pytest.mark.parametrize("field", sorted(PEO_TOML_CONSUMED))
def test_a2_4_a_consumed_peo_toml_field_needs_no_expression(make_catalog, field):
    assert run(make_catalog, question(feeds=json.dumps([field]))).errors == []


def test_a2_4_the_consumed_fields_exist_in_the_peo_toml_schema():
    schema = json.loads(SCHEMA.read_text())
    for dotted in PEO_TOML_CONSUMED:
        node = schema
        for part in dotted.split("."):
            if "properties" in node:        # a map such as `commands` has additionalProperties instead
                assert part in node["properties"], dotted
                node = node["properties"][part]
            else:
                assert "additionalProperties" in node, dotted
                node = node["additionalProperties"]


@pytest.mark.parametrize("fields, needle", [
    ({"round": "0"}, "round"), ({"round": '"1"'}, "round"), ({"kind": '"menu"'}, "kind"),
    ({"id": "1"}, "id"),
])
def test_a2_4_the_shape_of_a_question_is_checked(make_catalog, fields, needle):
    report = run(make_catalog, question(feeds='["project.mission"]', **fields))
    assert any(needle in e.message for e in report.errors)


def test_a2_4_feeds_must_be_a_non_empty_list(make_catalog):
    assert any("feeds" in e.message for e in run(make_catalog, question(feeds="[]")).errors)


def test_a2_4_at_most_four_options(make_catalog):
    options = "".join(f'[[questions.options]]\nvalue = "v{i}"\nlabel = "L"\n' for i in range(5))
    report = run(make_catalog, question(feeds='["project.mission"]') + options)
    assert any("options" in e.message for e in report.errors)


def test_a2_4_a_question_id_must_be_unique(make_catalog):
    text = question(feeds='["project.mission"]') * 2
    assert any("duplicate" in e.message for e in run(make_catalog, text).errors)


def test_a2_4_questions_are_counted(make_catalog):
    assert run(make_catalog, question(feeds='["project.mission"]')).counts["questions"] == 1
