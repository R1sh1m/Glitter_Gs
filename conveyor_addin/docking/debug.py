"""Transform visualization utilities — port axes, docking frames, debug JSON.

Two layers:
  1. Pure-Python (this module, testable offline): compute axis endpoints,
     frame markers, and the ``export_debug_json`` payload.
  2. Fusion presenter (``conveyor_addin.fusion.viz`` — Phase 6): draws the
     computed markers as construction geometry. It is INTENTIONALLY not
     here so this module never imports ``adsk``.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core import frames as _frames
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core import frames as _frames  # type: ignore[no-redef]

try:
    from docking.connection_rules import matrix_to_dict
except ImportError:
    from conveyor_addin.docking.connection_rules import matrix_to_dict  # type: ignore[no-redef]

try:
    from docking.port import ConveyorPort
except ImportError:
    from conveyor_addin.docking.port import ConveyorPort  # type: ignore[no-redef]

try:
    from docking.solver import DockingSolution
except ImportError:
    from conveyor_addin.docking.solver import DockingSolution  # type: ignore[no-redef]

__all__ = [
    "AXIS_LENGTH_DEFAULT_MM",
    "port_axes",
    "frame_markers",
    "debug_payload",
    "export_debug_json",
]

#: Display length for port triad shafts (mm).
AXIS_LENGTH_DEFAULT_MM = 200.0


def port_axes(
    port: ConveyorPort, axis_length_mm: float = AXIS_LENGTH_DEFAULT_MM
) -> Dict[str, List[float]]:
    """Axis endpoints for one port: ``{origin, x_end, y_end, z_end}``."""
    p = port.normalized()
    o = p.origin
    L = float(axis_length_mm)
    return {
        "origin": [o[0], o[1], o[2]],
        "x_end": [o[0] + p.direction[0] * L,
                  o[1] + p.direction[1] * L,
                  o[2] + p.direction[2] * L],
        "y_end": [o[0] + p.lateral_axis[0] * L,
                  o[1] + p.lateral_axis[1] * L,
                  o[2] + p.lateral_axis[2] * L],
        "z_end": [o[0] + p.up[0] * L,
                  o[1] + p.up[1] * L,
                  o[2] + p.up[2] * L],
    }


def frame_markers(
    parent_outlet: ConveyorPort,
    child_inlet: ConveyorPort,
    child_outlet: ConveyorPort | None,
    solution: DockingSolution,
) -> Dict[str, Any]:
    """Pre/post docking frames for viewport overlay or text review."""
    markers = {
        "parent_outlet_axes": port_axes(parent_outlet),
        "child_inlet_axes_local": port_axes(child_inlet),
        "child_inlet_axes_world": port_axes(
            _moved_port(child_inlet, solution)
        ),
    }
    if child_outlet is not None:
        markers["child_outlet_axes_world"] = port_axes(
            _moved_port(child_outlet, solution)
        )
    return markers


def _moved_port(port: ConveyorPort, solution: DockingSolution) -> ConveyorPort:
    import dataclasses

    p = port.normalized()
    return dataclasses.replace(
        p,
        origin=solution.transform_point_mm(p.origin),
        direction=_frames.mat_vec(solution.rotation, p.direction),
        lateral_axis=_frames.mat_vec(solution.rotation, p.lateral_axis),
        up=_frames.mat_vec(solution.rotation, p.up),
    )


def debug_payload(
    parent_outlet: ConveyorPort,
    child_inlet: ConveyorPort,
    solution: DockingSolution,
    checks: List[Tuple[str, bool, str]] | None = None,
    child_outlet: ConveyorPort | None = None,
    world_chain_4x4: List[List[float]] | None = None,
) -> Dict[str, Any]:
    """Full debug bundle (JSON-serializable) for one docking joint."""
    return {
        "schema_version": "1.0",
        "parent_outlet": parent_outlet.to_dict(),
        "child_inlet": child_inlet.to_dict(),
        "child_outlet": child_outlet.to_dict() if child_outlet else None,
        "solution": solution.to_dict(),
        "checks": [
            {"name": n, "passed": b, "message": m} for n, b, m in (checks or [])
        ],
        "frames": frame_markers(parent_outlet, child_inlet, child_outlet, solution),
        "world_chain_4x4": world_chain_4x4,
        "compatibility_matrix": matrix_to_dict(),
    }


def _safe_tag(tag: str) -> str:
    """Windows/posix-safe filename stem (module signatures contain | and =)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", tag).strip("._") or "joint"


def export_debug_json(
    output_dir: str,
    tag: str,
    parent_outlet: ConveyorPort,
    child_inlet: ConveyorPort,
    solution: DockingSolution,
    checks: List[Tuple[str, bool, str]] | None = None,
    child_outlet: ConveyorPort | None = None,
    world_chain_4x4: List[List[float]] | None = None,
) -> str:
    """Write ``{tag}_dock_debug.json``; return absolute path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{_safe_tag(tag)}_dock_debug.json")
    payload = debug_payload(parent_outlet, child_inlet, solution, checks,
                            child_outlet, world_chain_4x4)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    return os.path.abspath(path)
