# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Read native sheet-metal rules, component ownership and flat-pattern presence."""

from ..mcp_primitives.tool import Tool
from ..mcp_primitives.item import Item
from ..mcp_primitives.registry import register
from ._common import error, iter_collection, ok, safe
from . import _common, _sheet_common

_SLICES = ("rules", "library_rules", "components", "features")


def _normalize_include(include):
    """Return requested rich-read slices."""
    if include in (None, "", []):
        return []
    if isinstance(include, str):
        return [part.strip().lower() for part in include.split(",") if part.strip()]
    return [str(part).strip().lower() for part in include]


def _rules(design, scope, limit):
    """Return readable scoped rule rows up to the response cap."""
    collection = safe(lambda: (design.designSheetMetalRules if scope == "design"
                               else design.librarySheetMetalRules))
    if collection is None:
        return {"readable": False, "rules": None}
    rules = list(iter_collection(collection))
    return {"readable": True, "rules": [_sheet_common.rule_row(design, r, scope) for r in rules[:limit]],
            "total": len(rules), "truncated": len(rules) > limit}


def _components(design, limit):
    """Return component rows and disclose an incomplete design walk."""
    collection = safe(lambda: design.allComponents)
    expected = safe(lambda: collection.count) if collection is not None else None
    comps = _common.all_components(design)
    complete = expected is not None and len(comps) == expected
    return {"components": [_sheet_common.component_row(c) for c in comps[:limit]],
            "total": len(comps) if complete else None,
            "walk_complete": complete, "truncated": len(comps) > limit,
            "note": "Component names may repeat; use a body handle from find_geometry for sheet_convert."}


def _hem_kind(hem):
    """Return the hem's definition kind ('flat', 'rolled', ...) from its objectType suffix, or None."""
    cls = (safe(lambda: hem.definition.objectType) or "").split("::")[-1]
    if not cls:
        return None
    return cls[:-len("HemFeatureDefinition")].lower() if cls.endswith("HemFeatureDefinition") else cls.lower()


def _feature_row(component):
    """Return one component's fold/hem/rip/join/flange counts and flat-pattern state."""
    feats = safe(lambda: component.features)
    def _count(attr):
        coll = safe(lambda: getattr(feats, attr)) if feats is not None else None
        return safe(lambda: coll.count) if coll is not None else None
    hems_coll = safe(lambda: feats.hemFeatures) if feats is not None else None
    hems = ([{"name": safe(lambda h=h: h.name), "kind": _hem_kind(h)} for h in iter_collection(hems_coll)]
            if hems_coll is not None else None)
    return {"component": safe(lambda: component.name),
            "folds": _count("foldFeatures"), "hems": hems, "rips": _count("ripFeatures"),
            "joins": _count("joinByBendFeatures"), "flanges": _count("flangeFeatures"),
            "flat_pattern": _sheet_common.flat_pattern_row(component)}


def _features(design, limit):
    """Return per-component feature-family counts, capped, and disclose an incomplete walk."""
    collection = safe(lambda: design.allComponents)
    expected = safe(lambda: collection.count) if collection is not None else None
    comps = _common.all_components(design)
    complete = expected is not None and len(comps) == expected
    return {"components": [_feature_row(c) for c in comps[:limit]],
            "total": len(comps) if complete else None,
            "walk_complete": complete, "truncated": len(comps) > limit}


def handler(include=None, max_results: int = 50) -> dict:
    """See TOOL_DESCRIPTION."""
    inc = _normalize_include(include)
    bad = [name for name in inc if name not in _SLICES and name != "default"]
    if bad:
        return error(f"Unknown include {bad}. Use rules, library_rules, components, features, or default.")
    if not isinstance(max_results, int) or not 1 <= max_results <= 200:
        return error(f"max_results '{max_results}' must be an integer from 1 to 200.")
    design = _common.design()
    if design is None:
        return error("No active design. Create or open a design first.")
    out = {}
    if not inc or "default" in inc:
        local = safe(lambda: design.designSheetMetalRules)
        library = safe(lambda: design.librarySheetMetalRules)
        out["design_rule_count"] = safe(lambda: local.count) if local is not None else None
        out["library_rule_count"] = safe(lambda: library.count) if library is not None else None
        out["next"] = [name for name in _SLICES if name not in inc]
    if "rules" in inc:
        out["rules"] = _rules(design, "design", max_results)
    if "library_rules" in inc:
        out["library_rules"] = _rules(design, "library", max_results)
    if "components" in inc:
        out["components"] = _components(design, max_results)
    if "features" in inc:
        out["features"] = _features(design, max_results)
    return ok(out)


TOOL_DESCRIPTION = ("Read sheet-metal rule counts; include rules, library_rules, components or "
                    "features for detail.")

tool = (Tool.create_simple(name="sheet_get", description=TOOL_DESCRIPTION)
        .add_input_property("include", {"type": "array", "items": {"type": "string",
                                          "enum": list(_SLICES) + ["default"]}})
        .add_input_property("max_results", {"type": "integer", "description": "Response rows per slice, max 200."})
        .strict_schema())
item = Item.create_tool_item(tool=tool, write="read", handler=handler, run_on_main_thread=True)


def register_tool():
    register(item)
