"""Checks bounded Loft section edits and their failure evidence."""

from types import SimpleNamespace

import adsk.fusion
import pytest

from conftest import FakeTimeline, error_message, load_tool, payload


mod = load_tool("model_edit_loft")
_real_target_error = mod._target_error


class Timeline(FakeTimeline):
    """A marker that rolls before the Loft and can reject restoration."""

    def __init__(self):
        super().__init__(items=[None] * 5, marker=5)
        self.refuse_restore = False

    @FakeTimeline.markerPosition.setter
    def markerPosition(self, value):
        if value == 5 and self.refuse_restore:
            raise RuntimeError("marker restore refused")
        FakeTimeline.markerPosition.fset(self, value)

    def roll(self):
        self.markerPosition = 2
        return True


class Section:
    """A section with native-style entity assignment and checked deletion."""

    def __init__(self, owner, name):
        self.owner = owner
        self._entity = name
        self.mode = "land"
        self.endCondition = SimpleNamespace(objectType="adsk::fusion::LoftFreeEndCondition")

    @property
    def entity(self):
        return self._entity

    @entity.setter
    def entity(self, value):
        self.owner.assignments += 1
        if self.mode != "ignore":
            self._entity = value
        if self.mode == "raise_after_land":
            raise RuntimeError("setter raised after landing")

    def deleteMe(self):
        self.owner.assignments += 1
        if self.mode == "false":
            return False
        self.owner.sections.remove(self)
        return True


class Loft:
    """A Loft whose ordered section list changes in place."""

    def __init__(self, timeline):
        self.timelineObject = SimpleNamespace(index=2, rollTo=lambda _before: timeline.roll())
        self.entityToken = "loft-token"
        self.parentComponent = SimpleNamespace(name="Host")
        self.sections = [Section(self, name) for name in ("A", "B", "C")]
        self.assignments = 0
        self.mode = "land"

    @property
    def loftSections(self):
        return SimpleNamespace(count=len(self.sections), item=lambda i: self.sections[i])


@pytest.fixture
def rig(monkeypatch):
    """Install one edit orchestration scene with a result body and witness."""
    timeline = Timeline()
    loft = Loft(timeline)
    design = SimpleNamespace(timeline=timeline)
    monkeypatch.setattr(mod._inputs, "resolve_inputs", lambda _spec, raw: (
        {"feature": (loft, "Loft1"), "action": raw["action"]}, None))
    monkeypatch.setattr(mod, "_target_error", lambda *_args: None)
    monkeypatch.setattr(mod._common, "design", lambda: design)
    monkeypatch.setattr(mod, "_operand_error", lambda *_args: None)
    monkeypatch.setattr(mod._inputs.ProfileRef, "resolve", lambda _self, _raw, _scope: ("X", None))
    monkeypatch.setattr(mod._common, "native_identity", lambda operand: operand)
    monkeypatch.setattr(mod, "_same_feature", lambda *_args: True)
    monkeypatch.setattr(mod._assert, "compute_state", lambda _entity: ("healthy", None))
    monkeypatch.setattr(mod, "_health", lambda *_args: {"errors": [], "warnings": []})
    monkeypatch.setattr(mod, "_feature_body_keys", lambda _feature: {"target"})
    def definition(feature):
        ends = (mod._end_state(feature.sections[0]), mod._end_state(feature.sections[-1]))
        if None in ends:
            return None
        return {"sections": tuple(section.entity for section in feature.sections),
                "operation": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "is_solid": True, "is_closed": False, "guide_count": 0,
                "ends": ends}

    monkeypatch.setattr(mod, "_definition", definition)
    monkeypatch.setattr(mod, "_all_shapes", lambda _design: {
        "target": {"component": "Host", "body": "Target",
                   "shape": {"volume_cm3": 1 if tuple(s.entity for s in loft.sections) ==
                             ("A", "B", "C") else 2}},
        "witness": {"component": "Host", "body": "Witness",
                    "shape": {"volume_cm3": 1}}})
    return loft, timeline


def test_retarget_changes_only_middle_section_and_material(rig):
    loft, timeline = rig
    result = mod.handler(feature="Loft1", action="retarget", section_index=1, profile="X")
    assert result["isError"] is False
    assert tuple(s.entity for s in loft.sections) == ("A", "X", "C")
    assert payload(result)["definition_matches"] is True
    assert payload(result)["geometry_changed"] is True
    assert payload(result)["outside_body_changes"] == []
    assert timeline.markerPosition == 5


def test_remove_from_three_leaves_two_ordered_sections(rig):
    loft, timeline = rig
    result = mod.handler(feature="Loft1", action="remove", section_index=1)
    assert result["isError"] is False
    assert tuple(s.entity for s in loft.sections) == ("A", "C")
    assert payload(result)["definition_after"]["section_count"] == 2
    assert loft.assignments == 1 and timeline.markerPosition == 5


