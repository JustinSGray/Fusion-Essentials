# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Shared evaluated-body and timeline evidence for reference feature edits."""

import adsk.fusion
import math

from . import _common, _geom
from ._common import counted, safe


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
    return (any(entity == feature for entity in found)
            and safe(lambda: feature.isValid) is True
            and counted(lambda: feature.timelineObject.index) == index
            and counted(lambda: design.timeline.count) == count)
