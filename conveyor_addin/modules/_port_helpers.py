"""Shared port-geometry helpers for the stub module factories."""

from __future__ import annotations

from typing import Dict

try:  # pytest / Add-In dir on sys.path (repo convention)
    from docking.port import ConveyorPort
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.docking.port import ConveyorPort  # type: ignore[no-redef]

__all__ = ["straight_port_pair"]


def straight_port_pair(module_id: str, module_type: str, L: float, W: float,
                       H: float, P: float) -> Dict[str, ConveyorPort]:
    """Straight-compatible inlet/outlet pair (COORD §4.1)."""
    return {
        "inlet": ConveyorPort(
            id=f"{module_id}:inlet", origin=(0.0, W / 2.0, H),
            direction=(1.0, 0.0, 0.0), lateral_axis=(0.0, 1.0, 0.0),
            up=(0.0, 0.0, 1.0), width=W, height=H, roller_pitch=P,
            conveyor_type=module_type),
        "outlet": ConveyorPort(
            id=f"{module_id}:outlet", origin=(L, W / 2.0, H),
            direction=(1.0, 0.0, 0.0), lateral_axis=(0.0, 1.0, 0.0),
            up=(0.0, 0.0, 1.0), width=W, height=H, roller_pitch=P,
            conveyor_type=module_type),
    }
