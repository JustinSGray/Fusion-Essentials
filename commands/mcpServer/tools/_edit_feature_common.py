# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Shared evaluated-body and timeline evidence for reference feature edits."""

import adsk.fusion
import math
from itertools import islice

from . import _common, _geom, _sketch_detail
from ._common import counted, safe

MAP_BLURB = (
    "read_extrude_definition/read_sweep_definition/feature_definition - current reads; "
    "all_shapes/feature_body_keys/health/same_feature - edit evidence; "
    "operand_source/later_operand_refusal - dependency checks; "
    "sketch_address/at_address/address_text - operands; "
    "restore_definition/restore_gaps/matched/shape_match - rollback; "
    "rolled_back_text/failed/identical_geometry_reply - outcomes")


def _definition_value(getter, key, unavailable):
    """Read one field, recording the native failure separately from an absent value."""
    try:
        return getter()
    except Exception as exc:
        unavailable[key] = str(exc).split(" / ")[0].strip()[:200]
        return None


def _definition_participants(feature, unavailable, limit=None):
    """Participant names and truncation, or unknown when the current marker prevents the read."""
    def names():
        bodies = feature.participantBodies
        return [body.name for body in (islice(bodies, limit + 1) if limit is not None else bodies)]
    result = _definition_value(names, "participants", unavailable)
    return (result[:limit] if result is not None and limit is not None else result,
            len(result) > limit if result is not None and limit is not None else False)


def extrude_extent_kind(feature):
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


def read_extrude_definition(feature, limit=None):
    """Read Extrude values at the current marker, with signed lengths in cm and per-field failures."""
    unavailable = {}
    get = lambda key, getter: _definition_value(getter, key, unavailable)
    kind = extrude_extent_kind(feature)
    param = (get("distance", lambda: feature.extentOne.distance)
             if kind in ("distance", "symmetric", "two_side") else None)
    param2 = get("distance2", lambda: feature.extentTwo.distance) if kind == "two_side" else None
    participants, truncated = _definition_participants(feature, unavailable, limit)
    return {"profile": get("profile", lambda: feature.profile),
            "operation": next((name for name, enum in _common.OPERATIONS.items()
                               if safe(lambda: feature.operation) ==
                               getattr(adsk.fusion.FeatureOperations, enum)), None),
            "extent": kind,
            "distance_cm": _common.landed_extent_cm(feature) if param is not None else None,
            "distance2_cm": _common.landed_extent2_cm(feature) if kind == "two_side" else None,
            "distance_parameter": safe(lambda: param.name),
            "distance_expression": safe(lambda: param.expression),
            "distance2_parameter": safe(lambda: param2.name),
            "distance2_expression": safe(lambda: param2.expression),
            "symmetric_full_length": (_common.read_flag(lambda: feature.extentOne.isFullLength)
                                      if kind == "symmetric" else None),
            "participants": participants, "participants_truncated": truncated,
            "unavailable": unavailable}


def read_sweep_definition(feature):
    """Read each Sweep operand/control independently at the caller's current marker."""
    unavailable = {}
    read = {key: _definition_value(lambda name=name: getattr(feature, name), key, unavailable)
            for key, name in (("profile", "profile"), ("path", "path"), ("operation", "operation"),
                              ("orientation", "orientation"), ("is_solid", "isSolid"))}
    return {**read, "unavailable": unavailable}


def _definition_profile(entity):
    """A reusable single profile reference; bounded index search leaves larger sketches handle-only."""
    native = _common._native_of(entity)
    if native is None:
        return None
    sketch = safe(lambda: native.parentSketch)
    count = counted(lambda: sketch.profiles.count)
    curve_count = counted(lambda: sketch.sketchCurves.count)
    is_profile = safe(lambda: native.objectType) == "adsk::fusion::Profile"
    bounded = count is not None and count <= 64 and (is_profile or curve_count is not None and curve_count <= 64)
    address = sketch_address(native) if bounded else None
    return {"type": safe(lambda: native.objectType.rsplit("::", 1)[-1]),
            "profile_handle": (safe(lambda: native.entityToken)
                               if safe(lambda: native.objectType) == "adsk::fusion::Profile" else None),
            "source_sketch": safe(lambda: sketch.name),
            "source_component": safe(lambda: sketch.parentComponent.name),
            "profile_index": address[2] if address and address[1] == "profile" else None,
            "curve_ref": (f"{safe(lambda: sketch.name)}/{address[1]}:{address[2]}"
                          if address and address[1] != "profile" else None)}


