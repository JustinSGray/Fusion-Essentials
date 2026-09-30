# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Sweep and loft editing checks for model acts."""

import math

from verify_core import (
    _RECALL, _ctx_get, _datum_plane, _document_closed, _extruded, _fg, _home_address, _home_document, _lofted, _made_component, _measured, _near, _num, _new_document, _prof, _recall, _refused, _swept, _watch)





from verify_acts_model_combine_revolve import (
    _combine_body, _combine_inspect, _combine_pin)

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


def _solid_tool_expected(case, role):
    """Return analytic world bounds and volume in millimeters for the owned tool sweep."""
    angle = math.radians(25)
    co, si = math.cos(angle), math.sin(angle)
    x, y = 3200, 500
    if role == "source":
        half = 2.5 * (co + si)
        lo, hi, volume = (x - half, y - half, 0), (x + half, y + half, 5), 125
    else:
        lo = (x - 2.5 * (co + si), y - 2.5 * (co + si), 0)
        hi = (x + 22.5 * co + 2.5 * si, y + 22.5 * si + 2.5 * co, 5)
        volume = 625
    return {"min": dict(zip(("x", "y", "z"), lo)),
            "max": dict(zip(("x", "y", "z"), hi)), "volume": volume}


def _solid_tool_mass(case, role, previous=None):
    """Check measured volume and placed bounds against the tool sweep geometry."""
    def check(p):
        got, expected = _sweep_mode_shape(p), _solid_tool_expected(case, role)
        old = _RECALL.get(previous) if previous else None
        valid = (p.get("kind") == "body" and p.get("units") == "mm"
                 and _near(got["volume"], expected["volume"], 1.0)
                 and _sweep_mode_box_equal(got, expected, 0.3)
                 and (previous is None or got == old))
        return _measured(f"{case} solid tool {role} independent volume and world bounds",
                         {"actual": got, "expected": expected, "before": old}, valid)
    return check


def _solid_tool_census(p):
    """Return the owner's body identities and every SweepFeature row's (name, health), or None on an unreadable or truncated read."""
    bodies = ((p.get("tree") or {}).get("tree") or {}).get("bodies")
    timeline = (p.get("timeline") or {}).get("timeline")
    if (not isinstance(bodies, list) or not isinstance(timeline, list)
            or (p.get("timeline") or {}).get("truncated")):
        return None
    return {"bodies": sorted((b.get("name"), b.get("handle")) for b in bodies),
            "sweeps": sorted((r.get("name"), r.get("health")) for r in timeline
                             if r.get("type") == "SweepFeature")}


def _solid_tool_health(host, key):
    """Check the new sweep's own timeline row in its owner reads healthy."""
    def check(p):
        timeline = p.get("timeline") or {}
        feature = (_RECALL.get(key) or {}).get("feature")
        rows = [r for r in timeline.get("timeline") or []
                if r.get("name") == feature and r.get("component") == host
                and r.get("type") == "SweepFeature"]
        # A healthy timeline row is published without its health key.
        return _measured("new solid sweep timeline health", rows,
                         bool(feature) and not timeline.get("truncated") and len(rows) == 1
                         and rows[0].get("health", "healthy") == "healthy")
    return check


def _solid_tool_rows():
    """Exercise NewBody solid sweeps through placed proxy handles and independent geometry."""
    # A curved solid sweep in a component offset along x builds an empty feature that reads
    # healthy (measured on 2706.0.97, also through the raw API), so the owned story uses the
    # straight path; the tool refuses that empty result.
    cases = (("straight", "SolidToolStraight", 3200),)
    rows = [("design_activate_component", {"occurrence": "root"}, "ok", None),
            ("model_create_component", {"name": "SolidToolWitness", "activate": True,
                                        "x": 3225, "y": 520}, _made_component, None),
            ("sketch_create", {"plane": "xy", "name": "SolidToolWitnessS"}, "ok", None),
            ("sketch_add_geometry", {"sketch_name": "SolidToolWitnessS", "geometry": [
                {"kind": "rectangle", "x1": 0, "y1": 0, "x2": 10, "y2": 10}]}, "ok", None),
            ("model_extrude", {"sketch_name": "SolidToolWitnessS", "distance": 10},
             _extruded, ("st_witness", lambda p: p["result_bodies"][0])),
            ("model_inspect", lambda c: _combine_inspect(
                "SolidToolWitness:1:" + _ctx_get(c, "st_witness", "witness")),
             lambda p: _measured("unrelated solid sweep witness before", p.get("mass"),
                                 _near((p.get("mass") or {}).get("volume"), 1000, 0.01)),
             ("st_witness_shape", _recall("st_witness_shape", _sweep_mode_shape)))]
    # Host-named sketches share the host's camera group, so the hand frame below owns the story.
    for case, host, x in cases:
        source, path, body_key = host + "S", host + "Path", "st_" + case + "_body"
        rows.extend([
            ("design_activate_component", {"occurrence": "root"}, "ok", None),
            ("model_create_component", {"name": host, "activate": True,
                                        "x": x, "y": 500, "rotate_deg": 25}, _made_component, None),
            ("sketch_create", {"plane": "xy", "name": source}, "ok", None),
            ("sketch_add_geometry", {"sketch_name": source, "component": host,
                                     "geometry": [{"kind": "rectangle", "x1": -2.5, "y1": -2.5,
                                                   "x2": 2.5, "y2": 2.5}]}, "ok", None),
            ("sketch_create", {"plane": "xy", "name": path}, "ok", None),
            ("sketch_add_geometry", {"sketch_name": path, "component": host,
                                     "geometry": [{"kind": "line", "x1": 0, "y1": 0,
                                                   "x2": 20, "y2": 0}]}, "ok", None),
            ("model_extrude", {"sketch_name": source, "component": host, "distance": 5},
             _extruded, (body_key, lambda p: p["result_bodies"][0])),
            ("model_inspect", lambda c, key=body_key, host=host: _combine_inspect(
                host + ":1:" + _ctx_get(c, key, "solid tool source")),
             _solid_tool_mass(case, "source"),
             ("st_" + case + "_shape", _recall("st_" + case + "_shape", _sweep_mode_shape)))])
    # The swept result lies beside the witness, so one frame holds both hosts.
    rows.append(_watch(["SolidToolStraight:1", "SolidToolWitness:1"]))
    for case, host, x in cases:
        path, body_key = host + "Path", "st_" + case + "_body"
        handle_key, result_key = "st_" + case + "_handle", "st_" + case + "_result"
        rows.extend([
            ("find_geometry", lambda c, key=body_key, host=host, x=x: {
                "target": host + ":1:" + _ctx_get(c, key, "solid tool source"),
                "kind": "planar_face", "nearest_to": [x, 500, 5],
                "units": "mm", "max_results": 1},
             lambda p: _measured("placed source face handle for solid sweep", p.get("matches"),
                                  p.get("returned") == 1 and bool((p.get("matches") or [{}])[0].get("handle"))),
             _fg(handle_key)),
            ("design_activate_component", {"occurrence": "SolidToolWitness:1"}, "ok", None),
            ("model_sweep", lambda c, key=handle_key, path=path, host=host: {
                "solid_body": _ctx_get(c, key, "placed solid tool handle"),
                "path": "sketch:" + path, "component": host, "operation": "new"},
             lambda p, host=host: _measured("owner-local NewBody solid sweep", p,
                 p.get("swept") is True and p.get("component") == host
                 and p.get("source_retained") is True and bool(p.get("feature"))
                 and p.get("orientation") == "perpendicular"
                 and p.get("path_curves") == 1 and len(p.get("result_bodies") or []) == 1),
             (result_key, _recall(result_key, lambda p: {"feature": p["feature"],
                                                         "body": p["result_bodies"][0]}))),
            ("design_get", {"include": ["timeline"], "max_results": 2000},
             _solid_tool_health(host, result_key), None),
            ("model_inspect", lambda c, key=result_key, host=host: _combine_inspect(
                host + ":1:" + _ctx_get(c, key, "solid sweep result")["body"]),
             _solid_tool_mass(case, "result"), None),
            ("model_inspect", lambda c, key=body_key, host=host: _combine_inspect(
                host + ":1:" + _ctx_get(c, key, "solid tool source")),
             _solid_tool_mass(case, "source", "st_" + case + "_shape"), None),
            ("model_inspect", lambda c: _combine_inspect(
                "SolidToolWitness:1:" + _ctx_get(c, "st_witness", "witness")),
             lambda p: _measured("unrelated witness unchanged by solid sweep", _sweep_mode_shape(p),
                 _sweep_mode_shape(p) == _RECALL.get("st_witness_shape")
                 and _sweep_mode_box_equal(_sweep_mode_shape(p),
                                           _RECALL.get("st_witness_shape") or {}, 0)), None),
        ])
    rows.extend([
        ("design_get", {"include": ["tree", "timeline"], "component": "SolidToolStraight",
                        "tree_bodies": True, "tree_handles": True, "max_results": 2000},
         lambda p: _measured("solid sweep refusal baseline", _solid_tool_census(p),
                             _solid_tool_census(p) is not None),
         ("st_guard", _recall("st_guard", _solid_tool_census))),
        ("model_sweep", lambda c: {"solid_body": "SolidToolStraight:1:" + _ctx_get(
            c, "st_straight_body", "solid tool source"),
                                   "path": "sketch:SolidToolStraightPath", "as_surface": True},
         _refused("as_surface"), None),
        ("design_get", {"include": ["tree", "timeline"], "component": "SolidToolStraight",
                        "tree_bodies": True, "tree_handles": True, "max_results": 2000},
         lambda p: _measured("invalid solid sweep left bodies and features unchanged",
                             _solid_tool_census(p),
                             _solid_tool_census(p) is not None
                             and _solid_tool_census(p) == _RECALL.get("st_guard")), None),
        ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ])
    return rows


