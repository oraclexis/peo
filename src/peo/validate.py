"""Validator for the JSON Schema subset PEO's schemas use (spec 10, NF2). Standard library only."""

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, NamedTuple


class ValidationError(NamedTuple):
    path: str  # JSON Pointer to the offending value; "" is the root
    code: str  # the violated keyword
    message: str


class UnsupportedSchema(Exception):
    """The schema uses a keyword or reference outside the supported subset."""


_ANNOTATIONS = {"$schema", "$id", "title", "description", "$defs"}
_SUPPORTED = {"type", "required", "properties", "additionalProperties", "items", "enum", "const",
              "pattern", "minimum", "minItems", "$ref", "oneOf"}


@dataclass(frozen=True)
class Schema:
    """A schema known to stay inside the supported subset."""

    root: dict

    @classmethod
    def from_dict(cls, d: dict) -> "Schema":
        _verify(d, d)
        return cls(d)


_TYPES = {"string", "number", "integer", "boolean", "object", "array", "null"}


def _bad(keyword: str, why: str) -> UnsupportedSchema:
    return UnsupportedSchema(f"invalid value for {keyword}: {why}")


def _verify_values(schema: dict) -> None:
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not names or not all(isinstance(n, str) and n in _TYPES for n in names):
            raise _bad("type", "expected a type name or a non-empty list of type names")
    if "pattern" in schema:
        try:
            re.compile(schema["pattern"])
        except (re.error, TypeError) as e:
            raise _bad("pattern", f"not a valid regular expression ({e})") from e
    required = schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(k, str) for k in required):
        raise _bad("required", "expected a list of strings")
    for key in ("properties", "$defs"):
        if not isinstance(schema.get(key, {}), dict):
            raise _bad(key, "expected an object")
    if "oneOf" in schema and (not isinstance(schema["oneOf"], list) or not schema["oneOf"]):
        raise _bad("oneOf", "expected a non-empty list")
    if "enum" in schema and not isinstance(schema["enum"], list):
        raise _bad("enum", "expected a list")
    if "minimum" in schema and not _is_number(schema["minimum"]):
        raise _bad("minimum", "expected a number")
    if "minItems" in schema:
        n = schema["minItems"]
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise _bad("minItems", "expected an integer >= 0")
    if "$ref" in schema and not isinstance(schema["$ref"], str):
        raise _bad("$ref", "expected a string")


def _forbid_ref_cycle(schema: dict, root: dict, seen: frozenset = frozenset()) -> None:
    """A $ref/oneOf chain that returns to itself never consumes the instance: reject it."""
    if id(schema) in seen:
        raise UnsupportedSchema("circular $ref that does not descend into the instance")
    seen = seen | {id(schema)}
    nexts = list(schema.get("oneOf", []))
    if "$ref" in schema:
        nexts.append(_resolve(schema["$ref"], root))
    for nxt in nexts:
        _forbid_ref_cycle(nxt, root, seen)


def _verify(schema: Any, root: dict) -> None:
    """Reject, before any validation, whatever falls outside the supported subset."""
    if not isinstance(schema, dict):
        raise UnsupportedSchema("a schema must be an object")
    unknown = set(schema) - _SUPPORTED - _ANNOTATIONS
    if unknown:
        raise UnsupportedSchema(f"unsupported keyword(s): {', '.join(sorted(unknown))}")
    _verify_values(schema)
    if "$ref" in schema:
        _resolve(schema["$ref"], root)
    subschemas = [*schema.get("properties", {}).values(), *schema.get("$defs", {}).values(),
                  *schema.get("oneOf", [])]
    for key in ("items", "additionalProperties"):
        if key in schema and not isinstance(schema[key], bool):
            subschemas.append(schema[key])
    for sub in subschemas:
        _verify(sub, root)
    _forbid_ref_cycle(schema, root)


def load_schema(name: str) -> Schema:
    """Load a shipped schema from src/peo/schemas/<name>.schema.json."""
    text = (files("peo") / "schemas" / f"{name}.schema.json").read_text()
    return Schema.from_dict(json.loads(text))


def validate(instance: Any, schema: Schema) -> list[ValidationError]:
    """Return all errors, sorted; an empty list means the instance is valid."""
    if not isinstance(schema, Schema):
        raise TypeError("schema must be a Schema; use Schema.from_dict or load_schema")
    errors: list[ValidationError] = []
    _check(instance, schema.root, schema.root, "", errors)
    return sorted(errors)


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _type_ok(v: Any, name: str) -> bool:
    if name == "integer":
        return _is_number(v) and (isinstance(v, int) or v.is_integer())
    return {"number": _is_number, "string": lambda x: isinstance(x, str),
            "object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
            "boolean": lambda x: isinstance(x, bool), "null": lambda x: x is None}[name](v)


def _eq(a: Any, b: Any) -> bool:
    """JSON equality: True is not 1."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_eq(a[k], b[k]) for k in a)
    return a == b


def _resolve(ref: str, root: dict) -> dict:
    prefix = "#/$defs/"
    defs = root.get("$defs", {})
    if not ref.startswith(prefix) or ref[len(prefix):] not in defs:
        raise UnsupportedSchema(f"unsupported or unresolved $ref: {ref}")
    return defs[ref[len(prefix):]]


def _child(path: str, key: Any) -> str:
    return f"{path}/{str(key).replace('~', '~0').replace('/', '~1')}"


def _check(inst: Any, schema: Any, root: dict, path: str, errors: list) -> None:

    def err(code: str, msg: str, p: str = path) -> None:
        errors.append(ValidationError(p, code, msg))

    if "$ref" in schema:
        _check(inst, _resolve(schema["$ref"], root), root, path, errors)
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(inst, n) for n in names):
            err("type", f"expected type {' or '.join(names)}")
    if "enum" in schema and not any(_eq(inst, v) for v in schema["enum"]):
        err("enum", f"not one of {schema['enum']!r}")
    if "const" in schema and not _eq(inst, schema["const"]):
        err("const", f"expected {schema['const']!r}")
    if "pattern" in schema and isinstance(inst, str) and not re.search(schema["pattern"], inst):
        err("pattern", f"does not match {schema['pattern']!r}")
    if "minimum" in schema and _is_number(inst) and inst < schema["minimum"]:
        err("minimum", f"less than minimum {schema['minimum']}")
    if "minItems" in schema and isinstance(inst, list) and len(inst) < schema["minItems"]:
        err("minItems", f"fewer than {schema['minItems']} items")
    if "oneOf" in schema:
        matches = 0
        for alt in schema["oneOf"]:
            sub: list = []
            _check(inst, alt, root, path, sub)
            matches += not sub
        if matches != 1:
            err("oneOf", f"matches {matches} oneOf alternatives, expected exactly 1")
    if isinstance(inst, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in inst:
                err("required", f"missing required property {key!r}")
        for key, value in inst.items():
            if key in props:
                _check(value, props[key], root, _child(path, key), errors)
            elif "additionalProperties" in schema:
                extra = schema["additionalProperties"]
                if extra is False:
                    err("additionalProperties", f"additional property {key!r} not allowed",
                        _child(path, key))
                elif extra is not True:
                    _check(value, extra, root, _child(path, key), errors)
    if isinstance(inst, list) and "items" in schema:
        for i, item in enumerate(inst):
            _check(item, schema["items"], root, _child(path, i), errors)
