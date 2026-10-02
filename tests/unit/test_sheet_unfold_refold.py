from types import SimpleNamespace as NS
from unittest.mock import Mock
import json
import pytest
from conftest import load_tool


@pytest.fixture
def unfold(monkeypatch):
    mod = load_tool("sheet_create_unfold")
    body = NS(name="Sheet", faces=NS(count=14), isSheetMetal=True)
    feature = NS(name="Unfold1")
    factory = NS(createInput=Mock(return_value=NS()), add=Mock(return_value=feature))
    comp = NS(features=NS(unfoldFeatures=factory), parentDesign=NS(rootComponent=object()))
    body.parentComponent = comp
    monkeypatch.setattr(mod._FACE, "resolve", lambda x: (NS(body=body), None))
    monkeypatch.setattr(mod._BENDS, "resolve", lambda x: ([], None))
    monkeypatch.setattr(mod._common, "_native_of", lambda x: x)
    monkeypatch.setattr(mod._common, "native_identity", lambda x: id(x) if x else None)
    monkeypatch.setattr(mod._common, "same_component", lambda a, b: True)
    monkeypatch.setattr(mod._common, "design", lambda: comp.parentDesign)
    # The wall census before the add, then the groups still standing after it.
    monkeypatch.setattr(mod._sheet_common, "bend_wall_groups",
                        Mock(side_effect=[[["inner", "outer"]], []]))
    monkeypatch.setattr(mod._geom, "face_frames", lambda faces: {})
    monkeypatch.setattr(mod._geom, "faces_moved", lambda faces, before: (0, 14))
    return mod, factory


def test_unfold_unchanged_body_refused(unfold):
    mod, factory = unfold
    result = mod.handler(stationary_face="face", all_bends=True)
    assert result["isError"] is True
    assert "geometry" in str(result)


def test_unfold_conflicting_modes_do_not_mutate(unfold):
    mod, factory = unfold
    result = mod.handler(stationary_face="face", all_bends=True, bend_faces=["bend"])
    assert result["isError"] is True
    assert "exactly one" in str(result)
    factory.add.assert_not_called()


def test_unfold_all_bends_sends_every_wall_of_every_group_never_the_flag(unfold, monkeypatch):
    # An unfold made with isUnfoldAllBends refolds with the body rotated; the paired walls go in
    # as an explicit list instead, and a bend counts once however many pieces a cut left it in.
    mod, factory = unfold
    census = Mock(side_effect=[[["in_a", "out_a", "in_a2"], ["in_b", "out_b"]], []])
    monkeypatch.setattr(mod._sheet_common, "bend_wall_groups", census)
    monkeypatch.setattr(mod._geom, "faces_moved", lambda faces, before: (7, 14))
    captured = NS()
    factory.createInput = Mock(return_value=captured)
    result = mod.handler(stationary_face="face", all_bends=True)
    assert result["isError"] is False, result
    assert captured.bendFaces == ["in_a", "out_a", "in_a2", "in_b", "out_b"]
    assert not hasattr(captured, "isUnfoldAllBends")
    payload = json.loads(result["content"][0]["text"])
    assert payload["all_bends"] is True and payload["bend_count_unfolded"] == 2


def test_unfold_all_bends_walls_left_after_add_is_error(unfold, monkeypatch):
    mod, factory = unfold
    monkeypatch.setattr(mod._geom, "faces_moved", lambda faces, before: (7, 14))
    monkeypatch.setattr(mod._sheet_common, "bend_wall_groups",
                        Mock(side_effect=[[["inner", "outer"]], [["inner", "outer"]]]))
    result = mod.handler(stationary_face="face", all_bends=True)
    assert result["isError"] is True
    assert "changed geometry" in str(result)


def test_unfold_all_bends_raise_names_the_explicit_route(unfold, monkeypatch):
    mod, factory = unfold
    factory.add.side_effect = RuntimeError("3 : The selected face is not a bend face")
    result = mod.handler(stationary_face="face", all_bends=True)
    assert result["isError"] is True
    assert "bend_faces explicitly" in str(result) and "kind='cylinder_face'" in str(result)


