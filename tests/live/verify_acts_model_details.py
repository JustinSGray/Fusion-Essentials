# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""The model detail act and its read-back predicates."""


from verify_core import (
    EXPORT_DIR, _RECALL, _axis_aligned_face_at, _box, _chamfered, _ctx_get, _cut_a_chain, _cut_exactly, _marker_parked_after, _datum_plane, _extent_measured, _extruded, _fg, _fgn, _filleted, _full_rounded, _holes_recognized, _holes_windowed, _made_component, _made_component_inactive, _matched, _measured, _mirrored, _moved, _near, _needs, _offset_faces, _param_added, _param_deleted, _param_set_to, _path_count, _piped, _pocket_boss, _pockets_recognized, _prof, _recall, _recognized_cbore_walls, _recognized_pocket_floor, _refused, _shelled, _split_bodies, _unless, _watch)
from verify_acts_cam import (
    MACHINING_EXTENSION)
from verify_layout import (
    _px, _py)


_SHOT_PATH = EXPORT_DIR + "/w4_shot"



from verify_acts_model_extrude_organization import (
    _BODY_ORGANIZATION, _EXTRUDE_EDITS)
from verify_acts_model_definition_operand import (
    _DATUM_OPERANDS, _DEFINITION_READS)
from verify_acts_model_precision import (
    _section_camera, _section_camera_unchanged, _section_census, _section_created, _section_named_clear)

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

