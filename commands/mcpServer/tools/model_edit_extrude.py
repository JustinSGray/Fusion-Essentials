# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Edit one definition of an existing solid Extrude feature."""

import hashlib
import math

import adsk.core
import adsk.fusion

from ..mcp_primitives.tool import Tool
from ..mcp_primitives.item import Item, Verification
from ..mcp_primitives.registry import register
from . import _assert, _common, _geom, _inputs
from ._common import counted, error, ok, safe


_FEATURE = _inputs.FeatureRef("feature", required=True)
_ACTION = _inputs.Choice("action", ("profile", "operation", "participants", "extent"), required=True)
_PROFILE = _inputs.ProfileRef("profile")
_OPERATION = _inputs.boolean_op(default=None, description="")
_BODIES = _inputs.BodyRefList("target_bodies", kind="solid")
_EXTENT = _inputs.Choice("extent", ("distance", "symmetric", "two_side", "to_face", "through_all"))
_DIRECTION = _inputs.Choice("direction", ("positive", "negative", "both"))
_FACE = _inputs.GeometryHandle("to_object", require="face")
_UNITS = _inputs.UnitField()
_SPEC = [_FEATURE, _ACTION, _PROFILE, _OPERATION, _BODIES, _EXTENT, _DIRECTION, _FACE, _UNITS]
_UNREAD = object()


def _extent_kind(feature):
    """The supported extent configuration, or None for an unread or unsupported definition."""
    one = safe(lambda: feature.extentOne.objectType)
    two = safe(lambda: feature.hasTwoExtents)
    if two is True:
        other = safe(lambda: feature.extentTwo.objectType)
        if one == other == "adsk::fusion::DistanceExtentDefinition":
            return "two_side"
        if one == other == "adsk::fusion::ThroughAllExtentDefinition":
            return "through_all"
        return None
    if two is not False:
        return None
    return {"adsk::fusion::DistanceExtentDefinition": "distance",
            "adsk::fusion::SymmetricExtentDefinition": "symmetric",
            "adsk::fusion::ToEntityExtentDefinition": "to_face",
            "adsk::fusion::ThroughAllExtentDefinition": "through_all"}.get(one)


def _members_match(actual, requested):
    """Whether a native participant list contains exactly the requested bodies."""
    if actual is None:
        return None
    return len(actual) == len(requested) and all(
        any(_common._native_of(body) == _common._native_of(want) for body in actual)
        for want in requested)


def _definition_matches(feature, action, values):
    """Read back the requested definition while the marker is at the edit position."""
    if "preserved_bodies" in values and _members_match(
            safe(lambda: list(feature.participantBodies)), values["preserved_bodies"]) is not True:
        return False
    if action == "profile":
        return safe(lambda: _common._native_of(feature.profile) == values["profile"])
    if action in ("operation", "participants"):
        matched = True
        if action == "operation":
            matched = safe(lambda: feature.operation == values["native_operation"])
        if values["target_bodies"]:
            bodies = safe(lambda: list(feature.participantBodies))
            matched = matched is True and _members_match(bodies, values["target_bodies"])
        return matched
    kind = values["extent"]
    if _extent_kind(feature) != kind:
        return False
    if kind == "to_face":
        return safe(lambda: _common._native_of(feature.extentOne.entity) == values["to_object"]
                    and feature.extentOne.isChained is False
                    and abs(feature.extentOne.offset.value) < _common.EXTENT_MATCH_TOL_CM)
    if kind == "through_all":
        return (safe(lambda: feature.hasTwoExtents) is True if values["direction"] == "both"
                else safe(lambda: feature.hasTwoExtents) is False
                and safe(lambda: feature.extentOne.isPositiveDirection)
                is (values["direction"] == "positive"))
    distances = [_common.landed_extent_cm(feature)]
    if kind == "two_side":
        distances.append(_common.landed_extent2_cm(feature))
    if kind == "symmetric" and safe(lambda: feature.symmetricExtent.isFullLength) is not False:
        return False
    return all(got is not None and abs(got - want) <= _common.EXTENT_MATCH_TOL_CM
               for got, want in zip(distances, values["depths"]))