def test_unfold_all_bends_succeeds_through_the_real_wall_pairing(monkeypatch):
    mod = load_tool("sheet_create_unfold")
    monkeypatch.setattr(mod._sheet_common.adsk.core.Cylinder, "classType", staticmethod(lambda: "Cylinder"))
    def cyl(origin, axis, radius):
        return NS(geometry=NS(objectType="Cylinder", origin=NS(asArray=lambda: origin),
                              axis=NS(asArray=lambda: axis), radius=radius))
    inner = cyl((2.5, 0.0, 0.2), (0.0, 1.0, 0.0), 0.2)
    outer = cyl((2.5, 4.0, 0.2), (0.0, 1.0, 0.0), 0.35)
    leg_hole = cyl((2.4, 2.0, 0.8), (1.0, 0.0, 0.0), 0.2)      # in the base plane, yet no bend
    walls = {"items": [NS(geometry=NS(objectType="Plane")), inner, leg_hole, outer]}
    faces = NS(count=14)
    faces.item = lambda i: walls["items"][i] if i < len(walls["items"]) else None
    body = NS(name="Sheet", faces=faces, isSheetMetal=True,
              getBendFaces=lambda: (_ for _ in ()).throw(AssertionError("getBendFaces must not be called before an unfold")))
    feature = NS(name="Unfold1")
    factory = NS(createInput=Mock(return_value=NS()), add=Mock(return_value=feature))
    comp = NS(features=NS(unfoldFeatures=factory), parentDesign=NS(rootComponent=object()))
    body.parentComponent = comp
    monkeypatch.setattr(mod._FACE, "resolve", lambda x: (NS(body=body), None))
    monkeypatch.setattr(mod._BENDS, "resolve", lambda x: ([], None))
    monkeypatch.setattr(mod._common, "_native_of", lambda x: x)
    monkeypatch.setattr(mod._common, "native_identity", lambda x: id(x) if x else None)
    monkeypatch.setattr(mod._common, "same_component", lambda a, b: True)
    monkeypatch.setattr(mod._common, "design", lambda: comp.parentDesign)
    monkeypatch.setattr(mod._geom, "face_frames", lambda faces: {})
    monkeypatch.setattr(mod._geom, "faces_moved", lambda faces, before: (2, 14))

    sent = {}
    def add(inp):
        sent["bendFaces"] = list(getattr(inp, "bendFaces", []))
        sent["flag"] = hasattr(inp, "isUnfoldAllBends")
        walls["items"] = [NS(geometry=NS(objectType="Plane")), leg_hole]     # the bend is flat now
        return feature
    factory.add.side_effect = add

    result = mod.handler(stationary_face="face", all_bends=True)
    assert result["isError"] is False, result
    payload = json.loads(result["content"][0]["text"])
    assert payload["created"] is True and payload["bend_count_unfolded"] == 1
    assert sent == {"bendFaces": [inner, outer], "flag": False}


def test_unfold_all_bends_empty_census_without_cylinders_is_no_bends(unfold, monkeypatch):
    mod, factory = unfold
    monkeypatch.setattr(mod._sheet_common, "bend_wall_groups", lambda body: [])
    result = mod.handler(stationary_face="face", all_bends=True)
    assert result["isError"] is True
    assert "has no bends to unfold" in str(result)
    factory.createInput.assert_not_called()


def test_unfold_all_bends_unreadable_census_is_error(unfold, monkeypatch):
    mod, factory = unfold
    monkeypatch.setattr(mod._sheet_common, "bend_wall_groups", lambda body: None)
    result = mod.handler(stationary_face="face", all_bends=True)
    assert result["isError"] is True
    assert "could not be read" in str(result)
    factory.createInput.assert_not_called()


def test_unfold_explicit_bend_faces_succeeds(unfold, monkeypatch):
    mod, factory = unfold
    body = mod._FACE.resolve("face")[0].body
    bend1, bend2 = NS(body=body), NS(body=body)
    monkeypatch.setattr(mod._BENDS, "resolve", lambda x: ([bend1, bend2], None))
    monkeypatch.setattr(mod._geom, "faces_moved", lambda faces, before: (7, 14))
    captured = NS()
    factory.createInput = Mock(return_value=captured)
    result = mod.handler(stationary_face="face", bend_faces=["h1", "h2"])
    assert result["isError"] is False, result
    assert captured.bendFaces == [bend1, bend2]
    assert not hasattr(captured, "isUnfoldAllBends")
    payload = json.loads(result["content"][0]["text"])
    assert payload["all_bends"] is False and payload["bend_count_unfolded"] == 2


