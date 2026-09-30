# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Shared evaluated-body and timeline evidence for reference feature edits."""

import adsk.fusion
import math

from . import _common, _geom, _sketch_detail
from ._common import counted, safe

MAP_BLURB = (
    "the definition-edit substrate: all_shapes/feature_body_keys/health/same_feature - the evidence "
    "an edit is judged by; sketch_address/at_address/address_text - a prior operand re-resolved from "
    "its sketch; restore_definition/restore_gaps/matched/shape_match/rolled_back_text - the reverse, "
    "its re-read and any body it re-created; failed/identical_geometry_reply - the replies")


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
