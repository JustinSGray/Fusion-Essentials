# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Set a design parameter's expression, or create it as a user parameter (create=true). WRITES."""

import adsk.core

from ..mcp_primitives.tool import Tool
from ..mcp_primitives.item import Item, Verification
from ..mcp_primitives.registry import register
from ._common import ok, error, safe
from . import _common, _sketch_detail
from ._param_common import _find_parameter, _normalized_expression, _param_summary
from ._joints import (driven_joint_snapshot as _driven_joint_snapshot,
                      driven_joints_reset as _driven_joints_reset, driven_reset_note)

_SKETCH_CAP = 6          # driven sketches whose points are read around one write
_MOVED_CAP = 12          # moved points listed per sketch; moved_count carries the rest


def _driven_sketches(param):
    """[(sketch, [its dimension parameters])] among `param` and its dependentParameters."""
    groups = {}
    for p in [param] + list(_common.iter_collection(safe(lambda: param.dependentParameters))):
        # A dimension parameter's createdBy is its Sketch, not the dimension (measured).
        owner = safe(lambda p=p: p.createdBy)
        if type(owner).__name__ == "Sketch":
            key = _common.native_identity(owner) or safe(lambda p=p: p.name)
            groups.setdefault(key, (owner, []))[1].append(p)
    return list(groups.values())


def _moves_before(param):
    """(the capped driven sketches with their point census read now, how many were left unread)."""
    groups = _driven_sketches(param)
    return ([(sketch, params, _sketch_detail.point_census(sketch))
             for sketch, params in groups[:_SKETCH_CAP]], max(len(groups) - _SKETCH_CAP, 0))


def _dimension_rows(sketch, params):
    """{parameter, entities} for each of the sketch's dimensions whose parameter is in `params`."""
    token_ids = _sketch_detail.sketch_token_ids(sketch)
    rows = []
    for dim in _common.iter_collection(safe(lambda: sketch.sketchDimensions)):
        hit = next((p for p in params if safe(lambda p=p: dim.parameter == p) is True), None)
        if hit is not None:
            rows.append({"parameter": safe(lambda: hit.name),
                         "entities": _sketch_detail.dimension_entities(sketch, dim, token_ids)})
    return rows


def _sketch_move_row(sketch, params, before):
    """One driven sketch's dimensions and the points the write moved; moved is None when unread."""
    moved = _sketch_detail.moved_points(before, _sketch_detail.point_census(sketch))
    row = {"sketch": safe(lambda: sketch.name), "dimensions": _dimension_rows(sketch, params),
           "moved": None, "moved_count": None}
    if moved is not None:
        shown = moved[:_MOVED_CAP]
        ends = _sketch_detail.point_ends(sketch, [ref for ref, _was, _now in shown])
        row["moved"] = [{"id": ref, "from_mm": _sketch_detail.point_mm(was),
                         "to_mm": _sketch_detail.point_mm(now), "ends": ends[ref]}
                        for ref, was, now in shown]
        row["moved_count"] = len(moved)
    return row


def _with_moves(out, taken):
    """`out` plus sketch_moves: each driven sketch's points re-read after the write."""
    read, unread = taken
    if not read:
        return out
    out["sketch_moves"] = [_sketch_move_row(*entry) for entry in read]
    tol = _sketch_detail.MOVE_TOL_CM * _common.CM_TO_UNIT["mm"]
    notes = [f"sketch_moves lists the points that moved over {tol:g} mm, in each sketch's own "
             "coordinates (mm); sketch_get(sketch_name=...) gives that sketch's frame."]
    blind = [f"'{row['sketch']}'" for row in out["sketch_moves"] if row["moved"] is None]
    if blind:
        notes.append(f"The moves in sketch {', '.join(blind)} were not read.")
    if unread:
        out["sketch_moves_unread"] = unread
        notes.append(f"The moves in {unread} more driven sketch(es) were not read.")
    out["note"] = " ".join(([out["note"]] if out.get("note") else []) + notes)
    return out


def _before(design):
    """(driven-joint snapshot, timeline health census) read ahead of the write."""
    return _driven_joint_snapshot(design), _common.timeline_health(design)


