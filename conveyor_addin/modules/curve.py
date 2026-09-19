"""Curved conveyor module factory (adapter over legacy curve engine).

``ConveyorModule.length`` for a curve is the CENTERLINE arc length
``Rc·Θ`` (the conveying distance), not the footprint extents. Footprint
(``footprint_x_mm``/``footprint_y_mm``) is preserved in
``engineering_parameters`` for layout/collision use.
"""

from __future__ import annotations

import math
from typing import Any, Dict

try:  # pytest / Add-In dir on sys.path (repo convention)
    from docking.port import ConveyorPort
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.docking.port import ConveyorPort  # type: ignore[no-redef]

try:
    from modules import adapters as _ad
except ImportError:
    from conveyor_addin.modules import adapters as _ad  # type: ignore[no-redef]

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

__all__ = ["create_curve_module", "curve_engineering_parameters"]


def curve_engineering_parameters(params: Any, derived: Any) -> Dict[str, Any]:
    return {
        "inner_radius_mm": params.inner_radius_mm,
        "curve_angle_deg": params.curve_angle_deg,
        "width_mm": params.width_mm,
        "height_mm": params.height_mm,
        "roller_dia_inner_mm": params.roller_dia_inner_mm,
        "roller_pitch_outer_mm": params.roller_pitch_outer_mm,
        "support_spacing_mm": params.support_spacing_mm,
        "side_guard_height_mm": params.side_guard_height_mm,
        "side_guards": params.side_guards,
        "outer_radius_mm": derived.outer_radius_mm,
        "center_radius_mm": derived.center_radius_mm,
        "arc_inner_mm": derived.arc_inner_mm,
        "arc_center_mm": derived.arc_center_mm,
        "arc_outer_mm": derived.arc_outer_mm,
        "roller_dia_outer_mm": derived.roller_dia_outer_mm,
        "taper_ratio": derived.taper_ratio,
        "roller_count": derived.roller_count,
        "angular_pitch_deg": derived.angular_pitch_deg,
        "support_count": derived.support_count,
        "footprint_x_mm": derived.footprint_x_mm,
        "footprint_y_mm": derived.footprint_y_mm,
        # Conservative local envelope for layout collision (arc sweep box).
        "local_aabb_mm": {
            "min": [0.0, 0.0, 0.0],
            "max": [derived.outer_radius_mm,
                    derived.outer_radius_mm * math.sin(
                        math.radians(params.curve_angle_deg)),
                    params.height_mm],
        },
    }


def create_curve_module(
    inner_radius_mm: float,
    curve_angle_deg: float,
    width_mm: float,
    height_mm: float,
    roller_dia_inner_mm: float,
    roller_pitch_outer_mm: float,
    support_spacing_mm: float,
    side_guard_height_mm: float,
    side_guards: bool,
) -> ConveyorModule:
    """Build an intelligent curved module (validates via legacy engine)."""
    params = _ad.curve_inputs(
        inner_radius_mm, curve_angle_deg, width_mm, height_mm,
        roller_dia_inner_mm, roller_pitch_outer_mm, support_spacing_mm,
        side_guard_height_mm, side_guards,
    )
    derived = _ad.curve_derive(params)
    checks = _ad.curve_verify(params, derived)
    if not checks.get("all"):
        failed = sorted(k for k, v in checks.items() if not v)
        raise ValueError(f"Curve spec invalid, failed: {failed}")
    ports = _ad.curve_ports(params, derived)
    module_id = (
        f"CURVE_Ri{params.inner_radius_mm:.0f}_A{params.curve_angle_deg:.0f}"
        f"_W{params.width_mm:.0f}_H{params.height_mm:.0f}"
        f"_N{derived.roller_count}"
    )
    centerline_length = derived.center_radius_mm * math.radians(
        params.curve_angle_deg
    )
    return ConveyorModule(
        module_id=module_id,
        module_type="Curved",
        length=centerline_length,
        width=params.width_mm,
        height=params.height_mm,
        inlet_port=ConveyorPort.from_legacy_dict(
            f"{module_id}:inlet", {**ports["inlet_port"], "conveyor_type": "Curved"}
        ),
        outlet_port=ConveyorPort.from_legacy_dict(
            f"{module_id}:outlet", {**ports["outlet_port"], "conveyor_type": "Curved"}
        ),
        engineering_parameters=curve_engineering_parameters(params, derived),
        manufacturing_metadata={"signature": module_id, "spec": "tapered-curve"},
        bom_data={"roller_count": derived.roller_count,
                  "support_count": derived.support_count},
    )