_SOLID_TOOL = _solid_tool_rows()


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


def _loft_edit_definition(sources):
    """Check ordered section sources through an independent read."""
    def check(p):
        definition = p.get("definition") or {}
        rows = definition.get("sections") or []
        got = [row.get("source_sketch") for row in rows]
        return _measured("ordered Loft section sources", {
            "count": definition.get("section_count"), "sources": got,
            "indices": [row.get("index") for row in rows],
            "truncated": definition.get("truncated")},
            definition.get("section_count") == len(sources)
            and definition.get("truncated") is False
            and got == list(sources)
            and [row.get("index") for row in rows] == list(range(len(sources)))
            and all(row.get("kind") == "Profile" and row.get("profile_handle")
                    and row.get("source_component") == "LoftEdit"
                    for row in rows)
            and rows[0].get("end_condition") == "adsk::fusion::LoftDirectionEndCondition"
            and rows[-1].get("end_condition") == "adsk::fusion::LoftFreeEndCondition"
            and definition.get("is_solid") is True
            and definition.get("is_closed") is False
            and definition.get("guide_count") == 0)
    return check


def _loft_edit_landed(count):
    """Check one edit's definition, result material, scope and timeline evidence."""
    def check(p):
        before, after = p.get("target_before") or [], p.get("target_after") or []
        first = before[0].get("volume_cm3") if len(before) == 1 else None
        last = after[0].get("volume_cm3") if len(after) == 1 else None
        return _measured("interior Loft edit", {
            "before_cm3": first, "after_cm3": last,
            "sections": (p.get("definition_after") or {}).get("section_count"),
            "outside_changes": p.get("outside_body_changes"),
            "same_feature": p.get("same_feature"),
            "marker_restored": p.get("marker_restored"),
            "errors": p.get("new_timeline_errors"),
            "warnings": p.get("new_timeline_warnings")},
            p.get("edited") is True and p.get("definition_matches") is True
            and (p.get("definition_after") or {}).get("section_count") == count
            and p.get("geometry_changed") is True and _num(first) and _num(last)
            and abs(last - first) > 0.05
            and p.get("outside_body_changes") == []
            and p.get("same_feature") is True and p.get("marker_restored") is True
            and p.get("feature_health") == "healthy"
            and p.get("new_timeline_errors") == [] and p.get("new_timeline_warnings") == [])
    return check


def _loft_edit_volume(stage, previous=None):
    """Check an independent post-downstream material reading."""
    def check(p):
        volume = (p.get("mass") or {}).get("volume")
        prior = _RECALL.get(previous) if previous else None
        return _measured("Loft material after " + stage,
                         {"volume_cm3": volume, "previous_cm3": prior},
                         _num(volume) and volume > 0 and
                         (previous is None or (_num(prior) and abs(volume - prior) > 0.05)))
    return check


def _loft_edit_volume_kept(p):
    """Check the rolled-back Loft's independent volume against its pre-edit reading."""
    volume = (p.get("mass") or {}).get("volume")
    return _measured("rolled-back Loft material", {"volume_cm3": volume,
                                                   "created_cm3": _RECALL.get("le_volume_created")},
                     _near(volume, _RECALL["le_volume_created"], 0.0001))


def _rolled_back_body(volume_key, name_key, renamed=None):
    """(check, save) re-reading the one solid at a recalled volume; renamed pins its name change."""
    def solids(p):
        return [r.get("body") for r in (p.get("mass") or {}).get("per_body") or []
                if r.get("is_solid") is True and _near(r.get("volume"), _RECALL[volume_key], 0.0001)]

    def check(p):
        names, was = solids(p), _RECALL.get(name_key)
        return _measured("one solid at the rolled-back volume", {"names": names, "was": was},
                         len(names) == 1 and (renamed is None or (names[0] != was) is renamed))
    return check, (name_key, _recall(name_key, lambda p: solids(p)[0]))


def _loft_edit_identical(p):
    """Check a landed retarget whose bodies re-read identical, reported as a success."""
    return _measured("identical-geometry Loft retarget", {
        "edited": p.get("edited"), "definition_matches": p.get("definition_matches"),
        "geometry_changed": p.get("geometry_changed"), "rollback": p.get("rollback"),
        "outside_changes": p.get("outside_body_changes"), "note": p.get("note")},
        p.get("edited") is True and p.get("definition_matches") is True
        and p.get("geometry_changed") is False and p.get("outside_body_changes") == []
        and "rollback" not in p
        and (p.get("note") or "").endswith("The body geometry reads identical before and after."))


def _loft_edit_witness(p):
    """Check the unrelated witness body retained its measured volume."""
    volume = (p.get("mass") or {}).get("volume")
    return _measured("unchanged Loft witness", {"volume_cm3": volume},
                     _num(volume) and _near(volume, _RECALL["le_witness_volume"], 0.0001))


def _loft_edit_timeline_evidence(p):
    """The complete evaluated timeline and uniquely scoped dependent cut."""
    timeline = p.get("timeline") or {}
    rows = timeline.get("timeline") or []
    matches = [row for row in rows if row.get("name") == _RECALL.get("le_cut")
               and row.get("component") == "LoftEdit" and row.get("type") == "ExtrudeFeature"]
    summary = timeline.get("summary") or {}
    return {"cut": matches[0] if len(matches) == 1 else None,
            "cut_matches": len(matches), "marker": timeline.get("marker_position"),
            "count": timeline.get("count"), "returned": timeline.get("returned"),
            "row_count": len(rows), "states": summary.get("states"),
            "exceptions": summary.get("exceptions")}


def _loft_edit_downstream(p, baseline=False):
    """Check the scoped cut and complete timeline against their pre-edit state."""
    now = _loft_edit_timeline_evidence(p)
    before = _RECALL.get("le_timeline_before") if not baseline else None
    cut = now["cut"] or {}
    complete = (now["cut_matches"] == 1 and type(cut.get("index")) is int
                and type(now["count"]) is int and now["count"] > 0
                and now["marker"] == now["count"] == now["returned"] == now["row_count"]
                and now["states"] == {"healthy": now["count"]}
                and now["exceptions"] == [])
    retained = (baseline or (isinstance(before, dict) and
                all(now[key] == before.get(key) for key in
                    ("cut", "marker", "count", "returned", "states", "exceptions"))))
    return _measured("retained downstream Loft cut and timeline",
                     {"before": before, "after": now}, complete and retained)


def _loft_edit_end_parameter(key, baseline=None):
    """Check one public model parameter retained its expression and evaluated value."""
    def check(p):
        param = p.get("parameter") or {}
        expected = _RECALL.get("le_parameter_" + key) if baseline else None
        observed = {name: param.get(name) for name in
                    ("name", "expression", "value", "value_units")}
        return _measured("Loft " + key + " parameter", observed,
                         observed["name"] == _RECALL["le_parameters"][key]
                         and isinstance(observed["expression"], str)
                         and _num(observed["value"])
                         and (expected is None or observed == expected))
    return check


