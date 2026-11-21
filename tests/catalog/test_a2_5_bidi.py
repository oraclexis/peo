"""A2.5: a bidirectional control character in any catalog file makes the catalog invalid (13 section 1)."""

from datetime import date

import pytest

from peo.catalog import validate

from .conftest import REQUIREMENTS, demo_tool

TODAY = date(2026, 11, 18)
CODE_POINTS = [0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)]


def label(cp):
    return f"U+{cp:04X}"


@pytest.mark.parametrize("cp", CODE_POINTS, ids=label)
def test_a2_5_a_code_point_in_a_tool_entry_is_rejected(make_catalog, cp):
    text = demo_tool().replace('name        = "Serena"', f'name        = "Ser{chr(cp)}ena"')
    report = validate(make_catalog(tools={"demo": text}), today=TODAY)
    assert [e.file for e in report.errors] == ["tools/cli/demo.toml"]
    assert label(cp) in report.errors[0].message


@pytest.mark.parametrize("cp", CODE_POINTS, ids=label)
def test_a2_5_a_code_point_in_requirements_is_rejected(make_catalog, cp):
    report = validate(make_catalog(requirements=REQUIREMENTS + f"# a{chr(cp)}b\n"), today=TODAY)
    assert [e.file for e in report.errors] == ["requirements.toml"]
    assert label(cp) in report.errors[0].message


def test_a2_5_the_same_file_without_the_character_is_accepted(make_catalog):
    assert validate(make_catalog(), today=TODAY).errors == []


def test_a2_5_the_error_is_given_even_when_the_toml_is_also_invalid(make_catalog):
    report = validate(make_catalog(tools={"demo": 'id = "x‮" ='}), today=TODAY)
    assert label(0x202E) in report.errors[0].message and len(report.errors) == 1


def test_a2_5_other_unicode_is_fine(make_catalog):
    text = demo_tool().replace('name        = "Serena"', 'name        = "Sérena é中"')
    assert validate(make_catalog(tools={"demo": text}), today=TODAY).errors == []


def test_a2_5_opaque_tables_are_scanned_too(make_catalog):
    root = make_catalog(extra={"recipes/r.toml": "# ⁦\n"})
    assert [e.file for e in validate(root, today=TODAY).errors] == ["recipes/r.toml"]
