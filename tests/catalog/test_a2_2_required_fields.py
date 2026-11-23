"""A2.2: a tool entry without surface, surface.data_path, surface.fail_mode or notes.review_by is rejected."""

import re
from datetime import date

import pytest

from peo.catalog import validate

from .conftest import demo_tool

TODAY = date(2026, 11, 18)
CUTS = {
    "surface": (r"\[surface\].*?(?=\n\[cost\])", "surface"),
    "surface.data_path": (r"^data_path.*\n", "data_path"),
    "surface.fail_mode": (r"^fail_mode.*\n", "fail_mode"),
    "notes.review_by": (r"^review_by.*\n", "review_by"),
}


def without(pattern: str) -> str:
    text, n = re.subn(pattern, "", demo_tool(), flags=re.M | re.S if "surface" in pattern else re.M)
    assert n == 1, pattern
    return text


def test_a2_2_the_demo_catalog_is_valid(make_catalog):
    report = validate(make_catalog(), today=TODAY)
    assert report.errors == [] and report.counts["entries"] == 1


@pytest.mark.parametrize("name", CUTS)
def test_a2_2_missing_field_is_rejected_with_file_and_field(make_catalog, name):
    pattern, field = CUTS[name]
    report = validate(make_catalog(tools={"demo": without(pattern)}), today=TODAY)
    assert report.errors, name
    assert all(e.file == "tools/cli/demo.toml" for e in report.errors)
    assert any(field in f"{e.location} {e.message}" for e in report.errors)
