"""validate.py gives the same verdict as jsonschema on the spec examples (A2.6, NF2)."""

import json
import tomllib
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from peo.validate import Schema, UnsupportedSchema, ValidationError, load_schema, validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "design" / "spec" / "schemas"
GOLDEN = ROOT / "tests" / "golden" / "fx-split-stack"
PREFIX_TO_SCHEMA = [("profile", "profile"), ("selection", "selection"), ("plan", "plan"),
                    ("lock", "lock"), ("history", "history-event"), ("peo.", "peo-config"),
                    ("tool.", "tool-entry"), ("inventory", "inventory")]


def schema_for(name):
    for prefix, key in PREFIX_TO_SCHEMA:
        if name.startswith(prefix):
            return key
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
    schema = load_schema(schema_for(path.name))
    for doc in documents(path):
        expected = not list(Draft202012Validator(schema.root).iter_errors(doc))
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
    assert (validate(instance, Schema.from_dict(schema)) == []) == expected


def test_a2_6_errors_are_json_pointers_sorted_and_complete():
    schema = {"type": "object", "properties": {"b": {"type": "string"}, "a": {"type": "array", "items": {"type": "integer"}}}}
    errors = validate({"b": 1, "a": [1, "x"]}, Schema.from_dict(schema))
    assert [e.path for e in errors] == ["/a/1", "/b"]
    assert all(isinstance(e, ValidationError) and e.message for e in errors)


def test_a2_6_root_error_path_is_empty():
    assert validate(1, Schema.from_dict({"type": "string"}))[0].path == ""


def test_a2_6_schema_is_immutable_and_built_from_dict():
    schema = Schema.from_dict({"type": "null"})
    assert isinstance(schema, Schema)
    with pytest.raises(AttributeError):
        schema.root = {}


def test_a2_6_schema_keeps_a_deep_copy():
    source = {"type": "object", "properties": {"a": {"type": "integer"}}}
    schema = Schema.from_dict(source)
    source["properties"]["a"]["type"] = "string"
    source["format"] = "date"                       # outside the subset, added after the check
    assert validate({"a": 1}, schema) == []
    assert "format" not in schema.root


def test_a2_6_load_schema_returns_schema_and_rejects_unknown_name():
    assert isinstance(load_schema("profile"), Schema)
    with pytest.raises(FileNotFoundError):
        load_schema("nope")


def test_a2_6_validate_accepts_only_schema():
    with pytest.raises(TypeError):
        validate("x", {"type": "string"})


@pytest.mark.parametrize("schema,instance,code", [
    ({"type": "string"}, 1, "type"),
    ({"required": ["a"]}, {}, "required"),
    ({"enum": ["a"]}, "b", "enum"),
    ({"const": 1}, 2, "const"),
    ({"pattern": "^a$"}, "b", "pattern"),
    ({"minimum": 1}, 0, "minimum"),
    ({"minItems": 1}, [], "minItems"),
    ({"additionalProperties": False}, {"x": 1}, "additionalProperties"),
    ({"oneOf": [{"type": "string"}, {"type": "string"}]}, "a", "oneOf"),
])
def test_a2_6_errors_have_keyword_codes(schema, instance, code):
    errors = validate(instance, Schema.from_dict(schema))
    assert [e.code for e in errors] == [code]


def test_a2_6_error_paths_escape_tilde_and_slash():
    schema = Schema.from_dict({"properties": {"a/b~c": {"type": "string"}}})
    assert validate({"a/b~c": 1}, schema)[0].path == "/a~1b~0c"


def test_a2_6_validation_is_deterministic():
    schema = load_schema("profile")
    doc = {"schema": "x", "components": [1, {"a": 1}], "zzz": 1, "aaa": [None]}
    first = validate(doc, schema)
    assert first and validate(doc, schema) == first
    assert first == sorted(first)


def test_a2_6_every_shipped_schema_loads():
    names = sorted(p.name.removesuffix(".schema.json") for p in (ROOT / "src" / "peo" / "schemas").glob("*.schema.json"))
    assert len(names) == 8
    for name in names:
        assert isinstance(load_schema(name), Schema)


BAD = {"format": "date"}
UNSUPPORTED = [
    BAD, {"allOf": []}, {"$ref": "http://x/y"}, {"$ref": "#/$defs/missing"}, {"$ref": "#/properties/a"},
    {"properties": {"a": BAD}}, {"items": BAD}, {"oneOf": [{"type": "null"}, BAD]},
    {"additionalProperties": BAD}, {"items": []}, {"additionalProperties": "x"}, {"$defs": {"d": BAD}}, {"properties": {"a": {"items": {"oneOf": [BAD]}}}},
]


@pytest.mark.parametrize("schema", UNSUPPORTED, ids=lambda s: json.dumps(s)[:50])
def test_a2_6_unsupported_at_construction(schema):
    with pytest.raises(UnsupportedSchema):
        Schema.from_dict(schema)


@pytest.mark.parametrize("schema", [[], "x", None, {"properties": {"a": []}}])
def test_a2_6_unsupported_non_object_schema(schema):
    with pytest.raises(UnsupportedSchema):
        Schema.from_dict(schema)


def test_a2_6_annotations_and_resolvable_ref_are_accepted():
    Schema.from_dict({"$schema": "s", "$id": "i", "title": "t", "description": "d",
                      "$defs": {"d": {"type": "null"}}, "properties": {"a": {"$ref": "#/$defs/d"}}})


MALFORMED = [
    {"type": "foo"}, {"type": []}, {"type": ["string", "foo"]}, {"type": 1},
    {"pattern": "("}, {"pattern": 1},
    {"required": "a"}, {"required": [1]},
    {"properties": []}, {"properties": {"a": 1}}, {"$defs": []},
    {"oneOf": []}, {"oneOf": {}}, {"enum": "a"},
    {"minimum": "1"}, {"minimum": True}, {"minItems": -1}, {"minItems": 1.5}, {"minItems": True},
    {"$ref": 1}, {"$ref": "#/$defs/a"},
    {"$defs": {"a": {"$ref": "#/$defs/a"}}, "$ref": "#/$defs/a"},
    {"$defs": {"a": {"$ref": "#/$defs/b"}, "b": {"$ref": "#/$defs/a"}}, "$ref": "#/$defs/a"},
    {"$defs": {"a": {"oneOf": [{"$ref": "#/$defs/a"}]}}, "$ref": "#/$defs/a"},
]


@pytest.mark.parametrize("schema", MALFORMED, ids=lambda s: json.dumps(s)[:60])
def test_a2_6_malformed_keyword_values_rejected_at_construction(schema):
    with pytest.raises(UnsupportedSchema):
        Schema.from_dict(schema)


def test_a2_6_valid_values_still_accepted():
    Schema.from_dict({"type": ["string", "null"], "pattern": "^a$", "required": [], "minimum": 0.5,
                      "minItems": 0, "enum": [1], "additionalProperties": True,
                      "oneOf": [{"type": "null"}]})


def test_a2_6_recursion_through_properties_is_allowed():
    tree = Schema.from_dict({"$defs": {"n": {"type": "object", "properties": {"kid": {"$ref": "#/$defs/n"}}}},
                             "$ref": "#/$defs/n"})
    assert validate({"kid": {"kid": {}}}, tree) == []
    assert validate({"kid": {"kid": 1}}, tree)
