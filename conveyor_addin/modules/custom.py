"""Custom conveyor module — caller-defined ports (validated right-handed)."""

from __future__ import annotations

from typing import Any, Dict, Optional

try:  # pytest / Add-In dir on sys.path (repo convention)
    from docking.port import ConveyorPort
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.docking.port import ConveyorPort  # type: ignore[no-redef]

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

__all__ = ["create_custom_module"]


def create_custom_module(module_id: str, length_mm: float, width_mm: float,
                         height_mm: float, inlet_port: ConveyorPort,
                         outlet_port: ConveyorPort,
                         engineering_parameters: Optional[Dict[str, Any]] = None,
                         ) -> ConveyorModule:
    """Custom unit: caller-defined ports (both validated before accept)."""
    inlet_port.validate()
    outlet_port.validate()
    return ConveyorModule(
        module_id=module_id, module_type="Custom",
        length=float(length_mm), width=float(width_mm), height=float(height_mm),
        inlet_port=inlet_port, outlet_port=outlet_port,
        engineering_parameters=dict(engineering_parameters or {}),
        manufacturing_metadata={"signature": module_id, "spec": "custom"},
        bom_data={},
    )
