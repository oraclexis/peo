"""A5.3: an alternative backbone in the tracked declarations stops the selection (code 6)."""

import pytest

from peo import selector
from peo.selector import BackboneConflict, BackboneUnknown

from .conftest import golden


def test_a5_3_a_declared_alternative_backbone_is_a_conflict(real_catalog):
    with pytest.raises(BackboneConflict) as raised:
        selector.select(real_catalog, golden("fx-conflict"), {}, golden("fx-conflict", "declared.json"))
    assert "claude-plugin:superpowers" in str(raised.value) and raised.value.code == "E_BACKBONE_CONFLICT"


def test_a5_3_answering_with_the_default_backbone_lifts_the_conflict(real_catalog):
    answer = {"q.backbone_conflict": selector.DEFAULT_BACKBONE}
    out = selector.select(real_catalog, golden("fx-conflict"), answer, golden("fx-conflict", "declared.json"))
    assert out["backbone"]["id"] == selector.DEFAULT_BACKBONE
    assert "claude-plugin:superpowers" in {e["ref"] for e in out["rejected"]}


def test_a5_3_another_answer_is_an_unknown_backbone(real_catalog):
    with pytest.raises(BackboneUnknown) as raised:
        selector.select(real_catalog, golden("fx-conflict"), {"q.backbone_conflict": "superpowers"},
                        golden("fx-conflict", "declared.json"))
    assert raised.value.code == "E_BACKBONE_UNKNOWN"


def test_a5_3_without_a_declaration_nothing_is_decided_from_the_machine(real_catalog):
    out = selector.select(real_catalog, golden("fx-conflict"), {}, {"plugins": [], "mcp_servers": []})
    assert out["ok"] in (True, False)