def test_unfold_concatenated_composite_handles_refuse_before_native_input_and_arrays_keep_both(unfold, monkeypatch):
    mod, factory = unfold
    body = mod._FACE.resolve("face")[0].body
    body.faces.count = 22
    handles = ["first|@cylinder_face:2.576880,2.000000,0.222676;rv=revision",
               "second|@cylinder_face:5.459357,2.000000,-0.034601;rv=revision"]
    bends = [NS(body=body), NS(body=body)]
    resolve = Mock(side_effect=lambda _self, h: (bends[handles.index(h)], None))
    monkeypatch.setattr(mod._inputs.GeometryHandle, "resolve", resolve)
    monkeypatch.setattr(mod._BENDS, "resolve",
                        mod._inputs.GeometryHandleList.resolve.__get__(mod._BENDS))
    result = mod.handler(stationary_face="face", bend_faces=",".join(handles))
    assert result["isError"] is True
    assert "JSON array" in result["message"] and "comma-joined" in result["message"]
    resolve.assert_not_called()
    factory.createInput.assert_not_called()
    factory.add.assert_not_called()
    for count in (1, 2):
        monkeypatch.setattr(mod._geom, "faces_moved", lambda faces, before, count=count: (7 * count, 22))
        captured = NS()
        factory.createInput = Mock(return_value=captured)
        result = mod.handler(stationary_face="face", bend_faces=handles[:count])
        assert result["isError"] is False, result
        assert captured.bendFaces == bends[:count]
        assert json.loads(result["content"][0]["text"])["bend_count_unfolded"] == count


@pytest.fixture
def refold(monkeypatch):
    mod = load_tool("sheet_create_refold")
    body = NS(name="Sheet", faces=NS(count=14))
    source = NS(refoldFeature=None, stationaryFace=NS(body=body))
    feature = NS(name="Refold1", unfoldFeature=source)
    def add(inp):
        body.faces.count = 14
        return feature
    factory = NS(createInput=Mock(return_value=object()), add=Mock(side_effect=add))
    source.parentComponent = NS(features=NS(refoldFeatures=factory))
    monkeypatch.setattr(mod._UNFOLD, "resolve", lambda x: ((source, "Unfold1"), None))
    monkeypatch.setattr(mod.adsk.fusion, "UnfoldFeature", NS)
    monkeypatch.setattr(mod._common, "_native_of", lambda x: x)
    monkeypatch.setattr(mod._common, "native_identity", lambda x: id(x) if x else None)
    monkeypatch.setattr(mod._geom, "face_frames", lambda faces: {})
    monkeypatch.setattr(mod._geom, "faces_moved", lambda faces, before: (7, 14))
    return mod, source, feature, factory


def test_refold_wrong_association_refused(refold):
    mod, source, feature, factory = refold
    feature.unfoldFeature = object()
    result = mod.handler("Unfold1")
    assert result["isError"] is True
    assert "association" in str(result)


def test_refold_duplicate_does_not_mutate(refold):
    mod, source, feature, factory = refold
    source.refoldFeature = feature
    result = mod.handler("Unfold1")
    assert result["isError"] is True
    assert "already has refold" in str(result)
    factory.add.assert_not_called()


def test_refold_face_motion_with_unchanged_count_succeeds(refold):
    mod, source, feature, factory = refold
    result = mod.handler("Unfold1")
    assert result.get("isError") is not True
    factory.add.assert_called_once()


def test_refold_unchanged_geometry_refused(refold, monkeypatch):
    mod, source, feature, factory = refold
    monkeypatch.setattr(mod._geom, "faces_moved", lambda faces, before: (0, 14))
    result = mod.handler("Unfold1")
    assert result["isError"] is True
    assert "changed geometry" in str(result)
