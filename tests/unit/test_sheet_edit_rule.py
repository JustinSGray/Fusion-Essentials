"""Focused design-local sheet-metal rule edit checks."""

from types import SimpleNamespace

import pytest
from conftest import load_tool

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