def _loft_edit_rows():
    """Exercise profile retarget, three-to-two removal and minimum refusal in scratch."""
    rows = [("doc_get", {}, _home_document, ("le_story", _home_address)),
            ("doc_new", lambda c: {"expect_document": _ctx_get(c, "le_story", "story")},
             _new_document, ("le_doc", lambda p: p["document_handle"]))]

    def write(name, args, check="ok", save=None):
        rows.append((name, lambda c, args=args: _combine_pin(
            c, "le_doc", args(c) if callable(args) else args), check, save))

    def read_ends(baseline):
        for key in ("start_weight", "start_angle"):
            rows.append(("param_get", lambda c, key=key: {
                "name": _RECALL["le_parameters"][key]},
                _loft_edit_end_parameter(key, baseline),
                (("le_parameter_" + key, _recall("le_parameter_" + key,
                   lambda p: {name: (p.get("parameter") or {}).get(name) for name in
                              ("name", "expression", "value", "value_units")}))
                 if not baseline else None)))

    write("model_create_component", {"name": "LoftWitness", "activate": True}, _made_component)
    write("sketch_create", {"plane": "xy", "name": "WitnessSketch"})
    write("sketch_add_geometry", {"sketch_name": "WitnessSketch", "geometry": [
        {"kind": "rectangle", "x1": 100, "y1": 100, "x2": 110, "y2": 110}]})
    write("model_extrude", {"sketch_name": "WitnessSketch", "distance": 10}, _extruded,
          ("le_witness", lambda p: p["result_bodies"][0]))
    rows.append(("model_inspect", lambda c: {"target": "LoftWitness:" + _ctx_get(
        c, "le_witness", "witness body"), "include": ["mass"], "units": "cm"},
        lambda p: _num((p.get("mass") or {}).get("volume")),
        ("le_witness_volume", _recall("le_witness_volume", lambda p: p["mass"]["volume"]))))
    write("design_activate_component", {"occurrence": "root"})
    write("model_create_component", {"name": "LoftEdit", "activate": True}, _made_component)
    for sketch, plane, radius in (("Start", "xy", 5), ("Middle", "MidPlane", 6),
                                  ("MiddleTwin", "MidPlane", 6),
                                  ("Alternate", "MidPlane", 9), ("Narrow", "MidPlane", 1),
                                  ("Penultimate", "LatePlane", 7), ("End", "EndPlane", 4)):
        if sketch == "Middle":
            write("model_construction", {"kind": "plane", "plane": "xy", "offset": 10,
                                         "name": "MidPlane"}, _datum_plane("xy"))
        if sketch == "End":
            write("model_construction", {"kind": "plane", "plane": "xy", "offset": 20,
                                         "name": "EndPlane"}, _datum_plane("xy"))
        if sketch == "Penultimate":
            write("model_construction", {"kind": "plane", "plane": "xy", "offset": 15,
                                         "name": "LatePlane"}, _datum_plane("xy"))
        write("sketch_create", {"plane": plane, "name": sketch})
        write("sketch_add_geometry", {"sketch_name": sketch, "geometry": [
            {"kind": "circle", "cx": 0, "cy": 0, "radius": radius}]})
        rows.append(("sketch_get", {"sketch_name": sketch}, "ok", _prof("le_" + sketch.lower())))
    def loft_refs(p):
        _RECALL["le_body"] = p["result_bodies"][0]
        _RECALL["le_parameters"] = p["model_parameters"]
        return "LoftEdit/" + p["feature"]

    write("model_loft", lambda c: {"profiles": [_ctx_get(c, "le_start", "start profile"),
                                               _ctx_get(c, "le_middle", "middle profile"),
                                               _ctx_get(c, "le_penultimate", "late profile"),
                                               _ctx_get(c, "le_end", "end profile")],
                                           "start": "direction"},
          _lofted, ("le_feature", loft_refs))
    read_ends(False)
    rows.append(("design_get", lambda c: {"include": ["definition"],
        "feature": _ctx_get(c, "le_feature", "Loft feature")},
        _loft_edit_definition(("Start", "Middle", "Penultimate", "End")), None))
    # A side slot just under the middle section: every section set below reaches x=2.5 there
    # except the Narrow waist, which leaves the slot cutting air.
    write("sketch_create", {"plane": "MidPlane", "name": "DependentCutSketch"})
    write("sketch_add_geometry", {"sketch_name": "DependentCutSketch", "geometry": [
        {"kind": "rectangle", "x1": 2.5, "y1": -0.5, "x2": 20, "y2": 0.5}]})
    write("model_extrude", lambda c: {"sketch_name": "DependentCutSketch", "distance": -0.5,
        "operation": "cut", "target_bodies": ["LoftEdit:" + _RECALL["le_body"]]},
        _extruded, ("le_cut", _recall("le_cut", lambda p: p["feature"])))
    rows.append(("model_inspect", lambda c: {"target": "LoftEdit:" + _RECALL["le_body"],
        "include": ["mass"], "units": "cm"},
        _loft_edit_volume("creation"),
        ("le_volume_created", _recall("le_volume_created", lambda p: p["mass"]["volume"]))))
    rows.append(("design_get", {"include": ["timeline"], "max_results": 100},
                 lambda p: _loft_edit_downstream(p, baseline=True),
                 ("le_timeline_before", _recall("le_timeline_before",
                                                _loft_edit_timeline_evidence))))
    write("model_edit_loft", lambda c: {"feature": _ctx_get(c, "le_feature", "Loft feature"),
        "action": "retarget", "section_index": 1,
        "profile": _ctx_get(c, "le_narrow", "narrow profile"), "component": "LoftEdit"},
        _refused("New evaluated timeline errors or warnings", "It was rolled back and re-read: "
                 "section 1 reads sketch 'Middle' profile 0 again"))
    # The rows below target the Loft body by name, so the name is read back after the restore.
    rows.append(("model_inspect", {"target": "LoftEdit:1", "include": ["mass"], "units": "cm",
                                   "per_body": True}, *_rolled_back_body("le_volume_created", "le_body")))
    rows.append(("design_get", lambda c: {"include": ["definition"],
        "feature": _ctx_get(c, "le_feature", "Loft feature")},
        _loft_edit_definition(("Start", "Middle", "Penultimate", "End")), None))
    rows.append(("model_inspect", lambda c: {"target": "LoftEdit:" + _RECALL["le_body"],
        "include": ["mass"], "units": "cm"}, _loft_edit_volume_kept, None))
    rows.append(("design_get", {"include": ["timeline"], "max_results": 100},
                 _loft_edit_downstream, None))
    write("model_edit_loft", lambda c: {"feature": _ctx_get(c, "le_feature", "Loft feature"),
        "action": "retarget", "section_index": 1,
        "profile": _ctx_get(c, "le_middletwin", "middle twin profile"), "component": "LoftEdit"},
        _loft_edit_identical)
    rows.append(("design_get", lambda c: {"include": ["definition"],
        "feature": _ctx_get(c, "le_feature", "Loft feature")},
        _loft_edit_definition(("Start", "MiddleTwin", "Penultimate", "End")), None))
    rows.append(("model_inspect", lambda c: {"target": "LoftEdit:" + _RECALL["le_body"],
        "include": ["mass"], "units": "cm"}, _loft_edit_volume_kept, None))
    rows.append(("design_get", {"include": ["timeline"], "max_results": 100},
                 _loft_edit_downstream, None))
    write("model_edit_loft", lambda c: {"feature": _ctx_get(c, "le_feature", "Loft feature"),
        "action": "retarget", "section_index": 1,
        "profile": _ctx_get(c, "le_alternate", "alternate profile"), "component": "LoftEdit"},
        _loft_edit_landed(4))
    read_ends(True)
    rows.append(("design_get", lambda c: {"include": ["definition"],
        "feature": _ctx_get(c, "le_feature", "Loft feature")},
        _loft_edit_definition(("Start", "Alternate", "Penultimate", "End")), None))
    rows.append(("model_inspect", lambda c: {"target": "LoftEdit:" + _RECALL["le_body"],
        "include": ["mass"], "units": "cm"},
        _loft_edit_volume("retarget", "le_volume_created"),
        ("le_volume_retarget", _recall("le_volume_retarget", lambda p: p["mass"]["volume"]))))
    write("model_edit_loft", lambda c: {"feature": _ctx_get(c, "le_feature", "Loft feature"),
        "action": "remove", "section_index": 2}, _loft_edit_landed(3))
    read_ends(True)
    rows.append(("design_get", lambda c: {"include": ["definition"],
        "feature": _ctx_get(c, "le_feature", "Loft feature")},
        _loft_edit_definition(("Start", "Alternate", "End")), None))
    rows.append(("model_inspect", lambda c: {"target": "LoftEdit:" + _RECALL["le_body"],
        "include": ["mass"], "units": "cm"},
        _loft_edit_volume("four-to-three removal", "le_volume_retarget"),
        ("le_volume_three", _recall("le_volume_three", lambda p: p["mass"]["volume"]))))
    write("model_edit_loft", lambda c: {"feature": _ctx_get(c, "le_feature", "Loft feature"),
        "action": "remove", "section_index": 1}, _loft_edit_landed(2))
    read_ends(True)
    rows.append(("design_get", lambda c: {"include": ["definition"],
        "feature": _ctx_get(c, "le_feature", "Loft feature")},
        _loft_edit_definition(("Start", "End")), None))
    rows.append(("model_inspect", lambda c: {"target": "LoftEdit:" + _RECALL["le_body"],
        "include": ["mass"], "units": "cm"},
        _loft_edit_volume("three-to-two removal", "le_volume_three"),
        ("le_volume_removed", _recall("le_volume_removed", lambda p: p["mass"]["volume"]))))
    write("model_edit_loft", lambda c: {"feature": _ctx_get(c, "le_feature", "Loft feature"),
        "action": "remove", "section_index": 1}, _refused("fewer than two"))
    rows.append(("design_get", lambda c: {"include": ["definition"],
        "feature": _ctx_get(c, "le_feature", "Loft feature")},
        _loft_edit_definition(("Start", "End")), None))
    rows.append(("model_inspect", lambda c: {"target": "LoftEdit:" + _RECALL["le_body"],
        "include": ["mass"], "units": "cm"},
        lambda p: _near((p.get("mass") or {}).get("volume"),
                        _RECALL["le_volume_removed"], 0.0001), None))
    rows.append(("model_inspect", lambda c: {"target": "LoftWitness:" + _ctx_get(
        c, "le_witness", "witness body"), "include": ["mass"], "units": "cm"},
        _loft_edit_witness, None))
    rows.append(("design_get", {"include": ["timeline"], "max_results": 100},
                 _loft_edit_downstream, None))
    rows += [("doc_activate", lambda c: {"name": _ctx_get(c, "le_story", "story"),
                                         "expect_document": _ctx_get(c, "le_doc", "Loft edit")},
              "ok", None),
             ("doc_close", lambda c: {"name": _ctx_get(c, "le_doc", "Loft edit"),
                                      "save_changes": False,
                                      "expect_document": _ctx_get(c, "le_story", "story")},
              _document_closed, None)]
    return rows


