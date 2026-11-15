"""A3.16: conformance tables embedded in the package (spec 14 §3.5)."""

import importlib.resources
import json
from pathlib import Path

import pytest

from peo.validate import load_schema, validate

SPEC = Path(__file__).resolve().parents[1] / "docs" / "design" / "spec" / "conformance"
TABLES = sorted(p.name for p in SPEC.glob("claude-rules*.json"))


def embedded(name: str) -> bytes:
    return importlib.resources.files("peo").joinpath("conformance", name).read_bytes()


def test_a3_16_spec_has_the_darwin_table():
    assert "claude-rules.json" in TABLES


@pytest.mark.parametrize("name", TABLES)
def test_a3_16_embedded_table_is_byte_identical(name):
    assert embedded(name) == (SPEC / name).read_bytes()


def test_a3_16_no_embedded_table_without_spec_copy():
    package = importlib.resources.files("peo").joinpath("conformance")
    assert sorted(p.name for p in package.iterdir() if p.name.endswith(".json")) == TABLES


@pytest.mark.parametrize("name", TABLES)
def test_conformance_tables_are_valid(name):
    assert validate(json.loads(embedded(name)), load_schema("claude-rules")) == []
