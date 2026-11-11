"""Schemas shipped in the package match the spec and validate the spec examples (A2.6, A8.3)."""

import json
import tomllib
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "design" / "spec" / "schemas"
PKG = ROOT / "src" / "peo" / "schemas"

PREFIX_TO_SCHEMA = [("profile", "profile"), ("selection", "selection"), ("plan", "plan"),
                    ("lock", "lock"), ("history", "history-event"), ("peo.", "peo-config"),
                    ("tool.", "tool-entry")]


def schema_for(name: str) -> dict:
    for prefix, key in PREFIX_TO_SCHEMA:
        if name.startswith(prefix):
            return json.loads((PKG / f"{key}.schema.json").read_text())
    raise AssertionError(f"no schema for {name}")


def documents(path: Path) -> list:
    if path.suffix == ".toml":
        return [tomllib.loads(path.read_text())]
    if path.suffix == ".ndjson":
        return [json.loads(line) for line in path.read_text().splitlines() if line]
    return [json.loads(path.read_text())]


def test_package_schemas_are_the_spec_schemas():
    spec = {p.name: p.read_text() for p in SPEC.glob("*.schema.json")}
    pkg = {p.name: p.read_text() for p in PKG.glob("*.schema.json")}
    assert spec == pkg, "copy docs/design/spec/schemas/*.schema.json to src/peo/schemas/"


@pytest.mark.parametrize("path", sorted((SPEC / "examples").iterdir()), ids=lambda p: p.name)
def test_examples_are_valid(path):
    validator = Draft202012Validator(schema_for(path.name))
    errors = [e.message for doc in documents(path) for e in validator.iter_errors(doc)]
    assert errors == []


@pytest.mark.parametrize("path", sorted((SPEC / "invalid").iterdir()), ids=lambda p: p.name)
def test_counter_examples_are_rejected(path):
    validator = Draft202012Validator(schema_for(path.name))
    assert any(True for doc in documents(path) for _ in validator.iter_errors(doc))


def test_golden_files_are_valid():
    golden = ROOT / "tests" / "golden" / "fx-epure"
    for name, schema in (("profile.json", "profile"), ("selection.json", "selection")):
        validator = Draft202012Validator(json.loads((PKG / f"{schema}.schema.json").read_text()))
        assert list(validator.iter_errors(json.loads((golden / name).read_text()))) == []