_LOFT_EDITOR = _loft_edit_rows()


def _later_refusal(sketch, row, feature, feature_row):
    """The one sentence the editors refuse an operand drawn after their feature with."""
    return _refused(f"Editing '{feature}': sketch '{sketch}' is at timeline row {row}, after "
                    f"'{feature}' at row {feature_row}. Move it first with design_edit_timeline("
                    f"action='reorder', feature='{sketch}@{row}', to='before', "
                    f"end_feature='{feature}@{feature_row}'), then retry. Nothing was edited.")


def _timeline_names(p):
    """The timeline's row names in order, or None unless every row is listed and healthy."""
    t = p.get("timeline") or {}
    rows = t.get("timeline") or []
    whole = (t.get("count") == t.get("marker_position") == len(rows) and not t.get("truncated")
             and (t.get("summary") or {}).get("states") == {"healthy": len(rows)})
    return [r.get("name") for r in rows] if whole else None


def _timeline_reads(label, want):
    """An independent timeline read: every row healthy and `want(names)` true of the order."""
    return lambda p: _measured(label, _timeline_names(p),
                               _timeline_names(p) is not None and want(_timeline_names(p)))


def _later_operand_rows():
    """Refuse operands drawn after their feature, reorder one earlier and edit, refuse a cycle."""
    rows = [("doc_get", {}, _home_document, ("lo_story", _home_address)),
            ("doc_new", lambda c: {"expect_document": _ctx_get(c, "lo_story", "story")},
             _new_document, ("lo_doc", lambda p: p["document_handle"]))]

    def write(name, args, check="ok", save=None):
        rows.append((name, lambda c, args=args: _combine_pin(
            c, "lo_doc", args(c) if callable(args) else args), check, save))

    def read(name, args, check, save=None):
        rows.append((name, lambda c, args=args: args(c) if callable(args) else dict(args),
                     check, save))

    def sketch(name, plane, geometry):
        write("sketch_create", {"plane": plane, "name": name})
        write("sketch_add_geometry", {"sketch_name": name, "geometry": [geometry]})

    def volume(label, cm3):
        read("model_inspect", lambda c: {"target": _ctx_get(c, "lo_body", "sweep body"),
                                         "include": ["mass"], "units": "cm"},
             lambda p: _measured(label, (p.get("mass") or {}).get("volume"),
                                 _near((p.get("mass") or {}).get("volume"), cm3, 0.0001)))

    # Rows 0-10 hold the features; 11-14 the sketches drawn after every one of them.
    sketch("Prof", "yz", {"kind": "circle", "cx": 0, "cy": 0, "radius": 5})
    sketch("PathA", "xy", {"kind": "line", "x1": 0, "y1": 0, "x2": 100, "y2": 0})
    write("model_sweep", {"profile": {"sketch": "Prof", "profile_index": 0},
                          "path": "sketch:PathA", "operation": "new"}, _swept,
          ("lo_body", lambda p: p["result_bodies"][0]))
    sketch("Box", "xy", {"kind": "rectangle", "x1": 200, "y1": -20, "x2": 240, "y2": 20})
    write("model_extrude", {"sketch_name": "Box", "profile_index": 0, "distance": 20}, _extruded)
    for offset in (20, 40):
        write("model_construction", {"kind": "plane", "plane": "xy", "offset": offset,
                                     "name": f"PlaneZ{offset}"}, _datum_plane("xy"))
    for name, plane, radius in (("S0", "xy", 10), ("S1", "PlaneZ20", 6), ("S2", "PlaneZ40", 10)):
        sketch(name, plane, {"kind": "circle", "cx": 400, "cy": 0, "radius": radius})
    write("model_loft", {"profiles": [{"sketch": s, "profile_index": 0} for s in ("S0", "S1", "S2")]},
          _lofted)
    sketch("PathLater", "xy", {"kind": "line", "x1": 0, "y1": 0, "x2": 80, "y2": 0})
    sketch("ProfLater", "yz", {"kind": "circle", "cx": 0, "cy": 0, "radius": 8})
    sketch("BoxLater", "xy", {"kind": "rectangle", "x1": 300, "y1": -10, "x2": 320, "y2": 10})
    sketch("S1Later", "PlaneZ20", {"kind": "circle", "cx": 400, "cy": 0, "radius": 8})
    read("design_get", {"include": ["timeline"], "max_results": 100},
         _timeline_reads("later-operand baseline", lambda names: names[2] == "Sweep1"
                         and names[11:] == ["PathLater", "ProfLater", "BoxLater", "S1Later"]),
         ("lo_rows", _recall("lo_rows", _timeline_names)))
    volume("sweep volume along the 100 mm path", 7.853982)
    read("design_get", {"include": ["definition"], "feature": "Sweep1"},
         lambda p: _measured("Sweep definition keeps readable fields when path needs edit context", p.get("definition"),
             (p.get("definition") or {}).get("type") == "SweepFeature"
             and (p.get("definition") or {}).get("operation") == "new"
             and (p.get("definition") or {}).get("is_solid") is True
             and (p.get("definition") or {}).get("orientation") is not None
             and (p.get("definition") or {}).get("path") is None
             and (p.get("definition") or {}).get("path_count") is None
             and (p.get("definition") or {}).get("participants") is None
             and bool(((p.get("definition") or {}).get("unavailable") or {}).get("path"))
             and bool(((p.get("definition") or {}).get("unavailable") or {}).get("participants"))
             and ((p.get("definition") or {}).get("profile") or {}).get("source_sketch") == "Prof"
             and bool(((p.get("definition") or {}).get("profile") or {}).get("profile_handle"))),
         ("lo_profile_handle", lambda p: p["definition"]["profile"]["profile_handle"]))
    read("design_get", {"include": ["timeline"], "max_results": 100},
         _timeline_reads("definition read preserves every healthy timeline row and marker",
                         lambda names: names == _RECALL.get("lo_rows")))
    volume("definition read preserves the sweep volume", 7.853982)
    write("model_edit_sweep", lambda c: {"feature": "Sweep1", "action": "profile",
        "profile": _ctx_get(c, "lo_profile_handle", "profile from definition read")},
        _refused("already uses that profile", "Nothing was edited"))
    # Each editor names the later sketch, both rows and the move; nothing is edited.
    write("model_edit_sweep", {"feature": "Sweep1", "action": "path", "path": "sketch:PathLater"},
          _later_refusal("PathLater", 11, "Sweep1", 2))
    write("model_edit_sweep", {"feature": "Sweep1", "action": "profile",
                               "profile": {"sketch": "ProfLater", "profile_index": 0}},
          _later_refusal("ProfLater", 12, "Sweep1", 2))
    write("model_edit_extrude", {"feature": "Extrude1", "action": "profile",
                                 "profile": {"sketch": "BoxLater", "profile_index": 0}},
          _later_refusal("BoxLater", 13, "Extrude1", 4))
    write("model_edit_loft", {"feature": "Loft1", "action": "retarget", "section_index": 1,
                              "profile": {"sketch": "S1Later", "profile_index": 0}},
          _later_refusal("S1Later", 14, "Loft1", 10))
    read("design_get", {"include": ["timeline"], "max_results": 100},
         _timeline_reads("refused edits left the timeline as it was",
                         lambda names: names == _RECALL.get("lo_rows")))
    volume("refused edits left the sweep volume", 7.853982)
    # The move the refusal names, read back independently, then the edit it unblocks.
    write("design_edit_timeline", {"action": "reorder", "feature": "PathLater@11", "to": "before",
                                   "end_feature": "Sweep1@2"},
          lambda p: _measured("PathLater moved before Sweep1", p, p.get("reordered") is True
                              and (p.get("index_before"), p.get("index_after")) == (11, 2)))
    read("design_get", {"include": ["timeline"], "max_results": 100},
         _timeline_reads("PathLater sits before Sweep1, every other row in its order",
                         lambda names: names[1:4] == ["PathA", "PathLater", "Sweep1"]
                         and [n for n in names if n != "PathLater"]
                         == [n for n in _RECALL.get("lo_rows") or [] if n != "PathLater"]))
    write("model_edit_sweep", {"feature": "Sweep1", "action": "path", "path": "sketch:PathLater"},
          lambda p: _measured("the unblocked path edit landed", p, p.get("edited") is True
                              and p.get("operand_after") == "PathLater/line:0"))
    volume("sweep volume along the 80 mm path", 6.283185)
    # A sketch projecting the sweep's own edge depends on it: Fusion refuses the move.
    read("find_geometry", lambda c: {"target": _ctx_get(c, "lo_body", "sweep body"),
                                     "kind": "circular_edge", "max_results": 1},
         lambda p: _measured("one sweep end edge", p.get("returned"), p.get("returned") == 1),
         _fg("lo_edge"))
    write("sketch_create", {"plane": "xy", "name": "Dep"})
    write("sketch_project", lambda c: {"sketch_name": "Dep", "entities": [
        _ctx_get(c, "lo_edge", "sweep end edge")]},
          lambda p: _measured("the sweep edge projected into Dep", p.get("created_count"),
                              _num(p.get("created_count")) and p["created_count"] >= 1))
    read("design_get", {"include": ["timeline"], "max_results": 100},
         _timeline_reads("Dep drawn last", lambda names: names[-1] == "Dep"),
         ("lo_rows_dep", _recall("lo_rows_dep", _timeline_names)))
    write("design_edit_timeline", {"action": "reorder", "feature": "Dep", "to": "before",
                                   "end_feature": "Sweep1"},
          _refused("Fusion refused to move 'Dep' before 'Sweep1'", "CIRCULAR_DEPENDENCY",
                   "Nothing moved (the timeline re-reads unchanged)."))
    read("design_get", {"include": ["timeline"], "max_results": 100},
         _timeline_reads("the refused move left every row where it was",
                         lambda names: names == _RECALL.get("lo_rows_dep")))
    # An earlier item moves later; the end-of-timeline refusal names a two-move remedy.
    write("design_edit_timeline", {"action": "reorder", "feature": "PathA", "to": "after",
                                   "end_feature": "Loft1"},
          lambda p: _measured("PathA moved after Loft1", p, p.get("reordered") is True
                              and (p.get("index_before"), p.get("index_after")) == (1, 11)))
    read("design_get", {"include": ["timeline"], "max_results": 100},
         _timeline_reads("PathA sits right after Loft1; the end-move operands retain their rows",
                         lambda names: len(names) == 16 and names[10:12] == ["Loft1", "PathA"]
                         and names[12:] == ["ProfLater", "BoxLater", "S1Later", "Dep"]),
         ("lo_before_end", _recall("lo_before_end", _timeline_names)))
    write("design_edit_timeline", {"action": "reorder", "feature": "ProfLater", "to": "after",
                                   "end_feature": "Dep"},
          _refused("Fusion cannot place an item after the last timeline row", "Nothing moved.",
                   "To make 'ProfLater' last, run design_edit_timeline(action='reorder', "
                   "feature='ProfLater@12', to='before', end_feature='Dep@15'), then "
                   "design_edit_timeline(action='reorder', feature='Dep@15', to='before', "
                   "end_feature='ProfLater@14')."))
    read("design_get", {"include": ["timeline"], "max_results": 100},
         _timeline_reads("the refused end move left every row where it was",
                         lambda names: names == _RECALL.get("lo_before_end")))
    write("design_edit_timeline", lambda c: {
        "action": "reorder", "to": "before",
        "feature": "ProfLater@" + str(_ctx_get(c, "lo_before_end", "timeline").index("ProfLater")),
        "end_feature": "Dep@" + str(_ctx_get(c, "lo_before_end", "timeline").index("Dep"))},
        lambda p: _measured("the remedy moved ProfLater before Dep", p,
                            p.get("reordered") is True and p.get("feature") == "ProfLater"
                            and p.get("end_feature") == "Dep"))
    read("design_get", {"include": ["timeline"], "max_results": 100},
         _timeline_reads("ProfLater sits before Dep; every other row kept its order",
                         lambda names: names[-2:] == ["ProfLater", "Dep"]
                         and [n for n in names if n != "ProfLater"]
                         == [n for n in _RECALL.get("lo_before_end") or [] if n != "ProfLater"]),
         ("lo_before_swap", _recall("lo_before_swap", _timeline_names)))
    write("design_edit_timeline", lambda c: {
        "action": "reorder", "to": "before",
        "feature": "Dep@" + str(_ctx_get(c, "lo_before_swap", "timeline").index("Dep")),
        "end_feature": "ProfLater@" + str(_ctx_get(c, "lo_before_swap", "timeline").index("ProfLater"))},
        lambda p: _measured("the remedy moved Dep before ProfLater", p,
                            p.get("reordered") is True and p.get("feature") == "Dep"
                            and p.get("end_feature") == "ProfLater"))
    read("design_get", {"include": ["timeline"], "max_results": 100},
         _timeline_reads("ProfLater is last; every other row kept its order",
                         lambda names: names[-2:] == ["Dep", "ProfLater"]
                         and names == [n for n in _RECALL.get("lo_before_end") or []
                                       if n != "ProfLater"] + ["ProfLater"]))
    rows += [("doc_activate", lambda c: {"name": _ctx_get(c, "lo_story", "story"),
                                         "expect_document": _ctx_get(c, "lo_doc", "later operand")},
              "ok", None),
             ("doc_close", lambda c: {"name": _ctx_get(c, "lo_doc", "later operand"),
                                      "save_changes": False,
                                      "expect_document": _ctx_get(c, "lo_story", "story")},
              _document_closed, None)]
    return rows


