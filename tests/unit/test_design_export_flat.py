from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from conftest import load_tool


@pytest.fixture
def exporter(monkeypatch):
    mod = load_tool("design_export")
    body = NS(name="Sheet")
    flat = NS(foldedBody=body)
    opts = NS()
    design = NS(rootComponent=object(), exportManager=NS(
        createDXFFlatPatternExportOptions=Mock(return_value=opts), execute=Mock(return_value=True)))
    comp = NS(flatPattern=flat, parentDesign=design)
    body.parentComponent = comp
    monkeypatch.setattr(mod._DXF_FLAT, "resolve", lambda x: (body, None))
    monkeypatch.setattr(mod._common, "_native_of", lambda x: x)
    monkeypatch.setattr(mod._common, "same_component", lambda a, b: True)
    monkeypatch.setattr(mod._common, "native_identity", lambda x: id(x) if x else None)
    monkeypatch.setattr(mod._common, "design", lambda: design)
    monkeypatch.setattr(mod._export, "snapshot", lambda p: None)
    monkeypatch.setattr(mod._export, "verify_written", lambda p, before: (None, "no fresh file"))
    return mod, design, flat, opts


def test_native_success_without_file_is_error(exporter, tmp_path):
    mod, design, flat, opts = exporter
    result = mod.handler(format="dxf", dxf_flat_pattern="body", file_path=str(tmp_path / "blank.dxf"))
    assert result["isError"] is True
    assert "no fresh file" in str(result)


@pytest.mark.parametrize("extra", [{"dxf_face": "face"}, {"dxf_sketch": "Sketch1"},
                                  {"dxf_export_points": False}, {"dxf_component": "Part"}])
def test_flat_conflicts_refused_before_export(exporter, extra):
    mod, design, flat, opts = exporter
    assert mod.handler(format="dxf", dxf_flat_pattern="body", **extra)["isError"] is True
    design.exportManager.execute.assert_not_called()


def test_wrong_folded_body_is_refused(exporter):
    mod, design, flat, opts = exporter
    flat.foldedBody = object()
    assert mod.handler(format="dxf", dxf_flat_pattern="body")["isError"] is True
    design.exportManager.execute.assert_not_called()
