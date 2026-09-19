"""Incline conveyor module (port-geometry stub — no CAD builder yet)."""

from __future__ import annotations

import math

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core.params import validate_param
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core.params import validate_param  # type: ignore[no-redef]

try:
    from docking.port import ConveyorPort
except ImportError:
    from conveyor_addin.docking.port import ConveyorPort  # type: ignore[no-redef]

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

__all__ = ["create_incline_module"]


def create_incline_module(length_mm: float, width_mm: float,
                          height_in_mm: float, rise_mm: float,
                          roller_pitch_mm: float) -> ConveyorModule:
    """Incline unit: tilted flow ``x=(cos a, 0, sin a)`` (COORD §4.3).

    The case the legacy yaw-only solver could never handle — the 6-DOF
    solver orthogonalizes ``up`` via Gram-Schmidt (``frames``).
    """
    L = validate_param("L", length_mm)
    W = validate_param("W", width_mm)
    H = validate_param("H", height_in_mm)
    P = validate_param("P", roller_pitch_mm)
    if not 0 < rise_mm < L:
        raise ValueError(f"Incline rise must satisfy 0 < rise < L, got {rise_mm}")
    alpha = math.asin(rise_mm / L)
    run = L * math.cos(alpha)
    module_id = f"INCLINE_L{L:.0f}_W{W:.0f}_H{H:.0f}_R{rise_mm:.0f}"
    direction = (math.cos(alpha), 0.0, math.sin(alpha))
    inlet = ConveyorPort(
        id=f"{module_id}:inlet", origin=(0.0, W / 2.0, H),
        direction=direction, lateral_axis=(0.0, 1.0, 0.0),
        up=(0.0, 0.0, 1.0), width=W, height=H, roller_pitch=P,
        conveyor_type="Incline")
    outlet = ConveyorPort(
        id=f"{module_id}:outlet", origin=(run, W / 2.0, H + rise_mm),
        direction=direction, lateral_axis=(0.0, 1.0, 0.0),
        up=(0.0, 0.0, 1.0), width=W, height=H + rise_mm,
        roller_pitch=P, conveyor_type="Incline")
    return ConveyorModule(
        module_id=module_id, module_type="Incline", length=L, width=W,
        height=H + rise_mm,
        inlet_port=inlet, outlet_port=outlet,
        engineering_parameters={"length_mm": L, "width_mm": W,
                                "height_in_mm": H, "rise_mm": rise_mm,
                                "grade_deg": math.degrees(alpha),
                                "roller_pitch_mm": P},
        manufacturing_metadata={"signature": module_id, "spec": "incline-stub"},
        bom_data={},
    )
