# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""ACT rows: the solids, the details that cut them, and the parametric resize.

The modelling spine of the story: the sketches turn into the bracket, its edges are broken, the
cameo bodies carry the feature verbs the part has no home for, and the one driving length is
re-driven so every feature follows it.
"""

import math

from verify_core import (
    EXPORT_DIR, _RECALL, _axis_aligned_face_at, _box, _chamfered, _component_metadata, _ctx_get, _cut_a_chain,
    _cut_exactly, _cut_on_its_pivot, _marker_parked_after, _datum, _datum_plane,
    _document_closed, _drafted, _drafted_on_its_pivot, _drafted_symmetric, _drilled,
    _extent_measured, _extruded, _face_up_at, _fg, _fgn,
    _filleted, _full_rounded, _gap_measured, _holes_recognized, _holes_windowed, _home_address,
    _home_document, _interference_measured, _joined,
    _joint_origin_at, _joint_origins_listed, _lofted, _made_component, _made_component_inactive,
    _material_assigned, _matched, _measured, _metadata_set, _mirrored, _moved, _moved_occurrence,
    _captured, _near, _needs, _num,
    _new_document, _offset_faces, _param_added, _param_deleted, _param_read, _param_set_to,
    _param_traced, _path_count, _patterned, _piped, _pocket_boss, _pockets_recognized, _prof,
    _recall, _recognized_cbore_walls, _recognized_pocket_floor, _refused, _relation_measured,
    _relation_passes, _relation_read, _replaced_on_its_pivot, _revolved, _shelled,
    _sits_on_a_face, _split_bodies, _swept, _unless, _watch)
from verify_acts_cam import MACHINING_EXTENSION
from verify_layout import _px, _py


_RADIUS_DIAMETER_TOL_MM = 0.0005
_SHOT_PATH = EXPORT_DIR + "/w4_shot"


def _sweep_edit_at_volume(expected):
    """Check one edit's verified target shape and preserved sweep identity."""
    def check(p):
        bodies = p.get("target_after") or []
        volume = bodies[0].get("volume_cm3") if len(bodies) == 1 else None
        return _measured("sweep operand edit", {
            "same_feature": p.get("same_feature"), "definition_matches": p.get("definition_matches"),
            "geometry_changed": p.get("geometry_changed"), "target_volume_cm3": volume,
            "outside_body_changes": p.get("outside_body_changes"),
            "marker_restored": p.get("marker_restored"),
            "new_errors": p.get("new_timeline_errors"),
            "new_warnings": p.get("new_timeline_warnings")},
            p.get("edited") is True and p.get("same_feature") is True
            and p.get("definition_matches") is True and p.get("geometry_changed") is True
            and (p.get("definition_before") or {}).get("profile_members") == 1
            and (p.get("definition_after") or {}).get("profile_members") == 1
            and p.get("outside_body_changes") == [] and p.get("marker_restored") is True
            and p.get("feature_health") == "healthy"
            and p.get("new_timeline_errors") == [] and p.get("new_timeline_warnings") == []
            and _num(volume) and _near(volume, expected, 0.02))
    return check


def _sweep_inspected_at_volume(expected):
    """Check independent model_inspect volume in cm3 after a sweep edit."""
    def check(p):
        volume = (p.get("mass") or {}).get("volume")
        return _measured("independent swept body volume", {"volume_cm3": volume},
                         _num(volume) and _near(volume, expected, 0.02))
    return check


def _sweep_brep_list_edited(p):
    """Check the exact two-member BRep path and independent target material delta."""
    path_count = (p.get("definition_after") or {}).get("path_curves")
    return _sweep_edit_at_volume(math.pi * 0.8 ** 2 * (1 + math.pi / 4))(p) and _measured(
        "two BRep path members", {"count": path_count}, path_count == 2)


def _sweep_dependent_survived(changed_bounds):
    """Check the saved dependent body handle, material and expected support motion."""
    def check(p):
        base = _RECALL["sweep_dependent_before"]
        volume = (p.get("mass") or {}).get("volume")
        bounds = (p.get("min_point"), p.get("max_point"))
        moved = bounds != (base["min_point"], base["max_point"])
        return _measured("sweep dependent body", {"volume_cm3": volume, "bounds_moved": moved},
                         _num(volume) and _near(volume, base["volume"], 0.001)
                         and moved is changed_bounds)
    return check

_HOLE_HOST = "HoleHostB"
_HOLE_ACTIVE = "ActiveA"
_HOLE_X0 = 2600.0
_HOLE_ACTIVE_X0 = 2650.0
_HOLE_VOLUME = 125.663706


def _section_created(other_key=None):
    """Require one generated section name, distinct from an earlier cut when supplied."""
    def check(p):
        name = p.get("section")
        other = _RECALL.get(other_key) if other_key else None
        return _measured("generated section identity", {"section": name, "other": other},
                         isinstance(name, str) and bool(name)
                         and (other_key is None or name != other))
    return check


def _section_census(keys, visible):
    """Require the complete generated-name and visibility census for the retained sections."""
    def check(p):
        rows = p.get("sections") or []
        expected = [_RECALL.get(key) for key in keys]
        got = [row.get("name") for row in rows]
        bulbs = [row.get("visible") for row in rows]
        return _measured("section analysis census",
                         {"count": p.get("count"), "names": got, "visible": bulbs},
                         all(isinstance(name, str) and name for name in expected)
                         and p.get("count") == len(rows) == len(expected)
                         and got == expected and bulbs == list(visible))
    return check


def _section_named_clear(removed_key):
    """Require one exact generated section removed with bounded count facts."""
    def check(p):
        removed = _RECALL.get(removed_key)
        valid = (p.get("section") == removed and p.get("removed") == [removed]
                 and p.get("removed_count") == 1 and p.get("sections_before") == 2
                 and p.get("sections_after") == 1 and "remaining" not in p)
        return _measured("selected section deletion",
                         {"removed": p.get("removed"), "before": p.get("sections_before"),
                          "after": p.get("sections_after")},
                         valid)
    return check


def _section_camera(p):
    """Return one complete workspace camera record for later equality."""
    view = p.get("view") or {}
    if (view.get("projection") not in ("orthographic", "perspective")
            or not isinstance(view.get("eye"), dict) or not isinstance(view.get("target"), dict)):
        raise AssertionError(f"section camera is incomplete: {view!r}")
    return view


def _section_camera_unchanged(key):
    """Require the workspace camera to equal the retained pre-cut record."""
    def check(p):
        current, before = _section_camera(p), _RECALL.get(key)
        return _measured("section clear camera preservation",
                         {"before": before, "after": current}, current == before)
    return check


_FINE_ANGLE_DEG = 4.0909090909


def _fine_angle_plane(p):
    """model_construction at a long-decimal angle publishes the angle its own parameter landed."""
    return _datum("plane")(p) and _measured(
        "at_angle plane lands the long-decimal angle",
        {"angle_deg": p.get("angle_deg"), "expression": p.get("angle_expression"),
         "model_parameters": p.get("model_parameters")},
        _near(p.get("angle_deg"), _FINE_ANGLE_DEG, 1e-8)
        and bool((p.get("model_parameters") or {}).get("angle")))


def _fine_angle_param(p):
    """param_get of that plane's angle parameter reads every digit asked for, in degrees."""
    par = p.get("parameter") or {}
    return _measured("the fine plane's angle parameter read back",
                     {"name": par.get("name"), "expression": par.get("expression"),
                      "value": par.get("value"), "value_units": par.get("value_units")},
                     par.get("name") == _RECALL.get("db_fine_param")
                     and par.get("value_units") == "deg"
                     and _near(par.get("value"), _FINE_ANGLE_DEG, 1e-8))


def _addr_planes_own_their_params(p):
    """Both components' AddrPlane rows carry parameters, and no parameter name sits on both."""
    rows = [r for r in (p.get("timeline") or {}).get("timeline") or []
            if r.get("name") == "AddrPlane"]
    names = [sorted(q.get("name") for q in r.get("params") or []) for r in rows]
    # A construction plane's timeline row reads component None (measured rel6), so the two rows are
    # told apart by their parameters alone here.
    return _measured(
        "same-named planes in two components carry their own parameters",
        {"components": [r.get("component") for r in rows], "params": names},
        len(rows) == 2 and all(names) and not set(names[0]) & set(names[1]))


def _placed_xyz(component, xyz):
    """One authored point after the layout pass places its component."""
    return [_px(component, xyz[0]), _py(component, xyz[1]), xyz[2]]


def _hole_body_state(component, low, high, volume):
    """A body has the exact measured bounds and volume for one hole-participant beat."""
    def check(p):
        got_low, got_high = p.get("min_point") or {}, p.get("max_point") or {}
        want_low, want_high = _placed_xyz(component, low), _placed_xyz(component, high)
        got_volume = (p.get("mass") or {}).get("volume")
        bounds_ok = all(
            _near(got.get(axis), want, 0.01)
            for got, wanted in ((got_low, want_low), (got_high, want_high))
            for axis, want in zip(("x", "y", "z"), wanted))
        return _measured(
            f"{component} body volume and bounds",
            {"kind": p.get("kind"), "units": p.get("units"),
             "accuracy": (p.get("mass") or {}).get("accuracy_used"),
             "volume": got_volume, "min": got_low, "max": got_high},
            p.get("kind") == "body" and p.get("units") == "mm"
            and (p.get("mass") or {}).get("accuracy_used") == "very_high"
            and _near(got_volume, volume, 0.001) and bounds_ok)
    return check


def _hole_cylinders(component, positions):
    """The complete radius-2 cylinder census at the expected placed positions."""
    def check(p):
        matches = p.get("matches") or []
        wanted = sorted(tuple(round(v, 3) for v in _placed_xyz(component, pos))
                        for pos in positions)
        got = sorted(tuple(round(v, 3) for v in m.get("position", [])) for m in matches)
        exact_faces = all(
            m.get("kind") == "cylinder_face" and _near(m.get("radius"), 2.0, 0.001)
            for m in matches)
        return _measured(
            f"{component} radius-2 cylinder census",
            {"match_count": p.get("match_count"), "returned": p.get("returned"),
             "positions": got, "units": p.get("units"), "truncated": p.get("truncated")},
            p.get("units") == "mm"
            and p.get("match_count") == p.get("returned") == len(wanted)
            and len(matches) == len(wanted) and p.get("truncated") is not True
            and exact_faces and got == wanted)
    return check


def _hole_face_bounds(p):
    """The fresh scoped bore handle resolves to the measured 4 x 4 x 10 mm face."""
    low = _placed_xyz(_HOLE_HOST, (_HOLE_X0 + 8, 8, 0))
    high = _placed_xyz(_HOLE_HOST, (_HOLE_X0 + 12, 12, 10))
    center = _placed_xyz(_HOLE_HOST, (_HOLE_X0 + 10, 10, 5))
    got_low, got_high = p.get("min_point") or {}, p.get("max_point") or {}
    got_center = p.get("center") or {}
    return _measured(
        "fresh scoped bore face bounds",
        {"kind": p.get("kind"), "units": p.get("units"),
         "x": p.get("x"), "y": p.get("y"), "z": p.get("z"),
         "min": got_low, "max": got_high, "center": got_center},
        p.get("kind") == "face" and p.get("units") == "mm"
        and _near(p.get("x"), 4.0, 0.01) and _near(p.get("y"), 4.0, 0.01)
        and _near(p.get("z"), 10.0, 0.01)
        and all(_near(got_low.get(axis), want, 0.01)
                for axis, want in zip(("x", "y", "z"), low))
        and all(_near(got_high.get(axis), want, 0.01)
                for axis, want in zip(("x", "y", "z"), high))
        and all(_near(got_center.get(axis), want, 0.01)
                for axis, want in zip(("x", "y", "z"), center)))


def _hole_host_tree(p):
    """The component-rooted tree names both B bodies and publishes consumable handles."""
    tree = p.get("tree") or {}
    node = tree.get("tree") or {}
    bodies = node.get("bodies") or []
    return _measured(
        "HoleHostB component-rooted body tree",
        {"root": tree.get("root"), "component": node.get("component"),
         "body_count": node.get("body_count"),
         "bodies": [(b.get("name"), bool(b.get("handle"))) for b in bodies]},
        tree.get("root") == _HOLE_HOST and tree.get("truncated") is False
        and node.get("component") == _HOLE_HOST and node.get("body_count") == 2
        and [b.get("name") for b in bodies] == ["Body1", "Body2"]
        and all(isinstance(b.get("handle"), str) and b["handle"]
                and b.get("is_solid") is True for b in bodies))


def _hole_upper_handle(p):
    """The exact upper-body handle from the component-rooted tree."""
    bodies = ((p.get("tree") or {}).get("tree") or {}).get("bodies") or []
    hit = [b.get("handle") for b in bodies if b.get("name") == "Body1"]
    if len(hit) != 1 or not isinstance(hit[0], str) or not hit[0]:
        raise AssertionError(f"HoleHostB Body1 handle is not unique: {hit!r}")
    return hit[0]


def _hole_lower_handle(p):
    """The exact lower-body handle from the component-rooted tree."""
    bodies = ((p.get("tree") or {}).get("tree") or {}).get("bodies") or []
    hit = [b.get("handle") for b in bodies if b.get("name") == "Body2"]
    if len(hit) != 1 or not isinstance(hit[0], str) or not hit[0]:
        raise AssertionError(f"HoleHostB Body2 handle is not unique: {hit!r}")
    return hit[0]


def _hole_active_tree(p):
    """The component-rooted tree names A's sole body and its consumable handle."""
    tree = p.get("tree") or {}
    node = tree.get("tree") or {}
    bodies = node.get("bodies") or []
    return _measured(
        "ActiveA component-rooted body tree",
        {"root": tree.get("root"), "component": node.get("component"),
         "body_count": node.get("body_count"),
         "bodies": [(b.get("name"), bool(b.get("handle"))) for b in bodies]},
        tree.get("root") == _HOLE_ACTIVE and tree.get("truncated") is False
        and node.get("component") == _HOLE_ACTIVE and node.get("body_count") == 1
        and [b.get("name") for b in bodies] == ["Body1"]
        and isinstance(bodies[0].get("handle"), str) and bodies[0]["handle"]
        and bodies[0].get("is_solid") is True)


def _hole_active_handle(p):
    """The exact A-body handle from the component-rooted tree."""
    bodies = ((p.get("tree") or {}).get("tree") or {}).get("bodies") or []
    hit = [b.get("handle") for b in bodies if b.get("name") == "Body1"]
    if len(hit) != 1 or not isinstance(hit[0], str) or not hit[0]:
        raise AssertionError(f"ActiveA Body1 handle is not unique: {hit!r}")
    return hit[0]


def _hole_inspect_args(ctx, key):
    """Mass-and-bounds arguments consuming one retained body handle."""
    return {"target": _ctx_get(ctx, key, "hole fixture body"), "include": ["default", "mass"],
            "units": "mm", "accuracy": "very_high"}


def _hole_cylinder_args(ctx, key):
    """Cylinder-census arguments consuming one retained body handle."""
    return {"target": _ctx_get(ctx, key, "hole fixture body"), "kind": "cylinder_face",
            "radius": 2, "units": "mm", "max_results": 10}


def _hole_point_while_active_a(x, y, z):
    """A B-authored point before the layout wrapper adds active A's offset."""
    return [_px(_HOLE_HOST, x) - _px(_HOLE_ACTIVE, 0.0),
            _py(_HOLE_HOST, y) - _py(_HOLE_ACTIVE, 0.0), z]


def _scoped_top_args(ctx):
    """The upper-face acquisition at the scoped bore point."""
    return {"target": _ctx_get(ctx, "hh_upper", "HoleHostB upper body"),
            "kind": "planar_face",
            "nearest_to": _hole_point_while_active_a(_HOLE_X0 + 10, 10, 10),
            "units": "mm", "max_results": 1}


def _control_top_args(ctx):
    """The upper-face acquisition at the positive-control bore point."""
    return {"target": _ctx_get(ctx, "hh_upper", "HoleHostB upper body"),
            "kind": "planar_face",
            "nearest_to": _hole_point_while_active_a(_HOLE_X0 + 5, 5, 10),
            "units": "mm", "max_results": 1}


def _scoped_bore_args(ctx):
    """The complete post-write bore census on the retained upper-body handle."""
    return {"target": _ctx_get(ctx, "hh_upper", "HoleHostB upper body"),
            "kind": "cylinder_face", "radius": 2, "units": "mm", "max_results": 1}


def _scoped_hole_args(ctx):
    """The upper-only hole arguments while ActiveA remains the runtime edit target."""
    return {"face": _ctx_get(ctx, "hh_top", "HoleHostB upper top face"),
            "hole_type": "simple", "diameter": "4 mm", "extent": "through",
            "points_space": "world", "units": "mm",
            "points": [_hole_point_while_active_a(_HOLE_X0 + 10, 10, 10)],
            "target_bodies": [_ctx_get(ctx, "hh_upper", "HoleHostB upper body")]}


def _unscoped_hole_args(ctx):
    """The positive-control hole arguments with target_bodies intentionally absent."""
    return {"face": _ctx_get(ctx, "hh_top_control", "HoleHostB upper top face"),
            "hole_type": "simple", "diameter": "4 mm", "extent": "through",
            "points_space": "world", "units": "mm",
            "points": [_hole_point_while_active_a(_HOLE_X0 + 5, 5, 10)]}


def _hole_created(scoped):
    """model_hole reports the face host and the exact participant mode."""
    def check(p):
        scope = p.get("scoped_to_bodies")
        scope_ok = (scope == [f"{_HOLE_HOST}:1:Body1"] if scoped
                    else "scoped_to_bodies" not in p)
        suffix = "1" if scoped else "2"
        return _measured(
            "scoped hole" if scoped else "unscoped positive-control hole",
            {"feature": p.get("feature"), "host": p.get("host_component"),
             "sketch": p.get("placement_sketch"), "scope": scope},
            p.get("holes") == 1 and p.get("holes_verified") is True
            and p.get("host_from_face") is True and p.get("host_verified") is True
            and p.get("host_component") == _HOLE_HOST
            and p.get("world_lift_component") == _HOLE_HOST
            and p.get("points_space") == "world" and p.get("feature") == f"Hole{suffix}"
            and p.get("placement_sketch") == f"Sketch{int(suffix) + 2}" and scope_ok)
    return check


def _hole_timeline(control):
    """The complete bounded timeline locates each hole and placement sketch in B."""
    def check(p):
        timeline = p.get("timeline") or {}
        rows = timeline.get("timeline") or []
        required = {("Sketch3", "Sketch", _HOLE_HOST),
                    ("Hole1", "HoleFeature", _HOLE_HOST)}
        if control:
            required |= {("Sketch4", "Sketch", _HOLE_HOST),
                         ("Hole2", "HoleFeature", _HOLE_HOST)}
        got = {(r.get("name"), r.get("type"), r.get("component")) for r in rows}
        active_a_holes = [r.get("name") for r in rows
                          if r.get("component") == _HOLE_ACTIVE
                          and r.get("type") == "HoleFeature"]
        count, returned = timeline.get("count"), timeline.get("returned")
        return _measured(
            "complete bounded hole-host timeline",
            {"count": count, "returned": returned, "required": sorted(required - got),
             "active_a_holes": active_a_holes, "truncated": timeline.get("truncated")},
            isinstance(count, int) and count <= 2000 and returned == count == len(rows)
            and timeline.get("truncated") is not True and required <= got
            and not active_a_holes)
    return check


def _radius_body_size(label, diameter_mm):
    """A 10 mm cylinder whose diameter is precise enough to settle the radius boundary."""
    def check(p):
        return _measured(
            label,
            {"x": p.get("x"), "y": p.get("y"), "z": p.get("z")},
            _near(p.get("x"), diameter_mm, _RADIUS_DIAMETER_TOL_MM)
            and _near(p.get("y"), diameter_mm, _RADIUS_DIAMETER_TOL_MM)
            and _near(p.get("z"), 10.0, 0.01))
    return check


def _radius_filtered_handle(ctx, filtered_key, index):
    """One actual radius-filtered handle for independent body-size readback."""
    filtered = _ctx_get(ctx, filtered_key, "the radius-filtered handles")
    if not isinstance(filtered, list):
        raise AssertionError(f"filtered handles {filtered!r} are not a list")
    if not 0 <= index < len(filtered):
        raise AssertionError(f"filtered handle index {index} is outside {len(filtered)} handles")
    return {"target": filtered[index], "units": "mm"}


def _precision_geometry(kind, units):
    """Check analytic radii and positions without rounding away the journal's tolerance span."""
    def check(p):
        rows = sorted(p.get("matches") or [], key=lambda row: row.get("radius", 0))
        factor = 25.4 if units == "mm" else 1.0
        count = 2 if kind == "cylinder_face" else 4
        radii = [0.312125, 0.88575] if count == 2 else [0.312125] * 2 + [0.88575] * 2
        good = len(rows) == p.get("match_count") == count and p.get("units") == units
        for row, radius in zip(rows, radii):
            position = row.get("position") or []
            cx = 0.123456 if radius == 0.312125 else 3.654321
            good = (good and row.get("kind") == kind
                    and _near(row.get("radius"), radius * factor, 0.000001)
                    and len(position) == 3
                    and _near(position[0], _px("PrecisionBench", (cx + 100) * 25.4)
                              * factor / 25.4, 0.000001)
                    and _near(position[1], _py("PrecisionBench", 0.234567 * 25.4)
                              * factor / 25.4, 0.000001))
            if radius == 0.88575:
                diameter = 2 * row.get("radius", 0) / factor
                good = good and 1.7714 <= diameter <= 1.7716
        return _measured("close-tolerance acquired " + kind + " in " + units,
                         [{k: row.get(k) for k in ("radius", "position", "handle")} for row in rows], good)
    return check


def _precision_planes(units):
    """Check the four planar caps and their world frames against their analytic heights."""
    def check(p):
        rows = p.get("matches") or []
        factor = 1 if units == "mm" else 1 / 25.4
        return _measured("precise planar cap frames in " + units, rows,
                         len(rows) == p.get("match_count") == 4
                         and all(row.get("kind") == "planar_face" and row.get("frame")
                                 and _near(row["frame"]["origin"][2], row["position"][2], 0.000001)
                                 and any(_near(row["frame"]["origin"][2], z * factor, 0.000001)
                                         for z in (0, 10)) for row in rows)
                         and sum(_near(row["frame"]["origin"][2], 10 * factor, 0.000001)
                                 for row in rows) == 2)
    return check


def _precision_ellipse(units):
    """Check both analytic ellipse edges, including precise radii and world centers."""
    def check(p):
        rows = sorted(p.get("matches") or [], key=lambda row: (row.get("position") or [0, 0, 0])[2])
        factor = 1 if units == "mm" else 1 / 25.4
        center = [_px("PrecisionEllipseBench", 2700 + 0.123456 * 25.4),
                  _py("PrecisionEllipseBench", 0.234567 * 25.4)]
        good = len(rows) == p.get("match_count") == 2 and p.get("units") == units
        for row, z in zip(rows, (0, 10.123456)):
            position = row.get("position") or []
            good = (good and row.get("kind") == "ellipse_edge" and bool(row.get("handle"))
                    and _near(row.get("major_radius"), 0.88575 * 25.4 * factor, 0.000001)
                    and _near(row.get("minor_radius"), 0.312125 * 25.4 * factor, 0.000001)
                    and len(position) == 3
                    and all(_near(actual, expected * factor, 0.000001)
                            for actual, expected in zip(position, [*center, z])))
        return _measured("precise ellipse radii and centers in " + units, rows, good)
    return check


def _precision_vertex_points():
    """The eight independently authored box corners in world millimetres."""
    return [[_px("PrecisionVertexBench", 2800 + x * 25.4),
             _py("PrecisionVertexBench", y * 25.4), z]
            for x in (0.123456, 0.765432) for y in (0.234567, 0.876543)
            for z in (0, 10.123456)]


def _precision_vertices(units):
    """Check all fractional-coordinate vertices against the authored corner set."""
    def check(p):
        rows = p.get("matches") or []
        factor = 1 if units == "mm" else 1 / 25.4
        expected = sorted(_precision_vertex_points())
        good = (len(rows) == p.get("match_count") == 8 and p.get("units") == units
                and all(row.get("kind") == "vertex" and row.get("handle")
                        and len(row.get("position") or []) == 3 for row in rows))
        if good:
            actual = sorted(row["position"] for row in rows)
            good = all(_near(a, e * factor, 0.000001)
                       for point, wanted in zip(actual, expected) for a, e in zip(point, wanted))
        return _measured("precise fractional vertices in " + units, rows, good)
    return check


def _precision_vertex_bounds(p):
    """Independently confirm the vertex coupon's world bounds through model_inspect."""
    points = _precision_vertex_points()
    low, high = p.get("min_point") or {}, p.get("max_point") or {}
    return _measured("independent fractional vertex bounds", p,
                     all(_near(bound.get(axis), choose(q[i] for q in points), 0.000001)
                         for bound, choose in ((low, min), (high, max))
                         for i, axis in enumerate("xyz")))


def _precision_edge_gap(height, units):
    """Check actual cap-edge spacing and the measured endpoints in the requested units."""
    def check(p):
        expected = height if units == "mm" else height / 25.4
        a, b = p.get("closest_point_on_a") or {}, p.get("closest_point_on_b") or {}
        zs = [a.get("z"), b.get("z")]
        return _measured("independent cap-edge spacing in " + units, p,
                         p.get("mode") == "distance" and p.get("units") == units
                         and all(str(p.get(key, "")).startswith("edge '") for key in ("a", "b"))
                         and _near(p.get("distance"), expected, 0.000001)
                         and all(_near(a.get(axis), b.get(axis), 0.000001) for axis in ("x", "y"))
                         and all(isinstance(z, (int, float)) and not isinstance(z, bool) for z in zs)
                         and _near(min(zs), 0, 0.000001) and _near(max(zs), expected, 0.000001))
    return check


def _precision_rows():
    """Cross-check cylinder, ellipse and vertex acquisitions in inches and mm."""
    rows = [("design_activate_component", {"occurrence": "root"}, "ok", None),
            ("model_create_component", {"name": "PrecisionBench", "activate": True,
                                         "x": 2540}, _made_component, None)]
    for name, radius, cx in (("PrecisionLug", 0.312125, 0.123456),
                             ("PrecisionJournal", 0.88575, 3.654321)):
        rows += [
            ("sketch_create", {"plane": "xy", "name": name}, "ok", None),
            ("sketch_add_geometry", {"sketch_name": name, "units": "in", "geometry": [
                {"kind": "circle", "cx": cx, "cy": 0.234567, "radius": radius}]}, "ok", None),
            ("model_extrude", {"sketch_name": name, "distance": 10, "operation": "new"},
             _extruded, None),
        ]
    for units in ("in", "mm"):
        rows.append(("find_geometry", {"target": "PrecisionBench", "kind": "planar_face",
                                       "units": units}, _precision_planes(units), None))
        for kind in ("cylinder_face", "circular_edge"):
            key = "precision_" + kind + "_" + units
            rows.append(("find_geometry", {"target": "PrecisionBench", "kind": kind,
                                           "units": units}, _precision_geometry(kind, units),
                         (key, lambda p: [r["handle"] for r in sorted(
                             p["matches"], key=lambda row: row["radius"])])))
            for index, radius in enumerate([0.312125, 0.88575] if kind == "cylinder_face"
                                            else [0.312125] * 2 + [0.88575] * 2):
                rows.append(("model_inspect", lambda c, key=key, index=index: {
                    "target": _ctx_get(c, key, "the precise acquired handles")[index], "units": "mm"},
                    lambda p, radius=radius: _measured(
                        "independent acquired face or owning-body diameter",
                        {"x": p.get("x"), "y": p.get("y"), "z": p.get("z")},
                        _near(p.get("x"), radius * 50.8, 0.000002)
                        and _near(p.get("y"), radius * 50.8, 0.000002)
                        and _near(p.get("z"), 10, 0.000002)), None))
            if kind == "circular_edge":
                for first in (0, 2):
                    rows.append(("model_measure_between", lambda c, key=key, first=first, units=units: {
                        "a": _ctx_get(c, key, "the precise cap-edge handles")[first],
                        "b": _ctx_get(c, key, "the precise cap-edge handles")[first + 1],
                        "units": units}, _precision_edge_gap(10, units), None))
    rows += [
        ("design_activate_component", {"occurrence": "root"}, "ok", None),
        ("model_create_component", {"name": "PrecisionEllipseBench", "activate": True,
                                     "x": 2700}, _made_component, None),
        ("sketch_create", {"plane": "xy", "name": "PrecisionEllipse"}, "ok", None),
        ("sketch_add_geometry", {"sketch_name": "PrecisionEllipse", "units": "in", "geometry": [
            {"kind": "ellipse", "cx": 0.123456, "cy": 0.234567,
             "radius": 0.88575, "minor": 0.312125}]}, "ok", None),
        ("model_extrude", {"sketch_name": "PrecisionEllipse", "distance": 10.123456,
                           "operation": "new"}, _extruded, None),
    ]
    for units in ("in", "mm"):
        key = "precision_ellipse_" + units
        rows.append(("find_geometry", {"target": "PrecisionEllipseBench", "kind": "ellipse_edge",
                                       "units": units}, _precision_ellipse(units),
                     (key, lambda p: [r["handle"] for r in sorted(
                         p["matches"], key=lambda row: row["position"][2])])))
        for index in (0, 1):
            rows.append(("model_inspect", lambda c, key=key, index=index: {
                "target": _ctx_get(c, key, "the precise ellipse handles")[index], "units": "mm"},
                lambda p: _measured("independent ellipse owning-body extent", p,
                    _near(p.get("x"), 0.88575 * 50.8, 0.000002)
                    and _near(p.get("y"), 0.312125 * 50.8, 0.000002)
                    and _near(p.get("z"), 10.123456, 0.000001)
                    and _near((p.get("center") or {}).get("z"), 10.123456 / 2, 0.000001)), None))
        rows.append(("model_measure_between", lambda c, key=key, units=units: {
            "a": _ctx_get(c, key, "the precise ellipse cap-edge handles")[0],
            "b": _ctx_get(c, key, "the precise ellipse cap-edge handles")[1],
            "units": units}, _precision_edge_gap(10.123456, units), None))
    rows += [
        ("design_activate_component", {"occurrence": "root"}, "ok", None),
        ("model_create_component", {"name": "PrecisionVertexBench", "activate": True,
                                     "x": 2800}, _made_component, None),
        ("sketch_create", {"plane": "xy", "name": "PrecisionVertices"}, "ok", None),
        ("sketch_add_geometry", {"sketch_name": "PrecisionVertices", "units": "in", "geometry": [
            {"kind": "rectangle", "x1": 0.123456, "y1": 0.234567,
             "x2": 0.765432, "y2": 0.876543}]}, "ok", None),
        ("model_extrude", {"sketch_name": "PrecisionVertices", "distance": 10.123456,
                           "operation": "new"}, _extruded, None),
        ("model_inspect", {"target": "PrecisionVertexBench", "units": "mm"},
         _precision_vertex_bounds, None),
    ]
    for units in ("in", "mm"):
        rows.append(("find_geometry", {"target": "PrecisionVertexBench", "kind": "vertex",
                                       "units": units}, _precision_vertices(units), None))
    return rows


_PRECISION_READS = _precision_rows()


def _interference_pin(ctx, args):
    """Add the exact owned-document pin to one interference-fixture write."""
    return {**args, "expect_document": _ctx_get(
        ctx, "interference_scratch", "the interference scratch document")}


def _peg_faces_per_instance(p):
    """find_geometry over both Peg instances: one cylinder face per instance, each naming its own."""
    got = sorted(str(m.get("occurrence")) for m in p.get("matches") or [])
    return _measured("each Peg cylinder names the instance it was read through",
                     {"occurrences": got}, got == ["Peg:1", "Peg:2"])


def _separated_block_poses(p):
    """Read two 10 mm bodies whose world centers are 50 mm apart along X."""
    rows = {r.get("name"): r for r in p.get("occurrences", [])}
    a, b = rows.get("BlockA:1", {}), rows.get("BlockB:1", {})
    ca, cb = a.get("bbox_center", []), b.get("bbox_center", [])
    return _measured("separated scratch bodies have independent world poses",
                     {"a": a, "b": b},
                     a.get("body_count") == b.get("body_count") == 1
                     and a.get("bbox_size") == b.get("bbox_size") == [10, 10, 10]
                     and len(ca) == len(cb) == 3
                     and all(_near(y - x, d, 0.001) for x, y, d in
                             zip(ca, cb, [50, 0, 0])))


def _separated_interference(include_coincident_faces):
    """Check a complete clear result under one coincident-face policy."""
    def check(p):
        m = p.get("measured") or {}
        note = p.get("note") or ""
        policy = "included" if include_coincident_faces else "excluded"
        return _measured("separated scratch bodies: clear overlap, no fit claim",
                         {"measured": m, "note": note},
                         p.get("passed") is True and m.get("analysis_complete") is True
                         and m.get("interference_count") == 0
                         and m.get("pairs_analyzed") == 0 and m.get("pairs_pruned") == 1
                         and m.get("pairs_omitted") == 0
                         and p.get("tolerance_used", {}).get("coincident_faces_included")
                         is include_coincident_faces
                         and "compared solid bodies" in note
                         and "coincident faces " + policy in note
                         and "fits" not in note.lower())
    return check


def _interference_pair_named(p):
    """assembly_inspect_interference on the Peg/BlockA/BlockB rig: each of Peg's two instances
    interferes with its OWN block, named exactly - no '(or N more instance(s))' guess."""
    rows = (p.get("measured") or {}).get("interferences") or []
    by_pair = {tuple(sorted([r.get("occurrence_one"), r.get("occurrence_two")])): r for r in rows}
    a = by_pair.get(tuple(sorted(["Peg:1", "BlockA:1"])))
    b = by_pair.get(tuple(sorted(["Peg:2", "BlockB:1"])))
    no_candidates = not any("candidates" in k for r in rows for k in r)
    return _measured(
        "Peg:1 x BlockA:1 and Peg:2 x BlockB:1 named exactly, each with its own volume",
        {"pairs": sorted(by_pair), "vol_a": a and a.get("overlap_volume_cm3"),
         "vol_b": b and b.get("overlap_volume_cm3")},
        a is not None and b is not None and no_candidates
        and isinstance(a.get("overlap_volume_cm3"), (int, float)) and a["overlap_volume_cm3"] > 0
        and isinstance(b.get("overlap_volume_cm3"), (int, float)) and b["overlap_volume_cm3"] > 0)


def _shared_cube_overlap(volume, analyzed, pruned):
    """Require the reused two-placement part's independently sized overlap."""
    def check(p):
        rows = (p.get("measured") or {}).get("interferences") or []
        pair = [r for r in rows if {r.get("occurrence_one"), r.get("occurrence_two")}
                == {"OverlapPart:1", "OverlapPart:2"}]
        measured = p.get("measured") or {}
        return _measured("repeated component overlap volume and placed-body pair counts", measured,
                         p.get("passed") is False and len(pair) == 1
                         and measured.get("pair_unit") == "placed_body"
                         and measured.get("pairs_analyzed") == analyzed
                         and measured.get("pairs_pruned") == pruned
                         and measured.get("analysis_complete") is True
                         and measured.get("pairs_omitted") == 0
                         and _near(pair[0].get("overlap_volume_cm3"), volume, 0.001))
    return check


def _shared_cube_poses(body_count):
    """Read the body envelopes and 10 mm placement offset independently of interference."""
    def check(p):
        rows = {r.get("name"): r for r in p.get("occurrences", [])}
        a, b = rows.get("OverlapPart:1", {}), rows.get("OverlapPart:2", {})
        ca, cb = a.get("bbox_center", []), b.get("bbox_center", [])
        size = [20 if body_count == 1 else 70, 20, 20]
        return _measured("two shared parts overlap by 10 mm along X", {"first": a, "second": b},
                         a.get("component") == b.get("component") == "OverlapPart"
                         and a.get("body_count") == b.get("body_count") == body_count
                         and a.get("bbox_size") == b.get("bbox_size") == size
                         and len(ca) == len(cb) == 3
                         and all(_near(y - x, d, 0.001) for x, y, d in zip(ca, cb, [10, 0, 0])))
    return check


def _contact_part_poses(count):
    """Read the contact fixture's placed body count and independent envelope."""
    def check(p):
        rows = [r for r in p.get("occurrences", []) if r.get("name") == "ContactPart:1"]
        return _measured("contact bodies span 40 x 20 x 20 mm", {"rows": rows},
                         len(rows) == 1 and rows[0].get("body_count") == count
                         and all(_near(x, y, 0.001) for x, y in
                                 zip(rows[0].get("bbox_size", []), [40, 20, 20]))
                         and len(rows[0].get("bbox_size", [])) == 3)
    return check


def _contact_overlap(volumes):
    """Require separate rows for the contact fixture, including a colliding root-body label."""
    def check(p):
        measured = p.get("measured") or {}
        rows = [r for r in measured.get("interferences", [])
                if r.get("occurrence_one") == r.get("occurrence_two") == "ContactPart:1"]
        got = sorted((r.get("overlap_volume_cm3") for r in rows),
                     key=lambda v: v if isinstance(v, (int, float)) else math.inf)
        return _measured("contact and overlap results preserve physical pairs", {"rows": rows},
                         measured.get("analysis_complete") is True
                         and len(got) == len(volumes)
                         and (not volumes or p.get("passed") is False)
                         and all(_near(a, b, 0.001) for a, b in zip(got, volumes)))
    return check


def _interference_budget(p):
    """Require a partial self-volume when the dense body's pair count exceeds the limit."""
    m = p.get("measured") or {}
    rows = [r for r in m.get("interferences", [])
            if r.get("occurrence_one") == r.get("occurrence_two") == "BudgetPart:1"]
    return _measured("dense overlap stops with disclosed omitted pairs and partial volume", m,
                     p.get("passed") is False and m.get("analysis_complete") is False
                     and 0 < m.get("pairs_analyzed", 0) <= 5000
                     and m.get("pairs_omitted", 0) > 0
                     and len(rows) == 1 and rows[0].get("partial") is True
                     and isinstance(rows[0].get("overlap_volume_cm3"), (int, float))
                     and 0 < rows[0]["overlap_volume_cm3"] < 34133.96)


def _fractional_helix_cap(p, turns=1.1, start_z=100):
    """Read the piped spline's end cap at the requested fractional-turn endpoint."""
    wanted = [10 * math.cos(2 * turns * math.pi), 10 * math.sin(2 * turns * math.pi),
              start_z + 10 * turns]
    positions = [r.get("position", []) for r in p.get("matches", [])]
    return _measured(f"{turns:g}-turn helix end cap at {360 * turns:g} degrees",
                     {"positions": positions, "expected": wanted},
                     any(len(at) == 3 and all(_near(a, b, 0.002) for a, b in zip(at, wanted))
                         for at in positions))


def _combine_story_address(p):
    """Return the story handle while recording the open-document baseline."""
    _RECALL["combine_open_before"] = p.get("open_count")
    return _home_address(p)


def _combine_owned_active(key):
    """The new owned document is the sole active row and opened beside the story."""
    def check(p):
        active = p.get("active") or {}
        rows = [r for r in (p.get("open_documents") or []) if r.get("is_active")]
        return _measured(
            "owned combine document active at its exact handle",
            {"active": active.get("document_handle"), "owned": _RECALL.get(key),
             "open_count": p.get("open_count"), "before": _RECALL.get("combine_open_before")},
            len(rows) == 1 and active.get("document_handle") == _RECALL.get(key)
            and rows[0].get("document_handle") == _RECALL.get(key)
            and p.get("open_count") == _RECALL.get("combine_open_before") + 1)
    return check


def _combine_story_restored(p):
    """The owned document is gone and the original story handle is active again."""
    active = p.get("active") or {}
    rows = [r for r in (p.get("open_documents") or []) if r.get("is_active")]
    return _measured(
        "combine scratch closed and story document restored",
        {"active": active.get("document_handle"), "story": _RECALL.get("combine_story"),
         "open_count": p.get("open_count"), "before": _RECALL.get("combine_open_before")},
        len(rows) == 1 and active.get("document_handle") == _RECALL.get("combine_story")
        and rows[0].get("document_handle") == _RECALL.get("combine_story")
        and p.get("open_count") == _RECALL.get("combine_open_before"))


def _combine_census(label, bodies, low, high, volume, kind="design"):
    """A complete body census with exact names, lump counts, total volume and bounds."""
    expected = sorted((name, body_volume, 1) for name, body_volume, _lo, _hi in bodies)

    def check(p):
        mass = p.get("mass") or {}
        rows = mass.get("per_body") or []
        got = sorted((r.get("body"), r.get("volume"), r.get("lump_count")) for r in rows)
        bounds = ((p.get("min_point") or {}), (p.get("max_point") or {}))
        bounds_ok = all(_near(point.get(axis), want, 0.01)
                        for point, wanted in zip(bounds, (low, high))
                        for axis, want in zip(("x", "y", "z"), wanted))
        return _measured(
            label + " complete body census",
            {"count": mass.get("per_body_count"), "returned": len(rows),
             "truncated": mass.get("per_body_truncated"), "bodies": got,
             "volume": mass.get("volume"), "min": bounds[0], "max": bounds[1]},
            p.get("kind") == kind and p.get("units") == "mm"
            and mass.get("accuracy_used") == "very_high"
            and mass.get("per_body_count") == len(expected) == len(rows)
            and mass.get("per_body_truncated") is False and got == expected
            and _near(mass.get("volume"), volume, 0.001) and bounds_ok)
    return check


def _combine_body(label, low, high, volume):
    """One result or restored body has exact bounds, volume and one connected lump."""
    def check(p):
        mass = p.get("mass") or {}
        bounds = ((p.get("min_point") or {}), (p.get("max_point") or {}))
        bounds_ok = all(_near(point.get(axis), want, 0.01)
                        for point, wanted in zip(bounds, (low, high))
                        for axis, want in zip(("x", "y", "z"), wanted))
        return _measured(
            label + " body bounds and volume",
            {"kind": p.get("kind"), "units": p.get("units"), "lumps": p.get("lump_count"),
             "volume": mass.get("volume"), "min": bounds[0], "max": bounds[1]},
            p.get("kind") == "body" and p.get("units") == "mm"
            and mass.get("accuracy_used") == "very_high" and p.get("lump_count") == 1
            and _near(mass.get("volume"), volume, 0.001) and bounds_ok)
    return check


def _combine_join_outcome(outcome, result_bodies, result_lumps):
    """The combine response reports one complete result/lump classification."""
    def check(p):
        note = p.get("note") or ""
        note_ok = ("partially fused" in note and "fused NOTHING" not in note
                   if outcome == "partial" else
                   ("fused NOTHING" in note if outcome == "none" else "WARNING" not in note))
        return _measured(
            outcome + " join result/lump report",
            {"outcome": p.get("fusion_outcome"), "fused": p.get("fused"),
             "body_count": p.get("result_body_count"),
             "bodies_complete": p.get("result_bodies_complete"),
             "input_lumps": p.get("input_lump_total"),
             "result_lumps": p.get("result_lump_total"), "feature": p.get("feature")},
            p.get("fusion_outcome") == outcome
            and p.get("fused") is (outcome != "none")
            and p.get("result_body_count") == result_bodies
            and p.get("result_bodies_complete") is True
            and p.get("input_lump_total") == 3 and p.get("result_lump_total") == result_lumps
            and p.get("feature") == "Combine1" and note_ok)
    return check


def _combine_timeline(prefix, joined, component=None):
    """The bounded timeline is exactly the authored host, bodies and optional combine."""
    wanted = [(f"{prefix}{i}", "Sketch", component) if j % 2 == 0
              else (f"Extrude{i + 1}", "ExtrudeFeature", component)
              for i in range(3) for j in range(2)]
    if component:
        wanted.insert(0, (" " + component + ":1", "Occurrence", None))
    if joined:
        wanted.append(("Combine1", "CombineFeature", component))

    def check(p):
        timeline = p.get("timeline") or {}
        rows = timeline.get("timeline") or []
        got = [(r.get("name"), r.get("type"), r.get("component") if component else None)
               for r in rows]
        return _measured(
            ("complete combine timeline" if joined else
             ("restored combine timeline" if component else "restored six-row timeline")),
            {"count": timeline.get("count"), "returned": timeline.get("returned"),
             "truncated": timeline.get("truncated"), "rows": got},
            timeline.get("count") == timeline.get("returned") == len(wanted) == len(rows)
            and timeline.get("truncated") is not True and got == wanted)
    return check


def _combine_deleted(p, index=6):
    """Only the authored Combine1 feature at the expected timeline index was deleted."""
    return _measured(
        "Combine1 deleted by exact feature name",
        {"deleted": p.get("deleted"), "feature": p.get("feature"),
         "index": p.get("index"), "entity_type": p.get("entity_type")},
        p.get("deleted") is True and p.get("feature") == "Combine1"
        and p.get("index") == index and p.get("entity_type") == "CombineFeature")


def _combine_nonroot_component(p):
    """The non-root host reports its transformed occurrence and active component."""
    position = p.get("position") or {}
    return _measured(
        "transformed non-root combine host",
        {"occurrence": p.get("occurrence"), "component": p.get("component"),
         "position": position, "rotate_deg": p.get("rotate_deg"),
         "rotate_axis": p.get("rotate_axis"), "activated": p.get("activated")},
        p.get("created") is True and p.get("occurrence") == "JoinProxyHost:1"
        and p.get("component") == "JoinProxyHost"
        and p.get("full_path") == "JoinProxyHost:1" and p.get("units") == "mm"
        and [position.get(axis) for axis in ("x", "y", "z")] == [100, 40, 30]
        and _near(p.get("rotate_deg"), 90, 0.001) and p.get("rotate_axis") == "z"
        and p.get("activated") is True)


def _combine_face(position):
    """One planar-face handle was acquired at the expected world position."""
    def check(p):
        matches = p.get("matches") or []
        got = matches[0] if len(matches) == 1 else {}
        return _measured(
            "qualified non-root planar face",
            {"count": p.get("match_count"), "returned": p.get("returned"),
             "kind": got.get("kind"), "position": got.get("position")},
            p.get("units") == "mm" and p.get("match_count") == 6
            and p.get("returned") == len(matches) == 1
            and got.get("kind") == "planar_face"
            and isinstance(got.get("handle"), str) and bool(got["handle"])
            and len(got.get("position") or []) == len(position)
            and all(_near(a, b, 0.01) for a, b in zip(got["position"], position))
            and len(got.get("normal") or []) == 3
            and all(_near(a, b, 0.001) for a, b in zip(got["normal"], (0, 0, 1))))
    return check


def _combine_pin(ctx, key, args):
    """Add the exact owned-document pin to one write."""
    return {**args, "expect_document": _ctx_get(ctx, key, "the combine scratch document")}


def _combine_inspect(target=""):
    """The canonical bounds, mass and complete per-body read arguments."""
    args = {"include": ["default", "mass"], "units": "mm", "accuracy": "very_high"}
    if target:
        args["target"] = target
    else:
        args["per_body"] = True
    return args


def _combine_case_rows(case, rectangles, before, after):
    """Build one isolated root-parametric complete/partial/none combine control."""
    owned = "combine_" + case + "_doc"
    prefix = "Join" + case.title()
    low = tuple(min(body[2][i] for body in before) for i in range(3))
    high = tuple(max(body[3][i] for body in before) for i in range(3))
    before_volume = sum(body[1] for body in before)
    after_low = tuple(min(body[2][i] for body in after) for i in range(3))
    after_high = tuple(max(body[3][i] for body in after) for i in range(3))
    after_volume = sum(body[1] for body in after)
    rows = [
        ("doc_new",
         lambda c: {"expect_document": _ctx_get(c, "combine_story", "the story document")},
         _new_document, (owned, _recall(owned, lambda p: p["document_handle"]))),
        ("doc_get", {}, _combine_owned_active(owned), None),
    ]
    if case == "complete":
        # This scratch document never enters Manufacture, so the CAM-product refusal and the
        # library listing that needs no such product make a discriminating PAIR on it: the machine
        # catalog hangs off CAMManager.libraryManager, which the document does not own.
        rows += [
            ("cam_get", {}, _refused("no CAM"), None),
            ("cam_get", {"include": ["machines"], "vendor": "Haas", "machine_type": "milling"},
             lambda p: p.get("machines", {}).get("count", 0) > 0 and "setups" not in p, None),
        ]
    for i, (x1, x2) in enumerate(rectangles):
        rows += [
            ("sketch_create",
             lambda c, name=f"{prefix}{i}": _combine_pin(
                 c, owned, {"plane": "xy", "name": name}), "ok", None),
            ("sketch_add_geometry",
             lambda c, name=f"{prefix}{i}", x1=x1, x2=x2: _combine_pin(
                 c, owned, {"geometry": [{"kind": "rectangle", "x1": x1, "y1": 0,
                                          "x2": x2, "y2": 10}],
                            "sketch_name": name}), "ok", None),
            ("model_extrude",
             lambda c, name=f"{prefix}{i}": _combine_pin(
                 c, owned, {"sketch_name": name, "profile_index": 0,
                            "distance": 10, "operation": "new"}), _extruded, None),
        ]
    if case == "complete":
        rows += [
            ("find_geometry", {"target": "Body1", "kind": "planar_face",
                               "nearest_to": [5, 5, 10], "max_results": 1},
             "ok", _fg("combine_self_a")),
            ("find_geometry", {"target": "Body1", "kind": "planar_face",
                               "nearest_to": [5, 5, 0], "max_results": 1},
             "ok", _fg("combine_self_b")),
            ("model_combine",
             lambda c: _combine_pin(
                 c, owned, {"target": _ctx_get(c, "combine_self_a", "combine target"),
                            "tools": [_ctx_get(c, "combine_self_b", "the same body again")],
                            "operation": "join"}),
             _refused("same as the target", "distinct bodies"), None),
        ]
    rows += [
        ("model_inspect", _combine_inspect(),
         _combine_census(case + " before", before, low, high, before_volume), None),
    ]
    rows += [("model_inspect", _combine_inspect(name),
              _combine_body(case + " before " + name, body_low, body_high, volume), None)
             for name, volume, body_low, body_high in before]
    rows += [
        ("model_combine",
         lambda c: _combine_pin(c, owned, {"target": "Body1", "tools": ["Body2", "Body3"],
                                                   "operation": "join", "keep_tools": False,
                                                   "new_component": False}),
         _combine_join_outcome(case, len(after), len(after)), None),
        ("model_inspect", _combine_inspect(),
         _combine_census(case + " after", after, after_low, after_high, after_volume), None),
    ]
    rows += [("model_inspect", _combine_inspect(name),
              _combine_body(case + " after " + name, body_low, body_high, volume), None)
             for name, volume, body_low, body_high in after]
    rows += [
        ("design_get", {"include": ["timeline"], "max_results": 7},
         _combine_timeline(prefix, True), None),
        ("design_delete_feature",
         lambda c: _combine_pin(c, owned, {"feature": "Combine1"}), _combine_deleted, None),
        ("model_inspect", _combine_inspect(),
         _combine_census(case + " restored", before, low, high, before_volume), None),
    ]
    rows += [("model_inspect", _combine_inspect(name),
              _combine_body(case + " restored " + name, body_low, body_high, volume), None)
             for name, volume, body_low, body_high in before]
    rows += [
        ("design_get", {"include": ["timeline"], "max_results": 6},
         _combine_timeline(prefix, False), None),
        ("doc_activate",
         lambda c: {"name": _ctx_get(c, "combine_story", "the story document"),
                    "expect_document": _ctx_get(c, owned, "the combine scratch document")},
         "ok", None),
        ("doc_close",
         lambda c: {"name": _ctx_get(c, owned, "the combine scratch document"),
                    "save_changes": False,
                    "expect_document": _ctx_get(c, "combine_story", "the story document")},
         _document_closed, None),
        ("doc_get", {}, _combine_story_restored, None),
    ]
    return rows


_COMBINE_COMPLETE = _combine_case_rows(
    "complete", ((0, 20), (10, 30), (20, 40)),
    (("Body1", 2000.0, (0, 0, 0), (20, 10, 10)),
     ("Body2", 2000.0, (10, 0, 0), (30, 10, 10)),
     ("Body3", 2000.0, (20, 0, 0), (40, 10, 10))),
    (("Body1", 4000.0, (0, 0, 0), (40, 10, 10)),))

_COMBINE_PARTIAL = _combine_case_rows(
    "partial", ((0, 20), (10, 30), (50, 60)),
    (("Body1", 2000.0, (0, 0, 0), (20, 10, 10)),
     ("Body2", 2000.0, (10, 0, 0), (30, 10, 10)),
     ("Body3", 1000.0, (50, 0, 0), (60, 10, 10))),
    (("Body1", 3000.0, (0, 0, 0), (30, 10, 10)),
     ("Body4", 1000.0, (50, 0, 0), (60, 10, 10))))

_COMBINE_NONE = _combine_case_rows(
    "none", ((0, 20), (30, 50), (60, 80)),
    (("Body1", 2000.0, (0, 0, 0), (20, 10, 10)),
     ("Body2", 2000.0, (30, 0, 0), (50, 10, 10)),
     ("Body3", 2000.0, (60, 0, 0), (80, 10, 10))),
    (("Body1", 2000.0, (0, 0, 0), (20, 10, 10)),
     ("Body4", 2000.0, (30, 0, 0), (50, 10, 10)),
     ("Body5", 2000.0, (60, 0, 0), (80, 10, 10))))


def _combine_nonroot_partial_rows():
    """Build one transformed non-root partial join with proxy-face tool handles."""
    owned = "combine_nonroot_partial_doc"
    component = "JoinProxyHost"
    occurrence = component + ":1"
    before = (
        ("Body1", 2000.0, (90, 40, 30), (100, 60, 40)),
        ("Body2", 2000.0, (90, 50, 30), (100, 70, 40)),
        ("Body3", 1000.0, (90, 90, 30), (100, 100, 40)),
    )
    after = (
        ("Body1", 3000.0, (90, 40, 30), (100, 70, 40)),
        ("Body4", 1000.0, (90, 90, 30), (100, 100, 40)),
    )
    rows = [
        ("doc_new",
         lambda c: {"expect_document": _ctx_get(c, "combine_story", "the story document")},
         _new_document, (owned, _recall(owned, lambda p: p["document_handle"]))),
        ("doc_get", {}, _combine_owned_active(owned), None),
        ("model_create_component",
         lambda c: _combine_pin(
             c, owned, {"name": component, "x": 100, "y": 40, "z": 30,
                        "rotate_deg": 90, "rotate_axis": "z", "activate": True}),
         _combine_nonroot_component, None),
    ]
    for i, (x1, x2) in enumerate(((0, 20), (10, 30), (50, 60))):
        rows += [
            ("sketch_create",
             lambda c, name=f"ProxyBox{i}": _combine_pin(
                 c, owned, {"plane": "xy", "name": name}), "ok", None),
            ("sketch_add_geometry",
             lambda c, name=f"ProxyBox{i}", x1=x1, x2=x2: _combine_pin(
                 c, owned, {"geometry": [{"kind": "rectangle", "x1": x1, "y1": 0,
                                          "x2": x2, "y2": 10}],
                            "sketch_name": name}), "ok", None),
            ("model_extrude",
             lambda c, name=f"ProxyBox{i}": _combine_pin(
                 c, owned, {"sketch_name": name, "profile_index": 0,
                            "distance": 10, "operation": "new"}), _extruded, None),
        ]
    rows += [
        ("model_inspect", {**_combine_inspect(occurrence), "per_body": True},
         _combine_census("non-root partial before", before,
                         (90, 40, 30), (100, 100, 40), 5000.0, "occurrence"), None),
    ]
    rows += [
        ("model_inspect", _combine_inspect(occurrence + ":" + name),
         _combine_body("non-root partial before " + name, low, high, volume), None)
        for name, volume, low, high in before
    ]
    rows += [
        ("find_geometry", {"target": occurrence + ":Body2", "kind": "planar_face",
                           "nearest_to": [95, 60, 40], "max_results": 1},
         _combine_face((95, 60, 40)), _fg("combine_nonroot_tool_a")),
        ("find_geometry", {"target": occurrence + ":Body3", "kind": "planar_face",
                           "nearest_to": [95, 95, 40], "max_results": 1},
         _combine_face((95, 95, 40)), _fg("combine_nonroot_tool_b")),
        ("model_combine",
         lambda c: _combine_pin(
             c, owned, {"target": occurrence + ":Body1",
                        "tools": [_ctx_get(c, "combine_nonroot_tool_a", "Body2 planar face"),
                                  _ctx_get(c, "combine_nonroot_tool_b", "Body3 planar face")],
                        "operation": "join", "keep_tools": False, "new_component": False}),
         _combine_join_outcome("partial", 2, 2), None),
        ("model_inspect", {**_combine_inspect(occurrence), "per_body": True},
         _combine_census("non-root partial after", after,
                         (90, 40, 30), (100, 100, 40), 4000.0, "occurrence"), None),
    ]
    rows += [
        ("model_inspect", _combine_inspect(occurrence + ":" + name),
         _combine_body("non-root partial after " + name, low, high, volume), None)
        for name, volume, low, high in after
    ]
    rows += [
        ("design_get", {"include": ["timeline"], "max_results": 8},
         _combine_timeline("ProxyBox", True, component), None),
        ("design_delete_feature",
         lambda c: _combine_pin(c, owned, {"feature": "Combine1"}),
         lambda p: _combine_deleted(p, 7), None),
        ("model_inspect", {**_combine_inspect(occurrence), "per_body": True},
         _combine_census("non-root partial restored", before,
                         (90, 40, 30), (100, 100, 40), 5000.0, "occurrence"), None),
    ]
    rows += [
        ("model_inspect", _combine_inspect(occurrence + ":" + name),
         _combine_body("non-root partial restored " + name, low, high, volume), None)
        for name, volume, low, high in before
    ]
    rows += [
        ("design_get", {"include": ["timeline"], "max_results": 7},
         _combine_timeline("ProxyBox", False, component), None),
        ("doc_activate",
         lambda c: {"name": _ctx_get(c, "combine_story", "the story document"),
                    "expect_document": _ctx_get(c, owned, "the combine scratch document")},
         "ok", None),
        ("doc_close",
         lambda c: {"name": _ctx_get(c, owned, "the combine scratch document"),
                    "save_changes": False,
                    "expect_document": _ctx_get(c, "combine_story", "the story document")},
         _document_closed, None),
        ("doc_get", {}, _combine_story_restored, None),
    ]
    return rows


_COMBINE_NONROOT_PARTIAL = _combine_nonroot_partial_rows()

_REVOLVE_HOST = "RevolveProof"
_REVOLVE_OCCURRENCE = _REVOLVE_HOST + ":1"
_REVOLVE_BASELINE = (
    ("Body1", 1280 * math.pi, (-10, -10, 0), (10, 10, 20)),
    ("Body2", 500 * math.pi, (-5, -5, 0), (5, 5, 20)),
    ("Body3", 80 * math.pi, (28, -2, 0), (32, 2, 20)),
)


def _revolve_story_address(p):
    """Return the story handle while recording the open-document baseline."""
    _RECALL["revolve_open_before"] = p.get("open_count")
    return _home_address(p)


def _revolve_owned_active(p):
    """Require the new revolve document beside the exact story document."""
    active = p.get("active") or {}
    rows = [row for row in (p.get("open_documents") or []) if row.get("is_active")]
    return _measured(
        "owned revolve document active at its exact handle",
        {"active": active.get("document_handle"), "owned": _RECALL.get("revolve_participant_doc"),
         "open_count": p.get("open_count"), "before": _RECALL.get("revolve_open_before")},
        len(rows) == 1
        and active.get("document_handle") == _RECALL.get("revolve_participant_doc")
        and rows[0].get("document_handle") == _RECALL.get("revolve_participant_doc")
        and p.get("open_count") == _RECALL.get("revolve_open_before") + 1)


def _revolve_story_restored(p):
    """Require the revolve document gone and the exact story document active."""
    active = p.get("active") or {}
    rows = [row for row in (p.get("open_documents") or []) if row.get("is_active")]
    return _measured(
        "revolve scratch closed and story document restored",
        {"active": active.get("document_handle"), "story": _RECALL.get("revolve_story"),
         "open_count": p.get("open_count"), "before": _RECALL.get("revolve_open_before")},
        len(rows) == 1 and active.get("document_handle") == _RECALL.get("revolve_story")
        and rows[0].get("document_handle") == _RECALL.get("revolve_story")
        and p.get("open_count") == _RECALL.get("revolve_open_before"))


def _revolve_pin(ctx, args):
    """Add the exact owned-document pin to one revolve-fixture write."""
    return {**args, "expect_document": _ctx_get(
        ctx, "revolve_participant_doc", "the revolve scratch document")}


def _revolve_census(label, bodies):
    """Require one complete participant census with analytical volume and world bounds."""
    expected = {name: (volume, low, high) for name, volume, low, high in bodies}
    low = tuple(min(body[2][i] for body in bodies) for i in range(3))
    high = tuple(max(body[3][i] for body in bodies) for i in range(3))

    def check(p):
        mass = p.get("mass") or {}
        rows = mass.get("per_body") or []
        got = {row.get("body"): row for row in rows}
        bounds = (p.get("min_point") or {}, p.get("max_point") or {})
        bounds_ok = all(_near(point.get(axis), want, 0.01)
                        for point, wanted in zip(bounds, (low, high))
                        for axis, want in zip(("x", "y", "z"), wanted))
        bodies_ok = (
            set(got) == set(expected) and len(rows) == len(expected)
            and all(row.get("is_solid") is True and row.get("lump_count") == 1
                    and _near(row.get("volume"), expected[name][0], 0.001)
                    for name, row in got.items()))
        return _measured(
            label + " revolve participant census",
            {"count": mass.get("per_body_count"), "returned": len(rows),
             "truncated": mass.get("per_body_truncated"),
             "bodies": sorted((name, row.get("volume"), row.get("lump_count"))
                              for name, row in got.items()),
             "volume": mass.get("volume"), "min": bounds[0], "max": bounds[1]},
            p.get("kind") == "occurrence" and p.get("units") == "mm"
            and mass.get("accuracy_used") == "very_high"
            and mass.get("per_body_count") == len(expected) == len(rows)
            and mass.get("per_body_truncated") is False and bodies_ok
            and _near(mass.get("volume"), sum(body[1] for body in bodies), 0.001)
            and bounds_ok)
    return check


def _revolve_cut(profile, feature, result_bodies, scoped, volume_delta_cm3):
    """Require the reported cut scope/results and its material-effect mode."""
    def check(p):
        scope = p.get("scoped_to_bodies")
        scope_ok = (scope == [_REVOLVE_OCCURRENCE + ":Body1"] if scoped
                    else "scoped_to_bodies" not in p)
        if volume_delta_cm3 is None:
            effect_ok = ("volume_delta_cm3" not in p
                         and "body count changed" in (p.get("note") or ""))
        else:
            effect_ok = _near(p.get("volume_delta_cm3"), volume_delta_cm3, 0.000001)
        return _measured(
            profile + " revolve cut result",
            {"feature": p.get("feature"), "operation": p.get("operation"),
             "results": p.get("result_bodies"), "scope": scope,
             "volume_delta_cm3": p.get("volume_delta_cm3")},
            p.get("revolved") is True and p.get("feature") == feature
            and p.get("operation") == "cut" and p.get("sketch") == profile
            and p.get("component") == _REVOLVE_HOST and p.get("axis") == "z-axis"
            and _near(p.get("angle_deg"), 360.0, 0.000001)
            and p.get("result_bodies") == list(result_bodies) and scope_ok and effect_ok)
    return check


def _revolve_deleted(feature):
    """Require deletion of the exact temporary RevolveFeature."""
    def check(p):
        return _measured(
            feature + " deleted",
            {"deleted": p.get("deleted"), "feature": p.get("feature"),
             "index": p.get("index"), "entity_type": p.get("entity_type")},
            p.get("deleted") is True and p.get("feature") == feature
            and p.get("index") == 9 and p.get("entity_type") == "RevolveFeature")
    return check


def _revolve_groove_face(p):
    """Require the new radius-9 groove face at world z=7.5 mm."""
    matches = p.get("matches") or []
    groove = [row for row in matches
              if _near(row.get("radius"), 9.0, 0.001)
              and len(row.get("position") or []) == 3
              and _near(row["position"][2], 7.5, 0.01)]
    return _measured(
        "radius-9 groove face at its axial position",
        {"count": p.get("match_count"), "returned": p.get("returned"),
         "groove": [(row.get("radius"), row.get("position"), row.get("area"))
                    for row in groove], "truncated": p.get("truncated")},
        p.get("units") == "mm" and p.get("match_count") == p.get("returned") == len(matches)
        and p.get("truncated") is not True and len(groove) == 1
        and _near(groove[0].get("area"), 90 * math.pi, 0.001))


def _revolve_body_rows(label, bodies):
    """Build separate mass-and-bounds reads for every expected participant body."""
    return [
        ("model_inspect", _combine_inspect(_REVOLVE_OCCURRENCE + ":" + name),
         _combine_body(label + " " + name, low, high, volume), None)
        for name, volume, low, high in bodies
    ]


def _revolve_participant_rows():
    """Build one isolated scoped, unscoped and splitting revolve-cut proof."""
    scoped = (
        ("Body1", 1055 * math.pi, (-10, -10, 0), (10, 10, 20)),
        _REVOLVE_BASELINE[1], _REVOLVE_BASELINE[2])
    unscoped = (
        scoped[0],
        ("Body2", 420 * math.pi, (-5, -5, 0), (5, 5, 20)),
        _REVOLVE_BASELINE[2])
    split = (
        ("Body1", 320 * math.pi, (-10, -10, 0), (10, 10, 5)),
        _REVOLVE_BASELINE[1], _REVOLVE_BASELINE[2],
        ("Body4", 640 * math.pi, (-10, -10, 10), (10, 10, 20)))
    rows = [
        ("doc_get", {}, _home_document,
         ("revolve_story", _recall("revolve_story", _revolve_story_address))),
        ("doc_new",
         lambda c: {"expect_document": _ctx_get(c, "revolve_story", "the story document")},
         _new_document, ("revolve_participant_doc", _recall(
             "revolve_participant_doc", lambda p: p["document_handle"]))),
        ("doc_get", {}, _revolve_owned_active, None),
        ("model_create_component",
         lambda c: _revolve_pin(c, {"name": _REVOLVE_HOST, "activate": True}),
         _made_component, None),
        ("sketch_create",
         lambda c: _revolve_pin(c, {"name": "RingProfile", "plane": "xz"}), "ok", None),
        ("sketch_add_geometry",
         lambda c: _revolve_pin(c, {
             "sketch_name": "RingProfile",
             "geometry": [{"kind": "rectangle", "x1": 6, "y1": -20, "x2": 10, "y2": 0}]}),
         "ok", None),
        ("model_revolve",
         lambda c: _revolve_pin(c, {
             "sketch_name": "RingProfile", "axis": "z", "angle_deg": 360}),
         _revolved, None),
        ("sketch_create",
         lambda c: _revolve_pin(c, {"name": "InnerProfile", "plane": "xy"}), "ok", None),
        ("sketch_add_geometry",
         lambda c: _revolve_pin(c, {
             "sketch_name": "InnerProfile",
             "geometry": [{"kind": "circle", "cx": 0, "cy": 0, "radius": 5}]}),
         "ok", None),
        ("model_extrude",
         lambda c: _revolve_pin(c, {
             "sketch_name": "InnerProfile", "distance": 20, "operation": "new"}),
         _extruded, None),
        ("sketch_create",
         lambda c: _revolve_pin(c, {"name": "DecoyProfile", "plane": "xy"}), "ok", None),
        ("sketch_add_geometry",
         lambda c: _revolve_pin(c, {
             "sketch_name": "DecoyProfile",
             "geometry": [{"kind": "circle", "cx": 30, "cy": 0, "radius": 2}]}),
         "ok", None),
        ("model_extrude",
         lambda c: _revolve_pin(c, {
             "sketch_name": "DecoyProfile", "distance": 20, "operation": "new"}),
         _extruded, None),
        ("sketch_create",
         lambda c: _revolve_pin(c, {"name": "GrooveProfile", "plane": "xz"}), "ok", None),
        ("sketch_add_geometry",
         lambda c: _revolve_pin(c, {
             "sketch_name": "GrooveProfile",
             "geometry": [{"kind": "rectangle", "x1": 3, "y1": -10, "x2": 9, "y2": -5}]}),
         "ok", None),
        ("sketch_create",
         lambda c: _revolve_pin(c, {"name": "BandProfile", "plane": "xz"}), "ok", None),
        ("sketch_add_geometry",
         lambda c: _revolve_pin(c, {
             "sketch_name": "BandProfile",
             "geometry": [{"kind": "rectangle", "x1": 0, "y1": -10, "x2": 11, "y2": -5}]}),
         "ok", None),
        ("model_inspect", {**_combine_inspect(_REVOLVE_OCCURRENCE), "per_body": True},
         _revolve_census("baseline", _REVOLVE_BASELINE), None),
    ]
    rows += _revolve_body_rows("baseline", _REVOLVE_BASELINE)
    cases = (
        ("scoped", "GrooveProfile", "Revolve2", ("Body1",), True,
         -225 * math.pi / 1000, scoped),
        ("unscoped", "GrooveProfile", "Revolve3", ("Body1", "Body2"), False,
         -305 * math.pi / 1000, unscoped),
        ("split", "BandProfile", "Revolve4", ("Body1", "Body4"), True, None, split),
    )
    for label, profile, feature, result_bodies, is_scoped, delta, after in cases:
        def cut_args(c, profile=profile, is_scoped=is_scoped):
            args = {"sketch_name": profile, "component": _REVOLVE_HOST, "axis": "z",
                    "operation": "cut", "angle_deg": 360}
            if is_scoped:
                args["target_bodies"] = [_REVOLVE_HOST + ":Body1"]
            return _revolve_pin(c, args)

        rows += [
            ("model_revolve", cut_args,
             _revolve_cut(profile, feature, result_bodies, is_scoped, delta), None),
            ("model_inspect", {**_combine_inspect(_REVOLVE_OCCURRENCE), "per_body": True},
             _revolve_census(label, after), None),
        ]
        rows += _revolve_body_rows(label, after)
        if profile == "GrooveProfile":
            rows += [
                ("find_geometry", {"target": _REVOLVE_OCCURRENCE + ":Body1",
                                   "kind": "cylinder_face", "units": "mm", "max_results": 100},
                 _revolve_groove_face, None),
            ]
        rows += [
            ("design_delete_feature",
             lambda c, feature=feature: _revolve_pin(c, {"feature": feature}),
             _revolve_deleted(feature), None),
            ("model_inspect", {**_combine_inspect(_REVOLVE_OCCURRENCE), "per_body": True},
             _revolve_census(label + " restored", _REVOLVE_BASELINE), None),
        ]
        rows += _revolve_body_rows(label + " restored", _REVOLVE_BASELINE)
    rows += [
        ("doc_activate",
         lambda c: {"name": _ctx_get(c, "revolve_story", "the story document"),
                    "expect_document": _ctx_get(
                        c, "revolve_participant_doc", "the revolve scratch document")},
         "ok", None),
        ("doc_close",
         lambda c: {"name": _ctx_get(c, "revolve_participant_doc",
                                     "the revolve scratch document"),
                    "save_changes": False,
                    "expect_document": _ctx_get(c, "revolve_story", "the story document")},
         _document_closed, None),
        ("doc_get", {}, _revolve_story_restored, None),
    ]
    return rows


_REVOLVE_PARTICIPANTS = _revolve_participant_rows()


def _hole_definition(extent, units, tapped=False):
    """Check native hole extent and hidden child independently of the drilling response."""
    def check(p):
        row = p.get("definition") or {}
        thread = row.get("thread") or {}
        factor = 1 if units == "mm" else 1 / 25.4
        good = (row.get("type") == "HoleFeature" and row.get("component") == "DefinitionBench"
                and row.get("units") == units and row.get("extent") == extent
                and row.get("tapped") is tapped and row.get("thread_present") is tapped
                and row.get("depth_applicable") is (extent == "blind"))
        if tapped:
            info, child_info = row.get("tapped_hole_info") or {}, thread.get("thread_info") or {}
            full = thread.get("full_length")
            length, offset = thread.get("length"), thread.get("offset")
            numeric = (length is None and offset is None if full is True else
                       isinstance(length, (int, float)) and length > 0
                       and isinstance(offset, (int, float)) and offset >= 0)
            good = (good and _near(row.get("depth"), 22.225 * factor, 0.000001)
                    and row.get("diameter_parameter_applicable") is False
                    and row.get("diameter_parameter") is None
                    and info.get("designation") == "3/8-16 UNC"
                    and all(isinstance(info.get(key), str) and bool(info[key])
                            and child_info.get(key) == info[key]
                            for key in ("designation", "thread_type", "thread_class"))
                    and thread.get("type") == "ThreadFeature" and isinstance(full, bool)
                    and thread.get("length_applicable") is (not full)
                    and thread.get("offset_applicable") is (not full)
                    and isinstance(thread.get("modeled"), bool) and numeric)
            if units == "in":
                prior = (_RECALL.get("def_tap_mm") or {}).get("thread") or {}
                good = (good and child_info == prior.get("thread_info")
                        and all(thread.get(key) == prior.get(key) for key in
                                ("full_length", "modeled", "length_applicable", "offset_applicable"))
                        and all(thread.get(key) is None if prior.get(key) is None else
                                _near(thread.get(key), prior[key] / 25.4, 0.000001)
                                for key in ("length", "offset")))
        else:
            good = (good and row.get("depth") is None and row.get("thread") is None
                    and _near(row.get("diameter_parameter"), 4 * factor, 0.000001)
                    and row.get("diameter_parameter_applicable") is True)
        return _measured("hole definition and actual child in " + units, row, good)
    return check


def _thread_definition(full, units):
    """Check standalone full/partial thread metadata without inferring full-thread length."""
    def check(p):
        row = p.get("definition") or {}
        info = row.get("thread_info") or {}
        factor = 1 if units == "mm" else 1 / 25.4
        lengths = (row.get("length") is None and row.get("offset") is None if full else
                   _near(row.get("length"), 12 * factor, 0.000001)
                   and _near(row.get("offset"), 2 * factor, 0.000001))
        return _measured("standalone thread definition in " + units, row,
                         row.get("type") == "ThreadFeature" and row.get("component") == "DefinitionPost"
                         and row.get("units") == units and row.get("modeled") is False
                         and row.get("full_length") is full
                         and row.get("length_applicable") is (not full)
                         and row.get("offset_applicable") is (not full) and lengths
                         and info.get("designation") == "M10x1.5" and info.get("thread_class") == "6g"
                         and info.get("thread_type") == "ISO Metric profile"
                         and info.get("internal") is False)
    return check


def _definition_doc_state(p):
    """The active document identity and readable modified flag for a paired read check."""
    modified = (p.get("active") or {}).get("is_modified")
    if not isinstance(modified, bool):
        raise AssertionError("document modified state did not read")
    return {"document_handle": _home_address(p), "is_modified": modified}


def _tapped_created_ref(key, component="DefinitionBench"):
    """Retain the actual creation disclosure and return its scoped feature reference."""
    def capture(p):
        _RECALL[key] = p
        return component + "/" + p["feature"]
    return capture


def _tapped_control_definition(key, full=None, extent="blind", modeled=False, component="DefinitionBench"):
    """Compare the tapped-hole disclosure with its independent native definition reader."""
    def check(p):
        row, made = p.get("definition") or {}, _RECALL.get(key) or {}
        child = row.get("thread") or {}
        info = child.get("thread_info") or {}
        mapping = {"thread_full_length": "full_length", "thread_length_applicable": "length_applicable",
                   "thread_offset_applicable": "offset_applicable", "modeled": "modeled"}
        good = (row.get("type") == "HoleFeature" and row.get("component") == component
                and row.get("extent") == extent and row.get("depth_applicable") is (extent == "blind")
                and (_near(row.get("depth"), 22.225, 0.000001) if extent == "blind" else row.get("depth") is None)
                and row.get("tapped") is True and row.get("thread_present") is True
                and row.get("diameter_parameter") is None
                and row.get("diameter_parameter_applicable") is False
                and row.get("tapped_hole_info") == info and info.get("internal") is True
                and row.get("feature") == made.get("feature")
                and row.get("units") == made.get("units") == "mm"
                and info.get("designation") == made.get("tapped") == "3/8-16 UNC"
                and info.get("thread_type") == made.get("thread_type") == "ANSI Unified Screw Threads"
                and isinstance(info.get("thread_class"), str) and bool(info["thread_class"])
                and info.get("thread_class") == made.get("thread_class")
                and isinstance(child.get("full_length"), bool) and child.get("modeled") is modeled
                and all(key in made and made[key] == child.get(value) for key, value in mapping.items())
                and all(key in made and (made[key] is None if child.get(value) is None else
                        _near(made[key], child[value], 0.000001))
                        for key, value in (("thread_length", "length"), ("thread_offset", "offset"))))
        if full is not None:
            good = (good and info.get("thread_class") == "2B" and child.get("full_length") is full
                    and child.get("length_applicable") is (not full)
                    and child.get("offset_applicable") is (not full)
                    and (child.get("length") is None and child.get("offset") is None if full else
                         _near(child.get("length"), 12, 0.000001)
                         and _near(child.get("offset"), 2, 0.000001)))
        return _measured("tapped controls and actual creation disclosure", row, good)
    return check


def _tapped_geometry(p):
    """Capture the complete coupon face/edge measurements without transient handles."""
    matches = p.get("matches") or []
    if not matches or p.get("match_count") != len(matches) or p.get("returned") != len(matches):
        raise AssertionError("tapped coupon geometry acquisition was empty or capped")
    return [{key: value for key, value in row.items() if key != "handle"} for row in matches]


def _tapped_control_rows():
    """Exercise explicit and omitted tapped controls on the existing definition coupon."""
    rows = [("design_get", lambda c: {"include": ["definition"], "units": "mm",
             "feature": _ctx_get(c, "def_tap", "default tap")},
             _tapped_control_definition("def_tap_created"), None)]
    for extra, refusal in (({}, _refused("thread_length")),
                           ({"thread_length": 40, "thread_offset": 2}, _refused("THREAD_OVER_EXTENT"))):
        rows.append(("design_get", {"include": ["timeline"], "max_results": 1000}, "ok",
                     ("def_rejected_timeline", _recall("def_rejected_timeline", lambda p: p["timeline"]))))
        rows.append(("find_geometry", {"target": "DefinitionBench", "max_results": 1000}, "ok",
                     ("def_rejected_geometry", _recall("def_rejected_geometry", _tapped_geometry))))
        rows.append(("model_hole", lambda c, extra=extra: _combine_pin(c, "def_doc", {
            "face": _ctx_get(c, "def_top", "top face"), "points_space": "world", "points": [[5, 17, 30]],
            "diameter": "0.3125 in", "extent": "blind", "depth": "0.875 in", "tap": "3/8-16 UNC",
            "thread_type": "ANSI Unified Screw Threads", "thread_class": "2B", "thread_extent": "partial",
            **extra}), refusal, None))
        rows.append(("design_get", {"include": ["timeline"], "max_results": 1000},
                     lambda p: _measured("invalid partial preserves timeline", p.get("timeline"),
                         bool(_RECALL.get("def_rejected_timeline"))
                         and p.get("timeline") == _RECALL["def_rejected_timeline"]), None))
        rows.append(("find_geometry", {"target": "DefinitionBench", "max_results": 1000},
                     lambda p: _measured("invalid partial preserves coupon geometry", p.get("match_count"),
                         _tapped_geometry(p) == _RECALL.get("def_rejected_geometry")), None))
    for full, point in ((True, [5, 17, 30]), (False, [17, 5, 30])):
        key = "def_control_full" if full else "def_control_partial"
        rows.append(("model_hole", lambda c, full=full, point=point: _combine_pin(c, "def_doc", {
            "face": _ctx_get(c, "def_top", "top face"), "points_space": "world", "points": [point],
            "diameter": "0.3125 in", "extent": "blind", "depth": "0.875 in", "tap": "3/8-16 UNC",
            "thread_type": "ANSI Unified Screw Threads", "thread_class": "2B",
            "thread_extent": "full" if full else "partial",
            **({} if full else {"thread_length": 12, "thread_offset": 2})}),
            _drilled(1), (key, _tapped_created_ref(key))))
        rows.append(("design_get", lambda c, key=key: {"include": ["definition"], "units": "mm",
                     "feature": _ctx_get(c, key, "controlled tap")},
                     _tapped_control_definition(key, full), None))
        rows.append(("find_geometry", {"target": "DefinitionBench", "kind": "cylinder_face",
                     "nearest_to": [point[0], point[1], 20], "max_results": 1},
                     lambda p, point=point: _measured("controlled tap bore location", p.get("matches"),
                         _matched(1, "cylinder_face")(p)
                         and _near(p["matches"][0]["position"][0], point[0], 0.000001)
                         and _near(p["matches"][0]["position"][1], point[1], 0.000001)
                         and p["matches"][0].get("radius", 0) > 0), None))
    def write(name, args):
        rows.append((name, lambda c, args=args: _combine_pin(c, "def_doc", args), "ok", None))
    write("design_activate_component", {"occurrence": "root"})
    write("model_create_component", {"name": "TapControlBench", "activate": True})
    write("sketch_create", {"plane": "xy", "name": "TapControlStock"})
    write("sketch_add_geometry", {"sketch_name": "TapControlStock", "geometry": [
        {"kind": "rectangle", "x1": 100, "y1": 0, "x2": 160, "y2": 25}]})
    write("model_extrude", {"sketch_name": "TapControlStock", "distance": 30})
    rows.append(("find_geometry", {"target": "TapControlBench", "kind": "planar_face",
                 "nearest_to": [130, 12.5, 30], "max_results": 1},
                 _face_up_at(130, 12.5, 30, 0.000001), _fg("def_control_top")))
    for extent, modeled, x in (("through", False, 110), ("blind", False, 130), ("blind", True, 150)):
        full = extent == "through"
        key = "def_control_through" if full else "def_control_modeled" if modeled else "def_control_cosmetic"
        rows.append(("model_inspect", _combine_inspect("TapControlBench"), "ok",
                     ("def_control_volume", _recall("def_control_volume", lambda p: p["mass"]["volume"]))))
        rows.append(("model_hole", lambda c, extent=extent, modeled=modeled, x=x, full=full: _combine_pin(
            c, "def_doc", {"face": _ctx_get(c, "def_control_top", "control stock top"),
                "points_space": "world", "points": [[x, 10, 30]], "diameter": "0.3125 in",
                "extent": extent, "tap": "3/8-16 UNC", "thread_type": "ANSI Unified Screw Threads",
                "thread_class": "2B", "thread_extent": "full" if full else "partial", "modeled": modeled,
                **({} if full else {"depth": "0.875 in", "thread_length": 12, "thread_offset": 2})}),
            _drilled(1), (key, _tapped_created_ref(key, "TapControlBench"))))
        rows.append(("design_get", lambda c, key=key: {"include": ["definition"], "units": "mm",
                     "feature": _ctx_get(c, key, "controlled tap")},
                     _tapped_control_definition(key, full, extent, modeled, "TapControlBench"), None))
        rows.append(("model_inspect", _combine_inspect("TapControlBench"),
                     lambda p, modeled=modeled: _measured("tap material removal and modeled helix excess", {
                         "mass": p.get("mass"), "before": _RECALL.get("def_control_volume"),
                         "cosmetic_removed": _RECALL.get("def_control_cosmetic_removed")},
                         p.get("units") == "mm" and isinstance(_RECALL.get("def_control_volume"), (int, float))
                         and isinstance((p.get("mass") or {}).get("volume"), (int, float))
                         and 0 < p["mass"]["volume"] < _RECALL["def_control_volume"] - 1
                         and (not modeled or isinstance(_RECALL.get("def_control_cosmetic_removed"), (int, float))
                              and _RECALL["def_control_volume"] - p["mass"]["volume"]
                                  > _RECALL["def_control_cosmetic_removed"] + 1)),
                     ("def_control_cosmetic_removed", _recall("def_control_cosmetic_removed",
                         lambda p: _RECALL["def_control_volume"] - p["mass"]["volume"]))
                     if not full and not modeled else None))
        if full:
            rows.append(("find_geometry", {"target": "TapControlBench", "kind": "cylinder_face",
                         "nearest_to": [110, 10, 15], "max_results": 1},
                         _matched(1, "cylinder_face"), _fg("def_control_bore")))
            rows.append(("model_inspect", lambda c: {"target": _ctx_get(c, "def_control_bore", "through tap bore")},
                         lambda p: _measured("through tap crosses stock", p,
                             _near(p.get("z"), 30, 0.000001)
                             and _near((p.get("center") or {}).get("x"), 110, 0.000001)
                             and _near((p.get("center") or {}).get("y"), 10, 0.000001)
                             and p.get("x", 0) > 0 and _near(p.get("x"), p.get("y"), 0.000001)), None))
    return rows


def _hole_feedback_rows():
    """Check expression refusals, live parameter links, and tap-controlled bore geometry."""
    rows = []
    def write(tool, args, check="ok", save=None):
        rows.append((tool, lambda c, args=args: _combine_pin(
            c, "def_doc", args(c) if callable(args) else args), check, save))
    write("design_activate_component", {"occurrence": "root"})
    write("model_create_component", {"name": "HoleFeedback", "activate": True})
    write("sketch_create", {"plane": "xy", "name": "HoleFeedbackStock"})
    write("sketch_add_geometry", {"sketch_name": "HoleFeedbackStock", "geometry": [
        {"kind": "rectangle", "x1": 200, "y1": 0, "x2": 260, "y2": 40}]})
    write("model_extrude", {"sketch_name": "HoleFeedbackStock", "distance": 30})
    rows.append(("find_geometry", lambda c: {"target": "HoleFeedback", "kind": "planar_face",
                 "nearest_to": [230, 20, 30], "max_results": 1}, _face_up_at(230, 20, 30, .000001), _fg("hf_top")))
    for field, value in (("diameter", "5/16 in"), ("depth", "MissingHoleDepth/2")):
        for tool, args, key, extract in (
                ("design_get", {"include": ["timeline"], "max_results": 1000}, "hf_timeline", lambda p: p["timeline"]),
                ("sketch_get", {"component": "HoleFeedback", "max_results": 1000}, "hf_sketches", lambda p: p),
                ("find_geometry", {"target": "HoleFeedback", "max_results": 1000}, "hf_geometry", _tapped_geometry)):
            rows.append((tool, args, "ok", (key, _recall(key, extract))))
        write("model_hole", lambda c, field=field, value=value: {
            "face": _ctx_get(c, "hf_top", "stock top"), "points_space": "world", "points": [[230, 10, 30]],
            "diameter": "4 mm", "extent": "blind", "depth": "12 mm", field: value},
            _refused(field, value, "0.3125 in"))
        for tool, args, key, extract in (
                ("design_get", {"include": ["timeline"], "max_results": 1000}, "hf_timeline", lambda p: p["timeline"]),
                ("sketch_get", {"component": "HoleFeedback", "max_results": 1000}, "hf_sketches", lambda p: p),
                ("find_geometry", {"target": "HoleFeedback", "max_results": 1000}, "hf_geometry", _tapped_geometry)):
            rows.append((tool, args, lambda p, key=key, extract=extract: _measured(
                "invalid hole preserves " + key, extract(p), bool(_RECALL.get(key))
                and extract(p) == _RECALL[key]), None))
    write("param_add", {"name": "FeedbackDia", "expression": "4 mm"}, _param_added("FeedbackDia", 4))
    write("param_add", {"name": "FeedbackDepth", "expression": "12 mm"}, _param_added("FeedbackDepth", 12))
    write("model_hole", lambda c: {"face": _ctx_get(c, "hf_top", "stock top"), "points_space": "world",
        "points": [[210, 10, 30]], "diameter": "FeedbackDia", "depth": "FeedbackDepth", "extent": "blind"},
        _drilled(1), ("hf_ordinary", _tapped_created_ref("hf_ordinary", "HoleFeedback")))
    rows.append(("design_get", {"include": ["timeline"], "timeline_params": True, "max_results": 1000},
        lambda p: _measured("hole preserves both parameter expressions", p.get("timeline"), any(
            row.get("name") == (_RECALL.get("hf_ordinary") or {}).get("feature")
            and row.get("component") == "HoleFeedback"
            and {"FeedbackDia", "FeedbackDepth"}.issubset({q.get("expression") for q in row.get("params") or []})
            for row in (p.get("timeline") or {}).get("timeline") or [])), None))
    for diameter in (4, 6):
        if diameter == 6:
            write("param_set", {"name": "FeedbackDia", "expression": "6 mm"}, _param_set_to("FeedbackDia", 6))
        rows.append(("design_get", lambda c: {"include": ["definition"], "feature": _ctx_get(c, "hf_ordinary", "hole")},
            lambda p, diameter=diameter: _measured("ordinary diameter remains applicable", p.get("definition"),
                (p.get("definition") or {}).get("diameter_parameter_applicable") is True
                and _near((p.get("definition") or {}).get("diameter_parameter"), diameter, .000001)
                and _near((p.get("definition") or {}).get("depth"), 12, .000001)), None))
        rows.append(("find_geometry", {"target": "HoleFeedback", "kind": "cylinder_face", "radius": diameter/2},
            lambda p, diameter=diameter: _matched(1, "cylinder_face")(p)
            and _measured("parameter drives actual hole radius", p["matches"],
                _near(p["matches"][0].get("radius"), diameter/2, .000001)
                and _near(p["matches"][0]["position"][0], 210, .000001)), None))
    rows.append(("workspace_orient", {}, lambda p: _measured(
        "numeric-string hole requires disclosed millimeter document units", p.get("design"),
        (p.get("design") or {}).get("units") == "mm"), None))
    write("model_hole", lambda c: {"face": _ctx_get(c, "hf_top", "stock top"), "points_space": "world",
        "points": [[250/25.4, 10/25.4, 30/25.4]], "units": "in", "diameter": "5",
        "depth": "12 mm", "extent": "blind"}, _drilled(1),
        ("hf_unitless", lambda p: "HoleFeedback/" + p["feature"]))
    rows.append(("design_get", lambda c: {"include": ["definition"], "units": "mm",
                 "feature": _ctx_get(c, "hf_unitless", "numeric-string hole")},
        lambda p: _measured("numeric-string diameter uses document units", p.get("definition"),
            (p.get("definition") or {}).get("diameter_parameter_applicable") is True
            and _near((p.get("definition") or {}).get("diameter_parameter"), 5, .000001)
            and _near((p.get("definition") or {}).get("depth"), 12, .000001)), None))
    rows.append(("find_geometry", {"target": "HoleFeedback", "kind": "cylinder_face", "radius": 2.5},
        lambda p: _matched(1, "cylinder_face")(p) and _measured("numeric-string hole actual bore", p["matches"],
            _near(p["matches"][0].get("radius"), 2.5, .000001)
            and _near(p["matches"][0]["position"][0], 250, .000001)
            and _near(p["matches"][0]["position"][1], 10, .000001)), None))
    for index, diameter in enumerate(("0.3125 in", "10 mm")):
        key, x = "hf_tap_" + str(index), 215 + 30*index
        write("model_hole", lambda c, diameter=diameter, x=x: {
            "face": _ctx_get(c, "hf_top", "stock top"), "points_space": "world", "points": [[x, 30, 30]],
            "diameter": diameter, "extent": "blind", "depth": "0.875 in", "tap": "3/8-16 UNC",
            "thread_type": "ANSI Unified Screw Threads", "thread_class": "2B", "thread_extent": "full"},
            lambda p, diameter=diameter: _drilled(1)(p) and _measured("writer discloses unused diameter", p.get("note"),
                ("diameter=" + repr(diameter) + " is unused") in p.get("note", "")),
            (key, _tapped_created_ref(key, "HoleFeedback")))
        rows.append(("design_get", {"include": ["timeline"], "max_results": 1000}, "ok",
                     ("hf_read_timeline", _recall("hf_read_timeline", lambda p: p["timeline"]))))
        rows.append(("doc_get", {}, _home_document,
                     ("hf_read_doc", _recall("hf_read_doc", _definition_doc_state))))
        rows.append(("design_get", lambda c, key=key: {"include": ["definition"], "units": "mm",
                     "feature": _ctx_get(c, key, "tap")},
                     _tapped_control_definition(key, True, "blind", False, "HoleFeedback"), None))
        rows.append(("design_get", {"include": ["timeline"], "max_results": 1000},
            lambda p: _measured("diameter read preserves marker and timeline", p.get("timeline"),
                bool(_RECALL.get("hf_read_timeline")) and p.get("timeline") == _RECALL["hf_read_timeline"]), None))
        rows.append(("doc_get", {}, lambda p: _measured("diameter read preserves document state", p.get("active"),
            _definition_doc_state(p) == _RECALL.get("hf_read_doc")), None))
        rows.append(("find_geometry", lambda c, x=x: {"target": "HoleFeedback", "kind": "cylinder_face",
                     "nearest_to": [x, 30, 20], "max_results": 1},
            lambda p, index=index, x=x: _matched(1, "cylinder_face")(p) and _measured(
                "tap bore ignores nominal diameter input", p["matches"],
                _near(p["matches"][0].get("radius"), 7.9756/2, .0001)
                and _near(p["matches"][0]["position"][0], x, .000001)
                and (index == 0 or _near(p["matches"][0].get("radius"), _RECALL.get("hf_tap_radius"), .000001))),
            ("hf_tap_radius", _recall("hf_tap_radius", lambda p: p["matches"][0]["radius"])) if index == 0 else None))
    return rows


def _definition_rows():
    """Build a bounded Hole/Thread read coupon in an owned scratch document."""
    rows = [("doc_get", {}, _home_document, ("def_story", _home_address)),
            ("doc_new", lambda c: {"expect_document": _ctx_get(c, "def_story", "story")},
             _new_document, ("def_doc", lambda p: p["document_handle"]))]
    def write(name, args, save=None):
        rows.append((name, lambda c, args=args: _combine_pin(
            c, "def_doc", args(c) if callable(args) else args), "ok", save))
    def read(key, check, units):
        rows.append(("design_get", lambda c, key=key, units=units: {
            "include": ["definition"], "feature": _ctx_get(c, key, "created feature"), "units": units},
            check, (key + "_mm", _recall(key + "_mm", lambda p: p["definition"]))
            if units == "mm" else None))
    def state(before):
        if before:
            rows.append(("doc_get", {}, _home_document,
                         ("def_active", _recall("def_active", _definition_doc_state))))
            rows.append(("design_get", {"include": ["timeline"]}, "ok",
                         ("def_timeline", _recall("def_timeline", lambda p: {
                             key: p["timeline"][key] for key in ("marker_position", "count")}))))
        else:
            rows.append(("design_get", {"include": ["timeline"]},
                         lambda p: _measured("definition read preserves timeline", p.get("timeline"),
                             all((p.get("timeline") or {}).get(key) == value for key, value in
                                 (_RECALL.get("def_timeline") or {}).items())
                             and bool(_RECALL.get("def_timeline"))), None))
            rows.append(("doc_get", {}, lambda p: _measured("definition read preserves document state",
                         _definition_doc_state(p), _definition_doc_state(p) == _RECALL.get("def_active")), None))
    write("model_create_component", {"name": "DefinitionBench", "activate": True})
    write("sketch_create", {"plane": "xy", "name": "DefinitionBlock"})
    write("sketch_add_geometry", {"sketch_name": "DefinitionBlock", "geometry": [
        {"kind": "rectangle", "x1": 0, "y1": 0, "x2": 25, "y2": 25}]})
    write("model_extrude", {"sketch_name": "DefinitionBlock", "distance": 30})
    rows.append(("find_geometry", {"target": "DefinitionBench", "kind": "planar_face",
                                   "nearest_to": [12.5, 12.5, 30], "max_results": 1},
                 _matched(1, "planar_face"), _fg("def_top")))
    for key, point, extra in (("def_through", [5, 5, 30], {"diameter": "4 mm", "extent": "through"}),
                              ("def_tap", [17, 17, 30], {"tap": "3/8-16 UNC", "diameter": "0.3125 in", "extent": "blind",
                                                          "depth": "0.875 in"})):
        write("model_hole", lambda c, point=point, extra=extra: {
            "face": _ctx_get(c, "def_top", "top face"), "points_space": "world", "points": [point],
            **extra}, (key, _tapped_created_ref("def_tap_created") if key == "def_tap" else
                        lambda p: "DefinitionBench/" + p["feature"]))
        state(True)
        for units in ("mm", "in"):
            read(key, _hole_definition(extra["extent"], units, key == "def_tap"), units)
        state(False)
    rows.append(("find_geometry", {"target": "DefinitionBench", "kind": "cylinder_face", "radius": 2},
                 _matched(1, "cylinder_face"), _fg("def_bore")))
    rows.append(("model_inspect", lambda c: {"target": _ctx_get(c, "def_bore", "through bore")},
                 lambda p: _measured("independent through-hole diameter/depth", p,
                                     _near(p.get("x"), 4, 0.00001) and _near(p.get("y"), 4, 0.00001)
                                     and _near(p.get("z"), 30, 0.00001)), None))
    rows += _tapped_control_rows()
    rows += _hole_feedback_rows()
    write("design_activate_component", {"occurrence": "root"})
    write("model_create_component", {"name": "DefinitionPost", "activate": True})
    write("sketch_create", {"plane": "xy", "name": "DefinitionPostS"})
    write("sketch_add_geometry", {"sketch_name": "DefinitionPostS", "geometry": [
        {"kind": "circle", "cx": 50, "cy": 0, "radius": 5}]})
    write("model_extrude", {"sketch_name": "DefinitionPostS", "distance": 25})
    rows.append(("find_geometry", {"target": "DefinitionPost", "kind": "cylinder_face"},
                 _matched(1, "cylinder_face"), _fg("def_post")))
    for full in (True, False):
        if not full:
            write("sketch_create", {"plane": "xy", "name": "DefinitionPartialS"})
            write("sketch_add_geometry", {"sketch_name": "DefinitionPartialS", "geometry": [
                {"kind": "circle", "cx": 70, "cy": 0, "radius": 5}]})
            write("model_extrude", {"sketch_name": "DefinitionPartialS", "distance": 25})
            rows.append(("find_geometry", {"target": "DefinitionPost", "kind": "cylinder_face",
                                           "nearest_to": [70, 0, 12.5], "max_results": 1},
                         _matched(1, "cylinder_face"), _fg("def_post")))
        write("model_thread", lambda c, full=full: {
            "faces": [_ctx_get(c, "def_post", "post cylinder")], "designation": "M10x1.5",
            "thread_type": "ISO Metric profile", "thread_class": "6g",
            **({} if full else {"length": 12, "offset": 2})},
            ("def_thread", lambda p: "DefinitionPost/" + p["feature"]))
        rows.append(("model_inspect", lambda c: {"target": _ctx_get(c, "def_post", "threaded cylinder")},
                     lambda p, full=full: _measured("capture threaded cylinder before definition reads", p,
                         all(isinstance(p.get(key), (int, float)) and math.isfinite(p[key]) and p[key] > 0
                             for key in ("x", "y"))
                         and _near(p.get("z"), 25, 0.00001)
                         and _near((p.get("center") or {}).get("x"), 50 if full else 70, 0.00001)),
                     ("def_thread_shape", _recall("def_thread_shape", lambda p: {
                         key: p[key] for key in ("kind", "units", "x", "y", "z", "min_point", "max_point", "center")}))))
        state(True)
        for units in ("mm", "in"):
            read("def_thread", _thread_definition(full, units), units)
        state(False)
        rows.append(("model_inspect", lambda c: {"target": _ctx_get(c, "def_post", "threaded cylinder")},
                     lambda p, full=full: _measured("definition reads preserve threaded cylinder geometry", p,
                                         bool(_RECALL.get("def_thread_shape"))
                                         and all(p.get(key) == value for key, value in
                                                 (_RECALL.get("def_thread_shape") or {}).items())
                                         and _near(p.get("z"), 25, 0.00001)
                                         and _near((p.get("center") or {}).get("x"),
                                                   50 if full else 70, 0.00001)), None))
    rows += [("doc_activate", lambda c: {"name": _ctx_get(c, "def_story", "story"),
                                        "expect_document": _ctx_get(c, "def_doc", "coupon")}, "ok", None),
             ("doc_close", lambda c: {"name": _ctx_get(c, "def_doc", "coupon"), "save_changes": False,
                                     "expect_document": _ctx_get(c, "def_story", "story")}, _document_closed, None)]
    return rows


_DEFINITION_READS = _definition_rows()


# OperandBench is turned 30 deg about world Z and moved (100, 200, 0) mm, so its XZ plane - the one
# OperandS sits on - has the normal R30 * (0, 1, 0) and holds the moved origin.
_OPERAND_NORMAL = [-math.sin(math.radians(30)), math.cos(math.radians(30)), 0.0]
_OPERAND_MOVE = [100.0, 200.0, 0.0]


def _operand_frame_read():
    """The OperandS frame sketch_get published, as recalled."""
    f = _RECALL.get("dop_frame") or {}
    if not all(isinstance(f.get(k), list) for k in ("origin_mm", "x_world", "y_world", "normal")):
        raise AssertionError(f"the OperandS frame did not read: {f!r}")
    return f


def _frame_world(u, v):
    """WORLD mm of OperandS point (u, v) mm, through the frame sketch_get read off its proxy."""
    f = _operand_frame_read()
    return [f["origin_mm"][i] + u * f["x_world"][i] + v * f["y_world"][i] for i in range(3)]


def _swung(u, v, sign):
    """WORLD mm of OperandS point (u, v) after a 90 deg turn, either way, about its sketch x axis."""
    n = _operand_frame_read()["normal"]
    return [a + sign * v * b for a, b in zip(_frame_world(u, 0), n)]


def _operand_at(got, want, tol=0.001):
    """True when a published [x, y, z] (or {x, y, z}) sits at `want` within `tol` mm."""
    if isinstance(got, dict):
        got = [got.get(k) for k in "xyz"]
    return isinstance(got, list) and len(got) == 3 and all(_near(a, b, tol) for a, b in zip(got, want))


def _on_moved_plane(normal, origin):
    """True when a plane (unit normal, origin mm) is OperandBench's XZ plane, turned and moved."""
    if isinstance(origin, dict):
        origin = [origin.get(k) for k in "xyz"]
    if not (isinstance(normal, list) and len(normal) == 3 and isinstance(origin, list)
            and len(origin) == 3 and all(isinstance(v, (int, float)) for v in normal + origin)):
        return False
    along = sum(a * b for a, b in zip(normal, _OPERAND_NORMAL))
    return (_near(abs(along), 1.0, 1e-5)
            and _near(sum(a * b for a, b in zip(normal, origin)),
                      sum(a * b for a, b in zip(normal, _OPERAND_MOVE)), 1e-3))


def _operand_frame(p):
    """sketch_get: OperandS's world frame lies on the turned, moved XZ plane."""
    f = p.get("frame") or {}
    return _measured("OperandS frame on the turned, moved XZ plane", f,
                     f.get("space") == "world" and _on_moved_plane(f.get("normal"),
                                                                    f.get("origin_mm")))


def _operand_ends(ends, a, b):
    """True when a line operand's two published world ends are `a` and `b`, in either order."""
    if not isinstance(ends, list) or len(ends) != 2:
        return False
    return ((_operand_at(ends[0], a) and _operand_at(ends[1], b))
            or (_operand_at(ends[0], b) and _operand_at(ends[1], a)))


def _operand_ids(p):
    """The sketch ids and handles of OperandS's three free points, found by sketch-local position."""
    out = {}
    for key, (x, y) in (("p1", (10, 20)), ("p2", (40, 20)), ("p3", (10, 50))):
        hits = [r for r in p.get("entities") or [] if r.get("type") == "point"
                and _near((r.get("position") or {}).get("x"), x, 1e-6)
                and _near((r.get("position") or {}).get("y"), y, 1e-6)]
        if len(hits) != 1:
            raise AssertionError(f"OperandS point ({x}, {y}) read {len(hits)} rows")
        (row,) = hits
        out[key], out[key + "_handle"] = row["id"], row.get("handle")
    return out


def _operand_xray(p):
    """sketch_get: every point and curve row carries a handle minted through OperandBench:1."""
    rows = [r for r in p.get("entities") or []
            if r.get("type") in ("point", "line", "circle", "arc", "spline")]
    return _measured("each sketch row prints its handle beside its id",
                     [(r.get("id"), r.get("handle")) for r in rows],
                     (p.get("frame") or {}).get("space") == "world" and len(rows) >= 12
                     and all(isinstance(r.get("handle"), str) and "|@sketch_" in r["handle"]
                             and r["handle"].endswith(";occ=OperandBench:1") for r in rows))


def _operand_match(kind, wants, shape=None):
    """find_geometry: ONE `kind` read through OperandBench:1 at one of `wants()` (world mm)."""
    def check(p):
        rows = p.get("matches") or []
        row = rows[0] if len(rows) == 1 else {}
        return _measured(f"one {kind} at its world position", rows,
                         len(rows) == 1 and row.get("kind") == kind
                         and any(_operand_at(row.get("position"), w) for w in wants())
                         and row.get("occurrence") == "OperandBench:1"
                         and f"|@{kind}:" in (row.get("handle") or "")
                         and (shape is None or shape(row)))
    return check


def _round_shape(u, v, radius):
    """A find_geometry arc/circle row's world centre is OperandS (u, v) and its radius `radius` mm."""
    return lambda row: (_operand_at(row.get("center"), _frame_world(u, v))
                        and _near(row.get("radius"), radius, 1e-6))


def _operand_rows_at(p, wants, path="OperandBench:1"):
    """The datum's 'operands' sit at `wants` (world mm), each read through `path`."""
    ops = p.get("operands") or []
    return (len(ops) == len(wants)
            and all(op.get("assembly_path") == path and _operand_at(op.get("world"), w)
                    for op, w in zip(ops, wants)))


def _operand_plane(wants, path="OperandBench:1"):
    """three_points: through every operand, on the turned and moved XZ plane, read back in world."""
    def check(p):
        g = p.get("geometry") or {}
        return _datum("plane")(p) and _measured(
            "a plane through three points of the turned, moved component",
            {"geometry": g, "through": p.get("passes_through_points"),
             "operands": p.get("operands")},
            p.get("passes_through_points") is True and _operand_rows_at(p, wants(), path)
            and _on_moved_plane(g.get("normal"), g.get("origin")))
    return check


def _operand_axis(direction, through=True):
    """An axis along the world `direction()` (either sense), through its operands when asked."""
    def check(p):
        d = (p.get("geometry") or {}).get("direction") or [0, 0, 0]
        dot = sum(a * b for a, b in zip(d, direction()))
        return _datum("axis")(p) and _measured(
            "an axis along the operands' world direction",
            {"direction": d, "through": p.get("passes_through_points"),
             "operands": p.get("operands")},
            _near(abs(dot), 1.0, 1e-5)
            and (not through or p.get("passes_through_points") is True))
    return check


def _operand_point(u, v, path="OperandBench:1"):
    """at_point: the datum sits at OperandS (u, v)'s world point, read back off the datum."""
    def check(p):
        want = _frame_world(u, v)
        return _datum("point")(p) and _measured(
            "a point datum at its operand's world point", p,
            p.get("at_operand") is True and _operand_at(p.get("world"), want)
            and _operand_rows_at(p, [want], path))
    return check


def _rediscovered_axis(p):
    """The acquired axis lies on OperandS's independently read world x line."""
    rows = p.get("matches") or []
    row = rows[0] if len(rows) == 1 else {}
    point, direction = row.get("position"), row.get("direction")
    anchor, along = _frame_world(0, 0), _operand_frame_read()["x_world"]
    if (not isinstance(point, list) or len(point) != 3
            or not isinstance(direction, list) or len(direction) != 3):
        return False
    dot = sum(a * b for a, b in zip(direction, along))
    delta = [a - b for a, b in zip(point, anchor)]
    cross = [delta[1] * along[2] - delta[2] * along[1],
             delta[2] * along[0] - delta[0] * along[2],
             delta[0] * along[1] - delta[1] * along[0]]
    return _measured("rediscovered placed axis has its independent world line", row,
                     p.get("match_count") == 1 and row.get("occurrence") == "OperandBench:1"
                     and "|@construction_axis:" in (row.get("handle") or "")
                     and _near(abs(dot), 1, 1e-5)
                     and sum(v * v for v in cross) ** 0.5 < 0.001)


def _swung_about_the_piece(p):
    """After the 90 deg turn about the first piece: its start stays, P1 swings to one side."""
    rows = [r.get("position") for r in p.get("matches") or []]
    swung = [r for r in rows if _operand_at(r, _swung(10, 20, 1)) or _operand_at(r, _swung(10, 20, -1))]
    return _measured("a point on the axis stays put and one off it swings 90 deg", rows,
                     p.get("match_count") == len(rows)
                     and any(_operand_at(r, _frame_world(0, 0)) for r in rows)
                     and len(swung) == 1
                     and not any(_operand_at(r, _frame_world(10, 20)) for r in rows))


def _datum_operand_rows():
    """Sketch -> point -> plane/axis on a turned, moved component's XZ plane, in a scratch document."""
    rows = [("doc_get", {}, _home_document, ("dop_story", _home_address)),
            ("doc_new", lambda c: {"expect_document": _ctx_get(c, "dop_story", "story")},
             _new_document, ("dop_doc", lambda p: p["document_handle"]))]

    def write(name, args, check="ok", save=None):
        rows.append((name, lambda c, args=args: _combine_pin(
            c, "dop_doc", args(c) if callable(args) else args), check, save))

    def read(name, args, check, save=None):
        rows.append((name, lambda c, args=args: args(c) if callable(args) else dict(args),
                     check, save))

    def ids(c):
        return _ctx_get(c, "dop_ids", "OperandS ids and handles")

    def acquire(kind, u, v, wants, shape=None, save=None):
        # With no frame recalled (its read failed) the query goes unsorted and the check says so.
        read("find_geometry", lambda c: {"target": "OperandBench", "kind": kind, "max_results": 1,
                                         **({"nearest_to": _frame_world(u, v)}
                                            if _RECALL.get("dop_frame") else {})},
             _operand_match(kind, wants, shape), save)

    write("model_create_component", {"name": "OperandBench", "activate": True},
          _made_component)
    # XZ, so the sketch transform is not the identity: every expected world point below comes
    # from the frame sketch_get reads off the sketch proxy, a path apart from the one under test.
    write("sketch_create", {"plane": "xz", "name": "OperandS"})
    write("sketch_add_geometry", {"sketch_name": "OperandS", "geometry": [
        {"kind": "point", "cx": 10, "cy": 20}, {"kind": "point", "cx": 40, "cy": 20},
        {"kind": "point", "cx": 10, "cy": 50},
        {"kind": "line", "x1": 0, "y1": 0, "x2": 40, "y2": 0},
        {"kind": "circle", "cx": 30, "cy": 30, "radius": 10},
        {"kind": "arc", "cx": 60, "cy": 30, "x1": 70, "y1": 30, "sweep_deg": 90},
        {"kind": "spline", "points": [[80, 0], [90, 10], [100, 0]]}]})
    write("design_activate_component", {"occurrence": "root"})
    # A position capture reverts the pending move of the design's first root occurrence unless that
    # occurrence is released from its parent first; OperandBench:1 is this document's first.
    write("assembly_ground", {"occurrence": "OperandBench:1", "ground_to_parent": False},
          lambda p: p.get("isGroundToParent") is False)
    write("assembly_move", {"occurrence": "OperandBench:1", "rotate_deg": 30, "rotate_axis": "z",
                            "dx": 100, "dy": 200}, _moved_occurrence(100.0))
    # captured, or a later add recomputes the design and the uncaptured pose reverts.
    write("assembly_capture_position", {"action": "capture"}, _captured)
    read("sketch_get", {"sketch_name": "OperandS"}, _operand_frame,
         ("dop_frame", _recall("dop_frame", lambda p: p["frame"])))
    read("sketch_get", {"sketch_name": "OperandS", "include_entities": True}, _operand_xray,
         ("dop_ids", _recall("dop_ids", _operand_ids)))
    acquire("sketch_point", 10, 20, lambda: [_frame_world(10, 20)], save=_fg("dop_p1"))
    acquire("sketch_line", 20, 0, lambda: [_frame_world(20, 0)], save=_fg("dop_line"))
    # a curve's position is the midpoint of its ends: the arc's other end sits a quarter turn from
    # (70, 30) either way round, so both chord midpoints are the arithmetic; its centre is not.
    acquire("sketch_arc", 65, 30, lambda: [_frame_world(65, 35), _frame_world(65, 25)],
            _round_shape(60, 30, 10.0))
    acquire("sketch_circle", 30, 30, lambda: [_frame_world(30, 30)], _round_shape(30, 30, 10.0),
            ("dop_circle", lambda p: f"{p['matches'][0]['sketch']}/{p['matches'][0]['id']}:center"))
    acquire("sketch_spline", 90, 0, lambda: [_frame_world(90, 0)])
    # three forms in one call, from the root: a find_geometry handle, a sketch_get handle, and the
    # circle row's centre form, whose native point is lifted through the one placement.
    write("model_construction", lambda c: {
        "kind": "plane", "mode": "three_points", "name": "OperandPlane",
        "points": [_ctx_get(c, "dop_p1", "P1 handle"), ids(c)["p2_handle"],
                   _ctx_get(c, "dop_circle", "circle centre ref")]},
        _operand_plane(lambda: [_frame_world(10, 20), _frame_world(40, 20), _frame_world(30, 30)]))
    write("sketch_create", {"plane": "OperandPlane", "name": "OperandPlaneS"})
    read("sketch_get", {"sketch_name": "OperandPlaneS"},
         lambda p: _measured("a sketch on the operand plane frames the turned, moved XZ plane",
                             p.get("frame"), (p.get("frame") or {}).get("space") == "world"
                             and _on_moved_plane((p.get("frame") or {}).get("normal"),
                                                 (p.get("frame") or {}).get("origin_mm"))))
    read("find_geometry", {"kind": "construction_plane", "name": "OperandPlane"},
         lambda p: _matched(1, "construction_plane")(p)
         and p.get("match_count") == 1
         and _on_moved_plane(p["matches"][0].get("normal"), p["matches"][0].get("position"))
         and "|@construction_plane:" in (p["matches"][0].get("handle") or ""),
         _fg("dop_plane_rediscovered"))
    write("sketch_create", lambda c: {"plane": _ctx_get(c, "dop_plane_rediscovered", "plane"),
                                      "name": "RediscoveredPlaneS"})
    read("sketch_get", {"sketch_name": "RediscoveredPlaneS"},
         lambda p: _measured("rediscovered plane handle seats a sketch on the independent plane",
                             p.get("frame"), (p.get("frame") or {}).get("space") == "world"
                             and _on_moved_plane((p.get("frame") or {}).get("normal"),
                                                 (p.get("frame") or {}).get("origin_mm"))))
    write("model_construction", lambda c: {
        "kind": "axis", "mode": "two_points", "name": "OperandAxis",
        "points": [_ctx_get(c, "dop_p1", "P1 handle"), "OperandS/" + ids(c)["p3"]]},
        _operand_axis(lambda: _operand_frame_read()["y_world"]))
    write("model_construction", {"kind": "axis", "mode": "edge", "axis": "OperandS/line:0",
                                 "name": "OperandLineAxis"},
          lambda p: _operand_axis(lambda: _operand_frame_read()["x_world"], through=False)(p)
          and _measured(
              "the index-ref line went in through its one placement, ends in world",
              p.get("operands"),
              len(p.get("operands") or []) == 1
              and p["operands"][0].get("assembly_path") == "OperandBench:1"
              and _operand_ends(p["operands"][0].get("world"), _frame_world(0, 0),
                                _frame_world(40, 0))))
    write("model_construction", lambda c: {"kind": "point", "mode": "at_point",
                                           "name": "OperandCentre",
                                           "points": [_ctx_get(c, "dop_circle", "centre ref")]},
          _operand_point(30, 30))
    read("find_geometry", {"kind": "construction_point", "name": "OperandCentre"},
         lambda p: _matched(1, "construction_point")(p) and _measured(
             "the datum point read back where its operand sits", p["matches"],
             _operand_at(p["matches"][0].get("position"), _frame_world(30, 30))),
         _fg("dop_point_rediscovered"))
    write("model_construction", lambda c: {"kind": "point", "mode": "at_point",
                                           "name": "RediscoveredPoint",
                                           "points": [_ctx_get(c, "dop_point_rediscovered", "point")]},
          lambda p: _datum("point")(p) and p.get("at_operand") is True
          and _operand_at(p.get("world"), _frame_world(30, 30)))
    read("find_geometry", {"kind": "construction_point", "name": "RediscoveredPoint"},
         lambda p: _matched(1, "construction_point")(p)
         and _operand_at(p["matches"][0].get("position"), _frame_world(30, 30)))
    # inside the placed component the SAME native points go in native, and still land in world;
    # the plane's own read runs through the active occurrence.
    write("design_activate_component", {"occurrence": "OperandBench:1"})
    write("model_construction", lambda c: {"kind": "point", "mode": "at_point",
                                           "name": "LocalCentre",
                                           "points": ["OperandS/" + ids(c)["p2"]]},
          _operand_point(40, 20, path=None))
    write("model_construction", lambda c: {
        "kind": "plane", "mode": "three_points", "name": "LocalPlane",
        "points": ["OperandS/" + ids(c)[k] for k in ("p1", "p2", "p3")]},
        _operand_plane(lambda: [_frame_world(10, 20), _frame_world(40, 20), _frame_world(10, 50)],
                       path=None))
    write("design_activate_component", {"occurrence": "root"})
    read("find_geometry", {"target": "OperandBench:1", "kind": "construction_plane",
                           "name": "LocalPlane"},
         lambda p: _matched(1, "construction_plane")(p)
         and p.get("match_count") == 1
         and p["matches"][0].get("occurrence") == "OperandBench:1"
         and _on_moved_plane(p["matches"][0].get("normal"), p["matches"][0].get("position")),
         _fg("dop_local_plane_rediscovered"))
    write("sketch_create", lambda c: {"plane": _ctx_get(c, "dop_local_plane_rediscovered", "plane"),
                                      "name": "RediscoveredLocalPlaneS"})
    read("sketch_get", {"sketch_name": "RediscoveredLocalPlaneS"},
         lambda p: _measured("placed plane handle seats a sketch on the independent plane",
                             p.get("frame"), (p.get("frame") or {}).get("space") == "world"
                             and _on_moved_plane((p.get("frame") or {}).get("normal"),
                                                 (p.get("frame") or {}).get("origin_mm"))))
    # a split leaves the pre-split handle naming a piece that no longer sits where it was read.
    write("sketch_edit_curve", {"action": "split", "sketch_name": "OperandS",
                                "entity_one": "line:0", "x1": 20, "y1": 0})
    write("model_construction", lambda c: {"kind": "axis", "axis": _ctx_get(c, "dop_line", "line")},
          _refused("did not resolve", "find_geometry"))
    acquire("sketch_line", 10, 0, lambda: [_frame_world(10, 0)], save=_fg("dop_piece"))
    write("design_activate_component", {"occurrence": "OperandBench:1"})
    write("model_construction", lambda c: {"kind": "axis", "name": "OperandPieceAxis",
                                           "axis": _ctx_get(c, "dop_piece", "first piece")},
          lambda p: p.get("component") == "OperandBench"
          and _operand_axis(lambda: _operand_frame_read()["x_world"], through=False)(p))
    write("design_activate_component", {"occurrence": "root"})
    write("design_add_instance", {"component": "OperandBench", "x": 400, "units": "mm"},
          lambda p: p.get("occurrence") == "OperandBench:2")
    read("design_get", {"include": ["datums"], "name_filter": "Operand"},
         lambda p: _measured("lost datum replies rediscovered as definition rows",
                             (p.get("datums") or {}).get("counts"),
                             {("construction_axis", "OperandPieceAxis"),
                              ("construction_plane", "OperandPlane"),
                              ("construction_point", "OperandCentre")}
                             <= {(r.get("kind"), r.get("name"))
                                 for r in (p.get("datums") or {}).get("datums") or []}
                             and (p.get("datums") or {}).get("match_count") is not None
                             and any(r.get("name") == "OperandPieceAxis"
                                     and r.get("placement_count") == 2
                                     for r in (p.get("datums") or {}).get("datums") or [])))
    read("find_geometry", {"target": "OperandBench:1", "kind": "construction_axis",
                           "name": "OperandPieceAxis"}, _rediscovered_axis,
         _fg("dop_axis_rediscovered"))
    read("find_geometry", {"target": "OperandBench:2", "kind": "construction_axis",
                           "name": "OperandPieceAxis"},
         lambda p: _matched(1, "construction_axis")(p)
         and p.get("match_count") == 1
         and p["matches"][0].get("occurrence") == "OperandBench:2"
         and (p["matches"][0].get("handle") or "").endswith(";occ=OperandBench:2"))
    # The reacquired datum, consumed by handle, turns about the piece's WORLD line.
    write("assembly_move", lambda c: {"occurrence": "OperandBench:1", "rotate_deg": 90,
                                      "rotate_axis": _ctx_get(c, "dop_axis_rediscovered", "piece axis")},
          _moved_occurrence())
    read("find_geometry", {"target": "OperandBench:1", "kind": "sketch_point", "max_results": 100},
         _swung_about_the_piece)
    rows += [("doc_activate", lambda c: {"name": _ctx_get(c, "dop_story", "story"),
                                         "expect_document": _ctx_get(c, "dop_doc", "operands")},
              "ok", None),
             ("doc_close", lambda c: {"name": _ctx_get(c, "dop_doc", "operands"),
                                      "save_changes": False,
                                      "expect_document": _ctx_get(c, "dop_story", "story")},
              _document_closed, None)]
    return rows


_DATUM_OPERANDS = _datum_operand_rows()


def _extrude_edit_landed(p):
    """Require the existing feature, requested definition and restored marker to survive an edit."""
    return _measured("existing Extrude edit", p,
                     p.get("edited") is True and p.get("same_feature") is True
                     and p.get("definition_matches") is True and p.get("geometry_changed") is True
                     and p.get("marker_restored") is True
                     and p.get("marker_before") == p.get("marker_after")
                     and p.get("other_components_unchanged") is True
                     and p.get("linked_scope_verified_at_edit") is True
                     and p.get("new_timeline_errors") == [])


def _extrude_edit_mass(volume, center_axis=None, center=None):
    """Read the solid volume and optional mass centroid independently of the editor."""
    def check(p):
        mass = p.get("mass") or {}
        centroid = mass.get("center_of_mass")
        coordinate = (centroid["xyz".index(center_axis)]
                      if center_axis in ("x", "y", "z")
                      and isinstance(centroid, list) and len(centroid) == 3 else None)
        want = center
        if center_axis in ("x", "y"):
            want = _ee_shift(center, 0.0)[0] if center_axis == "x" else _ee_shift(0.0, center)[1]
        return _measured("edited Extrude material", {"volume": mass.get("volume"), "center": centroid},
                         _near(mass.get("volume"), volume, 0.005)
                         and (center_axis is None or _near(coordinate, want, 0.005)))
    return check


def _ee_shift(x, y):
    """(x, y) moved to where the extrusion story's block landed, the ee_at recall of its origin."""
    at = _RECALL.get("ee_at")
    if not isinstance(at, dict) or not all(
            isinstance(at.get(axis), (int, float)) and not isinstance(at.get(axis), bool)
            and math.isfinite(at[axis]) for axis in ("x", "y")):
        raise AssertionError("ee_at baseline requires finite numeric x and y")
    return x + at["x"], y + at["y"]


def _extrude_edit_roof(p):
    """Check the unaffected roof's six direct planar areas and world centroids."""
    rows = p.get("matches") or []
    expected = [[area, *_ee_shift(x, y), z] for area, x, y, z in (
        [100, -5, 5, 32.5], [100, 35, 5, 32.5], [200, 15, -5, 32.5], [200, 15, 15, 32.5],
        [800, 15, 5, 30], [800, 15, 5, 35])]
    actual = [[row.get("area"), *(row.get("position") or [])] for row in rows]
    good = (p.get("units") == "mm" and p.get("match_count") == len(rows) == 6
            and all(row.get("kind") == "planar_face" for row in rows)
            and all(len(row) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                          and math.isfinite(v) for v in row) for row in actual))
    return _measured("unaffected roof planar area/centroid set", actual,
                     good and all(_near(v, want, 0.00001) for row, wanted in zip(sorted(actual), expected)
                                  for v, want in zip(row, wanted)))


def _extrude_edit_history(p):
    """The complete timeline row identities and marker stay where the earlier read placed them."""
    timeline = p.get("timeline") or {}
    before = _RECALL.get("ee_history") or {}
    fields = lambda t: [(r.get("index"), r.get("name"), r.get("type"), r.get("component"))
                        for r in t.get("timeline") or []]
    return _measured("edit preserves timeline rows and parked marker", timeline,
                     timeline.get("marker_position") == before.get("marker_position")
                     and fields(timeline) == fields(before) and bool(fields(before)))


def _extrude_edit_rows():
    """Build a bounded definition-edit bench in an owned scratch document."""
    rows = [
        ("doc_get", {}, _home_document, ("ee_story", _recall("ee_story", _home_address))),
        ("doc_new", lambda c: {"expect_document": _ctx_get(c, "ee_story", "story")},
         _new_document, ("ee_doc", _recall("ee_doc", lambda p: p["document_handle"]))),
    ]

    def write(name, args, check="ok", save=None):
        rows.append((name, lambda c, args=args: _combine_pin(
            c, "ee_doc", args(c) if callable(args) else args), check, save))

    def rectangle(name, low, high, plane="xy"):
        write("sketch_create", {"name": name, "plane": plane})
        write("sketch_add_geometry", {"sketch_name": name, "geometry": [{
            "kind": "rectangle", "x1": low[0], "y1": low[1], "x2": high[0], "y2": high[1]}]})

    def inspect(target, check):
        rows.append(("model_inspect", lambda c, target=target: _combine_inspect(target), check, None))

    def placed(label, low, high, volume):
        # the layout moves this story's geometry as a block; the EditOriginal extrude's min point
        # (authored at the origin, recalled as ee_at) is where the block landed
        def check(p):
            dx, dy = _ee_shift(0.0, 0.0)
            return _combine_body(label, (low[0] + dx, low[1] + dy, low[2]),
                                 (high[0] + dx, high[1] + dy, high[2]), volume)(p)
        return check

    def edit(key, args):
        write("model_edit_extrude", lambda c, key=key, args=args: {
            "feature": _ctx_get(c, key, "existing Extrude"), **args}, _extrude_edit_landed)
        if key == "ee_scope":
            rows.append(("find_geometry", {"target": "EditProfile:Body1", "kind": "planar_face",
                          "units": "mm", "max_results": 6}, _extrude_edit_roof, None))
            inspect("EditProfile:Body2", _extrude_edit_mass(482))

    write("model_create_component", {"name": "EditProfile", "activate": True}, _made_component)
    write("model_construction", {"kind": "plane", "plane": "xy", "offset": 30, "name": "EditRoof"})
    rectangle("EditRoofS", (-5, -5), (35, 15), "EditRoof")
    write("model_extrude", {"sketch_name": "EditRoofS", "distance": 5}, _extruded)
    rows.append(("find_geometry", lambda c: {"target": "EditProfile:Body1", "kind": "planar_face",
                 "nearest_to": [25, 5, 30], "max_results": 1}, _matched(1, "planar_face"), _fg("ee_roof")))
    rectangle("EditOriginal", (0, 0), (10, 10))
    rectangle("EditShifted", (20, 0), (30, 10))
    write("model_extrude", {"sketch_name": "EditOriginal", "distance": 10}, _extruded,
          ("ee_profile", _recall("ee_profile", lambda p: "EditProfile/" + p["feature"])))
    rows.append(("model_inspect", lambda c: _combine_inspect("EditProfile:Body2"), "ok",
                 ("ee_at", _recall("ee_at", lambda p: p["min_point"]))))
    write("sketch_create", {"name": "EditTrailing", "plane": "xy"})
    write("design_edit_timeline", lambda c: {"action": "roll", "feature": _ctx_get(c, "ee_profile", "Extrude"),
                                             "to": "after"})
    rows.append(("design_get", {"include": ["timeline"], "max_results": 100}, "ok",
                 ("ee_history", _recall("ee_history", lambda p: p["timeline"]))))
    edit("ee_profile", {"action": "profile", "profile": {"sketch": "EditShifted", "profile_index": 0}})
    inspect("EditProfile:Body2", placed("shifted equal-volume extrusion", (20, 0, 0), (30, 10, 10), 1000))
    rows.append(("design_get", {"include": ["timeline"], "max_results": 100}, _extrude_edit_history, None))
    write("design_edit_timeline", {"action": "roll", "to": "end"})
    for args, low, high, volume in [
        ({"extent": "symmetric", "distance": 8}, (20, 0, -8), (30, 10, 8), 1600),
        ({"extent": "two_side", "distance": 12, "distance2": 8}, (20, 0, -8), (30, 10, 12), 2000),
    ]:
        edit("ee_profile", {"action": "extent", **args})
        inspect("EditProfile:Body2", placed(args["extent"], low, high, volume))
    write("model_edit_extrude", lambda c: {"feature": _ctx_get(c, "ee_profile", "Extrude"),
          "action": "extent", "extent": "to_face", "to_object": _ctx_get(c, "ee_roof", "roof")},
          _extrude_edit_landed)
    inspect("EditProfile:Body2", placed("to-face replacement", (20, 0, 0), (30, 10, 30), 3000))
    edit("ee_profile", {"action": "extent", "extent": "distance", "distance": 5})
    inspect("EditProfile:Body2", placed("distance replacement", (20, 0, 0), (30, 10, 5), 500))
    rectangle("EditDependentCut", (21, 1), (24, 4))
    write("model_extrude", {"sketch_name": "EditDependentCut", "distance": 2, "operation": "cut",
                            "target_bodies": ["EditProfile:Body2"]}, _extruded,
          ("ee_dependent", _recall("ee_dependent", lambda p: p["feature"])))
    write("model_edit_extrude", lambda c: {"feature": _ctx_get(c, "ee_profile", "Extrude"),
          "action": "profile", "profile": {"sketch": "EditOriginal", "profile_index": 0}},
          _refused("definition landed", "downstream"))
    rows.append(("design_get", {"include": ["timeline"], "max_results": 100},
                 lambda p: any(r.get("name") == _RECALL.get("ee_dependent")
                               and r.get("health") in ("warning", "error")
                               for r in (p.get("timeline") or {}).get("timeline") or []), None))
    inspect("EditProfile:Body2", placed("landed edit with failed dependent", (0, 0, 0), (10, 10, 5), 500))
    edit("ee_profile", {"action": "profile", "profile": {"sketch": "EditShifted", "profile_index": 0}})
    inspect("EditProfile:Body2", placed("dependent cut restored", (20, 0, 0), (30, 10, 5), 482))

    write("design_activate_component", {"occurrence": "root"})
    write("model_create_component", {"name": "EditScope", "activate": True}, _made_component)
    rectangle("EditStock", (0, 0), (10, 10))
    write("model_extrude", {"sketch_name": "EditStock", "distance": 10, "symmetric": True}, _extruded)
    for name, z, depth in (("EditUpper", 0, 20), ("EditHidden", 40, 10)):
        if z:
            write("model_construction", {"kind": "plane", "plane": "xy", "offset": z, "name": name})
        rectangle(name + "S", (0, 0), (10, 10), name if z else "xy")
        write("model_extrude", {"sketch_name": name + "S", "distance": depth}, _extruded)
    write("view_set", {"action": "hide", "target": "EditScope:Body3"})
    rows.append(("find_geometry", lambda c: {"target": "EditScope:Body3", "kind": "planar_face",
                 "nearest_to": [7.5, 2.5, 40], "max_results": 1}, _matched(1, "planar_face"), _fg("ee_scope_roof")))
    rectangle("EditPocketA", (1, 1), (4, 4))
    rectangle("EditPocketB", (6, 1), (9, 4))
    write("model_extrude", {"sketch_name": "EditPocketA", "distance": 2}, _extruded,
          ("ee_scope", _recall("ee_scope", lambda p: "EditScope/" + p["feature"])))
    for op, volume in (("join", 3000), ("cut", 1982), ("intersect", 18)):
        edit("ee_scope", {"action": "operation", "operation": op,
                          **({"target_bodies": ["EditScope:Body1"]} if op != "join" else {})})
        inspect("EditScope:Body1", _extrude_edit_mass(volume))
    edit("ee_scope", {"action": "operation", "operation": "new"})
    inspect("EditScope:1", _extrude_edit_mass(5018))
    edit("ee_scope", {"action": "operation", "operation": "cut", "target_bodies": ["EditScope:Body1"]})
    edit("ee_scope", {"action": "profile", "profile": {"sketch": "EditPocketB", "profile_index": 0}})
    inspect("EditScope:Body1", _extrude_edit_mass(1982, "x", (10000 - 18 * 7.5) / 1982))
    inspect("EditScope:Body2", _extrude_edit_mass(2000))
    write("model_edit_extrude", lambda c: {
        "feature": _ctx_get(c, "ee_scope", "Extrude"),
        "action": "extent", "extent": "through_all", "direction": "positive"},
        lambda p: _measured("linked source remains the addressed edit feature",
                            p.get("linked_component_aliases"),
                            _extrude_edit_landed(p) is True
                            and p.get("linked_component_aliases") == ["EditProfile"]))
    inspect("EditScope:Body1", _extrude_edit_mass(1910, "z", -450 / 1910))
    inspect("EditScope:Body2", _extrude_edit_mass(2000))
    write("model_edit_extrude", lambda c: {
        "feature": "EditProfile/" + _ctx_get(c, "ee_scope", "Extrude").split("/")[-1],
        "action": "extent", "extent": "distance", "distance": 5},
        _refused("no feature named", "EditProfile"))
    rows.append(("find_geometry", {"target": "EditProfile:Body1", "kind": "planar_face",
                                   "units": "mm", "max_results": 6}, _extrude_edit_roof, None))
    inspect("EditProfile:Body2", _extrude_edit_mass(482))
    inspect("EditScope:Body1", _extrude_edit_mass(1910, "z", -450 / 1910))
    inspect("EditScope:Body2", _extrude_edit_mass(2000))
    edit("ee_scope", {"action": "participants", "target_bodies": ["EditScope:Body2"]})
    inspect("EditScope:Body1", _extrude_edit_mass(2000))
    inspect("EditScope:Body2", _extrude_edit_mass(1820))
    inspect("EditScope:Body3", _extrude_edit_mass(1000))
    edit("ee_scope", {"action": "participants", "target_bodies": ["EditScope:Body1"]})
    edit("ee_scope", {"action": "extent", "extent": "through_all", "direction": "negative"})
    inspect("EditScope:Body1", _extrude_edit_mass(1910, "z", 450 / 1910))
    write("model_edit_extrude", lambda c: {"feature": _ctx_get(c, "ee_scope", "Extrude"),
          "action": "extent", "extent": "through_all", "direction": "both"},
          _refused("Two-sided through_all", "participant assignment is unsupported", "separate one-sided"))
    rows.append(("find_geometry", {"target": "EditProfile:Body1", "kind": "planar_face",
                                   "units": "mm", "max_results": 6}, _extrude_edit_roof, None))
    inspect("EditProfile:Body2", _extrude_edit_mass(482))
    inspect("EditScope:Body1", _extrude_edit_mass(1910, "z", 450 / 1910))
    inspect("EditScope:Body2", _extrude_edit_mass(2000))
    inspect("EditScope:Body3", _extrude_edit_mass(1000))
    write("model_edit_extrude", lambda c: {"feature": _ctx_get(c, "ee_scope", "Extrude"),
          "action": "extent", "extent": "to_face", "to_object": _ctx_get(c, "ee_scope_roof", "roof")},
          _extrude_edit_landed)
    rows.append(("find_geometry", {"target": "EditProfile:Body1", "kind": "planar_face",
                          "units": "mm", "max_results": 6}, _extrude_edit_roof, None))
    inspect("EditProfile:Body2", _extrude_edit_mass(482))
    inspect("EditScope:Body1", _extrude_edit_mass(1910, "z", -450 / 1910))
    inspect("EditScope:Body2", _extrude_edit_mass(2000))
    edit("ee_scope", {"action": "operation", "operation": "intersect", "target_bodies": ["EditScope:Body1"]})
    inspect("EditScope:Body1", _extrude_edit_mass(90))
    edit("ee_scope", {"action": "participants", "target_bodies": ["EditScope:Body2"]})
    inspect("EditScope:Body1", _extrude_edit_mass(2000))
    inspect("EditScope:Body2", _extrude_edit_mass(180))
    inspect("EditScope:Body3", _extrude_edit_mass(1000))
    rectangle("EditLate", (1, 1), (4, 4))
    write("model_edit_extrude", lambda c: {"feature": _ctx_get(c, "ee_scope", "Extrude"),
          "action": "profile", "profile": {"sketch": "EditLate", "profile_index": 0}},
          _refused("must precede"))
    inspect("EditScope:Body2", _extrude_edit_mass(180))
    write("model_extrude", {"sketch_name": "EditPocketA", "operation": "cut",
                            "extent": "through_all", "symmetric": True,
                            "target_bodies": ["EditScope:Body1"]}, _extruded,
          ("ee_both_source", lambda p: "EditScope/" + p["feature"]))
    for after_refusal in (False, True):
        if after_refusal:
            write("model_edit_extrude", lambda c: {
                "feature": _ctx_get(c, "ee_both_source", "existing two-sided through cut"),
                "action": "participants", "target_bodies": ["EditScope:Body2"]},
                _refused("Two-sided through_all", "participant assignment is unsupported", "separate one-sided"))
        inspect("EditScope:Body1", _extrude_edit_mass(1820, "z", 0))
        inspect("EditScope:Body2", _extrude_edit_mass(180))
        inspect("EditScope:Body3", _extrude_edit_mass(1000))
        rows.append(("find_geometry", {"target": "EditProfile:Body1", "kind": "planar_face",
                                       "units": "mm", "max_results": 6}, _extrude_edit_roof, None))

    def four_state(label, bodies, dimensions, fragment_volumes=()):
        def check(p):
            mass = p.get("mass") or {}
            got = {row.get("body"): row.get("volume") for row in mass.get("per_body") or []}
            fragments = [volume for name, volume in got.items() if name not in bodies]
            spans = sorted(p.get(axis) for axis in ("x", "y", "z")
                           if isinstance(p.get(axis), (int, float)))
            good = (p.get("kind") == "occurrence" and p.get("units") == "mm"
                    and mass.get("accuracy_used") == "very_high"
                    and mass.get("per_body_truncated") is False
                    and mass.get("per_body_count") == len(bodies) + len(fragment_volumes) == len(got)
                    and set(bodies).issubset(got) and len(spans) == 3
                    and all(_near(got[name], volume, 0.005) for name, volume in bodies.items())
                    and all(isinstance(volume, (int, float)) for volume in fragments)
                    and all(_near(a, b, 0.005) for a, b in
                            zip(sorted(fragments), sorted(fragment_volumes)))
                    and all(_near(a, b, 0.01) for a, b in zip(spans, sorted(dimensions)))
                    and _near(mass.get("volume"), sum(bodies.values()) + sum(fragment_volumes), 0.005))
            return _measured(label + " independent material and bounds",
                             {"bodies": got, "volume": mass.get("volume"), "dimensions": spans}, good)
        return check

    def four_read(bodies, dimensions, label, fragment_volumes=()):
        rows.append(("model_inspect", {**_combine_inspect("G18Four:1"), "per_body": True},
                     four_state(label, bodies, dimensions, fragment_volumes), None))
        rows.append(("model_inspect", {**_combine_inspect("G18EditDecoy:1"), "per_body": True},
                     four_state(label + " decoy", {"Body1": 500}, (5, 10, 10)), None))

    def four_edit(args, operation, sketch, participants):
        def check(p):
            landed = _extrude_edit_landed(p)
            after = p.get("definition_after") or {}
            return _measured("four-profile definition readback", after,
                             landed is True and p.get("action") == args["action"]
                             and after.get("operation") == operation
                             and after.get("profile_sketch") == sketch
                             and after.get("extent") == "symmetric"
                             and after.get("participants") == participants)
        write("model_edit_extrude", lambda c, args=args: {
            "feature": _ctx_get(c, "ee_four", "four-profile Extrude"), **args}, check)

    # A literal root keeps the owned mixed-plane fixture outside the story layout.
    rows.append(("design_activate_component", {"occurrence": "root"}, "ok", None))
    write("model_create_component", {"name": "G18EditDecoy", "activate": True}, _made_component)
    rectangle("G18DecoyProfile", (100, 100), (110, 110))
    write("model_extrude", {"sketch_name": "G18DecoyProfile", "distance": 5,
                            "operation": "new"}, _extruded)
    write("design_activate_component", {"occurrence": "root"})
    write("model_create_component", {"name": "G18Four", "activate": True}, _made_component)
    for name, low, high in (("G18StockA", (190, -30), (235, 0)),
                            ("G18StockB", (190, 0), (235, 30))):
        rectangle(name, low, high)
        write("model_extrude", {"sketch_name": name, "distance": 20,
                                "symmetric": True, "operation": "new"}, _extruded)
    rectangle("G18Replacement", (205, 0), (215, -10), "xz")
    write("sketch_create", {"name": "G18FourProfile", "plane": "xz"})
    write("sketch_add_geometry", {"sketch_name": "G18FourProfile", "geometry": [
        {"kind": "rectangle", "x1": 190, "y1": 0, "x2": 235, "y2": -6},
        {"kind": "rectangle", "x1": 194, "y1": 0, "x2": 200, "y2": -40}]})
    write("model_extrude", {"sketch_name": "G18FourProfile", "profile_index": "all",
                            "distance": 45, "symmetric": True, "operation": "new"},
          lambda p: _measured("four-profile source selection", p,
                              p.get("extruded") is True and p.get("profiles_extruded") == 4
                              and sorted(p.get("profile_index") or []) == [0, 1, 2, 3]),
          ("ee_four", _recall("ee_four", lambda p: "G18Four/" + p["feature"])))
    four_read({"Body1": 54000, "Body2": 54000, "Body3": 42660},
              (45, 90, 60), "four-profile initial")
    four_edit({"action": "extent", "extent": "symmetric", "distance": 30},
              "new", "G18FourProfile", [])
    four_read({"Body1": 54000, "Body2": 54000, "Body3": 28440},
              (45, 60, 60), "four-profile extent")
    four_edit({"action": "operation", "operation": "cut",
               "target_bodies": ["G18Four:Body1"]}, "cut", "G18FourProfile", ["Body1"])
    four_read({"Body2": 54000}, (40, 45, 60),
              "four-profile scoped cut", (1680, 14700, 27000))
    four_edit({"action": "participants", "target_bodies": ["G18Four:Body2"]},
              "cut", "G18FourProfile", ["Body2"])
    four_read({"Body1": 54000}, (40, 45, 60),
              "four-profile participant switch", (1680, 14700, 27000))
    four_edit({"action": "profile", "profile": {"sketch": "G18Replacement",
                                                "profile_index": 0}},
              "cut", "G18Replacement", ["Body2"])
    four_read({"Body1": 54000, "Body2": 51000}, (40, 45, 60),
              "four-profile scalar replacement")
    rows += [
        ("doc_activate", lambda c: {"name": _ctx_get(c, "ee_story", "story"),
                                    "expect_document": _ctx_get(c, "ee_doc", "scratch")}, "ok", None),
        ("doc_close", lambda c: {"name": _ctx_get(c, "ee_doc", "scratch"), "save_changes": False,
                                 "expect_document": _ctx_get(c, "ee_story", "story")}, _document_closed, None),
    ]
    return rows


def _org_vertices(p):
    """Read a complete set of finite world vertices from find_geometry."""
    rows = p.get("matches") or []
    if (p.get("units") != "mm" or p.get("truncated") is True
            or p.get("match_count") != len(rows) or not rows):
        raise AssertionError("Incomplete organization vertex census")
    points = []
    for row in rows:
        xyz = row.get("position")
        if (row.get("kind") != "vertex" or not isinstance(xyz, list) or len(xyz) != 3
                or not all(isinstance(x, (int, float)) and not isinstance(x, bool)
                           and math.isfinite(x) for x in xyz)):
            raise AssertionError("Unreadable organization vertex")
        if not any(all(abs(a-b) <= 0.00001 for a, b in zip(xyz, old)) for old in points):
            points.append(xyz)
    return sorted(points)


def _org_same_vertices(key):
    """Compare independently read world vertex sets with a saved source."""
    def check(p):
        before, after = _RECALL.get(key), _org_vertices(p)
        good = (isinstance(before, list) and len(before) == len(after) and len(before) in (4, 8)
                and all(sum(all(abs(a-b) <= 0.00001 for a, b in zip(point, candidate))
                            for candidate in after) == 1 for point in before))
        return _measured("organized body world vertices", {"before": before, "after": after}, good)
    return check


def _org_result(action, kind, source_count, destination_count):
    """Require the writer's ownership facts and a fresh consumable reference."""
    def check(p):
        return _measured("body ownership result", p,
                         p.get("action") == action and p.get("body_kind") == kind
                         and isinstance(p.get("handle"), str) and bool(p["handle"])
                         and p.get("source_membership_before") == source_count
                         and p.get("source_membership_after") == (
                             source_count if action == "copy" else source_count - 1)
                         and p.get("destination_membership_after") == destination_count
                         and p.get("selected_world_sample_preserved") is True
                         and p.get("source_retained") is (action == "copy"))
    return check


def _org_tree_counts(expected, root_count=0, no_children_of=()):
    """Read all occurrence body counts without trusting the ownership writer."""
    def check(p):
        tree = p.get("tree") or {}
        rows = tree.get("children") or []
        got = {}
        complete = tree.get("truncated") is False and tree.get("children_truncated") is False
        pending = list(rows)
        while pending:
            row = pending.pop()
            complete = (complete and row.get("children_truncated") is not True
                        and row.get("bodies_truncated") is not True)
            got[row.get("full_path")] = row.get("body_count")
            pending.extend(row.get("children") or [])
        wanted = expected() if callable(expected) else expected
        return _measured("organized body occurrence census", got,
                         complete and len(tree.get("root_bodies") or []) == root_count
                         and tree.get("root_bodies_truncated") is not True
                         and all(not any(path.startswith(parent + "+") for path in got)
                                 for parent in no_children_of)
                         and all(got.get(name) == count for name, count in wanted.items()))
    return check


def _org_mesh_count(count):
    """Require a complete scoped mesh census with the expected membership."""
    def check(p):
        rows = p.get("meshes") or []
        return _measured("organized mesh membership", {"count": p.get("count"), "rows": rows},
                         p.get("truncated") is False and p.get("count") == len(rows) == count
                         and all(row.get("triangle_count") == 12 for row in rows))
    return check


def _org_mesh_shape(p):
    """Read mesh topology and analytic box mass through an independent reader."""
    points = _RECALL.get("org_before") or []
    center = (p.get("bbox") or {}).get("center") or {}
    expected_center = [sum(point[i] for point in points) / len(points) for i in range(3)] if points else []
    return _measured("organized mesh shape", p,
                     p.get("kind") == "mesh" and p.get("units") == "mm"
                     and p.get("triangle_count") == 12 and p.get("is_closed") is True
                     and p.get("is_oriented") is True
                     and len(expected_center) == 3
                     and all(_near(center.get(axis), value, 0.001)
                             for axis, value in zip("xyz", expected_center))
                     and _near(p.get("volume"), 672.0, 0.001)
                     and _near(p.get("area"), 472.0, 0.001))


def _org_mesh_box_shape(p, vertices_key, volume, area, label="organized mesh witness"):
    """Measure a mesh witness against its authored box and world center."""
    points = _RECALL.get(vertices_key) or []
    center = (p.get("bbox") or {}).get("center") or {}
    expected = [sum(point[i] for point in points) / len(points) for i in range(3)] if points else []
    return _measured(label, p,
                     p.get("kind") == "mesh" and p.get("units") == "mm"
                     and p.get("triangle_count") == 12 and p.get("is_closed") is True
                     and p.get("is_oriented") is True and len(expected) == 3
                     and all(_near(center.get(axis), value, 0.001)
                             for axis, value in zip("xyz", expected))
                     and _near(p.get("volume"), volume, 0.001)
                     and _near(p.get("area"), area, 0.001))


def _org_mesh_snapshot(p):
    """Keep the independently read mesh geometry needed across a refused write."""
    bbox = p.get("bbox") or {}
    return {"name": p.get("name"), "kind": p.get("kind"), "units": p.get("units"),
            "triangle_count": p.get("triangle_count"), "is_closed": p.get("is_closed"),
            "is_oriented": p.get("is_oriented"), "volume": p.get("volume"),
            "area": p.get("area"), "center": bbox.get("center"),
            "min_point": bbox.get("min_point"), "max_point": bbox.get("max_point")}


def _org_mesh_unchanged(key):
    """Compare a mesh's direct geometry reads around a refused write."""
    def check(p):
        before, after = _RECALL.get(key), _org_mesh_snapshot(p)
        exact = ("name", "kind", "units", "triangle_count", "is_closed", "is_oriented")
        good = (isinstance(before, dict) and all(before.get(field) == after.get(field) for field in exact)
                and all(_num(before.get(field)) and _num(after.get(field))
                        and _near(after[field], before[field], 0.001)
                        for field in ("volume", "area"))
                and all(isinstance(before.get(field), dict) and isinstance(after.get(field), dict)
                        and all(_num(before[field].get(axis)) and _num(after[field].get(axis))
                                and _near(after[field][axis], before[field][axis], 0.001)
                                for axis in "xyz")
                        for field in ("center", "min_point", "max_point")))
        return _measured("mesh geometry after refused write", {"before": before, "after": after}, good)
    return check


def _org_mesh_inventory_unchanged(key):
    """Compare complete scoped mesh membership around a refused write."""
    def check(p):
        before = _RECALL.get(key) or {}
        old, now = before.get("meshes") or [], p.get("meshes") or []
        facts = lambda row: {name: value for name, value in row.items() if name != "handle"}
        good = (before.get("truncated") is False and p.get("truncated") is False
                and before.get("count") == len(old) and p.get("count") == len(now)
                and [facts(row) for row in old] == [facts(row) for row in now])
        return _measured("mesh membership after refused write", {"before": old, "after": now}, good)
    return check


def _org_translated_vertices(p):
    """Check that the returned body handle drives an independent one-millimeter move."""
    before, after = _RECALL.get("org_before"), _org_vertices(p)
    expected = [[x + 1, y, z] for x, y, z in before] if isinstance(before, list) else []
    return _measured("fresh handle consumer translation", {"expected": expected, "actual": after},
                     len(expected) == len(after) and len(expected) in (4, 8)
                     and all(sum(all(abs(a-b) <= 0.00001 for a, b in zip(point, candidate))
                                 for candidate in after) == 1 for point in expected))


def _org_sphere_mass(p):
    """Independently measure a six-millimeter sphere at its selected world position."""
    mass = p.get("mass") or {}
    center = mass.get("center_of_mass") or []
    return _measured("organized sphere mass and world center", mass,
                     mass.get("units") == "mm" and len(center) == 3
                     and all(_near(a, b, 0.001) for a, b in zip(center, (40, 20, 10)))
                     and _near(mass.get("volume"), 4 * math.pi * 6**3 / 3, 0.01)
                     and _near(mass.get("area"), 4 * math.pi * 6**2, 0.01))


def _org_same_copy_result(kind):
    """Require a fresh same-owner copy and its one-placement context."""
    def check(p):
        history = p.get("timeline_health") or {}
        witness = p.get("witness_check") or {}
        return _measured("same-owner body copy", p,
                         p.get("action") == "copy" and p.get("body_kind") == kind
                         and isinstance(p.get("handle"), str) and bool(p["handle"])
                         and p.get("full_path") == "OrgSameSource:1"
                         and p.get("owner_component") == "OrgSameSource"
                         and p.get("source_membership_before") == 2
                         and p.get("source_membership_after") == 3
                         and p.get("destination_membership_before") == 2
                         and p.get("destination_membership_after") == 3
                         and p.get("source_retained") is True
                         and p.get("selected_world_sample_preserved") is True
                         and history.get("checked") is True and history.get("healthy") is True
                         and witness.get("unchanged") is True)
    return check


def _org_same_timeline(p, copied):
    """Check a refused move leaves history or a copy adds one healthy row."""
    before, after = _RECALL.get("org_same_history"), p.get("timeline")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return _measured("same-owner timeline", after, False)
    old, now = before.get("timeline") or [], after.get("timeline") or []
    complete = (before.get("truncated") is not True and after.get("truncated") is not True
                and before.get("count") == before.get("returned") == len(old)
                and after.get("count") == after.get("returned") == len(now))
    fields = lambda rows: [(r.get("index"), r.get("name"), r.get("type"),
                            r.get("component"), r.get("health")) for r in rows]
    old_states = (before.get("summary") or {}).get("states") or {}
    new_states = (after.get("summary") or {}).get("states") or {}
    healthy_added = (isinstance(old_states.get("healthy"), int)
                     and new_states.get("healthy") == old_states["healthy"] + 1
                     and all(new_states.get(key) == value for key, value in old_states.items()
                             if key != "healthy")
                     and (after.get("summary") or {}).get("exceptions")
                     == (before.get("summary") or {}).get("exceptions"))
    good = (complete and isinstance(before.get("count"), int)
            and isinstance(before.get("marker_position"), int)
            and after.get("count") == before["count"] + (1 if copied else 0)
            and after.get("marker_position") == before.get("marker_position") + (1 if copied else 0)
            and fields(now[:len(old)]) == fields(old)
            and (bool(now) and now[-1].get("health", "healthy") == "healthy"
                 and healthy_added if copied else after == before))
    return _measured("same-owner copy history" if copied else "same-owner move refusal history",
                     {"before": before, "after": after}, good)


def _org_same_mesh_inventory(p, count):
    """Read the unchanged original/sibling rows and one new copied mesh."""
    rows = p.get("meshes") or []
    saved = _RECALL.get("org_same_mesh_rows") or []
    names = [row.get("name") for row in rows]
    copied = _RECALL.get("org_same_copied_name")
    facts = lambda row: {key: value for key, value in row.items() if key != "handle"}
    good = (p.get("truncated") is False and p.get("count") == len(rows) == count
            and len(saved) == 2 and len(set(names)) == count
            and all(row.get("triangle_count") == 12 for row in rows)
            and all(sum(row.get("name") == old.get("name") and facts(row) == facts(old)
                        for row in rows) == 1
                    for old in saved)
            and (count == 2 or (isinstance(copied, str)
                                and copied not in {old.get("name") for old in saved}
                                and names.count(copied) == 1)))
    return _measured("same-owner mesh census", {"before": saved, "after": rows}, good)


def _org_same_mesh_copy(p):
    """The copied handle resolves the new named mesh with measured geometry."""
    name = p.get("name")
    original_names = {row.get("name") for row in _RECALL.get("org_same_mesh_rows") or []}
    return (_org_mesh_shape(p) and _measured("copied mesh handle resolves new body", name,
                                            isinstance(name, str) and bool(name)
                                            and name not in original_names))


def _org_same_mesh_sibling(p):
    """Measure the actual sibling mesh against its authored box geometry."""
    return _org_mesh_box_shape(p, "org_same_sibling", 546.0, 422.0,
                               "same-owner sibling mesh geometry")


def _body_organization_rows():
    """Exercise ownership transfers and output-handle consumers in owned documents."""
    rows = []

    def row(name, args, check="ok", save=None, write=False):
        def arguments(c):
            values = args(c) if callable(args) else dict(args)
            if name == "doc_get":
                values["max_results"] = 1000
            if write:
                values["expect_document"] = _ctx_get(c, "org_doc", "owned organization document")
            return values
        rows.append((name, arguments, check, save))

    def save(key, getter):
        return key, _recall(key, getter)

    def box(sketch, low, high, height):
        row("sketch_create", {"plane": "xy", "name": sketch}, write=True)
        row("sketch_add_geometry", {"sketch_name": sketch, "geometry": [
            {"kind": "rectangle", "x1": low[0], "y1": low[1],
             "x2": high[0], "y2": high[1]}]}, write=True)
        row("model_extrude", {"sketch_name": sketch, "distance": height}, _extruded, write=True)

    def vertices(target, check, capture=None):
        row("find_geometry", lambda c: {"target": target(c) if callable(target) else target,
            "kind": "vertex", "units": "mm", "max_results": 64}, check, capture)

    def source_ref(c):
        return "OrgSource:2:" + _ctx_get(c, "org_body_name", "selected body")

    for kind, mode, surface in (("brep", "parametric", False), ("mesh", "parametric", False),
                                ("brep", "direct", False), ("mesh", "direct", False),
                                ("brep", "parametric", True)):
        row("doc_get", {}, _home_document, save("org_home", _home_address))
        row("doc_new", lambda c: {"expect_document": _ctx_get(c, "org_home", "home")},
            _new_document, save("org_doc", lambda p: p["document_handle"]))
        row("doc_get", {}, lambda p: (p.get("active") or {}).get("document_handle") == _RECALL.get("org_doc"),
            save("org_body_name", lambda p, kind=kind: "OrgMesh" if kind == "mesh" else "Body1"))
        # The literal root selector resets the sweep layout cursor for this owned document.
        rows.append(("design_activate_component", {"occurrence": "root"}, "ok", None))
        if mode == "direct":
            row("design_set_mode", {"target": "direct", "confirm_history_loss": True},
                lambda p: p.get("now") == "direct", write=True)
        row("model_create_component", {"name": "OrgSource", "activate": True, "x": 40, "y": 20,
            "z": 10, "rotate_deg": 90, "rotate_axis": "z"}, _made_component, write=True)
        box("OrgPicked", (2, 3), (14, 11), 7)
        box("OrgSibling", (22, 3), (28, 10), 13)
        if surface:
            row("find_geometry", {"target": "OrgSource:1:Body1", "kind": "planar_face",
                "max_results": 1}, _matched(1, "planar_face"), _fg("org_face"))
            row("surface_offset", lambda c: {"faces": [_ctx_get(c, "org_face", "face")],
                "distance": 0, "chaining": False},
                lambda p: p.get("offset") is True and p.get("is_solid") is False
                and len(p.get("result_bodies") or []) == 1,
                save("org_body_name", lambda p: p["result_bodies"][0]), write=True)
        if kind == "mesh":
            row("save_as_mesh", {"body": "OrgSource:1:Body1", "name": "OrgMesh", "quality": "low"},
                lambda p: p.get("triangle_count") == 12 and p.get("name") == "OrgMesh", write=True)
            row("save_as_mesh", {"body": "OrgSource:1:Body2", "name": "OrgSiblingMesh", "quality": "low"},
                lambda p: p.get("triangle_count") == 12 and p.get("name") == "OrgSiblingMesh", write=True)
        row("design_activate_component", {"occurrence": "root"}, write=True)
        row("model_create_component", {"name": "OrgDestination", "activate": True,
            "x": -30, "y": 70, "z": 5, "rotate_deg": -30, "rotate_axis": "z"},
            _made_component, write=True)
        box("OrgSentinel", (0, 0), (4, 6), 9)
        if kind == "mesh":
            row("save_as_mesh", {"body": "OrgDestination:1:Body1",
                "name": "OrgSentinelMesh", "quality": "low"},
                lambda p: p.get("triangle_count") == 12 and p.get("name") == "OrgSentinelMesh", write=True)
        row("design_activate_component", {"occurrence": "root"}, write=True)
        row("model_create_component", {"name": "OrgExistingChild", "parent": "OrgDestination:1"},
            lambda p: _made_component_inactive(p)
            and p.get("full_path") == "OrgDestination:1+OrgExistingChild:1", write=True)
        row("design_add_instance", {"component": "OrgSource", "x": -50, "y": -20,
            "z": 30, "rotate_deg": -45, "rotate_axis": "z"},
            lambda p: p.get("full_path") == "OrgSource:2", write=True)
        row("design_add_instance", {"component": "OrgDestination", "x": 70, "y": -50,
            "z": 10, "rotate_deg": 60, "rotate_axis": "z"},
            lambda p: p.get("full_path") == "OrgDestination:2", write=True)
        vertices((source_ref if surface else "OrgSource:2:Body1"),
                 lambda p, surface=surface: len(_org_vertices(p)) == (4 if surface else 8),
                 save("org_before", _org_vertices))
        vertices("OrgSource:2:Body2", lambda p: len(_org_vertices(p)) == 8,
                 save("org_sibling", _org_vertices))
        vertices("OrgDestination:2:Body1", lambda p: len(_org_vertices(p)) == 8,
                 save("org_sentinel", _org_vertices))
        if kind == "mesh":
            row("model_inspect", {"target": "OrgSource:2:OrgMesh"}, _org_mesh_shape,
                save("org_mesh_selected_before", _org_mesh_snapshot))
            row("model_inspect", {"target": "OrgSource:2:OrgSiblingMesh"},
                lambda p: _org_mesh_box_shape(p, "org_sibling", 546.0, 422.0),
                save("org_mesh_sibling_before", _org_mesh_snapshot))
            row("model_inspect", {"target": "OrgDestination:2:OrgSentinelMesh"},
                lambda p: _org_mesh_box_shape(p, "org_sentinel", 216.0, 228.0),
                save("org_mesh_sentinel_before", _org_mesh_snapshot))
            row("mesh_get", {"target": "OrgSource:2"}, _org_mesh_count(2),
                save("org_mesh_source_before", lambda p: p))
            row("mesh_get", {"target": "OrgDestination:2"}, _org_mesh_count(1),
                save("org_mesh_destination_before", lambda p: p))
        row("model_edit_body", lambda c: {"action": "copy", "body": source_ref(c)},
            _refused("destination"), write=True)
        vertices((source_ref if surface else "OrgSource:2:Body1"), _org_same_vertices("org_before"))
        if kind == "mesh":
            row("model_edit_body", lambda c: {"action": "copy", "body": source_ref(c),
                "destination": "OrgDestination:2"},
                _refused("Mesh copy", "OrgDestination:2", "component 'OrgDestination'",
                         "2 placements", "OrgDestination:1", "singly placed destination"), write=True)
            row("model_inspect", {"target": "OrgSource:2:OrgMesh"},
                _org_mesh_unchanged("org_mesh_selected_before"))
            row("model_inspect", {"target": "OrgSource:2:OrgSiblingMesh"},
                _org_mesh_unchanged("org_mesh_sibling_before"))
            row("model_inspect", {"target": "OrgDestination:2:OrgSentinelMesh"},
                _org_mesh_unchanged("org_mesh_sentinel_before"))
            row("mesh_get", {"target": "OrgSource:2"},
                _org_mesh_inventory_unchanged("org_mesh_source_before"))
            row("mesh_get", {"target": "OrgDestination:2"},
                _org_mesh_inventory_unchanged("org_mesh_destination_before"))
            row("design_activate_component", {"occurrence": "root"}, write=True)
            row("model_create_component", {"name": "OrgMeshLanding", "activate": True,
                "x": 110, "y": 40, "z": 15, "rotate_deg": -15, "rotate_axis": "z"},
                _made_component, write=True)
            box("OrgLandingSentinel", (0, 0), (4, 6), 9)
            row("save_as_mesh", {"body": "OrgMeshLanding:1:Body1",
                "name": "OrgLandingSentinelMesh", "quality": "low"},
                lambda p: p.get("triangle_count") == 12
                and p.get("name") == "OrgLandingSentinelMesh", write=True)
            row("design_activate_component", {"occurrence": "root"}, write=True)
            vertices("OrgMeshLanding:1:Body1", lambda p: len(_org_vertices(p)) == 8,
                     save("org_landing_sentinel", _org_vertices))
            row("model_inspect", {"target": "OrgMeshLanding:1:OrgLandingSentinelMesh"},
                lambda p: _org_mesh_box_shape(p, "org_landing_sentinel", 216.0, 228.0))
            row("mesh_get", {"target": "OrgMeshLanding:1"}, _org_mesh_count(1))
        landing = "OrgMeshLanding:1" if kind == "mesh" else "OrgDestination:2"
        row("model_edit_body", lambda c, landing=landing: {"action": "copy", "body": source_ref(c),
            "destination": landing}, _org_result("copy", kind, 3 if surface else 2, 2),
            save("org_copy", lambda p: p), write=True)
        if kind == "brep":
            vertices(lambda c: _ctx_get(c, "org_copy", "copy")["handle"], _org_same_vertices("org_before"))
            row("design_get", {"include": ["tree"], "tree_bodies": True, "tree_handles": True,
                "max_depth": 4}, _org_tree_counts({"OrgSource:1": 3 if surface else 2,
                                                  "OrgSource:2": 3 if surface else 2,
                                                  "OrgDestination:1": 2, "OrgDestination:2": 2}))
        else:
            row("model_inspect", lambda c: {"target": _ctx_get(c, "org_copy", "copy")["handle"]},
                _org_mesh_shape, save("org_mesh_copy_before", _org_mesh_snapshot))
            row("mesh_get", {"target": "OrgSource:2"}, _org_mesh_count(2))
            row("mesh_get", {"target": landing}, _org_mesh_count(2),
                save("org_mesh_landing_after_copy", lambda p: p))
            row("mesh_get", {"target": "OrgDestination:2"}, _org_mesh_count(1))
        if kind == "mesh" and mode == "direct":
            row("design_get", {"include": ["tree"], "tree_bodies": True,
                "tree_handles": True, "max_depth": 4},
                _org_tree_counts({"OrgMeshLanding:1": 1},
                                 no_children_of=("OrgMeshLanding:1",)))
            row("model_edit_body", lambda c: {"action": "create_component",
                "body": _ctx_get(c, "org_copy", "copy")["handle"]},
                _refused("Direct mesh create_component", "OrgMeshLanding:1",
                         "component 'OrgMeshLanding'", "nonidentity transforms",
                         "mesh in root", "identity-placed component"), write=True)
            row("model_inspect", lambda c: {"target": _ctx_get(c, "org_copy", "copy")["handle"]},
                _org_mesh_unchanged("org_mesh_copy_before"))
            row("model_inspect", {"target": "OrgSource:2:OrgMesh"},
                _org_mesh_unchanged("org_mesh_selected_before"))
            row("model_inspect", {"target": "OrgSource:2:OrgSiblingMesh"},
                _org_mesh_unchanged("org_mesh_sibling_before"))
            row("model_inspect", {"target": "OrgDestination:2:OrgSentinelMesh"},
                _org_mesh_unchanged("org_mesh_sentinel_before"))
            row("model_inspect", {"target": "OrgMeshLanding:1:OrgLandingSentinelMesh"},
                lambda p: _org_mesh_box_shape(p, "org_landing_sentinel", 216.0, 228.0))
            row("mesh_get", {"target": "OrgSource:2"},
                _org_mesh_inventory_unchanged("org_mesh_source_before"))
            row("mesh_get", {"target": "OrgDestination:2"},
                _org_mesh_inventory_unchanged("org_mesh_destination_before"))
            row("mesh_get", {"target": landing},
                _org_mesh_inventory_unchanged("org_mesh_landing_after_copy"))
            row("design_get", {"include": ["tree"], "tree_bodies": True,
                "tree_handles": True, "max_depth": 4},
                _org_tree_counts({"OrgMeshLanding:1": 1},
                                 no_children_of=("OrgMeshLanding:1",)))
            row("model_edit_body", lambda c: {"action": "move",
                "body": _ctx_get(c, "org_copy", "copy")["handle"], "destination": "root"},
                _org_result("move", "mesh", 2, 1), save("org_first_root", lambda p: p), write=True)
            row("model_inspect", lambda c: {"target": _ctx_get(c, "org_first_root", "root mesh")["handle"]},
                _org_mesh_shape)
            row("mesh_get", {"target": landing}, _org_mesh_count(1))
            row("mesh_get", {}, _org_mesh_count(5))
            row("model_edit_body", lambda c: {"action": "create_component",
                "body": _ctx_get(c, "org_first_root", "root mesh")["handle"]},
                _org_result("create_component", "mesh", 1, 1),
                save("org_first_child", lambda p: p), write=True)
            row("model_inspect", lambda c: {"target": _ctx_get(c, "org_first_child", "root child")["handle"]},
                _org_mesh_shape)
            row("mesh_get", lambda c: {"target": _ctx_get(c, "org_first_child", "root child")["full_path"]},
                _org_mesh_count(1))
            row("model_edit_body", lambda c: {"action": "create_component",
                "body": _ctx_get(c, "org_first_child", "root child")["handle"]},
                _org_result("create_component", "mesh", 1, 1),
                save("org_child", lambda p: p), write=True)
        else:
            row("model_edit_body", lambda c: {"action": "create_component",
                "body": _ctx_get(c, "org_copy", "copy")["handle"]},
                _org_result("create_component", kind, 2, 1), save("org_child", lambda p: p), write=True)
        row("design_get", {"include": ["tree"], "tree_bodies": True, "tree_handles": True, "max_depth": 4},
            _org_tree_counts({"OrgDestination:1+OrgExistingChild:1": 0,
                              "OrgDestination:2+OrgExistingChild:1": 0}))
        if kind == "brep":
            vertices(lambda c: _ctx_get(c, "org_child", "child")["handle"], _org_same_vertices("org_before"))
            row("design_get", {"include": ["tree"], "tree_bodies": True, "tree_handles": True,
                "max_depth": 4}, _org_tree_counts(lambda surface=surface: {
                    "OrgSource:1": 3 if surface else 2, "OrgSource:2": 3 if surface else 2,
                    "OrgDestination:1": 1, "OrgDestination:2": 1,
                    _RECALL["org_child"]["full_path"]: 1}))
        else:
            row("model_inspect", lambda c: {"target": _ctx_get(c, "org_child", "child")["handle"]},
                _org_mesh_shape)
            row("mesh_get", lambda c: {"target": _ctx_get(c, "org_child", "child")["full_path"]},
                _org_mesh_count(1))
            row("mesh_get", {"target": landing}, _org_mesh_count(1))
            row("mesh_get", {"target": "OrgDestination:2"}, _org_mesh_count(1))
        row("model_edit_body", lambda c: {"action": "move",
            "body": _ctx_get(c, "org_child", "new child")["handle"], "destination": "root"},
            _org_result("move", kind, 1, 1), save("org_root", lambda p: p), write=True)
        if kind == "brep":
            vertices(lambda c: _ctx_get(c, "org_root", "root body")["handle"], _org_same_vertices("org_before"))
            row("design_get", {"include": ["tree"], "tree_bodies": True, "tree_handles": True,
                "max_depth": 4}, _org_tree_counts(lambda surface=surface: {
                    "OrgSource:1": 3 if surface else 2, "OrgSource:2": 3 if surface else 2,
                    "OrgDestination:1": 1, "OrgDestination:2": 1,
                    _RECALL["org_child"]["full_path"]: 0}, root_count=1))
            row("model_move", lambda c: {"bodies": [_ctx_get(c, "org_root", "root body")["handle"]],
                "dx": 1, "units": "mm"}, _moved, write=True)
            vertices(lambda c: _ctx_get(c, "org_root", "root body")["handle"], _org_translated_vertices)
        else:
            row("model_inspect", lambda c: {"target": _ctx_get(c, "org_root", "root mesh")["handle"]},
                _org_mesh_shape)
            row("mesh_get", lambda c: {"target": _ctx_get(c, "org_child", "child")["full_path"]},
                _org_mesh_count(0))
            row("mesh_get", {}, _org_mesh_count(5))
            row("mesh_to_brep", lambda c: {"mesh": _ctx_get(c, "org_root", "root mesh")["handle"],
                "method": "faceted"}, lambda p: p.get("converted") is True
                and len(p.get("brep_bodies") or []) == 1,
                save("org_converted", lambda p: p["brep_bodies"][0]["handle"]), write=True)
            vertices(lambda c: _ctx_get(c, "org_converted", "converted body"), _org_same_vertices("org_before"))
        vertices("OrgSource:2:Body2", _org_same_vertices("org_sibling"))
        vertices("OrgDestination:2:Body1", _org_same_vertices("org_sentinel"))
        if kind == "mesh":
            row("model_inspect", {"target": "OrgSource:2:OrgMesh"},
                _org_mesh_unchanged("org_mesh_selected_before"))
            row("model_inspect", {"target": "OrgSource:2:OrgSiblingMesh"},
                _org_mesh_unchanged("org_mesh_sibling_before"))
            row("model_inspect", {"target": "OrgDestination:2:OrgSentinelMesh"},
                _org_mesh_unchanged("org_mesh_sentinel_before"))
            row("model_inspect", {"target": "OrgMeshLanding:1:OrgLandingSentinelMesh"},
                lambda p: _org_mesh_box_shape(p, "org_landing_sentinel", 216.0, 228.0))
        row("doc_close", lambda c: {"name": _ctx_get(c, "org_doc", "owned document"),
            "save_changes": False}, _document_closed, write=True)
        row("doc_activate", lambda c: {"name": _ctx_get(c, "org_home", "home")},
            lambda p: p.get("activated") is True)
        row("doc_get", {}, lambda p: (p.get("active") or {}).get("document_handle") == _RECALL.get("org_home"))

    for kind in ("brep", "mesh"):
        row("doc_get", {}, _home_document, save("org_home", _home_address))
        row("doc_new", lambda c: {"expect_document": _ctx_get(c, "org_home", "home")},
            _new_document, save("org_doc", lambda p: p["document_handle"]))
        rows.append(("design_activate_component", {"occurrence": "root"}, "ok", None))
        row("model_create_component", {"name": "OrgSameSource", "activate": True,
            "x": 40, "y": 20, "z": 10, "rotate_deg": 90, "rotate_axis": "z"},
            _made_component, write=True)
        box("OrgSamePicked", (2, 3), (14, 11), 7)
        box("OrgSameSibling", (22, 3), (28, 10), 13)
        if kind == "mesh":
            row("save_as_mesh", {"body": "OrgSameSource:1:Body1", "name": "OrgSameMesh",
                "quality": "low"}, lambda p: p.get("triangle_count") == 12
                and p.get("name") == "OrgSameMesh", write=True)
            row("save_as_mesh", {"body": "OrgSameSource:1:Body2", "name": "OrgSameSiblingMesh",
                "quality": "low"}, lambda p: p.get("triangle_count") == 12
                and p.get("name") == "OrgSameSiblingMesh", write=True)
        row("design_activate_component", {"occurrence": "root"}, write=True)
        vertices("OrgSameSource:1:Body1", lambda p: len(_org_vertices(p)) == 8,
                 save("org_before", _org_vertices))
        vertices("OrgSameSource:1:Body2", lambda p: len(_org_vertices(p)) == 8,
                 save("org_same_sibling", _org_vertices))
        same_ref = "OrgSameSource:1:OrgSameMesh" if kind == "mesh" else "OrgSameSource:1:Body1"
        if kind == "mesh":
            row("mesh_get", {"target": "OrgSameSource:1"}, _org_mesh_count(2),
                save("org_same_mesh_rows", lambda p: p["meshes"]))
            row("model_inspect", {"target": same_ref}, _org_mesh_shape)
            row("model_inspect", {"target": "OrgSameSource:1:OrgSameSiblingMesh"},
                _org_same_mesh_sibling)
        else:
            row("design_get", {"include": ["tree"], "tree_bodies": True, "tree_handles": True,
                "max_depth": 3}, _org_tree_counts({"OrgSameSource:1": 2}))
        row("design_get", {"include": ["timeline"], "max_results": 1000}, "ok",
            save("org_same_history", lambda p: p["timeline"]))
        row("model_edit_body", {"action": "move", "body": same_ref,
            "destination": "OrgSameSource:1"},
            _refused("Cannot copy the body" if kind == "brep" else "bodyPaths.size() == 1"),
            write=True)
        row("design_get", {"include": ["timeline"], "max_results": 1000},
            lambda p: _org_same_timeline(p, False))
        if kind == "mesh":
            row("mesh_get", {"target": "OrgSameSource:1"},
                lambda p: _org_same_mesh_inventory(p, 2))
            row("model_inspect", {"target": same_ref}, _org_mesh_shape)
            row("model_inspect", {"target": "OrgSameSource:1:OrgSameSiblingMesh"},
                _org_same_mesh_sibling)
        else:
            vertices(same_ref, _org_same_vertices("org_before"))
            row("design_get", {"include": ["tree"], "tree_bodies": True, "tree_handles": True,
                "max_depth": 3}, _org_tree_counts({"OrgSameSource:1": 2}))
        vertices("OrgSameSource:1:Body2", _org_same_vertices("org_same_sibling"))
        row("model_edit_body", {"action": "copy", "body": same_ref,
            "destination": "OrgSameSource:1"}, _org_same_copy_result(kind),
            save("org_same_copy", lambda p: p), write=True)
        row("design_get", {"include": ["timeline"], "max_results": 1000},
            lambda p: _org_same_timeline(p, True))
        if kind == "mesh":
            row("model_inspect", lambda c: {"target": _ctx_get(c, "org_same_copy", "copied mesh")["handle"]},
                _org_same_mesh_copy, save("org_same_copied_name", lambda p: p["name"]))
            row("mesh_get", {"target": "OrgSameSource:1"},
                lambda p: _org_same_mesh_inventory(p, 3))
            row("model_inspect", {"target": same_ref}, _org_mesh_shape)
            row("model_inspect", {"target": "OrgSameSource:1:OrgSameSiblingMesh"},
                _org_same_mesh_sibling)
        else:
            vertices(lambda c: _ctx_get(c, "org_same_copy", "copied body")["handle"],
                     _org_same_vertices("org_before"))
            row("design_get", {"include": ["tree"], "tree_bodies": True, "tree_handles": True,
                "max_depth": 3}, _org_tree_counts({"OrgSameSource:1": 3}))
            row("model_move", lambda c: {"bodies": [_ctx_get(c, "org_same_copy", "copied body")["handle"]],
                "dx": 1, "units": "mm"}, _moved, write=True)
            vertices(lambda c: _ctx_get(c, "org_same_copy", "copied body")["handle"],
                     _org_translated_vertices)
            vertices(same_ref, _org_same_vertices("org_before"))
        vertices("OrgSameSource:1:Body2", _org_same_vertices("org_same_sibling"))
        row("doc_close", lambda c: {"name": _ctx_get(c, "org_doc", "same-owner document"),
            "save_changes": False}, _document_closed, write=True)
        row("doc_activate", lambda c: {"name": _ctx_get(c, "org_home", "home")},
            lambda p: p.get("activated") is True)
        row("doc_get", {}, lambda p: (p.get("active") or {}).get("document_handle") == _RECALL.get("org_home"))

    row("doc_get", {}, _home_document, save("org_home", _home_address))
    row("doc_new", lambda c: {"expect_document": _ctx_get(c, "org_home", "home")},
        _new_document, save("org_doc", lambda p: p["document_handle"]))
    rows.append(("design_activate_component", {"occurrence": "root"}, "ok", None))
    row("model_create_component", {"name": "OrgSphere", "activate": True,
        "x": 40, "y": 20, "z": 10, "rotate_deg": 90, "rotate_axis": "z"},
        _made_component, write=True)
    row("sketch_create", {"plane": "xy", "name": "OrgSphereProfile"}, write=True)
    row("sketch_add_geometry", {"sketch_name": "OrgSphereProfile", "geometry": [
        {"kind": "arc", "cx": 0, "cy": 0, "x1": 0, "y1": 6, "sweep_deg": 180},
        {"kind": "line", "x1": 0, "y1": -6, "x2": 0, "y2": 6}]}, write=True)
    row("model_revolve", {"sketch_name": "OrgSphereProfile", "axis": "y", "angle_deg": 360},
        lambda p: p.get("revolved") is True and len(p.get("result_bodies") or []) == 1,
        save("org_sphere_body", lambda p: "OrgSphere:1:" + p["result_bodies"][0]), write=True)
    row("design_activate_component", {"occurrence": "root"}, write=True)
    row("model_create_component", {"name": "OrgSphereDestination", "activate": True,
        "x": -30, "y": 70, "z": 5, "rotate_deg": -30, "rotate_axis": "z"},
        _made_component, write=True)
    row("model_inspect", lambda c: {"target": _ctx_get(c, "org_sphere_body", "sphere"),
        "include": ["mass"], "units": "mm", "accuracy": "very_high"}, _org_sphere_mass)
    row("find_geometry", lambda c: {"target": _ctx_get(c, "org_sphere_body", "sphere"),
        "kind": "vertex", "units": "mm", "max_results": 64},
        lambda p: p.get("truncated") is not True
        and p.get("match_count") == len(p.get("matches") or []),
        save("org_sphere_vertex_count", lambda p: p["match_count"]))
    for action, input_key, output_key, destination in (
            ("copy", "org_sphere_body", "org_sphere_copy", "OrgSphereDestination:1"),
            ("create_component", "org_sphere_copy", "org_sphere_child", None),
            ("move", "org_sphere_child", "org_sphere_root", "root")):
        def sphere_args(c, action=action, input_key=input_key, destination=destination):
            value = _ctx_get(c, input_key, "sphere target")
            args = {"action": action, "body": value if isinstance(value, str) else value["handle"]}
            if destination is not None:
                args["destination"] = destination
            return args
        row("model_edit_body", sphere_args, _org_result(action, "brep", 1, 1),
            save(output_key, lambda p: p), write=True)
        row("model_inspect", lambda c, key=output_key: {
            "target": _ctx_get(c, key, "organized sphere")["handle"],
            "include": ["mass"], "units": "mm", "accuracy": "very_high"}, _org_sphere_mass)
        row("find_geometry", lambda c, key=output_key: {
            "target": _ctx_get(c, key, "organized sphere")["handle"],
            "kind": "sphere_face", "units": "mm", "max_results": 8},
            _matched(1, "sphere_face"))
    row("design_get", {"include": ["tree"], "tree_bodies": True, "tree_handles": True, "max_depth": 4},
        _org_tree_counts(lambda: {"OrgSphere:1": 1, "OrgSphereDestination:1": 0,
                                 _RECALL["org_sphere_child"]["full_path"]: 0}, root_count=1))
    row("doc_close", lambda c: {"name": _ctx_get(c, "org_doc", "sphere document"),
        "save_changes": False}, _document_closed, write=True)
    row("doc_activate", lambda c: {"name": _ctx_get(c, "org_home", "home")},
        lambda p: p.get("activated") is True)
    row("doc_get", {}, lambda p: (p.get("active") or {}).get("document_handle") == _RECALL.get("org_home"))
    return rows


_BODY_ORGANIZATION = _body_organization_rows()


_EXTRUDE_EDITS = _extrude_edit_rows()

# --- ACT 2: SOLIDS - the parts turn solid, each part its own color (mirrors scenario S2) -------
# The hero solids ride on ACT 1's parametric sketches; the multi-body feature tools that have no
# natural home on the part (draft/mirror/patterns/combine) ride cameo bodies in the SAME
# document, so every one is exercised without contorting the mechanism.
def _sweep_mode_shape(p):
    """Return the independent body volume, area and world bounds used by sweep edit rows."""
    mass = p.get("mass") or {}
    return {"volume": mass.get("volume"), "area": mass.get("area"),
            "min": p.get("min_point"), "max": p.get("max_point")}


def _sweep_mode_box_equal(left, right, tol=0.0001):
    """Compare complete measured body bounds without accepting unread coordinates."""
    return all(isinstance((left.get(side) or {}).get(axis), (int, float))
               and isinstance((right.get(side) or {}).get(axis), (int, float))
               and math.isfinite(left[side][axis]) and math.isfinite(right[side][axis])
               and abs(left[side][axis] - right[side][axis]) <= tol
               for side in ("min", "max") for axis in ("x", "y", "z"))


def _sweep_mode_expected_volume(case, stage):
    """Return the selected stock volume after clipping a circular sweep at x=0.05 cm."""
    radius = 0.1 if stage == "before" else 0.15
    length = 3.0 if stage == "path" else 2.0
    cap = 0.05
    disk = math.pi * radius * radius
    inside = (disk / 2 + cap * math.sqrt(radius * radius - cap * cap)
              + radius * radius * math.asin(cap / radius))
    return {"join": 1.65 + (disk - inside) * length,
            "cut": 1.65 - inside * length,
            "intersect": inside * length}[case]


def _sweep_mode_solid(case, stage, role, previous=None):
    """Require a selected volume change or a pristine independent witness read."""
    def check(p):
        got = _sweep_mode_shape(p)
        old = _RECALL.get(previous) if previous else None
        volume, area = got["volume"], got["area"]
        valid = (p.get("kind") == "body" and p.get("units") == "cm"
                 and (p.get("mass") or {}).get("accuracy_used") == "very_high"
                 and isinstance(volume, (int, float)) and math.isfinite(volume) and volume > 0
                 and isinstance(area, (int, float)) and math.isfinite(area) and area > 0
                 and _sweep_mode_box_equal(got, got)
                 and (previous is None or old is not None))
        if valid and role == "SelectedStock":
            valid = abs(volume - _sweep_mode_expected_volume(case, stage)) <= 0.002
        if valid and role != "SelectedStock":
            lo, hi, expected_volume = {
                "UnselectedStock": ((0.06, -0.5, 0), (0.6, 0.5, 3), 1.62),
                "OverlappingForeign": ((0.08, -0.5, 0), (0.3, 0.5, 3), 0.66),
            }[role]
            expected_box = {"min": dict(zip(("x", "y", "z"), lo)),
                            "max": dict(zip(("x", "y", "z"), hi))}
            valid = (abs(volume - expected_volume) <= 0.002
                     and _sweep_mode_box_equal(got, expected_box, 0.001))
        if old is not None and valid:
            if role == "SelectedStock":
                valid = (isinstance(old.get("volume"), (int, float))
                         and abs(volume - old["volume"]) > 0.0001)
            else:
                valid = (abs(volume - old["volume"]) <= 0.00001
                         and abs(area - old["area"]) <= 0.00001
                         and _sweep_mode_box_equal(got, old))
        return _measured(f"{case} {stage} {role} independent volume/bounds",
                         {"current": got, "previous": old,
                          "selected_expected_cm3": (_sweep_mode_expected_volume(case, stage)
                                                    if role == "SelectedStock" else None)}, valid)
    return check


def _sweep_mode_edit(case, action, surface=False):
    """Require one edit to retain its feature, scope, marker and readable body shape."""
    def check(p):
        after = p.get("target_after") or []
        shape = after[0] if len(after) == 1 else {}
        return _measured(f"{case} {action} sweep definition and participants", p,
                         p.get("edited") is True and p.get("action") == action
                         and p.get("same_feature") is True
                         and p.get("definition_matches") is True
                         and (p.get("definition_before") or {}).get("profile_members") == 1
                         and (p.get("definition_after") or {}).get("profile_members") == 1
                         and p.get("geometry_changed") is True
                         and p.get("participant_scope_preserved") is True
                         and p.get("participants_replayed") is (not surface)
                         and p.get("retained_participants") == ([] if surface else ["SelectedStock"])
                         and p.get("marker_restored") is True
                         and p.get("outside_body_changes") == []
                         and p.get("new_timeline_errors") == []
                         and p.get("new_timeline_warnings") == []
                         and shape.get("solid") is (not surface)
                         and (shape.get("volume_cm3") is None if surface else
                              isinstance(shape.get("volume_cm3"), (int, float))))
    return check


def _sweep_mode_surface(case, stage, previous=None):
    """Require the independently found surface face area to change after each edit."""
    def check(p):
        rows = p.get("matches") or []
        row = rows[0] if len(rows) == 1 else {}
        area = row.get("area")
        old = _RECALL.get(previous) if previous else None
        valid = (p.get("units") == "cm" and p.get("match_count") == 1
                 and p.get("returned") == 1 and p.get("truncated") is not True
                 and isinstance(area, (int, float)) and math.isfinite(area) and area > 0
                 and (previous is None or old is not None))
        width = 0.2 if stage == "before" else 0.3
        length = 3.0 if stage == "path" else 2.0
        expected = width * length if case == "open" else math.pi * width * length
        if valid:
            valid = abs(area - expected) <= 0.005
        if old is not None and valid:
            valid = abs(area - old) > 0.01
        return _measured(f"{case} {stage} independent surface face area",
                         {"area_cm2": area, "expected_cm2": expected,
                          "previous_cm2": old}, valid)
    return check


def _sweep_mode_bounds(case, stage, previous=None):
    """Require a complete surface body box, changed after each edit."""
    def check(p):
        got = _sweep_mode_shape(p)
        old = _RECALL.get(previous) if previous else None
        valid = (p.get("kind") == "body" and p.get("units") == "cm"
                 and _sweep_mode_box_equal(got, got)
                 and (previous is None or old is not None))
        expected_x = 0.2 if stage == "before" else 0.3
        expected_z = 3.0 if stage == "path" else 2.0
        if valid:
            valid = (_near(p.get("x"), expected_x, 0.01)
                     and _near(p.get("z"), expected_z, 0.01))
        if old is not None and valid:
            valid = not _sweep_mode_box_equal(got, old, 0.01)
        return _measured(f"{case} {stage} independent surface bounds",
                         {"current": got, "x": p.get("x"), "z": p.get("z"),
                          "expected_x": expected_x, "expected_z": expected_z,
                          "previous": old}, valid)
    return check


def _sweep_edit_modes_rows():
    """Exercise scoped boolean and surface sweep edits in one owned scratch document."""
    rows = [("doc_get", {}, _home_document, ("sem_story", _home_address)),
            ("doc_new", lambda c: {"expect_document": _ctx_get(c, "sem_story", "story")},
             _new_document, ("sem_doc", lambda p: p["document_handle"]))]

    def write(name, args, check="ok", save=None):
        rows.append((name, lambda c, args=args: _combine_pin(
            c, "sem_doc", args(c) if callable(args) else args), check, save))

    def read(name, args, check, save=None):
        rows.append((name, args, check, save))

    def box(component, name, low, high, key):
        sketch = component + name + "S"
        write("sketch_create", {"plane": "xy", "name": sketch})
        write("sketch_add_geometry", {"sketch_name": sketch, "geometry": [
            {"kind": "rectangle", "x1": low[0], "y1": low[1],
             "x2": high[0], "y2": high[1]}]})
        write("model_extrude", {"sketch_name": sketch, "profile_index": 0,
                                "distance": high[2]}, _extruded,
              (key, lambda p: p["result_bodies"][0]))
        write("design_set_name", lambda c: {
            "target": component + ":" + _ctx_get(c, key, "new stock body"),
            "new_name": name}, lambda p: p.get("renamed") is True and p.get("name") == name)

    def solid_read(case, stage, component, role, previous=None):
        key = f"sem_{case}_{stage}_{role}"
        read("model_inspect", {"target": f"{component}:{role}",
                               "include": ["default", "mass"], "units": "cm",
                               "accuracy": "very_high"},
             _sweep_mode_solid(case, stage, role, previous),
             (key, _recall(key, _sweep_mode_shape)))
        return key

    def surface_read(case, stage, component, face_kind, previous_area=None,
                     previous_bounds=None):
        target = f"{component}:SweepSheet"
        bkey, akey = f"sem_{case}_{stage}_bounds", f"sem_{case}_{stage}_area"
        read("model_inspect", {"target": target, "units": "cm"},
             _sweep_mode_bounds(case, stage, previous_bounds),
             (bkey, _recall(bkey, _sweep_mode_shape)))
        read("find_geometry", {"target": target, "kind": face_kind,
                               "units": "cm", "max_results": 2},
             _sweep_mode_surface(case, stage, previous_area),
             (akey, _recall(akey, lambda p: p["matches"][0]["area"])))
        return akey, bkey

    for case in ("join", "cut", "intersect"):
        host, foreign = "Sweep" + case.title(), "Foreign" + case.title()
        write("model_create_component", {"name": host, "activate": True}, _made_component)
        for name, radius in (("OriginalProfile", 1), ("AlternateProfile", 1.5)):
            write("sketch_create", {"plane": "xy", "name": name})
            write("sketch_add_geometry", {"sketch_name": name, "component": host, "geometry": [
                {"kind": "circle", "cx": 0, "cy": 0, "radius": radius}]})
        for name, length in (("OriginalPath", 20), ("AlternatePath", 30)):
            write("sketch_create", {"plane": "xz", "name": name})
            write("sketch_add_geometry", {"sketch_name": name, "component": host, "geometry": [
                {"kind": "line", "x1": 0, "y1": 0, "x2": 0, "y2": -length}]})
        for role, lo, hi in (
                ("SelectedStock", (-5, -5, 0), (0.5, 5, 30)),
                ("UnselectedStock", (0.6, -5, 0), (6, 5, 30))):
            box(host, role, lo, hi, f"sem_{case}_{role}_body")
        write("design_activate_component", {"occurrence": "root"})
        write("model_create_component", {"name": foreign, "activate": True}, _made_component)
        for role, lo, hi in (
                ("OverlappingForeign", (0.8, -5, 0), (3, 5, 30)),):
            box(foreign, role, lo, hi, f"sem_{case}_{role}_body")
        write("design_activate_component", {"occurrence": host + ":1"})
        feature_key = f"sem_{case}_feature"
        write("model_sweep", {"profile": {"sketch": "OriginalProfile", "profile_index": 0},
                              "path": "sketch:OriginalPath", "operation": case,
                              "target_bodies": [f"{host}:SelectedStock"], "component": host},
              lambda p, case=case, host=host: _measured(
                  f"{case} scoped sweep created", p,
                  p.get("swept") is True and p.get("operation") == case
                  and p.get("component") == host
                  and p.get("scoped_to_bodies") == ["SelectedStock"]
                  and p.get("is_solid") is True and bool(p.get("result_bodies"))),
              (feature_key, lambda p, host=host: host + "/" + p["feature"]))
        roles = ((host, "SelectedStock"), (host, "UnselectedStock"),
                 (foreign, "OverlappingForeign"))
        before = {role: solid_read(case, "before", component, role)
                  for component, role in roles}
        for action, operand in (("profile", {"sketch": "AlternateProfile", "profile_index": 0}),
                                ("path", "sketch:AlternatePath")):
            write("model_edit_sweep", lambda c, action=action, operand=operand, host=host,
                  feature_key=feature_key: {
                      "feature": _ctx_get(c, feature_key, "scoped sweep feature"),
                      "action": action, action: operand,
                      **({"component": host} if action == "profile" else {})},
                  _sweep_mode_edit(case, action))
            stage = action
            for component, role in roles:
                prior = before[role]
                before[role] = solid_read(case, stage, component, role, prior)
        write("design_activate_component", {"occurrence": "root"})

    for case, face_kind in (("open", "planar_face"), ("closed", "cylinder_face")):
        host = "Surface" + case.title()
        write("model_create_component", {"name": host, "activate": True}, _made_component)
        for name, width in (("OriginalProfile", 2), ("AlternateProfile", 3)):
            write("sketch_create", {"plane": "xy", "name": name})
            geometry = ({"kind": "line", "x1": 0, "y1": 0, "x2": width, "y2": 0}
                        if case == "open" else
                        {"kind": "circle", "cx": 0, "cy": 0, "radius": width / 2})
            write("sketch_add_geometry", {"sketch_name": name, "component": host, "geometry": [geometry]})
        for name, length in (("OriginalPath", 20), ("AlternatePath", 30)):
            write("sketch_create", {"plane": "xz", "name": name})
            write("sketch_add_geometry", {"sketch_name": name, "component": host, "geometry": [
                {"kind": "line", "x1": 0, "y1": 0, "x2": 0, "y2": -length}]})
        feature_key, body_key = f"sem_{case}_feature", f"sem_{case}_body"

        def surface_refs(p, host=host, body_key=body_key):
            _RECALL[body_key] = p["result_bodies"][0]
            return host + "/" + p["feature"]

        write("model_sweep", {"profile": {"sketch": "OriginalProfile", "profile_index": 0},
                              "path": "sketch:OriginalPath", "as_surface": True,
                              "component": host},
              lambda p, case=case, host=host: _measured(
                  f"{case} surface sweep created", p,
                  p.get("swept") is True and p.get("component") == host
                  and p.get("is_solid") is False
                  and p.get("as_surface") is True
                  and len(p.get("result_bodies") or []) == 1),
              (feature_key, surface_refs))
        write("design_set_name", lambda c, host=host, body_key=body_key: {
            "target": host + ":" + _RECALL[body_key],
            "new_name": "SweepSheet"},
            lambda p: p.get("renamed") is True and p.get("name") == "SweepSheet")
        area, bounds = surface_read(case, "before", host, face_kind)
        for action, operand in (("profile", {"sketch": "AlternateProfile", "profile_index": 0}),
                                ("path", "sketch:AlternatePath")):
            write("model_edit_sweep", lambda c, action=action, operand=operand, host=host,
                  feature_key=feature_key: {
                      "feature": _ctx_get(c, feature_key, "surface sweep feature"),
                      "action": action, action: operand,
                      **({"component": host} if action == "profile" else {})},
                  _sweep_mode_edit(case, action, surface=True))
            area, bounds = surface_read(case, action, host, face_kind, area, bounds)
        write("design_activate_component", {"occurrence": "root"})

    rows += [("doc_activate", lambda c: {"name": _ctx_get(c, "sem_story", "story"),
                                         "expect_document": _ctx_get(c, "sem_doc", "sweep modes")},
              "ok", None),
             ("doc_close", lambda c: {"name": _ctx_get(c, "sem_doc", "sweep modes"),
                                      "save_changes": False,
                                      "expect_document": _ctx_get(c, "sem_story", "story")},
              _document_closed, None)]
    return rows


_SWEEP_EDIT_MODES = _sweep_edit_modes_rows()


_SOLIDS = [
    # The sketch acts have already drawn the whole scratch field by now, so a whole-model fit is a
    # metre of scenery with the part a speck in it. Frame the profiles the features below consume,
    # and the bracket appears inside the shot instead of off the edge of one.
    _watch(["BracketBody", "BracketStep", "BracketPocket"]),
    ("design_activate_component", {"occurrence": "Bracket:1"}, "ok", None),
    # THE BLOCK, THE STEP AND THE BOSS - three extrudes off the three parametric profiles, each
    # taking its depth from the parameter that states it, so the resize walks the solid as well as
    # the sketches.
    ("model_extrude", {"sketch_name": "BracketBody", "profile_index": 0,
                       "distance": "PartHt - StepDrop"}, _extruded, None),
    # THE BLOCK MEASURED WHERE IT IS BUILT: the two span dimensions are the only thing standing
    # between the driver and the solid, and a dimension that anchored the wrong point leaves a
    # block of the wrong size that nothing downstream would name until the resize act.
    ("model_inspect", {"target": "Bracket:1"},
     lambda p: _measured("the block is PartLen x PartWid x (PartHt - StepDrop)",
                         {"x": p.get("x"), "y": p.get("y"), "z": p.get("z")},
                         _near(p.get("x"), 120.0, 0.1) and _near(p.get("y"), 80.0, 0.1)
                         and _near(p.get("z"), 30.0, 0.1)), None),
    ("model_extrude", {"sketch_name": "BracketStep", "profile_index": 0, "distance": "StepDrop",
                       "operation": "join"}, _extruded, None),
    ("model_extrude", {"sketch_name": "BracketBoss", "profile_index": 0, "distance": "PartHt / 8",
                       "operation": "join"}, _extruded, None),
    # WHAT A PARAMETER CHANGE TOUCHES, read instead of simulated: PartHt drives StepDrop and BoreDia
    # directly, reaches the boss diameter's own sketch dimension a hop further out, and the trace
    # names the extrudes that consume those sketches - the recompute an agent would otherwise have
    # to drive to find out. trace_depth=3 asks for the deep rows the default summarizes.
    ("param_get", {"name": "PartHt", "trace": True, "trace_depth": 3},
     _param_traced("PartHt", direct=("StepDrop", "BoreDia")), None),
    # THE POCKET, cut UP from its own floor and out through the step top - the direction with a
    # body in it. It runs one edge break PAST that face so the cut opens the pocket instead of
    # ending coincident with it.
    ("model_extrude", {"sketch_name": "BracketPocket", "profile_index": 0,
                       "distance": "PocketDepth + EdgeBreak", "operation": "cut"}, _extruded, None),
    # A MATERIAL-REMOVAL FEATURE IS JUDGED BY THE MATERIAL: the cut opened a floor 16 mm under the
    # step top, so the pocket floor is a planar face at z=14 that did not exist a step ago. A cut
    # that ran the wrong way, or found no body, leaves no such face.
    ("find_geometry", {"target": "Bracket", "kind": "planar_face", "nearest_to": [-35, 0, 14],
                       "max_results": 1}, _face_up_at(-35, 0, 14, tol=2.0), None),
    # THE POCKET'S CORNER RADII, at the parameter itself: model_fillet takes a radius EXPRESSION,
    # so the created feature holds 'PocketRad' rather than the number that expression evaluates to -
    # which is what lets the recompute in the resize act carry it.
    ("find_geometry", {"target": "Bracket", "kind": "line_edge", "nearest_to": [-50, -22, 22],
                       "max_results": 1}, _matched(1, "line_edge"), _fg("pk_c1")),
    ("find_geometry", {"target": "Bracket", "kind": "line_edge", "nearest_to": [-20, -22, 22],
                       "max_results": 1}, _matched(1, "line_edge"), _fg("pk_c2")),
    ("find_geometry", {"target": "Bracket", "kind": "line_edge", "nearest_to": [-20, 22, 22],
                       "max_results": 1}, _matched(1, "line_edge"), _fg("pk_c3")),
    ("find_geometry", {"target": "Bracket", "kind": "line_edge", "nearest_to": [-50, 22, 22],
                       "max_results": 1}, _matched(1, "line_edge"), _fg("pk_c4")),
    ("model_fillet", lambda c: {"edges": [_ctx_get(c, "pk_c1", "pocket corner one"),
                                          _ctx_get(c, "pk_c2", "pocket corner two"),
                                          _ctx_get(c, "pk_c3", "pocket corner three"),
                                          _ctx_get(c, "pk_c4", "pocket corner four")],
                                "radius": "PocketRad"}, _filleted, None),
    # THE TWO THROUGH BORES, one of them up the boss. model_hole's diameter is an EXPRESSION, so
    # these follow the part's own section where a fillet radius cannot.
    # EVERY hole below places its points in WORLD space. The default 'sketch' frame is the frame of
    # the placement sketch model_hole lays on the chosen face, and that frame is the face's, not the
    # world's; the tool converts a world point through the sketch's own converter and REFUSES one
    # that does not lie on the face, so the z coordinate is the face's own height.
    # Each face is MEASURED before it is drilled: a hole through the wrong face is a hole every
    # read after it still calls a hole. 'nearest_to' ranks by distance to each face's own CENTROID,
    # not to the nearest point on it - measured: a probe sitting ON this top face but off toward
    # its edge lost to the block's L-shaped +Y side wall, whose centroid was nearer - so every
    # probe below is aimed at the centroid the face it wants will have.
    # The raised half spans x[-10,60] and its middle is x=25; the boss standing on it takes a
    # circular bite that pulls the centroid about 1.2 mm back along -x, which the band absorbs.
    ("find_geometry", {"target": "Bracket", "kind": "planar_face", "nearest_to": [25, 0, 40],
                       "max_results": 1}, _face_up_at(25, 0, 40, tol=2.0), _fg("step_top")),
    ("model_hole", lambda c: {"face": _ctx_get(c, "step_top", "the high half of the top"),
                              "hole_type": "simple", "diameter": "BoreDia", "extent": "through",
                              "points_space": "world", "points": [[20, 0, 40]]}, _drilled(1), None),
    ("find_geometry", {"target": "Bracket", "kind": "planar_face", "nearest_to": [45, 0, 45],
                       "max_results": 1}, _face_up_at(45, 0, 45, tol=0.5), _fg("boss_top")),
    ("model_hole", lambda c: {"face": _ctx_get(c, "boss_top", "the boss top"),
                              "hole_type": "simple", "diameter": "BoreDia", "extent": "through",
                              "points_space": "world", "points": [[45, 0, 45]]}, _drilled(1), None),
    # THE MOUNTING PATTERN: four COUNTERBORED holes through the low half of the top in one call -
    # 'holes_verified' counts the drill axes off the created feature, so four here is four.
    # the low half spans x[-60,-10]: its middle is x=-35, and the pocket it lost is centred there
    # too, so removing that opening leaves the centroid where it was.
    ("find_geometry", {"target": "Bracket", "kind": "planar_face", "nearest_to": [-35, 0, 30],
                       "max_results": 1}, _face_up_at(-35, 0, 30, tol=2.0), _fg("low_top")),
    ("model_hole", lambda c: {"face": _ctx_get(c, "low_top", "the low half of the top"),
                              "hole_type": "counterbore", "diameter": "MountDia",
                              "cbore_diameter": "MountDia * 1.8", "cbore_depth": "EdgeBreak",
                              "extent": "through", "points_space": "world",
                              "points": [[-45, 30, 30], [-25, 30, 30],
                                         [-45, -30, 30], [-25, -30, 30]]},
     _drilled(4), None),
    # THE HANDLED EDGES, and the split between the two tools: a fillet RADIUS may be a parameter
    # expression, so the rounded edge carries 'EdgeBreak' itself; a chamfer DISTANCE is judged
    # against the number it was given, so it stays a literal READ from that same parameter.
    ("param_get", {"name": "EdgeBreak"}, _param_read("EdgeBreak", 3),
     ("edge_break", lambda p: p["parameter"]["value"])),
    ("find_geometry", {"target": "Bracket", "kind": "line_edge", "nearest_to": [-10, 0, 40],
                       "max_results": 1}, _matched(1, "line_edge"), _fg("step_lead")),
    ("model_fillet", lambda c: {"edges": [_ctx_get(c, "step_lead", "the step's leading edge")],
                                "radius": "EdgeBreak"}, _filleted, None),
    ("find_geometry", {"target": "Bracket", "kind": "line_edge", "nearest_to": [60, 0, 40],
                       "max_results": 1}, _matched(1, "line_edge"), _fg("step_out")),
    ("model_chamfer", lambda c: {"edges": [_ctx_get(c, "step_out", "the step's outboard edge")],
                                 "distance": _ctx_get(c, "edge_break", "the edge break")},
     _chamfered, None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    # The WCS anchor the CAM setup binds to, at the part's own origin: parametric, so it holds
    # position through the recompute the resize act drives.
    ("joint_create_origin", {"anchor": "coordinates", "target": "origin", "name": "StockCenter"},
     _joint_origin_at("StockCenter", 0, 0, 0), None),
    # THE TWO SOLID BUILDERS THE BRACKET HAS NO HOME FOR, each on a cameo of its own out on the
    # field: a base-to-post loft and a swept boss.
    # a default create with no 'part_number' input: the new component's own partNumber is WRITTEN
    # to its name (the timestamp Fusion mints it with otherwise), read back off the receipt.
    ("model_create_component", {"name": "LoftCameo", "activate": True},
     lambda p: _made_component(p) and _measured("part_number defaults to the component's own name",
                                                 {"part_number": p.get("part_number"),
                                                  "component": p.get("component")},
                                                 p.get("part_number") == p.get("component")), None),
    ("sketch_create", {"plane": "xy", "name": "LoftBase"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 250, "cy": 0, "radius": 16}],
                             "sketch_name": "LoftBase"}, "ok", None),
    ("sketch_get", {"sketch_name": "LoftBase"}, "ok", _prof("loft_base")),
    ("model_construction", {"kind": "plane", "plane": "xy", "offset": 40, "name": "LoftTopPlane"},
     _datum_plane("xy"), None),
    ("sketch_create", {"plane": "LoftTopPlane", "name": "LoftTop"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 250, "cy": 0, "radius": 8}],
                             "sketch_name": "LoftTop"}, "ok", None),
    ("sketch_get", {"sketch_name": "LoftTop"}, "ok", _prof("loft_top")),
    ("model_loft", lambda c: {"profiles": [_ctx_get(c, "loft_base", "the loft's base profile"),
                                           _ctx_get(c, "loft_top", "the loft's top profile")]},
     _lofted, ("sweep_edit_witness_body", lambda p: p["result_bodies"][0])),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "SweepCameo", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xz", "name": "SweepPath"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 250, "y1": 0,
                                           "x2": 250, "y2": -50}],
                             "sketch_name": "SweepPath"}, "ok", None),
    ("sketch_create", {"plane": "xy", "name": "SweepProf"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 250, "cy": 0, "radius": 5}],
                             "sketch_name": "SweepProf"}, "ok", None),
    ("sketch_create", {"plane": "xy", "name": "SweepProfWide"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 250, "cy": 0, "radius": 8}],
                             "sketch_name": "SweepProfWide"}, "ok", None),
    ("sketch_create", {"plane": "xz", "name": "SweepPathArc"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "arc", "cx": 300, "cy": 0,
                                            "x1": 250, "y1": 0, "sweep_deg": 90}],
                             "sketch_name": "SweepPathArc"}, "ok", None),
    ("sketch_create", {"plane": "xz", "name": "SweepPathBrepSource"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [
        {"kind": "line", "x1": 250, "y1": 0, "x2": 250, "y2": -10},
        {"kind": "arc", "cx": 260, "cy": -10, "x1": 250, "y1": -10, "sweep_deg": 45}],
        "sketch_name": "SweepPathBrepSource"}, "ok", None),
    ("model_extrude", {"sketch_name": "SweepPathBrepSource", "distance": 3,
                       "as_surface": True}, _extruded,
     ("sweep_brep_strip", lambda p: p["result_bodies"][0])),
    ("model_sweep", {"profile": {"sketch": "SweepProf", "profile_index": 0},
                     "path": "sketch:SweepPath"}, _swept,
     ("sweep_edit_body", lambda p: p["result_bodies"][0])),
    ("find_geometry", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_edit_body", "sweep body"),
                                  "kind": "planar_face", "nearest_to": [250, 0, 50],
                                  "max_results": 1}, _matched(1, "planar_face"), _fg("sweep_end_cap")),
    ("model_construction", lambda c: {"kind": "plane", "plane": _ctx_get(c, "sweep_end_cap", "end cap"),
                                       "offset": 2, "name": "SweepSupportPlane"},
     _datum_plane("xy"), None),
    ("sketch_create", {"plane": "SweepSupportPlane", "name": "SweepDependent"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 0, "cy": 0, "radius": 2}],
                             "sketch_name": "SweepDependent"}, "ok", None),
    ("model_extrude", {"sketch_name": "SweepDependent", "distance": 1}, _extruded,
     ("sweep_dependent_body", _recall("sweep_dependent_body", lambda p: p["result_bodies"][0]))),
    ("design_get", {"include": ["tree"], "component": "SweepCameo", "tree_bodies": True}, "ok",
     ("sweep_dependent_handle", lambda p: next(
         body["handle"] for body in p["tree"]["tree"]["bodies"]
         if body["name"] == _RECALL["sweep_dependent_body"]))),
    ("model_inspect", lambda c: {"target": _ctx_get(c, "sweep_dependent_handle", "dependent handle"),
                                 "include": ["default", "mass"], "units": "cm"}, "ok",
     ("sweep_dependent_before", _recall("sweep_dependent_before", lambda p: {
         "volume": p["mass"]["volume"], "min_point": p["min_point"],
         "max_point": p["max_point"]}))),
    ("model_inspect", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_edit_body", "sweep body"),
                                 "include": ["mass"], "units": "cm"},
     _sweep_inspected_at_volume(math.pi * 0.5 ** 2 * 5), None),
    ("model_inspect", lambda c: {"target": "LoftCameo:" + _ctx_get(
        c, "sweep_edit_witness_body", "loft witness"), "include": ["mass"], "units": "cm"},
     lambda p: _num((p.get("mass") or {}).get("volume")),
     ("sweep_edit_witness_volume", _recall("sweep_edit_witness_volume",
                                              lambda p: p["mass"]["volume"]))),
    ("model_edit_sweep", {"feature": "SweepCameo/Sweep1", "action": "profile",
                          "profile": {"sketch": "SweepProfWide", "profile_index": 0},
                          "component": "SweepCameo"},
     _sweep_edit_at_volume(math.pi * 0.8 ** 2 * 5), None),
    ("model_inspect", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_edit_body", "sweep body"),
                                 "include": ["mass"], "units": "cm"},
     _sweep_inspected_at_volume(math.pi * 0.8 ** 2 * 5), None),
    ("model_inspect", lambda c: {"target": _ctx_get(c, "sweep_dependent_handle", "dependent handle"),
                                 "include": ["default", "mass"], "units": "cm"},
     _sweep_dependent_survived(False), None),
    ("model_edit_sweep", {"feature": "SweepCameo/Sweep1", "action": "path",
                          "path": "sketch:SweepPathArc"},
     _sweep_edit_at_volume(math.pi * 0.8 ** 2 * 5 * math.pi / 2), None),
    ("model_inspect", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_edit_body", "sweep body"),
                                 "include": ["mass"], "units": "cm"},
     _sweep_inspected_at_volume(math.pi * 0.8 ** 2 * 5 * math.pi / 2), None),
    ("model_inspect", lambda c: {"target": _ctx_get(c, "sweep_dependent_handle", "dependent handle"),
                                 "include": ["default", "mass"], "units": "cm"},
     _sweep_dependent_survived(True), None),
    ("find_geometry", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_brep_strip", "strip"),
                                  "kind": "line_edge", "nearest_to": [250, 0, 5],
                                  "max_results": 1}, _matched(1, "line_edge"), _fg("sweep_brep_line")),
    ("find_geometry", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_brep_strip", "strip"),
                                  "kind": "arc_edge", "nearest_to": [251, 0, 13],
                                  "max_results": 1}, _matched(1, "arc_edge"), _fg("sweep_brep_arc")),
    ("model_edit_sweep", lambda c: {"feature": "SweepCameo/Sweep1", "action": "path",
                                       "path": [_ctx_get(c, "sweep_brep_line", "strip line"),
                                                _ctx_get(c, "sweep_brep_arc", "strip arc")]},
     _sweep_brep_list_edited, None),
    ("model_inspect", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_edit_body", "sweep body"),
                                 "include": ["mass"], "units": "cm"},
     _sweep_inspected_at_volume(math.pi * 0.8 ** 2 * (1 + math.pi / 4)), None),
    ("model_edit_sweep", {"feature": "SweepCameo/Sweep1", "action": "path",
                          "path": "sketch:SweepPath", "profile": {"sketch": "SweepProf", "profile_index": 0}},
     _refused("unused"), None),
    ("model_inspect", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_edit_body", "sweep body"),
                                 "include": ["mass"], "units": "cm"},
     _sweep_inspected_at_volume(math.pi * 0.8 ** 2 * (1 + math.pi / 4)), None),
    ("model_inspect", lambda c: {"target": "LoftCameo:" + _ctx_get(
        c, "sweep_edit_witness_body", "loft witness"), "include": ["mass"], "units": "cm"},
     lambda p: _measured("untouched loft witness", {"volume_cm3": (p.get("mass") or {}).get("volume")},
                         _num((p.get("mass") or {}).get("volume")) and _near(
                             p["mass"]["volume"], _RECALL["sweep_edit_witness_volume"], 0.001)),
     None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    # THE GUIDE SCOPE: a sketch name is only unique INSIDE a component, so two components each hold
    # one called 'Spine' and the loft below has to be told which one its rail lives in.
    ("model_create_component", {"name": "GuideRail", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "GuideBase"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 420, "cy": 0, "radius": 16}],
                             "sketch_name": "GuideBase"}, "ok", None),
    ("sketch_get", {"sketch_name": "GuideBase"}, "ok", _prof("guide_base")),
    ("model_construction", {"kind": "plane", "plane": "xy", "offset": 40, "name": "GuideTopPlane"},
     _datum_plane("xy"), None),
    ("sketch_create", {"plane": "GuideTopPlane", "name": "GuideTop"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 420, "cy": 0, "radius": 8}],
                             "sketch_name": "GuideTop"}, "ok", None),
    ("sketch_get", {"sketch_name": "GuideTop"}, "ok", _prof("guide_top")),
    # the rail climbs from the base circle's rim to the top circle's: z runs along the xy sketch's
    # own normal, which is where the offset plane above put the top section.
    ("sketch_create", {"plane": "xy", "name": "Spine"}, "ok", None),
    ("sketch_add_3d_line", {"sketch_name": "Spine", "component": "GuideRail",
                            "x1": 436, "y1": 0, "z1": 0, "x2": 428, "y2": 0, "z2": 40},
     "ok", None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "GuideDupe", "activate": True}, _made_component, None),
    # The DRAWN sketch carries a name of its own: the framing pass writes a camera row per sketch it
    # sees drawn, and view_set refuses a 'focus' that two sketches answer to.
    ("sketch_create", {"plane": "xy", "name": "DupeMark"}, "ok", None),
    ("sketch_add_3d_line", {"sketch_name": "DupeMark", "component": "GuideDupe",
                            "x1": 520, "y1": 0, "z1": 0, "x2": 520, "y2": 20, "z2": 10},
     "ok", None),
    # the SAME name in the second component, left EMPTY - nothing draws on it, so it is no framing
    # subject. Asserted: a name Fusion had deduped would leave every refusal below testing nothing.
    ("sketch_create", {"plane": "xy", "name": "Spine"},
     lambda p: _measured("the duplicate guide name survived the create",
                         {"sketch_name": p.get("sketch_name"),
                          "rename_warning": p.get("rename_warning")},
                         p.get("sketch_name") == "Spine" and "rename_warning" not in p), None),
    ("design_activate_component", {"occurrence": "GuideRail:1"}, "ok", None),
    # un-scoped, the rail's sketch name answers to two sketches and the loft refuses rather than
    # picking one - naming the scope that narrows the GUIDES, which is the one this call can pass.
    ("model_loft", lambda c: {"profiles": [_ctx_get(c, "guide_base", "the guide loft's base"),
                                           _ctx_get(c, "guide_top", "the guide loft's top")],
                              "rails": ["Spine/line:0"]},
     _refused("2 sketches are named 'Spine'", "'guide_component'"), None),
    # a scope that owns no sketch of that name refuses NAMING the scope - 'GuideBase' answers to
    # exactly one sketch design-wide, so dropping the scope would loft along another component's
    # curve and say nothing.
    ("model_loft", lambda c: {"profiles": [_ctx_get(c, "guide_base", "the guide loft's base"),
                                           _ctx_get(c, "guide_top", "the guide loft's top")],
                              "rails": ["GuideBase/circle:0"], "guide_component": "GuideDupe"},
     _refused("GuideDupe", "no sketch named 'GuideBase'", "GuideRail"), None),
    # scoped, the same call builds: the rail resolves inside GuideRail, whose 'Spine' is the line
    # that touches both sections (GuideDupe's runs off sideways and would fail the add).
    ("model_loft", lambda c: {"profiles": [_ctx_get(c, "guide_base", "the guide loft's base"),
                                           _ctx_get(c, "guide_top", "the guide loft's top")],
                              "rails": ["Spine/line:0"], "guide_component": "GuideRail"},
     lambda p: _measured("loft along the component-scoped guide",
                         {"feature": p.get("feature"), "result_bodies": p.get("result_bodies"),
                          "rails_count": p.get("rails_count")},
                         bool(p.get("feature")) and bool(p.get("result_bodies"))
                         and p.get("rails_count") == 1), None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    # the part is whole: frame IT for the colouring beats, not the metre-wide cameo grid.
    _watch("Bracket:1"),
    ("appearance_set", {"target": "Bracket", "color": "#5E6AD2"}, "ok", None),
    ("appearance_set", {"target": "LoftCameo", "color": "#8A94A6"}, "ok", None),
    ("appearance_set", {"target": "SweepCameo", "color": "#F5A623"}, "ok", None),
    ("model_set_material", {"target": "Bracket:1", "material": "Steel"}, _material_assigned, None),
    # a miss whose catalog carries the actual entry ('Steel AISI 4130 259 QT') alongside several
    # same-prefix decoys ('Steel AISI 1060/1061/...') - the CONTAINING name is what the Nearest
    # list has to lead with, not the decoys difflib's edit distance would rank ahead of it.
    ("model_set_material", {"target": "Bracket:1", "material": "Steel AISI 4130"},
     _refused("Nearest: 'Steel AISI 4130 259 QT'"), None),
    # honest reads on the real part: the boss wall to its own bore, the two of them coaxial, and
    # the part's measured extent.
    ("find_geometry", {"target": "Bracket", "kind": "cylinder_face", "radius": 10,
                       "max_results": 1}, _matched(1, "cylinder_face"), _fg("boss_wall")),
    # the bore INSIDE that boss, pinned by position: the part carries two of this diameter, and the
    # coaxial read below is only a claim about the boss if it picked the boss's own.
    ("find_geometry", {"target": "Bracket", "kind": "cylinder_face", "radius": 6,
                       "nearest_to": [45, 0, 42], "max_results": 1},
     _matched(1, "cylinder_face"), _fg("bore_wall")),
    ("model_measure_between", lambda c: {"a": _ctx_get(c, "boss_wall", "the boss wall"),
                                         "b": _ctx_get(c, "bore_wall", "the bore wall")},
     _gap_measured, None),
    ("model_measure_relation", lambda c: {"relation": "coaxial",
                                          "entity_a": _ctx_get(c, "boss_wall", "the boss wall"),
                                          "entity_b": _ctx_get(c, "bore_wall", "the bore wall")},
     _relation_measured("coaxial"), None),
    ("model_inspect", {"target": "Bracket:1"}, _extent_measured, None),
    # THE PART'S ENGINEERING IDENTITY: Fusion mints a part number of its own for every component, so
    # the read comes first and shows what is there; the set then replaces it with the shop's, and
    # the second read is the independent confirmation that the value is the component's own.
    ("design_get", {"include": ["metadata"]}, _component_metadata("Bracket"), None),
    ("design_set_metadata", {"target": "Bracket", "part_number": "FE-BRACKET-001",
                             "description": "Sweep bracket"},
     _metadata_set("Bracket", "FE-BRACKET-001", "Sweep bracket"), None),
    ("design_get", {"include": ["metadata"], "name_filter": "Bracket"},
     _component_metadata("Bracket", part_number="FE-BRACKET-001", description="Sweep bracket"),
     None),
    # PMI CONTENT writes need the Design or Manufacturing Extension (the platform raises
    # "Manufacturing or Design Extension is required" without one - measured on the lapsed install),
    # so the four write rows run entitled and assert the created/edited/deleted values read back off
    # the annotations, while the unentitled variants assert the refusal names the extension and the
    # next step. Reads and the blank-name guards run on either licence.
    ("find_geometry", {"target": "Bracket", "kind": "planar_face", "nearest_to": [-35, 0, 14],
                       "max_results": 1}, _face_up_at(-35, 0, 14, tol=2.0), _fg("pmi_floor")),
    ("pmi_create", lambda c: {"kind": "note", "geometry": [_ctx_get(c, "pmi_floor", "the pocket floor")], "text": "{flatness}0.05", "name": "PmiFlat"},
     _needs(MACHINING_EXTENSION, lambda p: p.get("annotation") == "PmiFlat" and p.get("markup") == "{flatness}0.05" and p.get("kind") == "note"), None),
    ("pmi_create", lambda c: {"kind": "note", "geometry": [_ctx_get(c, "pmi_floor", "the pocket floor")], "text": "{flatness}0.05", "name": "PmiFlat"},
     _unless(MACHINING_EXTENSION, _refused("Extension is required", "pmi_get")), None),
    ("find_geometry", {"target": "Bracket", "kind": "cylinder_face", "radius": 3, "max_results": 1},
     _matched(1, "cylinder_face"), _fg("mount_bore")),
    ("pmi_create", lambda c: {"kind": "hole_note", "geometry": [_ctx_get(c, "mount_bore", "a mounting bore")]},
     _needs(MACHINING_EXTENSION, lambda p: p.get("kind") == "hole_note" and bool(p.get("annotation")) and "<HDIA>" in str(p.get("markup"))), None),
    ("pmi_create", lambda c: {"kind": "hole_note", "geometry": [_ctx_get(c, "mount_bore", "a mounting bore")]},
     _unless(MACHINING_EXTENSION, _refused("Extension is required", "pmi_get")), None),
    ("pmi_get", {"include": ["segments", "detail"]}, "ok", None),
    # an over-cap 'max_results' is CLAMPED, not refused - pmi_get's own contract, since every record
    # it returns crosses the wire whole. The answer still comes back with its census keys.
    ("pmi_get", {"max_results": 99999},
     lambda p: isinstance(p.get("annotations"), list) and "total" in p, None),
    ("pmi_edit", {"action": "set_text", "annotation": "PmiFlat", "text": "{perpendicularity}0.03"},
     _needs(MACHINING_EXTENSION, lambda p: p.get("name") == "PmiFlat" and p.get("markup") == "{perpendicularity}0.03"), None),
    # the blank name is its own guard, ahead of any lookup - on either licence.
    ("pmi_edit", {"action": "hide", "annotation": ""}, "refused", None),
    ("pmi_delete", {"annotation": ""}, "refused", None),
    ("pmi_delete", {"annotation": "PmiFlat"},
     _needs(MACHINING_EXTENSION, lambda p: p.get("deleted") == "PmiFlat" and isinstance(p.get("remaining_pmi"), int)), None),
    # THE DATUM BENCH: one bored block, and every way the API knows of hanging a plane, an axis or a
    # point off it. The modes divide by what they READ, so the bench has to carry all of it - six
    # faces, the linear edges where they meet, the vertices where those meet, and a bore for the
    # curved-face and circular-edge modes. Each row's receipt is the created datum's OWN geometry:
    # every mode returns an object, and only the read-back distinguishes one that landed where the
    # mode says from one that landed anywhere at all.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "DatumBench", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "DBPad"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 200, "y1": 0,
                                           "x2": 260, "y2": 40}],
                             "sketch_name": "DBPad"}, "ok", None),
    ("model_extrude", {"sketch_name": "DBPad", "profile_index": 0, "distance": 20}, _extruded, None),
    ("find_geometry", {"target": "DatumBench", "kind": "planar_face", "nearest_to": [230, 20, 20],
                       "max_results": 1}, "ok", _fg("db_top")),
    ("model_hole", lambda c: {"face": _ctx_get(c, "db_top", "bench top face"), "hole_type": "simple",
                              "diameter": "10 mm", "extent": "through", "points": [[230, 20, 0]]},
     _drilled(1), None),
    # the reference set every mode below draws from, acquired once the bore exists so no handle is
    # stale: the top face, the bore, its rim, two coplanar top edges, one vertical edge that MEETS
    # one of them, and three top-face corners that form a triangle.
    ("find_geometry", {"target": "DatumBench", "kind": "planar_face", "nearest_to": [230, 20, 20],
                       "max_results": 1}, "ok", _fg("db_top2")),
    ("find_geometry", {"target": "DatumBench", "kind": "cylinder_face", "nearest_to": [230, 20, 10],
                       "max_results": 1}, "ok", _fg("db_bore")),
    ("find_geometry", {"target": "DatumBench", "kind": "circular_edge", "nearest_to": [230, 20, 20],
                       "max_results": 1}, "ok", _fg("db_rim")),
    ("find_geometry", {"target": "DatumBench", "kind": "line_edge", "nearest_to": [230, 0, 20],
                       "max_results": 1}, "ok", _fg("db_front")),
    ("find_geometry", {"target": "DatumBench", "kind": "line_edge", "nearest_to": [230, 40, 20],
                       "max_results": 1}, "ok", _fg("db_back")),
    ("find_geometry", {"target": "DatumBench", "kind": "line_edge", "nearest_to": [200, 0, 10],
                       "max_results": 1}, "ok", _fg("db_post")),
    ("find_geometry", {"target": "DatumBench", "kind": "vertex", "nearest_to": [200, 0, 20],
                       "max_results": 1}, "ok", _fg("db_c1")),
    ("find_geometry", {"target": "DatumBench", "kind": "vertex", "nearest_to": [260, 0, 20],
                       "max_results": 1}, "ok", _fg("db_c2")),
    ("find_geometry", {"target": "DatumBench", "kind": "vertex", "nearest_to": [200, 40, 20],
                       "max_results": 1}, "ok", _fg("db_c3")),
    # the bore's seam vertex - a point that sits ON the cylindrical face, which is what a tangent
    # plane needs. A box corner is not on the bore, and the tangency has nowhere to land.
    ("find_geometry", {"target": "DatumBench", "kind": "vertex", "nearest_to": [230, 20, 20],
                       "max_results": 1}, "ok", _fg("db_seam")),
    # PLANES. at_angle swings the XY plane about a top edge; three_points spans the three corners;
    # midplane splits XY and the top face, landing halfway up the block; two_edges spans the two
    # coplanar top edges; tangent_at_point rests on the bore wall.
    ("model_construction", lambda c: {"kind": "plane", "mode": "at_angle", "plane": "xy",
                                      "edges": [_ctx_get(c, "db_front", "bench front top edge")],
                                      "angle": 30, "name": "DBAngle"},
     lambda p: _datum("plane")(p) and _measured("swung off the base plane's normal",
                                                {"normal_changed": p.get("normal_changed")},
                                                p.get("normal_changed") is True), None),
    # a long-decimal angle: the plane's own parameter must hold every digit, read back separately.
    ("model_construction", lambda c: {"kind": "plane", "mode": "at_angle", "plane": "xy",
                                      "edges": [_ctx_get(c, "db_front", "bench front top edge")],
                                      "angle": _FINE_ANGLE_DEG, "name": "DBAngleFine"},
     _fine_angle_plane,
     ("db_fine_param", _recall("db_fine_param", lambda p: p["model_parameters"]["angle"]))),
    ("param_get", lambda c: {"name": _ctx_get(c, "db_fine_param", "the fine plane's parameter")},
     _fine_angle_param, None),
    ("model_construction", lambda c: {"kind": "plane", "mode": "three_points",
                                      "points": [_ctx_get(c, "db_c1", "bench corner 1"),
                                                 _ctx_get(c, "db_c2", "bench corner 2"),
                                                 _ctx_get(c, "db_c3", "bench corner 3")],
                                      "name": "DBTri"}, _datum("plane"), None),
    ("model_construction", lambda c: {"kind": "plane", "mode": "midplane", "plane": "xy",
                                      "plane2": _ctx_get(c, "db_top2", "bench top face"),
                                      "name": "DBMid"}, _datum("plane"), None),
    ("model_construction", lambda c: {"kind": "plane", "mode": "two_edges",
                                      "edges": [_ctx_get(c, "db_front", "bench front top edge"),
                                                _ctx_get(c, "db_back", "bench back top edge")],
                                      "name": "DBSpan"}, _datum("plane"), None),
    ("model_construction", lambda c: {"kind": "plane", "mode": "tangent_at_point",
                                      "face": _ctx_get(c, "db_bore", "bench bore"),
                                      "points": [_ctx_get(c, "db_seam", "bench bore seam vertex")],
                                      "name": "DBTangent"}, _datum("plane"), None),
    # AXES. An edge IS an axis; two corners span one; the bore's own centreline; and the normal of
    # the top face taken at a corner sitting on it.
    ("model_construction", lambda c: {"kind": "axis", "mode": "edge",
                                      "axis": _ctx_get(c, "db_front", "bench front top edge"),
                                      "name": "DBEdgeAxis"}, _datum("axis"), None),
    ("model_construction", lambda c: {"kind": "axis", "mode": "two_points",
                                      "points": [_ctx_get(c, "db_c1", "bench corner 1"),
                                                 _ctx_get(c, "db_c3", "bench corner 3")],
                                      "name": "DBSpanAxis"}, _datum("axis"), None),
    ("model_construction", lambda c: {"kind": "axis", "mode": "perpendicular_at_point",
                                      "face": _ctx_get(c, "db_top2", "bench top face"),
                                      "points": [_ctx_get(c, "db_c2", "bench corner 2")],
                                      "name": "DBNormalAxis"},
     lambda p: _datum("axis")(p) and _measured("axis along the face normal",
                                               {"aligned": p.get("aligned_to_face_normal")},
                                               p.get("aligned_to_face_normal") is True), None),
    # a world axis through a coordinate is setByLine, which is DIRECT-edit-only - this design is
    # parametric, so the mode is refused up front with the parametric routes named.
    ("model_construction", {"kind": "axis", "mode": "world", "axis": "x", "x": 200, "y": 0, "z": 0,
                            "name": "DBWorldAxis"}, "refused", None),
    # POINTS. The bore rim's centre; the corner where a top edge meets the post below it; the origin
    # the three world planes share; and where the post pierces XY.
    ("model_construction", lambda c: {"kind": "point", "mode": "circle_center",
                                      "edges": [_ctx_get(c, "db_rim", "bench bore rim")],
                                      "name": "DBBoreCentre"}, _datum("point"), None),
    ("model_construction", lambda c: {"kind": "point", "mode": "two_edges",
                                      "edges": [_ctx_get(c, "db_front", "bench front top edge"),
                                                _ctx_get(c, "db_post", "bench corner post")],
                                      "name": "DBCorner"}, _datum("point"), None),
    ("model_construction", {"kind": "point", "mode": "three_planes", "plane": "xy", "plane2": "xz",
                            "plane3": "yz", "name": "DBOrigin"}, _datum("point"), None),
    ("model_construction", lambda c: {"kind": "point", "mode": "edge_plane",
                                      "edges": [_ctx_get(c, "db_post", "bench corner post")],
                                      "plane": "xy", "name": "DBFoot"}, _datum("point"), None),
    # the coordinate point is setByPoint - direct-edit-only for the same reason as the world axis.
    ("model_construction", {"kind": "point", "mode": "coordinate", "x": 230, "y": 20, "z": 40,
                            "name": "DBCoord"}, "refused", None),
    # THE RELATION VOCABULARY, on the same block. Each relation reports a DIFFERENT measurement -
    # an angle for the alignments, a distance for the fits - and the pairs here are chosen so the
    # geometry, not the tool, settles the verdict: a face is flush with itself, a bore concentric
    # with itself, the top face perpendicular to a wall it meets and touching it along that edge,
    # and 20 mm clear of the floor below it.
    ("find_geometry", {"target": "DatumBench", "kind": "planar_face", "nearest_to": [200, 20, 10],
                       "max_results": 1}, "ok", _fg("db_wall")),
    ("find_geometry", {"target": "DatumBench", "kind": "planar_face", "nearest_to": [230, 20, 0],
                       "max_results": 1}, "ok", _fg("db_floor")),
    ("model_measure_relation", lambda c: {"relation": "perpendicular",
                                          "entity_a": _ctx_get(c, "db_top2", "bench top face"),
                                          "entity_b": _ctx_get(c, "db_wall", "bench wall")},
     _relation_passes("perpendicular"), None),
    ("model_measure_relation", lambda c: {"relation": "flush",
                                          "entity_a": _ctx_get(c, "db_top2", "bench top face"),
                                          "entity_b": _ctx_get(c, "db_top2", "bench top face")},
     _relation_read("flush", "normal_angle_deg"), None),
    ("model_measure_relation", lambda c: {"relation": "concentric",
                                          "entity_a": _ctx_get(c, "db_bore", "bench bore"),
                                          "entity_b": _ctx_get(c, "db_bore", "bench bore")},
     _relation_read("concentric", "center_distance"), None),
    ("model_measure_relation", lambda c: {"relation": "touching",
                                          "entity_a": _ctx_get(c, "db_top2", "bench top face"),
                                          "entity_b": _ctx_get(c, "db_wall", "bench wall")},
     _relation_read("touching", "min_distance"), None),
    ("model_measure_relation", lambda c: {"relation": "clearance",
                                          "entity_a": _ctx_get(c, "db_top2", "bench top face"),
                                          "entity_b": _ctx_get(c, "db_floor", "bench floor")},
     _relation_read("clearance", "min_distance"), None),
    # HOLE-HOST-1: two drillable B solids share z=0, while a separate A plate stays active. The
    # layout pass gives B and A different cells; the hole callables compensate for A's wrapper
    # offset so the world points land in B exactly once while every acquired handle stays unchanged.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": _HOLE_HOST, "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "Plate-upper"}, "ok", None),
    ("sketch_add_geometry",
     {"geometry": [{"kind": "rectangle", "x1": _HOLE_X0, "y1": 0,
                    "x2": _HOLE_X0 + 20, "y2": 20}], "sketch_name": "Plate-upper"}, "ok", None),
    ("model_extrude", {"sketch_name": "Plate-upper", "profile_index": 0, "distance": 10},
     _extruded, None),
    ("sketch_create", {"plane": "xy", "name": "Plate-lower"}, "ok", None),
    ("sketch_add_geometry",
     {"geometry": [{"kind": "rectangle", "x1": _HOLE_X0, "y1": 0,
                    "x2": _HOLE_X0 + 20, "y2": 20}], "sketch_name": "Plate-lower"}, "ok", None),
    ("model_extrude", {"sketch_name": "Plate-lower", "profile_index": 0, "distance": -10},
     _extruded, None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": _HOLE_ACTIVE, "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "Active-A-Plate"}, "ok", None),
    ("sketch_add_geometry",
     {"geometry": [{"kind": "rectangle", "x1": _HOLE_ACTIVE_X0, "y1": 0,
                    "x2": _HOLE_ACTIVE_X0 + 20, "y2": 20}],
      "sketch_name": "Active-A-Plate"}, "ok", None),
    ("model_extrude", {"sketch_name": "Active-A-Plate", "profile_index": 0, "distance": 10},
     _extruded, None),
    ("design_activate_component", {"occurrence": _HOLE_ACTIVE + ":1"},
     lambda p: (p.get("activated") == _HOLE_ACTIVE + ":1"
                and p.get("active_occurrence") == _HOLE_ACTIVE + ":1"
                and p.get("active_component") == _HOLE_ACTIVE), None),
    # The participant is a fresh body handle from a component-rooted tree read. Component scopes
    # only the tree; the separate timeline reads below use their own explicit full-list bound.
    ("design_get", {"include": ["tree"], "component": _HOLE_HOST,
                    "tree_bodies": True, "max_results": 10},
     _hole_host_tree, ("hh_upper", _hole_upper_handle)),
    ("design_get", {"include": ["tree"], "component": _HOLE_HOST,
                    "tree_bodies": True, "max_results": 10},
     _hole_host_tree, ("hh_lower", _hole_lower_handle)),
    ("design_get", {"include": ["tree"], "component": _HOLE_ACTIVE,
                    "tree_bodies": True, "max_results": 10},
     _hole_active_tree, ("hh_active", _hole_active_handle)),
    ("model_inspect", lambda c: _hole_inspect_args(c, "hh_upper"),
     _hole_body_state(_HOLE_HOST, (_HOLE_X0, 0, 0), (_HOLE_X0 + 20, 20, 10), 4000.0),
     None),
    ("model_inspect", lambda c: _hole_inspect_args(c, "hh_lower"),
     _hole_body_state(_HOLE_HOST, (_HOLE_X0, 0, -10), (_HOLE_X0 + 20, 20, 0), 4000.0),
     None),
    ("model_inspect", lambda c: _hole_inspect_args(c, "hh_active"),
     _hole_body_state(_HOLE_ACTIVE, (_HOLE_ACTIVE_X0, 0, 0),
                      (_HOLE_ACTIVE_X0 + 20, 20, 10), 4000.0), None),
    ("find_geometry", lambda c: _hole_cylinder_args(c, "hh_upper"),
     _hole_cylinders(_HOLE_HOST, ()), None),
    ("find_geometry", lambda c: _hole_cylinder_args(c, "hh_lower"),
     _hole_cylinders(_HOLE_HOST, ()), None),
    ("find_geometry", lambda c: _hole_cylinder_args(c, "hh_active"),
     _hole_cylinders(_HOLE_ACTIVE, ()), None),
    ("find_geometry", _scoped_top_args,
     lambda p: _face_up_at(_px(_HOLE_HOST, _HOLE_X0 + 10),
                           _py(_HOLE_HOST, 10), 10)(p), _fg("hh_top")),
    ("model_hole", _scoped_hole_args, _hole_created(True), None),
    # The scoped cut removes exactly one 4 mm x 10 mm bore from upper B. Lower B and active A keep
    # their original bounds, volume and empty cylinder censuses.
    ("model_inspect", lambda c: _hole_inspect_args(c, "hh_upper"),
     _hole_body_state(_HOLE_HOST, (_HOLE_X0, 0, 0), (_HOLE_X0 + 20, 20, 10),
                      4000.0 - _HOLE_VOLUME), None),
    ("model_inspect", lambda c: _hole_inspect_args(c, "hh_lower"),
     _hole_body_state(_HOLE_HOST, (_HOLE_X0, 0, -10), (_HOLE_X0 + 20, 20, 0), 4000.0),
     None),
    ("model_inspect", lambda c: _hole_inspect_args(c, "hh_active"),
     _hole_body_state(_HOLE_ACTIVE, (_HOLE_ACTIVE_X0, 0, 0),
                      (_HOLE_ACTIVE_X0 + 20, 20, 10), 4000.0), None),
    ("find_geometry", lambda c: _hole_cylinder_args(c, "hh_upper"),
     _hole_cylinders(_HOLE_HOST, ((_HOLE_X0 + 10, 10, 5),)), None),
    ("find_geometry", lambda c: _hole_cylinder_args(c, "hh_lower"),
     _hole_cylinders(_HOLE_HOST, ()), None),
    ("find_geometry", lambda c: _hole_cylinder_args(c, "hh_active"),
     _hole_cylinders(_HOLE_ACTIVE, ()), None),
    # Reacquire the new bore after the write and consume its real handle. Its 4 x 4 x 10 mm bounds
    # prove radius, depth and world location independently of model_hole's participant echo.
    ("find_geometry", _scoped_bore_args,
     _hole_cylinders(_HOLE_HOST, ((_HOLE_X0 + 10, 10, 5),)), _fg("hh_bore")),
    ("model_inspect", lambda c: {"target": _ctx_get(c, "hh_bore", "fresh scoped bore face"),
                                 "units": "mm"}, _hole_face_bounds, None),
    ("design_get", {"include": ["timeline"], "max_results": 2000},
     _hole_timeline(False), None),
    # Positive control: A is explicitly active again and target_bodies is omitted. Both stacked B
    # bodies lose one bore, proving the lower body was drillable; A still does not change.
    ("design_activate_component", {"occurrence": _HOLE_ACTIVE + ":1"},
     lambda p: (p.get("activated") == _HOLE_ACTIVE + ":1"
                and p.get("active_occurrence") == _HOLE_ACTIVE + ":1"
                and p.get("active_component") == _HOLE_ACTIVE), None),
    ("find_geometry", _control_top_args,
     lambda p: _face_up_at(_px(_HOLE_HOST, _HOLE_X0 + 10),
                           _py(_HOLE_HOST, 10), 10, tol=2.0)(p), _fg("hh_top_control")),
    ("model_hole", _unscoped_hole_args, _hole_created(False), None),
    ("model_inspect", lambda c: _hole_inspect_args(c, "hh_upper"),
     _hole_body_state(_HOLE_HOST, (_HOLE_X0, 0, 0), (_HOLE_X0 + 20, 20, 10),
                      4000.0 - 2 * _HOLE_VOLUME), None),
    ("model_inspect", lambda c: _hole_inspect_args(c, "hh_lower"),
     _hole_body_state(_HOLE_HOST, (_HOLE_X0, 0, -10), (_HOLE_X0 + 20, 20, 0),
                      4000.0 - _HOLE_VOLUME), None),
    ("model_inspect", lambda c: _hole_inspect_args(c, "hh_active"),
     _hole_body_state(_HOLE_ACTIVE, (_HOLE_ACTIVE_X0, 0, 0),
                      (_HOLE_ACTIVE_X0 + 20, 20, 10), 4000.0), None),
    ("find_geometry", lambda c: _hole_cylinder_args(c, "hh_upper"),
     _hole_cylinders(_HOLE_HOST, ((_HOLE_X0 + 5, 5, 5),
                                  (_HOLE_X0 + 10, 10, 5))), None),
    ("find_geometry", lambda c: _hole_cylinder_args(c, "hh_lower"),
     _hole_cylinders(_HOLE_HOST, ((_HOLE_X0 + 5, 5, -5),)), None),
    ("find_geometry", lambda c: _hole_cylinder_args(c, "hh_active"),
     _hole_cylinders(_HOLE_ACTIVE, ()), None),
    ("design_get", {"include": ["timeline"], "max_results": 2000},
     _hole_timeline(True), None),
    # feature cameos on same-doc scratch bodies (no natural home on the part for these verbs).
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "FeatureCameo", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "FCPad"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 200, "y1": 0,
                                           "x2": 240, "y2": 40}],
                             "sketch_name": "FCPad"}, "ok", None),
    ("model_extrude", {"sketch_name": "FCPad", "profile_index": 0, "distance": 20}, _extruded, None),
    _watch("FeatureCameo:1"),
    ("find_geometry", {"target": "FeatureCameo", "kind": "planar_face", "nearest_to": [200, 20, 10], "max_results": 1}, "ok", _fg("fc_side")),
    ("model_draft", lambda c: {"faces": [_ctx_get(c, "fc_side", "cameo side face")], "pull_direction": "xy", "angle_deg": 3},
     _drafted, None),
    # The three PIVOT gates: a write whose pull plane / replacement surface / edge set meets the
    # geometry at its MIDDLE adds exactly what it cuts, so the volume holds to the last bit. Each
    # of these was a false refusal until the boundary read joined the material one.
    ("model_create_component", {"name": "PivotCameo", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "PvL"}, "ok", None),
    ("sketch_add_geometry", {"sketch_name": "PvL", "geometry": [
        {"kind": "closed_path", "points": [[300, 0], [340, 0], [340, 20], [320, 20], [320, 40],
                                           [300, 40]]}]}, "ok", None),
    ("model_extrude", {"sketch_name": "PvL", "profile_index": 0, "distance": 30}, _extruded, None),
    ("model_construction", {"kind": "plane", "plane": "xy", "offset": 15, "name": "PvMid"},
     _datum_plane("xy"), None),
    # Each gate gets its OWN face, so none disturbs another and nothing has to be deleted: a fillet
    # standing on a drafted face eats a strip off it, which both spoils the pivot (measured: the
    # volume moves -0.000615 cm3) and consumes the input wrapper (faces_compared 0).
    # ONE-SIDED about a plane CROSSING the face: it pivots there, tilting the face while the volume
    # holds to the last bit - the case the material gate alone refused.
    ("find_geometry", {"target": "PivotCameo", "kind": "planar_face", "nearest_to": [300, 20, 15],
                       "max_results": 1}, "ok", _fg("pv_face")),
    ("model_draft", lambda c: {"faces": [_ctx_get(c, "pv_face", "the face the plane crosses")],
                               "pull_direction": "PvMid", "angle_deg": 5, "tangent_chain": False},
     _drafted_on_its_pivot, None),
    # SYMMETRIC, on the next face round: it SPLITS that face at the plane (faces_drafted 2 from one
    # requested) and, measured here, tapers both halves the same way - so the volume MOVES. This
    # branch carries its own verdict, not an exemption.
    ("find_geometry", {"target": "PivotCameo", "kind": "planar_face", "nearest_to": [320, 0, 15],
                       "max_results": 1}, "ok", _fg("pv_sym_face")),
    ("model_draft", lambda c: {"faces": [_ctx_get(c, "pv_sym_face", "the y=0 face")],
                               "pull_direction": "PvMid", "angle_deg": 5, "symmetric": True,
                               "tangent_chain": False}, _drafted_symmetric, None),
    # one CONVEX and one CONCAVE vertical edge, same length and radius, both on faces no draft
    # touched: the wedge cut off the first is the wedge filled into the second, so only the surface
    # area moves.
    ("find_geometry", {"target": "PivotCameo", "kind": "line_edge", "nearest_to": [340, 20, 15],
                       "max_results": 1}, "ok", _fg("pv_convex")),
    ("find_geometry", {"target": "PivotCameo", "kind": "line_edge", "nearest_to": [320, 20, 15],
                       "max_results": 1}, "ok", _fg("pv_concave")),
    ("model_fillet", lambda c: {"edges": [_ctx_get(c, "pv_convex", "the outer corner"),
                                          _ctx_get(c, "pv_concave", "the inner corner")],
                                "radius": 5, "tangent_chain": False}, _cut_on_its_pivot, None),
    # A sketch on a FACE has no construction plane to name. Both the write that makes it and the
    # read that returns to it name the BODY and carry that face's own handle instead of plane null;
    # the read gets there by rolling the marker to the sketch and putting it back, because
    # referencePlane answers a BRepFace only from there.
    ("find_geometry", {"target": "PivotCameo", "kind": "planar_face", "nearest_to": [310, 30, 30],
                       "max_results": 1}, "ok", _fg("pv_lid")),
    ("sketch_create", lambda c: {"on_face": _ctx_get(c, "pv_lid", "the L-prism lid"),
                                 "name": "PvOnFace"}, _sits_on_a_face, None),
    ("sketch_get", {"sketch_name": "PvOnFace"},
     lambda p: _sits_on_a_face(p) and "timeline_marker_unrestored" not in p,
     ("pv_face_handle", lambda p: p["on_face"]["handle"])),
    # the handle that read CONSUMED: fed straight back as a face handle, it pushes that same face.
    ("model_offset_face", lambda c: {"faces": [_ctx_get(c, "pv_face_handle", "the sketch's face")],
                                     "distance": 2}, _offset_faces, None),
    # the third pivot gate, in this same component so the block and the sheet share one cell: a
    # replacement surface TILTED about the middle of the face it replaces adds exactly what it cuts,
    # so volume AND face count both hold and only the area moves.
    ("sketch_create", {"plane": "xy", "name": "PvBlkS"}, "ok", None),
    ("sketch_add_geometry", {"sketch_name": "PvBlkS", "geometry": [
        {"kind": "rectangle", "x1": 360, "y1": 0, "x2": 390, "y2": 30}]}, "ok", None),
    ("model_extrude", {"sketch_name": "PvBlkS", "profile_index": 0, "distance": 20},
     _extruded, None),
    ("sketch_create", {"plane": "xz", "name": "PvRoofS"}, "ok", None),
    # sketch +Y maps to world -Z here, so these two points put the sheet at world z 16 -> 24,
    # crossing the block's z=20 top at x=375 - the middle of that face.
    ("sketch_add_geometry", {"sketch_name": "PvRoofS", "geometry": [
        {"kind": "line", "x1": 355, "y1": -16, "x2": 395, "y2": -24}]}, "ok", None),
    ("surface_extrude", {"sketch_name": "PvRoofS", "distance": 80, "symmetric": True},
     lambda p: p.get("is_solid") is False, ("pv_sheet_body", lambda p: p["result_bodies"][0])),
    ("find_geometry", {"target": "PivotCameo", "kind": "planar_face", "nearest_to": [375, 15, 20],
                       "max_results": 1}, "ok", _fg("pv_top")),
    ("model_replace_face", lambda c: {"faces": [_ctx_get(c, "pv_top", "the block top")],
                                      "target": "PivotCameo:" + _ctx_get(c, "pv_sheet_body", "the tilted sheet")},
     _replaced_on_its_pivot, None),
    ("design_activate_component", {"occurrence": "FeatureCameo:1"}, "ok", None),
    ("find_geometry", {"target": "FeatureCameo", "kind": "planar_face", "nearest_to": [220, 20, 20], "max_results": 1}, "ok", _fg("fc_top")),
    # hole points are in the FACE'S LOCAL frame, whose origin for this face is the MODEL origin
    # projected onto its plane - so on-pad coordinates are the world x,y. ([5,5] here drilled at
    # world (5,5), a point off this pad entirely: the hole silently cut whatever body sat near
    # the origin, and the axis-count read-back cannot see a wrong-body cut. Measured live.)
    ("model_hole", lambda c: {"face": _ctx_get(c, "fc_top", "cameo top face"), "hole_type": "simple", "diameter": "4 mm", "extent": "blind", "depth": "8 mm", "points": [[220, 20, 0]]}, _drilled(1), None),
    # the three additive placement modes. Each act re-acquires its own edge: the center act below
    # consumes the 4 mm rim by drilling an 8 mm bore concentric with it, so a handle captured once
    # and reused would be pointing at geometry that no longer exists.
    ("find_geometry", {"target": "FeatureCameo", "kind": "circular_edge", "radius": 2,
                       "nearest_to": [220, 20, 20], "max_results": 1}, "ok", _fg("fc_hole_edge")),
    ("model_hole", lambda c: {"face": _ctx_get(c, "fc_top", "cameo top face"),
                              "placement": "center", "edge": _ctx_get(c, "fc_hole_edge", "hole rim"),
                              "diameter": "8 mm", "extent": "blind", "depth": "3 mm"},
     lambda p: p.get("placement") == "center" and p.get("holes_verified") is True, None),
    ("find_geometry", {"target": "FeatureCameo", "kind": "line_edge", "nearest_to": [220, 0, 20],
                       "max_results": 1}, "ok", _fg("fc_edge")),
    ("model_hole", lambda c: {"face": _ctx_get(c, "fc_top", "cameo top face"),
                              "placement": "on_edge", "edge": _ctx_get(c, "fc_edge", "pad edge"),
                              "edge_position": "middle", "diameter": "3 mm",
                              "extent": "blind", "depth": "3 mm"},
     lambda p: p.get("placement") == "on_edge", None),
    # on_edge at the edge's START vertex - RE-ACQUIRED first: the middle-hole above SPLITS the
    # pad edge (measured: a handle captured before that hole resolves to 2 sub-edges and is
    # refused as stale), so every act re-acquires its own edge.
    ("find_geometry", {"target": "FeatureCameo", "kind": "line_edge", "nearest_to": [220, 0, 20],
                       "max_results": 1}, "ok", _fg("fc_edge2")),
    ("model_hole", lambda c: {"face": _ctx_get(c, "fc_top", "cameo top face"),
                              "placement": "on_edge", "edge": _ctx_get(c, "fc_edge2", "pad edge"),
                              "edge_position": "start", "diameter": "3 mm",
                              "extent": "blind", "depth": "3 mm"}, _drilled(1), None),
    # plane_offsets measures from STRAIGHT edges - a circular one is refused by name
    ("find_geometry", {"target": "FeatureCameo", "kind": "circular_edge",
                       "nearest_to": [220, 20, 20], "max_results": 1}, "ok", _fg("fc_rim2")),
    ("model_hole", lambda c: {"face": _ctx_get(c, "fc_top", "cameo top face"),
                              "placement": "plane_offsets", "point": [215, 15, 20],
                              "offset_edge_one": _ctx_get(c, "fc_rim2", "a round rim"),
                              "offset_one": "5 mm", "diameter": "3 mm", "extent": "blind",
                              "depth": "3 mm"}, "refused", None),
    # re-acquired again: the start-vertex hole above can notch this edge the same way. The query
    # aims at the LONG remaining stretch of the pad's bottom boundary (x~232) - the notch cuts
    # mint short edges near the hole sites that are NOT parallel to the hole plane, and Fusion
    # refuses a non-parallel reference edge (measured).
    ("find_geometry", {"target": "FeatureCameo", "kind": "line_edge", "nearest_to": [232, 0, 20],
                       "max_results": 1}, "ok", _fg("fc_edge3")),
    ("model_hole", lambda c: {"face": _ctx_get(c, "fc_top", "cameo top face"),
                              "placement": "plane_offsets", "point": [215, 15, 20],
                              "offset_edge_one": _ctx_get(c, "fc_edge3", "pad edge"),
                              "offset_one": "6 mm", "diameter": "3 mm", "extent": "blind",
                              "depth": "3 mm"},
     lambda p: p.get("placement") == "plane_offsets", None),
    ("find_geometry", {"target": "FeatureCameo", "kind": "planar_face", "nearest_to": [220, 20, 20], "max_results": 1}, "ok", _fg("fc_body")),
    ("model_mirror", lambda c: {"bodies": [_ctx_get(c, "fc_body", "cameo body")], "plane": "yz"}, _mirrored, None),
    # a real GRID, not a row: two directions at once, spaced wider than the 40 mm pad so the
    # instances stand clear of each other. 3 x 2 is also the read-back that catches a tool
    # multiplying the directions wrongly - a row of 3 and a row of 6 both pass a bare "more than 1".
    ("model_pattern_rectangular", lambda c: {"bodies": [_ctx_get(c, "fc_body", "cameo body")],
                                             "quantity_one": 3, "spacing_one": 75, "direction_one": "x",
                                             "quantity_two": 2, "spacing_two": 70, "direction_two": "y"},
     _patterned("total_instances", 6), None),
    # An axis OUTSIDE the part, so the pattern reads as an orbit rather than a body spun in place:
    # two origin planes offset to cross 30 mm clear of the pad's -X edge, and their INTERSECTION is
    # the axis. The world z axis would do the same job 200 mm away, swinging the copies across the
    # whole scene and through the machined part.
    ("model_construction", {"kind": "plane", "plane": "yz", "offset": 170, "name": "OrbitYZ"},
     _datum_plane("yz"), None),
    ("model_construction", {"kind": "plane", "plane": "xz", "offset": 20, "name": "OrbitXZ"},
     _datum_plane("xz"), None),
    ("model_construction", {"kind": "axis", "mode": "two_planes", "plane": "OrbitYZ",
                            "plane2": "OrbitXZ", "name": "CameoOrbit"},
     lambda p: bool(p.get("handle")), None),
    ("model_pattern_circular", lambda c: {"bodies": [_ctx_get(c, "fc_body", "cameo body")],
                                          "quantity": 4, "total_angle_deg": 360,
                                          "axis": "CameoOrbit"},
     lambda p: p.get("quantity") == 4 and p.get("axis") == "CameoOrbit", None),
    # pattern the cameo along one of its own line edges - the count is a read-back, never an echo.
    ("find_geometry", {"target": "FeatureCameo", "kind": "line_edge", "max_results": 1}, "ok", _fg("dc_edge")),
    ("model_pattern_path", lambda c: {"bodies": [_ctx_get(c, "fc_body", "cameo body")], "path": [_ctx_get(c, "dc_edge", "path edge")], "quantity": 3, "distance": 55, "distance_type": "spacing"},
     lambda p: p.get("patterned") is True and p.get("quantity") == 3, None),
    # the pattern axis as a DATUM: the cameo's own bore defines a construction axis, whose published
    # handle is what the pattern turns about. The axis label is read back off the resolved entity, so
    # the datum's name proves the handle reached the datum and not a world axis fallback.
    ("find_geometry", {"target": "FeatureCameo", "kind": "cylinder_face", "max_results": 1}, "ok",
     _fg("fc_cyl")),
    ("model_construction", lambda c: {"kind": "axis", "mode": "circular_face",
                                      "face": _ctx_get(c, "fc_cyl", "a cameo bore face"),
                                      "name": "CameoSpin"},
     lambda p: bool(p.get("handle")), ("cam_axis", lambda p: p["handle"])),
    ("model_pattern_circular", lambda c: {"bodies": [_ctx_get(c, "fc_body", "cameo body")],
                                          "quantity": 4, "total_angle_deg": 360,
                                          "axis": _ctx_get(c, "cam_axis", "the datum axis handle")},
     lambda p: p.get("quantity") == 4 and p.get("axis") == "CameoSpin", None),
    # the same axis reached BY NAME while its component is active - the handle-free route.
    ("model_pattern_circular", lambda c: {"bodies": [_ctx_get(c, "fc_body", "cameo body")],
                                          "quantity": 3, "total_angle_deg": 180,
                                          "axis": "CameoSpin"},
     lambda p: p.get("quantity") == 3 and p.get("axis") == "CameoSpin", None),
    # the CYLINDRICAL FACE itself as the axis: off-origin, the case a direction vector cannot
    # express, and the label reads the resolved entity's type because a face carries no name.
    ("model_pattern_circular", lambda c: {"bodies": [_ctx_get(c, "fc_body", "cameo body")],
                                          "quantity": 3,
                                          "axis": _ctx_get(c, "fc_cyl", "a cameo bore face")},
     lambda p: p.get("quantity") == 3 and p.get("axis") == "BRepFace", None),
    # a circular_face axis inside a ROTATED occurrence: ConstructionAxis.geometry stays COMPONENT-
    # LOCAL even through a face proxy, so the local axis must be LIFTED through the occurrence's own
    # transform2 to read as world. A YZ-plane rod's local axis is world X before the rotation; a
    # -90 deg Z turn carries it to world (0,-1,0).
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    # placed at x=1300 mm: clear of the story's stock and bracket in the interference census
    ("model_create_component", {"name": "AxisFrameRig", "activate": True, "x": 1300},
     _made_component, None),
    ("sketch_create", {"plane": "yz", "name": "AxisFrameRigS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 0, "cy": 0, "radius": 5}],
                             "sketch_name": "AxisFrameRigS"}, "ok", None),
    ("model_extrude", {"sketch_name": "AxisFrameRigS", "profile_index": 0, "distance": 20},
     _extruded, None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("assembly_move", {"occurrence": "AxisFrameRig:1", "rotate_deg": -90, "rotate_axis": "z"},
     _moved_occurrence(), None),
    # captured, or the add below recomputes the design and the uncaptured pose of this grounded
    # occurrence reverts to identity (measured burn82) - the row would then pass on no rotation.
    ("assembly_capture_position", {"action": "capture"}, _captured, None),
    ("design_activate_component", {"occurrence": "AxisFrameRig:1"}, "ok", None),
    ("find_geometry", {"target": "AxisFrameRig", "kind": "cylinder_face", "max_results": 1}, "ok",
     _fg("afr_cyl")),
    ("model_construction", lambda c: {"kind": "axis", "mode": "circular_face",
                                      "face": _ctx_get(c, "afr_cyl", "the rotated rod's face"),
                                      "name": "AxisFrameSpin"},
     lambda p: _measured("a rotated occurrence's local axis lifts to the face proxy's world reading",
                         {"frame": p.get("frame"),
                          "direction": (p.get("geometry") or {}).get("direction"),
                          "aligned": p.get("aligned_to_face_axis")},
                         p.get("frame") == "world" and p.get("aligned_to_face_axis") is True
                         and _near(abs(((p.get("geometry") or {}).get("direction") or [0, 0, 0])[1]),
                                   1.0, 1e-3)), None),
    # a rotate move BY NAME about that same construction axis, still inside a rotated, captured
    # occurrence: the axis's owning component equals the move's host, which a proxy lift must not
    # skip just because "nothing foreign" - the body it turns is what proves the axis landed.
    ("model_move", {"mode": "rotate", "bodies": ["AxisFrameRig"], "axis": "AxisFrameSpin",
                    "angle_deg": 30},
     lambda p: _measured("rotate by NAME about a construction axis owned by the rotated occurrence "
                         "itself",
                         {"mode": p.get("mode"), "moved": p.get("moved"),
                          "displacement": p.get("displacement")},
                         p.get("moved") is True and p.get("mode") == "rotate"
                         and isinstance(p.get("displacement"), (int, float))
                         and p.get("displacement") > 0), None),
    # a datum NAME reaches only the ACTIVE component, so the same name from the root is refused
    # rather than resolved to something else. (A second same-named axis is never ambiguous - Fusion
    # dedupes the name itself.) The activation is put back so the cameo tree is unchanged.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_pattern_circular", lambda c: {"bodies": [_ctx_get(c, "fc_body", "cameo body")],
                                          "quantity": 3, "axis": "CameoSpin"}, "refused", None),
    ("design_activate_component", {"occurrence": "FeatureCameo:1"}, "ok", None),
    # Three isolated root-parametric joins carry the accepted complete, partial and disjoint
    # controls. Each owns and closes its scratch document, then returns the story to root.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("doc_get", {}, _home_document,
     ("combine_story", _recall("combine_story", _combine_story_address))),
] + _COMBINE_COMPLETE + _COMBINE_PARTIAL + _COMBINE_NONE + _COMBINE_NONROOT_PARTIAL + _REVOLVE_PARTICIPANTS + [
    ("design_activate_component", {"occurrence": "root"}, "ok", None),    # the revolve axis as a CYLINDRICAL FACE, off the origin - the case a world key cannot express.
    # A face mapped to a direction VECTOR keeps the direction and DROPS the location, so the ring is
    # turned about the world axis through the ORIGIN and reported as success: the label is checked
    # AND the geometry measured. Live: a cylinder at x=30, a 2x3 mm profile at x 36-38 on the XZ
    # plane, ring bbox x 22..38. The cameo sits at z=100, clear of the part and the other cameos.
    ("model_create_component", {"name": "RevolveCameo", "activate": True}, _made_component, None),
    ("model_construction", {"kind": "plane", "plane": "xy", "offset": 100, "name": "RevAxisPlane"},
     _datum_plane("xy"), None),
    ("sketch_create", {"plane": "RevAxisPlane", "name": "RevAxisS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 30, "cy": 0, "radius": 5}],
                             "sketch_name": "RevAxisS"}, "ok", None),
    ("model_extrude", {"sketch_name": "RevAxisS", "profile_index": 0, "distance": 20}, _extruded, None),
    ("find_geometry", {"target": "RevolveCameo", "kind": "cylinder_face", "radius": 5, "max_results": 1}, "ok", _fg("rv_cyl")),
    ("sketch_create", {"plane": "xz", "name": "RevRingS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 36, "y1": 100,
                                           "x2": 38, "y2": 103}],
                             "sketch_name": "RevRingS"}, "ok", None),
    ("model_revolve", lambda c: {"sketch_name": "RevRingS", "profile_index": 0,
                                 "axis": _ctx_get(c, "rv_cyl", "the off-origin cylinder face"),
                                 "angle_deg": 360},
     lambda p: p.get("axis") == "BRepFace", None),
    # the label alone cannot see wrong geometry: the ring must stand AROUND x=30, never around the
    # origin (about the world z axis this profile spans x -38..38, so a positive min x is the tell).
    ("model_inspect", {"target": "RevolveCameo:1"},
     lambda p: (p["min_point"]["x"] >= 20 and p["max_point"]["x"] <= 40
                and p["min_point"]["x"] > 0), None),
    # a PLANAR face carries a normal, not an axis - refused by name (only a cylindrical/conical/
    # toroidal face defines one) instead of turned into a direction the caller never asked for.
    ("find_geometry", {"target": "RevolveCameo", "kind": "planar_face", "nearest_to": [30, 0, 120],
                       "max_results": 1}, "ok", _fg("rv_flat")),
    ("model_revolve", lambda c: {"sketch_name": "RevRingS", "profile_index": 0,
                                 "axis": _ctx_get(c, "rv_flat", "a planar cap face"),
                                 "angle_deg": 360}, "refused", None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    # 'all' takes EVERY closed region, and the bays inside a frame outline are closed regions too -
    # so this extrude fills them with material. The payload cannot show a solid bay, so the enclosed
    # regions are NAMED: an outer rectangle plus three bays reports the three that sit inside another.
    ("model_create_component", {"name": "BayCameo", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "BayS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 200, "y1": 900,
                                           "x2": 290, "y2": 960}],
                             "sketch_name": "BayS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 210, "y1": 910,
                                           "x2": 230, "y2": 950}],
                             "sketch_name": "BayS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 240, "y1": 910,
                                           "x2": 260, "y2": 950}],
                             "sketch_name": "BayS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 270, "y1": 910,
                                           "x2": 285, "y2": 950}],
                             "sketch_name": "BayS"}, "ok", None),
    ("model_extrude", {"sketch_name": "BayS", "profile_index": "all", "distance": 8},
     lambda p: (isinstance(p.get("enclosed_profile_indices"), list)
                and len(p["enclosed_profile_indices"]) > 0
                and "enclosed" in p.get("note", "")), None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    # Radius filtering uses the full measurement while the returned record stays at three decimals.
    # Two separately measured cylinders make the target/decoy decision observable in every unit.
    ("model_create_component", {"name": "RadiusFilterBench", "activate": True},
     _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "RadiusTargetS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 2300, "cy": 0,
                                           "radius": 2.68224}],
                             "sketch_name": "RadiusTargetS"}, "ok", None),
    ("model_extrude", {"sketch_name": "RadiusTargetS", "profile_index": 0, "distance": 10},
     _extruded, None),
    ("sketch_create", {"plane": "xy", "name": "RadiusDecoyS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 2320, "cy": 0,
                                           "radius": 5}],
                             "sketch_name": "RadiusDecoyS"}, "ok", None),
    ("model_extrude", {"sketch_name": "RadiusDecoyS", "profile_index": 0, "distance": 10},
     _extruded, None),
    # Position-only acquisition keeps the size proof independent of the radius filter. The target
    # face set has one cylindrical face; the target edge set has both circular rims, selected ahead
    # of the decoy by distance to their midpoint.
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "cylinder_face",
                       "nearest_to": [2300, 0, 5], "max_results": 1},
     _matched(1, "cylinder_face"), _fgn("radius_target_faces")),
    ("model_inspect", lambda c: {"target": _ctx_get(
        c, "radius_target_faces", "the independently acquired target face")[0], "units": "mm"},
     _radius_body_size("independent target face is a 2.68224 mm radius cylinder", 5.36448),
     None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "cylinder_face",
                       "nearest_to": [2320, 0, 5], "max_results": 1},
     _matched(1, "cylinder_face"), _fg("radius_decoy_face")),
    ("model_inspect", lambda c: {"target": _ctx_get(
        c, "radius_decoy_face", "the independently acquired decoy face"), "units": "mm"},
     _radius_body_size("independent decoy face is a 5 mm radius cylinder", 10.0), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "circular_edge",
                       "nearest_to": [2300, 0, 5], "max_results": 2},
     _matched(2, "circular_edge"), _fgn("radius_target_edges")),
    ("model_inspect", lambda c: {"target": _ctx_get(
        c, "radius_target_edges", "the independently acquired target edges")[0], "units": "mm"},
     _radius_body_size(
         "independent target edge resolves to its 2.68224 mm radius owning body", 5.36448),
     None),
    # The inside query must include the target and the 0.00124 mm farther query must exclude it.
    # Each positive call retains every handle. The following model_inspect calls consume the actual
    # filtered handles; the tight body-size readback proves each one belongs to the target cylinder.
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "cylinder_face",
                       "radius": 2.55524, "units": "mm"},
     _matched(1, "cylinder_face"), _fgn("radius_face_mm")),
    ("model_inspect", lambda c: _radius_filtered_handle(
        c, "radius_face_mm", 0),
     _radius_body_size("mm-filtered face is the 2.68224 mm radius target", 5.36448), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "cylinder_face",
                       "radius": 2.554, "units": "mm"},
     _matched(0, "cylinder_face"), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "cylinder_face",
                       "radius": 0.255524, "units": "cm"},
     _matched(1, "cylinder_face"), _fgn("radius_face_cm")),
    ("model_inspect", lambda c: _radius_filtered_handle(
        c, "radius_face_cm", 0),
     _radius_body_size("cm-filtered face is the 2.68224 mm radius target", 5.36448), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "cylinder_face",
                       "radius": 0.2554, "units": "cm"},
     _matched(0, "cylinder_face"), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "cylinder_face",
                       "radius": 0.1006, "units": "in"},
     _matched(1, "cylinder_face"), _fgn("radius_face_in")),
    ("model_inspect", lambda c: _radius_filtered_handle(
        c, "radius_face_in", 0),
     _radius_body_size("inch-filtered face is the 2.68224 mm radius target", 5.36448), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "cylinder_face",
                       "radius": 0.1005511811023622, "units": "in"},
     _matched(0, "cylinder_face"), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "circular_edge",
                       "radius": 2.55524, "units": "mm"},
     _matched(2, "circular_edge"), _fgn("radius_edges_mm")),
    ("model_inspect", lambda c: _radius_filtered_handle(
        c, "radius_edges_mm", 0),
     _radius_body_size("first mm-filtered edge owns the 2.68224 mm radius target", 5.36448), None),
    ("model_inspect", lambda c: _radius_filtered_handle(
        c, "radius_edges_mm", 1),
     _radius_body_size("second mm-filtered edge owns the 2.68224 mm radius target", 5.36448), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "circular_edge",
                       "radius": 2.554, "units": "mm"},
     _matched(0, "circular_edge"), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "circular_edge",
                       "radius": 0.255524, "units": "cm"},
     _matched(2, "circular_edge"), _fgn("radius_edges_cm")),
    ("model_inspect", lambda c: _radius_filtered_handle(
        c, "radius_edges_cm", 0),
     _radius_body_size("first cm-filtered edge owns the 2.68224 mm radius target", 5.36448), None),
    ("model_inspect", lambda c: _radius_filtered_handle(
        c, "radius_edges_cm", 1),
     _radius_body_size("second cm-filtered edge owns the 2.68224 mm radius target", 5.36448), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "circular_edge",
                       "radius": 0.2554, "units": "cm"},
     _matched(0, "circular_edge"), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "circular_edge",
                       "radius": 0.1006, "units": "in"},
     _matched(2, "circular_edge"), _fgn("radius_edges_in")),
    ("model_inspect", lambda c: _radius_filtered_handle(
        c, "radius_edges_in", 0),
     _radius_body_size(
         "first inch-filtered edge owns the 2.68224 mm radius target", 5.36448), None),
    ("model_inspect", lambda c: _radius_filtered_handle(
        c, "radius_edges_in", 1),
     _radius_body_size(
         "second inch-filtered edge owns the 2.68224 mm radius target", 5.36448), None),
    ("find_geometry", {"target": "RadiusFilterBench", "kind": "circular_edge",
                       "radius": 0.1005511811023622, "units": "in"},
     _matched(0, "circular_edge"), None),
    *_PRECISION_READS,
    # AS_SURFACE OVER A CLOSED ELLIPSE: the sketch also holds the ellipse's two construction axes.
    # The extrude must land a surface wall, read off the feature AND off the body's own flag. Each
    # of these three benches sits out at x 1410..1540 through its component placement.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "EllipseWall", "activate": True, "x": 1410},
     _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "EllipseWallS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "ellipse", "cx": 0, "cy": 0, "radius": 15,
                                           "minor": 8}],
                             "sketch_name": "EllipseWallS"}, "ok", None),
    ("model_extrude", {"sketch_name": "EllipseWallS", "profile_index": 0, "distance": 10,
                       "as_surface": True},
     lambda p: _measured("an ellipse extruded as_surface lands a surface",
                         {"as_surface": p.get("as_surface"), "is_solid": p.get("is_solid")},
                         p.get("as_surface") is True and p.get("is_solid") is False), None),
    ("model_inspect", {"target": "EllipseWall:1", "include": ["default", "mass"],
                       "per_body": True},
     lambda p: _measured("the ellipse wall's one body reads is_solid false",
                         [(r.get("body"), r.get("is_solid"))
                          for r in (p.get("mass") or {}).get("per_body") or []],
                         [r.get("is_solid") for r in (p.get("mass") or {}).get("per_body") or []]
                         == [False]), None),
    # TO_FACE DEPTH: a to-face extent has no distance parameter, so the landed depth is read off
    # the new body. The circle on z=0 runs up to the roof block's underside at z=30.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "ToFaceCap", "activate": True, "x": 1470},
     _made_component, None),
    ("model_construction", {"kind": "plane", "plane": "xy", "offset": 30, "name": "ToFaceRoof"},
     _datum_plane("xy"), None),
    ("sketch_create", {"plane": "ToFaceRoof", "name": "ToFaceRoofS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": -20, "y1": -20,
                                           "x2": 20, "y2": 20}],
                             "sketch_name": "ToFaceRoofS"}, "ok", None),
    ("model_extrude", {"sketch_name": "ToFaceRoofS", "profile_index": 0, "distance": 10},
     _extruded, None),
    # a callable, so the layout reads no world point off it: the bench is placed by its component
    ("find_geometry", lambda c: {"target": "ToFaceCap", "kind": "planar_face",
                                 "nearest_to": [1470, 0, 30], "max_results": 1},
     _matched(1, "planar_face"), _fg("to_face_floor")),
    ("sketch_create", {"plane": "xy", "name": "ToFaceS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 0, "cy": 0, "radius": 5}],
                             "sketch_name": "ToFaceS"}, "ok", None),
    ("model_extrude", lambda c: {"sketch_name": "ToFaceS", "profile_index": 0,
                                 "extent": "to_face",
                                 "to_object": _ctx_get(c, "to_face_floor", "the roof's underside")},
     lambda p: _measured("to_face publishes the landed depth",
                         {"extent": p.get("extent"), "depth_mm": p.get("depth_mm")},
                         p.get("extent") == "to_object" and _near(p.get("depth_mm"), 30.0, 0.05)),
     None),
    # A ROTATED OCCURRENCE'S BOX: a 40 mm disc turned 45 deg about its own axis still spans 40 mm.
    # Measured on a 200 mm disc: the proxy's plain boundingBox read 200 x sqrt 2 after the turn.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "RotDisc", "activate": True, "x": 1540},
     _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "RotDiscS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 0, "cy": 0, "radius": 20}],
                             "sketch_name": "RotDiscS"}, "ok", None),
    ("model_extrude", {"sketch_name": "RotDiscS", "profile_index": 0, "distance": 5},
     _extruded, None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("assembly_move", {"occurrence": "RotDisc:1", "rotate_deg": 45, "rotate_axis": "z"},
     _moved_occurrence(), None),
    ("assembly_capture_position", {"action": "capture"}, _captured, None),
    ("model_inspect", {"target": "RotDisc:1", "units": "mm"},
     lambda p: _measured("a 45 deg turned disc keeps its tight 40 mm box",
                         {"x": p.get("x"), "y": p.get("y"), "box_read": p.get("box_read")},
                         _near(p.get("x"), 40.0, 0.05) and _near(p.get("y"), 40.0, 0.05)
                         and p.get("box_read") == "preciseBoundingBox"), None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    *_SWEEP_EDIT_MODES,
]


_DETAILS = [
    *_DEFINITION_READS,
    *_DATUM_OPERANDS,
    # THE HOLES AS THE MACHINE SEES THEM, read FIRST: the chamfers below break two of these rims,
    # and a broken rim is a hole of a different shape, so the recognizer's grouping is read while
    # the drilled pattern is still as model_hole left it. The saved handles drive the CAM act's
    # recognized-hole drill; BoreDia is PartHt * 0.3 = 12 mm.
    # Recognition needs the Manufacturing Extension (measured on the lapsed install: "Requires the
    # Manufacturing Extension to be active"), so the recognizer rows ride the tier and the
    # unentitled variant asserts the refusal names the extension and the by-hand route.
    ("cam_find_holes", {"bodies": ["Bracket:1"]},
     _needs(MACHINING_EXTENSION, _holes_recognized(2, 4, 12.0)),
     _recognized_cbore_walls("recognized_cbore_walls", count_key="holes_group_count")),
    ("cam_find_holes", {"bodies": ["Bracket:1"]},
     _unless(MACHINING_EXTENSION, _refused("Manufacturing Extension", "find_geometry")), None),
    # The window, on the same part: at 11 mm every BoreDia group falls out (the step bore and the
    # longer boss bore are separate groups - the recognizer groups by identical length) and the
    # 10.8 mm counterbores stay; kept plus dropped is the unwindowed total, so nothing is lost.
    ("cam_find_holes", {"bodies": ["Bracket:1"], "max_diameter": 11},
     _needs(MACHINING_EXTENSION, _holes_windowed(12.0, "holes_group_count")), None),
    # THE POCKET AS THE MACHINE SEES IT, down the same axis a 3-axis setup attacks: PocketDepth is
    # PartHt * 0.4 = 16 mm, so the floor sits that far under the low top the cut opened, and the
    # four PocketRad corners round its single boundary loop. The saver takes that pocket's FLOOR
    # handle - the face whose locator sits lowest along the attack - which drives a 2D pocket of its
    # own in the CAM act; its count and its loop size are what the two rows after it read back.
    # Plain pocket recognition runs on the base licence (measured on the lapsed install: 8 pockets
    # read back); only the boss-aware route below rides the tier.
    ("cam_find_pockets", {"bodies": ["Bracket:1"]}, _pockets_recognized(16.0),
     _recognized_pocket_floor("pocket_floor", 16.0, count_key="pockets_plain_count",
                              loop_key="pocket_loop_segments")),
    # ...and the boss, which only the boss-aware route reports: it comes back as a pocket with an
    # ISLAND and no boundary - the one shape that separates a boss from a recess. The row rides the
    # extension tier, so a base licence skips it rather than reddening the run.
    ("cam_find_pockets", {"bodies": ["Bracket:1"], "include_bosses": True},
     _needs(MACHINING_EXTENSION, _pocket_boss("pockets_plain_count")), None),
    # The rims the part is handled by, each asked for by RADIUS - the one query that keeps naming
    # the same edge after the driver changes. A fillet's own tangent circle is not a corner, and
    # handing one back to model_fillet answers FILLET_NO_EDGE_FOUND, so every beat below picks a
    # rim no earlier feature has already rounded.
    # Every one of these queries FEEDS the next step, so each asserts the count it found: a radius
    # filter that matches nothing still returns ok, and the ledger then reports a bare pass on a
    # query whose handle the following row cannot take.
    ("find_geometry", {"target": "Bracket", "kind": "circular_edge", "radius": 10,
                       "max_results": 1}, _matched(1, "circular_edge"), _fg("boss_rim")),
    ("model_fillet", lambda c: {"edges": [_ctx_get(c, "boss_rim", "the boss rim")],
                                "radius": 1.5}, _filleted, None),
    ("find_geometry", {"target": "Bracket", "kind": "circular_edge", "radius": 6,
                       "max_results": 1}, _matched(1, "circular_edge"), _fg("bore_rim")),
    ("model_chamfer", lambda c: {"edges": [_ctx_get(c, "bore_rim", "a through-bore rim")], "distance": 1}, _chamfered, None),
    # the distance-and-angle definition with an explicit corner type. Both assertions are on values
    # READ BACK off the created feature - a corner type the platform silently ignored builds an
    # identical face count, so an echoed payload would sail through this predicate.
    ("find_geometry", {"target": "Bracket", "kind": "circular_edge", "radius": 3,
                       "max_results": 4}, _matched(4, "circular_edge"),
     ("mount_rim", lambda p: p["matches"][-1]["handle"])),
    ("model_chamfer", lambda c: {"edges": [_ctx_get(c, "mount_rim", "a mounting-bore rim")],
                                 "distance": 1, "angle_deg": 30, "corner_type": "miter"},
     lambda p: p.get("corner_type") == "miter" and abs((p.get("angle_deg") or 0) - 30) < 1e-6
     and not p.get("corner_type_unverified") and not p.get("angle_deg_unverified") and not p.get("chamfer_type_unverified"), None),
    # a shell cameo cap, a wart feature added and deleted (timeline health diff), a scratch occurrence.
    ("model_create_component", {"name": "ShellCap", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "ShellS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 400, "y1": 0,
                                           "x2": 430, "y2": 30}],
                             "sketch_name": "ShellS"}, "ok", None),
    ("model_extrude", {"sketch_name": "ShellS", "profile_index": 0, "distance": 20}, _extruded, None),
    ("find_geometry", {"target": "ShellCap", "kind": "planar_face", "nearest_to": [415, 15, 20], "max_results": 1}, "ok", _fg("shell_top")),
    ("model_shell", lambda c: {"body_name": "ShellCap", "remove_faces": [_ctx_get(c, "shell_top", "shell top")], "thickness": 2}, _shelled, None),
    # THE TWO-SIDED EXTENT, in its own component so nothing else's body census moves. Side one lands
    # on extentOne and side two on extentTwo, each reporting the depth THAT side asked for, and the
    # tool now compares them side by side - so an UNEQUAL pair is the shape that tells the compare
    # apart from one reading a single number twice. The payload alone cannot show where the material
    # went, hence the inspect below.
    ("model_create_component", {"name": "TwoSideCap", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "TwoSideS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 470, "y1": 0,
                                           "x2": 500, "y2": 30}],
                             "sketch_name": "TwoSideS"}, "ok", None),
    # 'model_parameters' carrying BOTH distance and distance2 is the feature really holding two
    # extents; an EMPTY unverified disclosure is the compare having judged both sides rather than
    # skipping one (it names any side it could not judge).
    ("model_extrude", {"sketch_name": "TwoSideS", "profile_index": 0, "extent": "two_side",
                       "distance": 12, "distance2": 8},
     lambda p: (p.get("extent") == "two_side" and p.get("distance") == 12.0
                and p.get("distance2") == 8.0 and bool(p.get("result_bodies"))
                and "distance" in (p.get("model_parameters") or {})
                and "distance2" in (p.get("model_parameters") or {})
                and "not depth-verified" not in (p.get("note") or "")), None),
    # Where the material actually went: the sketch sits on z=0, so a correct two-sided extrude
    # STRADDLES it 20 mm deep and UNEQUALLY. A symmetric 12/12 or 8/8 fails the inequality, a
    # one-sided 20 fails the straddle, and a swap only changes which face is which - all three are
    # payloads that would read identically above.
    ("model_inspect", {"target": "TwoSideCap:1"},
     lambda p: (p["min_point"]["z"] < -0.001 and p["max_point"]["z"] > 0.001
                and abs((p["max_point"]["z"] - p["min_point"]["z"]) - 20) < 0.05
                and abs(abs(p["max_point"]["z"]) - abs(p["min_point"]["z"])) > 3), None),
    # back to the shell cameo's component, so every step after this lands where it did before.
    *_EXTRUDE_EDITS,
    *_BODY_ORGANIZATION,
    ("design_activate_component", {"occurrence": "ShellCap:1"}, "ok", None),
    # THE WartPlane ROW carries the offset_from predicate - the sweep's only offset-plane call, so
    # it is where 'offset_from' gets read once against a real resolved origin plane: the payload
    # must name the PLANE ('XY'), never echo the 'xy' request token. The unit fake spells the name
    # uppercase from the sibling convention; this beat is what MEASURES the live casing, so a
    # failure on the string alone means the FAKE is what is wrong, never the tool.
    ("model_construction", {"kind": "plane", "plane": "xy", "offset": 12, "name": "WartPlane"},
     lambda p: p.get("offset_from") == "XY", None),
    # 'deleted' is true only where the timeline name census read on BOTH sides of the delete; null is
    # an absence nothing could prove, and a delete that broke a downstream feature says so.
    ("design_delete_feature", {"feature": "WartPlane"},
     lambda p: (p["deleted"] is True and p["feature"] == "WartPlane"
                and "timeline_warning" not in p), None),
    # the three datum modes with no other route in the API: a plane rotated about a curved face's
    # own inferred axis, a plane pinned through a vertex, and a plane/point at a ratio along a path.
    # The angled plane is built on the DATUM BENCH's bore, not on the machined part. A datum
    # plane is an infinite visual object and the shaft sits at the world origin - which is where the
    # vise is later built around the machined part, so a plane hung there leans across the fixture
    # for the rest of the run. The bench is out on the field with its own cell and its own frame.
    ("model_construction", lambda c: {"kind": "plane", "mode": "at_angle_on_face",
                                      "face": _ctx_get(c, "db_bore", "bench bore"),
                                      "plane": "xz", "angle": 30, "name": "BenchAnglePlane"},
     # the bore's axis is Z through the bench's own centre, so the plane contains that axis and its
     # origin sits ON it - asked through _px/_py because the layout moves the bench.
     lambda p: p.get("contains_face_axis") is True and p.get("angle_deg") == 30
     and _near(p["geometry"]["origin"]["x"], _px("DatumBench", 230.0), 1e-3)
     and _near(p["geometry"]["origin"]["y"], _py("DatumBench", 20.0), 1e-3), None),
    ("find_geometry", {"target": "ShellCap", "kind": "vertex", "max_results": 1}, "ok", _fg("cd_vert")),
    ("model_construction", lambda c: {"kind": "plane", "mode": "offset_through_point", "plane": "xy",
                                      "points": [_ctx_get(c, "cd_vert", "shell vertex")],
                                      "name": "ThroughVertexPlane"},
     lambda p: p.get("passes_through_point") is True, None),
    # the bottom front edge specifically: (400,0,0) -> (430,0,0), midpoint (415,0,0).
    ("find_geometry", {"target": "ShellCap", "kind": "line_edge", "nearest_to": [415, 0, 0], "max_results": 1},
     "ok", _fg("cd_edge")),
    # The on-path placements all ride ONE known path: the cap's bottom front edge, 30 mm long from
    # (400,0,0) to (430,0,0). A PROPORTIONAL placement reads 'at' as a unitless ratio and publishes
    # it back as the ratio it landed on - no path extent at all, because a ratio cannot leave the
    # path. Every absolute beat below is measured against that same 30 mm.
    ("model_construction", lambda c: {"kind": "plane", "mode": "on_path",
                                      "path": _ctx_get(c, "cd_edge", "datum path edge"),
                                      "at": 0.5, "name": "MidPathPlane"},
     lambda p: p.get("at_ratio") == 0.5
     and abs(p["geometry"]["origin"]["x"] - _px("ShellCap", 415)) < 1e-3
     and abs(p["geometry"]["origin"]["y"] - _py("ShellCap", 0)) < 1e-3
     and abs(p["geometry"]["origin"]["z"]) < 1e-3
     and p.get("landed", {}).get("distance") == "0.5"
     and "path_length" not in p and "beyond_path" not in p
     and "not clamped" not in (p.get("note") or ""), None),
    # a quarter along the SAME edge: 7.5 mm from the midpoint whichever way the edge runs.
    ("model_construction", lambda c: {"kind": "point", "mode": "on_path",
                                      "path": _ctx_get(c, "cd_edge", "datum path edge"),
                                      "at": 0.25, "name": "QuarterPathPoint"},
     lambda p: p.get("at_ratio") == 0.25
     and abs(abs(p["geometry"]["at"]["x"] - _px("ShellCap", 415)) - 7.5) < 1e-3
     and abs(p["geometry"]["at"]["y"] - _py("ShellCap", 0)) < 1e-3
     and abs(p["geometry"]["at"]["z"]) < 1e-3, None),
    # setByPath RAISES on a proportional value outside 0-1 and the raise rolls back the whole
    # transaction, so the range is refused before the call - and the next call still answers.
    ("model_construction", lambda c: {"kind": "point", "mode": "on_path",
                                      "path": _ctx_get(c, "cd_edge", "datum path edge"), "at": 1.5},
     "refused", None),
    # ABSOLUTE: 'at' is a LENGTH from the path start, so the payload swaps the ratio for the pair
    # that can be compared - the measured path length and where this datum sits along it. 12 mm is
    # inside the 30 mm edge, so beyond_path is false and the note warns of nothing.
    ("model_construction", lambda c: {"kind": "plane", "mode": "on_path",
                                      "path": _ctx_get(c, "cd_edge", "datum path edge"),
                                      "at": 12, "distance_type": "absolute",
                                      "name": "AbsInsidePlane"},
     lambda p: p.get("distance_type") == "absolute" and "at_ratio" not in p
     and isinstance(p.get("landed", {}).get("distance"), str)
     and abs(p.get("path_length", 0) - 30.0) < 1e-3
     and abs(p.get("along_path", -1) - 12.0) < 1e-3
     and p.get("beyond_path") is False and "OFF the path" not in (p.get("note") or ""), None),
    # An absolute distance is not clamped at EITHER end: a NEGATIVE one places the datum before the
    # path start, along the tangent, with a healthy feature. That is a legal placement the platform
    # accepts, so it is reported with its measured numbers - and the note says it landed off.
    ("model_construction", lambda c: {"kind": "plane", "mode": "on_path",
                                      "path": _ctx_get(c, "cd_edge", "datum path edge"),
                                      "at": -5, "distance_type": "absolute",
                                      "name": "BeforeStartPlane"},
     lambda p: p.get("beyond_path") is True and abs(p.get("along_path", 0) + 5.0) < 1e-3
     and "OFF the path" in (p.get("note") or ""), None),
    # the far end of the same range, on the point kind: 500 mm along a 30 mm edge.
    ("model_construction", lambda c: {"kind": "point", "mode": "on_path",
                                      "path": _ctx_get(c, "cd_edge", "datum path edge"),
                                      "at": 500, "distance_type": "absolute",
                                      "name": "PastEndPoint"},
     lambda p: p.get("beyond_path") is True and abs(p.get("path_length", 0) - 30.0) < 1e-3, None),
    # the boundary itself: a datum exactly AT the path length is ON the path, not beyond it.
    ("model_construction", lambda c: {"kind": "plane", "mode": "on_path",
                                      "path": _ctx_get(c, "cd_edge", "datum path edge"),
                                      "at": 30, "distance_type": "absolute",
                                      "name": "AtEndPlane"},
     lambda p: p.get("beyond_path") is False
     and abs(p.get("along_path", -1) - p.get("path_length", 0)) < 1e-6, None),
    # an EXPRESSION placement is measured exactly as a literal one - the expression is what the
    # datum's own model parameter carries, and that parameter's name is what param_set retargets.
    ("model_construction", lambda c: {"kind": "point", "mode": "on_path",
                                      "path": _ctx_get(c, "cd_edge", "datum path edge"),
                                      "at": "22 mm", "distance_type": "absolute",
                                      "name": "ExprPathPoint"},
     lambda p: "22" in (p.get("landed", {}).get("distance") or "")
     and str(p.get("model_parameters", {}).get("distance", "")).startswith("d"), None),
    # proportional on the plane kind reads back as the bare ratio, with no extent published - the
    # pair that separates the two distance types in one payload.
    ("model_construction", lambda c: {"kind": "plane", "mode": "on_path",
                                      "path": _ctx_get(c, "cd_edge", "datum path edge"),
                                      "at": 0.5, "distance_type": "proportional",
                                      "name": "RatioPlane"},
     lambda p: p.get("landed", {}).get("distance") == "0.5"
     and "path_length" not in p and "beyond_path" not in p, None),
    # to_object: the plane lands at a VERTEX's own along-path position PLUS a signed offset, and the
    # two arrive as SEPARATE model parameters. 40 mm past either end of a 30 mm edge is off the path
    # whichever vertex the edge starts at, so this one carries the same off-path disclosure.
    ("find_geometry", {"target": "ShellCap", "kind": "vertex", "nearest_to": [430, 0, 0],
                       "max_results": 1}, "ok", _fg("cd_vert_end")),
    ("model_construction", lambda c: {"kind": "plane", "mode": "on_path",
                                      "path": _ctx_get(c, "cd_edge", "datum path edge"),
                                      "to_object": _ctx_get(c, "cd_vert_end", "a path end vertex"),
                                      "offset": 40, "name": "ToObjectFarPlane"},
     lambda p: p.get("to_object") is True
     and set(p.get("landed", {})) == {"distance", "offset"}
     and set(p.get("model_parameters", {})) == {"distance", "offset"}
     and abs(p.get("path_length", 0) - 30.0) < 1e-3
     and p.get("along_path", 0) > p.get("path_length", 0)
     and p.get("beyond_path") is True and "OFF the path" in (p.get("note") or ""), None),
    # the same shape landing INSIDE, so the disclosure is proven to discriminate: the cap's bottom
    # front and right edges chain into a 60 mm path whose shared vertex sits at 30 mm, and 5 mm past
    # that is still on the path.
    ("find_geometry", {"target": "ShellCap", "kind": "line_edge", "nearest_to": [430, 15, 0],
                       "max_results": 1}, "ok", _fg("cd_edge2")),
    ("model_construction", lambda c: {"kind": "plane", "mode": "on_path",
                                      "path": [_ctx_get(c, "cd_edge", "datum path edge"),
                                               _ctx_get(c, "cd_edge2", "the connected second edge")],
                                      "to_object": _ctx_get(c, "cd_vert_end", "the shared vertex"),
                                      "offset": 5, "name": "ToObjectMidPlane"},
     lambda p: p.get("beyond_path") is False and abs(p.get("along_path", 0) - 35.0) < 1e-3
     and "OFF the path" not in (p.get("note") or ""), None),
    # ConstructionPointInput carries setByPath but NOT setByPathToObject, so the point kind refuses
    # 'to_object' by name instead of dropping it.
    ("model_construction", lambda c: {"kind": "point", "mode": "on_path",
                                      "path": _ctx_get(c, "cd_edge", "datum path edge"),
                                      "to_object": _ctx_get(c, "cd_vert_end", "a path end vertex")},
     "refused", None),
    # a CHAINED path is measured whole: 45 mm is past the first edge but inside the 60 mm total, so
    # the datum is on the path and 'path_length' is the SUM, not the seed edge's own length.
    ("model_construction", lambda c: {"kind": "plane", "mode": "on_path",
                                      "path": [_ctx_get(c, "cd_edge", "datum path edge"),
                                               _ctx_get(c, "cd_edge2", "the connected second edge")],
                                      "at": 45, "distance_type": "absolute",
                                      "name": "ChainedPathPlane"},
     lambda p: p.get("beyond_path") is False and abs(p.get("path_length", 0) - 60.0) < 1e-3
     and abs(p.get("along_path", 0) - 45.0) < 1e-3, None),
    # sketch_project's two new actions, on the cap the datum beats already measured. The section
    # sketch sits on MidPathPlane (x=415, normal along X), which crosses the cap cleanly; the cap's
    # x=400 side face is PARALLEL to that plane, so it is the same-context source that contributes
    # nothing and the partial path must name it.
    ("sketch_create", {"plane": "MidPathPlane", "name": "SecS"}, "ok", None),
    # the section of the HOLLOW cap is outer + inner rectangles - at least 8 curves. Attribution is
    # honestly SUPPRESSED whenever any created curve fails to match back, so the beat asserts the
    # census, not per_source.
    ("sketch_project", {"action": "intersect", "sketch_name": "SecS", "bodies": ["ShellCap"]},
     lambda p: p.get("created_count", 0) >= 8 and len(p.get("entity_refs") or []) >= 8, None),
    # the cap's x=400 side face is PARALLEL to the section plane: zero curves created is the
    # measured silent-empty, which the tool's own gate converts into an error naming the source.
    ("find_geometry", {"target": "ShellCap", "kind": "planar_face", "nearest_to": [400, 15, 10], "max_results": 1}, "ok", _fg("sp_far")),
    ("sketch_project", lambda c: {"action": "intersect", "sketch_name": "SecS",
                                  "entities": [_ctx_get(c, "sp_far", "cap far side face")]},
     "refused", None),
    # to_surface: ShellS's own lines projected onto the cap's top face, received by a THIRD sketch -
    # the source sketch must differ from the receiver (measured same-sketch refusal), the curves
    # land ON the face (off the receiver's plane), and the linkage is read back per curve.
    ("sketch_create", {"plane": "xy", "name": "ProjS"}, "ok", None),
    ("find_geometry", {"target": "ShellCap", "kind": "planar_face", "nearest_to": [415, 15, 20], "max_results": 1}, "ok", _fg("sp_top")),
    ("sketch_project", lambda c: {"action": "to_surface", "sketch_name": "ProjS",
                                  "target_faces": [_ctx_get(c, "sp_top", "cap top face")],
                                  "source_sketch": "ShellS", "curve_refs": ["line:0"]},
     lambda p: p.get("created_count", 0) >= 1
     and (p.get("off_plane_count") == p.get("created_count") or "census alone" in p.get("note", ""))
     and ("REFERENCE curves" in p.get("note", "") or "census alone" in p.get("note", "")), None),
    ("sketch_project", {"action": "to_surface", "sketch_name": "ProjS", "target_faces": [],
                        "source_sketch": "ProjS", "curve_refs": ["line:0"]}, "refused", None),
    ("sketch_project", lambda c: {"action": "to_surface", "sketch_name": "ProjS",
                                  "target_faces": [_ctx_get(c, "sp_top", "cap top face")],
                                  "source_sketch": "ShellS", "curve_refs": ["line:0"],
                                  "project_type": "along_vector"}, "refused", None),
    ("model_create_component", {"name": "ScratchOcc", "activate": False}, _made_component_inactive, None),
    # 'deleted' is true only where the assembly path census carried this occurrence BEFORE the delete
    # and not after; null is an unverified absence the payload publishes as a successful call.
    ("design_delete_occurrence", {"occurrence": "ScratchOcc:1"},
     lambda p: (p["deleted"] is True and p["occurrence"] == "ScratchOcc:1"
                and "timeline_warning" not in p), None),
    # scale + offset-face beats on a scratch block: push a face and read the volume move, then the
    # scale contract - uniform f^3, per-axis x*y*z, the three refusal shapes (unresolvable /
    # length-carrying / angle-carrying expression), a bare unitless parameter accepted, and a
    # vertex-anchored scale.
    ("model_create_component", {"name": "ScaleBlock", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "ScaleS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 470, "y1": 0,
                                           "x2": 490, "y2": 20}],
                             "sketch_name": "ScaleS"}, "ok", None),
    ("model_extrude", {"sketch_name": "ScaleS", "profile_index": 0, "distance": 20}, _extruded, None),
    _watch("ScaleBlock:1"),
    ("find_geometry", {"target": "ScaleBlock", "kind": "planar_face", "nearest_to": [480, 10, 20],
                       "max_results": 1}, "ok", _fg("scale_top")),
    ("model_offset_face", lambda c: {"faces": [_ctx_get(c, "scale_top", "block top")],
                                     "distance": 2}, _offset_faces, None),
    # a UNITLESS and an ANGLE parameter: 'value_units' is the parameter's OWN unit read back, which
    # is what says the angle came out of the internal radians into degrees.
    ("param_add", {"name": "ShrinkProbe", "expression": "0.5", "unit": ""},
     _param_added("ShrinkProbe", 0.5, units=""), None),
    ("param_add", {"name": "TiltProbe", "expression": "30 deg", "unit": "deg"},
     _param_added("TiltProbe", 30, units="deg"), None),
    # a solid body's volume IS readable, so the verdict is the measured ratio and the skip flag is
    # absent - its presence would mean the check fell back to "the geometry moved".
    # A SCALE IS ORIGIN-RELATIVE: it multiplies coordinates measured from the world origin, so a
    # block authored at x=470 doubles to x=940 - it grows AND travels, right out of the frame it was
    # framed in. Every scale that moves it is followed by a fresh frame, or the operation the viewer
    # came to watch happens off screen.
    ("model_scale", {"bodies": ["ScaleBlock"], "factor": 2},
     lambda p: p.get("scale_check") == "volume_ratio"
     and abs(p.get("volume_ratio", 0) - 8.0) < 1e-6 and "volume_check_skipped" not in p, None),
    _watch("ScaleBlock:1"),
    ("model_scale", {"bodies": ["ScaleBlock"], "x_factor": 3, "y_factor": 2, "z_factor": 1},
     lambda p: abs(p.get("expected_volume_ratio", 0) - 6.0) < 1e-6, None),
    _watch("ScaleBlock:1"),
    ("model_scale", {"bodies": ["ScaleBlock"], "factor": "NoSuchParamXyz * 2"}, "refused", None),
    ("model_scale", {"bodies": ["ScaleBlock"], "factor": "5 mm"}, "refused", None),
    ("model_scale", {"bodies": ["ScaleBlock"], "factor": "TiltProbe"}, "refused", None),
    ("model_scale", {"bodies": ["ScaleBlock"], "factor": "ShrinkProbe"},
     lambda p: abs(p.get("expected_volume_ratio", 0) - 0.125) < 1e-6, None),
    _watch("ScaleBlock:1"),
    ("find_geometry", {"target": "ScaleBlock", "kind": "vertex", "max_results": 1}, "ok",
     _fg("scale_vtx")),
    ("model_scale", lambda c: {"bodies": ["ScaleBlock"], "factor": 1.5,
                               "anchor": _ctx_get(c, "scale_vtx", "block vertex")},
     lambda p: abs(p.get("volume_ratio", 0) - 3.375) < 1e-6, None),
    ("param_delete", {"name": "ShrinkProbe"}, _param_deleted("ShrinkProbe"), None),
    ("param_delete", {"name": "TiltProbe"}, _param_deleted("TiltProbe"), None),
    ("model_move", {"bodies": ["ScaleBlock"], "dx": 10},
     lambda p: abs(p.get("displacement", 0) - 10.0) < 1e-3, None),
    ("model_move", {"mode": "along_entity", "bodies": ["ScaleBlock"], "axis": "y",
                    "distance": 5}, lambda p: abs(p.get("displacement", 0) - 5.0) < 1e-3, None),
    ("model_move", {"mode": "rotate", "bodies": ["ScaleBlock"], "axis": "z", "angle_deg": 15},
     _moved, None),
    ("model_move", lambda c: {"mode": "along_entity", "bodies": ["ScaleBlock"],
                              "axis": _ctx_get(c, "scale_top", "block top"), "distance": 5},
     "refused", None),
    ("model_move", lambda c: {"bodies": ["ScaleBlock"],
                              "faces": [_ctx_get(c, "scale_top", "block top")], "dx": 5},
     "refused", None),
    # SINGLE vs DOUBLE placement: the along_entity beats above moved a body in a component placed
    # ONCE (the axis is proxied into that one occurrence). The same call on a component placed TWICE
    # must refuse naming BOTH paths - each instance holds that body somewhere else, and the
    # displacement read-back cannot tell a right instance from a wrong one.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "TwicePlaced", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "TwicePlacedS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 1900, "y1": 200,
                                           "x2": 1920, "y2": 220}],
                             "sketch_name": "TwicePlacedS"}, "ok", None),
    ("model_extrude", {"sketch_name": "TwicePlacedS", "profile_index": 0, "distance": 10},
     _extruded, None),
    # [F75]/NEW-16: name the body uniquely, then resolve it BARE while the component is still the
    # ACTIVE component and placed ONCE - the walk reaches it both natively (active-comp scope) and
    # as the occurrence proxy, whose entityTokens DIFFER; grouping by native token collapses the
    # pair to ONE candidate (a bare-token key refused this as 'names 2 bodies').
    ("find_geometry", {"target": "TwicePlaced", "kind": "planar_face",
                       "nearest_to": [1910, 210, 10], "max_results": 1}, "ok",
     _fg("twice_face")),
    ("design_set_name", lambda c: {"target": _ctx_get(c, "twice_face", "the TwicePlaced body"),
                                   "new_name": "TwiceBody"},
     lambda p: p.get("name") == "TwiceBody", None),
    ("model_inspect", {"target": "TwiceBody"}, _extent_measured, None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("design_add_instance", {"component": "TwicePlaced", "x": 40, "y": 0, "units": "mm"},
     lambda p: p.get("created") is True, ("twice_b", lambda p: p["full_path"])),
    ("model_move", {"mode": "along_entity", "bodies": ["TwicePlaced"], "axis": "y", "distance": 5},
     _refused("placed 2 times", "TwicePlaced:1"), None),
    # placed TWICE the same bare name is two world placements - the refusal lists BOTH
    # instance-qualified forms (the dropped native spelling is not offered), and the qualified
    # form is the way out.
    ("model_inspect", {"target": "TwiceBody"},
     _refused("TwicePlaced:1", "TwicePlaced:2"), None),
    ("model_inspect", {"target": "TwicePlaced:2:TwiceBody"}, _extent_measured, None),
    # back to the component that was active before this cameo, so the ones after it nest as before.
    ("design_activate_component", {"occurrence": "ScaleBlock:1"}, "ok", None),
    # point_to_point: the tool refuses a travel that does not equal the two vertices' own
    # separation, so a plain ok here IS the distance check
    ("find_geometry", {"target": "ScaleBlock", "kind": "vertex", "max_results": 8}, "ok",
     _fgn("mv_verts")),
    ("model_move", lambda c: {"mode": "point_to_point", "bodies": ["ScaleBlock"],
                              "from_point": _ctx_get(c, "mv_verts", "block vertices")[0],
                              "to_point": _ctx_get(c, "mv_verts", "block vertices")[1]},
     lambda p: p.get("moved") is True and p.get("displacement", 0) > 0, None),
    ("model_create_component", {"name": "ThreadPost", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "ThreadS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 530, "cy": 10, "radius": 5}],
                             "sketch_name": "ThreadS"}, "ok", None),
    ("model_extrude", {"sketch_name": "ThreadS", "profile_index": 0, "distance": 25}, _extruded, None),
    ("find_geometry", {"target": "ThreadPost", "kind": "cylinder_face", "max_results": 1}, "ok",
     _fg("post_wall")),
    ("model_thread", lambda c: {"faces": [_ctx_get(c, "post_wall", "post wall")],
                                "designation": "M99x9"}, "refused", None),
    ("model_thread", lambda c: {"faces": [_ctx_get(c, "post_wall", "post wall")],
                                "designation": "M10x1.5", "offset": 2}, "refused", None),
    ("model_thread", lambda c: {"faces": [_ctx_get(c, "post_wall", "post wall")],
                                "designation": "M10x1.5", "length": 12, "offset": 2},
     lambda p: p.get("internal") is False and p.get("designation") == "M10x1.5"
     and p.get("right_handed") is True and p.get("length") == 12, None),
    # the partial extent is read back off the feature, and a metric call-out sits in several
    # standards, so the alternatives ride along
    ("model_thread", lambda c: {"faces": [_ctx_get(c, "post_wall", "post wall")],
                                "designation": "M10x1.5", "length": 12, "offset": 2,
                                "thread_type": "ISO Metric profile"},
     lambda p: p.get("thread_type") == "ISO Metric profile"
     and len(p.get("thread_type_alternatives") or []) > 1, None),
    # a modeled designation far too big for the post grows the body instead of cutting it
    ("model_thread", lambda c: {"faces": [_ctx_get(c, "post_wall", "post wall")],
                                "designation": "M30x3.5", "modeled": True}, "refused", None),
    # a modeled thread that FITS must cut real material - the rung-4 gate's own regression net
    ("model_create_component", {"name": "ThreadPost2", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "ThreadS2"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 570, "cy": 10, "radius": 5}],
                             "sketch_name": "ThreadS2"}, "ok", None),
    ("model_extrude", {"sketch_name": "ThreadS2", "profile_index": 0, "distance": 25}, _extruded, None),
    ("find_geometry", {"target": "ThreadPost2", "kind": "cylinder_face", "max_results": 1}, "ok",
     _fg("post2_wall")),
    ("model_thread", lambda c: {"faces": [_ctx_get(c, "post2_wall", "second post wall")],
                                "designation": "M10x1.5", "modeled": True},
     lambda p: p.get("modeled") is True and p.get("volume_delta_cm3", 0) < 0, None),
    # the INTERNAL side of the same tool, on a real bore: 'internal' is derived from the face's own
    # out-of-material normal (never echoed), and the ThreadInfo it built is checked against the face
    # at add() - so an 'internal' that disagreed with the geometry would have raised. Then a PARTIAL
    # thread measured from the LOW end, with the end it was measured from read back off the feature.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "ThreadBore", "activate": True}, _made_component, None),
    # the bore is CUT, not left as the inner loop of a two-circle profile: which region a
    # multi-profile sketch calls its last one is the platform's to decide, and picking the disc
    # there builds a plain rod whose radius-4 wall is EXTERNAL - the thread then lands external and
    # the beat asserts nothing about bores. A solid rod plus a through cut is unambiguous.
    ("sketch_create", {"plane": "xy", "name": "ThreadBoreS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 610, "cy": 10, "radius": 12}],
                             "sketch_name": "ThreadBoreS"}, "ok", None),
    ("model_extrude", {"sketch_name": "ThreadBoreS", "profile_index": 0, "distance": 25},
     _extruded, None),
    ("sketch_create", {"plane": "xy", "name": "ThreadBoreCut"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 610, "cy": 10, "radius": 4}],
                             "sketch_name": "ThreadBoreCut"}, "ok", None),
    ("model_extrude", {"sketch_name": "ThreadBoreCut", "profile_index": 0, "distance": 25,
                       "operation": "cut"}, _extruded, None),
    ("find_geometry", {"target": "ThreadBore", "kind": "cylinder_face", "radius": 4,
                       "max_results": 1}, "ok", _fg("bore_wall")),
    ("model_thread", lambda c: {"faces": [_ctx_get(c, "bore_wall", "the bore wall")],
                                "designation": "M8x1.25"},
     lambda p: p.get("internal") is True and p.get("designation") == "M8x1.25", None),
    ("model_thread", lambda c: {"faces": [_ctx_get(c, "bore_wall", "the bore wall")],
                                "designation": "M8x1.25", "length": 10, "location": "low"},
     lambda p: p.get("internal") is True and p.get("location") == "low"
     and p.get("length") == 10, None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    # a model EDGE handle as the path: the placement call accepts it and Fusion then rejects the
    # add, so the guard refuses it up front and points at sketch_project.
    ("sketch_set_text", lambda c: {"text": "EDGE", "sketch_name": "TextPaths", "create": True,
                                   "mode": "along_path",
                                   "path": _ctx_get(c, "cd_edge", "a model edge handle")},
     "refused", None),
    # design_remove_feature: cast a scratch body, remove it (the census is the verdict), then
    # delete the Remove feature - the body comes back, which is the reversibility the note claims.
    ("model_create_component", {"name": "RmScratch", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "RmS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 1100, "y1": 0,
                                           "x2": 1120, "y2": 20}],
                             "sketch_name": "RmS"}, "ok", None),
    ("model_extrude", {"sketch_name": "RmS", "profile_index": 0, "distance": 5}, _extruded, None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("design_remove_feature", {"body": "RmScratch"},
     lambda p: p.get("target_kind") == "body" and p.get("feature_read_back") is True,
     ("rm_feat", lambda p: p["feature"])),
    ("design_delete_feature", lambda c: {"feature": _ctx_get(c, "rm_feat", "remove feature")},
     "ok", None),
    # the body is back: a component with no body has no faces, so exactly one match discriminates.
    ("find_geometry", {"target": "RmScratch", "kind": "planar_face", "max_results": 1},
     lambda p: len(p.get("matches") or []) == 1, None),
    # the occurrence variant of the same round trip.
    ("design_remove_feature", {"occurrence": "RmScratch:1"},
     lambda p: p.get("target_kind") == "occurrence" and p.get("feature_read_back") is True,
     ("rm_feat2", lambda p: p["feature"])),
    ("design_delete_feature", lambda c: {"feature": _ctx_get(c, "rm_feat2", "remove feature")},
     "ok", None),
    ("model_inspect", {"target": "RmScratch:1"}, _extent_measured, None),
    # model_emboss: a raise then an engrave on one scratch block's top face. The profiles are drawn
    # on a datum plane COINCIDENT with that face, so each sketch holds exactly one profile (an
    # on-face sketch auto-projects the face boundary and would offer two). The verdict is the
    # measured volume direction: 'mode' echoes the sign of the depth and the call is refused when
    # the material moved the other way.
    *_box("EmbossBlock", ox=600, oy=100),
    ("model_construction", {"kind": "plane", "plane": "xy", "offset": 10, "name": "EmbPlane"},
     _datum_plane("xy"), None),
    ("find_geometry", {"target": "EmbossBlock", "kind": "planar_face", "nearest_to": [610, 110, 10],
                       "max_results": 1}, "ok", _fg("emb_top")),
    ("sketch_create", {"plane": "EmbPlane", "name": "EmbRaise"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 605, "cy": 105, "radius": 3}],
                             "sketch_name": "EmbRaise"}, "ok", None),
    ("sketch_get", {"sketch_name": "EmbRaise"}, "ok", _prof("emb_prof_up")),
    ("model_emboss", lambda c: {"profiles": [_ctx_get(c, "emb_prof_up", "emboss profile")],
                                "faces": [_ctx_get(c, "emb_top", "emboss block top")], "depth": 2},
     lambda p: p.get("mode") == "raise" and p.get("volume_delta_cm3", 0) > 0,
     ("emb_feat", lambda p: p["feature"])),
    # the top face was re-cut by the raise, so the engrave takes a FRESH handle for it.
    ("find_geometry", {"target": "EmbossBlock", "kind": "planar_face", "nearest_to": [610, 110, 10],
                       "max_results": 1}, "ok", _fg("emb_top2")),
    ("sketch_create", {"plane": "EmbPlane", "name": "EmbCut"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 615, "cy": 115, "radius": 3}],
                             "sketch_name": "EmbCut"}, "ok", None),
    ("sketch_get", {"sketch_name": "EmbCut"}, "ok", _prof("emb_prof_down")),
    ("model_emboss", lambda c: {"profiles": [_ctx_get(c, "emb_prof_down", "engrave profile")],
                                "faces": [_ctx_get(c, "emb_top2", "emboss block top")], "depth": -2},
     lambda p: p.get("mode") == "engrave" and p.get("volume_delta_cm3", 0) < 0, None),
    ("model_emboss", lambda c: {"profiles": [_ctx_get(c, "emb_prof_up", "emboss profile")],
                                "faces": [_ctx_get(c, "emb_top2", "emboss block top")], "depth": 0},
     "refused", None),
    # model_mirror's FEATURE mode, on the emboss the beat above just made - an EmbossFeature is the
    # class MEASURED as accepted by the input collection. The mirror plane runs down the block's own
    # middle so the mirrored emboss lands back ON the block; the body/volume census is the verdict,
    # since MirrorFeature.resultFeatures.count reads None even when the mirror mints geometry.
    ("model_construction", {"kind": "plane", "plane": "yz", "offset": 610, "name": "EmbMirrorPlane"},
     _datum_plane("yz"), None),
    ("model_mirror", lambda c: {"features": [_ctx_get(c, "emb_feat", "the emboss feature")],
                                "plane": "EmbMirrorPlane"},
     lambda p: p.get("mode") == "features"
     and (p.get("bodies_added") or p.get("volume_change_cm3")), None),
    # join is a BODY-mode setting and 'joined' is read off the created feature, never echoed. The
    # body is named through a FRESH face handle: the mirrored emboss re-cut the one taken above.
    # A JOIN NEEDS THE TWO HALVES TO TOUCH, and the mirror plane is what decides whether they do.
    # About an ORIGIN plane this block's reflection lands 200 mm away with nothing between them:
    # Fusion keeps the feature, makes a second body and marks it "Could not join, multiple bodies
    # created" - a timeline WARNING left in the finished document, which the 'joined' flag alone does
    # not catch because the SETTING was honoured even though the join was not. Mirroring about the
    # block's own +X face gives the reflection that face to fuse across, and the volume the tool
    # measures for itself is what says it fused rather than landing beside it.
    ("model_construction", {"kind": "plane", "plane": "yz", "offset": 620, "name": "EmbJoinPlane"},
     _datum_plane("yz"), None),
    ("find_geometry", {"target": "EmbossBlock", "kind": "planar_face", "nearest_to": [610, 110, 10],
                       "max_results": 1}, "ok", _fg("emb_body")),
    ("model_mirror", lambda c: {"bodies": [_ctx_get(c, "emb_body", "the emboss block body")],
                                "plane": "EmbJoinPlane", "join": True},
     lambda p: p.get("joined") is True and _mirrored(p), None),
    ("model_mirror", lambda c: {"features": [_ctx_get(c, "emb_feat", "the emboss feature")],
                                "plane": "EmbMirrorPlane", "join": True}, "refused", None),
    # model_replace_face: a scratch block whose top face is replaced by an OPEN sheet sitting above
    # it. The sheet is sloped, so the body's measured volume has to move - a replace that changed
    # nothing is an error, not a quiet ok.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "ReplBlock", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "ReplS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 660, "y1": 0,
                                           "x2": 690, "y2": 30}],
                             "sketch_name": "ReplS"}, "ok", None),
    ("model_extrude", {"sketch_name": "ReplS", "profile_index": 0, "distance": 20}, _extruded, None),
    # the replacement rides its own component so one find_geometry names it without ambiguity, and
    # surface_extrude reads is_solid=false back off the result - which is what makes it a legal
    # target. Symmetric, so the sheet spans the block whichever way the extrude runs.
    ("model_create_component", {"name": "ReplRoof", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xz", "name": "ReplRoofS"}, "ok", None),
    # on the xz plane sketch +Y maps to world -Z, so y=-26 puts the sheet at world z=+26 - a FLAT
    # plane ABOVE the z0-20 block, the measured-computable replace shape (a tilted or below-the-
    # block sheet fails compute with ASM_REPL_FACE_FAILED).
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 655, "y1": -26,
                                           "x2": 695, "y2": -26}],
                             "sketch_name": "ReplRoofS"}, "ok", None),
    ("surface_extrude", {"sketch_name": "ReplRoofS", "distance": 80, "symmetric": True},
     lambda p: p.get("is_solid") is False, None),
    ("find_geometry", {"target": "ReplRoof", "kind": "planar_face", "max_results": 1}, "ok",
     _fg("repl_sheet")),
    # build the feature on the component that owns the BODY, not the one holding the sheet.
    ("design_activate_component", {"occurrence": "ReplBlock:1"}, "ok", None),
    ("find_geometry", {"target": "ReplBlock", "kind": "planar_face", "nearest_to": [675, 15, 20],
                       "max_results": 1}, "ok", _fg("repl_top")),
    # a clean parametric replace has a feature to read AND a measured volume move, so the payload
    # carries no 'effect_unverified' hedge - that key appears only when neither could be read.
    ("model_replace_face", lambda c: {"faces": [_ctx_get(c, "repl_top", "block top")],
                                      "target": _ctx_get(c, "repl_sheet", "the open roof sheet")},
     lambda p: p.get("replaced") is True and p.get("volume_delta_cm3") not in (None, 0)
     and "effect_unverified" not in p, None),
    # a SOLID face as the replacement target is refused: the target must be a surface face or body.
    ("find_geometry", {"target": "ReplBlock", "kind": "planar_face", "nearest_to": [675, 15, 0],
                       "max_results": 1}, "ok", _fg("repl_bottom")),
    ("find_geometry", {"target": "ReplBlock", "kind": "planar_face", "nearest_to": [660, 15, 10],
                       "max_results": 1}, "ok", _fg("repl_side")),
    ("model_replace_face", lambda c: {"faces": [_ctx_get(c, "repl_side", "block side")],
                                      "target": _ctx_get(c, "repl_bottom", "a solid face")},
     "refused", None),
    # model_pipe: a HOLLOW pipe on its own path (the wall is read back off the created feature),
    # then a HALF-path pipe whose bounding box proves path_fraction is a FRACTION - 20 mm of pipe on
    # a 40 mm path, not 0.5 mm - and finally the reverse extent refused on an OPEN path, which the
    # platform would otherwise swallow in silence.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "PipeRun", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xz", "name": "PipeRunPath"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 720, "y1": 0,
                                           "x2": 720, "y2": 40}],
                             "sketch_name": "PipeRunPath"}, "ok", None),
    # PipeFeature.startFaces/endFaces/sideFaces all read EMPTY on a freshly added hollow pipe, so
    # nothing on this build can say whether the ends are capped - and the payload publishes no
    # 'capped_ends' key rather than a guess dressed as a read.
    ("model_pipe", {"path": "sketch:PipeRunPath", "section_size": 10, "wall_thickness": 1.5},
     lambda p: p.get("hollow") is True and abs((p.get("wall_thickness") or 0) - 1.5) < 1e-6
     and "capped_ends" not in p, None),
    # a five-curve TANGENT stadium (line, arc, line, arc, line), each joint coincident-constrained
    # but the curves' own SketchPoints unmerged - the showcase's hoop as agents draw it. Curves
    # that merely touch by coordinate are not a path at all (Path.create raises, measured burn83);
    # constrained, the collection build takes every curve, so the pipe follows the whole 102.83 mm
    # loop and its volume is the d10 section area times that length, not the first leg.
    ("model_create_component", {"name": "PipeChain", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "PipeChainPath"}, "ok", None),
    # (x >= 900: clear of the story's stock and bracket, which the interference census walks)
    ("sketch_add_geometry", {"geometry": [
        {"kind": "line", "x1": 905, "y1": 0, "x2": 920, "y2": 0},
        {"kind": "arc", "cx": 920, "cy": 10, "x1": 920, "y1": 0, "sweep_deg": 180},
        {"kind": "line", "x1": 920, "y1": 20, "x2": 900, "y2": 20},
        {"kind": "arc", "cx": 900, "cy": 10, "x1": 900, "y1": 20, "sweep_deg": 180},
        {"kind": "line", "x1": 900, "y1": 0, "x2": 905, "y2": 0}],
                             "sketch_name": "PipeChainPath"}, "ok", None),
    ("sketch_constrain", {"constraints": [
        {"constraint": "coincident", "entity_one": "line:0:end", "entity_two": "arc:0:start"},
        {"constraint": "coincident", "entity_one": "arc:0:end", "entity_two": "line:1:start"},
        {"constraint": "coincident", "entity_one": "line:1:end", "entity_two": "arc:1:start"},
        {"constraint": "coincident", "entity_one": "arc:1:end", "entity_two": "line:2:start"},
        {"constraint": "coincident", "entity_one": "line:2:end", "entity_two": "line:0:start"}],
                          "sketch_name": "PipeChainPath"}, "ok", None),
    ("model_pipe", {"path": "sketch:PipeChainPath", "section_size": 10},
     lambda p: _measured("5-curve tangent stadium pipes the whole 102.83 mm loop at d10",
                         {"path_curves": p.get("path_curves"),
                          "path_sketch_curves": p.get("path_sketch_curves"),
                          "volume_cm3": p.get("volume_cm3")},
                         p.get("path_curves") == 5 and p.get("path_sketch_curves") == 5
                         and _near(p.get("volume_cm3"), 8.076396, 0.1)), None),
    ("model_create_component", {"name": "PipeHalf", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xz", "name": "PipeHalfPath"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 760, "y1": 0,
                                           "x2": 760, "y2": 40}],
                             "sketch_name": "PipeHalfPath"}, "ok", None),
    ("model_pipe", {"path": "sketch:PipeHalfPath", "section_size": 6, "section_type": "square",
                    "path_fraction": 0.5}, _piped, None),
    # the occurrence bounding box counts BODIES only, so the path sketch cannot inflate this read.
    ("model_inspect", {"target": "PipeHalf:1"}, lambda p: abs(p.get("z", 0) - 20.0) < 1.0, None),
    ("model_pipe", {"path": "sketch:PipeRunPath", "section_size": 6, "path_fraction": 0.5,
                    "path_fraction_reverse": 0.4}, "refused", None),
    # a CUT scoped to named bodies: participantBodies is write-only on the created feature, so the
    # scope cannot be read back - the note says the list is what was REQUESTED rather than dressing
    # an echo up as a read-back. The block is built around the path so the cut has material to take.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "PipeCut", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "PipeCutS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 800, "y1": -20,
                                           "x2": 840, "y2": 20}],
                             "sketch_name": "PipeCutS"}, "ok", None),
    ("model_extrude", {"sketch_name": "PipeCutS", "profile_index": 0, "distance": 20}, _extruded, None),
    ("sketch_create", {"plane": "xz", "name": "PipeCutPath"}, "ok", None),
    # on an xz sketch +Y maps to world -Z, so this line runs through the block at world z=10, y=0,
    # entering and leaving it - a cut that removes real material.
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 790, "y1": -10,
                                           "x2": 850, "y2": -10}],
                             "sketch_name": "PipeCutPath"}, "ok", None),
    ("model_pipe", {"path": "sketch:PipeCutPath", "section_size": 8, "operation": "cut",
                    "target_bodies": ["PipeCut"]},
     lambda p: "REQUESTED" in (p.get("note") or "") and p.get("scoped_to_bodies"), None),
    # a pipe JOIN whose path touches nothing: the tube lands as a body of its own, so the error
    # names the new orphan body and points at model_combine(join) instead of just "nothing changed".
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "PipeJoinMiss", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "PipeJoinTargetS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 1000, "y1": 0,
                                           "x2": 1020, "y2": 20}],
                             "sketch_name": "PipeJoinTargetS"}, "ok", None),
    ("model_extrude", {"sketch_name": "PipeJoinTargetS", "profile_index": 0, "distance": 10},
     _extruded, None),
    ("sketch_create", {"plane": "xy", "name": "PipeJoinMissPath"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 1050, "y1": 0,
                                           "x2": 1050, "y2": 40}],
                             "sketch_name": "PipeJoinMissPath"}, "ok", None),
    # the miss as a CUT first, scoped to the box (the component's ONE body before the join lands
    # its orphan; an unscoped miss raises NO_TARGET_SWEEP_BODY and leaves nothing - measured): the
    # feature lands with no effect, retained at WARNING severity ("No target body!") - the boundary
    # FSAE-0922-FAILED-FEATURE-SEVERITY-1 keeps apart from an ERROR, which alone breaks is_healthy.
    ("model_pipe", {"path": "sketch:PipeJoinMissPath", "section_size": 6, "operation": "cut",
                    "target_bodies": ["PipeJoinMiss"]},
     _refused("no body's volume changed", "remains in the timeline"), None),
    # then the same path as a JOIN lands an orphan tube, which the error names
    ("model_pipe", {"path": "sketch:PipeJoinMissPath", "section_size": 6, "operation": "join"},
     _refused("no body's volume changed", "operation='join' landed a NEW body (",
              "model_combine(join) merges them"), None),
    # is_healthy must stay TRUE over a retained WARNING feature - only an ERROR breaks it.
    ("assembly_get", {},
     lambda p: _measured("a retained WARNING-severity pipe feature reads healthy on assembly_get",
                         {"is_healthy": p.get("is_healthy"),
                          "timeline_problems": p.get("timeline_problems"),
                          "timeline_warnings": p.get("timeline_warnings")},
                         p.get("is_healthy") is True and p.get("timeline_problems") == []
                         and any("Pipe" in (w.get("name") or "")
                                for w in (p.get("timeline_warnings") or []))), None),
    # the same warning's own message on the timeline row reads as plain text, no markup
    ("design_get", {"include": ["timeline"], "max_results": 2000},
     lambda p: (lambda warned: _measured(
         "the retained pipe's warning message carries no markup",
         {"warned": [(r.get("name"), r.get("message")) for r in warned]},
         bool(warned) and all(r.get("message") and "<" not in r["message"] for r in warned)))(
         [r for r in ((p.get("timeline") or {}).get("timeline") or [])
          if r.get("health") == "warning" and "Pipe" in (r.get("name") or "")]), None),
    # the SAME state through workspace_orient's health counts (uncapped, unlike the timeline
    # slice's row list) - a warning, no error, is_healthy true: the severity must agree.
    ("workspace_orient", {},
     lambda p: _measured("workspace_orient counts the retained pipe as a warning, not an error",
                         {"health": p.get("health")},
                         (p.get("health") or {}).get("timeline_errors") == 0
                         and ((p.get("health") or {}).get("timeline_warnings") or 0) >= 1
                         and (p.get("health") or {}).get("is_healthy") is True), None),
    # a d70 CUT across a 100 x 30 x 8 plate: the tube is wider than the plate, so it DISCONNECTS
    # the plate into two bodies - the split is named, not left for 'result_bodies' alone to imply.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "PipeSplit", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "PipeSplitS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 1100, "y1": 0,
                                           "x2": 1200, "y2": 30}],
                             "sketch_name": "PipeSplitS"}, "ok", None),
    ("model_extrude", {"sketch_name": "PipeSplitS", "profile_index": 0, "distance": 8},
     _extruded, None),
    ("sketch_create", {"plane": "xy", "name": "PipeSplitPath"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 1150, "y1": -20,
                                           "x2": 1150, "y2": 50}],
                             "sketch_name": "PipeSplitPath"}, "ok", None),
    ("model_pipe", {"path": "sketch:PipeSplitPath", "section_size": 70, "operation": "cut",
                    "target_bodies": ["PipeSplit"]},
     lambda p: _measured("a d70 cut across a 100x30x8 plate DISCONNECTS it into 2 bodies",
                         {"body_split": p.get("body_split"), "note": (p.get("note") or "")[:200]},
                         isinstance(p.get("body_split"), list) and len(p["body_split"]) == 2
                         and "DISCONNECTED" in (p.get("note") or "")), None),
    # A parameter change that breaks a downstream feature: the split plane rides a user parameter,
    # and moving it off the box leaves the split with nothing to cut. param_set names the split
    # among the errors it newly raised; putting the value back clears it.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    # placed at x=1300 mm like AxisFrameRig, drawn at the component's own origin: the split plane's
    # offset is a parameter, which a re-packed literal sketch would leave behind.
    ("model_create_component", {"name": "ParamBreak", "activate": True, "x": 1300},
     _made_component, None),
    ("param_add", {"name": "BrkSplitX", "expression": "20 mm"},
     _param_added("BrkSplitX", 20), None),
    ("sketch_create", {"plane": "xy", "name": "ParamBreakS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 0, "y1": 0,
                                           "x2": 40, "y2": 20}],
                             "sketch_name": "ParamBreakS"}, "ok", None),
    ("model_extrude", {"sketch_name": "ParamBreakS", "profile_index": 0, "distance": 10},
     _extruded, None),
    ("model_construction", {"kind": "plane", "plane": "yz", "offset": "BrkSplitX",
                            "name": "BrkSplitPlane"}, _datum_plane("yz"), None),
    ("find_geometry", {"target": "ParamBreak", "kind": "planar_face",
                       "nearest_to": [1310, 10, 10], "max_results": 1}, "ok", _fg("brk_body")),
    ("model_split", lambda c: {"split": "body", "target": _ctx_get(c, "brk_body", "the box"),
                               "split_plane": "BrkSplitPlane"},
     _split_bodies, ("brk_split", _recall("brk_split", lambda p: p["feature"]))),
    ("param_set", {"name": "BrkSplitX", "expression": "200 mm"},
     lambda p: _param_set_to("BrkSplitX", 200)(p) and _measured(
         "param_set names the split its value broke",
         {"split": _RECALL.get("brk_split"), "new_timeline_errors": p.get("new_timeline_errors"),
          "note": p.get("note")},
         _RECALL.get("brk_split") in (p.get("new_timeline_errors") or [])), None),
    ("param_set", {"name": "BrkSplitX", "expression": "20 mm"},
     lambda p: _param_set_to("BrkSplitX", 20)(p) and _measured(
         "restoring the value raised no new error",
         {"new_timeline_errors": p.get("new_timeline_errors")},
         not p.get("new_timeline_errors")), None),
    ("assembly_get", {},
     lambda p: _measured("the split reads healthy again after the restore",
                         {"split": _RECALL.get("brk_split"),
                          "timeline_problems": p.get("timeline_problems")},
                         _RECALL.get("brk_split") not in
                         [r.get("name") for r in (p.get("timeline_problems") or [])]), None),
    # sketch_add_3d_spline: a 2-turn helix (r20 mm, pitch30 mm) as a FITTED spline pipes at d4 to
    # the analytic tube volume (pi*r_section^2*helix_length = 3.2477 cm3, measured within 0.04%);
    # the SAME helix as a CONTROL-POINT spline mints construction lines beside it (one per
    # control-polygon segment) and still pipes as ONE path curve - a pipe ignores construction geometry.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "PipeSpline", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "PipeSplineFitted"}, "ok", None),
    ("sketch_add_3d_spline", {"sketch_name": "PipeSplineFitted", "kind": "fitted",
                              "helix": {"axis": "z", "center": [2800, 0, 0], "radius": 20,
                                        "pitch": 30, "turns": 2}},
     lambda p: p.get("kind") == "fitted" and p.get("point_count") == 49
     and p.get("off_plane") is True, None),
    ("model_pipe", {"path": "sketch:PipeSplineFitted", "section_size": 4},
     lambda p: _measured("a 2-turn r20/pitch30 helix pipes at d4 to the analytic tube volume",
                         {"path_curves": p.get("path_curves"), "volume_cm3": p.get("volume_cm3")},
                         p.get("path_curves") == 1 and _near(p.get("volume_cm3"), 3.2477, 0.033)),
     None),
    ("sketch_create", {"plane": "xy", "name": "PipeSplineControl"}, "ok", None),
    ("sketch_add_3d_spline", {"sketch_name": "PipeSplineControl", "kind": "control", "degree": "3",
                              "helix": {"axis": "z", "center": [2900, 0, 0], "radius": 20,
                                        "pitch": 30, "turns": 2}},
     lambda p: p.get("kind") == "control"
     and (p.get("construction_lines_added") or 0) > 0, None),
    ("model_pipe", {"path": "sketch:PipeSplineControl", "section_size": 4},
     lambda p: p.get("path_curves") == 1, None),
    # BUILD_PATH's measured chaining rule, on two fixtures of its own. ONE seed handle is not one
    # edge: chaining follows TANGENT CONTINUITY and stops where that continuity breaks - a sharp
    # corner ends an open run, while a genuinely tangent loop chains the whole way round ([F52a],
    # and [F68] which corrected [F52b]: the earlier no-chaining reading came from a rig whose
    # junctions ran through fillet corner PATCHES, not from the loop being closed). Neither open
    # nor closed predicts the number, so the label's count is read off the BUILT path - these two
    # beats are what keep the wording honest for every consumer of the shared resolver (sweep /
    # pipe / path pattern / on-path datum).
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "TangentRun", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "TangentRunS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 1900, "y1": 0,
                                           "x2": 1960, "y2": 60}],
                             "sketch_name": "TangentRunS"}, "ok", None),
    ("model_extrude", {"sketch_name": "TangentRunS", "profile_index": 0, "distance": 20},
     _extruded, None),
    # ONE vertical edge rounded: the top rim reads line - arc - line, bounded by sharp corners.
    ("find_geometry", {"target": "TangentRun", "kind": "line_edge", "nearest_to": [1900, 0, 10],
                       "max_results": 1}, "ok", _fg("tr_corner")),
    ("model_fillet", lambda c: {"edges": [_ctx_get(c, "tr_corner", "the box corner edge")],
                                "radius": 8}, _filleted, None),
    # a fillet's rim is an ARC (Arc3D), not a full circle - find_geometry keys its edge kinds off
    # the curve type, so 'circular_edge' does not match it and 'arc_edge' is the pick.
    ("find_geometry", {"target": "TangentRun", "kind": "arc_edge", "nearest_to": [1900, 0, 20],
                       "max_results": 1}, "ok", _fg("tr_arc")),
    ("find_geometry", {"target": "TangentRun", "kind": "line_edge", "nearest_to": [1940, 0, 20],
                       "max_results": 1}, "ok", _fg("tr_line")),
    # TWO handles are used EXACTLY - no chaining at all - and the label says which of the two rules
    # ran, so a list quietly chained into more edges could not report this.
    ("find_geometry", {"target": "TangentRun", "kind": "planar_face", "nearest_to": [1930, 30, 20],
                       "max_results": 1}, "ok", _fg("tr_body")),
    ("model_pattern_path", lambda c: {"bodies": [_ctx_get(c, "tr_body", "the tangent-run body")],
                                      "path": [_ctx_get(c, "tr_arc", "the fillet arc"),
                                               _ctx_get(c, "tr_line", "the tangent-adjacent line")],
                                      "quantity": 2, "distance": 6, "distance_type": "spacing"},
     lambda p: p.get("path") == "2 edge(s) from 2 handles, used exactly", None),
    # ONE seed on the OPEN run: the arc chains across both tangent connections, so the built path
    # holds MORE than the seed.
    ("model_pipe", lambda c: {"path": _ctx_get(c, "tr_arc", "the fillet arc"), "section_size": 3},
     lambda p: _path_count(p.get("path"), 1) > 1, None),
    # the CLOSED tangent loop: all four verticals rounded, so the top rim is 4 lines + 4 arcs, every
    # junction tangent. One seed chains the WHOLE loop - all 8 edges - and the built path reports
    # itself closed. Rounding the VERTICALS is what makes the junctions tangent: rounding the top
    # edges instead puts a corner patch at each junction and the chain stops there ([F68]).
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "TangentLoop", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "TangentLoopS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 2000, "y1": 0,
                                           "x2": 2060, "y2": 60}],
                             "sketch_name": "TangentLoopS"}, "ok", None),
    ("model_extrude", {"sketch_name": "TangentLoopS", "profile_index": 0, "distance": 20},
     _extruded, None),
    # each vertical edge is the nearest line edge to its own corner at mid-height (10 mm away from
    # the two horizontals meeting there), so the four picks are unambiguous.
    ("find_geometry", {"target": "TangentLoop", "kind": "line_edge", "nearest_to": [2000, 0, 10],
                       "max_results": 1}, "ok", _fg("tl_e1")),
    ("find_geometry", {"target": "TangentLoop", "kind": "line_edge", "nearest_to": [2060, 0, 10],
                       "max_results": 1}, "ok", _fg("tl_e2")),
    ("find_geometry", {"target": "TangentLoop", "kind": "line_edge", "nearest_to": [2060, 60, 10],
                       "max_results": 1}, "ok", _fg("tl_e3")),
    ("find_geometry", {"target": "TangentLoop", "kind": "line_edge", "nearest_to": [2000, 60, 10],
                       "max_results": 1}, "ok", _fg("tl_e4")),
    ("model_fillet", lambda c: {"edges": [_ctx_get(c, "tl_e1", "loop corner 1"),
                                          _ctx_get(c, "tl_e2", "loop corner 2"),
                                          _ctx_get(c, "tl_e3", "loop corner 3"),
                                          _ctx_get(c, "tl_e4", "loop corner 4")],
                                "radius": 8}, _filleted, None),
    ("find_geometry", {"target": "TangentLoop", "kind": "arc_edge",
                       "nearest_to": [2000, 0, 20], "max_results": 1}, "ok", _fg("tl_arc")),
    ("model_pipe", lambda c: {"path": _ctx_get(c, "tl_arc", "one arc of the closed tangent loop"),
                              "section_size": 3},
     lambda p: _measured("closed tangent loop: want 8 edges from 1 seed, closed",
                         {"path": p.get("path"), "path_closed": p.get("path_closed")},
                         _path_count(p.get("path"), 1) == 8
                         and p.get("path_closed") is True), None),
    # THE SAME CLOSED RIM, now as an edge TREATMENT target: one handle on the front top line, cut
    # with tangent_chain=false. edges_cut is read off the feature's own edge set, and the rim
    # OPPOSITE is then read independently - a chain that reached it would put a 45 deg bevel face
    # centred exactly where the query looks.
    ("find_geometry", {"target": "TangentLoop", "kind": "line_edge", "nearest_to": [2030, 0, 20],
                       "max_results": 1}, _matched(1, "line_edge"), _fg("tl_rim_front")),
    ("model_chamfer", lambda c: {"edges": [_ctx_get(c, "tl_rim_front", "the front top rim line")],
                                 "distance": 1, "tangent_chain": False},
     _cut_exactly("chamfer", 1), None),
    ("find_geometry", {"target": "TangentLoop", "kind": "planar_face",
                       "nearest_to": [2030, 59.5, 19.5], "max_results": 1},
     _axis_aligned_face_at(2030, 59.5, 19.5), None),
    # and the DEFAULT on the back rim line: the seeds chain, so the feature cuts more edges than the
    # one handle it was given. The number is read off the built feature - the beat above broke the
    # rim's tangency at the front, so how far this chain reaches is not something to predict.
    ("find_geometry", {"target": "TangentLoop", "kind": "line_edge", "nearest_to": [2030, 60, 20],
                       "max_results": 1}, _matched(1, "line_edge"), _fg("tl_rim_back")),
    ("model_chamfer", lambda c: {"edges": [_ctx_get(c, "tl_rim_back", "the back top rim line")],
                                 "distance": 1}, _cut_a_chain("chamfer", 1), None),
    # A PARKED MARKER, which reading the resolved edge set has to move and put back. Rolling to the
    # previous step parks it before the chamfer above; the cut below lands at the marker, and the
    # rolled-out feature has to still be rolled out afterwards. The seed is the front BOTTOM rim,
    # which no earlier beat has touched.
    # the parked INDEX is saved off the roll's own receipt: it is where the cut below lands, and a
    # feature name cannot say that - names are component-local and the Bracket has chamfers of its
    # own carrying the same ones.
    ("design_edit_timeline", {"action": "roll", "to": "previous"},
     lambda p: _measured("one feature rolled out", {"rolled_back": p.get("rolled_back"),
                                                    "marker_position": p.get("marker_position")},
                         p.get("rolled") is True and p.get("rolled_back") == 1),
     ("parked_at", _recall("parked_at", lambda p: p["marker_position"]))),
    ("find_geometry", {"target": "TangentLoop", "kind": "line_edge", "nearest_to": [2030, 0, 0],
                       "max_results": 1}, _matched(1, "line_edge"), _fg("tl_rim_low")),
    ("model_chamfer", lambda c: {"edges": [_ctx_get(c, "tl_rim_low", "the front bottom rim line")],
                                 "distance": 1, "tangent_chain": False},
     _cut_exactly("chamfer", 1),
     ("parked_chamfer", _recall("parked_chamfer", lambda p: p["feature"]))),
    # the INDEPENDENT read: the design's own timeline, not the chamfer's receipt.
    ("design_get", {"include": ["timeline"], "max_results": 2000},
     _marker_parked_after("parked_at", "parked_chamfer"), None),
    ("design_edit_timeline", {"action": "roll", "to": "end"},
     lambda p: _measured("nothing left rolled out", {"rolled_back": p.get("rolled_back")},
                         p.get("rolled") is True and p.get("rolled_back") == 0), None),
    # THE BLANKET call, on a box of its own: every one of a cuboid's 12 edges is a sharp corner with
    # no tangent junction to chain across, so the resolved set is the swept set.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "BlanketBox", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "BlanketS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 2200, "y1": 0,
                                           "x2": 2220, "y2": 20}],
                             "sketch_name": "BlanketS"}, "ok", None),
    ("model_extrude", {"sketch_name": "BlanketS", "profile_index": 0, "distance": 10},
     _extruded, None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_chamfer", {"body_name": "BlanketBox", "edge_filter": "all", "distance": 1},
     _cut_exactly("chamfer", 12, chain=True), None),
    # FULL ROUND, on a slab of its own: one face replaced by a round tangent to the two beside it,
    # so the radius comes from the geometry and 'radius' does not drive it at all.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "FullRound", "activate": True}, _made_component, None),
    ("sketch_create", {"plane": "xy", "name": "FullRoundS"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 2100, "y1": 0,
                                           "x2": 2180, "y2": 40}],
                             "sketch_name": "FullRoundS"}, "ok", None),
    ("model_extrude", {"sketch_name": "FullRoundS", "profile_index": 0, "distance": 10},
     _extruded, None),
    ("find_geometry", {"target": "FullRound", "kind": "planar_face", "nearest_to": [2140, 0, 5],
                       "max_results": 1}, _matched(1, "planar_face"), _fg("fr_side")),
    ("find_geometry", {"target": "FullRound", "kind": "planar_face", "nearest_to": [2140, 20, 0],
                       "max_results": 1}, _matched(1, "planar_face"), _fg("fr_bottom")),
    ("find_geometry", {"target": "FullRound", "kind": "planar_face", "nearest_to": [2140, 20, 10],
                       "max_results": 1}, _matched(1, "planar_face"), _fg("fr_top")),
    ("model_fillet", lambda c: {"fillet_type": "full_round",
                                "center_face": _ctx_get(c, "fr_side", "the face to round away"),
                                "faces": [_ctx_get(c, "fr_bottom", "the slab's underside")],
                                "second_faces": [_ctx_get(c, "fr_top", "the slab's top")]},
     _full_rounded, None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    # Section lifecycle: preserve the camera, retain both generated names, remove one exact cut,
    # and independently read the surviving decoy before the existing clear-all cleanup.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    _watch("Bracket:1"),
    ("workspace_orient", {}, lambda p: bool(_section_camera(p)),
     ("section_camera_before", _recall("section_camera_before", _section_camera))),
    ("view_section", {"action": "cut", "plane": "xz", "offset": 0, "auto_view": False},
     _section_created(), ("section_one", _recall("section_one", lambda p: p["section"]))),
    ("view_section", {"action": "cut", "plane": "xy", "offset": 0, "auto_view": False},
     _section_created("section_one"),
     ("section_two", _recall("section_two", lambda p: p["section"]))),
    ("view_section", {"action": "list"},
     _section_census(("section_one", "section_two"), (False, True)), None),
    ("view_section", {"action": "clear", "section": "SweepNoSuchSection"},
     _refused("no section named", "Available"), None),
    ("view_section", {"action": "list"},
     _section_census(("section_one", "section_two"), (False, True)), None),
    ("view_section", lambda c: {"action": "clear",
                                "section": _ctx_get(c, "section_one", "the first generated cut")},
     _section_named_clear("section_one"), None),
    ("view_section", {"action": "list"},
     _section_census(("section_two",), (True,)), None),
    ("workspace_orient", {}, _section_camera_unchanged("section_camera_before"), None),
    ("view_screenshot", {"width": 500, "height": 400}, "ok", None),
    ("view_section", {"action": "clear"},
     lambda p: (p["removed"] == [_RECALL.get("section_two")]
                and p["removed_count"] == p["sections_before"] == 1
                and p["sections_after"] == 0), None),
    ("view_screenshot_multi", {"views": ["front", "top"], "width": 400, "height": 300}, "ok", None),
    # THE RASTER WRITER (NEW-13): file_path also writes the rendered PNG to disk - the extension is
    # appended, the landed file is verified non-zero, and path + size are published beside the
    # inline image. The fleet's only raster writer, which is what feeds drawing_insert_image.
    ("view_screenshot", {"width": 400, "height": 300,
                         "file_path": _SHOT_PATH},
     lambda p: "w4_shot.png" in str(p) and "size_bytes=" in str(p), None),
    # a second write to the SAME path lands without a refusal - the overwrite behaviour that makes
    # this tool write-kind (and puts it behind the write guard below).
    ("view_screenshot", {"width": 200, "height": 150,
                         "file_path": _SHOT_PATH},
     lambda p: "w4_shot.png" in str(p) and "size_bytes=" in str(p), None),
    ("view_screenshot", {"width": 200, "height": 150,
                         "file_path": _SHOT_PATH,
                         "expect_document": "ZzNoSuchDocument"},
     _refused("active_document_changed"), None),
    # The dimension/constraint beats that measure TO a model face sit at the end of the act,
    # not in the middle of the modelling: they are sketch work, and they are here only
    # because a face is what they measure against.
    # the angular wedge rule: a horizontal and a 60 deg line crossing far from the origin. The
    # measured contract dims the wedge FACING THE SKETCH ORIGIN - 60 deg, not the 120 supplement.
    ("sketch_create", {"plane": "xy", "name": "W3Dims"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 900, "y1": 100,
                                           "x2": 920, "y2": 100}],
                             "sketch_name": "W3Dims"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 905, "y1": 91.34,
                                           "x2": 915, "y2": 108.66}],
                             "sketch_name": "W3Dims"}, "ok", None),
    ("sketch_dimension", {"dimensions": [{"dim_type": "angle", "entity_one": "line:0",
                                          "entity_two": "line:1"}],
                          "sketch_name": "W3Dims"},
     lambda p: "deg" in (p["results"][0].get("value") or "")
     and abs(float((p["results"][0].get("value") or "0 x").split()[0]) - 60) < 0.1, None),
    # offset with a NON-parallel second line: the constraint ROTATES it parallel (geometry moves,
    # no raise) and the note says so.
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 940, "y1": 100,
                                           "x2": 960, "y2": 100}],
                             "sketch_name": "W3Dims"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 940, "y1": 110,
                                           "x2": 960, "y2": 113}],
                             "sketch_name": "W3Dims"}, "ok", None),
    ("sketch_dimension", {"dimensions": [{"dim_type": "offset", "entity_one": "line:2",
                                          "entity_two": "line:3"}],
                          "sketch_name": "W3Dims"},
     lambda p: "ROTAT" in (p["results"][0].get("note") or ""), None),
    # linear_diameter with the same shape REFUSES - the API's own parallelism sentence surfaces.
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 980, "y1": 100,
                                           "x2": 1000, "y2": 100}],
                             "sketch_name": "W3Dims"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 980, "y1": 110,
                                           "x2": 1000, "y2": 114}],
                             "sketch_name": "W3Dims"}, "ok", None),
    ("sketch_dimension", {"dimensions": [{"dim_type": "linear_diameter", "entity_one": "line:4",
                                          "entity_two": "line:5"}],
                          "sketch_name": "W3Dims"}, "refused", None),
    # line/point vs a MODEL face: the ShellCap outer -X wall sits on the x=400 plane, 620 mm from
    # a line at x=1020. The value is read back off the parameter; the surface label is the
    # RESOLVED entity, so 'BRepFace' proves the payload is not echoing the handle string.
    ("find_geometry", {"target": "ShellCap", "kind": "planar_face", "nearest_to": [400, 15, 10],
                       "max_results": 1}, "ok", _fg("w3_wall")),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 1020, "y1": 100,
                                           "x2": 1020, "y2": 140}],
                             "sketch_name": "W3Dims"}, "ok", None),
    ("sketch_dimension", lambda c: {"dimensions": [{
        "dim_type": "line_to_surface", "entity_one": "line:6",
        "surface": _ctx_get(c, "w3_wall", "shell wall")}],
        "sketch_name": "W3Dims"},
     lambda p: "mm" in (p["results"][0].get("value") or "")
     and abs(float((p["results"][0].get("value") or "0 x").split()[0])
             - abs(_px("W3Dims", 1020) - _px("ShellCap", 400))) < 0.1
     and p["results"][0].get("surface") == "BRepFace", None),
    # a line NOT parallel to that wall refuses with the API's self-naming error.
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 1040, "y1": 100,
                                           "x2": 1060, "y2": 100}],
                             "sketch_name": "W3Dims"}, "ok", None),
    ("sketch_dimension", lambda c: {"dimensions": [{
        "dim_type": "line_to_surface", "entity_one": "line:7",
        "surface": _ctx_get(c, "w3_wall", "shell wall")}],
        "sketch_name": "W3Dims"}, "refused", None),
    # anchored on line:7 (undimensioned - the refused line_to_surface left it free): dimensioning
    # line:6's own endpoint against the same wall it is dimensioned to over-constrains the sketch.
    ("sketch_dimension", lambda c: {"dimensions": [{
        "dim_type": "point_to_surface", "entity_one": "line:7:start",
        "surface": _ctx_get(c, "w3_wall", "shell wall")}],
        "sketch_name": "W3Dims"},
     lambda p: p["results"][0].get("surface") == "BRepFace", None),
    # shared-resolver regression: the point dim's resolver allows curved faces; the constrain
    # tool rides the same _inputs.resolve_surface, so a cylinder accepted here and refused for
    # line_on_surface pins the allow_curved split. Fresh sketch: the origin point is point:0,
    # so the drawn point is point:1.
    ("sketch_create", {"plane": "xy", "name": "W3Pt"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "point", "cx": 1080, "cy": 100}],
                             "sketch_name": "W3Pt"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 1080, "y1": 120,
                                           "x2": 1100, "y2": 120}],
                             "sketch_name": "W3Pt"}, "ok", None),
    ("sketch_constrain", lambda c: {"constraints": [{
        "constraint": "coincident_to_surface", "entity_one": "point:1",
        "surface": _ctx_get(c, "post_wall", "thread post wall")}],
        "sketch_name": "W3Pt"},
     lambda p: p["results"][0].get("surface") == "BRepFace", None),
    ("sketch_constrain", lambda c: {"constraints": [{
        "constraint": "line_on_surface", "entity_one": "line:0",
        "surface": _ctx_get(c, "post_wall", "thread post wall")}],
        "sketch_name": "W3Pt"}, "refused", None),
]

def _fillet_expression_followed(expression, mm):
    """design_get(include=['timeline'], timeline_params=True): the row whose Radius parameter is
    the EXPRESSION the fillet was built with, and the value that expression now evaluates to.

    A radius passed as a parameter name is stored as that name, so the recompute re-evaluates it -
    a radius baked to a number would read back as the number it was built at. Rows carry their
    value in internal cm, and the feature is found by its own expression rather than by a
    'Fillet<n>' name the platform picks."""
    def check(p):
        rows = (p.get("timeline") or {}).get("timeline") or []
        hit = next(((r, q) for r in rows for q in (r.get("params") or [])
                    if q.get("expression") == expression), (None, None))
        row, param = hit
        return _measured(f"the fillet built at '{expression}' now measures {mm} mm",
                         {"feature": row and row.get("name"), "param": param},
                         param is not None and _near(param.get("value"), mm / 10.0, 1e-3))
    return check


# --- ACT 6: THE RESIZE - the parametric resize check (mirrors scenario S6) ---------------------
# Bump the one driving length; the whole bracket grows. It runs BEFORE the billet and the vise are
# built, which is the order a shop works in: the part is settled, then the stock is sized from it
# and the jaws close on that.
_RESIZE = [
    # the resize walks the whole part - frame it so the features are seen to move.
    _watch("Bracket:1"),
    ("view_screenshot", {"width": 400, "height": 300}, "ok", None),
    ("sketch_get", {"sketch_name": "BracketBody"}, "ok", None),   # before
    ("param_set", {"name": "PartLen", "expression": "160 mm"},
     _param_set_to("PartLen", 160), None),
    # 'new_errors' names the features that came back broken from THIS rebuild (the walk before it is
    # what makes that a difference) - a resize that breaks a downstream feature returns ok.
    ("design_recompute", {},
     lambda p: (p["recomputed"] is True and isinstance(p["error_count"], int)
                and "new_errors" not in p), None),
    ("sketch_get", {"sketch_name": "BracketBody"}, "ok", None),   # after - the block grew
    ("sketch_get", {"sketch_name": "BracketPocket"}, "ok", None),
    # THE MEASURED PROOF, on all three axes: the driver is the part's LENGTH, so x follows it a
    # third longer while the width and the height - their own parameters - hold exactly where they
    # were. A resize that moved every axis is a sketch anchored on the wrong point, and only
    # reading the two that must NOT move says so.
    ("model_inspect", {"target": "Bracket:1"},
     lambda p: _measured("only the length followed the driver (want x 160, y 80, z 45)",
                         {"x": p.get("x"), "y": p.get("y"), "z": p.get("z")},
                         _near(p.get("x"), 160.0, 0.1) and _near(p.get("y"), 80.0, 0.1)
                         and _near(p.get("z"), 45.0, 0.1)), None),
    # ...and the FEATURE side of the same recompute: the pocket's corner fillet was built at the
    # expression 'PocketRad', so the timeline row holds that name and the value it evaluates to now
    # (PartLen/15 at the driven 160 mm), not the 8 mm the feature was created at.
    ("design_get", {"include": ["timeline"], "timeline_params": True},
     _fillet_expression_followed("PocketRad", 160.0 / 15.0), None),
    # the StockCenter JO (the CAM WCS anchor) read back after the resize: parametrically anchored at
    # the part's own origin, it HOLDS position through the recompute.
    ("assembly_get", {"include": ["joint_origins"]}, _joint_origins_listed("StockCenter"), None),
    ("view_screenshot", {"width": 400, "height": 300}, "ok", None),
    ("param_set", {"name": "PartLen", "expression": "120 mm"},
     _param_set_to("PartLen", 120), None),   # restore
    ("design_recompute", {}, "ok", None),
    ("sketch_get", {"sketch_name": "BracketBody"}, "ok", None),   # restored
    ("param_add", {"name": "ScratchDim", "expression": "5 mm"}, _param_added("ScratchDim", 5), None),
    ("param_delete", {"name": "ScratchDim"}, _param_deleted("ScratchDim"), None),
    # the design at rest after the rebuild: the census the check ran, with the rows it found.
    ("assembly_inspect_interference", {}, _interference_measured, None),
    # FSAE-0922-INTERFERENCE-INSTANCE-1: a component instanced twice must be named EXACTLY, never
    # guessed from candidates - and two occurrences with no body must refuse, never pass. Isolated
    # in its own scratch document so the census is exactly what this rig places.
    ("doc_get", {}, _home_document,
     ("interference_story", _recall("interference_story", _home_address))),
    ("doc_new",
     lambda c: {"expect_document": _ctx_get(c, "interference_story", "the story document")},
     _new_document,
     ("interference_scratch", _recall("interference_scratch", lambda p: p["document_handle"]))),
    ("model_create_component",
     lambda c: _interference_pin(c, {"name": "EmptyA", "activate": True}), _made_component, None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "root"}), "ok", None),
    ("model_create_component",
     lambda c: _interference_pin(c, {"name": "EmptyB", "activate": True}), _made_component, None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "root"}), "ok", None),
    # two occurrences with ZERO solid bodies between them - the false pass this row exists to catch.
    ("assembly_inspect_interference", {}, _refused("EmptyA:1", "EmptyB:1", "NOT a pass"), None),
    ("model_create_component",
     lambda c: _interference_pin(c, {"name": "BlockA", "activate": True}), _made_component, None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "BlockAS"}), "ok", None),
    ("sketch_add_geometry",
     lambda c: _interference_pin(c, {"geometry": [{"kind": "rectangle", "x1": 0, "y1": 0,
                                                    "x2": 10, "y2": 10}], "sketch_name": "BlockAS"}),
     "ok", None),
    ("model_extrude",
     lambda c: _interference_pin(c, {"sketch_name": "BlockAS", "profile_index": 0, "distance": 10}),
     _extruded, None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "root"}), "ok", None),
    ("model_create_component",
     lambda c: _interference_pin(c, {"name": "BlockB", "activate": True, "x": 50}),
     _made_component, None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "BlockBS"}), "ok", None),
    ("sketch_add_geometry",
     lambda c: _interference_pin(c, {"geometry": [{"kind": "rectangle", "x1": 0, "y1": 0,
                                                    "x2": 10, "y2": 10}], "sketch_name": "BlockBS"}),
     "ok", None),
    ("model_extrude",
     lambda c: _interference_pin(c, {"sketch_name": "BlockBS", "profile_index": 0, "distance": 10}),
     _extruded, None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "root"}), "ok", None),
    ("assembly_get", {"include": ["poses"]}, _separated_block_poses, None),
    ("assembly_inspect_interference", {}, _separated_interference(False), None),
    ("assembly_inspect_interference", {"include_coincident_faces": True},
     _separated_interference(True), None),
    ("model_create_component",
     lambda c: _interference_pin(c, {"name": "Peg", "activate": True}), _made_component, None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "PegS"}), "ok", None),
    ("sketch_add_geometry",
     lambda c: _interference_pin(c, {"geometry": [{"kind": "circle", "cx": 5, "cy": 5, "radius": 2}],
                                     "sketch_name": "PegS"}), "ok", None),
    ("model_extrude",
     lambda c: _interference_pin(c, {"sketch_name": "PegS", "profile_index": 0, "distance": 10}),
     _extruded, None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "root"}), "ok", None),
    # a second instance of the SAME component, overlapping the OTHER block - the multi-instance case
    # analyzeInterference alone cannot name (native bodies carry no assemblyContext).
    ("design_add_instance",
     lambda c: _interference_pin(c, {"component": "Peg", "x": 50}),
     lambda p: p.get("created") is True, None),
    ("assembly_inspect_interference", {}, _interference_pair_named, None),
    ("find_geometry", {"target": "Peg", "kind": "cylinder_face"}, _peg_faces_per_instance, None),
    ("model_create_component",
     lambda c: _interference_pin(c, {"name": "OverlapPart", "activate": True, "x": 200}),
     _made_component, None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "OverlapCubeA"}), "ok", None),
    ("sketch_add_geometry",
     lambda c: _interference_pin(c, {"sketch_name": "OverlapCubeA", "geometry": [
         {"kind": "rectangle", "x1": 0, "y1": 0, "x2": 20, "y2": 20}]}), "ok", None),
    ("model_extrude",
     lambda c: _interference_pin(c, {"sketch_name": "OverlapCubeA", "profile_index": 0,
                                     "distance": 20}), _extruded, None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "root"}), "ok", None),
    ("design_add_instance",
     lambda c: _interference_pin(c, {"component": "OverlapPart", "x": 210}),
     lambda p: p.get("created") is True, None),
    ("assembly_get", {"include": ["poses"]}, _shared_cube_poses(1), None),
    ("assembly_inspect_interference", {}, _shared_cube_overlap(4.0, 3, 12), None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "OverlapPart:1"}), "ok", None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "OverlapCubeB"}), "ok", None),
    ("sketch_add_geometry",
     lambda c: _interference_pin(c, {"sketch_name": "OverlapCubeB", "geometry": [
         {"kind": "rectangle", "x1": 50, "y1": 0, "x2": 70, "y2": 20}]}), "ok", None),
    ("model_extrude",
     lambda c: _interference_pin(c, {"sketch_name": "OverlapCubeB", "profile_index": 0,
                                     "distance": 20}), _extruded, None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "root"}), "ok", None),
    ("assembly_get", {"include": ["poses"]}, _shared_cube_poses(2), None),
    ("assembly_inspect_interference", {}, _shared_cube_overlap(8.0, 4, 24), None),
    ("model_create_component",
     lambda c: _interference_pin(c, {"name": "ContactPart", "activate": True, "x": 400}),
     _made_component, None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "ContactLeft"}), "ok", None),
    ("sketch_add_geometry",
     lambda c: _interference_pin(c, {"sketch_name": "ContactLeft", "geometry": [
         {"kind": "rectangle", "x1": 0, "y1": 0, "x2": 20, "y2": 20}]}), "ok", None),
    ("model_extrude",
     lambda c: _interference_pin(c, {"sketch_name": "ContactLeft", "distance": 20,
                                     "operation": "new"}), _extruded, None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "ContactRight"}), "ok", None),
    ("sketch_add_geometry",
     lambda c: _interference_pin(c, {"sketch_name": "ContactRight", "geometry": [
         {"kind": "rectangle", "x1": 20, "y1": 0, "x2": 40, "y2": 20}]}), "ok", None),
    ("model_extrude",
     lambda c: _interference_pin(c, {"sketch_name": "ContactRight", "distance": 20,
                                     "operation": "new"}), _extruded, None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "root"}), "ok", None),
    ("assembly_get", {"include": ["poses"]}, _contact_part_poses(2), None),
    ("assembly_inspect_interference", {}, _contact_overlap([]), None),
    ("assembly_inspect_interference", {"include_coincident_faces": True}, _contact_overlap([0.0]), None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "ContactPart:1"}), "ok", None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "ContactMiddle"}), "ok", None),
    ("sketch_add_geometry",
     lambda c: _interference_pin(c, {"sketch_name": "ContactMiddle", "geometry": [
         {"kind": "rectangle", "x1": 10, "y1": 0, "x2": 30, "y2": 20}]}), "ok", None),
    ("model_extrude",
     lambda c: _interference_pin(c, {"sketch_name": "ContactMiddle", "distance": 20,
                                     "operation": "new"}), _extruded, None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "root"}), "ok", None),
    ("assembly_get", {"include": ["poses"]}, _contact_part_poses(3), None),
    ("assembly_inspect_interference", {}, _contact_overlap([8.0]), None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "ContactAlias"}), "ok", None),
    ("sketch_add_geometry",
     lambda c: _interference_pin(c, {"sketch_name": "ContactAlias", "geometry": [
         {"kind": "rectangle", "x1": 400, "y1": 0, "x2": 420, "y2": 20}]}), "ok", None),
    ("model_extrude",
     lambda c: _interference_pin(c, {"sketch_name": "ContactAlias", "distance": 20,
                                     "operation": "new"}), _extruded, None),
    ("design_get", {"include": ["tree"], "max_depth": 1, "tree_bodies": True, "tree_handles": True},
     lambda p: len(p["tree"]["root_bodies"]) == 1
     and bool(p["tree"]["root_bodies"][0].get("handle")),
     ("contact_alias", _recall("contact_alias", lambda p: p["tree"]["root_bodies"][0]["handle"]))),
    ("design_set_name",
     lambda c: _interference_pin(c, {"target": _ctx_get(c, "contact_alias", "the sole root body"),
                                     "new_name": "ContactPart:1"}),
     lambda p: p.get("name") == "ContactPart:1" and p.get("kind") == "body", None),
    ("model_inspect", lambda c: {"target": _ctx_get(c, "contact_alias", "the colliding-label body")},
     lambda p: _near(p.get("x"), 20, 0.001) and _near(p.get("y"), 20, 0.001)
     and _near(p.get("z"), 20, 0.001), None),
    ("assembly_inspect_interference", {}, _contact_overlap([8.0, 12.0]), None),
    ("model_create_component",
     lambda c: _interference_pin(c, {"name": "BudgetPart", "activate": True, "x": 600}),
     _made_component, None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "BudgetCube"}), "ok", None),
    ("sketch_add_geometry",
     lambda c: _interference_pin(c, {"sketch_name": "BudgetCube", "geometry": [
         {"kind": "rectangle", "x1": 0, "y1": 0, "x2": 20, "y2": 20}]}), "ok", None),
    ("model_extrude",
     lambda c: _interference_pin(c, {"sketch_name": "BudgetCube", "distance": 20}),
     _extruded, None),
    ("model_pattern_rectangular",
     lambda c: _interference_pin(c, {"bodies": ["BudgetPart"], "direction_one": "x",
                                     "quantity_one": 102, "spacing_one": 0.1}),
     _patterned("total_instances", 102), None),
    ("design_activate_component",
     lambda c: _interference_pin(c, {"occurrence": "root"}), "ok", None),
    ("assembly_get", {"include": ["poses"]},
     lambda p: _measured("102 overlapping cubes, each shifted 0.1 mm",
                         {"rows": [r for r in p.get("occurrences", [])
                                   if r.get("name") == "BudgetPart:1"]},
                         any(r.get("name") == "BudgetPart:1" and r.get("body_count") == 102
                             and len(r.get("bbox_size", [])) == 3
                             and all(_near(a, b, 0.005) for a, b in
                                     zip(r["bbox_size"], [30.1, 20, 20]))
                             for r in p.get("occurrences", []))), None),
    ("assembly_inspect_interference", {}, _interference_budget, None),
    ("model_create_component",
     lambda c: _interference_pin(c, {"name": "HelixCheck", "activate": True}),
     _made_component, None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "FractionalHelix"}), "ok", None),
    ("sketch_add_3d_spline",
     lambda c: _interference_pin(c, {"sketch_name": "FractionalHelix", "helix": {
         "axis": "z", "center": [0, 0, 100], "radius": 10, "pitch": 10,
         "turns": 1.1, "points_per_turn": 24}}),
     lambda p: p.get("kind") == "fitted" and p.get("is_valid") is True, None),
    ("model_pipe",
     lambda c: _interference_pin(c, {"path": "sketch:FractionalHelix", "section_size": 1}),
     lambda p: p.get("path_curves") == 1, None),
    ("find_geometry", {"target": "HelixCheck:1", "kind": "planar_face", "max_results": 2},
     _fractional_helix_cap, None),
    ("sketch_create",
     lambda c: _interference_pin(c, {"plane": "xy", "name": "ShortHelix"}), "ok", None),
    ("sketch_add_3d_spline",
     lambda c: _interference_pin(c, {"sketch_name": "ShortHelix", "helix": {
         "axis": "z", "center": [0, 0, 120], "radius": 10, "pitch": 10,
         "turns": 0.1, "points_per_turn": 6}}),
     lambda p: p.get("kind") == "fitted" and p.get("is_valid") is True
     and p.get("point_count") == 3, None),
    ("model_pipe",
     lambda c: _interference_pin(c, {"path": "sketch:ShortHelix", "section_size": 1}),
     lambda p: p.get("path_curves") == 1, None),
    ("find_geometry", {"target": "HelixCheck:1", "kind": "planar_face",
                       "nearest_to": [8.09017, 5.87785, 121], "max_results": 1},
     lambda p: _fractional_helix_cap(p, turns=0.1, start_z=120), None),
    ("doc_activate",
     lambda c: {"name": _ctx_get(c, "interference_story", "the story document"),
                "expect_document": _ctx_get(c, "interference_scratch",
                                            "the interference scratch document")},
     "ok", None),
    ("doc_close",
     lambda c: {"name": _ctx_get(c, "interference_scratch", "the interference scratch document"),
                "save_changes": False,
                "expect_document": _ctx_get(c, "interference_story", "the story document")},
     _document_closed, None),
    # TIMELINE: roll back over the assembly, group a range, suppress and restore, then return the
    # marker to the end. Every beat reads the marker back, and the blast-radius refusal is exercised
    # WITHOUT the confirmation so nothing is discarded from the story.
    ("design_edit_timeline", {"action": "roll", "to": "previous"},
     lambda p: p.get("marker_position") == p.get("marker_position_before", -1) - 1, None),
    ("design_edit_timeline", {"action": "delete_after_marker"}, "refused", None),
    ("design_edit_timeline", {"action": "roll", "to": "end"},
     lambda p: p.get("rolled_back") == 0, None),
    ("design_edit_timeline", {"action": "roll", "feature": "NoSuchFeature"}, "refused", None),
    ("design_edit_timeline", {"action": "group", "feature": "ScratchDim",
                              "end_feature": "ScratchDim"}, "refused", None),
    # ATTRIBUTES: tag a real timeline feature (the part's own step floor), re-tag it,
    # then remove the tag. An attribute reached through the timeline lives on the ENTITY the item
    # wraps, and every beat reads back both the value on that entity and the design-wide census of
    # the group/name pair - which is what turns the delete into a verdict instead of a claim.
    ("design_edit_timeline", {"action": "set_attribute", "feature": "StepFloor",
                              "attribute_group": "sweep_w11_8", "attribute_name": "note",
                              "attribute_value": "beat-1"},
     lambda p: p.get("value") == "beat-1" and p.get("design_matches", 0) >= 1
     and "previous_value" not in p, None),
    # add() on an existing group/name UPDATES in place, so the value it replaced is readable only
    # before the call - and it is disclosed rather than lost.
    ("design_edit_timeline", {"action": "set_attribute", "feature": "StepFloor",
                              "attribute_group": "sweep_w11_8", "attribute_name": "note",
                              "attribute_value": "beat-2"},
     lambda p: p.get("previous_value") == "beat-1" and p.get("value") == "beat-2", None),
    # this tool's own wire bound on the value, refused with the length that broke it.
    ("design_edit_timeline", {"action": "set_attribute", "feature": "StepFloor",
                              "attribute_group": "sweep_w11_8", "attribute_name": "note",
                              "attribute_value": "x" * 10001}, "refused", None),
    # a leading 're:' turns the attribute search into a REGULAR EXPRESSION instead of naming this
    # literal group, so it is refused rather than silently matching something else.
    ("design_edit_timeline", {"action": "set_attribute", "feature": "StepFloor",
                              "attribute_group": "re:sweep", "attribute_name": "note",
                              "attribute_value": "beat-3"}, "refused", None),
    ("design_edit_timeline", {"action": "delete_attribute", "feature": "StepFloor",
                              "attribute_group": "sweep_w11_8", "attribute_name": "note"},
     lambda p: p.get("attribute_deleted") is True and p.get("deleted_value") == "beat-2"
     and p.get("design_matches") == 0, None),
    # the same delete again has nothing to remove, and says so naming the group/name pair.
    ("design_edit_timeline", {"action": "delete_attribute", "feature": "StepFloor",
                              "attribute_group": "sweep_w11_8", "attribute_name": "note"},
     "refused", None),
    # THE 'name@index' FORM - a valid address in its own right, resolved by reading each timeline
    # object's OWN .index - the same number design_get publishes - never by position in a list, so
    # the index taken from this read is the index that must resolve.
    # the slice is a DICT (marker_position / count / summary / groups / timeline) and the ordered
    # rows sit under its own 'timeline' key - each a terse {index, name, type}.
    ("design_get", {"include": ["timeline"]},
     lambda p: any(r.get("name") == "StepFloor" for r in p["timeline"]["timeline"]),
     ("hub_index", lambda p: next(r["index"] for r in p["timeline"]["timeline"]
                                  if r["name"] == "StepFloor"))),
    ("design_edit_timeline", lambda c: {
        "action": "set_attribute",
        "feature": "StepFloor@{0}".format(_ctx_get(c, "hub_index", "the step floor's index")),
        "attribute_group": "sweep_w1d", "attribute_name": "at", "attribute_value": "by-index"},
     lambda p: p.get("value") == "by-index" and p.get("feature") == "StepFloor", None),
    ("design_edit_timeline", lambda c: {
        "action": "delete_attribute",
        "feature": "StepFloor@{0}".format(_ctx_get(c, "hub_index", "the step floor's index")),
        "attribute_group": "sweep_w1d", "attribute_name": "at"},
     lambda p: p.get("attribute_deleted") is True, None),
    # the NEIGHBOURING index: the pair must agree, so an off-by-one is refused - and the refusal
    # says what sits at the index asked for and which index 'StepFloor' answers to now, rather than
    # editing the feature next door.
    ("design_edit_timeline", lambda c: {
        "action": "set_attribute",
        "feature": "StepFloor@{0}".format(_ctx_get(c, "hub_index",
                                                         "the step floor's index") + 1),
        "attribute_group": "sweep_w1d", "attribute_name": "at", "attribute_value": "x"},
     _refused("'StepFloor' is at index", "design_get(include=['timeline'])"), None),
    # THE '<component>/<name>' FORM: two components each hold a plane named 'AddrPlane', so the bare
    # name is refused naming BOTH qualified candidates; the qualified form deletes the right one, and
    # the bare name resolving alone afterwards is the independent proof it was the right one that went.
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "AddrCompA", "activate": True}, _made_component, None),
    ("model_construction", {"kind": "plane", "plane": "xy", "offset": 5, "name": "AddrPlane"},
     _datum_plane("xy"), None),
    ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ("model_create_component", {"name": "AddrCompB", "activate": True}, _made_component, None),
    ("model_construction", {"kind": "plane", "plane": "xy", "offset": 5, "name": "AddrPlane"},
     _datum_plane("xy"), None),
    # the two same-named planes each own an offset parameter: a row resolved by name hands one
    # plane's parameters to the other.
    ("design_get", {"include": ["timeline"], "timeline_params": True, "max_results": 5000},
     _addr_planes_own_their_params, None),
    ("design_delete_feature", {"feature": "AddrPlane"},
     _refused("AddrCompA/AddrPlane", "AddrCompB/AddrPlane", "matches 2 timeline objects"), None),
    ("design_delete_feature", {"feature": "AddrCompA/AddrPlane"},
     lambda p: p["deleted"] is True and p["feature"] == "AddrPlane", None),
    ("design_delete_feature", {"feature": "AddrPlane"},
     lambda p: p["deleted"] is True and p["feature"] == "AddrPlane", None),
]

# --- the retained SCRATCH fixtures - the precondition fallbacks (today's proven step bodies) ---
# When an act's precondition read fails (an upstream act could not build the geometry it consumes),
# the act runs one of these instead, so its tools are still covered - each row marked "(fallback
# fixture)". These are the minimal self-contained scratch fixtures the sweep has always used.

_SOLIDS_FB = (
    _box("FbSolid")
    + [
        ("find_geometry", {"target": "FbSolid", "kind": "planar_face", "nearest_to": [10, 10, 10], "max_results": 1}, "ok", _fg("fb_body")),
        ("appearance_set", {"target": "FbSolid", "color": "#1E8E3E"}, "ok", None),
        ("model_set_material", {"target": "FbSolid", "material": "Steel"}, _material_assigned, None),
        ("model_mirror", lambda c: {"bodies": [_ctx_get(c, "fb_body", "body handle")], "plane": "yz"}, _mirrored, None),
        ("model_pattern_rectangular", lambda c: {"bodies": [_ctx_get(c, "fb_body", "body handle")], "quantity_one": 2, "spacing_one": 60, "direction_one": "y"}, _patterned("total_instances", 2), None),
        ("model_pattern_circular", lambda c: {"bodies": [_ctx_get(c, "fb_body", "body handle")], "quantity": 3, "total_angle_deg": 360, "axis": "z"}, _patterned("quantity", 3), None),
        ("find_geometry", {"target": "FbSolid", "kind": "planar_face", "nearest_to": [10, 10, 10], "max_results": 1}, "ok", _fg("fb_top")),
        ("model_hole", lambda c: {"face": _ctx_get(c, "fb_top", "top face"), "hole_type": "simple", "diameter": "4 mm", "extent": "blind", "depth": "8 mm", "points": [[5, 5, 0]]}, _drilled(1), None),
        ("find_geometry", {"target": "FbSolid", "kind": "planar_face", "nearest_to": [0, 10, 5], "max_results": 1}, "ok", _fg("fb_side")),
        ("model_draft", lambda c: {"faces": [_ctx_get(c, "fb_side", "side face")], "pull_direction": "xy", "angle_deg": 3},
         _drafted, None),
        ("model_measure_between", lambda c: {"a": _ctx_get(c, "fb_body", "body"), "b": "FbSolid"}, _gap_measured, None),
        # a face compared with ITSELF is parallel to itself, so this beat asserts the verdict too.
        ("model_measure_relation", lambda c: {"relation": "parallel", "entity_a": _ctx_get(c, "fb_top", "top face"), "entity_b": _ctx_get(c, "fb_top", "top face")}, _relation_passes("parallel"), None),
        ("model_inspect", {"target": "FbSolid"}, _extent_measured, None),
        ("model_create_component", {"name": "FbRev", "activate": True}, _made_component, None),
        ("sketch_create", {"plane": "xz", "name": "FbRevS"}, "ok", None),
        ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 10, "y1": 0,
                                               "x2": 20, "y2": 30}],
                                 "sketch_name": "FbRevS"}, "ok", None),
        ("model_revolve", {"sketch_name": "FbRevS", "profile_index": 0, "axis": "z", "angle_deg": 360}, _revolved, None),
        ("model_create_component", {"name": "FbSwp", "activate": True}, _made_component, None),
        ("sketch_create", {"plane": "xz", "name": "FbPath"}, "ok", None),
        ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 0, "y1": 0,
                                               "x2": 0, "y2": 40}],
                                 "sketch_name": "FbPath"}, "ok", None),
        ("sketch_create", {"plane": "xy", "name": "FbProf"}, "ok", None),
        ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 0, "cy": 0, "radius": 5}],
                                 "sketch_name": "FbProf"}, "ok", None),
        ("model_sweep", {"profile": {"sketch": "FbProf", "profile_index": 0}, "path": "sketch:FbPath"}, _swept, None),
        ("model_create_component", {"name": "FbLft", "activate": True}, _made_component, None),
        ("sketch_create", {"plane": "xy", "name": "FbLb"}, "ok", None),
        ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 0, "cy": 0, "radius": 10}],
                                 "sketch_name": "FbLb"}, "ok", None),
        ("sketch_get", {"sketch_name": "FbLb"}, "ok", _prof("fb_lb")),
        ("model_construction", {"kind": "plane", "plane": "xy", "offset": 40, "name": "FbTop"},
         _datum_plane("xy"), None),
        ("sketch_create", {"plane": "FbTop", "name": "FbLt"}, "ok", None),
        ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 0, "cy": 0, "radius": 5}],
                                 "sketch_name": "FbLt"}, "ok", None),
        ("sketch_get", {"sketch_name": "FbLt"}, "ok", _prof("fb_lt")),
        ("model_loft", lambda c: {"profiles": [_ctx_get(c, "fb_lb", "loft bottom"), _ctx_get(c, "fb_lt", "loft top")]}, _lofted, None),
        ("model_create_component", {"name": "FbCmb", "activate": True}, _made_component, None),
        ("sketch_create", {"plane": "xy", "name": "FbCb1"}, "ok", None),
        ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 0, "y1": 0,
                                               "x2": 30, "y2": 30}],
                                 "sketch_name": "FbCb1"}, "ok", None),
        ("model_extrude", {"sketch_name": "FbCb1", "profile_index": 0, "distance": 10}, _extruded, None),
        ("sketch_create", {"plane": "xy", "name": "FbCb2"}, "ok", None),
        ("sketch_add_geometry", {"geometry": [{"kind": "rectangle", "x1": 20, "y1": 20,
                                               "x2": 50, "y2": 50}],
                                 "sketch_name": "FbCb2"}, "ok", None),
        ("model_extrude", {"sketch_name": "FbCb2", "profile_index": 0, "distance": 10}, _extruded, None),
        ("find_geometry", {"target": "FbCmb", "kind": "planar_face", "nearest_to": [5, 5, 10], "max_results": 1}, "ok", _fg("fb_c1")),
        ("find_geometry", {"target": "FbCmb", "kind": "planar_face", "nearest_to": [45, 45, 10], "max_results": 1}, "ok", _fg("fb_c2")),
        ("model_combine", lambda c: {"target": _ctx_get(c, "fb_c1", "combine target"), "tools": [_ctx_get(c, "fb_c2", "combine tool")], "operation": "join"}, _joined, None),
        ("design_activate_component", {"occurrence": "root"}, "ok", None),
        # the WCS anchor by the name the CAM acts bind to, so a fallback world still carries one.
        ("joint_create_origin", {"anchor": "coordinates", "target": "origin",
                                 "name": "StockCenter"},
         _joint_origin_at("StockCenter", 0, 0, 0), None),
    ]
)

# ACT 4 fallback: a scratch details fixture.
_DETAILS_FB = (
    _box("FbDet")
    + [
        ("find_geometry", {"target": "FbDet", "kind": "line_edge", "max_results": 1}, "ok", _fg("fd_edge")),
        ("model_fillet", lambda c: {"edges": [_ctx_get(c, "fd_edge", "edge")], "radius": 1}, _filleted, None),
        ("find_geometry", {"target": "FbDet", "kind": "line_edge", "max_results": 1}, "ok", _fg("fd_edge2")),
        ("model_chamfer", lambda c: {"edges": [_ctx_get(c, "fd_edge2", "edge")], "distance": 0.5}, _chamfered, None),
        ("find_geometry", {"target": "FbDet", "kind": "planar_face", "nearest_to": [10, 10, 10], "max_results": 1}, "ok", _fg("fd_top")),
        ("model_shell", lambda c: {"body_name": "FbDet", "remove_faces": [_ctx_get(c, "fd_top", "top")], "thickness": 2}, _shelled, None),
        ("model_construction", {"kind": "plane", "plane": "xy", "offset": 5, "name": "FbWart"},
         _datum_plane("xy"), None),
        ("design_delete_feature", {"feature": "FbWart"},
         lambda p: (p["deleted"] is True and p["feature"] == "FbWart"
                    and "timeline_warning" not in p), None),
        ("model_create_component", {"name": "FbJunk", "activate": False}, _made_component_inactive, None),
        ("design_delete_occurrence", {"occurrence": "FbJunk:1"},
         lambda p: (p["deleted"] is True and p["occurrence"] == "FbJunk:1"
                    and "timeline_warning" not in p), None),
        ("design_activate_component", {"occurrence": "root"}, "ok", None),
        ("view_section", {"action": "cut", "plane": "xy", "offset": 5,
                          "auto_view": False},
         _section_created(),
         ("fb_section_one", _recall("fb_section_one", lambda p: p["section"]))),
        ("view_section", {"action": "cut", "plane": "yz", "offset": 5,
                          "auto_view": False},
         _section_created("fb_section_one"),
         ("fb_section_two", _recall("fb_section_two", lambda p: p["section"]))),
        ("view_section", {"action": "list"},
         _section_census(("fb_section_one", "fb_section_two"), (False, True)), None),
        ("view_section", lambda c: {"action": "clear",
                                    "section": _ctx_get(c, "fb_section_one",
                                                        "the first fallback section")},
         _section_named_clear("fb_section_one"), None),
        ("view_section", {"action": "list"},
         _section_census(("fb_section_two",), (True,)), None),
        ("view_screenshot", {"width": 400, "height": 300}, "ok", None),
        ("view_section", {"action": "clear"},
         lambda p: (p["removed"] == [_RECALL.get("fb_section_two")]
                    and p["removed_count"] == p["sections_before"] == 1
                    and p["sections_after"] == 0), None),
        ("view_screenshot_multi", {"views": ["front", "top"], "width": 300, "height": 250}, "ok", None),
    ]
)

# ACT 6 fallback: a scratch parameter set/delete.
_RESIZE_FB = [
    ("param_add", {"name": "FbParam", "expression": "12 mm"}, _param_added("FbParam", 12), None),
    ("param_set", {"name": "FbParam", "expression": "14 mm"}, _param_set_to("FbParam", 14), None),
    ("design_recompute", {},
     lambda p: (p["recomputed"] is True and isinstance(p["error_count"], int)
                and "new_errors" not in p), None),
    ("param_delete", {"name": "FbParam"}, _param_deleted("FbParam"), None),
]
