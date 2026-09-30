"""Unit tests for ``param_set.py`` - input validation and the set/create read-back.

Includes the subtle carve-out that an expression of ``"0"`` is NOT treated as "empty".
"""

import math
from types import SimpleNamespace

import adsk.core
import pytest

from conftest import (FakeFeature, FakeModelParameter, FakePoint, FakeSketchPoint, FakeTimeline,
                      FakeTimelineObject, FakeUserParameter, FakeUserParameters, MakeComp,
                      MakeDesign, Sketch, SketchCurves, _NamedCollection, load_tool, make_joint,
                      make_timeline, payload as _payload)

params = load_tool("param_set")


def _design(user_params, timeline, all_params=()):
    """A design carrying the two collections the param write path walks."""
    return MakeDesign(user_parameters=user_params, timeline=timeline,
                      all_parameters=list(all_params))


def _stub_design(monkeypatch, design):
    monkeypatch.setattr(params._common, "design", lambda: design)
    # the create path uses adsk.core.ValueInput.createByString; the string it carries is what the
    # new parameter's expression reads back as.
    monkeypatch.setattr(adsk.core.ValueInput, "createByString",
                        staticmethod(lambda s: SimpleNamespace(stringValue=s)))


class TestSetValidation:
    def test_empty_name_is_error(self):
        res = params.handler(name="", expression="5")
        assert res["isError"] is True
        assert "Provide 'name'" in res["message"]

    def test_empty_expression_is_error(self):
        res = params.handler(name="StockX", expression="")
        assert res["isError"] is True
        assert "Provide 'expression'" in res["message"]

    def test_zero_expression_passes_the_empty_guard(self, monkeypatch):
        # "0" is a legitimate value and must NOT trip the empty-expression guard
        # (note the explicit `expression != "0"` carve-out in the source). Stub
        # _design to a known failure so we can prove we got PAST validation to a
        # different, later error - not the "Provide 'expression'" rejection.
        monkeypatch.setattr(params._common, "design", lambda: None)
        result = params.handler(name="StockX", expression="0")
        assert result["isError"] is True
        assert "Provide 'expression'" not in result["message"]
        assert "active design" in result["message"]   # reached the _design() check


class TestSetCreateOrUpdate:
    def test_set_existing_updates(self, monkeypatch):
        up = FakeUserParameters([FakeUserParameter(name="PartX", expression="10 mm")])
        design = _design(up, make_timeline())
        _stub_design(monkeypatch, design)
        out = _payload(params.handler(name="PartX", expression="20 mm"))
        assert out["set"] is True and out["created"] is False

    def test_silent_no_op_assignment_bites(self, monkeypatch):
        # the assignment raises nothing but the parameter still reads the same expression -> error

        class StuckParam(FakeUserParameter):
            @property
            def expression(self):
                return "10 mm"

            @expression.setter
            def expression(self, v):
                pass                                     # silently ignores the assignment

        up = FakeUserParameters([StuckParam(name="PartX")])
        design = _design(up, make_timeline())
        _stub_design(monkeypatch, design)
        res = params.handler(name="PartX", expression="20 mm")
        assert res["isError"] is True
        assert "did not take" in res["message"]

    def test_setting_the_current_expression_is_already_current(self, monkeypatch):
        up = FakeUserParameters([FakeUserParameter(name="PartX", expression="10 mm")])
        design = _design(up, make_timeline())
        _stub_design(monkeypatch, design)
        out = _payload(params.handler(name="PartX", expression="10 mm"))
        assert out["set"] is True and out["already_current"] is True

    def test_whitespace_normalized_current_expression_is_already_current(self, monkeypatch):
        class NormalizedParam(FakeUserParameter):
            @property
            def expression(self):
                return "10mm"

            @expression.setter
            def expression(self, value):
                pass

        up = FakeUserParameters([NormalizedParam(name="PartX")])
        design = _design(up, make_timeline())
        _stub_design(monkeypatch, design)
        out = _payload(params.handler(name="PartX", expression="10 mm"))
        assert out["set"] is True and out["already_current"] is True

    def test_normalization_keeps_identifier_boundaries_and_quoted_text(self):
        assert params._normalized_expression("10 mm") == params._normalized_expression("10mm")
        assert params._normalized_expression("A B") != params._normalized_expression("AB")
        assert params._normalized_expression("1 e-3") != params._normalized_expression("1e-3")
        assert params._normalized_expression("'a b'") != params._normalized_expression("'ab'")

    def test_silent_equal_value_dependency_change_is_not_already_current(self, monkeypatch):
        class StuckParam(FakeUserParameter):
            @property
            def expression(self):
                return "DriverA"

            @expression.setter
            def expression(self, value):
                pass

        up = FakeUserParameters([StuckParam(name="PartX", value=1.0)])
        _stub_design(monkeypatch, _design(up, make_timeline()))
        res = params.handler(name="PartX", expression="DriverB")
        assert res["isError"] is True and "did not take" in res["message"]

    def test_set_missing_without_create_errors(self, monkeypatch):
        design = _design(FakeUserParameters([]), make_timeline())
        _stub_design(monkeypatch, design)
        res = params.handler(name="Ghost", expression="5 mm")
        assert res["isError"] is True and "create=true" in res["message"]

    def test_set_missing_with_create_makes_user_param(self, monkeypatch):
        up = FakeUserParameters([])
        design = _design(up, make_timeline())
        _stub_design(monkeypatch, design)
        out = _payload(params.handler(name="NewP", expression="3 mm", create=True))
        assert out["set"] is True and out["created"] is True
        assert out["before"] is None
        assert up.itemByName("NewP") is not None        # it was created


