"""Focused design-local sheet-metal rule edit checks."""

from types import SimpleNamespace

import pytest
from conftest import load_tool
from tests.fakes.scaffold import _NamedCollection

mod = load_tool("sheet_edit_rule")



@pytest.fixture
def rule_design(monkeypatch):
    source = SimpleNamespace(name="Steel (mm)")
    local = SimpleNamespace(count=0)
    design = SimpleNamespace(designSheetMetalRules=local)
    monkeypatch.setattr(mod._common, "design", lambda: design)
    monkeypatch.setattr(mod._RULE, "resolve", lambda raw: ((source, "library"), None))
    monkeypatch.setattr(mod._sheet_common, "matching_rules", lambda *args: [])
    return design, source


def test_copy_requires_initialized_design_rules(rule_design):
    design, _source = rule_design
    result = mod.handler(action="copy", rule="library:Steel (mm)", name="Shop gauge")
    assert result["isError"] is True
    assert "model_create_component(sheet_metal=true)" in result["message"]
    assert design.designSheetMetalRules.count == 0


def test_update_refuses_library_rule(rule_design):
    result = mod.handler(action="update", rule="library:Steel (mm)", thickness="1.5 mm")
    assert result["isError"] is True
    assert "library rule" in result["message"]


def test_length_readback_checks_evaluated_centimeters(rule_design, monkeypatch):
    design, source = rule_design
    value = SimpleNamespace(expression="2 mm", value=0.2)
    source.thickness = value
    monkeypatch.setattr(mod._RULE, "resolve", lambda raw: ((source, "design"), None))
    result = mod.handler(action="update", rule="design:Steel (mm)", thickness="1.5 mm")
    assert result["isError"] is True
    assert "did not evaluate to" in result["message"]
    assert value.expression == "1.5 mm"


def test_literal_ordinal_collision_refuses_then_disclosed_refs_edit_only_each_intended_rule(monkeypatch):
    rules = [SimpleNamespace(name=name, kFactor=0.44, thickness=SimpleNamespace(expression=expr, value=cm))
             for name, expr, cm in [("Steel (mm)", "1.2 mm", .12),
                                   ("Steel (mm)", "2.50 mm", .25), ("Steel (mm)#1", "3 mm", .3)]]
    design = SimpleNamespace(designSheetMetalRules=_NamedCollection(items=rules))
    monkeypatch.setattr(mod._common, "design", lambda: design)
    refs = [mod._sheet_common.rule_ref_and_index(design, r, "design")[0] for r in rules]
    assert refs == [{"scope": "design", "index": 0}, "design:Steel (mm)#2", {"scope": "design", "index": 2}]
    for raw in ("design:Steel (mm)#1", "design:Steel (mm)"):
        result = mod.handler(action="update", rule=raw, thickness="4 mm")
        assert result["isError"] is True and "sheet_get" in result["message"]
        assert [r.thickness.expression for r in rules] == ["1.2 mm", "2.50 mm", "3 mm"]
    expected = [0.44] * 3
    for index, ref in enumerate(refs):
        expected[index] = .5 + index * .1
        result = mod.handler(action="update", rule=ref, k_factor=expected[index])
        assert result["isError"] is False, result
        assert [r.kFactor for r in rules] == expected


@pytest.mark.parametrize("raw", [{"scope": "design", "index": True}, {"scope": "design", "index": -1},
                                  {"scope": "design", "index": 0.5}, {"scope": "design", "index": 3},
                                  {"scope": "Design", "index": 0}, {"scope": "design", "index": 0, "extra": 1}])
def test_rule_index_ref_rejects_invalid_selectors_before_assignment(monkeypatch, raw):
    rule = SimpleNamespace(name="Steel (mm)", kFactor=.44)
    monkeypatch.setattr(mod._common, "design", lambda: SimpleNamespace(
        designSheetMetalRules=_NamedCollection(items=[rule])))
    result = mod.handler(action="update", rule=raw, k_factor=.7)
    assert result["isError"] is True and "ref" in result["message"]
    assert rule.kFactor == .44


def test_unread_native_rule_slot_cannot_shift_a_disclosed_collision_index(monkeypatch):
    first = SimpleNamespace(name="Steel (mm)", kFactor=.44)
    literal = SimpleNamespace(name="Steel (mm)#1", kFactor=.44)
    design = SimpleNamespace(designSheetMetalRules=_NamedCollection(items=[first, None, literal]))
    monkeypatch.setattr(mod._common, "design", lambda: design)
    assert mod._sheet_common.rule_ref_and_index(design, literal, "design") == (None, None)
    result = mod.handler(action="update", rule={"scope": "design", "index": 1}, k_factor=.7)
    assert result["isError"] is True and "could not be read" in result["message"]
    assert first.kFactor == literal.kFactor == .44
