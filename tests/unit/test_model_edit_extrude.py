"""Checks for silent edits, partial failures and timeline restoration."""

from types import SimpleNamespace

import pytest
import adsk.core
import adsk.fusion

from conftest import (BRepBody, BRepFace, FakeFeature, FakeTimeline, FakeTimelineObject,
                      FakeValueInput, MakeComp, Profile, Sketch, _NamedCollection, error_message,
                      install, load_tool, make_bbox, make_design, payload)


mod = load_tool("model_edit_extrude")


class Extrude(FakeFeature):
    """Extrude-specific setters have no shared measured shape fake."""

    def __init__(self, component, body):
        super().__init__(parent_component=component, bodies=[body], entity_token="extrude-token")
        self.objectType = "adsk::fusion::ExtrudeFeature"
        self.isParametric = self.isSolid = self.isValid = True
        self.isThinExtrude = False
        self.baseFeature = None
        self.linkedFeatures = _NamedCollection([])
        self._profile = None
        self.mode = "change"
        self.assignments = 0
        self.after_edit = lambda: None
        self.operation = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        self._participants = []
        self.fail_participants = False
        self.extentOne = SimpleNamespace(objectType="adsk::fusion::DistanceExtentDefinition",
                                         distance=SimpleNamespace(value=1))
        self.extentTwo = None
        self.hasTwoExtents = False
        self.taperAngleOne = SimpleNamespace(value=0)
        self.taperAngleTwo = SimpleNamespace(value=0)
        self.startExtent = SimpleNamespace(objectType="adsk::fusion::ProfilePlaneStartDefinition")
        self.setter_ok = True
        self.setter_args = None

    @property
    def participantBodies(self):
        return self._participants

    @participantBodies.setter
    def participantBodies(self, bodies):
        if self.fail_participants:
            raise RuntimeError("participant setter refused")
        self._participants = bodies
        self.bodies.item(0).volume = 0.5

    def setOneSideExtent(self, extent, direction, taper):
        self.setter_args = extent, direction, taper
        if self.setter_ok:
            self.extentOne = extent
            self.extentTwo = None
            self.hasTwoExtents = False
            self.bodies.item(0).volume = 0.5
        return self.setter_ok

    def setSymmetricExtent(self, distance, full, taper):
        self.setter_args = distance, full, taper
        if self.setter_ok:
            self.extentOne = SimpleNamespace(objectType="adsk::fusion::SymmetricExtentDefinition",
                distance=SimpleNamespace(value=distance.realValue), isFullLength=full)
            self.symmetricExtent = self.extentOne
            self.hasTwoExtents = False
            self.bodies.item(0).volume = 2 * distance.realValue
        return self.setter_ok

    def setTwoSidesExtent(self, one, two, taper_one, taper_two):
        self.setter_args = one, two, taper_one, taper_two
        if self.setter_ok:
            self.extentOne, self.extentTwo = one, two
            self.hasTwoExtents = True
            self.bodies.item(0).volume = 2
        return self.setter_ok

    @property
    def profile(self):
        return self._profile

    @profile.setter
    def profile(self, value):
        self.assignments += 1
        if self.mode == "noop":
            return
        if self.mode == "raise_before":
            raise RuntimeError("profile setter refused")
        self._profile = value
        self.bodies.item(0).boundingBox = make_bbox((2, 0, 0), (3, 1, 1))
        self.after_edit()
        if self.mode == "raise_after":
            raise RuntimeError("profile setter failed after changing")


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setattr(adsk.fusion, "Profile", Profile)
    monkeypatch.setattr(adsk.core.ValueInput, "createByReal", FakeValueInput)
    monkeypatch.setattr(adsk.core.ValueInput, "createByString", lambda value: FakeValueInput(0))
    monkeypatch.setattr(adsk.fusion.DistanceExtentDefinition, "create", lambda value:
        SimpleNamespace(objectType="adsk::fusion::DistanceExtentDefinition",
                        distance=SimpleNamespace(value=value.realValue)))
    monkeypatch.setattr(adsk.fusion.ThroughAllExtentDefinition, "create", lambda:
        SimpleNamespace(objectType="adsk::fusion::ThroughAllExtentDefinition",
                        isPositiveDirection=True))
    component = MakeComp(name="Part", entity_token="part-token")
    body = BRepBody("Body1", volume=1, area=6, bbox=make_bbox((0, 0, 0), (1, 1, 1)),
                    parent_component=component)
    component.bRepBodies = _NamedCollection([body])
    body.isValid = True
    body.physicalProperties = SimpleNamespace(centerOfMass=SimpleNamespace(x=0.5, y=0.5, z=0.5))
    body.faces = _NamedCollection([BRepFace(None, area=1, centroid=SimpleNamespace(x=x, y=y, z=z))
                                  for x, y, z in ((0, .5, .5), (1, .5, .5), (.5, 0, .5),
                                                  (.5, 1, .5), (.5, .5, 0), (.5, .5, 1))])
    monkeypatch.setattr(adsk.fusion, "BRepBody", BRepBody)
    feature = Extrude(component, body)
    sketches = [Sketch(name=name, parent_component=component)
                for name in ("Original", "Replacement")]
    profiles = [Profile(entity_token=f"profile-{i}", parent_sketch=s)
                for i, s in enumerate(sketches)]
    for profile in profiles:
        profile.isValid = True
        profile.assemblyContext = None
    feature._profile = profiles[0]
    rows = [FakeTimelineObject(name=s.name, index=i, entity=s)
            for i, s in enumerate(sketches)]
    rows += [FakeTimelineObject(name=feature.name, index=2, entity=feature),
             FakeTimelineObject(name="Trailing", index=3)]
    timeline = FakeTimeline(rows, marker=3)
    feature.timelineObject = rows[2]
    for i, sketch in enumerate(sketches):
        sketch.timelineObject = rows[i]
    monkeypatch.setattr(rows[2], "rollTo", lambda before: timeline._move(2 if before else 3))
    monkeypatch.setattr(adsk.fusion.ExtrudeFeature, "classType",
                        lambda: "adsk::fusion::ExtrudeFeature")
    design = make_design(comp=component,
                         tokens={"extrude-token": feature, "profile-1": profiles[1]})
    design.timeline = timeline
    install(mod, design)
    return SimpleNamespace(feature=feature, body=body, timeline=timeline, design=design,
                           profiles=profiles, rows=rows, component=component)


