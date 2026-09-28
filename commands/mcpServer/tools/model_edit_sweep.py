# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Replace one profile or path operand on a parametric Sweep feature."""

import hashlib

import adsk.core
import adsk.fusion

from ..mcp_primitives.tool import Tool
from ..mcp_primitives.item import Item, Verification
from ..mcp_primitives.registry import register
from . import _assert, _common, _geom, _inputs, _sketch_detail, _sweep_common
from ._common import counted, error, ok, safe


_FEATURE = _inputs.FeatureRef("feature", required=True)
_ACTION = _inputs.Choice("action", ("profile", "path"), required=True)
_SPEC = [_FEATURE, _ACTION]
_UNREAD = object()


def _profile_members(profile):
    """The profile's native identity or ordered open-curve identities, or None."""
    entity = _common._native_of(profile)
    if safe(lambda: entity.objectType) == "adsk::fusion::Path":
        return _path_members(entity)
    if safe(lambda: entity.objectType) == "adsk::core::ObjectCollection":
        count = counted(lambda: entity.count)
        if not count:
            return None
        keys = [_common.native_identity(safe(lambda i=i: entity.item(i))) for i in range(count)]
        return tuple(keys) if all(keys) else None
    key = _common.native_identity(entity)
    return (key,) if key is not None else None


def _path_members(path):
    """Ordered native identities of a path's actual member entities, or None."""
    count = counted(lambda: path.count)
    if not count:
        return None
    keys = [_common.native_identity(safe(lambda i=i: path.item(i).entity)) for i in range(count)]
    return tuple(keys) if all(keys) else None


def _definition(feature):
    """The edit-position sweep definition, or None when a required getter fails."""
    profile = _profile_members(safe(lambda: feature.profile))
    path = _path_members(safe(lambda: feature.path))
    operation = safe(lambda: feature.operation)
    orientation = safe(lambda: feature.orientation)
    solid = safe(lambda: feature.isSolid)
    if (profile is None or path is None or operation is None or orientation is None
            or solid not in (True, False)):
        return None
    return {"profile": profile, "path": path, "operation": operation,
            "orientation": orientation, "is_solid": solid}


def _definition_report(definition):
    """A compact account of read-back members and retained mode controls."""
    if definition is None:
        return None
    profile, path = definition["profile"], definition["path"]
    return {"profile_signature": hashlib.sha256(repr(profile).encode("ascii")).hexdigest()[:16],
            "profile_members": len(profile) if isinstance(profile, tuple) else 1,
            "path_signature": hashlib.sha256(repr(path).encode("ascii")).hexdigest()[:16],
            "path_curves": len(path), "operation": definition["operation"],
            "orientation": definition["orientation"], "is_solid": definition["is_solid"]}


def _participants(feature, operation):
    """Native participant bodies for a boolean sweep, or None on an unreadable list."""
    if operation == adsk.fusion.FeatureOperations.NewBodyFeatureOperation:
        return []
    bodies = safe(lambda: list(feature.participantBodies))
    if bodies is None:
        return None
    native = [_common._native_of(body) for body in bodies]
    keys = [_common.native_identity(body) for body in native]
    return native if native and len(native) == len(set(keys)) and all(keys) else None


def _participant_keys(feature, operation):
    """Native participant identities after a setter, or None when unreadable."""
    bodies = _participants(feature, operation)
    return None if bodies is None else {_common.native_identity(body) for body in bodies}


def _all_shapes(design):
    """Native body snapshots across components, or None on an unreadable census."""
    components = safe(lambda: list(design.allComponents))
    if not components:
        return None
    rows = {}
    for component in components:
        bodies = safe(lambda c=component: c.bRepBodies)
        count = counted(lambda: bodies.count)
        if count is None:
            return None
        for i in range(count):
            body = safe(lambda i=i: bodies.item(i))
            key = _common.native_identity(body)
            shape = _geom.body_shape(body)
            if key is None or shape is None or key in rows:
                return None
            rows[key] = {"component": safe(lambda c=component: c.name),
                         "body": safe(lambda b=body: b.name), "shape": shape}
    return rows