def _with_reset(out, before, design):
    """`out`, plus observed driven-joint value changes and newly raised timeline health."""
    joints_before, (errors_before, warnings_before, _total) = before
    reset = _driven_joints_reset(joints_before, _driven_joint_snapshot(design))
    notes = []
    if reset:
        out["driven_joints_reset"] = reset
        notes.append(driven_reset_note(reset))
    errors_after, warnings_after, _total = _common.timeline_health(design)
    new_errors = [n for n in errors_after if n not in errors_before]
    new_warnings = [n for n in warnings_after if n not in warnings_before]
    if new_errors:
        out["new_timeline_errors"] = new_errors
    if new_warnings:
        out["new_timeline_warnings"] = new_warnings
    if new_errors or new_warnings:
        named = ", ".join(new_errors + new_warnings)
        notes.append(f"The value took, and the recompute left {len(new_errors)} new timeline "
                     f"error(s) and {len(new_warnings)} new warning(s): {named}. Nothing was "
                     "rolled back; read design_get(include=['timeline']) for the messages, or "
                     "set the previous value again.")
    if notes:
        out["note"] = " ".join(notes)
    return out


def handler(name: str = "", expression: str = "", create: bool = False,
            unit: str = "mm") -> dict:
    """Set a design parameter's expression, or create it if missing (create=true). WRITES."""
    name = (name or "").strip()
    if not name:
        return error("Provide 'name' - the parameter to set.")
    if (expression or "").strip() == "" and expression != "0":
        return error("Provide 'expression' - the new value/expression for the parameter.")

    design = _common.design()
    if not design:
        return error("No active design (open a document with design geometry).")

    param = _find_parameter(design, name)
    if not param:
        if not create:
            return error(f"Parameter not found: '{name}'. Use param_get to list them, or pass "
                          "create=true to make it a new user parameter.")
        # create-or-update: make a new user parameter with the given expression + unit.
        reads_before = _before(design)
        try:
            vi = adsk.core.ValueInput.createByString(expression)
            param = design.userParameters.add(name, vi, unit or "", "")
        except Exception as e:
            return error(f"Could not create user parameter '{name}' = '{expression}' "
                          f"(unit '{unit}'): {e}.")
        if not param:
            return error(f"Creating user parameter '{name}' returned nothing.")
        return ok(_with_reset({"set": True, "created": True, "name": name,
        "before": None, "after": _param_summary(param)}, reads_before, design))

    before = _param_summary(param)
    reads_before = _before(design)
    moves_before = _moves_before(param)
    try:
        param.expression = expression
    except Exception as e:
        return error(f"Could not set '{name}' to '{expression}': {e}. "
    "(Model/feature parameters may be read-only or require a valid "
    "expression; text parameters need quotes, e.g. \"'text'\".)")

    after = _param_summary(param)
    if after == before:
        if _normalized_expression(expression) == _normalized_expression(before.get("expression")):
            return ok(_with_moves(_with_reset({"set": True, "created": False, "name": name,
                       "already_current": True, "before": before, "after": after},
                       reads_before, design), moves_before))
        return error(f"Assignment raised no error but '{name}' still reads expression "
                     f"'{before.get('expression')}' - setting '{expression}' did not take.")
    return ok(_with_moves(_with_reset({"set": True, "created": False, "name": name,
              "before": before, "after": after}, reads_before, design), moves_before))


TOOL_DESCRIPTION = (
"Set a parameter expression. driven_joints_reset lists value changes, not causes. "
"Discover names with param_get."
)

tool = (
    Tool.create_with_string_input(
        name="param_set",
        description=TOOL_DESCRIPTION,
        input_param_name="name",
        input_param_description="The parameter to set.",
    )
    .add_input_property("expression", {"type": "string",
            "description": "e.g. '2 in', 'StockX/2', \"'text'\"; function args use ';': if(a>=2 in; 10 mm; 5 mm)."})
    .add_input_property("create", {"type": "boolean"})
    .add_input_property("unit", {"type": "string",
            "description": "For a created parameter ('' unitless)."})
    .strict_schema()
)

item = Item.create_tool_item(
    tool=tool, write="write", handler=handler, run_on_main_thread=True,
    verification=Verification(
        kind="inline", rung="value",
        evidence_test="tests/unit/test_param_set.py::TestSetCreateOrUpdate"
                      "::test_silent_no_op_assignment_bites"))


def register_tool():
    register(item)
