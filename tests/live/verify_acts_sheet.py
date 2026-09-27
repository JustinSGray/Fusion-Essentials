# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""The sheet-metal coupon act in the existing live sweep."""

from pathlib import Path
import math
import time
import re

from cloud_config import FOLDER, PROJECT
from verify_acts_cam import _operation_row, _op_valid
from verify_acts_cloud import (_drawing_terminal, _drawing_terminal_payload,
                               _file_settled, _opened, _version_args, _version_record,
                               _version_settled, _version_snapshot, _versioned, _version_current)

from verify_core import (EXPORT_DIR, _RECALL, _ctx_get, _dwell, _extruded, _measured, facade,
                         _near, _recall, _refused)

_SEED = "SM Sweep Seed"
_SEED2 = "SM Sweep Second Seed"
_PART = "SM Sweep Blank"
_RULE = "SM Sweep Rule"
_BASE = "SM Sweep Base"
_SEED_BASE = "SM Sweep Seed Base"
_BEND = "SM Sweep Bend"
_BEND2 = "SM Sweep Second Bend"
_SLOT = "SM Sweep Cross Bend Slot"
_CAM_SETUP = "SM Sweep Laser Setup"
_CAM_OP = "SM Sweep Laser Perimeter"
_CAM_UNSELECTED = "SM Sweep Unfinished Path"
_MILL_SETUP = "SM Sweep Flat Mill Setup"
_MILL_OP = "SM Sweep Flat Mill Contour"
_LASER_LIBRARY = "systemlibraryroot://Samples/Cutting Tools (Metric)"
_STAMP = time.strftime("%Y%m%d-%H%M%S")
_DRAW_SOURCE = "SM Sweep Coupon " + _STAMP
_DRAW_KEY = "sm-sweep-drawing-" + _STAMP
_FLAT_TEMPLATE = "SM Sweep Flat " + _STAMP
_DXF = EXPORT_DIR + "/sm_sweep_flat.dxf"
_CUT_DXF = EXPORT_DIR + "/sm_sweep_cut.dxf"
_PDF = EXPORT_DIR + "/sm_sweep_drawing.pdf"
_PDF_KEY = "sm-sweep-pdf-" + _STAMP


def _ruled_component(p):
    """Require native sheet-metal component creation and an inherited rule."""
    return _measured("sheet component rule", {"component": p.get("component"),
                     "rule": p.get("active_sheet_metal_rule")},
                     p.get("sheet_metal") is True and p.get("component") == _SEED
                     and p.get("activated") is True
                     and bool(p.get("active_sheet_metal_rule")))


def _rule_settings(p):
    """Read copied rule values from the design-local collection."""
    rows = (p.get("rules") or {}).get("rules") or []
    matches = [r for r in rows if r.get("name") == _RULE]
    r = matches[0] if len(matches) == 1 else {}
    return _measured("design-local rule", {"matches": len(matches), "rule": r},
                     len(matches) == 1 and r.get("ref") == "design:" + _RULE
                     and _near((r.get("thickness") or {}).get("value_cm"), 0.15, 1e-6)
                     and _near((r.get("bendRadius") or {}).get("value_cm"), 0.2, 1e-6)
                     and _near((r.get("gap") or {}).get("value_cm"), 0.05, 1e-6)
                     and _near(r.get("k_factor"), 0.42, 1e-9))


def _seed_guard(p):
    """Check refusal preserved both the seed rule and its ordinary body."""
    rules = (p.get("rules") or {}).get("rules") or []
    components = (p.get("components") or {}).get("components") or []
    seed = [r for r in components if r.get("component") == _SEED]
    steel = [r for r in rules if r.get("name") == "Steel (mm)"]
    return _measured("ruled-component conversion refusal", {"seed": seed, "steel": steel},
                     len(seed) == 1 and len(steel) == 1
                     and len(seed[0].get("bodies") or []) == 1
                     and seed[0]["bodies"][0].get("is_sheet_metal") is False
                     and _near((steel[0].get("thickness") or {}).get("value_cm"), 0.25, 1e-6))


# addByCopy under a name already in use RAISES 'Invalid name, rule already exists' (measured live on
# 2706.0.97) and lands nothing, so the only way a same-named duplicate arises is Fusion's OWN copy on
# addNewSheetMetalComponent - the raw API, bypassing the tool's adoption entirely.
_DUP_STEEL_RULE_SCRIPT = '''import adsk.core, adsk.fusion

def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    occ = design.rootComponent.occurrences.addNewSheetMetalComponent(adsk.core.Matrix3D.create())
    print("added " + occ.name)
'''


def _rule_adopted_from_copy(p):
    """Require the tool's own before/after census to fold a fresh same-named copy into 'Steel (mm)'."""
    return _measured("sheet component rule adopted from a same-named copy",
                     {"active_rule": p.get("active_sheet_metal_rule"),
                      "adopted": p.get("rule_adopted_existing"),
                      "deleted": p.get("rule_copy_deleted")},
                     p.get("sheet_metal") is True and p.get("rule_adopted_existing") is True
                     and p.get("rule_copy_deleted") is True
                     and p.get("active_sheet_metal_rule") == "Steel (mm)")


def _design_rule_count_after_adopt(p):
    """Require the design rule count unchanged from before the adopt, with exactly one 'Steel (mm)'."""
    rows = (p.get("rules") or {}).get("rules") or []
    before = _RECALL.get("sm_rule_count_before_adopt")
    steel = [r for r in rows if r.get("name") == "Steel (mm)"]
    return _measured("design rule count unchanged after adoption",
                     {"before": before, "after": len(rows), "steel_count": len(steel)},
                     isinstance(before, int) and len(rows) == before and len(steel) == 1)


def _duplicate_steel_rows(p):
    """Require a direct-API duplicate name to read back as ordinal '#1'/'#2' refs with distinct indices."""
    rows = (p.get("rules") or {}).get("rules") or []
    dups = sorted([r for r in rows if r.get("name") == "Steel (mm)"], key=lambda r: r.get("ref") or "")
    return _measured("duplicate Steel (mm) rows carry ordinal refs", {"rows": dups},
                     len(dups) == 2 and dups[0].get("ref") == "design:Steel (mm)#1"
                     and dups[1].get("ref") == "design:Steel (mm)#2"
                     and isinstance(dups[0].get("index"), int) and isinstance(dups[1].get("index"), int)
                     and dups[0]["index"] != dups[1]["index"])


def _second_dup_gap_updated(p):
    """Require the '#2' ordinal ref to resolve and land its own gap edit."""
    row = p.get("rule") or {}
    return _measured("duplicate rule '#2' gap update", {"rule": row, "applied": p.get("applied")},
                     p.get("action") == "update" and row.get("ref") == "design:Steel (mm)#2"
                     and _near((row.get("gap") or {}).get("value_cm"), 0.06, 1e-6)
                     and "gap" in (p.get("applied") or []))


def _dup_gap_isolated(p):
    """Require only the edited '#2' duplicate's gap to have moved; '#1' stays off that value."""
    rows = (p.get("rules") or {}).get("rules") or []
    by_ref = {r.get("ref"): r for r in rows if r.get("name") == "Steel (mm)"}
    r1, r2 = by_ref.get("design:Steel (mm)#1"), by_ref.get("design:Steel (mm)#2")
    return _measured("only the edited duplicate's gap moved", {"r1": r1, "r2": r2},
                     r1 is not None and r2 is not None
                     and _near((r2.get("gap") or {}).get("value_cm"), 0.06, 1e-6)
                     and not _near((r1.get("gap") or {}).get("value_cm"), 0.06, 1e-6))


def _top_match(p, area):
    """Select the upward broad face by measured area and normal."""
    matches = [m for m in (p.get("matches") or [])
               if m.get("kind") == "planar_face" and (m.get("area") or 0) > area
               and (m.get("normal") or [0, 0, 0])[2] > 0.99]
    return matches[0] if len(matches) == 1 else None


def _top_face(area):
    """Require one broad upward planar face independent of face order."""
    def check(p):
        m = _top_match(p, area)
        return _measured("sheet broad top face", {"top": m, "count": len(p.get("matches") or [])},
                         m is not None and bool(m.get("handle")))
    return check


def _top_handle(area):
    """Extract the verified broad face's handle."""
    return ("sm_top", lambda p: _top_match(p, area)["handle"])


def _line_match(p, x=25):
    """Find one vertical 40 mm bend line at the requested local x."""
    matches = []
    for row in p.get("entities") or []:
        if row.get("type") != "line":
            continue
        a, b = row.get("start") or {}, row.get("end") or {}
        if (_near(a.get("x"), x, 0.01) and _near(b.get("x"), x, 0.01)
                and sorted([round(a.get("y", -999), 2), round(b.get("y", -999), 2)]) == [0.0, 40.0]):
            matches.append(row)
    return matches[0] if len(matches) == 1 else None


def _bend_line(p, x=25):
    """Require a unique intended line despite auto-projected boundary curves."""
    line = _line_match(p, x)
    return _measured("one intended bend line", {"line": line,
                     "line_count": len([e for e in p.get("entities") or []
                                        if e.get("type") == "line"])},
                     line is not None and bool(line.get("id")))


