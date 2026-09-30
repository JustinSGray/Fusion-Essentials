# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""The model solid creation act and its read-back predicates."""

import math

from verify_core import (
    _RECALL, _chamfered, _component_metadata, _ctx_get, _cut_on_its_pivot, _datum, _datum_plane, _drafted, _drafted_on_its_pivot, _drafted_symmetric, _drilled, _extent_measured, _extruded, _face_up_at, _fg, _fgn, _filleted, _gap_measured, _home_document, _joint_origin_at, _lofted, _made_component, _material_assigned, _matched, _measured, _metadata_set, _mirrored, _moved_occurrence, _captured, _near, _needs, _num, _offset_faces, _param_read, _param_traced, _patterned, _prof, _recall, _refused, _relation_measured, _relation_passes, _relation_read, _replaced_on_its_pivot, _sits_on_a_face, _swept, _unless, _watch)
from verify_acts_cam import (
    MACHINING_EXTENSION)
from verify_layout import (
    _px, _py)





from verify_acts_model_combine_revolve import (
    _COMBINE_COMPLETE, _COMBINE_NONE, _COMBINE_NONROOT_PARTIAL, _COMBINE_PARTIAL, _REVOLVE_PARTICIPANTS, _combine_story_address)
from verify_acts_model_extrude_organization import (
    _extrude_edit_dependent)
from verify_acts_model_precision import (
    _FINE_ANGLE_DEG, _HOLE_ACTIVE, _HOLE_ACTIVE_X0, _HOLE_HOST, _HOLE_VOLUME, _HOLE_X0, _PRECISION_READS, _control_top_args, _fine_angle_param, _fine_angle_plane, _hole_active_handle, _hole_active_tree, _hole_body_state, _hole_created, _hole_cylinder_args, _hole_cylinders, _hole_face_bounds, _hole_host_tree, _hole_inspect_args, _hole_lower_handle, _hole_timeline, _hole_upper_handle, _radius_body_size, _radius_filtered_handle, _scoped_bore_args, _scoped_hole_args, _scoped_top_args, _sweep_brep_list_edited, _sweep_dependent_survived, _sweep_edit_at_volume, _sweep_inspected_at_volume, _unscoped_hole_args)