class _JointResettingParam(FakeUserParameter):
    """A user parameter whose expression write recomputes, resetting its assigned joint's value."""
    _reset_joint = None

    @property
    def expression(self):
        return self._expression

    @expression.setter
    def expression(self, value):
        self._expression = value
        if self._reset_joint is not None:
            self._reset_joint.jointMotion.rotationValue = 0.0


class TestDrivenJointsReset:
    def test_a_reset_driven_joint_is_named_with_before_and_after(self, monkeypatch):
        joint = make_joint(name="Elbow", kind="revolute", rotation=math.radians(30))
        param = _JointResettingParam(name="PartX", expression="10 mm")
        param._reset_joint = joint
        design = MakeDesign(user_parameters=FakeUserParameters([param]), timeline=make_timeline(),
                            comp=MakeComp(joints=[joint]))
        _stub_design(monkeypatch, design)
        out = _payload(params.handler(name="PartX", expression="20 mm"))
        assert out["driven_joints_reset"] == [
            {"name": "Elbow", "before": {"angle_deg": 30.0}, "after": {"angle_deg": 0.0}}]
        assert "1 driven joint(s) reset" in out["note"]

    def test_a_joint_holding_its_value_is_not_reported(self, monkeypatch):
        joint = make_joint(name="Elbow", kind="revolute", rotation=math.radians(30))
        up = FakeUserParameters([FakeUserParameter(name="PartX", expression="10 mm")])
        design = MakeDesign(user_parameters=up, timeline=make_timeline(),
                            comp=MakeComp(joints=[joint]))
        _stub_design(monkeypatch, design)
        out = _payload(params.handler(name="PartX", expression="20 mm"))
        assert "driven_joints_reset" not in out

    def test_no_joints_publishes_no_reset_key(self, monkeypatch):
        up = FakeUserParameters([FakeUserParameter(name="PartX", expression="10 mm")])
        _stub_design(monkeypatch, _design(up, make_timeline()))
        out = _payload(params.handler(name="PartX", expression="20 mm"))
        assert "driven_joints_reset" not in out


class SketchLinearDimension:
    """No measured shape; named as the live class so its getters entityOne/entityTwo are read."""
    def __init__(self, one, two, parameter):
        self.entityOne, self.entityTwo, self.parameter = one, two, parameter


