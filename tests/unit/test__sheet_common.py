"""Unit tests for the sheet-metal helpers in ``_sheet_common.py`` that the flange family shares."""

from types import SimpleNamespace as NS

from conftest import _NamedCollection, load_tool

sc = load_tool("_sheet_common")


def test_bend_face_count_collects_only_cylindrical_faces(monkeypatch):
    monkeypatch.setattr(sc.adsk.core.Cylinder, "classType", staticmethod(lambda: "Cylinder"))
    cyl = NS(geometry=NS(objectType="Cylinder"))
    flat = NS(geometry=NS(objectType="Plane"))
    body = NS(faces=[cyl, flat, cyl])
    monkeypatch.setattr(sc, "iter_collection", lambda coll: list(coll))
    assert sc.bend_face_count(body) == 2


def _cyl(origin, axis, radius):
    """A cylindrical face fake with the geometry reads bend_wall_groups makes."""
    return NS(geometry=NS(objectType="Cylinder", origin=NS(asArray=lambda: origin),
                          axis=NS(asArray=lambda: axis), radius=radius))


def test_bend_wall_groups_pairs_walls_per_axis_and_drops_holes(monkeypatch):
    monkeypatch.setattr(sc.adsk.core.Cylinder, "classType", staticmethod(lambda: "Cylinder"))
    inner = _cyl((2.5, 0.0, 0.2), (0.0, 1.0, 0.0), 0.2)
    inner_split = _cyl((2.5, 3.0, 0.2), (0.0, 1.0, 0.0), 0.2)          # the same bend past a slot
    outer = _cyl((2.5, 1.0, 0.2), (0.0, -2.0, 0.0), 0.35)              # flipped, unnormalized axis
    base_hole = _cyl((3.1, 2.0, 0.0), (0.0, 0.0, 1.0), 0.2)
    leg_hole = _cyl((2.4, 2.0, 0.8), (1.0, 0.0, 0.0), 0.2)             # axis in the base plane
    plane = NS(geometry=NS(objectType="Plane"))
    body = NS(faces=_NamedCollection(items=[plane, base_hole, leg_hole, inner, outer, inner_split]))
    assert sc.bend_wall_groups(body) == [[inner, outer, inner_split]]


def test_bend_wall_groups_keeps_parallel_offset_bends_apart(monkeypatch):
    # A U-channel: two y-axis bends at x=2.5 and x=5.5 are two groups, not one.
    monkeypatch.setattr(sc.adsk.core.Cylinder, "classType", staticmethod(lambda: "Cylinder"))
    a_in, a_out = _cyl((2.5, 0.0, 0.2), (0.0, 1.0, 0.0), 0.2), _cyl((2.5, 0.0, 0.2), (0.0, 1.0, 0.0), 0.35)
    b_in, b_out = _cyl((5.5, 0.0, 0.2), (0.0, 1.0, 0.0), 0.2), _cyl((5.5, 0.0, 0.2), (0.0, 1.0, 0.0), 0.35)
    body = NS(faces=_NamedCollection(items=[a_in, b_in, a_out, b_out]))
    assert sc.bend_wall_groups(body) == [[a_in, a_out], [b_in, b_out]]


def test_bend_wall_groups_reads_a_noisy_radius_as_one_radius(monkeypatch):
    # A hole cut in two pieces whose radii differ by float noise is still one radius, not a pair.
    monkeypatch.setattr(sc.adsk.core.Cylinder, "classType", staticmethod(lambda: "Cylinder"))
    piece_a = _cyl((1.0, 1.0, 0.0), (0.0, 0.0, 1.0), 0.2000004)
    piece_b = _cyl((1.0, 1.0, 0.0), (0.0, 0.0, 1.0), 0.2000006)
    assert sc.bend_wall_groups(NS(faces=_NamedCollection(items=[piece_a, piece_b]))) == []