def _converted(p):
    """Require actual sheet state and applied thickness, not requested-rule echo."""
    return _measured("converted sheet body", {"applied": p.get("applied_rule"),
                     "thickness_cm": p.get("applied_rule_thickness_cm")},
                     p.get("converted") is True and bool(p.get("applied_rule_ref"))
                     and _near(p.get("measured_blank_thickness_cm"), 0.15, 1e-6)
                     and _near(p.get("applied_rule_thickness_cm"), 0.15, 1e-6))


def _sheet_body(p):
    """Read sheet ownership independently of conversion's return payload."""
    rows = (p.get("components") or {}).get("components") or []
    matches = [r for r in rows if r.get("component") == _PART]
    row = matches[0] if len(matches) == 1 else {}
    bodies = row.get("bodies") or []
    return _measured("sheet body census", {"component": row},
                     len(matches) == 1 and row.get("active_rule") == _RECALL.get("sm_applied")
                     and len(bodies) == 1 and bodies[0].get("is_sheet_metal") is True)


def _folded(p):
    """Require a landed 90-degree fold and changed body topology."""
    return _measured("folded coupon", {"feature": p.get("feature"),
                     "angle": p.get("angle_deg"), "faces": (p.get("faces_before"), p.get("faces_after"))},
                     p.get("created") is True and bool(p.get("feature"))
                     and _near(p.get("angle_deg"), 90, 1e-5)
                     and isinstance(p.get("faces_before"), int)
                     and isinstance(p.get("faces_after"), int)
                     and p["faces_after"] > p["faces_before"])


def _formed_extent(p):
    """Require the formed body to leave its former 1.5 mm slab plane."""
    return _measured("formed height", {"z_mm": p.get("z")},
                     isinstance(p.get("z"), (int, float)) and p["z"] > 10)


def _flat(p):
    """Require one nonempty flat associated with the source part."""
    return _measured("flat coupon", {"component": p.get("component"),
                     "source": p.get("folded_body"), "volume": p.get("flat_volume_cm3")},
                     p.get("created") is True and p.get("component") == _PART
                     and p.get("is_solid") is True
                     and _near(p.get("flat_volume_cm3"), 4.8, 0.02))


def _flat_census(p):
    """Read the component's flat presence independently of creation."""
    rows = (p.get("components") or {}).get("components") or []
    matches = [r for r in rows if r.get("component") == _PART]
    return _measured("flat installed", {"matches": matches},
                     len(matches) == 1 and matches[0].get("has_flat_pattern") is True)