def edit():
    return mod.handler(feature="Extrude1", action="profile", profile="profile-1")


def test_equal_volume_profile_shift_and_parked_marker(scene):
    result = payload(edit())
    assert result["edited"] is True
    assert result["geometry_before"][0][0] == result["geometry_after"][0][0] == 1
    assert result["geometry_after"][0][2:4] == [2, 3]
    assert result["same_feature"] is True
    assert "mass properties stale" not in result["note"]
    assert scene.timeline.markerPosition == 3
    assert scene.timeline.count == 4


def test_silent_profile_setter_is_an_error(scene):
    scene.feature.mode = "noop"
    result = edit()
    assert result["isError"] is True
    assert result["details"]["definition_matches"] is False
    assert result["details"]["geometry_changed"] is False
    assert scene.timeline.markerPosition == 3


@pytest.mark.parametrize("mode,landed", [("raise_before", False), ("raise_after", True)])
def test_exception_discloses_landed_state_and_restores_marker(scene, mode, landed):
    scene.feature.mode = mode
    result = edit()
    assert result["isError"] is True
    assert "profile setter" in error_message(result)
    assert result["details"]["definition_matches"] is landed
    assert result["details"]["geometry_changed"] is landed
    assert scene.timeline.markerPosition == 3


def test_marker_restoration_failure_is_not_success(scene, monkeypatch):
    def marker_set(timeline, value):
        if value == 3:
            raise RuntimeError("marker restore refused")
        timeline._marker = value
    monkeypatch.setattr(FakeTimeline, "markerPosition",
                        property(lambda t: t._marker, marker_set))
    result = edit()
    assert result["isError"] is True
    assert result["details"]["definition_matches"] is True
    assert result["details"]["marker_restored"] is False
    assert result["details"]["geometry_changed"] is None