def _feature_body_keys(feature):
    """Native identities of result bodies, or None on an unreadable collection."""
    bodies = safe(lambda: feature.bodies)
    count = counted(lambda: bodies.count)
    if count is None:
        return None
    keys = {_common.native_identity(safe(lambda i=i: bodies.item(i))) for i in range(count)}
    return None if None in keys else keys


def _health(design, marker):
    """Evaluated timeline errors and warnings, or None when a state cannot be read."""
    timeline = safe(lambda: design.timeline)
    states = adsk.fusion.FeatureHealthStates
    known = (states.HealthyFeatureHealthState, states.WarningFeatureHealthState,
             states.ErrorFeatureHealthState)
    if any(safe(lambda i=i: timeline.item(i).healthState) not in known for i in range(marker)):
        return None
    errors, warnings, total = _common.timeline_health(design, limit=marker)
    return {"errors": errors, "warnings": warnings} if total == marker else None


def _same_feature(design, token, feature, index, count):
    """Whether the saved feature still occupies its original timeline row."""
    found = safe(lambda: design.findEntityByToken(token))
    if found is None:
        return None
    return (any(entity == feature for entity in found)
            and safe(lambda: feature.isValid) is True
            and counted(lambda: feature.timelineObject.index) == index
            and counted(lambda: design.timeline.count) == count)


def _operand_owner(entity):
    """The native profile or path member's component and source timeline index."""
    native = _common._native_of(entity)
    source = (safe(lambda: native.parentSketch) or safe(lambda: native.body)
              or native)
    owner = safe(lambda: source.parentComponent)
    row = counted(lambda: source.timelineObject.index)
    if row is None and safe(lambda: native.parentSketch) is not None:
        row = counted(lambda: native.parentSketch.timelineObject.index)
    return owner, row


def _operand_error(operand, action, component, index):
    """A refusal for a future, foreign or invalid replacement operand, or None."""
    if action == "profile" and safe(lambda: operand.objectType) == "adsk::fusion::Path":
        members = [safe(lambda i=i: operand.item(i).entity)
                   for i in range(counted(lambda: operand.count) or 0)]
    elif action == "profile" and safe(lambda: operand.objectType) == "adsk::core::ObjectCollection":
        members = list(_common.iter_collection(operand))
    elif action == "profile":
        members = [operand]
    else:
        members = [operand.item(i).entity for i in range(operand.count)]
    if not members:
        return f"'{action}' has no readable members."
    for member in members:
        owner, row = _operand_owner(member)
        if _common.same_component(owner, component) is not True:
            return f"'{action}' has a member outside the Sweep's owning component."
        if (row is None and safe(lambda m=member: m.parentSketch) is not None) or (
                row is not None and row >= index):
            return f"'{action}' has a member at row {row}; every source must precede Sweep row {index}."
        if row is None:
            body = safe(lambda m=member: _common._native_of(m).body)
            bodies = safe(lambda: component.bRepBodies)
            edges = safe(lambda: body.edges)
            body_key = _common.native_identity(body)
            member_key = _common.native_identity(member)
            body_count = counted(lambda: bodies.count)
            edge_count = counted(lambda: edges.count)
            if (body_key is None or member_key is None or body_count is None
                    or edge_count is None or not any(
                        _common.native_identity(safe(lambda i=i: bodies.item(i))) == body_key
                        for i in range(body_count)) or not any(
                        _common.native_identity(safe(lambda i=i: edges.item(i))) == member_key
                        for i in range(edge_count))):
                return f"'{action}' has an edge absent from its evaluated source body at the Sweep row."
        if safe(lambda m=member: m.isValid) is not True:
            return f"'{action}' has an invalid member at the Sweep edit position."
    return None


def _inactive_link_count(feature, index):
    """Count same-row bodyless rolled-back Sweep companions, or return None."""
    links = safe(lambda: feature.linkedFeatures)
    count = counted(lambda: links.count)
    if count is None:
        return None
    states = adsk.fusion.FeatureHealthStates
    for i in range(count):
        link = safe(lambda i=i: links.item(i))
        if (link is None or safe(lambda l=link: l.objectType) != adsk.fusion.SweepFeature.classType()
                or counted(lambda l=link: l.timelineObject.index) != index
                or safe(lambda l=link: l.healthState) != states.RolledBackFeatureHealthState
                or counted(lambda l=link: l.bodies.count) != 0):
            return None
    return count


