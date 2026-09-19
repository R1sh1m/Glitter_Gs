"""Generator adapters — intelligent module -> legacy engine inputs (pure).

The live CAD builders stay in the legacy engines / dialog until the Fusion
verification loop runs them inside Fusion 360. This module maps
``ConveyorModule`` back to ``ConveyorInput`` / ``CurveInput`` and describes
the build plan (ordered op list) so the dialog-side executor needs no
dimensional knowledge.
"""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from modules import adapters as _ad
except ImportError:
    from conveyor_addin.modules import adapters as _ad  # type: ignore[no-redef]

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

__all__ = ["module_to_straight_inputs", "module_to_curve_inputs",
           "describe_build_plan"]


def _req(eng: Dict[str, Any], key: str) -> Any:
    if key not in eng:
        raise KeyError(f"Module engineering_parameters missing {key!r}")
    return eng[key]


def module_to_straight_inputs(module: ConveyorModule) -> Any:
    """Rebuild the legacy ``ConveyorInput`` a straight-family module came from."""
    if module.module_type not in ("Straight", "Transfer", "Merge"):
        raise ValueError(f"Not a straight-family module: {module.module_type}")
    eng = module.engineering_parameters
    cross = bool(eng.get("cross_bracing", False))
    legacy = _ad.straight_inputs(
        eng.get("length_mm", module.length),
        eng.get("width_mm", module.width),
        eng.get("height_mm", module.height),
        eng.get("roller_diameter_mm", 60.0),
        eng.get("roller_pitch_mm", eng.get("roller_spacing_mm", 110.0)),
        eng.get("support_spacing_mm", 700.0),
        eng.get("side_guard_height_mm", 0.0),
        bool(eng.get("side_guards", False)),
    )
    if cross:
        import dataclasses

        legacy = dataclasses.replace(legacy, cross_bracing=True)
    return legacy


def module_to_curve_inputs(module: ConveyorModule) -> Any:
    """Rebuild the legacy ``CurveInput`` a curved module came from."""
    if module.module_type != "Curved":
        raise ValueError(f"Not a curved module: {module.module_type}")
    eng = module.engineering_parameters
    return _ad.curve_inputs(
        _req(eng, "inner_radius_mm"), _req(eng, "curve_angle_deg"),
        eng.get("width_mm", module.width),
        eng.get("height_mm", module.height),
        _req(eng, "roller_dia_inner_mm"),
        _req(eng, "roller_pitch_outer_mm"),
        eng.get("support_spacing_mm", 700.0),
        eng.get("side_guard_height_mm", 0.0),
        bool(eng.get("side_guards", False)),
    )


def describe_build_plan(module: ConveyorModule) -> List[str]:
    """Ordered CAD op list for the dialog-side executor (no dimensions)."""
    ops = ["create_parameters", "build_rails", "build_master_roller",
           "pattern_rollers", "build_legs", "validate_subset", "label_model"]
    if module.module_type == "Curved":
        ops.insert(2, "revolve_tapered_master")
        ops.append("verify_taper_cone_face")
    if bool(module.engineering_parameters.get("side_guards", False)):
        ops.append("unsuppress_guards")
    else:
        ops.append("suppress_guards")
    if module.module_type in ("Merge", "Transfer", "Incline", "Custom"):
        ops.append("custom_ports_only:no-cad-builder-yet")
    return ops