_LATER_OPERAND = _later_operand_rows()


def _loft_scoped_body(case, stage, role, expected, previous=None):
    """Check a scoped loft body using an independent mass and bounds read."""
    def check(p):
        got = _sweep_mode_shape(p)
        old = _RECALL.get(previous) if previous else None
        volume, area = got["volume"], got["area"]
        valid = (p.get("kind") == "body" and p.get("units") == "cm"
                 and (p.get("mass") or {}).get("accuracy_used") == "very_high"
                 and _num(volume) and _num(area) and _sweep_mode_box_equal(got, got)
                 and _near(volume, expected, 0.002)
                 and (previous is None or old is not None))
        if valid and old is not None:
            if role == "SelectedStock":
                valid = (abs(volume - old["volume"]) > 0.001
                         and abs(area - old["area"]) > 0.001)
            else:
                valid = (abs(volume - old["volume"]) < 0.00001
                         and abs(area - old["area"]) < 0.00001
                         and _sweep_mode_box_equal(got, old))
        return _measured(f"{case} loft {stage} {role} independent material and bounds",
                         {"current": got, "previous": old, "expected_cm3": expected}, valid)
    return check


def _loft_consumed_public(p):
    """Require the retained selected body's zero material from a typed independent read."""
    mass = p.get("mass") or {}
    return _measured("retained selected body has zero volume, area and lumps",
                     {"kind": p.get("kind"), "units": p.get("units"),
                      "lumps": p.get("lump_count"),
                      "volume_mm3": mass.get("volume"), "area_mm2": mass.get("area"),
                      "accuracy": mass.get("accuracy_used")},
                     p.get("kind") == "body" and p.get("units") == "mm"
                     and mass.get("accuracy_used") == "very_high"
                     and p.get("lump_count") == 0
                     and mass.get("volume") == 0 and mass.get("area") == 0)