def test_new_downstream_error_is_reported_as_partial_edit(scene):
    scene.timeline.markerPosition = 4
    def break_trailing():
        scene.rows[3].healthState = adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState
    scene.feature.after_edit = break_trailing
    result = edit()
    assert result["isError"] is True
    assert result["details"]["definition_matches"] is True
    assert result["details"]["new_timeline_errors"] == ["Trailing"]


def test_preexisting_error_is_not_new(scene):
    scene.timeline.markerPosition = 4
    scene.rows[3].healthState = adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState
    result = payload(edit())
    assert result["new_timeline_errors"] == []


def test_new_downstream_warning_reports_landed_partial_edit(scene):
    scene.timeline.markerPosition = 4
    def warn_trailing():
        scene.rows[3].healthState = adsk.fusion.FeatureHealthStates.WarningFeatureHealthState
    scene.feature.after_edit = warn_trailing
    result = edit()
    assert result["isError"] is True
    assert "definition landed" in error_message(result)
    assert result["details"]["new_timeline_warnings"] == ["Trailing"]
    assert result["details"]["definition_matches"] is True
    assert scene.timeline.markerPosition == 4


def test_preexisting_warning_is_not_new(scene):
    scene.timeline.markerPosition = 4
    scene.rows[3].healthState = adsk.fusion.FeatureHealthStates.WarningFeatureHealthState
    result = payload(edit())
    assert result["new_timeline_warnings"] == []


def test_later_profile_is_refused_before_roll(scene):
    scene.profiles[1].parentSketch.timelineObject.index = 3
    result = edit()
    assert "must precede" in error_message(result)
    assert scene.feature.assignments == 0
    assert scene.timeline._moves == []


def test_same_count_replacement_is_not_same_feature(scene, monkeypatch):
    original_find = scene.design.findEntityByToken
    monkeypatch.setattr(scene.design, "findEntityByToken",
                        lambda token: [] if token == "extrude-token" else original_find(token))
    result = edit()
    assert result["isError"] is True
    assert result["details"]["same_feature"] is False


def test_profile_definition_without_geometric_change_is_error(scene, monkeypatch):
    monkeypatch.setattr(scene.feature, "after_edit", lambda: setattr(
        scene.body, "boundingBox", make_bbox((0, 0, 0), (1, 1, 1))))
    result = edit()
    assert result["isError"] is True
    assert result["details"]["definition_matches"] is True
    assert result["details"]["geometry_changed"] is False


def test_operation_cut_requires_explicit_participants(scene):
    result = mod.handler(feature="Extrude1", action="operation", operation="cut")
    assert "requires explicit" in error_message(result)
    assert scene.timeline._moves == []


def test_operation_reports_partial_when_participant_setter_fails(scene):
    scene.feature.fail_participants = True
    result = mod.handler(feature="Extrude1", action="operation", operation="cut",
                         target_bodies=["Body1"])
    assert result["isError"] is True
    assert result["details"]["definition_after"]["operation"] == "cut"
    assert result["details"]["definition_matches"] is False
    assert "participant setter refused" in error_message(result)
    assert scene.timeline.markerPosition == 3


def test_operation_sets_requested_participants(scene):
    result = payload(mod.handler(feature="Extrude1", action="operation", operation="cut",
                                 target_bodies=["Body1"]))
    assert result["edited"] is True
    assert scene.feature.participantBodies == [scene.body]
    assert result["definition_after"]["operation"] == "cut"


def test_symmetric_requires_explicit_zero_taper_and_half_length(scene):
    result = payload(mod.handler(feature="Extrude1", action="extent", extent="symmetric",
                                 distance=8))
    assert result["definition_matches"] is True
    assert scene.feature.setter_args[1] is False
    assert scene.feature.setter_args[2].realValue == 0
    assert scene.feature.extentOne.distance.value == pytest.approx(0.8)


@pytest.mark.parametrize("scoped", [False, True])
def test_two_side_reads_each_distance_independently(scene, scoped):
    if scoped:
        scene.feature.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
        scene.feature._participants = [scene.body]
    result = payload(mod.handler(feature="Extrude1", action="extent", extent="two_side",
                                 distance=12, distance2=8))
    assert result["definition_matches"] is True
    assert scene.feature.extentOne.distance.value == pytest.approx(1.2)
    assert scene.feature.extentTwo.distance.value == pytest.approx(0.8)


