"""Focused rich-read routing checks for sheet_get."""

import json
from types import SimpleNamespace

import pytest
from conftest import load_tool

mod = load_tool("sheet_get")


def payload(result):
    assert result["isError"] is False, result
    return json.loads(result["content"][0]["text"])


@pytest.fixture
def sheet_design(monkeypatch):
    design = SimpleNamespace(designSheetMetalRules=SimpleNamespace(count=2),
                             librarySheetMetalRules=SimpleNamespace(count=6))
    monkeypatch.setattr(mod._common, "design", lambda: design)
    return design


def test_default_is_light_and_names_deeper_slices(sheet_design, monkeypatch):
    monkeypatch.setattr(mod, "_rules", lambda *args: pytest.fail("deep rules read on default"))
    out = payload(mod.handler())
    assert out["design_rule_count"] == 2
    assert out["library_rule_count"] == 6
    assert out["next"] == ["rules", "library_rules", "components", "features"]


def test_requested_rule_slice_does_not_repeat_default(sheet_design, monkeypatch):
    monkeypatch.setattr(mod, "_rules", lambda design, scope, cap: {"scope": scope, "cap": cap})
    out = payload(mod.handler(include=["rules"], max_results=3))
    assert out == {"rules": {"scope": "design", "cap": 3}}


def test_features_include_adds_exactly_that_slice(sheet_design, monkeypatch):
    monkeypatch.setattr(mod, "_features", lambda design, cap: {"cap": cap})
    out = payload(mod.handler(include=["features"], max_results=5))
    assert out == {"features": {"cap": 5}}
    assert "features" in mod.TOOL_DESCRIPTION


def test_hem_kind_strips_suffix_and_lowercases():
    hem = SimpleNamespace(definition=SimpleNamespace(objectType="adsk::fusion::FlatHemFeatureDefinition"))
    assert mod._hem_kind(hem) == "flat"
