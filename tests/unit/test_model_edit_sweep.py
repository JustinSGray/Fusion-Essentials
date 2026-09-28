"""Checks sweep operand replacement and its failure evidence."""

from types import SimpleNamespace

import adsk.fusion
import pytest

from conftest import FakeTimeline, error_message, load_tool, payload


mod = load_tool("model_edit_sweep")
_real_target_error = mod._target_error
_real_definition = mod._definition
_real_profile_members = mod._profile_members
_real_path_members = mod._path_members
_real_operand_error = mod._operand_error


def test_closed_profile_identity_reports_one_member():
    profile = SimpleNamespace(entityToken="closed-profile", objectType="adsk::fusion::Profile")
    members = _real_profile_members(profile)
    assert len(members) == 1
    assert mod._definition_report({"profile": members, "path": (("path-line", None),),
                                   "operation": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                                   "orientation": adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType,
                                   "is_solid": True})[
                                       "profile_members"] == 1


class Sweep:
    """One editable sweep with a configurable profile setter."""

    def __init__(self, timeline):
        self.timelineObject = SimpleNamespace(index=1, rollTo=lambda _before: timeline.roll())
        self.entityToken = "sweep-token"
        self.parentComponent = SimpleNamespace(name="Host")
        self.guideRail = None
        self.guideSurfaces = []
        self.solidBody = None
        self.linkedFeatures = SimpleNamespace(count=0, item=lambda _i: None)
        self._profile = "old"
        self._path = ("line",)
        self._participants = []
        self.events = []
        self.assignments = 0
        self.mode = "land"

    @property
    def profile(self):
        return self._profile

    @profile.setter
    def profile(self, value):
        self.assignments += 1
        self.events.append("profile")
        if self.mode != "ignore":
            self._profile = value
        if self.mode == "raise_after_land":
            raise RuntimeError("setter raised after landing")

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        self.assignments += 1
        self.events.append("path")
        self._path = value

    @property
    def participantBodies(self):
        return self._participants

    @participantBodies.setter
    def participantBodies(self, value):
        self.events.append("participants")
        self._participants = value


class Timeline(FakeTimeline):
    """A marker whose restore assignment can be made to fail."""

    def __init__(self):
        super().__init__(items=[None, None, None], marker=3)
        self.refuse_restore = False

    @FakeTimeline.markerPosition.setter
    def markerPosition(self, value):
        if value == 3 and self.refuse_restore:
            raise RuntimeError("marker refused restore")
        FakeTimeline.markerPosition.fset(self, value)

    def roll(self):
        self.markerPosition = 1
        return True


@pytest.fixture
def rig(monkeypatch):
    """Install one measured-contract orchestration seam for each test."""
    timeline = Timeline()
    sweep = Sweep(timeline)
    design = SimpleNamespace(timeline=timeline)
    monkeypatch.setattr(mod._inputs, "resolve_inputs", lambda _spec, _raw: (
        {"feature": (sweep, "Sweep1"), "action": _raw["action"]}, None))
    monkeypatch.setattr(mod, "_target_error", lambda *_args: None)
    monkeypatch.setattr(mod._common, "design", lambda: design)
    monkeypatch.setattr(mod._common, "same_component", lambda *_args: True)
    monkeypatch.setattr(mod, "_operand_error", lambda *_args: None)
    monkeypatch.setattr(mod._sweep_common, "resolve_profile", lambda *_args: (
        "new", True, False, sweep.parentComponent, None, None))
    monkeypatch.setattr(mod._common, "build_path", lambda *_args: (("arc",), "arc", None))
    monkeypatch.setattr(mod._common, "path_sketch_curve_count", lambda *_args: 1)
    monkeypatch.setattr(mod, "_profile_members", lambda operand: operand)
    monkeypatch.setattr(mod, "_path_members", lambda operand: operand)
    monkeypatch.setattr(mod, "_same_feature", lambda *_args: True)
    monkeypatch.setattr(mod._assert, "compute_state", lambda _entity: ("healthy", None))
    monkeypatch.setattr(mod, "_health", lambda *_args: {"errors": [], "warnings": []})
    monkeypatch.setattr(mod, "_feature_body_keys", lambda _feature: {("target", None)})
    monkeypatch.setattr(mod, "_definition", lambda entity: {
        "profile": entity.profile, "path": entity.path,
        "operation": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        "orientation": adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType,
        "is_solid": True})
    monkeypatch.setattr(mod, "_all_shapes", lambda _design: {
        ("target", None): {"component": "Host", "body": "Target",
                           "shape": {"volume_cm3": 1 if sweep.profile == "old" and
                                     sweep.path == ("line",) else 2}},
        ("witness", None): {"component": "Host", "body": "Witness",
                            "shape": {"volume_cm3": 1}}})
    return sweep, timeline