from verify_acts_model_sweep import (
    _LATER_OPERAND, _LOFT_ALIGNMENT, _LOFT_EDITOR, _LOFT_PARTICIPANTS, _SOLID_TOOL,
    _SWEEP_EDIT_MODES, _rolled_back_body)

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
    ("sketch_create", {"plane": "xz", "name": "SweepPathDown"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 250, "y1": 0,
                                           "x2": 250, "y2": 50}],
                             "sketch_name": "SweepPathDown"}, "ok", None),
    ("sketch_create", {"plane": "xy", "name": "SweepBasePocket"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "circle", "cx": 255, "cy": 0, "radius": 1}],
                             "sketch_name": "SweepBasePocket"}, "ok", None),
    ("sketch_create", {"plane": "xz", "name": "SweepPathSide"}, "ok", None),
    ("sketch_add_geometry", {"geometry": [{"kind": "line", "x1": 260, "y1": 0,
                                           "x2": 260, "y2": -50}],
                             "sketch_name": "SweepPathSide"}, "ok", None),
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
     ("sweep_edit_body", _recall("sweep_edit_body", lambda p: p["result_bodies"][0]))),
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
    # A pocket up into the start cap. A downward path leaves it cutting air, so the new warning
    # fails the check and the prior path curve is swept again.
    ("model_extrude", lambda c: {"sketch_name": "SweepBasePocket", "distance": 2, "operation": "cut",
                                 "target_bodies": ["SweepCameo:" + _ctx_get(c, "sweep_edit_body",
                                                                            "sweep body")]},
     _extruded, ("sweep_base_pocket", _recall("sweep_base_pocket", lambda p: p["feature"]))),
    ("model_inspect", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_edit_body", "sweep body"),
                                 "include": ["mass"], "units": "cm"},
     _sweep_inspected_at_volume(math.pi * 0.8 ** 2 * 5 - math.pi * 0.1 ** 2 * 0.2),
     ("sweep_pocketed_volume", _recall("sweep_pocketed_volume", lambda p: p["mass"]["volume"]))),
    # The restored path sweeps the prior shape into a body of a new name and identity.
    ("model_edit_sweep", {"feature": "SweepCameo/Sweep1", "action": "path",
                          "path": "sketch:SweepPathDown"},
     _refused("New evaluated timeline errors or warnings",
              "It was rolled back and re-read: path reads SweepPath/line:0 again; the body shapes "
              "match the pre-edit read. The body now reads as '",
              "; re-read names and handles held for it."), None),
    ("model_inspect", {"target": "SweepCameo:1", "include": ["mass"], "units": "cm", "per_body": True},
     *_rolled_back_body("sweep_pocketed_volume", "sweep_edit_body", renamed=True)),
    ("model_inspect", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_edit_body", "sweep body"),
                                 "include": ["mass"], "units": "cm"},
     lambda p: _measured("rolled-back sweep volume", (p.get("mass") or {}).get("volume"), _near(
         (p.get("mass") or {}).get("volume"), _RECALL["sweep_pocketed_volume"], 0.0001)), None),
    ("design_get", {"include": ["timeline"], "max_results": 2000},
     _extrude_edit_dependent("sweep_base_pocket", "SweepCameo", healthy=True), None),
    ("model_inspect", lambda c: {"target": _ctx_get(c, "sweep_dependent_handle", "dependent handle"),
                                 "include": ["default", "mass"], "units": "cm"},
     _sweep_dependent_survived(False), None),
    # A parallel straight path 10 mm to the side sweeps the same body: the edit lands, the bodies
    # read identical before and after, and the call succeeds saying so.
    ("model_inspect", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_edit_body", "sweep body"),
                                 "include": ["default", "mass"], "units": "cm"}, "ok",
     ("sweep_side_before", _recall("sweep_side_before", lambda p: {
         "volume": p["mass"]["volume"], "min_point": p["min_point"],
         "max_point": p["max_point"]}))),
    ("model_edit_sweep", {"feature": "SweepCameo/Sweep1", "action": "path",
                          "path": "sketch:SweepPathSide"},
     lambda p: _measured("identical-geometry path edit", {
         "edited": p.get("edited"), "geometry_changed": p.get("geometry_changed"),
         "operand_after": p.get("operand_after"), "note": p.get("note")},
         p.get("edited") is True and p.get("definition_matches") is True
         and p.get("geometry_changed") is False and p.get("outside_body_changes") == []
         and p.get("operand_after") == "SweepPathSide/line:0" and "rollback" not in p
         and "The body geometry reads identical before and after." in str(p.get("note"))), None),
    ("model_inspect", lambda c: {"target": "SweepCameo:" + _ctx_get(c, "sweep_edit_body", "sweep body"),
                                 "include": ["default", "mass"], "units": "cm"},
     lambda p: _measured("sweep body after the identical-geometry edit", {
         "volume": (p.get("mass") or {}).get("volume"), "min_point": p.get("min_point"),
         "max_point": p.get("max_point"), "before": _RECALL["sweep_side_before"]},
         _near((p.get("mass") or {}).get("volume"), _RECALL["sweep_side_before"]["volume"], 0.0001)
         and all(_near((p.get(corner) or {}).get(axis),
                       _RECALL["sweep_side_before"][corner][axis], 0.0001)
                 for corner in ("min_point", "max_point") for axis in "xyz")), None),
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
    *_LOFT_EDITOR,
    *_LATER_OPERAND,
    *_LOFT_PARTICIPANTS,
    *_LOFT_ALIGNMENT,
    *_SOLID_TOOL,
]
