from types import SimpleNamespace as NS
from unittest.mock import Mock
import json
import math
import pytest
from conftest import load_tool


def _bbox(min_xyz, max_xyz):
    return NS(minPoint=NS(x=min_xyz[0], y=min_xyz[1], z=min_xyz[2]),
              maxPoint=NS(x=max_xyz[0], y=max_xyz[1], z=max_xyz[2]))


@pytest.fixture
def flange(monkeypatch):
    mod = load_tool("sheet_create_flange")
    design = NS(rootComponent=object())
    comp = NS(name="Comp1")
    comp.parentDesign = design
    body = NS(name="Sheet", isSheetMetal=True, parentComponent=comp,
             faces=NS(count=6), volume=10.0, _bbox=_bbox((0, 0, 0), (80, 40, 1.5)))
    edge = NS(body=body)
    sheet_face, rim_face = NS(name="SheetFace"), NS(name="RimFace")

    feat = NS(name="EdgeFlange1", definition=NS(
        objectType="adsk::fusion::EdgeFlangeFeatureDefinition",
        distance=NS(value=2.0), angle=NS(value=math.radians(90.0)),
        heightDatumType=mod.adsk.fusion.FlangeHeightDatumTypes.OuterFacesFlangeHeightDatumType,
        bendPositionType=mod.adsk.fusion.BendPositionTypes.StartEdgeBendPositionType,
        isFlipped=False))
    inp = NS(heightDatumType=None, bendPositionType=None, isMiteredCorners=None, isFlipped=None, angle=None)

    def _do_add(_inp):
        body.faces = NS(count=14)
        body.volume = 12.0
        body._bbox = _bbox((0, 0, 0), (83.5, 40, 20.0))
        return feat

    ff = NS(createEdgeFlangeInput=Mock(return_value=inp), add=Mock(side_effect=_do_add))
    comp.features = NS(flangeFeatures=ff)
    comp.bRepBodies = NS(itemByName=Mock(return_value=body))

    monkeypatch.setattr(mod._EDGES, "resolve", lambda x: ([edge], None))
    monkeypatch.setattr(mod._common, "_native_of", lambda x: x)
    monkeypatch.setattr(mod._common, "design", lambda: design)
    monkeypatch.setattr(mod._common, "same_component", lambda a, b: True)
    monkeypatch.setattr(mod._common, "native_identity", lambda x: id(x))
    monkeypatch.setattr(mod._sheet_common, "sheet_edge_faces", lambda e: (sheet_face, rim_face, None))
    monkeypatch.setattr(mod._sheet_common, "outward_normal", lambda f: NS(x=0.0, y=0.0, z=1.0))
    monkeypatch.setattr(mod._sheet_common, "bend_face_count", Mock(side_effect=[0, 2]))
    monkeypatch.setattr(mod._sheet_common, "flat_pattern_row", lambda c: {"present": False})
    monkeypatch.setattr(mod._geom, "signed_volume", lambda b: b.volume)
    monkeypatch.setattr(mod._geom, "body_aabb", lambda b: b._bbox)
    return mod, comp, ff, feat, inp, body, edge


def _call(mod, **kw):
    kw.setdefault("kind", "edge")
    kw.setdefault("distance", 20)
    return mod.handler(**kw)


def test_bend_edge_is_refused(flange, monkeypatch):
    mod, comp, ff, *_ = flange
    monkeypatch.setattr(mod._sheet_common, "sheet_edge_faces",
                        lambda e: (None, None, "meets a curved face."))
    result = _call(mod)
    assert result["isError"] is True
    assert "edges[0] meets a curved face." in str(result)
    ff.createEdgeFlangeInput.assert_not_called()


def test_edges_on_two_bodies_are_refused(flange, monkeypatch):
    mod, comp, ff, feat, inp, body, edge = flange
    other_body = NS(name="Other", isSheetMetal=True)
    other_edge = NS(body=other_body)
    monkeypatch.setattr(mod._EDGES, "resolve", lambda x: ([edge, other_edge], None))
    result = _call(mod)
    assert result["isError"] is True
    assert "same sheet body" in str(result)
    ff.createEdgeFlangeInput.assert_not_called()


def test_add_raising_reports_compute_text(flange):
    mod, comp, ff, *_ = flange
    ff.add = Mock(side_effect=RuntimeError(
        "Flange geometry is invalid Compute Failed: a huge internal stack dump"))
    result = _call(mod)
    assert result["isError"] is True
    assert "Flange geometry is invalid" in str(result)
    assert "internal stack dump" not in str(result)


def test_bend_faces_short_of_two_is_error(flange, monkeypatch):
    mod, comp, ff, *_ = flange
    monkeypatch.setattr(mod._sheet_common, "bend_face_count", Mock(side_effect=[0, 1]))
    result = _call(mod)
    assert result["isError"] is True
    assert "bend faces 0->1" in str(result)


def test_definition_distance_mismatch_is_error(flange):
    mod, comp, ff, feat, inp, body, edge = flange
    feat.definition.distance = NS(value=999.0)
    result = _call(mod)
    assert result["isError"] is True
    assert "999.0" in str(result)


