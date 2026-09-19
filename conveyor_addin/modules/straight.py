"""Straight conveyor module factory (adapter over legacy straight engine)."""

from __future__ import annotations

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

__all__ = ["create_straight_module", "straight_engineering_parameters"]


def straight_engineering_parameters(params: Any, derived: Any) -> Dict[str, Any]:
    return {
        "length_mm": params.length_mm,
        "width_mm": params.width_mm,
        "height_mm": params.height_mm,
        "roller_diameter_mm": params.roller_diameter_mm,
        "roller_spacing_mm": params.roller_spacing_mm,
        "support_spacing_mm": params.support_spacing_mm,
        "side_guard_height_mm": params.side_guard_height_mm,
        "side_guards": params.side_guards,
        "roller_count": derived.roller_count,
        "roller_positions_mm": list(derived.roller_positions_mm),
        "actual_roller_spacing_mm": derived.actual_roller_spacing_mm,
        "support_pair_count": derived.support_pair_count,
        "support_positions_mm": list(derived.support_positions_mm),
    }


def create_straight_module(
    length_mm: float,
    width_mm: float,
    height_mm: float,
    roller_diameter_mm: float,
    roller_spacing_mm: float,
    support_spacing_mm: float,
    side_guard_height_mm: float,
    side_guards: bool,
) -> ConveyorModule:
    """Build an intelligent straight module (validates via legacy engine)."""
    params = _ad.straight_inputs(
        length_mm, width_mm, height_mm, roller_diameter_mm,
        roller_spacing_mm, support_spacing_mm, side_guard_height_mm,
        side_guards,
    )
    derived = _ad.straight_derive(params)
    checks = _ad.straight_verify(params, derived)
    if not checks.get("all"):
        failed = sorted(k for k, v in checks.items() if not v)
        raise ValueError(f"Straight spec invalid, failed: {failed}")
    ports = _ad.straight_ports(params)
    module_id = _ad.straight_signature(params, derived)
    return ConveyorModule(
        module_id=module_id,
        module_type="Straight",
        length=params.length_mm,
        width=params.width_mm,
        height=params.height_mm,
        inlet_port=ConveyorPort.from_legacy_dict(
            f"{module_id}:inlet", {**ports["inlet_port"], "conveyor_type": "Straight"}
        ),
        outlet_port=ConveyorPort.from_legacy_dict(
            f"{module_id}:outlet", {**ports["outlet_port"], "conveyor_type": "Straight"}
        ),
        engineering_parameters=straight_engineering_parameters(params, derived),
        manufacturing_metadata={"signature": module_id, "spec": "Problem Statement A"},
        bom_data=dict(_ad.straight_bom(derived, params.side_guards)),
    )