def test_ignored_setter_is_an_error(rig):
    sweep, timeline = rig
    sweep.mode = "ignore"
    result = mod.handler(feature="Sweep1", action="profile", profile="new")
    assert result["isError"] is True
    assert sweep.assignments == 1
    assert result["details"]["definition_matches"] is False
    assert timeline.markerPosition == 3


def test_wrong_operand_is_refused_before_assignment(rig):
    sweep, timeline = rig
    result = mod.handler(feature="Sweep1", action="profile", profile="new", path="sketch:Other")
    assert result["isError"] is True
    assert "unused" in error_message(result)
    assert sweep.assignments == 0
    assert timeline.markerPosition == 3


def test_setter_exception_reports_landed_definition(rig):
    sweep, timeline = rig
    sweep.mode = "raise_after_land"
    result = mod.handler(feature="Sweep1", action="profile", profile="new")
    assert result["isError"] is True
    assert (result["details"]["definition_after"]["profile_signature"] !=
            result["details"]["definition_before"]["profile_signature"])
    assert result["details"]["mutation_attempted"] is True
    assert timeline.markerPosition == 3


def test_restore_failure_is_reported(rig):
    sweep, timeline = rig
    timeline.refuse_restore = True
    result = mod.handler(feature="Sweep1", action="profile", profile="new")
    assert result["isError"] is True
    assert result["details"]["marker_restored"] is False


def test_new_downstream_warning_is_an_error(rig, monkeypatch):
    sweep, timeline = rig
    monkeypatch.setattr(mod, "_health", lambda *_args: {
        "errors": [], "warnings": ["Dependent"] if sweep.profile == "new" else []})
    result = mod.handler(feature="Sweep1", action="profile", profile="new")
    assert result["isError"] is True
    assert result["details"]["new_timeline_warnings"] == ["Dependent"]
    assert timeline.markerPosition == 3


def test_path_edit_checks_actual_target_shape_and_witness(rig):
    sweep, timeline = rig
    result = mod.handler(feature="Sweep1", action="path", path="sketch:Arc")
    assert result["isError"] is False
    assert payload(result)["geometry_changed"] is True
    assert payload(result)["outside_body_changes"] == []
    assert sweep.events == ["path"]
    assert timeline.markerPosition == 3


def test_boolean_scope_is_replayed_before_evaluation(rig, monkeypatch):
    sweep, timeline = rig
    selected = SimpleNamespace(entityToken="selected")
    extra = SimpleNamespace(entityToken="extra")
    sweep._participants = [selected]
    original_setter = Sweep.profile.fset

    def expanding_setter(entity, value):
        original_setter(entity, value)
        entity._participants = [selected, extra]

    monkeypatch.setattr(Sweep, "profile", property(Sweep.profile.fget, expanding_setter))
    original_definition = mod._definition
    monkeypatch.setattr(mod, "_definition", lambda entity: {
        **original_definition(entity),
        "operation": adsk.fusion.FeatureOperations.CutFeatureOperation})
    monkeypatch.setattr(mod, "_participants", lambda entity, _op: list(entity.participantBodies))
    monkeypatch.setattr(mod._common, "native_identity", lambda body: body.entityToken)
    result = mod.handler(feature="Sweep1", action="profile", profile="new")
    assert result["isError"] is False
    assert payload(result)["participant_scope_preserved"] is True
    assert sweep.events == ["profile", "participants"]
    assert sweep.participantBodies == [selected]
    assert timeline.markerPosition == 3


def test_only_bodyless_rolled_back_same_row_sweep_links_are_editable(rig, monkeypatch):
    sweep, timeline = rig
    sweep.objectType = adsk.fusion.SweepFeature.classType()
    sweep.isParametric = True
    sweep.isSuppressed = False
    sweep.baseFeature = None
    companion = SimpleNamespace(
        objectType=adsk.fusion.SweepFeature.classType(),
        timelineObject=SimpleNamespace(index=1),
        healthState=adsk.fusion.FeatureHealthStates.RolledBackFeatureHealthState,
        bodies=SimpleNamespace(count=0))
    sweep.linkedFeatures = SimpleNamespace(count=1, item=lambda _i: companion)
    monkeypatch.setattr(mod, "_target_error", _real_target_error)
    result = mod.handler(feature="Sweep1", action="path", path="sketch:Arc")
    assert result["isError"] is False
    assert payload(result)["inactive_linked_before"] == 1
    assert payload(result)["inactive_linked_after"] == 1
    companion.bodies.count = 1
    result = mod.handler(feature="Sweep1", action="profile", profile="new")
    assert result["isError"] is True
    assert "linked features" in error_message(result)
    assert sweep.assignments == 1
    assert timeline.markerPosition == 3