def test_definition_angle_mismatch_is_error(flange):
    mod, comp, ff, feat, inp, body, edge = flange
    feat.definition.angle = NS(value=math.radians(999.0))
    result = _call(mod)
    assert result["isError"] is True
    assert str(math.radians(999.0)) in str(result)


def test_definition_flip_mismatch_is_error(flange):
    mod, comp, ff, feat, inp, body, edge = flange
    feat.definition.isFlipped = True
    result = _call(mod)
    assert result["isError"] is True
    assert "flip True" in str(result)


def test_happy_path_reports_counts_and_extent(flange):
    mod, comp, ff, feat, inp, body, edge = flange
    out = _call(mod)
    assert out["isError"] is False, out
    payload = json.loads(out["content"][0]["text"])
    assert payload["created"] is True and payload["kind"] == "edge"
    assert payload["feature"] == "EdgeFlange1"
    assert payload["faces_before"] == 6 and payload["faces_after"] == 14
    assert payload["bend_faces_before"] == 0 and payload["bend_faces_after"] == 2
    assert "extent_mm" not in payload
    assert payload["flat_pattern"] == {"present": False}
    assert payload["height_datum"] == "outer" and payload["position"] == "start_edge"
    assert payload["flip"] is False
    assert inp.heightDatumType == mod.adsk.fusion.FlangeHeightDatumTypes.OuterFacesFlangeHeightDatumType
    assert inp.isFlipped is False and inp.isMiteredCorners is True


@pytest.fixture
def base_flange(monkeypatch):
    mod = load_tool("sheet_create_flange")
    design = NS(rootComponent=object())
    active = NS(name="Active")
    active.activeSheetMetalRule = NS(name="Steel", thickness=NS(value=0.25))
    active.bRepBodies = NS(count=1)
    sketch = NS(parentComponent=active)
    plane = NS(normal=NS(x=0.0, y=0.0, z=1.0))
    prof = NS(parentSketch=sketch, plane=plane)

    new_body = NS(name="BaseFlange1Body", isSheetMetal=True, _bbox=_bbox((0, 0, 0), (8, 4, 0.25)))
    feat = NS(name="BaseFlange1", definition=NS(
        objectType="adsk::fusion::BaseFlangeFeatureDefinition",
        orientation=mod.adsk.fusion.FlangeOrientations.SideOneFlangeOrientation),
             bodies=NS(count=1, item=lambda i: new_body))
    inp = NS(orientation=None)

    def _do_add(_inp):
        active.bRepBodies.count = 2
        return feat

    ff = NS(createBaseFlangeInput=Mock(return_value=inp), add=Mock(side_effect=_do_add))
    active.features = NS(flangeFeatures=ff)

    monkeypatch.setattr(mod._PROFILE, "resolve", lambda raw, comp="": (prof, None))
    monkeypatch.setattr(mod._common, "design", lambda: design)
    monkeypatch.setattr(mod._common, "target_component", lambda d: active)
    monkeypatch.setattr(mod._common, "same_component", lambda a, b: a is b)
    monkeypatch.setattr(mod._geom, "body_aabb", lambda b: b._bbox)
    return mod, active, ff, feat, inp, new_body, sketch


def _call_base(mod, **kw):
    kw.setdefault("kind", "base")
    kw.setdefault("profile", "handle")
    return mod.handler(**kw)


def test_base_profile_in_non_active_component_is_refused(base_flange):
    mod, active, ff, feat, inp, new_body, sketch = base_flange
    sketch.parentComponent = NS(name="Other")
    result = _call_base(mod)
    assert result["isError"] is True
    assert "not the active component" in str(result)
    ff.createBaseFlangeInput.assert_not_called()


def test_base_body_not_sheet_is_error(base_flange):
    mod, active, ff, feat, inp, new_body, sketch = base_flange
    new_body.isSheetMetal = False
    result = _call_base(mod)
    assert result["isError"] is True
    assert "isSheetMetal=False" in str(result)


def test_base_thickness_mismatch_is_error(base_flange):
    mod, active, ff, feat, inp, new_body, sketch = base_flange
    active.activeSheetMetalRule = NS(name="Steel", thickness=NS(value=999.0))
    result = _call_base(mod)
    assert result["isError"] is True
    assert "999.0" in str(result)


def test_base_orientation_mismatch_is_error(base_flange):
    mod, active, ff, feat, inp, new_body, sketch = base_flange
    feat.definition.orientation = mod.adsk.fusion.FlangeOrientations.SideTwoFlangeOrientation
    result = _call_base(mod)
    assert result["isError"] is True
    assert "orientation" in str(result)


def test_base_happy_path_reports_body_and_thickness(base_flange):
    mod, active, ff, feat, inp, new_body, sketch = base_flange
    out = _call_base(mod)
    assert out["isError"] is False, out
    payload = json.loads(out["content"][0]["text"])
    assert payload["created"] is True and payload["kind"] == "base"
    assert payload["body"] == "BaseFlange1Body"
    assert payload["bodies_before"] == 1 and payload["bodies_after"] == 2
    assert payload["thickness_mm"] == 2.5
    assert payload["rule"] == "Steel" and payload["rule_existed_before"] is True
    assert payload["orientation"] == "side_one"
