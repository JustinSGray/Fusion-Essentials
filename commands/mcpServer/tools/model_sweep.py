# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Sweep a profile or solid tool body along a path."""

import adsk.core
import adsk.fusion

from ..mcp_primitives.tool import Tool
from ..mcp_primitives.item import Item, Verification
from ..mcp_primitives.registry import register
from ._common import error, ok, safe, target_component, root_body_advisory, build_path
from . import _common
from . import _geom
from . import _inputs
from . import _outputs
from . import _sketch_detail
from . import _sweep_common
from . import _surface_common

app = adsk.core.Application.get()

# scope_input: the {sketch, profile_index} form addresses a sketch BY NAME, and Fusion numbers
# sketches per component from 1, so a name two components carry is refused, naming 'component'.
_TARGET_BODIES = _inputs.BodyRefList("target_bodies", required=False)
_SOLID_BODY = _inputs.BodyRef("solid_body", kind="solid")

# orientation keyword -> adsk.fusion.SweepOrientationTypes attribute.
_ORIENTATIONS = {
    "perpendicular": "PerpendicularOrientationType",
    "parallel": "ParallelOrientationType",
}

RETURNS = [
    _outputs.ReturnsValue("result_bodies", "the names of the bodies the sweep created/modified"),
    _outputs.ReturnsValue("is_solid", "whether the sweep produced a SOLID (vs an open surface)"),
    _outputs.ReturnsValue("path_curves", "how many curves the built path actually holds"),
]


def _cut_check_bodies(comp):
    """The solid bodies an UNSCOPED cut/intersect sweep can act on: every solid directly in the
    feature's host component, resolved once so the same objects are re-read afterwards."""
    return [b for b in _common.iter_collection(safe(lambda: comp.bRepBodies))
            if safe(lambda b=b: b.isSolid)]


def _host_body_keys(host):
    """Return native body keys and fresh bodies, or None when the census is unreadable."""
    coll = safe(lambda: host.bRepBodies)
    count = _common.counted(lambda: coll.count)
    if count is None:
        return None
    found = {}
    for i in range(count):
        body = safe(lambda i=i: coll.item(i))
        key = _common.native_identity(body)
        if key is None or key in found:
            return None
        found[key] = body
    return found