def _loft_split_fragment(index, first_key=None):
    """Verify one independently inspected half of the selected split stock."""
    def check(p):
        mass = p.get("mass") or {}
        lo, hi = p.get("min_point") or {}, p.get("max_point") or {}
        side = (-1 if _num(hi.get("x")) and hi["x"] < 0 else
                1 if _num(lo.get("x")) and lo["x"] > 0 else 0)
        previous_side = _RECALL.get(first_key) if first_key else None
        valid = (p.get("kind") == "body" and p.get("units") == "mm"
                 and mass.get("accuracy_used") == "very_high"
                 and _near(mass.get("volume"), 246.9417, 0.02)
                 and side != 0 and (first_key is None or
                                    previous_side in (-1, 1) and side == -previous_side)
                 and _near(lo.get("y"), -2, 0.01) and _near(hi.get("y"), 2, 0.01)
                 and _near(lo.get("z"), 10, 0.01) and _near(hi.get("z"), 20, 0.01)
                 and _near(lo.get("x") if side < 0 else hi.get("x"),
                           -10 if side < 0 else 10, 0.01)
                 and _near(hi.get("x") if side < 0 else lo.get("x"),
                           -math.sqrt(12) if side < 0 else math.sqrt(12), 0.02))
        return _measured(f"split loft fragment {index} independent volume and opposite X bounds",
                         {"volume_mm3": mass.get("volume"), "min": lo, "max": hi,
                          "side": side, "previous_side": previous_side}, valid)
    return check