def _driven_sketch(name, parameter, y=4.0):
    """A sketch whose line point:1 -> point:2 (x 0 -> 3 cm) `parameter` drives; d_other spans 0-1."""
    points = [FakeSketchPoint(geometry=FakePoint(0.0, 0.0), entity_token=f"{name}-p0"),
              FakeSketchPoint(geometry=FakePoint(0.0, y), entity_token=f"{name}-p1"),
              FakeSketchPoint(geometry=FakePoint(3.0, y), entity_token=f"{name}-p2")]
    line = SimpleNamespace(entityToken=f"{name}-l0", isConstruction=False,
                           startSketchPoint=points[1], endSketchPoint=points[2])
    sketch = Sketch(name=name, curves=SketchCurves(lines=[line]), points=points)
    sketch.sketchDimensions = _NamedCollection([
        SketchLinearDimension(points[0], points[1], FakeModelParameter(name="d_other")),
        SketchLinearDimension(points[1], points[2], parameter)])
    return sketch


class _DrivingParam(FakeModelParameter):
    """A parameter whose write solves each driven sketch: point:2 and later go to (x, 4 cm)."""
    moves = ()

    @FakeModelParameter.expression.setter
    def expression(self, text):
        self._expression = text
        for sketch, x in self.moves:
            points = sketch.sketchPoints
            for i in range(2, points.count):
                points.item(i).geometry = FakePoint(x, 4.0)


def _set(monkeypatch, param, others=()):
    design = MakeDesign(user_parameters=FakeUserParameters([]), timeline=make_timeline(),
                        all_parameters=[param, *others])
    _stub_design(monkeypatch, design)
    return params.handler(name=param.name, expression="45 mm")