def _solid_sweep(design, solid_body, path, op_key, orient_key, as_surface,
                 target_bodies, component):
    """Sweep one solid body on an owner-local path, retaining its source."""
    if op_key not in ("new", "new_body"):
        return error("'solid_body' supports operation='new' only.")
    if orient_key != "perpendicular":
        return error("'solid_body' uses perpendicular orientation; omit 'orientation'.")
    if as_surface:
        return error("'solid_body' makes a solid; omit as_surface or set it false.")
    if target_bodies not in (None, "", []):
        return error("'target_bodies' applies to profile cut/join/intersect, not solid_body new.")
    if not isinstance(path, str) or not path.strip().lower().startswith("sketch:"):
        return error("'solid_body' needs an owner-local 'sketch:<name>' path; draw the path "
                     "in the body's component.")
    path_name = path.split(":", 1)[1].strip()
    if not path_name:
        return error("'path' needs a sketch name after 'sketch:'.")

    scope = None
    if component:
        scope, serr = _inputs._body_scope(design, component, "component")
        if serr:
            return error(serr)
    body, berr = _SOLID_BODY.resolve(solid_body, scope=scope)
    if berr:
        return error(berr)
    unread = object()
    context = safe(lambda: body.assemblyContext, unread)
    if context is unread:
        return error("'solid_body' has no readable assembly context; reacquire its body handle.")
    if context is not None and safe(lambda: body.nativeObject) is None:
        return error("'solid_body' proxy has no native body; reacquire its body handle.")
    source = _common._native_of(body)
    host = safe(lambda: source.parentComponent)
    if (host is None or _common.same_component(
            safe(lambda: host.parentDesign.rootComponent), safe(lambda: design.rootComponent))
            is not True):
        return error("'solid_body' must belong to this design's native component, not a linked source.")
    if context is not None and _common.same_component(safe(lambda: context.component), host) is not True:
        return error("'solid_body' proxy context does not match its native owner or could not be "
                     "read; reacquire a body handle from that component.")
    if scope is not None:
        scoped_host = safe(lambda: scope[0].component) or scope[0]
        if _common.same_component(scoped_host, host) is not True:
            return error(f"'component' '{component}' does not own 'solid_body'. Use its owner "
                         "or omit component and pass a body handle.")
    if safe(lambda: source.isSolid) is not True:
        return error("'solid_body' is not a readable closed solid; choose a solid body handle.")
    source_key = _common.native_identity(source)
    source_shape = _geom.body_shape(source)
    source_name = safe(lambda: source.name)
    before = _host_body_keys(host)
    if source_key is None or source_shape is None or before is None or source_key not in before:
        return error("'solid_body' identity or shape is unreadable in its owner; no sweep was made.")
    named = [sk for sk in _common.iter_collection(safe(lambda: host.sketches))
             if safe(lambda sk=sk: sk.name) == path_name]
    if len(named) != 1:
        return error(f"'path' sketch '{path_name}' must name exactly one sketch in the "
                     f"solid body's component; found {len(named)}.")
    sweep_path, path_label, patherr = build_path(host, path)
    if patherr:
        return error(patherr)
    path_curves = _common.counted(lambda: sweep_path.count)
    if path_curves is None or path_curves < 1:
        return error("The solid sweep path has no readable curves; draw one connected path.")
    sketch_curves = _common.path_sketch_curve_count(host, path)
    sweeps = host.features.sweepFeatures
    op = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    try:
        sweep_input = sweeps.createInputForSolid(source, sweep_path, op)
    except Exception as exc:
        return error(f"Could not start solid-body sweep: {exc}")
    if sweep_input is None or _common.native_identity(safe(lambda: sweep_input.solidBody)) != source_key:
        return error("Solid sweep input did not retain the requested tool body; no sweep was made.")
    perpendicular = adsk.fusion.SweepSolidOrientationTypes.PerpendicularSolidOrientationType
    if safe(lambda: sweep_input.solidOrientation) != perpendicular:
        return error("Solid sweep input did not retain perpendicular orientation; no sweep was made.")
    try:
        feature = sweeps.add(sweep_input)
    except Exception as exc:
        return error(f"Solid-body sweep failed: {exc}")
    if feature is None:
        return error(_common.no_feature_error(design, "Solid sweep"))

    after = _host_body_keys(host)
    created, face_count, readable = _surface_common._created_bodies(feature)
    created_keys = {_common.native_identity(b) for b in created}
    new_keys = set(after or ()) - set(before)
    if (after is None or not readable or face_count < 1 or None in created_keys
            or len(new_keys) != 1 or created_keys != new_keys):
        return error("Solid sweep was built, but its new result body could not be identified "
                     "from created faces and the owner's body census. "
                     + _common.failed_effect_remedy(design, feature))
    key = next(iter(new_keys))
    feature_keys = {_common.native_identity(b) for b in _common.result_bodies(feature)}
    result = after[key]
    result_shape = _geom.body_shape(result)
    if key not in feature_keys or result_shape is None or result_shape["solid"] is not True \
            or result_shape["volume_cm3"] <= 0 or result_shape == source_shape:
        return error("Solid sweep was built, but its result is not a verified new solid body. "
                     + _common.failed_effect_remedy(design, feature))
    if source_key not in after or _geom.body_shape(after[source_key]) != source_shape:
        return error("Solid sweep was built, but its source tool body's geometry was not retained. "
                     + _common.failed_effect_remedy(design, feature))
    health = safe(lambda: feature.healthState)
    states = adsk.fusion.FeatureHealthStates
    if health not in (states.HealthyFeatureHealthState, states.WarningFeatureHealthState):
        return error("Solid sweep was built, but feature health is unreadable or failed. "
                     + _common.failed_effect_remedy(design, feature))
    if safe(lambda: feature.solidOrientation) != perpendicular:
        return error("Solid sweep was built, but its perpendicular orientation did not persist. "
                     + _common.failed_effect_remedy(design, feature))
    result_name = safe(lambda: result.name)
    if not result_name:
        return error("Solid sweep was built, but the new result body has no readable name. "
                     + _common.failed_effect_remedy(design, feature))
    note = "Solid body swept into a new result; its source tool body retains its geometry."
    if health == states.WarningFeatureHealthState:
        note += " Feature warning: " + str(safe(lambda: feature.errorOrWarningMessage) or "details unreadable") + "."
    warning = _common.path_chain_warning(path_curves, sketch_curves, "sweep")
    if warning:
        note += " " + warning
    return ok({"swept": True, "feature": safe(lambda: feature.name),
               "operation": op_key, "component": safe(lambda: host.name),
               "path": path_label, "path_curves": path_curves,
               "path_sketch_curves": sketch_curves, "orientation": "perpendicular",
               "as_surface": False, "open_profile": False, "is_solid": True,
               "solid_body": source_name, "source_retained": True,
               "result_bodies": [result_name], "note": note})


