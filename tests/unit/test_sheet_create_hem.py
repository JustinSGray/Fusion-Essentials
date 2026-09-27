from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from conftest import load_tool


@pytest.fixture
def hem(monkeypatch):
    mod = load_tool("sheet_create_hem")
    comp = NS(parentDesign=NS(rootComponent=object()))
    body = NS(name="Sheet1", isSheetMetal=True, faces=NS(count=6), parentComponent=comp)
    edge = NS(body=body)
    feature = NS(name="Hem1", definition=NS(objectType="adsk::fusion::FlatHemFeatureDefinition"))
    inp = NS(setFlatHem=Mock(return_value=True), setOpenHem=Mock(return_value=True),
             setRolledHem=Mock(return_value=True), setRopeHem=Mock(return_value=True),
             setTeardropHem=Mock(return_value=True), setDoubleHem=Mock(return_value=True))
    factory = NS(createHemFeatureInput=Mock(return_value=inp), add=Mock(return_value=feature))
    comp.features = NS(hemFeatures=factory)
    body_after = NS(name="Sheet1", faces=NS(count=8))
    comp.bRepBodies = NS(itemByName=Mock(return_value=body_after))
    vol_map = {id(body): 10.0, id(body_after): 12.0}
    monkeypatch.setattr(mod._EDGE, "resolve", lambda x: (edge, None))
    monkeypatch.setattr(mod._common, "_native_of", lambda x: x)
    monkeypatch.setattr(mod._common, "same_component", lambda a, b: True)
    monkeypatch.setattr(mod._common, "design", lambda: comp.parentDesign)
    monkeypatch.setattr(mod._sheet_common, "sheet_edge_faces", lambda e: (object(), object(), None))
    monkeypatch.setattr(mod._sheet_common, "bend_face_count", lambda b: 2)
    monkeypatch.setattr(mod._geom, "signed_volume", lambda b: vol_map.get(id(b)))
    return mod, body, body_after, inp, factory, feature


def test_missing_dimension_is_refused_and_no_mutation(hem):
    mod, body, body_after, inp, factory, feature = hem
    result = mod.handler(edge="e", kind="rope", length=5, gap=2)
    assert result["isError"] is True
    assert "radius" in result["message"] and "missing" in result["message"]
    factory.createHemFeatureInput.assert_not_called()


def test_extra_dimension_is_refused_and_no_mutation(hem):
    mod, body, body_after, inp, factory, feature = hem
    result = mod.handler(edge="e", kind="flat", length=5, gap=2)
    assert result["isError"] is True
    assert "drop gap" in result["message"]
    factory.createHemFeatureInput.assert_not_called()


def test_position_choice_only_accepts_the_two_names(hem):
    mod, body, body_after, inp, factory, feature = hem
    result = mod.handler(edge="e", kind="flat", length=5, position="outside")
    assert result["isError"] is True
    factory.createHemFeatureInput.assert_not_called()


def test_landed_definition_class_mismatch_is_error(hem):
    mod, body, body_after, inp, factory, feature = hem
    feature.definition.objectType = "adsk::fusion::OpenHemFeatureDefinition"
    result = mod.handler(edge="e", kind="flat", length=5)
    assert result["isError"] is True
    assert "verified" in result["message"]


def test_unchanged_body_is_not_success(hem):
    mod, body, body_after, inp, factory, feature = hem
    body_after.faces.count = 6            # unchanged from faces_before
    result = mod.handler(edge="e", kind="flat", length=5)
    assert result["isError"] is True
    assert "verified" in result["message"]