def _prepare(action, values, raw, design, entity):
    """Validate this action's inputs and construct its nonmutating extent definitions."""
    allowed = {"profile": {"profile"}, "operation": {"operation", "target_bodies"},
               "participants": {"target_bodies"},
               "extent": {"extent", "distance", "distance2", "units", "to_object", "direction"}}
    for name in ("profile", "operation", "target_bodies", "extent", "distance", "distance2",
                 "to_object", "direction"):
        if raw[name] not in (None, "", []) and name not in allowed[action]:
            return f"'{name}'={raw[name]!r} is not used by action='{action}'. Remove it."
    scoped_operation = safe(lambda: entity.operation) in (
        adsk.fusion.FeatureOperations.CutFeatureOperation,
        adsk.fusion.FeatureOperations.IntersectFeatureOperation)
    assigns_scope = (action in ("profile", "extent", "participants") and scoped_operation
                     or action == "operation" and values["operation"] in ("cut", "intersect"))
    requested_both = (action == "extent" and values["extent"] == "through_all"
                      and values["direction"] == "both" and scoped_operation)
    if (requested_both or assigns_scope and safe(lambda: entity.hasTwoExtents) is True
            and _extent_kind(entity) == "through_all"):
        return ("Two-sided through_all with cut/intersect participant assignment is unsupported. "
                "Use separate one-sided features or the Fusion UI.")
    if action == "profile":
        return None if values["profile"] is not None else "action='profile' requires 'profile'."
    if action == "operation":
        op = values["operation"]
        if not op:
            return "action='operation' requires 'operation'."
        values["native_operation"] = getattr(adsk.fusion.FeatureOperations, _common.OPERATIONS[op])
        if op in ("cut", "intersect") and not values["target_bodies"]:
            return f"operation='{op}' requires explicit 'target_bodies'."
        if op in ("new", "join") and values["target_bodies"]:
            return f"operation='{op}' does not take 'target_bodies'."
    if action == "participants":
        if not values["target_bodies"]:
            return "action='participants' requires nonempty 'target_bodies'."
        if safe(lambda: entity.operation) not in (
                adsk.fusion.FeatureOperations.CutFeatureOperation,
                adsk.fusion.FeatureOperations.IntersectFeatureOperation):
            return "action='participants' requires an existing cut/intersect Extrude."
    if action != "extent":
        return None
    kind = values["extent"]
    if not kind:
        return "action='extent' requires 'extent'."
    if safe(lambda: entity.startExtent.objectType) != "adsk::fusion::ProfilePlaneStartDefinition":
        return "Extent replacement requires a profile-plane start; edit this start in Fusion."
    tapers = [safe(lambda: entity.taperAngleOne.value)]
    if safe(lambda: entity.hasTwoExtents) is True:
        tapers.append(safe(lambda: entity.taperAngleTwo.value))
    if any(taper is None or abs(taper) > 1e-12 for taper in tapers):
        return "Extent replacement requires zero readable taper angles; inspect param_get."
    used = {"distance": {"distance", "units"}, "symmetric": {"distance", "units"},
            "two_side": {"distance", "distance2", "units"}, "to_face": {"to_object"},
            "through_all": {"direction"}}[kind]
    for name in ("distance", "distance2", "to_object", "direction"):
        if raw[name] not in (None, "", []) and name not in used:
            return f"'{name}'={raw[name]!r} is not used by extent='{kind}'. Remove it."
    if kind == "through_all" and values["direction"] is None:
        return "extent='through_all' requires 'direction'."
    if kind == "to_face" and values["to_object"] is None:
        return "extent='to_face' requires 'to_object'."
    depths, inputs = [], []
    for name in (["distance", "distance2"] if kind == "two_side" else
                 ["distance"] if kind in ("distance", "symmetric") else []):
        scale = _common.scale(raw["units"] or "mm")
        if scale is None:
            return f"Unknown units '{raw['units']}'; use mm, cm or in."
        val, cm, why = _inputs.length_value_input(raw[name], scale, design, name)
        if why:
            return why
        if cm is None or not math.isfinite(cm) or cm <= 0:
            return f"'{name}'={raw[name]!r} must evaluate to a positive length."
        depths.append(cm)
        inputs.append(val)
    values["depths"], values["length_inputs"] = depths, inputs
    return None