def test_two_section_removal_refuses_before_delete(rig):
    loft, timeline = rig
    loft.sections.pop(1)
    result = mod.handler(feature="Loft1", action="remove", section_index=1)
    assert result["isError"] is True
    assert "fewer than two" in error_message(result)
    assert loft.assignments == 0 and timeline.markerPosition == 5


def test_unreadable_link_count_refuses_before_mutation(rig):
    loft, timeline = rig
    loft.objectType = adsk.fusion.LoftFeature.classType()
    loft.isParametric, loft.isSuppressed, loft.baseFeature = True, False, None
    assert "unreadable link count" in _real_target_error(loft, "Loft1")
    loft.linkedFeatures = SimpleNamespace(count=1)
    assert "linked features" in _real_target_error(loft, "Loft1")
    loft.linkedFeatures.count = 0
    assert _real_target_error(loft, "Loft1") is None
    assert loft.assignments == 0 and timeline.markerPosition == 5


def test_direction_end_weight_and_angle_retained(rig):
    loft, timeline = rig
    loft.sections[0].endCondition = SimpleNamespace(
        objectType="adsk::fusion::LoftDirectionEndCondition",
        weight=SimpleNamespace(name="StartWeight", expression="1.5", value=1.5),
        angle=SimpleNamespace(name="StartAngle", expression="5 deg", value=0.0872664626))
    result = mod.handler(feature="Loft1", action="remove", section_index=1)
    assert result["isError"] is False
    assert payload(result)["definition_matches"] is True
    assert payload(result)["definition_after"]["end_controls"] == (
        payload(result)["definition_before"]["end_controls"])
    assert timeline.markerPosition == 5


def test_changed_direction_weight_is_detected(rig, monkeypatch):
    loft, timeline = rig
    loft.sections[0].endCondition = SimpleNamespace(
        objectType="adsk::fusion::LoftDirectionEndCondition",
        weight=SimpleNamespace(name="StartWeight", expression="1.5", value=1.5),
        angle=SimpleNamespace(name="StartAngle", expression="5 deg", value=0.0872664626))
    original_setter = Section.entity.fset

    def altering_setter(section, value):
        original_setter(section, value)
        section.owner.sections[0].endCondition.weight.value = 2.0

    monkeypatch.setattr(Section, "entity", property(Section.entity.fget, altering_setter))
    result = mod.handler(feature="Loft1", action="retarget", section_index=1, profile="X")
    assert result["isError"] is True
    assert result["details"]["definition_matches"] is False
    assert timeline.markerPosition == 5


def test_unreadable_direction_angle_refuses_before_mutation(rig):
    loft, timeline = rig
    loft.sections[0].endCondition = SimpleNamespace(
        objectType="adsk::fusion::LoftDirectionEndCondition",
        weight=SimpleNamespace(name="StartWeight", expression="1.5", value=1.5))
    result = mod.handler(feature="Loft1", action="remove", section_index=1)
    assert result["isError"] is True
    assert "definition is unreadable" in error_message(result)
    assert loft.assignments == 0 and timeline.markerPosition == 5


def test_ignored_retarget_is_error(rig):
    loft, timeline = rig
    loft.sections[1].mode = "ignore"
    result = mod.handler(feature="Loft1", action="retarget", section_index=1, profile="X")
    assert result["isError"] is True
    assert result["details"]["definition_matches"] is False
    assert loft.assignments == 1 and timeline.markerPosition == 5


def test_failed_delete_is_error_and_marker_restored(rig):
    loft, timeline = rig
    loft.sections[1].mode = "false"
    result = mod.handler(feature="Loft1", action="remove", section_index=1)
    assert result["isError"] is True
    assert "deleteMe()" in error_message(result)
    assert tuple(s.entity for s in loft.sections) == ("A", "B", "C")
    assert timeline.markerPosition == 5


def test_setter_exception_reports_partial_change(rig):
    loft, timeline = rig
    loft.sections[1].mode = "raise_after_land"
    result = mod.handler(feature="Loft1", action="retarget", section_index=1, profile="X")
    assert result["isError"] is True
    assert result["details"]["mutation_attempted"] is True
    assert result["details"]["definition_after"]["section_signatures"] != (
        result["details"]["definition_before"]["section_signatures"])
    assert timeline.markerPosition == 5


def test_new_downstream_warning_is_error(rig, monkeypatch):
    loft, timeline = rig
    monkeypatch.setattr(mod, "_health", lambda *_args: {
        "errors": [], "warnings": ["Dependent"] if loft.sections[1].entity == "X" else []})
    result = mod.handler(feature="Loft1", action="retarget", section_index=1, profile="X")
    assert result["isError"] is True
    assert result["details"]["new_timeline_warnings"] == ["Dependent"]
    assert timeline.markerPosition == 5


def test_restore_failure_is_error(rig):
    _loft, timeline = rig
    timeline.refuse_restore = True
    result = mod.handler(feature="Loft1", action="remove", section_index=1)
    assert result["isError"] is True
    assert result["details"]["marker_restored"] is False