def test_false_extent_setter_does_not_report_success(scene):
    scene.feature.setter_ok = False
    result = mod.handler(feature="Extrude1", action="extent", extent="symmetric", distance=8)
    assert "setter returned false" in error_message(result)
    assert scene.timeline.markerPosition == 3
    assert result["details"]["definition_matches"] is False


def test_negative_through_all_sets_both_direction_inputs(scene):
    result = payload(mod.handler(feature="Extrude1", action="extent", extent="through_all",
                                 direction="negative"))
    assert result["definition_matches"] is True
    definition, direction, taper = scene.feature.setter_args
    assert definition.isPositiveDirection is False
    assert direction == adsk.fusion.ExtentDirections.NegativeExtentDirection
    assert taper.realValue == 0


@pytest.mark.parametrize("operation", ["CutFeatureOperation", "IntersectFeatureOperation"])
def test_scoped_through_all_both_refused_before_roll(scene, operation):
    scene.feature.operation = getattr(adsk.fusion.FeatureOperations, operation)
    scene.feature._participants = [scene.body]
    result = mod.handler(feature="Extrude1", action="extent", extent="through_all", direction="both")
    assert "Two-sided through_all with cut/intersect" in error_message(result)
    assert "separate one-sided features" in error_message(result)
    assert scene.timeline._moves == []
    assert scene.feature.setter_args is None
    assert scene.body.volume == 1


@pytest.mark.parametrize("source_operation,args", [
    ("CutFeatureOperation", {"action": "profile", "profile": "profile-1"}),
    ("IntersectFeatureOperation", {"action": "extent", "extent": "distance", "distance": 8}),
    ("CutFeatureOperation", {"action": "participants", "target_bodies": ["Body1"]}),
    ("NewBodyFeatureOperation", {"action": "operation", "operation": "cut", "target_bodies": ["Body1"]}),
    ("JoinFeatureOperation", {"action": "operation", "operation": "intersect", "target_bodies": ["Body1"]}),
])
def test_two_sided_through_source_refuses_scope_assignment_before_roll(scene, source_operation, args):
    scene.feature.operation = getattr(adsk.fusion.FeatureOperations, source_operation)
    scene.feature.hasTwoExtents = True
    scene.feature.extentOne = adsk.fusion.ThroughAllExtentDefinition.create()
    scene.feature.extentTwo = adsk.fusion.ThroughAllExtentDefinition.create()
    result = mod.handler(feature="Extrude1", **args)
    assert "Two-sided through_all with cut/intersect" in error_message(result)
    assert scene.timeline._moves == []
    assert scene.feature.assignments == 0
    assert scene.feature.setter_args is None
    assert scene.feature.participantBodies == []
    assert scene.body.volume == 1


def test_unscoped_new_body_through_all_both_is_not_refused(scene):
    result = payload(mod.handler(feature="Extrude1", action="extent", extent="through_all", direction="both"))
    assert result["edited"] is True
    assert scene.feature.hasTwoExtents is True


def test_distance_replacement_accepts_existing_extent_kind(scene):
    result = payload(mod.handler(feature="Extrude1", action="extent", extent="distance", distance=8))
    assert result["definition_matches"] is True
    assert scene.feature.extentOne.distance.value == pytest.approx(0.8)


def test_nonzero_taper_refused_before_extent_mutation(scene):
    scene.feature.taperAngleOne.value = 0.2
    result = mod.handler(feature="Extrude1", action="extent", extent="symmetric", distance=8)
    assert "zero readable taper" in error_message(result)
    assert scene.timeline._moves == []


def test_equal_volume_pocket_move_is_detected_by_face_centroids(scene, monkeypatch):
    def move_pocket():
        scene.body.boundingBox = make_bbox((0, 0, 0), (1, 1, 1))
        scene.body.faces.item(0).centroid.x = 0.1
    monkeypatch.setattr(scene.feature, "after_edit", move_pocket)
    result = payload(edit())
    assert result["geometry_before"][0][:8] == result["geometry_after"][0][:8]
    assert result["geometry_before"][0][8] == result["geometry_after"][0][8] == 6
    assert result["geometry_before"][0][9] != result["geometry_after"][0][9]