class TestSketchMoves:
    def test_a_dimension_write_reports_the_point_and_the_line_end_it_moved(self, monkeypatch):
        param = _DrivingParam(name="d11", expression="30 mm")
        sketch = _driven_sketch("Drive", param)
        param.createdBy, param.moves = sketch, ((sketch, 4.5),)
        out = _payload(_set(monkeypatch, param))
        assert out["sketch_moves"] == [{
            "sketch": "Drive", "dimensions": [{"parameter": "d11",
                                               "entities": ["point:1", "point:2"]}],
            "moved": [{"id": "point:2", "from_mm": [30.0, 40.0, 0.0], "to_mm": [45.0, 40.0, 0.0],
                       "ends": ["line:0 end"]}], "moved_count": 1}]
        assert "moved over 0.001 mm, in each sketch's own coordinates" in out["note"]

    def test_the_moved_list_stops_at_the_cap_and_counts_every_move(self, monkeypatch):
        param = _DrivingParam(name="d11", expression="30 mm")
        sketch = _driven_sketch("Drive", param)
        sketch.sketchPoints._items += [FakeSketchPoint(geometry=FakePoint(0.0, float(i)))
                                       for i in range(params._MOVED_CAP)]
        param.createdBy, param.moves = sketch, ((sketch, 4.5),)
        row = _payload(_set(monkeypatch, param))["sketch_moves"][0]
        assert (len(row["moved"]), row["moved_count"]) == (params._MOVED_CAP, params._MOVED_CAP + 1)

    @pytest.mark.parametrize("x,moved", [(0.0001, []), (0.0002, ["point:2"])])
    def test_a_point_moving_no_further_than_the_tolerance_reads_held(self, monkeypatch, x, moved):
        param = _DrivingParam(name="d11", expression="30 mm")
        sketch = _driven_sketch("Drive", param)
        sketch.sketchPoints.item(2).geometry = FakePoint(0.0, 4.0)
        param.createdBy, param.moves = sketch, ((sketch, x),)
        row = _payload(_set(monkeypatch, param))["sketch_moves"][0]
        assert [m["id"] for m in row["moved"]] == moved and row["moved_count"] == len(moved)

    def test_an_unreadable_census_says_the_moves_were_not_read(self, monkeypatch):
        param = _DrivingParam(name="d11", expression="30 mm")
        sketch = _driven_sketch("Drive", param)
        param.createdBy, param.moves = sketch, ((sketch, None),)
        out = _payload(_set(monkeypatch, param))
        assert (out["sketch_moves"][0]["moved"], out["sketch_moves"][0]["moved_count"]) == (None, None)
        assert "The moves in sketch 'Drive' were not read." in out["note"]

    @pytest.mark.parametrize("over,unread", [(0, None), (1, 1)])
    def test_a_user_parameter_reports_each_sketch_it_drives_up_to_the_cap(self, monkeypatch, over,
                                                                         unread):
        count = params._SKETCH_CAP + over
        dims = [FakeModelParameter(name=f"d{i}") for i in range(count)]
        sketches = [_driven_sketch(f"Drive{i}", d) for i, d in enumerate(dims)]
        for d, s in zip(dims, sketches):
            d.createdBy = s
        driver = _DrivingParam(name="SlotW", expression="30 mm", dependents=dims)
        driver.createdBy, driver.moves = None, tuple((s, 4.0) for s in sketches)
        out = _payload(_set(monkeypatch, driver, dims))
        assert [r["sketch"] for r in out["sketch_moves"]] == [
            f"Drive{i}" for i in range(params._SKETCH_CAP)]
        assert all(r["moved"][0]["to_mm"] == [40.0, 40.0, 0.0] for r in out["sketch_moves"])
        assert out.get("sketch_moves_unread") == unread

    def test_a_feature_parameter_among_the_dependents_adds_no_row(self, monkeypatch):
        dim = FakeModelParameter(name="d1")
        sketch = _driven_sketch("DriveA", dim)
        dim.createdBy = sketch
        depth = FakeModelParameter(name="d2", owner=FakeFeature("Extrude1"))
        driver = _DrivingParam(name="SlotW", expression="30 mm", dependents=[depth, dim])
        driver.createdBy, driver.moves = None, ((sketch, 4.5),)
        out = _payload(_set(monkeypatch, driver, (depth, dim)))
        assert [r["sketch"] for r in out["sketch_moves"]] == ["DriveA"]
        assert "were not read" not in out["note"]


class _BreakingParam(FakeUserParameter):
    """A user parameter whose expression write recomputes the listed rows into new health states."""
    _breaks = ()

    @property
    def expression(self):
        return self._expression

    @expression.setter
    def expression(self, value):
        self._expression = value
        for row, state in self._breaks:
            row.healthState = state


class TestNewTimelineProblems:
    def test_a_feature_the_set_breaks_is_named_beside_an_old_warning(self, monkeypatch):
        split = FakeTimelineObject(name="Split1", index=0)
        loft = FakeTimelineObject(name="Loft1", index=1)
        old = FakeTimelineObject(name="Old1", index=2, health=1)
        param = _BreakingParam(name="PartX", expression="10 mm")
        param._breaks = ((split, 2), (loft, 1))
        _stub_design(monkeypatch, _design(FakeUserParameters([param]),
                                          FakeTimeline([split, loft, old])))
        out = _payload(params.handler(name="PartX", expression="200 mm"))
        assert out["set"] is True
        assert out["new_timeline_errors"] == ["Split1"]
        assert out["new_timeline_warnings"] == ["Loft1"]
        assert "Split1, Loft1" in out["note"]

    def test_a_clean_set_publishes_no_problem_keys(self, monkeypatch):
        old = FakeTimelineObject(name="Old1", index=0, health=2)
        up = FakeUserParameters([FakeUserParameter(name="PartX", expression="10 mm")])
        _stub_design(monkeypatch, _design(up, FakeTimeline([old])))
        out = _payload(params.handler(name="PartX", expression="20 mm"))
        assert "new_timeline_errors" not in out and "note" not in out