def _apply_edit(feature, action, values):
    """Apply one semantic definition change; exceptions retain any native partial change."""
    if action == "profile":
        feature.profile = values["profile"]
    elif action in ("operation", "participants"):
        if action == "operation":
            feature.operation = values["native_operation"]
        if values["target_bodies"]:
            feature.participantBodies = list(values["target_bodies"])
    else:
        kind = values["extent"]
        zero = adsk.core.ValueInput.createByString("0 deg")
        lengths = values["length_inputs"]
        distance = adsk.fusion.DistanceExtentDefinition.create
        through = adsk.fusion.ThroughAllExtentDefinition.create
        positive = adsk.fusion.ExtentDirections.PositiveExtentDirection
        if kind == "symmetric":
            applied = feature.setSymmetricExtent(lengths[0], False, zero)
        elif kind == "two_side":
            applied = feature.setTwoSidesExtent(distance(lengths[0]), distance(lengths[1]), zero, zero)
        elif kind == "through_all" and values["direction"] == "both":
            applied = feature.setTwoSidesExtent(through(), through(), zero, zero)
        else:
            extent = (distance(lengths[0]) if kind == "distance" else through()
                      if kind == "through_all" else
                      adsk.fusion.ToEntityExtentDefinition.create(values["to_object"], False))
            direction = positive
            if kind == "through_all" and values["direction"] == "negative":
                extent.isPositiveDirection = False
                direction = adsk.fusion.ExtentDirections.NegativeExtentDirection
            applied = feature.setOneSideExtent(extent, direction, zero)
        if applied is not True:
            raise RuntimeError(f"The '{kind}' extent setter returned false.")
    if "preserved_bodies" in values:
        feature.participantBodies = list(values["preserved_bodies"])


def _geometry(component):
    """The component's solid-body volume, area, bounds and face signature, or None."""
    bodies = safe(lambda: component.bRepBodies)
    count = counted(lambda: bodies.count)
    if count is None:
        return None
    rows = []
    for i in range(count):
        body = safe(lambda: bodies.item(i))
        solid = safe(lambda: body.isSolid)
        if solid is None:
            return None
        if not solid:
            continue
        volume = _geom.signed_volume(body)
        area = _geom.areas([body]).get(id(body))
        bounds = _geom._aabb_extents(body)
        if volume is None or not isinstance(area, (int, float)) or bounds is None:
            return None
        faces = safe(lambda: body.faces)
        face_count = counted(lambda: faces.count)
        if not face_count:
            return None
        samples = []
        for j in range(face_count):
            face = safe(lambda: faces.item(j))
            face_area = safe(lambda: face.area)
            centroid = _geom._coords(safe(lambda: face.centroid))
            if (not isinstance(face_area, (int, float)) or isinstance(face_area, bool)
                    or centroid is None or not all(math.isfinite(v) for v in (face_area, *centroid))):
                return None
            samples.append((round(float(face_area), 9) or 0.0,
                            *[round(float(v), 7) or 0.0 for v in centroid]))
        # PhysicalProperties can retain collateral-cut mass after native faces are restored.
        signature = hashlib.sha256(repr(sorted(samples)).encode("ascii")).hexdigest()
        rows.append([round(volume, 9), round(area, 9),
                     *[round(v, 7) for pair in bounds for v in pair],
                     face_count, signature])
    return sorted(rows)


def _health(design):
    """The evaluated timeline error/warning census, or None when a row's health is unreadable."""
    timeline = safe(lambda: design.timeline)
    count = counted(lambda: timeline.markerPosition)
    states = adsk.fusion.FeatureHealthStates
    evaluated = (states.HealthyFeatureHealthState, states.WarningFeatureHealthState,
                 states.ErrorFeatureHealthState)
    if count is None or any(safe(lambda i=i: timeline.item(i).healthState) not in evaluated
                            for i in range(count)):
        return None
    result = safe(lambda: _common.timeline_health(design, limit=count))
    return None if result is None else {"errors": result[0], "warnings": result[1]}