@pytest.mark.parametrize("unread", [None, float("nan")])
def test_unread_face_centroid_reports_unverified_landed_edit(scene, unread):
    scene.feature.after_edit = lambda: setattr(scene.body.faces.item(0).centroid, "x", unread)
    result = edit()
    assert result["isError"] is True
    assert result["details"]["definition_matches"] is True
    assert result["details"]["geometry_changed"] is None
    assert scene.timeline.markerPosition == 3


def test_unevaluated_rows_are_disclosed_at_parked_marker(scene):
    scene.rows[3].healthState = adsk.fusion.FeatureHealthStates.RolledBackFeatureHealthState
    result = payload(edit())
    assert result["unevaluated_timeline_items"] == 1
    assert "unevaluated" in result["note"]


def test_extra_action_input_refused_before_mutation(scene):
    result = mod.handler(feature="Extrude1", action="profile", profile="profile-1", operation="cut")
    assert "not used" in error_message(result)
    assert scene.feature.assignments == 0


def test_own_component_proxy_participant_is_normalized(scene, monkeypatch):
    proxy = SimpleNamespace(nativeObject=scene.body, assemblyContext=object())
    monkeypatch.setattr(mod._BODIES, "resolve", lambda raw: ([proxy], None))
    result = payload(mod.handler(feature="Extrude1", action="operation", operation="cut",
                                 target_bodies=["Part:Body1"]))
    assert result["definition_matches"] is True
    assert scene.feature.participantBodies == [scene.body]


@pytest.mark.parametrize("action", ["profile", "extent"])
def test_profile_and_extent_preserve_participant_scope(scene, monkeypatch, action):
    other = BRepBody("Other", volume=1, parent_component=scene.component)
    scene.feature.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    scene.feature._participants = [scene.body]
    original_members = Extrude.participantBodies
    assignments = []
    def set_members(feature, bodies):
        assignments.append(list(bodies))
        original_members.fset(feature, bodies)
    monkeypatch.setattr(Extrude, "participantBodies", property(original_members.fget, set_members))
    if action == "profile":
        scene.feature.after_edit = lambda: setattr(scene.feature, "_participants", [scene.body, other])
        result = payload(edit())
    else:
        original_extent = scene.feature.setSymmetricExtent
        def extent(*args):
            returned = original_extent(*args)
            scene.feature._participants = [scene.body, other]
            return returned
        monkeypatch.setattr(scene.feature, "setSymmetricExtent", extent)
        result = payload(mod.handler(feature="Extrude1", action="extent", extent="symmetric", distance=8))
    assert result["definition_matches"] is True
    assert assignments == [[scene.body], [scene.body]]
    assert scene.feature.participantBodies == [scene.body]


def test_scope_reapply_silent_noop_is_partial_failure(scene, monkeypatch):
    other = BRepBody("Other", parent_component=scene.component)
    scene.feature.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    scene.feature._participants = [scene.body]
    scene.feature.after_edit = lambda: setattr(scene.feature, "_participants", [scene.body, other])
    monkeypatch.setattr(Extrude, "participantBodies",
                        property(lambda f: f._participants, lambda f, bodies: None))
    result = edit()
    assert result["isError"] is True
    assert result["details"]["definition_matches"] is False
    assert result["details"]["definition_after"]["participants"] == ["Body1", "Other"]


def test_to_face_proxy_readback_compares_native_entity(scene):
    native_face = SimpleNamespace(nativeObject=None)
    proxy = SimpleNamespace(nativeObject=native_face)
    scene.feature.extentOne = SimpleNamespace(objectType="adsk::fusion::ToEntityExtentDefinition",
                                              entity=proxy, isChained=False,
                                              offset=SimpleNamespace(value=0))
    assert mod._definition_matches(scene.feature, "extent",
                                   {"extent": "to_face", "to_object": native_face}) is True


