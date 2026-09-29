# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Retarget or remove one interior profile section of a simple solid Loft."""

import hashlib
import math

import adsk.fusion

from ..mcp_primitives.tool import Tool
from ..mcp_primitives.item import Item, Verification
from ..mcp_primitives.registry import register
from . import _assert, _common, _inputs, _sketch_detail
from ._edit_feature_common import (all_shapes as _all_shapes,
                                   feature_body_keys as _feature_body_keys,
                                   health as _health, same_feature as _same_feature)
from ._common import counted, error, ok, safe


_FEATURE = _inputs.FeatureRef("feature", required=True)
_ACTION = _inputs.Choice("action", ("retarget", "remove"), required=True)
_SPEC = [_FEATURE, _ACTION]
_UNREAD = object()


def _section_keys(feature):
    """Ordered native profile identities, or None when a section is unreadable."""
    sections = safe(lambda: feature.loftSections)
    count = counted(lambda: sections.count)
    if count is None or count < 2:
        return None
    keys = []
    for i in range(count):
        section = safe(lambda i=i: sections.item(i))
        entity = safe(lambda s=section: s.entity)
        if safe(lambda e=entity: e.objectType) != adsk.fusion.Profile.classType():
            return None
        key = _common.native_identity(entity)
        if key is None:
            return None
        keys.append(key)
    return tuple(keys)


def _end_state(section):
    """A Loft end's type and applicable parameter identity, expression and value."""
    condition = safe(lambda: section.endCondition)
    kind = safe(lambda: condition.objectType)
    fields = {"adsk::fusion::LoftFreeEndCondition": (),
              "adsk::fusion::LoftTangentEndCondition": ("weight",),
              "adsk::fusion::LoftSmoothEndCondition": ("weight",),
              "adsk::fusion::LoftDirectionEndCondition": ("weight", "angle"),
              "adsk::fusion::LoftPointSharpEndCondition": (),
              "adsk::fusion::LoftPointTangentEndCondition": ("weight",)}.get(kind)
    if fields is None:
        return None
    parameters = []
    for field in fields:
        param = safe(lambda f=field: getattr(condition, f))
        name = safe(lambda p=param: p.name)
        expression = safe(lambda p=param: p.expression)
        value = safe(lambda p=param: p.value)
        if (not isinstance(name, str) or not name
                or not isinstance(expression, str) or not expression
                or not isinstance(value, (int, float)) or not math.isfinite(value)):
            return None
        parameters.append((field, name, expression, value))
    return (kind, tuple(parameters))


def _definition(feature):
    """Ordered profiles and retained Loft controls at its edit position."""
    sections = _section_keys(feature)
    operation = safe(lambda: feature.operation)
    solid = safe(lambda: feature.isSolid)
    closed = safe(lambda: feature.isClosed)
    guides = counted(lambda: feature.centerLineOrRails.count)
    if (sections is None or operation is None or solid not in (True, False)
            or closed not in (True, False) or guides is None):
        return None
    last = len(sections) - 1
    ends = tuple(_end_state(safe(lambda i=i: feature.loftSections.item(i)))
                 for i in (0, last))
    if None in ends:
        return None
    return {"sections": sections, "operation": operation, "is_solid": solid,
            "is_closed": closed, "guide_count": guides, "ends": ends}


def _definition_report(definition):
    """Compact ordered definition evidence for a tool result."""
    if definition is None:
        return None
    sections = definition["sections"]
    return {"section_count": len(sections),
            "section_signatures": [hashlib.sha256(repr(key).encode("ascii")).hexdigest()[:16]
                                   for key in sections],
            "operation": definition["operation"], "is_solid": definition["is_solid"],
            "is_closed": definition["is_closed"], "guide_count": definition["guide_count"],
            "end_controls": definition["ends"]}


def _target_error(feature, label):
    """A refusal for Loft forms outside interior profile-section editing."""
    if safe(lambda: feature.objectType) != adsk.fusion.LoftFeature.classType():
        return f"'{label}' is not a Loft feature. Read design_get(include=['timeline'])."
    for name, want in (("isParametric", True), ("isSuppressed", False)):
        got = safe(lambda n=name: getattr(feature, n))
        if got is not want:
            return f"'{label}' has {name}={got}; this edit requires {name}={want}."
    if safe(lambda: feature.baseFeature, _UNREAD) is not None:
        return f"'{label}' is not a standalone parametric Loft."
    links = safe(lambda: feature.linkedFeatures)
    link_count = counted(lambda: links.count)
    if link_count != 0:
        return f"'{label}' has {link_count} linked features or an unreadable link count; this edit requires none."
    return None


def _operand_error(profile, component, index):
    """A refusal for a foreign, future or invalid replacement profile."""
    if safe(lambda: profile.objectType) != adsk.fusion.Profile.classType():
        return "'profile' must resolve to one sketch profile."
    sketch = safe(lambda: profile.parentSketch)
    owner = safe(lambda: sketch.parentComponent)
    row = counted(lambda: sketch.timelineObject.index)
    if _common.same_component(owner, component) is not True:
        return "'profile' is outside the Loft's owning component."
    if row is None or row >= index:
        return f"'profile' source row {row} must precede Loft row {index}."
    if safe(lambda: profile.isValid) is not True:
        return "'profile' is invalid at the Loft edit position."
    return None