def _target_error(feature, label):
    """A refusal for sweep forms whose profile/path setters are outside this tool."""
    if safe(lambda: feature.objectType) != adsk.fusion.SweepFeature.classType():
        return f"'{label}' is not a Sweep feature. Use design_get(include=['timeline'])."
    for name, want in (("isParametric", True), ("isSuppressed", False)):
        got = safe(lambda n=name: getattr(feature, n))
        if got is not want:
            return f"'{label}' has {name}={got}; this edit requires {name}={want}."
    if safe(lambda: feature.baseFeature, _UNREAD) is not None:
        return f"'{label}' is not a standalone parametric Sweep."
    index = counted(lambda: feature.timelineObject.index)
    if index is None or _inactive_link_count(feature, index) is None:
        return f"'{label}' has linked features outside readable same-row bodyless rolled-back Sweeps; inspect design_get."
    return None


def handler(feature: str = "", action: str = "", profile=None, path=None,
            component: str = "") -> dict:
    """Replace one Sweep operand and report definition, geometry, scope and health evidence."""
    raw = dict(locals())
    values, refusal = _inputs.resolve_inputs(_SPEC, raw)
    if refusal:
        return refusal
    action = values["action"]
    for name in ("profile", "path"):
        if name != action and raw[name] not in (None, "", []):
            return error(f"'{name}' is unused for action='{action}'; remove it.")
    if raw[action] in (None, "", []):
        return error(f"action='{action}' requires '{action}'.")
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
    component_owner = safe(lambda: entity.parentComponent)
    if None in (marker, count, index) or not token or component_owner is None:
        return error(f"'{label}' has unreadable timeline identity; nothing was edited.")
    if marker <= index:
        return error(f"'{label}' is after marker {marker}; roll after it with design_edit_timeline.")
    linked_before = _inactive_link_count(entity, index)
    if linked_before is None:
        return error(f"'{label}' has unreadable or active linked features; nothing was edited.")
    health_before = _health(design, marker)
    if health_before is None:
        return error(f"'{label}'s evaluated-health census is unreadable; nothing was edited.")
    failure = restore_failure = post_error_read_failure = None
    attempted = replayed = False
    definition_before = definition_after = None
    participants_before = participants_after = participant_names = None
    desired = before_shapes = after_shapes = target_before = target_after = None
    linked_evaluated = linked_restored = None
    sketch_curve_count = None
    try:
        if entity.timelineObject.rollTo(True) is not True or counted(lambda: timeline.markerPosition) != index:
            raise RuntimeError("Fusion refused the Sweep edit position.")
        if (safe(lambda: entity.guideRail, _UNREAD) is not None
                or safe(lambda: len(entity.guideSurfaces), _UNREAD) != 0
                or safe(lambda: entity.solidBody, _UNREAD) is not None):
            raise ValueError("Sweep guide or solid-tool definition is not absent/readable at the edit position.")
        timeline.markerPosition = index + 1
        if counted(lambda: timeline.markerPosition) != index + 1:
            raise RuntimeError("The original Sweep could not be evaluated for a body census.")
        before_shapes = _all_shapes(design)
        target_before = _feature_body_keys(entity)
        if before_shapes is None or not target_before:
            raise ValueError("The original Sweep's body census is unreadable.")
        if entity.timelineObject.rollTo(True) is not True or counted(lambda: timeline.markerPosition) != index:
            raise RuntimeError("The Sweep could not return to its edit position.")
        definition_before = _definition(entity)
        if definition_before is None:
            raise ValueError("The Sweep definition is unreadable at its edit position.")
        operation = definition_before["operation"]
        allowed_operations = (adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                              adsk.fusion.FeatureOperations.JoinFeatureOperation,
                              adsk.fusion.FeatureOperations.CutFeatureOperation,
                              adsk.fusion.FeatureOperations.IntersectFeatureOperation)
        if operation not in allowed_operations:
            raise ValueError("This Sweep operation is outside model_sweep's editable operation set.")
        participants = _participants(entity, operation)
        if participants is None:
            raise ValueError("Current boolean participants are empty or unreadable; their material scope cannot be retained.")
        participants_before = {_common.native_identity(body) for body in participants}
        participant_names = [safe(lambda b=body: b.name) for body in participants]
        if action == "profile":
            operand, solid, open_profile, host, source_sketch, refusal = _sweep_common.resolve_profile(
                design, component_owner, profile, not definition_before["is_solid"], component)
            if refusal:
                raise ValueError(refusal)
            if _common.same_component(host, component_owner) is not True or solid != definition_before["is_solid"]:
                raise ValueError("Replacement profile must keep this Sweep's owner and solid/surface mode.")
            checked_operand = operand
            if open_profile:
                source_name = safe(lambda: source_sketch.name)
                if not source_name:
                    raise ValueError("The open profile's source sketch name is unreadable.")
                checked_operand, _label, refusal = _common.build_path(host, f"sketch:{source_name}")
                if refusal:
                    raise ValueError(refusal)
                source_count = _common.path_sketch_curve_count(host, f"sketch:{source_name}")
                if source_count is None or counted(lambda: checked_operand.count) != source_count:
                    raise ValueError("The open profile's source path omits sketch curves.")
            desired = _profile_members(checked_operand)
        else:
            operand, _label, refusal = _common.build_path(component_owner, path)
            if refusal:
                raise ValueError(refusal)
            desired = _path_members(operand)
            sketch_curve_count = _common.path_sketch_curve_count(component_owner, path)
            checked_operand = operand
        if desired is None:
            raise ValueError(f"Replacement '{action}' members could not be read.")
        refusal = _operand_error(checked_operand, action, component_owner, index)
        if refusal:
            raise ValueError(refusal)
        if desired == definition_before[action]:
            raise ValueError(f"'{label}' already uses that {action}; nothing was edited.")
        attempted = True
        setter_failure = None
        try:
            setattr(entity, action, operand)
        except Exception as exc:
            setter_failure = exc
        # Native setters can expand scope even when they raise after a partial assignment.
        if participants:
            entity.participantBodies = list(participants)
            replayed = True
        participants_after = _participant_keys(entity, operation)
        definition_after = _definition(entity)
        if setter_failure is not None:
            raise setter_failure
        timeline.markerPosition = index + 1
        if counted(lambda: timeline.markerPosition) != index + 1:
            raise RuntimeError("The edited Sweep could not be evaluated for a body census.")
        after_shapes = _all_shapes(design)
        target_after = _feature_body_keys(entity)
        linked_evaluated = _inactive_link_count(entity, index)
        if linked_evaluated is None:
            raise RuntimeError("The edited Sweep has an active or unreadable linked feature.")
        if entity.timelineObject.rollTo(True) is not True or counted(lambda: timeline.markerPosition) != index:
            raise RuntimeError("The evaluated Sweep could not be rolled back for definition verification.")
        definition_after = _definition(entity)
        participants_after = _participant_keys(entity, operation)
    except Exception as exc:
        failure = str(exc)
        if attempted:
            if counted(lambda: timeline.markerPosition) == index:
                definition_after = _definition(entity)
                participants_after = _participant_keys(entity, definition_before["operation"])
            if after_shapes is None:
                try:
                    timeline.markerPosition = index + 1
                    if counted(lambda: timeline.markerPosition) != index + 1:
                        raise RuntimeError("The partial edit could not be evaluated.")
                    after_shapes = _all_shapes(design)
                    target_after = _feature_body_keys(entity)
                    if after_shapes is None or target_after is None:
                        raise RuntimeError("The partial edit body census is unreadable.")
                except Exception as read_exc:
                    post_error_read_failure = str(read_exc)
        elif definition_before is not None:
            definition_after = _definition(entity)
    finally:
        try:
            timeline.markerPosition = marker
        except Exception as exc:
            restore_failure = str(exc)
    restored = counted(lambda: timeline.markerPosition) == marker
    linked_restored = _inactive_link_count(entity, index) if restored else None
    same = _same_feature(design, token, entity, index, count)
    state, compute_failure = _assert.compute_state(entity)
    health_after = _health(design, marker) if restored else None
    new_errors = (None if health_after is None else
                  [name for name in health_after["errors"] if name not in health_before["errors"]])
    new_warnings = (None if health_after is None else
                    [name for name in health_after["warnings"] if name not in health_before["warnings"]])
    definition_matches = (definition_before is not None and definition_after is not None
                          and definition_after[action] == desired
                          and all(definition_after[key] == definition_before[key]
                                  for key in definition_before if key != action))
    scope_matches = participants_after == participants_before if participants_after is not None else None
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
    details = {"feature": label, "action": action, "mutation_attempted": attempted,
               "definition_before": _definition_report(definition_before),
               "definition_after": _definition_report(definition_after),
               "definition_matches": definition_matches, "participants_replayed": replayed,
               "participant_scope_preserved": scope_matches,
               "retained_participants": participant_names, "geometry_changed": geometry_changed,
               "target_before": list(target_before_shapes.values()) if target_before_shapes is not None else None,
               "target_after": list(target_after_shapes.values()) if target_after_shapes is not None else None,
               "outside_body_changes": outside_changes,
               "outside_check": "all bodies present immediately after the Sweep, before downstream features",
               "same_feature": same,
               "inactive_linked_before": linked_before,
               "inactive_linked_evaluated": linked_evaluated,
               "inactive_linked_after": linked_restored,
               "marker_before": marker, "marker_after": counted(lambda: timeline.markerPosition),
               "marker_restored": restored, "feature_health": state,
               "unevaluated_timeline_items": count - marker,
               "post_error_read_failure": post_error_read_failure,
               "new_timeline_errors": new_errors, "new_timeline_warnings": new_warnings,
               "geometry_frame": "owning_component", "geometry_units": "cm, cm2, cm3"}
    if action == "path":
        details["path_curves"] = len(desired) if desired is not None else None
        if sketch_curve_count is not None:
            details["path_sketch_curves"] = sketch_curve_count
    if (failure or restore_failure or not restored or same is not True
            or linked_evaluated is None or linked_restored is None
            or definition_matches is not True or scope_matches is not True
            or geometry_changed is not True or outside_changes != [] or state != "healthy"
            or new_errors is None or new_errors or new_warnings):
        reason = (failure or restore_failure or
                  ("New evaluated timeline errors or warnings appeared." if new_errors or new_warnings else "")
                  or ("Material outside the Sweep result changed." if outside_changes else "")
                  or str(compute_failure or "")
                  or "Definition, geometry, scope, identity, marker or health verification failed.")
        result = error(f"Editing '{label}': {reason} Inspect design_get(include=['timeline']); observed state is in details.")
        result["details"] = details
        result["content"].extend(ok({"details": details})["content"])
        return result
    details["edited"] = True
    details["note"] = ("Sweep operand changed on the same feature. Boolean edits retain the current "
                       "participants; newly reached bodies are excluded. Inspect model_inspect.")
    if action == "path":
        details["note"] += " " + _common.path_chain_warning(len(desired), sketch_curve_count, "sweep")
        details["note"] = details["note"].strip()
    return ok(details)


tool = _inputs.apply_to_tool(
    Tool.create_simple(name="model_edit_sweep", description=(
        "Edit Sweep profile/path. Keep current boolean participants; exclude newly reached "
        "bodies. Read model_inspect.")),
    _SPEC)
tool.add_input_property("profile", _inputs.ProfileRef("profile", scope_input="component").schema())
tool.add_input_property("path", {"type": ["string", "array"], "items": {"type": "string"},
                                 "description": "Edge handle(s) or sketch:<name>."})
tool.add_input_property(*_sketch_detail.COMPONENT_SCOPE)
tool.strict_schema()
item = Item.create_tool_item(
    tool=tool, write="write", handler=handler, run_on_main_thread=True,
    verification=Verification(kind="inline", rung="geometry",
                              evidence_test="tests/unit/test_model_edit_sweep.py::test_ignored_setter_is_an_error"))


def register_tool():
    register(item)