def _profile_source(feature, component):
    """The native profile and one verified owning sketch, or a refusal."""
    profile = _common._native_of(safe(lambda: feature.profile))
    if isinstance(profile, adsk.fusion.Profile):
        sketch = _common._native_of(safe(lambda: profile.parentSketch))
        if _common.same_component(component, safe(lambda: sketch.parentComponent)) is not True:
            return profile, sketch, False, ("The feature does not own its profile; address the "
                                           "original Extrude, not its linked alias.")
        return profile, sketch, False, None
    if safe(lambda: profile.objectType) != "adsk::core::ObjectCollection":
        return profile, None, False, "The feature's profile is unreadable; inspect its definition."
    size = counted(lambda: profile.count)
    if size is None or size <= 0:
        return profile, None, True, ("The feature's profile collection is empty or unreadable; "
                                     "inspect its definition.")
    sketch, identity = None, None
    for i in range(size):
        member = _common._native_of(safe(lambda i=i: profile.item(i)))
        if not isinstance(member, adsk.fusion.Profile):
            return profile, None, True, ("The feature's profile collection has an unreadable or "
                                         "non-profile member; inspect its definition.")
        owner_sketch = _common._native_of(safe(lambda: member.parentSketch))
        owner_identity = _common.native_identity(owner_sketch)
        if owner_identity is None:
            return profile, None, True, ("The feature's profile collection has an unreadable "
                                         "sketch identity; inspect its definition.")
        same_owner = _common.same_component(component, safe(lambda: owner_sketch.parentComponent))
        if same_owner is None:
            return profile, None, True, ("The feature's profile collection has an unreadable "
                                         "component owner; inspect its definition.")
        if same_owner is False:
            return profile, None, True, ("The feature's profile collection includes a profile "
                                         "outside its owning component; inspect the source Extrude.")
        if identity is not None and owner_identity != identity:
            return profile, None, True, ("The feature's profile collection spans sketches; "
                                         "inspect the source Extrude.")
        sketch, identity = owner_sketch, owner_identity
    return profile, sketch, True, None


def _definition(feature):
    """The definition fields readable at the feature's edit position."""
    _, sketch, _, _ = _profile_source(feature, safe(lambda: feature.parentComponent))
    return {"profile_sketch": safe(lambda: sketch.name),
            "operation": next((name for name, enum in _common.OPERATIONS.items()
                               if safe(lambda: feature.operation) ==
                               getattr(adsk.fusion.FeatureOperations, enum)), None),
            "extent": _extent_kind(feature),
            "participants": safe(lambda: [b.name for b in feature.participantBodies])}


def _same_feature(design, token, feature, index, count):
    """Whether the original feature resolves at its original index with unchanged timeline count."""
    found = safe(lambda: design.findEntityByToken(token))
    if found is None:
        return None
    same = safe(lambda: any(entity == feature for entity in found))
    return (same is True and safe(lambda: feature.isValid) is True
            and counted(lambda: feature.timelineObject.index) == index
            and counted(lambda: design.timeline.count) == count)


def _target_error(feature, label):
    """Why this feature is outside the supported solid Extrude edit scope."""
    if safe(lambda: feature.objectType) != adsk.fusion.ExtrudeFeature.classType():
        return f"'{label}' is not an Extrude feature. Use design_get(include=['timeline'])."
    flags = (("isParametric", True), ("isSolid", True),
             ("isSuppressed", False), ("isThinExtrude", False))
    for prop, wanted in flags:
        got = safe(lambda prop=prop: getattr(feature, prop))
        if got is not wanted:
            return f"'{label}' has {prop}={got}; this edit requires {prop}={wanted}."
    if safe(lambda: feature.baseFeature, _UNREAD) is not None:
        return f"'{label}' is not a verified standalone parametric feature. Inspect design_get."
    links = counted(lambda: feature.linkedFeatures.count)
    if links is None or links > 1:
        return f"'{label}' has unreadable or multiple linked features; only one linked alias is supported."
    return None