def test_new_inactive_link_after_setter_is_allowed_but_material_link_is_not(rig, monkeypatch):
    sweep, timeline = rig
    companion = SimpleNamespace(
        objectType=adsk.fusion.SweepFeature.classType(),
        timelineObject=SimpleNamespace(index=1),
        healthState=adsk.fusion.FeatureHealthStates.RolledBackFeatureHealthState,
        bodies=SimpleNamespace(count=0))
    original_setter = Sweep.profile.fset

    def linking_setter(entity, value):
        original_setter(entity, value)
        entity.linkedFeatures = SimpleNamespace(count=1, item=lambda _i: companion)

    monkeypatch.setattr(Sweep, "profile", property(Sweep.profile.fget, linking_setter))
    result = mod.handler(feature="Sweep1", action="profile", profile="new")
    assert result["isError"] is False
    assert payload(result)["inactive_linked_before"] == 0
    assert payload(result)["inactive_linked_evaluated"] == 1
    assert payload(result)["inactive_linked_after"] == 1
    sweep._profile = "old"
    sweep.linkedFeatures = SimpleNamespace(count=0, item=lambda _i: None)
    companion.bodies.count = 1
    result = mod.handler(feature="Sweep1", action="profile", profile="new")
    assert result["isError"] is True
    assert result["details"]["mutation_attempted"] is True
    assert result["details"]["inactive_linked_evaluated"] is None
    assert timeline.markerPosition == 3


def test_open_surface_opaque_profile_reads_back_as_proxy_curve_path(rig, monkeypatch):
    sweep, timeline = rig
    host = sweep.parentComponent
    old_sketch = SimpleNamespace(name="OriginalProfile", parentComponent=host,
                                 timelineObject=SimpleNamespace(index=0))
    new_sketch = SimpleNamespace(name="AlternateProfile", parentComponent=host,
                                 timelineObject=SimpleNamespace(index=0))
    old_line = SimpleNamespace(entityToken="old-line", parentSketch=old_sketch, isValid=True)
    new_line = SimpleNamespace(entityToken="new-line", parentSketch=new_sketch, isValid=True)

    def path_of(line):
        proxy = SimpleNamespace(nativeObject=line, isValid=True)
        return SimpleNamespace(objectType="adsk::fusion::Path", count=1,
                               item=lambda _i: SimpleNamespace(entity=proxy))

    old_profile = path_of(old_line)
    new_profile = path_of(new_line)
    opaque = SimpleNamespace(objectType="adsk::fusion::Profile")
    sweep._profile = old_profile
    sweep._path = path_of(old_line)
    sweep.isSolid = False
    sweep.operation = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    sweep.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    original_setter = Sweep.profile.fset

    def profile_setter(entity, value):
        original_setter(entity, value)
        if entity.mode != "ignore":
            assert value is opaque
            entity._profile = new_profile

    monkeypatch.setattr(Sweep, "profile", property(Sweep.profile.fget, profile_setter))
    monkeypatch.setattr(mod, "_definition", _real_definition)
    monkeypatch.setattr(mod, "_profile_members", _real_profile_members)
    monkeypatch.setattr(mod, "_path_members", _real_path_members)
    monkeypatch.setattr(mod, "_operand_error", _real_operand_error)
    monkeypatch.setattr(mod._sweep_common, "resolve_profile", lambda *_args: (
        opaque, False, True, host, new_sketch, None))
    monkeypatch.setattr(mod._common, "build_path", lambda _host, raw: (
        new_profile, raw, None))
    monkeypatch.setattr(mod, "_all_shapes", lambda _design: {
        ("target", None): {"component": "Host", "body": "Sheet",
                           "shape": {"area_cm2": 0.4 if sweep.profile is old_profile else 0.6}},
        ("witness", None): {"component": "Host", "body": "Witness",
                            "shape": {"area_cm2": 1.0}}})
    result = mod.handler(feature="Sweep1", action="profile", profile={"sketch": "AlternateProfile"})
    assert result["isError"] is False
    assert payload(result)["definition_matches"] is True
    assert payload(result)["geometry_changed"] is True
    assert payload(result)["outside_body_changes"] == []
    sweep._profile = old_profile
    sweep.mode = "ignore"
    result = mod.handler(feature="Sweep1", action="profile", profile={"sketch": "AlternateProfile"})
    assert result["isError"] is True
    assert result["details"]["definition_matches"] is False
    assert timeline.markerPosition == 3
