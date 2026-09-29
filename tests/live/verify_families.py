# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Owned sweep families and the local inputs each builds before its judged acts."""

from verify_acts_cam import _CAM_EXTENSION, _CAM_SCOPE, _SWARF_RIG
from verify_acts_model import _DETAILS, _SOLIDS
from verify_acts_motion import _MOTION, _VISE
from verify_acts_sketch import _SKELETON
from verify_core import _DWELL
from verify_layout import _placed


FAMILY_GROUPS = (
    ("sketch", ("ACT 0", "ACT 1 -", "ACT 1b")),
    ("solids", ("ACT 2 -",)),
    ("surfaces", ("ACT 3 -",)),
    ("mesh", ("ACT 4 -",)),
    ("details", ("ACT 5 -",)),
    ("resize", ("ACT 6 -",)),
    ("nesting", ("ACT 6b",)),
    ("vise", ("ACT 7 -",)),
    ("motion", ("ACT 7b",)),
    ("showcase", ("ACT 9 -",)),
    ("swarf_cam", ("ACT 8 -", "ACT 10b2", "ACT 10c -", "ACT 10c6b")),
    ("hub_cam", ("ACT 8b", "ACT 10c4", "ACT 10c5", "ACT 10c6 -",
                 "ACT 10c7", "ACT 10c8", "ACT 10c9", "ACT 10c10", "ACT 10c11",
                 "ACT 10c12", "ACT 10c13", "ACT 10c14", "ACT 10c15")),
    ("part_cam", ("ACT 10a", "ACT 10b -", "ACT 10b1", "ACT 10d", "ACT 10e", "ACT 10f")),
    ("cloud", ("ACT 11",)),
    ("sheet_coupon", ("ACT 12 -", "ACT 12b", "ACT 12c", "ACT 12d")),
    ("sheet_selected", ("ACT 12e",)),
    ("sheet_positions", ("ACT 12f",)),
    ("sheet_flange", ("ACT 12g",)),
    ("finale", ("FINALE",)),
)
FAMILY_SLOTS = {}


def family_names(acts):
    """Return act-to-family ownership, refusing missing or multiply owned acts."""
    result = {}
    for name, _pre, _narrative, _fallback in acts:
        hits = [family for family, prefixes in FAMILY_GROUPS
                if any(name.startswith(prefix) for prefix in prefixes)]
        if len(hits) != 1:
            raise ValueError("act has {0} families: {1}".format(len(hits), name))
        result[name] = hits[0]
    return result


def ordered_acts(acts):
    """Place each family's dependency chain in one contiguous document."""
    owners = family_names(acts)
    return [act for family, _prefixes in FAMILY_GROUPS for act in acts
            if owners[act[0]] == family]


def _through(steps, tool, name):
    """Take a producer's rows through its named last effect."""
    matches = [i for i, step in enumerate(steps)
               if step[0] == tool and isinstance(step[1], dict)
               and step[1].get("name") == name]
    if len(matches) != 1:
        raise ValueError("fixture boundary is not unique: " + name)
    return list(steps[:matches[0] + 1])


def _component_block(steps, component, last_tool, last_key=None, last_value=None):
    """Take one named component's producer through its last required effect."""
    starts = [i for i, row in enumerate(steps)
              if row[0] == "model_create_component" and isinstance(row[1], dict)
              and row[1].get("name") == component]
    if len(starts) != 1:
        raise ValueError("component fixture boundary is not unique: " + component)
    start = starts[0]
    ends = [i for i in range(start + 1, len(steps))
            if steps[i][0] == last_tool
            and (last_key is None or (isinstance(steps[i][1], dict)
                                      and steps[i][1].get(last_key) == last_value))]
    if not ends:
        raise ValueError("component fixture has no last effect: " + component)
    return list(steps[start:ends[0] + 1])


_HANDLE_END = next(i for i, row in enumerate(_VISE)
                   if row[0] == "model_extrude" and isinstance(row[1], dict)
                   and row[1].get("sketch_name") == "HandleS")
STOCK_VISE = list(_VISE[:_HANDLE_END + 2])
RECOGNITION = [step for step in _DETAILS
               if step[0] in ("cam_find_holes", "cam_find_pockets")]