def handler(feature: str = "", action: str = "", section_index: int = None,
            profile=None, component: str = "") -> dict:
    """Edit one interior Loft section and report definition and evaluated evidence."""
    values, refusal = _inputs.resolve_inputs(_SPEC, dict(locals()))
    if refusal:
        return refusal
    action = values["action"]
    if type(section_index) is not int or section_index < 0:
        return error(f"'section_index' must be a nonnegative integer (got {section_index!r}).")
    if action == "retarget" and profile in (None, "", []):
        return error("action='retarget' requires 'profile'.")
    if action == "remove" and profile not in (None, "", []):
        return error("'profile' is unused for action='remove'; remove it.")
    entity, label = values["feature"]
    refusal = _target_error(entity, label)
    if refusal:
        return error(refusal)
    design = _common.design()
    timeline = safe(lambda: design.timeline)
    marker = counted(lambda: timeline.markerPosition)
    count = counted(lambda: timeline.count)
    index = counted(lambda: entity.timelineObject.index)
    token = safe(lambda: entity.entityToken)
    owner = safe(lambda: entity.parentComponent)
    if None in (marker, count, index) or not token or owner is None:
        return error(f"'{label}' has unreadable timeline identity; nothing was edited.")
    if marker <= index:
        return error(f"'{label}' is after marker {marker}; roll after it with design_edit_timeline.")
    health_before = _health(design, marker)
    if health_before is None:
        return error(f"'{label}'s evaluated-health census is unreadable; nothing was edited.")
    failure = restore_failure = post_error_read_failure = None
    attempted = False
    definition_before = definition_after = desired = None
    before_shapes = after_shapes = target_before = target_after = None
    try:
        if entity.timelineObject.rollTo(True) is not True or counted(lambda: timeline.markerPosition) != index:
            raise RuntimeError("Fusion refused the Loft edit position.")
        definition_before = _definition(entity)
        if definition_before is None:
            raise ValueError("The Loft definition is unreadable at its edit position.")
        sections = definition_before["sections"]
        if action == "remove" and len(sections) - 1 < 2:
            raise ValueError("Removing this section would leave fewer than two Loft sections.")
        if section_index == 0 or section_index >= len(sections) - 1:
            raise ValueError(f"'section_index'={section_index} must select an interior section of {len(sections)}.")
        if (definition_before["operation"] != adsk.fusion.FeatureOperations.NewBodyFeatureOperation
                or definition_before["is_solid"] is not True or definition_before["is_closed"] is not False
                or definition_before["guide_count"] != 0):
            raise ValueError("Loft must be open, unguided, solid and use the NEW body operation.")
        if action == "retarget":
            operand, refusal = _inputs.ProfileRef("profile", scope_input="component").resolve(
                profile, component)
            if refusal:
                raise ValueError(refusal)
            refusal = _operand_error(operand, owner, index)
            if refusal:
                raise ValueError(refusal)
            replacement = _common.native_identity(operand)
            if replacement is None:
                raise ValueError("'profile' native identity is unreadable.")
            desired = sections[:section_index] + (replacement,) + sections[section_index + 1:]
            if desired == sections:
                raise ValueError(f"'{label}' already uses that profile at section {section_index}.")
        else:
            desired = sections[:section_index] + sections[section_index + 1:]
        timeline.markerPosition = index + 1
        if counted(lambda: timeline.markerPosition) != index + 1:
            raise RuntimeError("The original Loft could not be evaluated for a body census.")
        before_shapes = _all_shapes(design)
        target_before = _feature_body_keys(entity)
        if before_shapes is None or not target_before:
            raise ValueError("The original Loft's body census is unreadable.")
        if entity.timelineObject.rollTo(True) is not True or counted(lambda: timeline.markerPosition) != index:
            raise RuntimeError("The Loft could not return to its edit position.")
        attempted = True
        section = entity.loftSections.item(section_index)
        if action == "retarget":
            section.entity = operand
        elif section.deleteMe() is not True:
            raise RuntimeError(f"Loft section {section_index} deleteMe() did not return true.")
        definition_after = _definition(entity)
        timeline.markerPosition = index + 1
        if counted(lambda: timeline.markerPosition) != index + 1:
            raise RuntimeError("The edited Loft could not be evaluated for a body census.")
        after_shapes = _all_shapes(design)
        target_after = _feature_body_keys(entity)
        if entity.timelineObject.rollTo(True) is not True or counted(lambda: timeline.markerPosition) != index:
            raise RuntimeError("The evaluated Loft could not return to its edit position.")
        definition_after = _definition(entity)
    except Exception as exc:
        failure = str(exc)
        if definition_before is not None and counted(lambda: timeline.markerPosition) == index:
            definition_after = _definition(entity)
        if attempted and after_shapes is None:
            try:
                timeline.markerPosition = index + 1
                if counted(lambda: timeline.markerPosition) != index + 1:
                    raise RuntimeError("The partial Loft edit could not be evaluated.")
                after_shapes = _all_shapes(design)
                target_after = _feature_body_keys(entity)
                if after_shapes is None or target_after is None:
                    raise RuntimeError("The partial Loft body census is unreadable.")
            except Exception as read_exc:
                post_error_read_failure = str(read_exc)
    finally:
        try:
            timeline.markerPosition = marker
        except Exception as exc:
            restore_failure = str(exc)
    restored = counted(lambda: timeline.markerPosition) == marker
    same = _same_feature(design, token, entity, index, count)
    state, compute_failure = _assert.compute_state(entity)
    health_after = _health(design, marker) if restored else None
    new_errors = (None if health_after is None else
                  [name for name in health_after["errors"] if name not in health_before["errors"]])
    new_warnings = (None if health_after is None else
                    [name for name in health_after["warnings"] if name not in health_before["warnings"]])
    definition_matches = (definition_before is not None and definition_after is not None
                          and definition_after["sections"] == desired
                          and all(definition_after[key] == definition_before[key]
                                  for key in definition_before if key != "sections"))
    target_before_shapes = ({key: before_shapes[key]["shape"] for key in target_before}
                            if before_shapes is not None and target_before is not None
                            and target_before <= set(before_shapes) else None)
    target_after_shapes = ({key: after_shapes[key]["shape"] for key in target_after}
                           if after_shapes is not None and target_after is not None
                           and target_after <= set(after_shapes) else None)
    geometry_changed = (None if target_before_shapes is None or target_after_shapes is None else
                        sorted(target_before_shapes.values(), key=repr) !=
                        sorted(target_after_shapes.values(), key=repr))
    outside = (set(before_shapes) - target_before if before_shapes is not None
               and target_before is not None else None)
    outside_changes = (None if after_shapes is None or target_after is None or outside is None else
                       [before_shapes[key]["body"] for key in outside
                        if key not in after_shapes or after_shapes[key] != before_shapes[key]]
                       + [after_shapes[key]["body"] for key in set(after_shapes) - set(before_shapes)
                          if key not in target_after])
    details = {"feature": label, "action": action, "section_index": section_index,
               "mutation_attempted": attempted, "definition_before": _definition_report(definition_before),
               "definition_after": _definition_report(definition_after),
               "definition_matches": definition_matches, "geometry_changed": geometry_changed,
               "target_before": list(target_before_shapes.values()) if target_before_shapes is not None else None,
               "target_after": list(target_after_shapes.values()) if target_after_shapes is not None else None,
               "outside_body_changes": outside_changes,
               "outside_check": "all bodies immediately after the Loft, before downstream features",
               "same_feature": same, "marker_before": marker,
               "marker_after": counted(lambda: timeline.markerPosition), "marker_restored": restored,
               "feature_health": state, "unevaluated_timeline_items": count - marker,
               "post_error_read_failure": post_error_read_failure,
               "new_timeline_errors": new_errors, "new_timeline_warnings": new_warnings,
               "geometry_frame": "owning_component", "geometry_units": "cm, cm2, cm3"}
    if (failure or restore_failure or not restored or same is not True
            or definition_matches is not True or geometry_changed is not True
            or outside_changes != [] or state != "healthy"
            or new_errors is None or new_errors or new_warnings):
        reason = (failure or restore_failure or
                  ("New evaluated timeline errors or warnings appeared." if new_errors or new_warnings else "")
                  or ("Material outside the Loft result changed." if outside_changes else "")
                  or str(compute_failure or "")
                  or "Definition, geometry, identity, marker or health verification failed.")
        result = error(f"Editing '{label}': {reason} Inspect design_get(include=['timeline']); observed state is in details.")
        result["details"] = details
        result["content"].extend(ok({"details": details})["content"])
        return result
    details["edited"] = True
    details["note"] = "Loft section changed on the same feature. Inspect model_inspect."
    return ok(details)


tool = _inputs.apply_to_tool(
    Tool.create_simple(name="model_edit_loft", description=(
        "Edit interior sections of an open unguided solid NEW Loft. "
        "Read design_get(include=['definition']).")),
    _SPEC)
tool.add_input_property("section_index", {"type": "integer", "minimum": 0,
                                          "description": "Zero-based interior section index."})
tool.add_required_input("section_index")
tool.add_input_property("profile", _inputs.ProfileRef("profile", scope_input="component").schema())
tool.add_input_property(*_sketch_detail.COMPONENT_SCOPE)
tool.strict_schema()
item = Item.create_tool_item(
    tool=tool, write="write", handler=handler, run_on_main_thread=True,
    verification=Verification(kind="inline", rung="geometry",
                              evidence_test="tests/unit/test_model_edit_loft.py::test_ignored_retarget_is_error"))


def register_tool():
    register(item)