def _dxf(p, slotted=False):
    """Inspect the landed flat DXF's closed outline, units and bend entities."""
    path = Path(p.get("file_path") or "")
    lines = path.read_text(encoding="latin-1", errors="ignore").splitlines() if path.is_file() else []
    pairs = [(lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]
    unit = next((pairs[i + 1][1] for i, pair in enumerate(pairs[:-1])
                 if pair == ("9", "$INSUNITS")), None)
    entities, current = [], None
    for code, value in pairs:
        if code == "0":
            if current is not None:
                entities.append(current)
            current = {"type": value, "props": []}
        elif current is not None:
            current["props"].append((code, value))
    if current is not None:
        entities.append(current)
    def layer(row):
        return next((value for code, value in row["props"] if code == "8"), None)
    outer = [row for row in entities if row["type"] == "LWPOLYLINE"
             and layer(row) == "OUTER_PROFILES"]
    inner = [row for row in entities if row["type"] == "LWPOLYLINE"
             and layer(row) == "INTERIOR_PROFILES"]
    slot = inner[0]["props"] if len(inner) == 1 else []
    slot_x = [float(v) for c, v in slot if c == "10"]
    slot_y = [float(v) for c, v in slot if c == "20"]
    bulges = [float(v) for c, v in slot if c == "42"]
    slot_ok = (len(inner) == 1 and any(c == "70" and int(v) & 1 for c, v in slot)
               and sorted(slot_x) == [50.0, 50.0, 60.0, 60.0]
               and sorted(slot_y) == [18.0, 18.0, 22.0, 22.0]
               and len(bulges) == 2 and all(_near(abs(v), 1, 1e-6) for v in bulges))
    bends = [row for row in entities if row["type"] == "LINE" and layer(row) == "BEND"]
    extents = [row for row in entities if row["type"] == "LINE"
               and layer(row) == "BEND_EXTENT"]
    poly = outer[0]["props"] if len(outer) == 1 else []
    xs = [float(value) for code, value in poly if code == "10"]
    ys = [float(value) for code, value in poly if code == "20"]
    flags = next((int(value) for code, value in poly if code == "70"), 0)
    return _measured("flat DXF entities", {"bytes": p.get("size_bytes"),
                     "insunits": unit, "outline_vertices": (xs, ys),
                     "closed": bool(flags & 1), "bends": len(bends),
                     "bend_extents": len(extents), "slot_verified": slot_ok},
                     p.get("exported") is True and p.get("size_bytes", 0) > 1000
                     and unit == "4" and len(outer) == 1 and bool(flags & 1)
                     and len(xs) == len(ys) == 4
                     and _near(max(xs) - min(xs), 80, 0.01)
                     and _near(max(ys) - min(ys), 40, 0.01)
                     and ((not bends and not extents and slot_ok) if slotted
                          else (len(bends) == 1 and len(extents) == 2 and not inner)))


def _unfolded(p):
    """Require the explicit bend faces to unfold with measured face movement before the cut."""
    return _measured("unfolded coupon", {"feature": p.get("feature"),
                     "faces": (p.get("faces_before"), p.get("faces_after"))},
                     p.get("created") is True and p.get("all_bends") is False
                     and (p.get("faces_moved") or 0) > 0)


def _fold_cylinders_check(p):
    """Require the coupon's one fold to answer exactly its inner and outer cylinder face."""
    rows = [m for m in (p.get("matches") or []) if m.get("kind") == "cylinder_face"]
    return _measured("fold cylinder faces", {"count": len(rows), "match_count": p.get("match_count")},
                     len(rows) == 2)


def _fold_cylinder_handles(p):
    return [m["handle"] for m in (p.get("matches") or []) if m.get("kind") == "cylinder_face"]


def _slot_volume(p):
    """Measure removal against the folded pre-cut component volume."""
    before = _RECALL.get("sm_before_slot_volume")
    after = (p.get("mass") or {}).get("volume")
    return _measured("cross-bend slot removed material", {"before_mm3": before,
                     "after_mm3": after},
                     isinstance(before, (int, float)) and isinstance(after, (int, float))
                     and 50 < before - after < 110)


def _refolded(p, source_key="sm_unfold"):
    """Require refold to bind the recalled unfold and move its faces."""
    source = _RECALL.get(source_key)
    return _measured("refolded coupon", {"feature": p.get("feature"),
                     "unfold": p.get("unfold"), "source": source,
                     "faces": (p.get("faces_before"), p.get("faces_after"))},
                     p.get("created") is True and p.get("unfold") == source
                     and (p.get("faces_moved") or 0) > 0)


def _cutting_setup(p):
    """Verify the cutting setup accepted one flat from the folded source."""
    return _measured("flat cutting setup", {"name": p.get("setup_name"),
                     "type": p.get("operation_type"), "flat_sources": p.get("flat_sources")},
                     p.get("created") is True and p.get("setup_name") == _CAM_SETUP
                     and p.get("operation_type") == "cutting"
                     and p.get("flat_models_verified") is True
                     and p.get("model_count") == 1
                     and len(p.get("flat_sources") or []) == 1)


def _cutting_setup_read(p):
    """Read cutting type and selected flat model from the CAM setup census."""
    rows = p.get("setups") or []
    matches = [row for row in rows if row.get("name") == _CAM_SETUP]
    row = matches[0] if len(matches) == 1 else {}
    return _measured("CAM cutting setup readback", {"matches": matches},
                     len(matches) == 1 and row.get("operation_type") == "JetOperation"
                     and bool(_RECALL.get("sm_machine"))
                     and row.get("machine") == _RECALL["sm_machine"]
                     and len(row.get("selected_models") or []) == 1)


def _cutting_fit_frames_flat(p):
    """Verify a cutting fit frames the flat model, not the folded source's own footprint - the
    flat's own 80 mm developed width (_dxf, already verified) is the discriminating span, checked
    beside the camera's own read-back target landing on the fit box's centre."""
    box = p.get("fit_box_cm") or {}
    lo, hi = box.get("min"), box.get("max")
    span = max(hi[0] - lo[0], hi[1] - lo[1]) if lo and hi else None
    center = [(lo[i] + hi[i]) / 2 for i in range(3)] if lo and hi else None
    target = p.get("camera_target_cm")
    on_center = (center is not None and target is not None
                and all(abs(target[i] - center[i]) <= 0.1 for i in range(3)))
    return _measured("cutting fit frames the flat model", {"fitted_to": p.get("fitted_to"),
                     "fit_box_cm": box, "xy_span_cm": span,
                     "camera_target_cm": target, "fit_box_center_cm": center},
                     p.get("fitted_to") == "model" and span is not None and span >= 7.0
                     and on_center)


def _laser_inspected(p):
    """Require the scoped path to be valid and cut material."""
    measured = p.get("measured") or {}
    states = measured.get("states") or {}
    return _measured("nonempty flat laser path", {"passed": p.get("passed"),
                     "measured": measured},
                     p.get("passed") is True and measured.get("empty_toolpath_count") == 0
                     and states.get("valid", 0) >= 1)


def _laser_posted(p, as_is=False, scope="setup"):
    """Verify the shipped laser post wrote a nonempty NC artifact."""
    files = p.get("files") or []
    return _measured("laser post artifact", {"post": p.get("post_config"),
                     "files": files, "posted_operations": p.get("posted_operations")},
                     p.get("posted") is True and p.get("partial") is not True
                     and not p.get("failed_stubs") and not p.get("program_error")
                     and ((p.get("scope") == "as_is" and p.get("mode") == "as_is") if as_is
                          else p.get("scope") == scope and p.get("post_scope") == "fusion")
                     and p.get("posted_operations") == 1
                     and p.get("flat_models_refreshed") == 1
                     and p.get("flat_setups_regenerated") == 1
                     and p.get("flat_operations_ready") == 1
                     and p.get("file_count") == len(files) and len(files) >= 1
                     and all(f.get("size_bytes", 0) > 0 for f in files))



def _laser_feed_value(p, operation=_CAM_OP, setup_name=_CAM_SETUP):
    """Read the single coupon operation's cutting distance in millimeters."""
    rows = (p.get("time") or {}).get("setups") or []
    setup = [r for r in rows if r.get("setup") == setup_name]
    ops = [r for r in (setup[0].get("operations") or []) if r.get("operation") == operation] if len(setup) == 1 else []
    return ops[0].get("feed_distance") if len(ops) == 1 and p["time"].get("units") == "mm" else None


def _unselected_path_untouched(p):
    """Require the selected path to be current while its unfinished sibling stays ungenerated."""
    sibling = _operation_row(p, _CAM_SETUP, _CAM_UNSELECTED) or {}
    return _op_valid(_CAM_SETUP, _CAM_OP)(p) and _measured(
        "unselected operation stays ungenerated", sibling,
        sibling.get("has_toolpath") is False and sibling.get("state") != "valid")


def _laser_feed(p, width_delta=None, operation=_CAM_OP):
    """Require the perimeter to gain twice the blank's width change."""
    feed = _laser_feed_value(p, operation)
    baseline = _RECALL.get("sm_feed_baseline")
    return _measured("source width reaches cutting path", {"feed_mm": feed,
                     "baseline_mm": baseline, "width_change_mm": width_delta},
                     isinstance(feed, (int, float)) and feed > 200
                     and (width_delta is None or isinstance(baseline, (int, float))
                          and _near(feed - baseline, 2 * width_delta, 0.11)))


def _stale_after_widen(p):
    """Verify a synced read catches the widened flat as out-of-date, never falsely ready."""
    rows = (p.get("operations") or {}).get("setups") or []
    row = rows[0] if len(rows) == 1 else {}
    summary = row.get("summary") or {}
    states = summary.get("states") or {}
    return _measured("cutting setup reads stale after a design change", {
                     "states": states, "validity_synced": summary.get("validity_synced"),
                     "readiness": summary.get("readiness")},
                     row.get("setup") == _CAM_SETUP and states.get("out_of_date") == 1
                     and summary.get("validity_synced") is True
                     and "ready to post" not in (summary.get("readiness") or ""))


def _flat_template_path(p):
    """Check the created operation's native state and resized cutting distance."""
    operation = _RECALL["sm_flat_applied"]["operation"]
    return _op_valid(_CAM_SETUP, operation)(p) and _laser_feed(p, 10, operation)


def _flat_template_applied(p):
    """Require one generated flat operation and one identifiable library fork."""
    forked = (p.get("library_tools") or {}).get("forked") or []
    return _measured("flat template generation", p,
                     p.get("applied") is True and p.get("generation_mode") == "generate"
                     and p.get("flat_models_refreshed") == 1 and p.get("created_count") == 1
                     and len(p.get("created_operations") or []) == 1
                     and len(forked) == 1 and isinstance(forked[0].get("index"), int))


def _flat_generation_settled(p, empty=False, target=None):
    """Poll the owned generation within a bound and return its final status."""
    args = ({"handle": _RECALL["sm_empty_generation"]} if empty else
            {"target": target or _RECALL["sm_flat_applied"]["operation"]})
    for attempt in range(18):
        states = p.get("live_states") or {}
        settled = p.get("completed") is True and (empty or states.get("valid") == 1)
        if settled or states.get("errored") or attempt == 17:
            return p
        time.sleep(1.0)
        failed, p = facade("call")("cam_get_status", args)
        if failed or not isinstance(p, dict):
            raise AssertionError(f"Flat generation status unavailable: {p!r}")
    return p


def _flat_template_generated(p):
    """Require the applied operation's settled, nonempty native path."""
    p = _flat_generation_settled(p)
    return _measured("flat template current path", p,
                     p.get("completed") is True and (p.get("live_states") or {}).get("valid") == 1
                     and p.get("empty_toolpaths") == [])


def _mill_generated(p):
    """Require a current nonempty path on the converted flat milling setup."""
    p = _flat_generation_settled(p, target=_MILL_OP)
    return _measured("flat milling generation", p,
                     p.get("completed") is True and (p.get("live_states") or {}).get("valid") == 1
                     and p.get("empty_toolpaths") == [])


def _laser_generated(p):
    """Require the laser perimeter's settled, nonempty native path before the fit reads it."""
    p = _flat_generation_settled(p, target=_CAM_OP)
    return _measured("laser perimeter generation", p,
                     p.get("completed") is True and (p.get("live_states") or {}).get("valid") == 1
                     and p.get("empty_toolpaths") == [])


def _mill_feed(p, width_delta=None):
    """Require source width changes to reach the developed milling contour."""
    feed = _laser_feed_value(p, _MILL_OP, _MILL_SETUP)
    baseline = _RECALL.get("sm_mill_feed_baseline")
    return _measured("flat milling width reaches path", {"feed_mm": feed,
                     "baseline_mm": baseline, "width_change_mm": width_delta},
                     isinstance(feed, (int, float)) and feed > 250
                     and (width_delta is None or isinstance(baseline, (int, float))
                          and _near(feed - baseline, 2 * width_delta, 0.11)))


def _created_empty_path(p):
    """Require the generated unselected contour to stay current and explicitly empty."""
    p = _flat_generation_settled(p, empty=True)
    states = p.get("live_states") or {}
    return _measured("unselected flat operation generation", p,
                     p.get("completed") is True and states.get("out_of_date") == 0
                     and p.get("empty_toolpaths") == [_CAM_UNSELECTED]
                     and (p.get("counts") or {}).get("empty_toolpaths") == 1)


def _width_dimension(p):
    """Require a driving 90 mm blank-width dimension and its parameter name."""
    rows = p.get("results") or []
    row = rows[0] if len(rows) == 1 else {}
    solved = row.get("solved") or []
    return _measured("driving blank width", row, p.get("dimensioned") == 1
                     and row.get("is_driving") is True and bool(row.get("parameter"))
                     and len(solved) == 1 and _near(solved[0].get("length_mm"), 90, 0.01))


def _width_set(width):
    """Set the captured blank-width parameter and verify its measured value."""
    return ("param_set", lambda c: {"name": _ctx_get(c, "sm_width", "blank width parameter"),
                                     "expression": f"{width} mm"},
            lambda p: _measured("blank width changed", p.get("after"),
                                p.get("set") is True and _near((p.get("after") or {}).get("value"), width, 0.01)), None)


def _home_session(p):
    """Capture the original unsaved story document's exact session handle."""
    active = p.get("active") or {}
    return _measured("story session before sheet coupon", active,
                     active.get("has_data_file") is False
                     and str(active.get("document_handle") or "").startswith("session:"))


def _coupon_session(p):
    """Require a separate active scratch design for the sheet fixture."""
    return _measured("isolated sheet coupon session", p,
                     p.get("created") is True and p.get("is_active") is True
                     and str(p.get("document_handle") or "").startswith("session:")
                     and p.get("document_handle") != _RECALL.get("sm_home"))


def _source_saved(p):
    """Read the coupon's new cloud lineage and its requested scratch destination."""
    return _measured("sheet coupon saved for drawing", p,
                     p.get("saved") is True and p.get("name") == _DRAW_SOURCE
                     and p.get("destination_folder") == FOLDER
                     and str(p.get("document_id") or "").startswith("urn:")
                     and not p.get("name_collision"))


def _source_session(p):
    """Verify the saved coupon remains the active source document."""
    active = p.get("active") or {}
    return _measured("saved coupon source session", active,
                     active.get("document_id") == _RECALL.get("sm_source_urn")
                     and active.get("document_handle") == _RECALL.get("sm_coupon")
                     and active.get("has_data_file") is True)


def _drawing_started(p):
    """Keep the exact accepted drawing job for the bounded status poll."""
    poll = p.get("poll") or {}
    return _measured("coupon drawing job accepted", p,
                     p.get("accepted") is True and p.get("status") == "accepted"
                     and p.get("request_key") == _DRAW_KEY and bool(p.get("job_id"))
                     and poll.get("tool") == "drawing_get_status"
                     and poll.get("request_key") == _DRAW_KEY)


def _drawing_complete(p):
    """Verify the exact deferred drawing job, cloud file, and applied flat options."""
    expected = {"standard": "iso", "units": "mm", "sheet_size": "a3",
                "sheet_types": ["flat_pattern", "folded_model"],
                "flat_isometric": True, "bend_table": True,
                "bend_table_location": "bottom_right",
                "expect_document": _RECALL.get("sm_source_session")}
    payload = _drawing_terminal(p, "sm_draw_job", _DRAW_KEY, "drawing_create", expected)
    applied = (payload or {}).get("flat_settings_applied") or {}
    return _measured("coupon drawing cloud file and flat preferences", {"status": p.get("status"),
                     "job_id": p.get("job_id"), "payload": payload},
                     (payload or {}).get("created") is True
                     and ((payload or {}).get("settings_requested") or {}).get("auto_dimension") == "off"
                     and str((payload or {}).get("file_id") or "").startswith("urn:")
                     and applied.get("isFoldedModelIsometricViewAdded") is True
                     and applied.get("isBendTableIncluded") is True
                     and applied.get("bendTableLocation") == 3)


def _drawing_file(p):
    """Extract the successful deferred drawing's consumable cloud identity."""
    payload = _drawing_terminal_payload(p) or {}
    return [payload["file_id"], payload["drawing_name"]]


def _drawing_sheets(p):
    """Find the coupon's two native sheets and disclose their view types."""
    sheets = p.get("sheets") or []
    names = {_PART, _PART + "_2"}
    coupon = [row for row in sheets if isinstance(row, dict)
              and row.get("name") in names]
    view_types = [[view.get("type") for view in row.get("view_rows") or []]
                  for row in coupon]
    return _measured("coupon flat and folded sheet view rows", {"coupon": coupon,
                     "view_types": view_types, "active_command_id": p.get("active_command_id"),
                     "all_sheet_names": [
                         row.get("name") for row in sheets if isinstance(row, dict)]},
                     bool(p.get("active_command_id"))
                     and p.get("active_command_id") != "FusionDrawingAutoDimensionEditCommand"
                     and len(coupon) == 2 and {row.get("name") for row in coupon} == names
                     and all(isinstance(row.get("view_rows"), list)
                             and row.get("view_rows_truncated") is not True
                             and isinstance(row.get("views"), int) and row["views"] > 0
                             for row in coupon)
                     and any("flat_pattern" in types for types in view_types))




def _drawing_layout_saved(p):
    """Require the tidy edit saved in the exact opened drawing session."""
    drawing = _RECALL.get("sm_drawing") or [None, None]
    acted = p.get("acted_on") or {}
    return _measured("tidied drawing saved in its own session", {"save": p,
                     "expected_lineage": drawing[0]},
                     _versioned(drawing[1])(p)
                     and acted.get("document_id") == drawing[0]
                     and acted.get("name") == drawing[1]
                     and not p.get("lineage_changed"))


def _drawing_initial_session_saved(p):
    """Require the guarded drawing session to read clean after saving."""
    drawing = _RECALL.get("sm_drawing") or [None, None]
    active = p.get("active") or {}
    return _measured("tidied drawing clean in exact session", active,
                     active.get("document_handle") == _RECALL.get("sm_drawing_initial_session")
                     and active.get("document_id") == drawing[0]
                     and active.get("name") == drawing[1]
                     and active.get("is_saved") is True
                     and active.get("is_modified") is False)


def _drawing_saved_version(p):
    """Require a fresh completed drawing version newer than the baseline."""
    drawing = _RECALL.get("sm_drawing") or [None, None]
    before = _RECALL.get("sm_drawing_before") or {}
    snap = _version_record(p)
    return _measured("fresh saved drawing version", {"before": before, "after": snap},
                     _version_current(snap)
                     and snap.get("lineage") == drawing[0] == before.get("lineage")
                     and isinstance(before.get("number"), int)
                     and snap["number"] > before["number"])


def _drawing_saved_session(p):
    """Require the reopened saved version to be active and clean before export."""
    drawing = _RECALL.get("sm_drawing") or [None, None]
    saved = _RECALL.get("sm_drawing_saved_version") or {}
    active = p.get("active") or {}
    return _measured("saved drawing active before PDF export", active,
                     active.get("document_handle") == _RECALL.get("sm_drawing_session")
                     and active.get("document_id") == drawing[0]
                     and active.get("version_id") == saved.get("version_id")
                     and active.get("is_saved") is True
                     and active.get("is_modified") is False)


def _pdf_flat_geometry(page, reader):
    """Read a stroked 2:1 flat outline and bend strokes from native PDF layers."""
    from pypdf.generic import ContentStream
    properties = page["/Resources"].get("/Properties", {})
    layer, points, outlines, bend_strokes = "", [], 0, 0
    for args, op in ContentStream(page.get_contents(), reader).operations:
        if op == b"BDC":
            layer = properties[args[1]].get_object().get("/Name", "")
        elif op == b"EMC":
            layer = ""
        elif op == b"m":
            points = [tuple(float(v) for v in args)]
        elif op == b"l":
            points.append(tuple(float(v) for v in args))
        elif op == b"S":
            bend_strokes += int(layer == "Bend Center" and len(points) >= 2)
            if layer == "Visible" and len(points) == 5 and points[0] == points[-1]:
                xs, ys = {xy[0] for xy in points}, {xy[1] for xy in points}
                if len(xs) == len(ys) == 2:
                    width, height = max(xs) - min(xs), max(ys) - min(ys)
                    outlines += int(height > 0 and _near(width / height, 2, 0.002))
            points = []
    return {"flat_outlines": outlines, "bend_strokes": bend_strokes}


def _drawing_pdf(p):
    """Read the actual PDF's bend table and retain pages for visual inspection."""
    from pypdf import PdfReader
    expected = {"expect_document": _RECALL.get("sm_drawing_session"),
                "file_path": _PDF, "format": "pdf"}
    payload = _drawing_terminal(p, "sm_pdf_job", _PDF_KEY, "drawing_export", expected) or {}
    path = Path(payload.get("file_path") or "")
    reader = PdfReader(path) if path.is_file() else None
    pages = list(reader.pages) if reader else []
    texts = [re.sub(r"\s+", "", page.extract_text()) for page in pages]
    tables = [i for i, t in enumerate(texts) if "BendTableIDDirectionAngleRadius1Up902" in t]
    geometry = _pdf_flat_geometry(pages[tables[0]], reader) if len(tables) == 1 else {}
    return _measured("PDF bend table; inspect rendered flat and formed views", {
        "file": str(path), "pages": len(pages), "bend_tables": len(tables), "geometry": geometry},
        payload.get("exported") is True and len(pages) == 4 and len(tables) == 1
        and geometry.get("flat_outlines") == 1 and geometry.get("bend_strokes", 0) > 0
        and path.stat().st_size == payload.get("size_bytes")
        and (payload.get("acted_on") or {}).get("document_id") == _RECALL["sm_drawing"][0])


def _closed_one(p):
    """Require a confirmed single-document close with no reported errors."""
    return _measured("owned sheet document closed", p,
                     p.get("closed_count") == 1 and len(p.get("closed") or []) == 1
                     and p.get("close_unconfirmed") == [] and p.get("errors") == []
                     and p.get("save_changes") is False)


def _story_restored(p):
    """Verify the original unsaved story session is active before the finale."""
    active = p.get("active") or {}
    handles = {r.get("document_handle") for r in p.get("open_documents") or []}
    return _measured("story session restored", {"active": active, "open_handles": sorted(str(h) for h in handles)},
                     active.get("document_handle") == _RECALL.get("sm_home")
                     and active.get("has_data_file") is False and p.get("truncated") is False
                     and _RECALL.get("sm_coupon") not in handles
                     and _RECALL.get("sm_drawing_session") not in handles)



def _second_folded(p):
    """Require the second, negative-angle fold to change the part."""
    return _measured("negative second bend", {"angle_deg": p.get("angle_deg"),
                     "faces": (p.get("faces_before"), p.get("faces_after"))},
                     p.get("created") is True and _near(p.get("angle_deg"), -60, 1e-5)
                     and isinstance(p.get("faces_before"), int)
                     and isinstance(p.get("faces_after"), int)
                     and p["faces_after"] > p["faces_before"])


def _bend_cylinders(p):
    """Return complete radius-bearing cylinder-face rows."""
    rows = p.get("matches") or []
    if p.get("match_count") != len(rows):
        return []
    return [r for r in rows if r.get("kind") == "cylinder_face"
            and isinstance(r.get("position"), list)
            and len(r["position"]) == 3 and isinstance(r.get("radius"), (int, float))]


def _two_bends(p):
    """Find both inner and outer cylinder pairs after both bends are folded."""
    rows = _bend_cylinders(p)
    inner = [r for r in rows if _near(r.get("radius"), 2, 0.05)]
    outer = [r for r in rows if _near(r.get("radius"), 3.5, 0.05)]
    return _measured("two physical bends", {"cylinders": rows,
                     "match_count": p.get("match_count")},
                     len(rows) == 4 and len(inner) == len(outer) == 2
                     and len([r for r in inner if 20 < r["position"][0] < 40]) == 1
                     and len([r for r in inner if r["position"][0] > 50]) == 1)


def _selected_bend_handle(p):
    """Return the unique inner face of the second bend."""
    rows = [r for r in _bend_cylinders(p)
            if _near(r.get("radius"), 2, 0.05) and r["position"][0] > 50]
    return rows[0]["handle"] if len(rows) == 1 else None


def _selected_unfolded(p):
    """Require selected-bend mode and changed geometry."""
    return _measured("selected bend unfolded", {"feature": p.get("feature"),
                     "all_bends": p.get("all_bends"), "faces_moved": p.get("faces_moved")},
                     p.get("created") is True and p.get("all_bends") is False
                     and (p.get("faces_moved") or 0) > 0)


def _one_bend(p):
    """Require only the first bend's two cylinder faces to remain."""
    rows = _bend_cylinders(p)
    inner = [r for r in rows if _near(r.get("radius"), 2, 0.05)]
    outer = [r for r in rows if _near(r.get("radius"), 3.5, 0.05)]
    return _measured("one bend remains after selected unfold", {"cylinders": rows,
                     "match_count": p.get("match_count")},
                     len(rows) == 2 and len(inner) == len(outer) == 1
                     and 20 < inner[0]["position"][0] < 40)


def _selected_refolded(p):
    """Require refold to bind the selected unfold and move geometry."""
    return _measured("selected bend refolded", {"feature": p.get("feature"),
                     "unfold": p.get("unfold"), "faces_moved": p.get("faces_moved")},
                     p.get("created") is True
                     and p.get("unfold") == _RECALL.get("sm_selected_unfold")
                     and (p.get("faces_moved") or 0) > 0)


def _selected_before_rule(p):
    """Read both formed extents before changing the active rule."""
    x, z = p.get("x"), p.get("z")
    return _measured("two-bend extents before rule edit", {"x_mm": x, "z_mm": z},
                     isinstance(x, (int, float)) and isinstance(z, (int, float))
                     and x > 30 and z > 20)


def _used_rule_updated(p):
    """Read K factor from the applied design rule after the write."""
    row = p.get("rule") or {}
    return _measured("in-use rule K-factor update", {"rule": row,
                     "applied": p.get("applied")},
                     p.get("action") == "update"
                     and row.get("ref") == "design:" + str(_RECALL.get("sm_applied"))
                     and _near(row.get("k_factor"), 0.5, 1e-9)
                     and "k_factor" in (p.get("applied") or []))


def _selected_after_rule(p):
    """Require both formed extents to respond to the in-use rule edit."""
    before = _RECALL.get("sm_selected_extents")
    x, z = p.get("x"), p.get("z")
    dx = abs(x - before[0]) if isinstance(x, (int, float)) and before else None
    dz = abs(z - before[1]) if isinstance(z, (int, float)) and before else None
    return _measured("in-use K factor changed folded extents", {"before_mm": before,
                     "after_mm": (x, z), "change_mm": (dx, dz)},
                     isinstance(dx, (int, float)) and isinstance(dz, (int, float))
                     and 0.05 < dx < 0.5 and 0.05 < dz < 0.5)


def _fold_position_extent(position):
    """Require the formed envelope implied by the bend allowance and chosen line position."""
    allowance = math.pi / 2 * (2 + 0.42 * 1.5)
    start_min_x = 25 - 2 - 1.5
    end_height = 25 + 2 + 1.5
    min_x = start_min_x + (allowance if position == "end" else 0)
    height = end_height - (allowance if position == "start" else 0)

    def check(p):
        minimum, maximum = p.get("min_point") or {}, p.get("max_point") or {}
        start = _RECALL.get("sm_start_envelope") if position == "end" else None
        paired = (position == "start" or
                  (isinstance(start, tuple) and len(start) == 2
                   and isinstance(minimum.get("x"), (int, float))
                   and isinstance(p.get("z"), (int, float))
                   and _near(minimum["x"] - start[0], allowance, 0.01)
                   and _near(p["z"] - start[1], allowance, 0.01)))
        measured = {"x": p.get("x"), "y": p.get("y"), "z": p.get("z"),
                    "min_point": minimum, "max_point": maximum,
                    "bend_allowance_mm": allowance, "start_envelope": start}
        return _measured(f"{position} bend-line formed envelope", measured,
                         paired and _near(minimum.get("x"), min_x, 0.01)
                         and _near(minimum.get("y"), 0, 0.01)
                         and _near(minimum.get("z"), 0, 0.01)
                         and _near(maximum.get("x"), 80, 0.01)
                         and _near(maximum.get("y"), 40, 0.01)
                         and _near(maximum.get("z"), height, 0.01)
                         and _near(p.get("x"), 80 - min_x, 0.01)
                         and _near(p.get("y"), 40, 0.01)
                         and _near(p.get("z"), height, 0.01))
    return check

_SHEET_BUILD = [
    ("doc_get", {}, _home_session,
     ("sm_home", _recall("sm_home", lambda p: p["active"]["document_handle"]))),
    ("doc_new", {}, _coupon_session,
     ("sm_coupon", _recall("sm_coupon", lambda p: p["document_handle"]))),
    ("model_create_component", {"name": _SEED, "sheet_metal": True, "activate": True}, _ruled_component, None),
    ("sheet_get", {"include": ["library_rules"]}, "ok", None),
    ("sheet_edit_rule", {"rule": "library:Steel (mm)", "name": _RULE,
                         "thickness": "1.5 mm", "bend_radius": "2 mm",
                         "gap": "0.5 mm", "k_factor": 0.4}, "ok", None),
    ("sheet_edit_rule", {"action": "update", "rule": "design:" + _RULE,
                         "k_factor": 0.42}, "ok", None),
    ("sheet_get", {"include": ["rules"]}, _rule_settings, None),
    ("sketch_create", {"name": _SEED_BASE, "plane": "xy"}, "ok", None),
    ("sketch_add_geometry", {"sketch_name": _SEED_BASE, "geometry": [
        {"kind": "rectangle", "x1": 100, "y1": 0, "x2": 180, "y2": 40}]}, "ok", None),
    ("model_extrude", {"sketch_name": _SEED_BASE, "profile_index": 0,
                       "distance": 1.5, "operation": "new"}, _extruded, None),
    ("find_geometry", {"target": _SEED, "kind": "planar_face", "max_results": 20},
     _top_face(3000), _top_handle(3000)),
    ("sheet_convert", lambda c: {"body": _SEED, "base_face": _ctx_get(c, "sm_top", "seed top face"),
                                  "rule": "design:" + _RULE}, _refused("would be ignored"), None),
    ("sheet_convert", lambda c: {"body": _SEED, "base_face": _ctx_get(c, "sm_top", "seed top face"),
                                  "rule": "design:Steel (mm)"}, _refused("shared rule"), None),
    ("sheet_get", {"include": ["rules", "components"], "max_results": 200}, _seed_guard, None),
    ("model_create_component", {"name": _PART, "activate": True}, "ok", None),
    ("sketch_create", {"name": _BASE, "plane": "xy"}, "ok", None),
    ("sketch_add_geometry", {"sketch_name": _BASE, "geometry": [
        {"kind": "rectangle", "x1": 0, "y1": 0, "x2": 80, "y2": 40}]}, "ok", None),
    ("model_extrude", {"sketch_name": _BASE, "profile_index": 0,
                       "distance": 1.5, "operation": "new"}, _extruded, None),
    ("find_geometry", {"target": _PART, "kind": "planar_face", "max_results": 20},
     _top_face(3000), _top_handle(3000)),
    ("sheet_convert", lambda c: {"body": _PART, "base_face": _ctx_get(c, "sm_top", "blank top face"),
                                  "rule": "design:" + _RULE},
     _converted, ("sm_applied", _recall("sm_applied", lambda p: p["applied_rule"]))),
    ("sheet_get", {"include": ["components"], "max_results": 200}, _sheet_body, None),
    ("find_geometry", {"target": _PART, "kind": "planar_face", "max_results": 20},
     _top_face(3000), _top_handle(3000)),
    ("sketch_create", lambda c: {"name": _BEND, "on_face": _ctx_get(c, "sm_top", "sheet top face")},
     "ok", None),
    ("sketch_add_geometry", {"sketch_name": _BEND, "geometry": [
        {"kind": "line", "x1": 25, "y1": 0, "x2": 25, "y2": 40}]}, "ok", None),
    ("sketch_get", {"sketch_name": _BEND, "include_entities": True},
     _bend_line, ("sm_line", lambda p: _BEND + "/" + _line_match(p)["id"])),
    ("sheet_create_fold", lambda c: {"stationary_face": _ctx_get(c, "sm_top", "sheet top face"),
                                      "bend_line": _ctx_get(c, "sm_line", "intended bend line"),
                                      "component": _PART, "angle_deg": 90}, _folded, None),
]

_SHEET = _SHEET_BUILD + [
    # SHEET-RULE-DUPLICATE-REF-1: addNewSheetMetalComponent copies a fresh library-default rule only
    # when the design's same-named rule no longer matches the library default (measured) - the step
    # above's 1.2 mm edit is what makes _SEED2's add copy instead of handing 'Steel (mm)' straight back.
    ("sheet_edit_rule", {"action": "update", "rule": "design:Steel (mm)",
                         "thickness": "1.2 mm"}, "ok", None),
    ("sheet_get", {}, "ok",
     ("sm_rule_count_before_adopt", _recall("sm_rule_count_before_adopt",
                                            lambda p: p["design_rule_count"]))),
    ("model_create_component", {"name": _SEED2, "sheet_metal": True}, _rule_adopted_from_copy, None),
    ("sheet_get", {"include": ["rules"], "max_results": 200}, _design_rule_count_after_adopt, None),
    # A duplicate the TOOL never created (direct API, bypassing the adopt path) still has to read
    # and resolve as '#1'/'#2' - sheet_get's rows and sheet_edit_rule's rule kind, not a special case.
    ("sys_execute_script", {"script": _DUP_STEEL_RULE_SCRIPT}, "ok", None),
    ("sheet_get", {"include": ["rules"], "max_results": 200}, _duplicate_steel_rows, None),
    ("sheet_edit_rule", {"action": "update", "rule": "design:Steel (mm)#2",
                         "gap": "0.6 mm"}, _second_dup_gap_updated, None),
    ("sheet_get", {"include": ["rules"], "max_results": 200}, _dup_gap_isolated, None),
    ("model_inspect", {"target": _PART, "include": ["default", "mass"]}, _formed_extent,
     ("sm_before_slot_volume", _recall("sm_before_slot_volume", lambda p: (p.get("mass") or {})["volume"]))),
    ("find_geometry", {"target": _PART, "kind": "planar_face", "max_results": 25},
     _top_face(900), _top_handle(900)),
    ("sheet_create_flat_pattern", lambda c: {"stationary_face": _ctx_get(c, "sm_top", "folded stationary face")},
     _flat, None),
    ("sheet_get", {"include": ["components"], "max_results": 200}, _flat_census, None),
    ("find_geometry", {"target": _PART, "kind": "planar_face", "max_results": 25},
     _top_face(900), _top_handle(900)),
    ("sheet_create_flat_pattern", lambda c: {"stationary_face": _ctx_get(c, "sm_top", "flat source face")},
     _refused("already has a flat pattern"), None),
    ("design_export", {"format": "dxf", "dxf_flat_pattern": _PART, "file_path": _DXF,
                       "dxf_flat_units": "mm", "dxf_bend_lines": True,
                       "dxf_bend_extents": True}, _dxf, None),
    ("find_geometry", {"target": _PART, "kind": "planar_face", "max_results": 25},
     _top_face(900), _top_handle(900)),
    ("find_geometry", {"target": _PART, "kind": "cylinder_face", "max_results": 20},
     _fold_cylinders_check, ("sm_fold_cyls", _fold_cylinder_handles)),
    ("sheet_create_unfold", lambda c: {"stationary_face": _ctx_get(c, "sm_top", "folded stationary face"),
                                        "bend_faces": _ctx_get(c, "sm_fold_cyls", "fold cylinder faces")},
     _unfolded, ("sm_unfold", _recall("sm_unfold", lambda p: p["feature"]))),
    ("model_inspect", {"target": _PART},
     lambda p: _measured("unfolded slab height", {"z_mm": p.get("z")},
                         _near(p.get("z"), 1.5, 0.01)), None),
    ("sketch_create", {"plane": "xy", "name": _SLOT}, "ok", None),
    ("sketch_add_geometry", {"sketch_name": _SLOT, "geometry": [
        {"kind": "slot", "x1": 20, "y1": 20, "x2": 30, "y2": 20, "radius": 2}]}, "ok", None),
    ("model_extrude", {"sketch_name": _SLOT, "profile_index": 0,
                       "distance": 2, "operation": "cut"}, _extruded, None),
    ("sheet_create_refold", lambda c: {"unfold": _ctx_get(c, "sm_unfold", "unfold feature")},
     _refolded, None),
    ("model_inspect", {"target": _PART}, _formed_extent, None),
    ("model_inspect", {"target": _PART, "include": ["mass"]}, _slot_volume, None),
    ("sheet_create_refold", lambda c: {"unfold": _ctx_get(c, "sm_unfold", "already refolded feature")},
     _refused("already has refold"), None),
    # all_bends on the CONVERTED, slotted coupon: the wall pairing (inner + outer cylinder on one
    # axis, no bend registry read) sends the split walls and skips the slot end on the leg, whose
    # axis lies in the base plane; the refold lands the slab back where it was.
    ("find_geometry", {"target": _PART, "kind": "planar_face", "max_results": 25},
     _top_face(900), _top_handle(900)),
    ("sheet_create_unfold", lambda c: {"stationary_face": _ctx_get(c, "sm_top", "folded stationary face"),
                                        "all_bends": True},
     lambda p: _measured("converted coupon unfolds by all_bends",
                         {"bend_count_unfolded": p.get("bend_count_unfolded"), "faces_moved": p.get("faces_moved")},
                         p.get("created") is True and p.get("all_bends") is True
                         and p.get("bend_count_unfolded") == 1 and (p.get("faces_moved") or 0) > 0),
     ("sm_unfold_all", _recall("sm_unfold_all", lambda p: p["feature"]))),
    ("model_inspect", {"target": _PART},
     lambda p: _measured("all_bends slab height", {"z_mm": p.get("z")}, _near(p.get("z"), 1.5, 0.01)), None),
    ("sheet_create_refold", lambda c: {"unfold": _ctx_get(c, "sm_unfold_all", "all_bends unfold feature")},
     lambda p: _refolded(p, "sm_unfold_all"), None),
    ("model_inspect", {"target": _PART}, _formed_extent, None),
    ("design_export", {"format": "dxf", "dxf_flat_pattern": _PART,
                       "file_path": _CUT_DXF, "dxf_flat_units": "mm",
                       "dxf_bend_lines": False, "dxf_bend_extents": False},
     lambda p: _dxf(p, slotted=True), None),
    ("view_switch_workspace", {"workspace": "manufacture"}, "ok", None),
    ("cam_create_setup", {"operation_type": "cutting", "name": _CAM_SETUP,
                          "flat_patterns": [_PART]}, _cutting_setup, None),
    ("cam_edit_setup", {"setup": _CAM_SETUP, "machine": "Avid CNC|EX 3 Axis"},
     lambda p: _measured("cutting machine assignment", p,
                         bool(p.get("machine_set"))),
     ("sm_machine", _recall("sm_machine", lambda p: p["machine_set"]))),
    ("cam_get", {"include": ["setups"], "setup": _CAM_SETUP}, _cutting_setup_read, None),
    ("cam_create_operation", {"setup": _CAM_SETUP, "strategy": "profile2d",
                              "name": _CAM_OP, "tool_library_url": _LASER_LIBRARY,
                              "tool_index": 0, "generate": False}, "ok", None),
    ("cam_select_geometry", {"operation": _CAM_OP, "selection": "silhouette",
                             "loop_type": "all", "generate": False},
     lambda p: _measured("flat silhouette selected", p,
                         p.get("setup_models_selected") is True), None),
    ("cam_generate", {"target": _CAM_SETUP, "skip_valid": False}, "ok", None),
    ("cam_get_status", {"target": _CAM_OP}, _laser_generated, None),
    ("cam_show_toolpath", {"action": "isolate", "operation": _CAM_OP, "fit": True},
     _cutting_fit_frames_flat, None),
]


_SHEET_SELECTED = _SHEET_BUILD + [
    ("find_geometry", {"target": _PART, "kind": "planar_face", "max_results": 30},
     _top_face(900), _top_handle(900)),
    ("sketch_create", lambda c: {"name": _BEND2,
                                  "on_face": _ctx_get(c, "sm_top", "first-fold stationary face")},
     "ok", None),
    ("sketch_add_geometry", {"sketch_name": _BEND2, "geometry": [
        {"kind": "line", "x1": 55, "y1": 0, "x2": 55, "y2": 40}]}, "ok", None),
    ("sketch_get", {"sketch_name": _BEND2, "include_entities": True},
     lambda p: _bend_line(p, 55),
     ("sm_line2", lambda p: _BEND2 + "/" + _line_match(p, 55)["id"])),
    ("sheet_create_fold", lambda c: {
        "stationary_face": _ctx_get(c, "sm_top", "first-fold stationary face"),
        "bend_line": _ctx_get(c, "sm_line2", "second bend line"),
        "component": _PART, "angle_deg": -60}, _second_folded, None),
    ("find_geometry", {"target": _PART, "kind": "cylinder_face", "max_results": 30},
     _two_bends, ("sm_selected_bend", _selected_bend_handle)),
    ("find_geometry", {"target": _PART, "kind": "planar_face", "max_results": 30},
     _top_face(900), _top_handle(900)),
    ("sheet_create_unfold", lambda c: {
        "stationary_face": _ctx_get(c, "sm_top", "top face between bends"),
        "bend_faces": [_ctx_get(c, "sm_selected_bend", "second bend inner face")]},
     _selected_unfolded,
     ("sm_selected_unfold", _recall("sm_selected_unfold", lambda p: p["feature"]))),
    ("find_geometry", {"target": _PART, "kind": "cylinder_face", "max_results": 30},
     _one_bend, None),
    ("sheet_create_refold", lambda c: {
        "unfold": _ctx_get(c, "sm_selected_unfold", "selected unfold feature")},
     _selected_refolded, None),
    ("find_geometry", {"target": _PART, "kind": "cylinder_face", "max_results": 30},
     _two_bends, None),
    ("find_geometry", {"target": _PART, "kind": "planar_face", "max_results": 30},
     _top_face(900), _top_handle(900)),
    ("sheet_create_flat_pattern", lambda c: {
        "stationary_face": _ctx_get(c, "sm_top", "refolded stationary face")},
     _flat, None),
    ("model_inspect", {"target": _PART, "include": ["default", "mass"]},
     _selected_before_rule,
     ("sm_selected_extents", _recall("sm_selected_extents", lambda p: (p["x"], p["z"])))),
    ("sheet_edit_rule", lambda c: {
        "action": "update", "rule": "design:" + _ctx_get(c, "sm_applied", "applied rule"),
        "k_factor": 0.5}, _used_rule_updated, None),
    ("model_inspect", {"target": _PART, "include": ["default", "mass"]},
     _selected_after_rule, None),
    ("sheet_get", {"include": ["components"], "max_results": 200},
     _flat_census, None),
    ("doc_close", lambda c: {"name": _ctx_get(c, "sm_coupon", "selected coupon session"),
                             "save_changes": False}, _closed_one, None),
    ("doc_activate", lambda c: {"name": _ctx_get(c, "sm_home", "original story session")},
     "ok", None),
    _dwell(4.0),
    ("doc_get", {}, _story_restored, None),
]



def _position_variant(position):
    """Build, fold, inspect, and close one position-specific scratch coupon."""
    return _SHEET_BUILD[:-1] + [
        ("sheet_create_fold", lambda c: {
            "stationary_face": _ctx_get(c, "sm_top", "sheet top face"),
            "bend_line": _ctx_get(c, "sm_line", "intended bend line"),
            "component": _PART, "angle_deg": 90, "position": position}, _folded, None),
        ("model_inspect", {"target": _PART, "include": ["default"]},
         _fold_position_extent(position),
         (("sm_start_envelope", _recall("sm_start_envelope", lambda p: (
             p["min_point"]["x"], p["z"]))) if position == "start" else None)),
        ("doc_close", lambda c: {"name": _ctx_get(c, "sm_coupon", "position coupon session"),
                                 "save_changes": False}, _closed_one, None),
        ("doc_activate", lambda c: {"name": _ctx_get(c, "sm_home", "original story session")},
         "ok", None),
        _dwell(4.0),
        ("doc_get", {}, _story_restored, None),
    ]


_SHEET_POSITIONS = _position_variant("start") + _position_variant("end")

_SHEET_CAM_READ = [
    ("cam_inspect_toolpaths", {"scope": _CAM_SETUP}, _laser_inspected, None),
    ("cam_post", {"scope": _CAM_SETUP, "post": "grbl laser", "post_scope": "fusion",
                  "output_folder": EXPORT_DIR + "/nc", "program_name": "SM1001"},
     _laser_posted, None),
    ("cam_get", {"setup": _CAM_SETUP, "include": ["time"]}, lambda p: _laser_feed(p),
     ("sm_feed_baseline", _recall("sm_feed_baseline", _laser_feed_value))),
    ("sketch_dimension", {"sketch_name": _BASE, "dimensions": [{
        "dim_type": "horizontal_distance", "entity_one": "line:0:start",
        "entity_two": "line:0:end", "value": "90 mm"}]}, _width_dimension,
     ("sm_width", _recall("sm_width", lambda p: p["results"][0]["parameter"]))),
    ("cam_generate", {"target": _CAM_OP}, "ok", None),
]

_SHEET_CAM_REFRESH = [
    ("cam_get", {"setup": _CAM_SETUP, "include": ["time"]}, lambda p: _laser_feed(p, 10), None),
    _width_set(80),
    ("design_export", {"format": "dxf", "dxf_flat_pattern": _PART,
                       "file_path": _CUT_DXF, "dxf_flat_units": "mm",
                       "dxf_bend_lines": False, "dxf_bend_extents": False},
     lambda p: _dxf(p, slotted=True), None),
    ("cam_post", {"program_name": "SM1001"}, lambda p: _laser_posted(p, as_is=True), None),
    ("cam_get", {"setup": _CAM_SETUP, "include": ["time"]}, lambda p: _laser_feed(p, 0), None),
    _width_set(90),
    ("cam_get", {"setup": _CAM_SETUP, "include": ["operations"]}, _stale_after_widen, None),
    ("cam_post", {"scope": _CAM_SETUP, "post": "grbl laser", "post_scope": "fusion",
                  "output_folder": EXPORT_DIR + "/nc", "program_name": "SM1001"},
     _laser_posted, None),
    ("cam_get", {"setup": _CAM_SETUP, "include": ["time"]}, lambda p: _laser_feed(p, 10), None),
    _width_set(85),
    ("cam_select_geometry", {"operation": _CAM_OP, "selection": "silhouette",
                             "loop_type": "all", "generate": True}, "ok", None),
]

_SHEET_CAM_RESTORE = [
    ("cam_get", {"setup": _CAM_SETUP, "include": ["time"]}, lambda p: _laser_feed(p, 5), None),
    _width_set(80),
    ("cam_post", {"program_name": "SM1001"}, lambda p: _laser_posted(p, as_is=True), None),
    ("cam_get", {"setup": _CAM_SETUP, "include": ["time"]}, lambda p: _laser_feed(p, 0), None),
    ("cam_create_operation", {"setup": _CAM_SETUP, "strategy": "profile2d",
                              "name": _CAM_UNSELECTED, "tool_library_url": _LASER_LIBRARY,
                              "tool_index": 0, "generate": False}, "ok", None),
    ("cam_post", {"scope": _CAM_OP, "post": "grbl laser", "post_scope": "fusion",
                  "output_folder": EXPORT_DIR + "/nc", "program_name": "SM1002"},
     lambda p: _laser_posted(p, scope="operation"), None),
    ("cam_get", {"setup": _CAM_SETUP, "include": ["operations"]},
     _unselected_path_untouched, None),
    ("cam_delete", {"entity": _CAM_UNSELECTED}, "ok", None),
]


_SHEET_CAM_RESTORE += [
    ("cam_save_template", {"setup": _CAM_SETUP, "operations": _CAM_OP,
                           "template_name": _FLAT_TEMPLATE, "location": "local"},
     lambda p: p.get("saved") is True and p.get("operation_count") == 1,
     ("sm_flat_template", _recall("sm_flat_template", lambda p: p["template_url"]))),
    _width_set(90),
    ("cam_apply_template", lambda c: {"setup": _CAM_SETUP, "generate": "generate",
        "template_url": _ctx_get(c, "sm_flat_template", "owned flat template"),
        "location": "local"}, _flat_template_applied,
     ("sm_flat_applied", _recall("sm_flat_applied", lambda p: {
         "operation": p["created_operations"][0],
         "tool": p["library_tools"]["forked"][0]["index"]}))),
    ("cam_get_status", lambda c: {"target": _ctx_get(c, "sm_flat_applied",
        "applied flat operation")["operation"]},
     _flat_template_generated, None),
    ("cam_get", {"setup": _CAM_SETUP, "include": ["operations", "time"]},
     _flat_template_path, None),
    ("cam_delete", lambda c: {"entity": _ctx_get(c, "sm_flat_applied",
        "applied flat operation")["operation"]}, "ok", None),
    ("cam_edit_tools", lambda c: {"action": "remove", "scope": "document",
        "remove_indices": [_ctx_get(c, "sm_flat_applied", "owned template fork")["tool"]]},
     "ok", None),
    ("cam_delete_template", lambda c: {"template_url": _ctx_get(c, "sm_flat_template",
        "owned flat template"), "confirm_name": _FLAT_TEMPLATE},
     lambda p: p.get("deleted") is True and p.get("loads_after_delete") is False, None),
    _width_set(85),
    ("cam_create_operation", {"setup": _CAM_SETUP, "strategy": "profile2d",
                              "name": _CAM_UNSELECTED, "tool_library_url": _LASER_LIBRARY,
                              "tool_index": 0, "generate": True},
     lambda p: p.get("generation_started") is True and p.get("flat_models_refreshed") == 1,
     ("sm_empty_generation", _recall("sm_empty_generation", lambda p: p["generation_handle"]))),
    ("cam_get_status", lambda c: {"handle": _ctx_get(c, "sm_empty_generation",
        "unselected contour generation")}, _created_empty_path, None),
    ("cam_delete", {"entity": _CAM_UNSELECTED}, "ok", None),
    _width_set(80),
    ("cam_post", {"program_name": "SM1001"}, lambda p: _laser_posted(p, as_is=True), None),
    ("cam_get", {"setup": _CAM_SETUP, "include": ["time"]}, lambda p: _laser_feed(p, 0), None),
]


_SHEET_CAM_RESTORE += [
    ("cam_create_setup", {"name": _MILL_SETUP, "operation_type": "cutting",
                          "flat_patterns": [_PART]},
     lambda p: p.get("flat_models_verified") is True, None),
    ("cam_edit_setup", {"setup": _MILL_SETUP, "machine": "Avid CNC|EX 3 Axis",
                        "parameters": {"job_type": "'milling'"}},
     lambda p: p.get("edited") is True and p.get("updated_count") == 1, None),
    ("cam_edit_tools", {"action": "add", "scope": "document", "add_tools": [
        {"from_type": "flat end mill", "diameter": "2 mm", "description": "SM flat mill"}]},
     lambda p: p.get("added") == 1 and p.get("tool_count", 0) > 0,
     ("sm_mill_tool", _recall("sm_mill_tool", lambda p: p["tool_count"] - 1))),
    ("cam_create_operation", lambda c: {"setup": _MILL_SETUP, "name": _MILL_OP,
        "strategy": "contour2d", "tool_scope": "document", "generate": False,
        "tool_index": _ctx_get(c, "sm_mill_tool", "owned flat mill")}, "ok", None),
    ("cam_select_geometry", {"operation": _MILL_OP, "selection": "silhouette",
                             "loop_type": "all", "generate": True},
     lambda p: p.get("setup_models_selected") is True and p.get("flat_models_refreshed") == 1, None),
    ("cam_get_status", {"target": _MILL_OP}, _mill_generated, None),
    ("cam_get", {"setup": _MILL_SETUP, "include": ["time"]}, lambda p: _mill_feed(p),
     ("sm_mill_feed_baseline", _recall("sm_mill_feed_baseline",
        lambda p: _laser_feed_value(p, _MILL_OP, _MILL_SETUP)))),
    _width_set(90),
    ("cam_generate", {"target": _MILL_OP},
     lambda p: p.get("launched") is True and p.get("flat_models_refreshed") == 1, None),
    ("cam_get_status", {"target": _MILL_OP}, _mill_generated, None),
    ("cam_get", {"setup": _MILL_SETUP, "include": ["time"]}, lambda p: _mill_feed(p, 10), None),
    _width_set(80),
    ("cam_post", {"scope": _MILL_OP, "post": "grbl", "post_scope": "fusion",
                  "output_folder": EXPORT_DIR + "/nc-mill", "program_name": "SM1003"},
     lambda p: _laser_posted(p, scope="operation"), None),
    ("cam_get", {"setup": _MILL_SETUP, "include": ["time"]}, lambda p: _mill_feed(p, 0), None),
    ("cam_delete", {"entity": "SM1003"}, lambda p: p.get("deleted") is True, None),
    ("cam_delete", {"entity": _MILL_SETUP}, lambda p: p.get("deleted") is True, None),
    ("cam_edit_tools", lambda c: {"action": "remove", "scope": "document",
        "remove_indices": [_ctx_get(c, "sm_mill_tool", "owned flat mill")]},
     lambda p: p.get("removed") == 1, None),
    ("cam_post", {"program_name": "SM1001"}, lambda p: _laser_posted(p, as_is=True), None),
    ("cam_get", {"setup": _CAM_SETUP, "include": ["time"]}, lambda p: _laser_feed(p, 0), None),
]


_SHEET_DRAWING = [
    ("doc_save_as", {"name": _DRAW_SOURCE, "project": PROJECT, "folder": FOLDER},
     _source_saved, ("sm_source_urn", _recall("sm_source_urn", lambda p: p["document_id"]))),
    ("doc_get", {}, _source_session,
     ("sm_source_session", _recall("sm_source_session", lambda p: p["active"]["document_handle"]))),
    ("data_get", lambda c: {"file": _ctx_get(c, "sm_source_urn", "the saved coupon")},
     _file_settled(FOLDER), None),
    ("drawing_create", lambda c: {"standard": "iso", "units": "mm", "sheet_size": "a3",
                                  "sheet_types": ["flat_pattern", "folded_model"],
                                  "flat_isometric": True, "bend_table": True,
                                  "bend_table_location": "bottom_right",
                                  "deferred": True,
                                  "request_key": _DRAW_KEY,
                                  "expect_document": _ctx_get(c, "sm_source_session", "coupon source session")},
     _drawing_started, ("sm_draw_job", _recall("sm_draw_job", lambda p: p["job_id"]))),
    ("drawing_get_status", {"request_key": _DRAW_KEY}, _drawing_complete,
     ("sm_drawing", _recall("sm_drawing", _drawing_file))),
    ("doc_open", lambda c: {"file_id": _ctx_get(c, "sm_drawing", "coupon drawing")[0],
                            "force_api_open": True},
     _opened(lambda: _RECALL.get("sm_drawing", [None, None])[1],
             lambda: _RECALL.get("sm_drawing", [None, None])[0]),
     ("sm_drawing_initial_session", _recall("sm_drawing_initial_session",
                                            lambda p: p["document_handle"]))),
    _dwell(4.0),
    ("drawing_get", {"include": ["views"]}, _drawing_sheets, None),
    ("data_get", lambda c: _version_args("sm_drawing_before")(
        {"source_urn": _ctx_get(c, "sm_drawing", "coupon drawing")[0]}),
     _version_snapshot("sm_drawing_before"),
     ("sm_drawing_before", _recall("sm_drawing_before", _version_record))),
    ("drawing_edit_sheet", {"action": "tidy_up", "sheet": _PART + "_2"},
     lambda p: _measured("flat sheet layout refreshed", p,
                         p.get("tidied") is True and p.get("sheet") == _PART + "_2"), None),
    ("doc_save", lambda c: {"description": "Persist the flat sheet layout",
                            "expect_document": _ctx_get(c, "sm_drawing_initial_session",
                                                        "coupon drawing session")},
     _drawing_layout_saved, None),
    ("doc_get", {}, _drawing_initial_session_saved, None),
    ("data_get", lambda c: {"file": _ctx_get(c, "sm_drawing", "coupon drawing")[0]},
     _version_settled("sm_drawing_before"), None),
    ("data_get", lambda c: {"file": _ctx_get(c, "sm_drawing", "coupon drawing")[0]},
     _drawing_saved_version,
     ("sm_drawing_saved_version", _recall("sm_drawing_saved_version", _version_record))),
    ("doc_close", lambda c: {"name": _ctx_get(c, "sm_drawing_initial_session",
                                          "original drawing session"),
                             "save_changes": False}, _closed_one, None),
    ("doc_activate", lambda c: {"name": _ctx_get(c, "sm_coupon", "coupon source session")},
     "ok", None),
    ("doc_open", lambda c: {"file_id": _ctx_get(c, "sm_drawing", "coupon drawing")[0],
                            "force_api_open": True},
     _opened(lambda: _RECALL.get("sm_drawing", [None, None])[1],
             lambda: _RECALL.get("sm_drawing", [None, None])[0]),
     ("sm_drawing_session", _recall("sm_drawing_session", lambda p: p["document_handle"]))),
    _dwell(4.0),
    ("doc_get", {}, _drawing_saved_session, None),
    ("drawing_get", {"include": ["views"]}, _drawing_sheets, None),
    ("drawing_edit_sheet", {"action": "tidy_up", "sheet": _PART + "_2"},
     lambda p: p.get("tidied") is True and p.get("views") == 4, None),
    ("drawing_export", lambda c: {"format": "pdf", "file_path": _PDF,
                                  "deferred": True, "request_key": _PDF_KEY,
                                  "expect_document": _ctx_get(c, "sm_drawing_session", "coupon drawing")},
     lambda p: _measured("PDF job accepted", p, p.get("accepted") is True
                         and p.get("request_key") == _PDF_KEY and bool(p.get("job_id"))),
     ("sm_pdf_job", _recall("sm_pdf_job", lambda p: p["job_id"]))),
    ("drawing_get_status", {"request_key": _PDF_KEY}, _drawing_pdf, None),
    ("doc_close", lambda c: {"name": _ctx_get(c, "sm_drawing_session", "coupon drawing session"),
                             "save_changes": False}, _closed_one, None),
    ("doc_activate", lambda c: {"name": _ctx_get(c, "sm_coupon", "coupon source session")}, "ok", None),
    _dwell(4.0),
    ("doc_get", {}, _source_session, None),
]

_SHEET_CLEANUP = [
    ("doc_close", lambda c: {"name": _ctx_get(c, "sm_coupon", "coupon session"),
                             "save_changes": False}, _closed_one, None),
    ("doc_activate", lambda c: {"name": _ctx_get(c, "sm_home", "original story session")}, "ok", None),
    _dwell(4.0),
    ("doc_get", {}, _story_restored, None),
]

