# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Copy or edit a design-local sheet-metal rule."""

import math
import re

from ..mcp_primitives.tool import Tool
from ..mcp_primitives.item import Item, Verification
from ..mcp_primitives.registry import register
from ._common import error, ok, safe
from . import _common, _inputs, _sheet_common

_RULE = _inputs.SheetMetalRuleRef("rule", required=True)
_ACTION = _inputs.Choice("action", ("copy", "update"), default="copy")
_LENGTH = re.compile(r"^\s*[+]?(?:\d+(?:\.\d*)?|\.\d+)\s*(?:mm|cm|in)\s*$", re.I)
_FIELDS = (("thickness", "thickness"), ("bend_radius", "bendRadius"), ("gap", "gap"))


def _length_cm(expr):
    """Return an explicit-unit positive length in centimeters."""
    match = re.fullmatch(r"\s*([+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(mm|cm|in)\s*", expr, re.I)
    number, unit = float(match.group(1)), match.group(2).lower()
    return number * _common.scale(unit)


def _specs(thickness, bend_radius, gap, k_factor):
    """Return validated explicit-unit expressions and K factor."""
    values = {"thickness": thickness, "bend_radius": bend_radius, "gap": gap}
    for key, expr in values.items():
        if expr is not None and not _LENGTH.fullmatch(expr):
            return None, f"'{key}' value '{expr}' needs a positive literal with mm, cm, or in units."
        if expr is not None and float(re.match(r"\s*([+]?(?:\d+(?:\.\d*)?|\.\d+))", expr).group(1)) <= 0:
            return None, f"'{key}' value '{expr}' must be positive."
    if k_factor is not None and (not isinstance(k_factor, (int, float))
                                 or not math.isfinite(k_factor) or not 0 <= k_factor <= 1):
        return None, f"'k_factor' value '{k_factor}' must be a finite number from 0 to 1."
    return values, None


def handler(action: str = "copy", rule: str = "", name: str = "", thickness: str = None,
            bend_radius: str = None, gap: str = None, k_factor: float = None) -> dict:
    """See TOOL_DESCRIPTION."""
    design = _common.design()
    if design is None:
        return error("No active design. Create or open a design first.")
    choice, cerr = _ACTION.resolve(action)
    if cerr:
        return error(cerr)
    source, rerr = _RULE.resolve(rule)
    if rerr:
        return error(rerr)
    selected, scope = source
    values, verr = _specs(thickness, bend_radius, gap, k_factor)
    if verr:
        return error(verr)
    if choice == "update" and scope != "design":
        return error(f"rule '{rule}' is a library rule; copy it with action='copy' before editing.")
    if choice == "copy":
        new_name = name.strip()
        if not new_name:
            return error("action='copy' needs a nonempty 'name' for the design-local rule.")
        existing = _sheet_common.matching_rules(design, "design", new_name)
        if existing is None:
            return error("Design-local rules could not be read; no copy attempted.")
        if existing:
            return error(f"Design-local rule '{new_name}' already exists; choose another name or update it.")
        local = safe(lambda: design.designSheetMetalRules)
        if local is None or safe(lambda: local.count) in (None, 0):
            return error("Design sheet-metal rule data is uninitialized. Create a root sheet-metal "
                         "component with model_create_component(sheet_metal=true), then retry the copy.")
        before = safe(lambda: local.count)
        try:
            created = local.addByCopy(selected, new_name)
        except Exception as exc:
            return error(f"Could not copy rule '{rule}' as '{new_name}': {exc}. "
                         "Read sheet_get(include=['rules']) before retrying.")
        hits = _sheet_common.matching_rules(design, "design", new_name)
        if created is None or hits is None or len(hits) != 1 or safe(lambda: local.count) != before + 1:
            return error(f"Copy of '{rule}' as '{new_name}' was not verified. "
                         "Read sheet_get(include=['rules']) to inspect any partial effect.")
        target = hits[0]
    else:
        if name.strip():
            return error("'name' applies only to action='copy'; use the scoped rule ref for update.")
        if not any(v is not None for v in values.values()) and k_factor is None:
            return error("action='update' needs thickness, bend_radius, gap, or k_factor.")
        target = selected
    applied = []
    for input_name, native_name in _FIELDS:
        expr = values[input_name]
        if expr is None:
            continue
        value = safe(lambda native_name=native_name: getattr(target, native_name))
        if value is None:
            return error(f"Rule '{safe(lambda: target.name)}' persists; {input_name} could not be read. "
                         f"Applied so far: {applied}. Read sheet_get(include=['rules']).")
        try:
            value.expression = expr
        except Exception as exc:
            return error(f"Rule '{safe(lambda: target.name)}' persists; {input_name}='{expr}' failed: {exc}. "
                         f"Applied so far: {applied}. Read sheet_get(include=['rules']).")
        landed = safe(lambda value=value: value.expression)
        actual_cm = safe(lambda value=value: value.value)
        expected_cm = _length_cm(expr)
        if landed is None or actual_cm is None or not math.isclose(actual_cm, expected_cm, rel_tol=1e-8, abs_tol=1e-9):
            return error(f"Rule '{safe(lambda: target.name)}' persists; {input_name}='{expr}' "
                         f"did not evaluate to {expected_cm} cm (got {actual_cm} cm; expression '{landed}'). "
                         f"Applied so far: {applied}.")
        applied.append(input_name)
    if k_factor is not None:
        try:
            target.kFactor = float(k_factor)
        except Exception as exc:
            return error(f"Rule '{safe(lambda: target.name)}' persists; k_factor={k_factor} failed: {exc}. "
                         f"Applied so far: {applied}.")
        landed = safe(lambda: target.kFactor)
        if landed is None or not math.isclose(landed, k_factor, abs_tol=1e-9):
            return error(f"Rule '{safe(lambda: target.name)}' persists; k_factor={k_factor} did not "
                         f"read back (got '{landed}'). Applied so far: {applied}.")
        applied.append("k_factor")
    row = _sheet_common.rule_row(design, target, "design")
    if choice == "copy" and row["name"] != new_name:
        return error(f"Copied rule name '{new_name}' did not persist; actual is '{row['name']}'.")
    return ok({"action": choice, "rule": row, "applied": applied,
               "note": "Design-local rule read back. Assign or convert a component separately."})


TOOL_DESCRIPTION = "Copy a sheet rule into this design, or edit a design rule."

tool = (Tool.create_simple(name="sheet_edit_rule", description=TOOL_DESCRIPTION)
        .add_input_property(*_ACTION.as_property())
        .add_input_property(*_RULE.as_property())
        .add_required_input("rule")
        .add_input_property("name", {"type": "string"})
        .add_input_property("thickness", {"type": "string", "description": "Length with units."})
        .add_input_property("bend_radius", {"type": "string", "description": "Length with units."})
        .add_input_property("gap", {"type": "string", "description": "Length with units."})
        .add_input_property("k_factor", {"type": "number", "minimum": 0, "maximum": 1})
        .strict_schema())
item = Item.create_tool_item(
    tool=tool, write="write", handler=handler, run_on_main_thread=True,
    verification=Verification(kind="effect", rung="value",
                              evidence_test="tests/unit/test_sheet_edit_rule.py::test_copy_requires_initialized_design_rules"))


def register_tool():
    register(item)