def _linked_scope_error(feature, component, components, index):
    """Refuse foreign-profile aliases and unverified linked-feature structures while rolled."""
    profile, _, collection, refusal = _profile_source(feature, component)
    if refusal:
        return refusal
    links = safe(lambda: list(feature.linkedFeatures))
    if links is None or len(links) > 1:
        return "Linked features are unreadable or exceed the supported one-alias scope."
    if collection and links:
        return "Linked profile collections are unverified; inspect the source Extrude."
    for linked in links:
        owner = safe(lambda: linked.parentComponent)
        reciprocal = safe(lambda: list(linked.linkedFeatures))
        participants = safe(lambda: list(feature.participantBodies))
        if (safe(lambda: linked.objectType) != adsk.fusion.ExtrudeFeature.classType()
                or safe(lambda: linked.assemblyContext, _UNREAD) is not None
                or _common.same_component(component, owner) is not False
                or not any(_common.same_component(owner, c) is True for c in components)
                or counted(lambda: linked.timelineObject.index) != index
                or safe(lambda: _common._native_of(linked.profile) == profile) is not True
                or counted(lambda: linked.bodies.count) != 0
                or reciprocal is None or len(reciprocal) != 1 or reciprocal[0] != feature
                or participants is None
                or _members_match(safe(lambda: list(linked.participantBodies)), participants) is not True):
            return "The linked feature is not a verified native alias of this Extrude."
    return None