def test_bend_wall_groups_unreadable_face_is_none(monkeypatch):
    monkeypatch.setattr(sc.adsk.core.Cylinder, "classType", staticmethod(lambda: "Cylinder"))
    assert sc.bend_wall_groups(NS(faces=_NamedCollection(items=[NS(geometry=None)]))) is None
    blind = NS(geometry=NS(objectType="Cylinder", origin=None, axis=None, radius=0.2))
    assert sc.bend_wall_groups(NS(faces=_NamedCollection(items=[blind]))) is None
    flat = _cyl((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.2)
    assert sc.bend_wall_groups(NS(faces=_NamedCollection(items=[flat]))) is None


def test_sheet_edge_faces_refuses_an_edge_that_meets_a_curved_face(monkeypatch):
    monkeypatch.setattr(sc.adsk.core.Line3D, "classType", staticmethod(lambda: "Line3D"))
    monkeypatch.setattr(sc.adsk.core.Plane, "classType", staticmethod(lambda: "Plane"))
    edge = NS(geometry=NS(objectType="Line3D"),
              faces=[NS(geometry=NS(objectType="Plane"), area=5.0),
                     NS(geometry=NS(objectType="Cylinder"), area=1.0)])
    monkeypatch.setattr(sc, "iter_collection", lambda coll: list(coll))
    sheet, rim, why = sc.sheet_edge_faces(edge)
    assert sheet is None and rim is None
    assert "curved face" in why


def test_rule_row_dedupes_same_name_with_hash_refs_and_index():
    design = NS()
    r1 = NS(name="Steel (mm)")
    r2 = NS(name="Steel (mm)", kFactor=0.9)
    design.designSheetMetalRules = _NamedCollection(items=[r1, r2])
    row1, row2 = sc.rule_row(design, r1, "design"), sc.rule_row(design, r2, "design")
    assert row1["ref"] == "design:Steel (mm)#1" and row1["index"] == 0
    assert row2["ref"] == "design:Steel (mm)#2" and row2["index"] == 1


def test_rule_row_keeps_a_unique_name_ref_unsuffixed():
    design = NS()
    r = NS(name="Aluminum (mm)")
    design.designSheetMetalRules = _NamedCollection(items=[r])
    row = sc.rule_row(design, r, "design")
    assert row["ref"] == "design:Aluminum (mm)" and row["index"] == 0


def test_rule_ref_and_index_reads_a_library_rule_via_the_passed_design_not_parentDesign():
    # rule.parentDesign is measured only on DESIGN rules; a library rule has no such attribute,
    # so the design must come in as a parameter, never a read off the rule itself.
    design = NS()
    lib = NS(name="Aluminum (mm)")
    design.librarySheetMetalRules = _NamedCollection(items=[lib])
    ref, index = sc.rule_ref_and_index(design, lib, "library")
    assert ref == "library:Aluminum (mm)" and index == 0


def test_sheet_edge_faces_orders_the_broad_sheet_face_first(monkeypatch):
    monkeypatch.setattr(sc.adsk.core.Line3D, "classType", staticmethod(lambda: "Line3D"))
    monkeypatch.setattr(sc.adsk.core.Plane, "classType", staticmethod(lambda: "Plane"))
    broad = NS(geometry=NS(objectType="Plane"), area=5.0, name="broad")
    thin = NS(geometry=NS(objectType="Plane"), area=1.0, name="thin")
    edge = NS(geometry=NS(objectType="Line3D"), faces=[thin, broad])
    monkeypatch.setattr(sc, "iter_collection", lambda coll: list(coll))
    normals = {id(broad): NS(dotProduct=lambda other: 0.0), id(thin): NS(dotProduct=lambda other: 0.0)}
    monkeypatch.setattr(sc, "outward_normal", lambda face: normals[id(face)])
    sheet, rim, why = sc.sheet_edge_faces(edge)
    assert why is None
    assert sheet is broad and rim is thin