def handler(profile=None, path=None, operation: str = "new", orientation: str = "perpendicular",
            as_surface: bool = False, target_bodies=None, component: str = "",
            solid_body=None) -> dict:
    """See TOOL_DESCRIPTION."""
    op_key = (operation or "new").strip().lower()
    if op_key not in _common.OPERATIONS:
        return error(f"Unknown operation '{operation}'. Use: new, join, cut, intersect.")
    orient_key = (orientation or "perpendicular").strip().lower()
    if orient_key not in _ORIENTATIONS:
        return error(f"Unknown orientation '{orientation}'. Use: perpendicular, parallel.")

    design = _common.design()
    if not design:
        return error("No active design. Create or open a document first (see doc_new).")
    if solid_body not in (None, "", []):
        if profile not in (None, "", []):
            return error("Choose 'profile' or 'solid_body', not both.")
        return _solid_sweep(design, solid_body, path, op_key, orient_key, as_surface,
                            target_bodies, component)
    comp = target_component(design)

    profile_arg, want_solid, open_profile, host, _source_sketch, perr = _sweep_common.resolve_profile(
        design, comp, profile, as_surface, component)
    if perr:
        return error(perr)

    # Build the path AND the feature on the profile's OWNING component (host) - a profile-consuming
    # feature created on the active component raises bSet when the profile is owned elsewhere.
    sweep_path, path_label, patherr = build_path(host, path)
    if patherr:
        return error(patherr)
    # What the built Path HOLDS, beside what the request named: the profile is driven over these
    # curves and no others, so a chain that stopped short sweeps a stub of the intended run.
    path_curves = _common.counted(lambda: sweep_path.count)
    sketch_curves = _common.path_sketch_curve_count(host, path)

    op = getattr(adsk.fusion.FeatureOperations, _common.OPERATIONS[op_key])
    try:
        sweep_input = host.features.sweepFeatures.createInput(profile_arg, sweep_path, op)
    except Exception as e:
        return error(f"Could not start sweep: {e}. (The path must geometrically connect and the "
                     "profile should sit on/near the path start.)")

    try:
        sweep_input.isSolid = bool(want_solid) # False -> open surface, no end caps
        sweep_input.orientation = getattr(adsk.fusion.SweepOrientationTypes, _ORIENTATIONS[orient_key])
    except Exception as e:
        return error(f"Could not configure the sweep: {e}")

    # target_bodies: scope a cut/intersect to specific bodies so it can't bleed through others.
    scoped_to = None
    bodies_ents = None
    if target_bodies not in (None, "", []):
        if op_key == "new":
            return error("'target_bodies' only applies to cut/join/intersect (a 'new' body has no "
                         "participants). Remove it, or change the operation.")
        bodies_ents, berr = _TARGET_BODIES.resolve(target_bodies)
        if berr:
            return error(berr)
        try:
            sweep_input.participantBodies = list(bodies_ents)
            scoped_to = [safe(lambda b=b: b.name) for b in bodies_ents]
        except Exception as e:
            return error(f"Could not scope to target_bodies: {e}")

    # cut/intersect MATERIAL evidence: the volumes the operation must move, sampled BEFORE the add.
    # A sweep along a path that misses the body reports a healthy feature and result bodies just the
    # same, so only this before/after pair can say material actually changed.
    check_bodies = []
    if op_key in ("cut", "intersect"):
        check_bodies = list(bodies_ents) if bodies_ents else _cut_check_bodies(host)
    vol_before = _geom.volumes(check_bodies)
    # A join is told "grew a body" from "made a second one" by the host's body NAMES before the add.
    bodies_before = _common.component_body_names(host) if op_key == "join" else None

    try:
        feature = host.features.sweepFeatures.add(sweep_input)
    except Exception as e:
        return error(f"Sweep failed: {e}. (A 'cut'/'intersect' needs existing geometry to act on; "
                     "the profile and path must form a valid sweep.)")
    if not feature:
        return error(_common.no_feature_error(design, "Sweep"))

    body_names = [f["name"] for f in _common.body_facts(_common.result_bodies(feature))]

    # An operation that reports success but produced no body is a silent no-op - fail it honestly.
    if op_key == "new" and not body_names:
        return error("Sweep reported success but created no body. Check that the profile sits on the "
                     "path and the path forms a valid, connected sweep.")

    volume_delta_cm3 = None
    if check_bodies:
        delta, readable = _geom.volume_delta(check_bodies, vol_before)
        # A body whose volume read BEFORE and reads unreadable now was consumed whole - a real effect
        # that contributes no delta, so it must not be counted as "nothing moved".
        consumed = [b for b in check_bodies
                    if vol_before.get(id(b)) is not None and _geom.signed_volume(b) is None]
        if readable:
            volume_delta_cm3 = round(delta, 6)
        if readable and not consumed and abs(delta) < _common.NO_VOLUME_CHANGE_CM3:
            if scoped_to:
                # SCOPED: only a participant body can be affected, and every one of them measures
                # what it did before - nothing landed anywhere, so the feature is safe to remove.
                named = ", ".join(n for n in scoped_to if n) or "the scoped bodies"
                rolled = bool(safe(lambda: feature.deleteMe(), False))
                return error(f"Sweep reported success but this {op_key} changed nothing - "
                             f"{named} measure the volumes they had before and none was consumed, so "
                             "the profile does not sweep through any of them. A cut/intersect can "
                             "only affect bodies named in 'target_bodies' - check the path runs "
                             "through them. "
                             + ("The sweep feature was rolled back." if rolled else
                                "Remove the empty feature with design_delete_feature."))
            where = safe(lambda: host.name) or "the host component"
            return error(f"Sweep reported success but this {op_key} changed nothing - every solid "
                         f"body in '{where}' measures the volume it had before and none was "
                         "consumed, so the swept profile does not overlap any of them. Check the "
                         "path runs through the target body (an 'intersect' whose target lies "
                         "entirely INSIDE the swept solid also reads this way). "
                         + _common.failed_effect_remedy(design, feature))

    # SOLID/SURFACE verdict read BACK off the feature - never assumed from the request.
    is_solid = safe(lambda: feature.isSolid)
    if open_profile or is_solid is False:
        note = ("Swept into a SURFACE (no end caps) - pair with model_stitch to close several "
                "surfaces into a solid.")
    else:
        note = "Profile swept into a solid along the path. Pair with view_screenshot (iso) to view it."
    if op_key == "new":
        adv = root_body_advisory(design, host)
        if adv:
            note += " " + adv
    join_clause = _common.join_new_body_clause(op_key, bodies_before, body_names)
    if join_clause:
        note += " " + join_clause
    warning = _common.path_chain_warning(path_curves, sketch_curves, "sweep")
    if warning:
        note += " " + warning

    payload = {
        "swept": True,
        "feature": safe(lambda: feature.name),
        "operation": op_key,
        "component": safe(lambda: feature.parentComponent.name),
        "path": path_label,
        "path_curves": path_curves,
        "orientation": orient_key,
        "as_surface": bool(open_profile or is_solid is False),
        "open_profile": bool(open_profile),
        "is_solid": is_solid,
        "scoped_to_bodies": scoped_to,
        "result_bodies": body_names,
        "note": note,
    }
    # Only a 'sketch:<name>' path has a source curve count; a null would read as an unreadable sketch.
    if sketch_curves is not None:
        payload["path_sketch_curves"] = sketch_curves
    # Absent, never null: a null would read as "no material moved".
    if volume_delta_cm3 is not None:
        payload["volume_delta_cm3"] = volume_delta_cm3
    return ok(payload)