def _loft_participants_rows():
    """Exercise explicit cut and intersect participants with five independent body witnesses."""
    rows = []
    for case, selected_after in (("cut", 1.09530556), ("intersect", 0.94469444)):
        story, doc = f"loft_{case}_story", f"loft_{case}_doc"
        host, foreign = f"Loft{case.title()}Host", f"Loft{case.title()}Foreign"
        rows.extend([
            ("doc_get", {}, _home_document, (story, _home_address)),
            ("doc_new", lambda c, story=story: {
                "expect_document": _ctx_get(c, story, "loft story")},
             _new_document, (doc, lambda p: p["document_handle"]))])

        def write(tool, args, check="ok", save=None, doc=doc):
            rows.append((tool, lambda c, args=args, doc=doc: _combine_pin(
                c, doc, args(c) if callable(args) else args), check, save))

        def box(owner, role, low, high):
            sketch = role + "Sketch"
            plane = "xy"
            if low[2]:
                plane = role + "Plane"
                write("model_construction", {"kind": "plane", "plane": "xy",
                                             "offset": low[2], "name": plane}, _datum_plane("xy"))
            write("sketch_create", {"plane": plane, "name": sketch})
            write("sketch_add_geometry", {"sketch_name": sketch, "component": owner,
                                           "geometry": [{"kind": "rectangle", "x1": low[0],
                                                         "y1": low[1], "x2": high[0],
                                                         "y2": high[1]}]})
            body_key = f"loft_{case}_{role}_body"
            write("model_extrude", {"sketch_name": sketch, "component": owner,
                                    "distance": high[2] - low[2], "operation": "new"}, _extruded,
                  (body_key, lambda p: p["result_bodies"][0]))
            write("design_set_name", lambda c, owner=owner, role=role, key=body_key: {
                "target": owner + ":" + _ctx_get(c, key, "loft stock"),
                "new_name": role},
                  lambda p, role=role: p.get("renamed") is True and p.get("name") == role)

        write("model_create_component", {"name": host, "activate": True}, _made_component)
        for role, low, high in (
                ("SelectedStock", (-6, -5, 0), (0.8, 5, 30)),
                ("UnselectedOverlap", (1.2, -5, 0), (6, 5, 30)),
                ("HostSentinel", (30, 30, 0), (40, 40, 10))):
            box(host, role, low, high)
        write("sketch_create", {"plane": "xy", "name": "LoftBase"})
        write("sketch_add_geometry", {"sketch_name": "LoftBase", "component": host,
                                       "geometry": [{"kind": "circle", "cx": 0, "cy": 0,
                                                     "radius": 4}]})
        write("model_construction", {"kind": "plane", "plane": "xy", "offset": 30,
                                     "name": "LoftTopPlane"}, _datum_plane("xy"))
        write("sketch_create", {"plane": "LoftTopPlane", "name": "LoftTop"})
        write("sketch_add_geometry", {"sketch_name": "LoftTop", "component": host,
                                       "geometry": [{"kind": "circle", "cx": 0, "cy": 0,
                                                     "radius": 4}]})
        write("design_activate_component", {"occurrence": "root"})
        write("model_create_component", {"name": foreign, "activate": True}, _made_component)
        for role, low, high in (
                ("ForeignOverlap", (-2.5, -3, 0), (2.5, 3, 30)),
                ("ForeignSentinel", (50, 50, 0), (60, 60, 10))):
            box(foreign, role, low, high)
        roles = ((host, "SelectedStock", 2.04), (host, "UnselectedOverlap", 1.44),
                 (host, "HostSentinel", 1.0), (foreign, "ForeignOverlap", 0.9),
                 (foreign, "ForeignSentinel", 1.0))
        for owner, role, expected in roles:
            key = f"loft_{case}_before_{role}"
            rows.append(("model_inspect", {"target": f"{owner}:{role}",
                                           "include": ["default", "mass"],
                                           "units": "cm", "accuracy": "very_high"},
                         _loft_scoped_body(case, "before", role, expected),
                         (key, _recall(key, _sweep_mode_shape))))
        write("model_loft", {"profiles": [{"sketch": "LoftBase", "profile_index": 0},
                                          {"sketch": "LoftTop", "profile_index": 0}],
                             "component": host, "operation": case,
                             "target_bodies": ["SelectedStock"]},
              lambda p, case=case, host=host: _measured(
                  f"{case} loft configured scope and verified outside bodies", p,
                  p.get("lofted") is True and p.get("operation") == case
                  and p.get("scoped_to_bodies") == [f"{host}:SelectedStock"]
                  and p.get("outside_body_changes") == []
                  and _num(p.get("volume_delta_cm3")) and bool(p.get("result_bodies"))))
        for owner, role, expected in roles:
            key = f"loft_{case}_before_{role}"
            rows.append(("model_inspect", {"target": f"{owner}:{role}",
                                           "include": ["default", "mass"],
                                           "units": "cm", "accuracy": "very_high"},
                         _loft_scoped_body(case, "after", role,
                                           selected_after if role == "SelectedStock" else expected,
                                           key), None))
        if case == "cut":
            write("design_activate_component", {"occurrence": host + ":1"})
            box(host, "ConsumedStock", (-1, -1, 0), (1, 1, 30))
            rows.append(("model_inspect", _combine_inspect(host + ":ConsumedStock"),
                         _combine_body("loft stock before full consumption",
                                       (-1, -1, 0), (1, 1, 30), 120), None))
            rows.append(("design_get", {"include": ["tree"], "component": host,
                                        "tree_bodies": True, "tree_handles": True},
                         lambda p: _measured(
                             "loft full-consumption source identity",
                             (p.get("tree") or {}).get("tree"),
                             sum(b.get("name") == "ConsumedStock" for b in
                                 ((p.get("tree") or {}).get("tree") or {}).get("bodies", [])) == 1),
                         ("loft_consumed_handle", _recall("loft_consumed_handle", lambda p:
                             next(b["handle"] for b in p["tree"]["tree"]["bodies"]
                                  if b["name"] == "ConsumedStock")))))
            write("model_loft", {"profiles": [{"sketch": "LoftBase", "profile_index": 0},
                                              {"sketch": "LoftTop", "profile_index": 0}],
                                 "component": host, "operation": "cut",
                                 "target_bodies": ["ConsumedStock"]},
                  lambda p, host=host: _measured(
                      "fully consumed selected stock scoped loft", p,
                      p.get("lofted") is True and p.get("operation") == "cut"
                      and p.get("scoped_to_bodies") == [host + ":ConsumedStock"]
                      and p.get("outside_body_changes") == []
                      and _near(p.get("volume_delta_cm3"), -0.12, 0.00001)
                      and p.get("result_bodies") == ["ConsumedStock"]))
            rows.append(("design_get", {"include": ["tree"], "component": host,
                                        "tree_bodies": True, "tree_handles": True},
                         lambda p: (lambda bodies: _measured(
                             "fully cut source retains its identity with zero material",
                             bodies, len(bodies) == 4
                             and sum(b.get("name") == "ConsumedStock"
                                     and b.get("handle") == _RECALL.get("loft_consumed_handle")
                                     for b in bodies) == 1))(
                                 ((p.get("tree") or {}).get("tree") or {}).get("bodies", [])), None))
            rows.append(("model_inspect", lambda c: {
                "target": _ctx_get(c, "loft_consumed_handle", "consumed stock identity"),
                "include": ["default", "mass"], "units": "mm", "accuracy": "very_high"},
                _loft_consumed_public, None))
            for owner, role, expected in (roles[1], roles[3]):
                rows.append(("model_inspect", {"target": f"{owner}:{role}",
                                               "include": ["default", "mass"],
                                               "units": "cm", "accuracy": "very_high"},
                             _loft_scoped_body("consumed", "after", role, expected,
                                               f"loft_cut_before_{role}"), None))

            box(host, "SplitStock", (-10, -2, 10), (10, 2, 20))
            rows.append(("model_inspect", _combine_inspect(host + ":SplitStock"),
                         _combine_body("loft stock before split", (-10, -2, 10),
                                       (10, 2, 20), 800), None))
            write("model_loft", {"profiles": [{"sketch": "LoftBase", "profile_index": 0},
                                              {"sketch": "LoftTop", "profile_index": 0}],
                                 "component": host, "operation": "cut",
                                 "target_bodies": ["SplitStock"]},
                  lambda p, host=host: _measured(
                      "selected stock split into two attributed result bodies", p,
                      p.get("lofted") is True and p.get("operation") == "cut"
                      and p.get("scoped_to_bodies") == [host + ":SplitStock"]
                      and p.get("outside_body_changes") == []
                      and len(p.get("result_bodies") or []) == 2
                      and "volume_delta_cm3" not in p),
                  ("loft_split_names", _recall("loft_split_names", lambda p: p["result_bodies"])))
            rows.append(("design_get", {"include": ["tree"], "component": host,
                                        "tree_bodies": True, "tree_handles": True},
                         lambda p: (lambda bodies, names: _measured(
                             "split result names independently present in host census",
                             {"tree": bodies, "results": names},
                             len(bodies) == 6 and len(names) == 2
                             and len(set(names)) == 2
                             and set(names) <= {b.get("name") for b in bodies}
                             and sum(b.get("name") == "ConsumedStock"
                                     and b.get("handle") == _RECALL.get("loft_consumed_handle")
                                     for b in bodies) == 1))(
                                 ((p.get("tree") or {}).get("tree") or {}).get("bodies", []),
                                 _RECALL.get("loft_split_names") or []), None))
            for index in range(2):
                rows.append(("model_inspect", lambda c, index=index, host=host: {
                    **_combine_inspect(host + ":" + _ctx_get(
                        c, "loft_split_names", "split loft result bodies")[index])},
                    _loft_split_fragment(index, "loft_split_first_side" if index else None),
                    ("loft_split_first_side", _recall("loft_split_first_side", lambda p:
                        -1 if p["max_point"]["x"] < 0 else 1)) if index == 0 else None))
            for owner, role, expected in (roles[1], roles[3]):
                rows.append(("model_inspect", {"target": f"{owner}:{role}",
                                               "include": ["default", "mass"],
                                               "units": "cm", "accuracy": "very_high"},
                             _loft_scoped_body("split", "after", role, expected,
                                               f"loft_cut_before_{role}"), None))
        rows.extend([
            ("doc_activate", lambda c, story=story, doc=doc: {
                "name": _ctx_get(c, story, "loft story"),
                "expect_document": _ctx_get(c, doc, "loft scratch")}, "ok", None),
            ("doc_close", lambda c, story=story, doc=doc: {
                "name": _ctx_get(c, doc, "loft scratch"), "save_changes": False,
                "expect_document": _ctx_get(c, story, "loft story")},
             _document_closed, None)])
    return rows


_LOFT_PARTICIPANTS = _loft_participants_rows()


def _loft_alignment_census(p):
    """Return host body identities and Loft timeline rows when both slices read."""
    bodies = ((p.get("tree") or {}).get("tree") or {}).get("bodies")
    timeline = (p.get("timeline") or {}).get("timeline")
    if not isinstance(bodies, list) or not isinstance(timeline, list):
        return None
    return {"bodies": sorted((b.get("name"), b.get("handle")) for b in bodies),
            "lofts": sorted((r.get("name"), r.get("health")) for r in timeline
                            if r.get("component") == "LoftEdgeAlign"
                            and r.get("type") == "LoftFeature")}


def _loft_alignment_face(p):
    """Return the source face's independent area, position and cylinder geometry."""
    row = (p.get("matches") or [{}])[0]
    return {key: row.get(key) for key in ("kind", "area", "position", "radius", "axis")}


def _loft_alignment_world(x, y):
    """Return the placed host's world query point in mm."""
    angle = math.radians(25)
    return [100 + math.cos(angle) * x - math.sin(angle) * y,
            50 + math.sin(angle) * x + math.cos(angle) * y, 0]