def feature_definition(feature, factor):
    """Format an Extrude or Sweep definition without rolling, scaling only dimensional lengths."""
    if safe(lambda: feature.objectType) == "adsk::fusion::ExtrudeFeature":
        read = read_extrude_definition(feature, limit=64)
        kind = read["extent"]
        applicable = None if kind is None else kind in ("distance", "two_side", "symmetric")
        out = {key: read[key] for key in ("operation", "extent", "distance_parameter", "distance_expression",
            "distance2_parameter", "distance2_expression", "symmetric_full_length", "participants",
            "participants_truncated", "unavailable")}
        out.update(distance=_common.measured(lambda: read["distance_cm"], factor),
                   distance2=_common.measured(lambda: read["distance2_cm"], factor),
                   distance_applicable=applicable,
                   distance2_applicable=None if kind is None else kind == "two_side")
    else:
        read = read_sweep_definition(feature)
        unavailable = dict(read["unavailable"])
        participants, truncated = _definition_participants(feature, unavailable, 64)
        path = read["path"]
        count = counted(lambda: path.count)
        out = {"operation": next((name for name, enum in _common.OPERATIONS.items()
                                  if read["operation"] == getattr(adsk.fusion.FeatureOperations, enum)), None),
               "orientation": read["orientation"], "is_solid": read["is_solid"],
               "path": ([_definition_profile(safe(lambda i=i: path.item(i).entity))
                         for i in range(min(count, 64))] if count is not None else None),
               "path_count": count, "path_truncated": count is not None and count > 64,
               "participants": participants, "participants_truncated": truncated,
               "unavailable": unavailable}
    out["profile"] = _definition_profile(read["profile"])
    return out


def _empty_solid_shape(body):
    """Measured zero-geometry solid, or None when any required read is unavailable."""
    valid, solid = safe(lambda: body.isValid), safe(lambda: body.isSolid)
    area, volume = safe(lambda: body.area), _geom.signed_volume(body)
    faces = counted(lambda: body.faces.count)
    edges = counted(lambda: body.edges.count)
    lumps = counted(lambda: body.lumps.count)
    numbers = (area, volume)
    if (valid is not True or solid is not True
            or (faces, edges, lumps) != (0, 0, 0)
            or any(not isinstance(value, (int, float)) or isinstance(value, bool)
                   or not math.isfinite(value) or value != 0 for value in numbers)):
        return None
    return {"empty": True, "solid": True, "area_cm2": 0.0, "volume_cm3": 0.0,
            "face_count": faces, "edge_count": edges, "lump_count": lumps}


def all_shapes(design, allow_empty_solids=False):
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
            if shape is None and allow_empty_solids:
                shape = _empty_solid_shape(body)
            if key is None or shape is None or key in rows:
                return None
            rows[key] = {"component": safe(lambda c=component: c.name),
                         "body": safe(lambda b=body: b.name), "shape": shape}
    return rows


def feature_body_keys(feature):
    """Native identities of result bodies, or None on an unreadable collection."""
    bodies = safe(lambda: feature.bodies)
    count = counted(lambda: bodies.count)
    if count is None:
        return None
    keys = {_common.native_identity(safe(lambda i=i: bodies.item(i))) for i in range(count)}
    return None if None in keys else keys