_MANUFACTURE = ("view_switch_workspace", {"workspace": "manufacture"}, "ok", None)
_DESIGN = ("view_switch_workspace", {"workspace": "design"}, "ok", None)


def fixture_steps(family, before_act=None, entitled=True, raw=False, slots=None):
    """Return local producer rows for one family boundary."""
    selected = None if raw else (FAMILY_SLOTS[family] if slots is None else slots)
    place = (lambda rows: list(rows)) if raw else (lambda rows: _placed(rows, selected))
    if before_act is not None:
        if before_act.startswith("ACT 10e") and family == "part_cam":
            rows = [_DESIGN] + place(_SWARF_RIG) + [
                _MANUFACTURE] + place(_CAM_SCOPE)
            return rows + (place(_CAM_EXTENSION) if entitled else [])
        if before_act.startswith("ACT 10c15") and family == "hub_cam" and entitled:
            return [_DESIGN] + place(_SWARF_RIG) + [
                _MANUFACTURE] + place(_CAM_EXTENSION)
        if family == "swarf_cam" and before_act.startswith("ACT 10b2"):
            return [_MANUFACTURE]
        if family == "hub_cam" and before_act.startswith("ACT 10c4"):
            return [_MANUFACTURE]
        return []
    if family in ("solids", "details", "resize", "vise", "part_cam", "showcase"):
        rows = list(_SKELETON)
        if family != "solids":
            rows += _through(_SOLIDS, "joint_create_origin", "StockCenter")
        if family == "details":
            rows += place(_component_block(_SOLIDS, "DatumBench", "find_geometry",
                                           "kind", "cylinder_face"))
        if family == "resize":
            rows += place(_component_block(_SOLIDS, "DatumBench", "model_extrude"))
            rows.append(("design_activate_component", {"occurrence": "root"}, "ok", None))
        if family in ("part_cam", "showcase"):
            rows += STOCK_VISE
        if family == "part_cam":
            rows += RECOGNITION
        if family == "showcase":
            captured = next(i for i, row in enumerate(_VISE)
                            if row[0] == "assembly_capture_position"
                            and isinstance(row[1], dict)
                            and row[1].get("action") == "capture")
            rows += [row for row in _VISE[len(STOCK_VISE):captured + 1]
                     if row[0] not in (_DWELL, "view_set", "view_screenshot")]
            rows += showcase_shapes(raw=raw, slots=selected)
        return rows
    if family in ("swarf_cam", "hub_cam"):
        return [_MANUFACTURE,
                ("cam_edit_tools", {"action": "add", "scope": "document",
                 "add_tools": [{"from_type": "flat end mill", "diameter": "10 mm"}]},
                 lambda p: p.get("added") == 1 and p.get("tool_count", 0) >= 1, None),
                _DESIGN]
    if family == "finale":
        return [("view_switch_workspace", {"workspace": "manufacture"}, "ok", None),
                ("view_set", {"action": "display", "categories": ["sketches"],
                              "visible": False}, "ok", None)]
    return []


def showcase_shapes(raw=False, slots=None):
    """Build the four measured cameos without replaying the modelling benches."""
    ball = next(i for i, row in enumerate(_MOTION)
                if row[0] == "model_create_component" and row[1].get("name") == "BallSphere")
    torus = next(i for i, row in enumerate(_MOTION)
                 if row[0] == "model_create_component" and row[1].get("name") == "TorusRing")
    face = next(i for i, row in enumerate(_SOLIDS)
                if row[0] == "find_geometry" and row[3] and row[3][0] == "fc_body")
    orbit = next(i for i in range(face + 1, len(_SOLIDS))
                 if _SOLIDS[i][0] == "model_pattern_circular")
    rows = (list(_MOTION[ball:torus])
            + _component_block(_MOTION, "TorusRing", "joint_at_geometry")
            + _component_block(_MOTION, "MateSeat", "design_recompute")
            + _component_block(_SOLIDS, "FeatureCameo", "model_draft")
            + list(_SOLIDS[face:orbit + 1]))
    return list(rows) if raw else _placed(rows, FAMILY_SLOTS["showcase"] if slots is None else slots)