def _loft_alignment_rows():
    """Demonstrate open-edge alignment through owned-component public geometry reads."""
    rows = []
    host, decoy = "LoftEdgeAlign", "LoftEdgeDecoy"
    rows.append(("design_activate_component", {"occurrence": "root"}, "ok", None))
    rows.append(("model_create_component", {"name": host, "activate": True,
                                            "x": 100, "y": 50, "rotate_deg": 25},
                 _made_component, None))
    rows.append(("model_construction", {"kind": "plane", "plane": "xy",
                                         "offset": 30, "name": "LoftAlignTop"},
                 _datum_plane("xy"), None))
    rows.append(("design_activate_component", {"occurrence": "root"}, "ok", None))
    rows.append(("model_create_component", {"name": decoy, "activate": True},
                 _made_component, None))
    rows.extend([
        ("sketch_create", {"plane": "xy", "name": "LoftAlignWitnessS"}, "ok", None),
        ("sketch_add_geometry", {"sketch_name": "LoftAlignWitnessS", "geometry": [
            {"kind": "rectangle", "x1": 3000, "y1": 3000, "x2": 3010, "y2": 3010}]},
         "ok", None),
        ("model_extrude", {"sketch_name": "LoftAlignWitnessS", "distance": 10},
         _extruded, ("la_witness", lambda p: p["result_bodies"][0])),
        ("model_inspect", lambda c: {"target": decoy + ":" +
             _ctx_get(c, "la_witness", "Loft witness"), "include": ["mass"], "units": "cm"},
         lambda p: _measured("unrelated Loft witness before alignment",
                             (p.get("mass") or {}).get("volume"),
                             _near((p.get("mass") or {}).get("volume"), 1.0, 0.001)), None),
    ])

    cases = (("start_g1_free", 2600, "start", "tangent", "free", 322.7386),
             ("start_g1_edges", 2660, "start", "tangent", "align_edges", 346.3860),
             ("end_g2_free", 2720, "end", "smooth", "free", 321.6790),
             ("end_g2_surface", 2780, "end", "smooth", "align_surface", 347.9951))
    for label, x, side, condition, alignment, expected_area in cases:
        source, target = label + "Source", label + "Target"
        source_key, edge_key, loft_key = label + "Body", label + "Edge", label + "Loft"
        shape_key = label + "SourceShape"
        rows.extend([
            ("design_activate_component", {"occurrence": host + ":1"}, "ok", None),
            ("sketch_create", {"plane": "xy", "name": source}, "ok", None),
            ("sketch_add_geometry", {"sketch_name": source, "component": host,
                                      "geometry": [{"kind": "arc", "cx": x, "cy": 1,
                                                    "x1": x + 8, "y1": 1,
                                                    "sweep_deg": 90}]}, "ok", None),
            ("model_extrude", {"sketch_name": source, "component": host,
                               "distance": -10, "as_surface": True},
             lambda p: p.get("is_solid") is False and len(p.get("result_bodies") or []) == 1,
             (source_key, lambda p: p["result_bodies"][0])),
            ("find_geometry", lambda c, key=source_key: {
                "target": host + ":" + _ctx_get(c, key, "alignment source body"),
                "kind": "cylinder_face", "units": "mm", "max_results": 1},
             lambda p: _measured("a single quarter-cylinder source face before Loft",
                                  p.get("matches"), p.get("match_count") == 1
                                  and _near((p["matches"][0]).get("area"), 125.664, 0.5)),
             (shape_key, _recall(shape_key, _loft_alignment_face))),
            ("find_geometry", lambda c, key=source_key, near=x: {
                "target": host + ":" + _ctx_get(c, key, "alignment source body"),
                "kind": "arc_edge", "radius": 8,
                "nearest_to": _loft_alignment_world(near + 6, 7),
                "units": "mm", "max_results": 1},
             lambda p: _measured("one top connected arc edge", p.get("matches"),
                                  p.get("match_count") == 2 and p.get("returned") == 1
                                  and _near((p["matches"][0]).get("length"), 12.566, 0.05)
                                  and _near(((p["matches"][0]).get("position") or
                                             [None, None, None])[2], 0, 0.05)),
             _fg(edge_key)),
            ("sketch_create", {"plane": "LoftAlignTop", "name": target}, "ok", None),
            ("sketch_add_geometry", {"sketch_name": target, "component": host,
                                      "geometry": [{"kind": "arc", "cx": x + 5, "cy": 1,
                                                    "x1": x + 11, "y1": 1,
                                                    "sweep_deg": 90}]}, "ok", None),
            ("design_activate_component", {"occurrence": decoy + ":1"}, "ok", None),
            ("model_loft", lambda c, s=side, cond=condition, mode=alignment,
                           edge=edge_key, target=target: {
                "profiles": ([_ctx_get(c, edge, "connected source edge"), target + "/arc:0"]
                             if s == "start" else
                             [target + "/arc:0", _ctx_get(c, edge, "connected source edge")]),
                "component": host, "as_surface": True, "operation": "new",
                s: cond, s + "_alignment": mode},
             lambda p, s=side, cond=condition, mode=alignment: _measured(
                 "owned open-edge Loft control", p,
                 p.get("lofted") is True and p.get("is_solid") is False
                 and p.get("section_kinds") == (["open_edge", "curve"] if s == "start"
                                                  else ["curve", "open_edge"])
                 and (p.get("ends") or {}).get(s) == cond
                 and p.get(s + "_alignment") == mode
                 and len(p.get("result_bodies") or []) == 1),
             (loft_key, lambda p: {"feature": host + "/" + p["feature"],
                                   "body": host + ":" + p["result_bodies"][0]})),
            ("design_get", lambda c, key=loft_key: {
                "include": ["definition"],
                "feature": _ctx_get(c, key, "aligned Loft")["feature"]},
             lambda p, s=side, mode=alignment: _measured(
                 "Loft definition in its source component", p.get("definition"),
                 (p.get("definition") or {}).get("component") == host
                 and (p.get("definition") or {}).get("section_count") == 2
                 and (p.get("definition") or {}).get(s + "_alignment") == mode
                 and (p.get("definition") or {}).get("is_solid") is False), None),
            ("find_geometry", lambda c, key=loft_key: {
                "target": _ctx_get(c, key, "aligned Loft")["body"],
                "kind": "nurbs_face", "units": "mm", "max_results": 1},
             lambda p, want=expected_area, mode=alignment, s=side: _measured(
                 "aligned Loft body area independently differs from Free",
                 p.get("matches"), p.get("match_count") == 1
                 and _near((p["matches"][0]).get("area"), want, 5)
                 and (mode == "free" or
                      (p["matches"][0]).get("area", 0) >
                      _RECALL.get(s + "_free_area", float("inf")) + 15)),
             ((side + "_free_area", _recall(side + "_free_area",
               lambda p: p["matches"][0]["area"])) if alignment == "free" else None)),
            ("model_measure_continuity", lambda c, edge=edge_key, key=loft_key: {
                "edges": [_ctx_get(c, edge, "connected source edge")],
                "against": _ctx_get(c, key, "aligned Loft")["body"],
                "samples": 9, "units": "mm"},
             lambda p, cond=condition: _measured(
                 "nine sampled points on the connected Loft seam", p.get("edges"),
                 len(p.get("edges") or []) == 1
                 and (p["edges"][0]).get("samples") == 9
                 and _num((p["edges"][0]).get("max_gap"))
                 and p["edges"][0]["max_gap"] < 0.02
                 and _num((p["edges"][0]).get("max_normal_angle_deg"))
                 and p["edges"][0]["max_normal_angle_deg"] < 0.5
                 and (cond != "smooth" or
                      (_num((p["edges"][0]).get("max_curvature_jump"))
                       and p["edges"][0]["max_curvature_jump"] < 0.01))), None),
            ("find_geometry", lambda c, key=source_key: {
                "target": host + ":" + _ctx_get(c, key, "alignment source body"),
                "kind": "cylinder_face", "units": "mm", "max_results": 1},
             lambda p, key=shape_key: _measured("original connected sheet remains unchanged",
                                  p.get("matches"), p.get("match_count") == 1
                                  and _loft_alignment_face(p) == _RECALL.get(key)
                                  and _near((p["matches"][0]).get("area"), 125.664, 0.5)), None),
        ])
    rows.extend([
        ("design_get", {"include": ["tree", "timeline"], "component": host,
                        "tree_bodies": True, "tree_handles": True, "max_results": 2000},
         lambda p: _measured("alignment guard baseline census", _loft_alignment_census(p),
                             _loft_alignment_census(p) is not None),
         ("la_guard_census", _recall("la_guard_census", _loft_alignment_census))),
        ("model_loft", lambda c: {"profiles": ["end_g2_surfaceTarget/arc:0",
                            _ctx_get(c, "end_g2_surfaceEdge", "connected source edge")],
                            "component": host, "as_surface": True, "end": "smooth",
                            "start_alignment": "align_edges"},
         _refused("start_alignment"), None),
        ("design_get", {"include": ["tree", "timeline"], "component": host,
                        "tree_bodies": True, "tree_handles": True, "max_results": 2000},
         lambda p: _measured("invalid alignment left feature and body census unchanged",
                             _loft_alignment_census(p),
                             _loft_alignment_census(p) is not None
                             and _loft_alignment_census(p) == _RECALL.get("la_guard_census")), None),
    ])
    rows.extend([
        ("model_inspect", lambda c: {"target": decoy + ":" +
             _ctx_get(c, "la_witness", "Loft witness"), "include": ["mass"], "units": "cm"},
         lambda p: _measured("unrelated Loft witness still has its original volume",
                             (p.get("mass") or {}).get("volume"),
                             _near((p.get("mass") or {}).get("volume"), 1.0, 0.001)), None),
        ("design_activate_component", {"occurrence": "root"}, "ok", None),
    ])
    return rows


_LOFT_ALIGNMENT = _loft_alignment_rows()
