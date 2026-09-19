"""Viewport visualization — pure overlay specs + guarded Fusion presenter.

``triad_spec`` / ``joint_markers_spec`` are pure data (tested offline) that
describe port axes and docked frames. ``draw_*`` functions require Fusion
and degrade to ``False`` outside it — the offline debug path is
``docking/debug.export_debug_json``.
"""

from __future__ import annotations

from typing import Any, Dict, List

try:
    import adsk.core  # type: ignore
    _HAS_ADSK = True
except ImportError:
    adsk = None  # type: ignore
    _HAS_ADSK = False

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core import frames as _frames
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core import frames as _frames  # type: ignore[no-redef]

try:
    from docking.debug import AXIS_LENGTH_DEFAULT_MM, port_axes
except ImportError:
    from conveyor_addin.docking.debug import (  # type: ignore[no-redef]
        AXIS_LENGTH_DEFAULT_MM, port_axes)

try:
    from docking.port import ConveyorPort
except ImportError:
    from conveyor_addin.docking.port import ConveyorPort  # type: ignore[no-redef]

try:
    from docking.solver import DockingSolution
except ImportError:
    from conveyor_addin.docking.solver import DockingSolution  # type: ignore[no-redef]

__all__ = ["HAS_ADSK", "triad_spec", "joint_markers_spec",
           "draw_triad", "draw_joint_markers"]


HAS_ADSK = _HAS_ADSK


def triad_spec(port: ConveyorPort,
               axis_length_mm: float = AXIS_LENGTH_DEFAULT_MM) -> Dict[str, Any]:
    """Pure overlay spec: origin + three shaft polylines with CAD colors."""
    axes = port_axes(port, axis_length_mm)
    return {
        "port_id": port.id,
        "origin_mm": axes["origin"],
        "shafts": [
            {"axis": "x/flow", "to_mm": axes["x_end"], "color": "red"},
            {"axis": "y/lateral", "to_mm": axes["y_end"], "color": "green"},
            {"axis": "z/up", "to_mm": axes["z_end"], "color": "blue"},
        ],
    }


def joint_markers_spec(parent_outlet: ConveyorPort, child_inlet: ConveyorPort,
                       solution: DockingSolution) -> Dict[str, Any]:
    """Pure overlay spec for one solved joint (pre/post frames)."""
    moved_inlet_origin = solution.transform_point_mm(child_inlet.origin)
    residual = _frames.vlen(_frames.vsub(moved_inlet_origin,
                                         parent_outlet.origin))
    return {
        "parent_triad": triad_spec(parent_outlet),
        "child_triad_world": triad_spec(_moved(child_inlet, solution)),
        "coincidence_residual_mm": residual,
    }


def _moved(port: ConveyorPort, solution: DockingSolution) -> ConveyorPort:
    import dataclasses

    p = port.normalized()
    return dataclasses.replace(
        p,
        origin=solution.transform_point_mm(p.origin),
        direction=_frames.mat_vec(solution.rotation, p.direction),
        lateral_axis=_frames.mat_vec(solution.rotation, p.lateral_axis),
        up=_frames.mat_vec(solution.rotation, p.up),
    )


def _sketch_lines(sketch, origin_mm: List[float], to_mm: List[float]) -> bool:
    try:
        from core.units import mm_to_cm
    except ImportError:
        from conveyor_addin.core.units import mm_to_cm  # type: ignore[no-redef]
    lines = sketch.sketchCurves.sketchLines
    lines.addByTwoPoints(
        adsk.core.Point3D.create(*(mm_to_cm(v) for v in origin_mm)),
        adsk.core.Point3D.create(*(mm_to_cm(v) for v in to_mm)),
    )
    return True


def draw_triad(sketch, port: ConveyorPort,
               axis_length_mm: float = AXIS_LENGTH_DEFAULT_MM) -> bool:
    """Draw RGB port triad into a Fusion sketch (False outside Fusion)."""
    if not _HAS_ADSK or sketch is None:
        return False
    try:
        spec = triad_spec(port, axis_length_mm)
        for shaft in spec["shafts"]:
            _sketch_lines(sketch, spec["origin_mm"], shaft["to_mm"])
        return True
    except Exception:
        return False


def draw_joint_markers(sketch, parent_outlet: ConveyorPort,
                       child_inlet: ConveyorPort,
                       solution: DockingSolution) -> bool:
    """Draw parent + docked-child triads (False outside Fusion)."""
    if not _HAS_ADSK or sketch is None:
        return False
    try:
        spec = joint_markers_spec(parent_outlet, child_inlet, solution)
        for triad in (spec["parent_triad"], spec["child_triad_world"]):
            for shaft in triad["shafts"]:
                _sketch_lines(sketch, triad["origin_mm"], shaft["to_mm"])
        return True
    except Exception:
        return False
