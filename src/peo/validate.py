"""Validator for the JSON Schema subset PEO's schemas use (spec 10, NF2). Standard library only."""

import re
from typing import Any, NamedTuple


class ValidationError(NamedTuple):
    path: str  # JSON Pointer to the offending value; "" is the root
    message: str


class UnsupportedSchema(Exception):
    """The schema uses a keyword or reference outside the supported subset."""


_ANNOTATIONS = {"$schema", "$id", "title", "description", "$defs"}
_SUPPORTED = {"type", "required", "properties", "additionalProperties", "items", "enum", "const",
              "pattern", "minimum", "minItems", "$ref", "oneOf"}


def validate(instance: Any, schema: dict) -> list[ValidationError]:
    """Return all errors, sorted; an empty list means the instance is valid."""
    errors: list[ValidationError] = []
    _check(instance, schema, schema, "", errors)
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
    if not isinstance(schema, dict):
        raise UnsupportedSchema("a schema must be an object")
    unknown = set(schema) - _SUPPORTED - _ANNOTATIONS
    if unknown:
        raise UnsupportedSchema(f"unsupported keyword(s): {', '.join(sorted(unknown))}")

    def err(msg: str, p: str = path) -> None:
        errors.append(ValidationError(p, msg))

    if "$ref" in schema:
        _check(inst, _resolve(schema["$ref"], root), root, path, errors)
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(inst, n) for n in names):
            err(f"expected type {' or '.join(names)}")
    if "enum" in schema and not any(_eq(inst, v) for v in schema["enum"]):
        err(f"not one of {schema['enum']!r}")
    if "const" in schema and not _eq(inst, schema["const"]):
        err(f"expected {schema['const']!r}")
    if "pattern" in schema and isinstance(inst, str) and not re.search(schema["pattern"], inst):
        err(f"does not match {schema['pattern']!r}")
    if "minimum" in schema and _is_number(inst) and inst < schema["minimum"]:
        err(f"less than minimum {schema['minimum']}")
    if "minItems" in schema and isinstance(inst, list) and len(inst) < schema["minItems"]:
        err(f"fewer than {schema['minItems']} items")
    if "oneOf" in schema:
        matches = 0
        for alt in schema["oneOf"]:
            sub: list = []
            _check(inst, alt, root, path, sub)
            matches += not sub
        if matches != 1:
            err(f"matches {matches} oneOf alternatives, expected exactly 1")
    if isinstance(inst, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in inst:
                err(f"missing required property {key!r}")
        for key, value in inst.items():
            if key in props:
                _check(value, props[key], root, _child(path, key), errors)
            elif "additionalProperties" in schema:
                extra = schema["additionalProperties"]
                if extra is False:
                    err(f"additional property {key!r} not allowed", _child(path, key))
                elif extra is not True:
                    _check(value, extra, root, _child(path, key), errors)
    if isinstance(inst, list) and "items" in schema:
        for i, item in enumerate(inst):
            _check(item, schema["items"], root, _child(path, i), errors)