@pytest.mark.parametrize("replay", ["repair", "stale_mass", "noop", "raise"])
def test_evaluated_scope_replay_and_sibling_material_proof(scene, monkeypatch, replay):
    sibling = MakeComp(name="Sibling", entity_token="sibling")
    roof = BRepBody("Roof", volume=4, area=22, bbox=make_bbox((0, 0, 3), (4, 2, 3.5)),
                    parent_component=sibling)
    roof.physicalProperties = SimpleNamespace(centerOfMass=SimpleNamespace(x=2, y=1, z=3.25))
    roof.faces = _NamedCollection([BRepFace(None, area=area, centroid=SimpleNamespace(x=x, y=y, z=z))
                                  for area, x, y, z in ((1, 0, 1, 3.25), (1, 4, 1, 3.25),
                                      (2, 2, 0, 3.25), (2, 2, 2, 3.25), (8, 2, 1, 3), (8, 2, 1, 3.5))])
    sibling.bRepBodies = _NamedCollection([roof])
    scene.design._all_components.append(sibling)
    scene.feature.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    scene.feature._participants = [scene.body]
    scene.timeline.markerPosition = 4
    alias = Extrude(sibling, roof)
    alias.bodies = _NamedCollection([])
    alias._profile, alias._participants = scene.profiles[0], [scene.body]
    alias.timelineObject = scene.feature.timelineObject
    alias.assemblyContext = None
    alias.linkedFeatures = _NamedCollection([scene.feature])
    evaluated, assigned = [], []
    original_marker = FakeTimeline.markerPosition
    def move(timeline, value):
        original_marker.fset(timeline, value)
        if value == 3 and not evaluated:
            evaluated.append(True)
            roof.volume = 3.955
            scene.feature.linkedFeatures = _NamedCollection([alias])
    monkeypatch.setattr(FakeTimeline, "markerPosition", property(original_marker.fget, move))
    original_members = Extrude.participantBodies
    def members(feature, bodies):
        assigned.append(scene.timeline.markerPosition)
        if evaluated and replay == "raise":
            raise RuntimeError("post-evaluation scope replay refused")
        original_members.fset(feature, bodies)
        if evaluated and replay in ("repair", "stale_mass"):
            roof.volume = 4
            if replay == "stale_mass":
                roof.physicalProperties.volume = 3.955
                roof.physicalProperties.centerOfMass.x = 2.0085335
                roof.faces = _NamedCollection(list(reversed(list(roof.faces))))
    monkeypatch.setattr(Extrude, "participantBodies", property(original_members.fget, members))
    result = mod.handler(feature="Extrude1", action="extent", extent="through_all", direction="positive")
    repaired = replay in ("repair", "stale_mass")
    details = payload(result) if repaired else result["details"]
    assert assigned == [2, 2]
    assert scene.timeline.markerPosition == 4
    assert details["same_feature"] is True
    assert details["other_components_unchanged"] is repaired
    if repaired:
        assert details["linked_component_aliases"] == ["Sibling"]
        assert details["linked_scope_verified_at_edit"] is True
        assert details["participants_reapplied_after_evaluation"] is True
        assert "Linked replay may leave mass properties stale." in details["note"]
        assert "design_recompute" in details["note"]
        assert "reset uncaptured joint poses" in details["note"]
        assert roof.volume == 4
    else:
        assert result["isError"] is True
        assert details["definition_matches"] is True
        assert details["other_component_changes"][0]["component"] == "Sibling"
        assert details["other_component_changes"][0]["after"][0][0] == 3.955


def test_linked_alias_address_is_refused_before_mutation(scene, monkeypatch):
    foreign = MakeComp(name="AliasOwner", entity_token="alias-owner")
    foreign.bRepBodies = _NamedCollection([])
    scene.design._all_components.append(foreign)
    alias = Extrude(foreign, scene.body)
    alias._profile = scene.profiles[0]
    alias.timelineObject = scene.feature.timelineObject
    alias.linkedFeatures = _NamedCollection([scene.feature])
    monkeypatch.setattr(mod._FEATURE, "resolve", lambda raw: ((alias, "AliasOwner/Extrude1"), None))
    result = mod.handler(feature="AliasOwner/Extrude1", action="extent", extent="distance", distance=5)
    assert result["isError"] is True
    assert "original Extrude" in error_message(result)
    assert result["details"]["mutation_attempted"] is False
    assert alias.setter_args is None
    assert scene.timeline.markerPosition == 3
