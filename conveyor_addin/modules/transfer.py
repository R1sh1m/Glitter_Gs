"""Transfer conveyor module (port-geometry stub — no CAD builder yet)."""

from __future__ import annotations

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core.params import validate_param
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core.params import validate_param  # type: ignore[no-redef]

try:
    from modules._port_helpers import straight_port_pair
except ImportError:
    from conveyor_addin.modules._port_helpers import straight_port_pair  # type: ignore[no-redef]

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

__all__ = ["create_transfer_module"]


def create_transfer_module(length_mm: float, width_mm: float, height_mm: float,
                           roller_pitch_mm: float) -> ConveyorModule:
    """Transfer unit: a short straight (L <= 800) with Transfer typing."""
    L = float(length_mm)
    if L > 800.0:
        raise ValueError(f"Transfer length must be <= 800mm, got {L}")
    W = validate_param("W", width_mm)
    H = validate_param("H", height_mm)
    P = validate_param("P", roller_pitch_mm)
    module_id = f"TRANSFER_L{L:.0f}_W{W:.0f}_H{H:.0f}"
    ports = straight_port_pair(module_id, "Transfer", L, W, H, P)
    return ConveyorModule(
        module_id=module_id, module_type="Transfer", length=L, width=W, height=H,
        inlet_port=ports["inlet"], outlet_port=ports["outlet"],
        engineering_parameters={"length_mm": L, "width_mm": W, "height_mm": H,
                                "roller_pitch_mm": P},
        manufacturing_metadata={"signature": module_id, "spec": "transfer-stub"},
        bom_data={},
    )
