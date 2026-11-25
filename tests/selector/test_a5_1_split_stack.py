"""A5.1: `fx-split-stack` gives the selection of spec 13 section 8.4, reason and detail texts aside."""

import json
import time

from jsonschema import Draft202012Validator

from peo import selector
from peo.validate import load_schema
from peo.validate import validate as validate_schema

from .conftest import EXAMPLES, GOLDEN, ROOT, golden

EXPECTED = json.loads((EXAMPLES / "selection.split-stack.json").read_text())


def strip(out: dict) -> dict:
    """The output without the free texts (`reason` of selected, `detail` of rejected)."""
    cut = json.loads(json.dumps(out))
    for item in cut["selected"]:
        item.pop("reason", None)
    for item in cut["rejected"]:
        item.pop("detail", None)
    return cut


def test_a5_1_the_selection_equals_the_expected_file(real_catalog):
    started = time.perf_counter()
    out = selector.select(real_catalog, golden("fx-split-stack"), {}, {})
    assert time.perf_counter() - started < 5                   # SC-005 says 1 s; CI gets slack
    assert json.dumps(strip(out), sort_keys=True, indent=1) == json.dumps(strip(EXPECTED), sort_keys=True,
                                                                         indent=1)
    assert (len(out["selected"]), len(out["reused"]), len(out["rejected"]), out["cost_total"]) == (11, 1, 9, 23)


def test_a5_1_the_output_validates_against_the_schema(real_catalog):
    schema = json.loads((ROOT / "docs/design/spec/schemas/selection.schema.json").read_text())
    out = selector.select(real_catalog, golden("fx-split-stack"), {}, {})
    assert list(Draft202012Validator(schema).iter_errors(out)) == []
    assert json.loads((GOLDEN / "fx-split-stack" / "selection.json").read_text()) == EXPECTED


def test_a5_1_validate_py_and_jsonschema_give_the_same_verdict(real_catalog):
    out = selector.select(real_catalog, golden("fx-split-stack"), {}, {})
    schema = json.loads((ROOT / "docs/design/spec/schemas/selection.schema.json").read_text())
    assert validate_schema(out, load_schema("selection")) == []
    assert list(Draft202012Validator(schema).iter_errors(out)) == []
    broken = {**out, "cost_total": -1}
    assert validate_schema(broken, load_schema("selection")) != []
    assert list(Draft202012Validator(schema).iter_errors(broken)) != []
