"""Merge conveyor module (port-geometry stub — no CAD builder yet)."""

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
    from modules._port_helpers import straight_port_pair
except ImportError:
    from conveyor_addin.modules._port_helpers import straight_port_pair  # type: ignore[no-redef]

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

__all__ = ["create_merge_module"]


def create_merge_module(length_mm: float, width_mm: float, height_mm: float,
                        roller_pitch_mm: float,
                        branch_angle_deg: float = 30.0) -> ConveyorModule:
    """Merge unit: main inlet + branch inlet, one straight-compatible outlet.

    The branch inlet lives in ``engineering_parameters`` (extra ports beyond
    the mandatory inlet/outlet pair) and carries
    ``connection_rules={"branch": True}`` so the compatibility matrix can
    gate it (see ``docking/connection_rules.py``).
    """
    L = validate_param("L", length_mm)
    W = validate_param("W", width_mm)
    H = validate_param("H", height_mm)
    P = validate_param("P", roller_pitch_mm)
    module_id = f"MERGE_L{L:.0f}_W{W:.0f}_H{H:.0f}_B{branch_angle_deg:.0f}"
    ports = straight_port_pair(module_id, "Merge", L, W, H, P)
    branch_rad = math.radians(branch_angle_deg)
    branch = ConveyorPort(
        id=f"{module_id}:branch", origin=(L * 0.4, 0.0, H),
        direction=(math.cos(branch_rad), math.sin(branch_rad), 0.0),
        lateral_axis=(-math.sin(branch_rad), math.cos(branch_rad), 0.0),
        up=(0.0, 0.0, 1.0), width=W, height=H, roller_pitch=P,
        conveyor_type="Merge",
        connection_rules={"branch": True})
    return ConveyorModule(
        module_id=module_id, module_type="Merge", length=L, width=W, height=H,
        inlet_port=ports["inlet"], outlet_port=ports["outlet"],
        engineering_parameters={"length_mm": L, "width_mm": W, "height_mm": H,
                                "roller_pitch_mm": P,
                                "branch_angle_deg": branch_angle_deg,
                                "branch_inlet_port": branch.to_dict()},
        manufacturing_metadata={"signature": module_id, "spec": "merge-stub"},
        bom_data={},
    )