def health(design, marker):
    """Evaluated timeline errors and warnings, or None when a state cannot be read."""
    timeline = safe(lambda: design.timeline)
    states = adsk.fusion.FeatureHealthStates
    known = (states.HealthyFeatureHealthState, states.WarningFeatureHealthState,
             states.ErrorFeatureHealthState)
    if any(safe(lambda i=i: timeline.item(i).healthState) not in known for i in range(marker)):
        return None
    errors, warnings, total = _common.timeline_health(design, limit=marker)
    return {"errors": errors, "warnings": warnings} if total == marker else None


def same_feature(design, token, feature, index, count):
    """Whether the saved feature still occupies its original timeline row."""
    found = safe(lambda: design.findEntityByToken(token))
    if found is None:
        return None
    same = safe(lambda: any(entity == feature for entity in found))
    return (same is True and safe(lambda: feature.isValid) is True
            and counted(lambda: feature.timelineObject.index) == index
            and counted(lambda: design.timeline.count) == count)


def operand_source(entity):
    """(source sketch/body/entity, its timeline row or None, whether that source is a sketch)."""
    native = _common._native_of(entity)
    sketch = safe(lambda: native.parentSketch)
    source = sketch if sketch is not None else (safe(lambda: native.body) or native)
    return source, counted(lambda: source.timelineObject.index), sketch is not None


def later_operand_refusal(label, index, operands):
    """The refusal for the first operand drawn in a sketch at or after row `index`, else None."""
    for entity in operands:
        source, row, from_sketch = operand_source(entity)
        if not from_sketch or row is None or row < index:
            continue
        name = safe(lambda: source.name)
        return (f"Editing '{label}': sketch '{name}' is at timeline row {row}, after '{label}' at "
                f"row {index}. Move it first with design_edit_timeline(action='reorder', "
                f"feature='{name}@{row}', to='before', end_feature='{label}@{index}'), then retry. "
                "Nothing was edited.")
    return None


def sketch_address(entity):
    """(sketch, 'profile' or a curve kind, index) naming a native profile or curve, or None."""
    native = _common._native_of(entity)
    sketch = safe(lambda: native.parentSketch)
    if sketch is None:
        return None
    # The two pieces a split returns share one entityToken, so both kinds match by identity.
    profiles = safe(lambda: sketch.profiles)
    hits = [i for i in range(counted(lambda: profiles.count) or 0)
            if safe(lambda i=i: profiles.item(i) == native) is True]
    if hits:
        return (sketch, "profile", hits[0]) if len(hits) == 1 else None
    kind, _, index = (_sketch_detail.curve_id(sketch, native) or "").rpartition(":")
    return (sketch, kind, int(index)) if kind else None


def at_address(address):
    """The profile or sketch curve a sketch_address names now, or None."""
    sketch, kind, index = address
    if kind != "profile":
        return _common.resolve_entity_ref(sketch, f"{kind}:{index}")
    profiles = safe(lambda: sketch.profiles)
    return safe(lambda: profiles.item(index)) if index < (counted(lambda: profiles.count) or 0) else None


def address_text(address):
    """A sketch_address as an outcome sentence names it: a profile, or '<sketch>/<kind>:<i>'."""
    if address is None:
        return None
    sketch, kind, index = address
    name = safe(lambda: sketch.name)
    return f"sketch '{name}' profile {index}" if kind == "profile" else f"{name}/{kind}:{index}"


def restore_definition(design, entity, restore, read_definition, evaluate_at, snapshot, park):
    """Run `restore` at `entity`'s row, re-read it there, `snapshot` at `evaluate_at`, park at `park`."""
    timeline = safe(lambda: design.timeline)
    errors, ran = [], []

    def step():
        index = counted(lambda: entity.timelineObject.index)
        if index is None or counted(lambda: timeline.markerPosition) != index:
            raise RuntimeError("the marker did not reach the feature's edit position")
        ran.append(True)
        try:
            restore()
        except Exception as exc:
            errors.append(f"the restore raised: {exc}")
        definition = read_definition(entity)
        timeline.markerPosition = evaluate_at
        if counted(lambda: timeline.markerPosition) != evaluate_at:
            raise RuntimeError("the restored feature could not be evaluated")
        return definition, snapshot()

    try:
        got, _clause = _common.rolled_to(design, entity, step, "the restore", park=park)
    except Exception as exc:
        got = None
        errors.append(str(exc))
    if got is None and not errors:
        errors.append("the feature could not be rolled to its edit position")
    definition, shapes = got if got is not None else (None, None)
    return {"ran": bool(ran), "error": "; ".join(errors) or None, "definition": definition,
            "shapes": shapes, "marker_after": counted(lambda: timeline.markerPosition)}


