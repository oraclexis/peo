"""`load` (research D3): the validated catalog as an immutable value the Selector reads."""

import dataclasses
from datetime import date
from pathlib import Path

import pytest

from peo.catalog import Catalog, CatalogInvalid, load, validate

from .conftest import demo_tool

REAL = Path(__file__).resolve().parents[2] / "catalog"


def test_the_real_catalog_loads_with_its_counts():
    catalog = load(REAL, today=date(2026, 11, 23))
    assert (len(catalog.entries), len(catalog.capabilities), len(catalog.rules)) == (21, 24, 9)
    assert catalog.entries["claude-plugin:php-lsp"]["capabilities"]["provides"] == ["nav.lsp.php"]
    assert catalog.capabilities["spec.authoring"] is True and catalog.capabilities["nav.graph"] is False
    assert list(catalog.capabilities)[0] == "clarify.interview"      # file order is kept


def test_a_loaded_catalog_is_immutable():
    catalog = load(REAL, today=date(2026, 11, 23))
    assert dataclasses.is_dataclass(catalog) and isinstance(catalog, Catalog)
    with pytest.raises(dataclasses.FrozenInstanceError):
        catalog.entries = {}                                   # type: ignore[misc]


def test_a_catalog_with_errors_raises_with_the_report(make_catalog):
    root = make_catalog(tools={"demo": demo_tool().replace('data_path   = "none"\n', "")})
    with pytest.raises(CatalogInvalid) as raised:
        load(root, today=date(2026, 11, 18))
    assert raised.value.report.errors and "tools/cli/demo.toml" in str(raised.value)
    assert str(root.parent) not in str(raised.value)


def test_load_and_validate_agree(make_catalog):
    root = make_catalog()
    catalog = load(root, today=date(2026, 11, 18))
    report = validate(root, today=date(2026, 11, 18))
    assert report.errors == [] and list(catalog.entries) == ["cli:demo"]
    assert report.counts["entries"] == len(catalog.entries)