def handler(feature: str = "", action: str = "", profile=None, operation: str = "",
            target_bodies=None, extent: str = "", distance=None, distance2=None,
            units: str = "mm", to_object: str = "", direction: str = "") -> dict:
    """Edit one Extrude definition and verify its native and geometric effect."""
    raw = dict(locals())
    values, refusal = _inputs.resolve_inputs(_SPEC, raw)
    if refusal:
        return refusal
    entity, label = values["feature"]
    profile_entity = values["profile"]
    action = values["action"]
    refusal = _target_error(entity, label)
    if refusal:
        return error(refusal)
    design = _common.design()
    refusal = _prepare(action, values, raw, design, entity)
    if refusal:
        return error(refusal)
    timeline = safe(lambda: design.timeline)
    marker = counted(lambda: timeline.markerPosition)
    count = counted(lambda: timeline.count)
    index = counted(lambda: entity.timelineObject.index)
    token = safe(lambda: entity.entityToken)
    if marker is None or count is None or index is None or not token:
        return error(f"'{label}' has unreadable timeline identity; nothing was edited.")
    if marker <= index:
        return error(f"'{label}' is after marker {marker}; roll after it with design_edit_timeline.")
    component = safe(lambda: entity.parentComponent)
    values["target_bodies"] = [_common._native_of(body) for body in values["target_bodies"]]
    for key in ("profile", "to_object"):
        if values[key] is not None:
            values[key] = _common._native_of(values[key])
    profile_entity = values["profile"]
    operands = list(values["target_bodies"])
    if profile_entity is not None:
        sketch = safe(lambda: profile_entity.parentSketch)
        if _common.same_component(component, safe(lambda: sketch.parentComponent)) is not True:
            return error(f"profile '{profile}' must belong to '{label}'s owning component.")
        profile_index = counted(lambda: sketch.timelineObject.index)
        if profile_index is None or profile_index >= index:
            return error(f"profile '{profile}' must precede '{label}' in the timeline.")
        operands.append(profile_entity)
    if values["to_object"] is not None:
        operands.append(values["to_object"])
    for operand in operands:
        owner = (safe(lambda: operand.parentComponent)
                 or safe(lambda: operand.parentSketch.parentComponent)
                 or safe(lambda: operand.body.parentComponent))
        if _common.same_component(component, owner) is not True:
            return error(f"An operand does not belong to '{label}'s owning component.")
        if safe(lambda: operand.assemblyContext, _UNREAD) is not None:
            return error(f"An operand for '{label}' is not native to its owning component.")
    if any(a == b for i, a in enumerate(values["target_bodies"])
           for b in values["target_bodies"][i + 1:]):
        return error("'target_bodies' repeats one body; list each participant once.")
    before = _geometry(component)
    if before is None:
        return error(f"'{label}'s body geometry could not be read; nothing was edited.")
    components = safe(lambda: list(design.allComponents))
    if not components or not any(_common.same_component(component, c) is True for c in components):
        return error("The design's component census could not be read; nothing was edited.")
    siblings = [(c, _geometry(c)) for c in components
                if _common.same_component(component, c) is not True]
    if any(geometry is None for c, geometry in siblings):
        return error("Other component geometry could not be read; nothing was edited.")
    health_before = _health(design)
    if action == "profile" and safe(lambda: entity.profile == profile_entity) is True:
        return error(f"'{label}' already uses profile '{profile}'; nothing was edited.")
    failure, restore_failure, attempted = None, None, False
    definition_matches = None
    replayed, linked_verified, linked_owners = False, None, None
    verified_links = None
    definition_before, definition_after = None, None
    try:
        if entity.timelineObject.rollTo(True) is not True:
            failure = "Fusion refused rollTo(True)."
        elif counted(lambda: timeline.markerPosition) != index:
            failure = "The marker did not reach the feature's edit position."
        elif any(safe(lambda operand=operand: operand.isValid) is not True for operand in operands):
            failure = "An operand is invalid at the edit position; use preceding geometry."
        else:
            definition_before = _definition(entity)
            linked_error = _linked_scope_error(entity, component, components, index)
            if linked_error:
                raise ValueError(linked_error)
            if (counted(lambda: entity.linkedFeatures.count)
                    and action == "operation" and values["operation"] in ("new", "join")):
                raise ValueError("A linked Extrude supports only scoped cut/intersect operation edits.")
            if action in ("profile", "extent") and entity.operation in (
                    adsk.fusion.FeatureOperations.CutFeatureOperation,
                    adsk.fusion.FeatureOperations.IntersectFeatureOperation):
                prior = [_common._native_of(body) for body in entity.participantBodies]
                if not prior or any(_common.same_component(component, body.parentComponent)
                                    is not True for body in prior):
                    raise ValueError("Existing participants are not confined to the owning component.")
                values["preserved_bodies"] = prior
            attempted = True
            _apply_edit(entity, action, values)
            scoped = values.get("preserved_bodies") or values["target_bodies"]
            if scoped:
                # Evaluation can cut a sibling despite the first participant assignment.
                # Replaying the same scope after evaluation removes that collateral material change.
                timeline.markerPosition = index + 1
                if counted(lambda: timeline.markerPosition) != index + 1:
                    raise RuntimeError("The feature could not be evaluated before participant replay.")
                if (entity.timelineObject.rollTo(True) is not True
                        or counted(lambda: timeline.markerPosition) != index):
                    raise RuntimeError("The feature could not be rolled back for participant replay.")
                entity.participantBodies = list(scoped)
                replayed = True
            definition_matches = _definition_matches(entity, action, values)
            definition_after = _definition(entity)
            linked_error = _linked_scope_error(entity, component, components, index)
            linked_verified = linked_error is None
            verified_links = safe(lambda: list(entity.linkedFeatures))
            linked_owners = safe(lambda: [f.parentComponent.name for f in entity.linkedFeatures])
            if linked_error:
                raise ValueError(linked_error)
    except Exception as exc:
        failure = str(exc)
        definition_matches = safe(lambda: _definition_matches(entity, action, values))
        definition_after = _definition(entity)
    finally:
        try:
            timeline.markerPosition = marker
        except Exception as exc:
            restore_failure = str(exc)
    restored = counted(lambda: timeline.markerPosition) == marker
    after = _geometry(component) if restored else None
    final_links = safe(lambda: list(entity.linkedFeatures)) if restored else None
    links_stable = (None if final_links is None or verified_links is None else
                    len(final_links) == len(verified_links)
                    and all(any(final == checked for final in final_links)
                            for checked in verified_links))
    final_components = safe(lambda: list(design.allComponents)) if restored else None
    scope_verified, sibling_changes = None, []
    if (final_components is not None and len(final_components) == len(components)
            and all(sum(_common.same_component(c, other) is True for other in final_components) == 1
                    for c in components)):
        scope_verified = True
        for sibling, prior_geometry in siblings:
            final_geometry = _geometry(sibling)
            if final_geometry is None:
                scope_verified = None
            elif final_geometry != prior_geometry:
                sibling_changes.append({"component": safe(lambda: sibling.name),
                                        "before": prior_geometry, "after": final_geometry})
        if sibling_changes:
            scope_verified = False
    same = _same_feature(design, token, entity, index, count)
    state, compute_failure = _assert.compute_state(entity)
    health_after = _health(design)
    new_errors = (None if health_before is None or health_after is None else
                  [n for n in health_after["errors"] if n not in health_before["errors"]])
    new_warnings = (None if health_before is None or health_after is None else
                    [n for n in health_after["warnings"] if n not in health_before["warnings"]])
    changed = None if after is None else before != after
    out = {"feature": label, "action": action, "definition_matches": definition_matches,
           "geometry_changed": changed, "same_feature": same, "marker_restored": restored,
           "marker_before": marker, "marker_after": counted(lambda: timeline.markerPosition),
           "feature_health": state, "new_timeline_errors": new_errors,
           "new_timeline_warnings": new_warnings, "mutation_attempted": attempted,
           "unevaluated_timeline_items": count - marker,
           "definition_before": definition_before, "definition_after": definition_after,
           "geometry_before": before, "geometry_after": after,
           "other_components_unchanged": scope_verified, "other_component_changes": sibling_changes,
           "participants_reapplied_after_evaluation": replayed,
           "linked_scope_verified_at_edit": linked_verified, "linked_component_aliases": linked_owners,
           "linked_aliases_stable_after_evaluation": links_stable,
           "geometry_frame": "owning_component", "geometry_units": "cm, cm2, cm3"}
    if (failure or restore_failure or not restored or same is not True
            or definition_matches is not True or changed is not True or state != "healthy"
            or scope_verified is not True or linked_verified is not True or links_stable is not True
            or new_errors is None or new_errors or new_warnings):
        downstream = ("The definition landed but introduced downstream errors or warnings."
                      if definition_matches is True and (new_errors or new_warnings) else None)
        reason = failure or restore_failure or downstream or (str(compute_failure) if compute_failure else
                 "Definition, component scope, geometry, identity, marker or health verification failed.")
        result = error(f"Editing '{label}': {reason} The feature was not deleted; inspect "
                       "design_get(include=['timeline']). Observed edit state is in 'details'.")
        result["details"] = out
        result["content"].extend(ok({"details": out})["content"])
        return result
    out["edited"] = True
    out["note"] = ("Definition changed on the same Extrude. Use param_get/param_set for numeric edits."
                   + (" Later timeline items remain unevaluated at the restored marker."
                      if marker < count else "")
                   + (" Linked replay may leave mass properties stale. Use design_recompute before "
                      "mass inspection; it can reset uncaptured joint poses."
                      if replayed and linked_owners else ""))
    return ok(out)


TOOL_DESCRIPTION = (
    "Edit solid Extrude; refs from design_get/sketch_get."
)
tool = _inputs.apply_to_tool(
    Tool.create_simple(name="model_edit_extrude", description=TOOL_DESCRIPTION), _SPEC
)
tool.add_input_property("distance", {"type": ["number", "string"],
                                    "description": "Positive; symmetric per side."})
tool.add_input_property("distance2", {"type": ["number", "string"]})
tool.strict_schema()
item = Item.create_tool_item(
    tool=tool, write="write", handler=handler, run_on_main_thread=True,
    verification=Verification(kind="inline", rung="geometry",
                              evidence_test="tests/unit/test_model_edit_extrude.py"
                                            "::test_silent_profile_setter_is_an_error"))


def register_tool():
    register(item)