_GAPS = {"definition": ("the definition re-read differs from before the edit",
                        "the definition was not re-read"),
         "scope": ("the participant scope differs from before the edit",
                   "the participant scope was not re-read"),
         "shapes": ("the bodies do not match the pre-edit read", "the bodies were not re-read"),
         "health": ("the timeline health does not match before the edit",
                    "the timeline health was not re-read"),
         "row": ("the feature did not re-read at its row", "the feature's row was not re-read")}


def restore_gaps(error, **held):
    """Why a restore's re-read does not prove the pre-edit state: False differs, None was unread."""
    return ([error] if error else []) + [_GAPS[name][good is None] for name, good in held.items()
                                         if good is not True]


def matched(got, want):
    """None when either side was not read, else whether they are equal."""
    return None if got is None or want is None else got == want


def _by_component(shapes):
    """An all_shapes snapshot as {component: [(identity, body name, shape repr)]}."""
    grouped = {}
    for key, row in shapes.items():
        grouped.setdefault(row["component"], []).append((key, row["body"], repr(row["shape"])))
    return grouped


def shape_match(after, before):
    """(whether each component's body shapes match, re-created bodies), (None, []) when unread."""
    if after is None or before is None:
        return None, []
    now, was = _by_component(after), _by_component(before)
    profile = lambda side: {c: sorted(row[2] for row in rows) for c, rows in side.items()}
    recreated = []
    for component in sorted(set(now) & set(was), key=str):
        kept = {row[:2] for row in now[component]} & {row[:2] for row in was[component]}
        gone = [row for row in was[component] if row[:2] not in kept]
        new = [row for row in now[component] if row[:2] not in kept]
        for shape in sorted({row[2] for row in gone}):
            now_names = sorted((row[1] for row in new if row[2] == shape), key=str)
            if now_names:
                was_names = sorted((row[1] for row in gone if row[2] == shape), key=str)
                recreated.append({"component": component, "now": now_names, "was": was_names})
    return profile(now) == profile(was), recreated


def rolled_back_text(rows, recreated):
    """The verified-restore sentence over (field, now, was), naming any body shape_match re-created."""
    if not recreated:
        return _common.outcome_clause("rolled_back", "", rows,
                                      evidence="the bodies match the pre-edit read")
    quoted = lambda names: ", ".join(f"'{name}'" for name in names)
    many = len(recreated) > 1 or len(recreated[0]["now"]) > 1
    return (_common.outcome_clause("rolled_back", "", rows,
                                   evidence="the body shapes match the pre-edit read")
            + f" The {'bodies now read' if many else 'body now reads'} as "
            + ", ".join(f"{quoted(r['now'])} (was {quoted(r['was'])})" for r in recreated)
            + f"; re-read names and handles held for {'them' if many else 'it'}.")


def sentence(text):
    """`text` as a sentence ending in a full stop, for a raised message quoted as a reason."""
    text = str(text).strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def failed(text, details):
    """An error result carrying the observed edit state in 'details'."""
    result = _common.error(text)
    result["details"] = details
    result["content"].extend(_common.ok({"details": details})["content"])
    return result


def identical_geometry_reply(details):
    """Success for a definition that landed and re-read clean while its bodies read identical."""
    details["edited"] = True
    details["note"] += " The body geometry reads identical before and after."
    return _common.ok(details)