TOOL_DESCRIPTION = (
"Sweep profile or solid body.\n"
+ _outputs.produces_block(RETURNS)
)

sweep_tool = (
    Tool.create_simple(name="model_sweep", description=TOOL_DESCRIPTION)
    .add_input_property("profile", {"type": ["string", "object"]})
    .add_input_property("solid_body", _SOLID_BODY.schema())
    .add_input_property("path", {"type": ["string", "array"], "items": {"type": "string"},
            "description": "Edge handle: TANGENT connections only; 'path' count is the truth. "
                           "Or 'sketch:<name>'."})
    .add_input_property(*_inputs.boolean_op(default="new", description="").as_property())
    .add_input_property("orientation", {"type": "string", "enum": ["perpendicular", "parallel"]})
    .add_input_property("as_surface", {"type": "boolean"})
    .add_input_property("target_bodies", _TARGET_BODIES.schema())
    .add_input_property(*_sketch_detail.COMPONENT_SCOPE)
    .strict_schema()
)
sweep_item = Item.create_tool_item(
    tool=sweep_tool, write="write", handler=handler, run_on_main_thread=True,
    verification=Verification(
        kind="inline",
        rung="geometry",
        evidence_test="tests/unit/test_model_sweep.py::TestCutMovesMaterial"
                      "::test_unscoped_cut_that_moves_no_volume_is_an_error"))


def register_tool():
    register(sweep_item)
