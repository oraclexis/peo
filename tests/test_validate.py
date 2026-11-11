"""validate.py gives the same verdict as jsonschema on the spec examples (A2.6, NF2)."""

import json
import tomllib
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from peo.validate import UnsupportedSchema, ValidationError, validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "design" / "spec" / "schemas"
GOLDEN = ROOT / "tests" / "golden" / "fx-epure"
PREFIX_TO_SCHEMA = [("profile", "profile"), ("selection", "selection"), ("plan", "plan"),
                    ("lock", "lock"), ("history", "history-event"), ("peo.", "peo-config"),
                    ("tool.", "tool-entry")]


def schema_for(name):
    for prefix, key in PREFIX_TO_SCHEMA:
        if name.startswith(prefix):
            return json.loads((SPEC / f"{key}.schema.json").read_text())
    raise AssertionError(name)


def documents(path):
    if path.suffix == ".toml":
        return [tomllib.loads(path.read_text())]
    if path.suffix == ".ndjson":
        return [json.loads(line) for line in path.read_text().splitlines() if line]
    return [json.loads(path.read_text())]


FILES = ([(p, True) for p in sorted((SPEC / "examples").iterdir())]
         + [(p, False) for p in sorted((SPEC / "invalid").iterdir())]
         + [(p, True) for p in sorted(GOLDEN.glob("*.json"))])


@pytest.mark.parametrize("path,valid", FILES, ids=lambda x: x.name if hasattr(x, "name") else "")
def test_a2_6_same_verdict_as_jsonschema_on_spec_files(path, valid):
    schema = schema_for(path.name)
    for doc in documents(path):
        expected = not list(Draft202012Validator(schema).iter_errors(doc))
        assert (validate(doc, schema) == []) == expected
    assert all(validate(d, schema) == [] for d in documents(path)) == valid


S_OBJ = {"type": "object", "required": ["a"], "additionalProperties": False,
         "properties": {"a": {"type": "integer", "minimum": 0}}}
CASES = [
    # (schema, instance)
    (S_OBJ, {"a": 1}), (S_OBJ, {}), (S_OBJ, {"a": -1}), (S_OBJ, {"a": 1, "b": 2}),
    (S_OBJ, {"a": True}), (S_OBJ, {"a": 1.0}), (S_OBJ, {"a": 1.5}), (S_OBJ, []),
    ({"type": "number"}, True), ({"type": "number"}, 2), ({"type": "integer"}, 2.0),
    ({"type": ["string", "null"]}, None), ({"type": ["string", "null"]}, 3),
    ({"type": "object", "additionalProperties": {"type": "string"}}, {"x": "y"}),
    ({"type": "object", "additionalProperties": {"type": "string"}}, {"x": 1}),
    ({"type": "array", "items": {"type": "string"}, "minItems": 1}, ["a"]),
    ({"type": "array", "items": {"type": "string"}, "minItems": 1}, []),
    ({"type": "array", "items": {"type": "string"}, "minItems": 1}, ["a", 1]),
    ({"enum": ["a", "b"]}, "a"), ({"enum": ["a", "b"]}, "c"), ({"enum": [1]}, True),
    ({"const": 1}, 1), ({"const": 1}, True), ({"const": "x"}, "y"),
    ({"type": "string", "pattern": "^a[0-9]+$"}, "a12"), ({"type": "string", "pattern": "^a[0-9]+$"}, "b1"),
    ({"pattern": "a"}, 5),
    ({"minimum": 3}, "x"), ({"minItems": 2}, "x"),
    ({"oneOf": [{"type": "string"}, {"type": "null"}]}, None),
    ({"oneOf": [{"type": "string"}, {"type": "null"}]}, 1),
    ({"oneOf": [{"type": "integer"}, {"type": "number"}]}, 1),
    ({"$defs": {"n": {"type": "integer"}}, "type": "array", "items": {"$ref": "#/$defs/n"}}, [1, 2]),
    ({"$defs": {"n": {"type": "integer"}}, "type": "array", "items": {"$ref": "#/$defs/n"}}, [1, "x"]),
    ({"$schema": "x", "$id": "y", "title": "t", "description": "d", "type": "null"}, None),
]


@pytest.mark.parametrize("schema,instance", CASES)
def test_a2_6_same_verdict_as_jsonschema_per_keyword(schema, instance):
    expected = not list(Draft202012Validator(schema).iter_errors(instance))
    assert (validate(instance, schema) == []) == expected


def test_errors_are_json_pointers_sorted_and_complete():
    schema = {"type": "object", "properties": {"b": {"type": "string"}, "a": {"type": "array", "items": {"type": "integer"}}}}
    errors = validate({"b": 1, "a": [1, "x"]}, schema)
    assert [e.path for e in errors] == ["/a/1", "/b"]
    assert all(isinstance(e, ValidationError) and e.message for e in errors)


def test_root_error_path_is_empty():
    assert validate(1, {"type": "string"})[0].path == ""


@pytest.mark.parametrize("schema", [{"format": "date"}, {"allOf": []}, {"$ref": "http://x/y"},
                                    {"$ref": "#/$defs/missing"}])
def test_unsupported_schema_raises(schema):
    with pytest.raises(UnsupportedSchema):
        validate("x", schema)
