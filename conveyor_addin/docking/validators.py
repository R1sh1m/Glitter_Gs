"""Engineering docking validators — height/width/pitch/collision gates.

Each validator EITHER returns a passing message OR raises ``DockingError``
with module snapshots and the required correction. ``validate_joint``
runs the full gate suite and returns the list of ``(name, passed, message)``
tuples (legacy-compatible shape) — it raises on the FIRST fatal failure so
callers get the actionable error, not just a False flag.
"""

from __future__ import annotations

from typing import List, Tuple

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core import frames as _frames
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core import frames as _frames  # type: ignore[no-redef]

try:
    from core.errors import DockingError
except ImportError:
    from conveyor_addin.core.errors import DockingError  # type: ignore[no-redef]

try:
    from core.invariants import DEFAULT_TOLERANCES, Tolerances
except ImportError:
    from conveyor_addin.core.invariants import DEFAULT_TOLERANCES, Tolerances  # type: ignore[no-redef]

try:
    from docking.port import ConveyorPort
except ImportError:
    from conveyor_addin.docking.port import ConveyorPort  # type: ignore[no-redef]

__all__ = [
    "equivalent_pitch_mm",
    "check_height",
    "check_width",
    "check_pitch",
    "check_collision_aabb",
    "validate_joint",
]


def equivalent_pitch_mm(port: ConveyorPort, inner_radius_mm: float | None = None) -> float:
    """Centerline-equivalent pitch (``Docs/COORDINATE_SYSTEM.md`` §5).

    Straight-family ports store linear pitch directly. Curved ports store
    outer-arc pitch ``P_outer``; the equivalent centerline pitch is
    ``P_outer · Rc / Ro``. ``inner_radius_mm`` is required for curved ports
    (``Rc = Ri + W/2``, ``Ro = Ri + W``); without it the raw pitch returns.
    """
    if port.conveyor_type != "Curved" or inner_radius_mm is None:
        return float(port.roller_pitch)
    ri = float(inner_radius_mm)
    rc = ri + port.width / 2.0
    ro = ri + port.width
    if ro <= 0:
        return float(port.roller_pitch)
    return float(port.roller_pitch) * rc / ro


def _snap(port: ConveyorPort, module_id: str = "") -> dict:
    return {
        "port_id": port.id,
        "module_id": module_id,
        "conveyor_type": port.conveyor_type,
        "height_mm": port.height,
        "width_mm": port.width,
        "pitch_mm": port.roller_pitch,
    }


def check_height(
    parent_outlet: ConveyorPort,
    child_inlet: ConveyorPort,
    tolerances: Tolerances = DEFAULT_TOLERANCES,
    module_a_id: str = "",
    module_b_id: str = "",
) -> str:
    diff = float(parent_outlet.height) - float(child_inlet.height)
    if abs(diff) <= tolerances.height_tol_mm:
        return (
            f"Parent H={parent_outlet.height:.1f}mm, "
            f"Child H={child_inlet.height:.1f}mm, "
            f"Diff={abs(diff):.2f}mm "
            f"(tolerance <= {tolerances.height_tol_mm:.1f}mm)"
        )
    correction = (
        f"+{abs(diff):.1f}mm riser module"
        if diff > 0
        else f"+{abs(diff):.1f}mm riser under parent"
    )
    raise DockingError(
        reason="height_mismatch",
        message=(
            f"Height mismatch: Module A {parent_outlet.height:.0f}mm vs "
            f"Module B {child_inlet.height:.0f}mm "
            f"(diff {abs(diff):.1f}mm > {tolerances.height_tol_mm:.1f}mm)"
        ),
        module_a=_snap(parent_outlet, module_a_id),
        module_b=_snap(child_inlet, module_b_id),
        required_correction=correction,
        details={"height_diff_mm": diff},
    )


def check_width(
    parent_outlet: ConveyorPort,
    child_inlet: ConveyorPort,
    tolerances: Tolerances = DEFAULT_TOLERANCES,
    module_a_id: str = "",
    module_b_id: str = "",
) -> str:
    diff = abs(float(parent_outlet.width) - float(child_inlet.width))
    if diff <= tolerances.width_tol_mm:
        return (
            f"Parent W={parent_outlet.width:.1f}mm, "
            f"Child W={child_inlet.width:.1f}mm, "
            f"Diff={diff:.2f}mm "
            f"(tolerance <= {tolerances.width_tol_mm:.1f}mm)"
        )
    raise DockingError(
        reason="width_mismatch",
        message=(
            f"Width mismatch: Module A {parent_outlet.width:.0f}mm vs "
            f"Module B {child_inlet.width:.0f}mm "
            f"(diff {diff:.1f}mm > {tolerances.width_tol_mm:.1f}mm)"
        ),
        module_a=_snap(parent_outlet, module_a_id),
        module_b=_snap(child_inlet, module_b_id),
        required_correction=(
            f"standardize on {max(parent_outlet.width, child_inlet.width):.0f}mm "
            "width or add a transition module"
        ),
        details={"width_diff_mm": diff},
    )


def check_pitch(
    parent_outlet: ConveyorPort,
    child_inlet: ConveyorPort,
    tolerances: Tolerances = DEFAULT_TOLERANCES,
    parent_inner_radius_mm: float | None = None,
    child_inner_radius_mm: float | None = None,
    module_a_id: str = "",
    module_b_id: str = "",
) -> str:
    p_p = equivalent_pitch_mm(parent_outlet, parent_inner_radius_mm)
    p_c = equivalent_pitch_mm(child_inlet, child_inner_radius_mm)
    limit = max(p_p, p_c) + tolerances.pitch_joint_slack_mm
    mismatch = abs(p_p - p_c)
    if mismatch <= tolerances.pitch_joint_slack_mm:
        return (
            f"Parent pitch={p_p:.1f}mm, Child pitch={p_c:.1f}mm, "
            f"Joint gap limit <= {limit:.1f}mm"
        )
    # Moderate step: pass with an explicit bridging warning (e.g. the
    # canonical straight P110 -> curve P_eq 90.2 transition). Gross steps
    # fail — small packages would tip into the joint.
    warn_band = 2.0 * tolerances.pitch_joint_slack_mm
    if mismatch <= warn_band:
        return (
            f"WARNING: pitch step {mismatch:.1f}mm "
            f"(parent {p_p:.1f}mm vs child {p_c:.1f}mm); "
            f"verify package bridging across joint (limit {limit:.1f}mm)"
        )
    raise DockingError(
        reason="pitch_exceeded",
        message=(
            f"Roller pitch mismatch {mismatch:.1f}mm exceeds joint slack "
            f"{tolerances.pitch_joint_slack_mm:.1f}mm "
            f"(parent {p_p:.1f}mm vs child {p_c:.1f}mm)"
        ),
        module_a=_snap(parent_outlet, module_a_id),
        module_b=_snap(child_inlet, module_b_id),
        required_correction=(
            f"re-pitch one module to within "
            f"{tolerances.pitch_joint_slack_mm:.0f}mm (joint limit {limit:.1f}mm)"
        ),
        details={"pitch_diff_mm": mismatch, "joint_limit_mm": limit},
    )


def check_collision_aabb(
    a_min: _frames.Vec3,
    a_max: _frames.Vec3,
    b_min: _frames.Vec3,
    b_max: _frames.Vec3,
    clearance_mm: float = 0.0,
) -> str:
    """Axis-aligned footprint overlap gate (Phase-1 conservative check)."""
    overlap = all(
        a_min[i] - clearance_mm < b_max[i] and b_min[i] - clearance_mm < a_max[i]
        for i in range(3)
    )
    if overlap:
        raise DockingError(
            reason="collision",
            message=(
                f"Module footprints overlap (AABB): A={a_min}/{a_max} vs "
                f"B={b_min}/{b_max}"
            ),
            details={"a_min": list(a_min), "a_max": list(a_max),
                     "b_min": list(b_min), "b_max": list(b_max)},
            required_correction="increase spacing or revise layout heading",
        )
    return "No AABB footprint overlap"


def validate_joint(
    parent_outlet: ConveyorPort,
    child_inlet: ConveyorPort,
    tolerances: Tolerances = DEFAULT_TOLERANCES,
    parent_inner_radius_mm: float | None = None,
    child_inner_radius_mm: float | None = None,
    module_a_id: str = "",
    module_b_id: str = "",
) -> List[Tuple[str, bool, str]]:
    """Run height/width/pitch gates; raise on first fatal failure."""
    checks: List[Tuple[str, bool, str]] = [
        ("Carry Surface Height Match",
         True, check_height(parent_outlet, child_inlet, tolerances,
                            module_a_id, module_b_id)),
        ("Rail Width Match",
         True, check_width(parent_outlet, child_inlet, tolerances,
                           module_a_id, module_b_id)),
        ("Pitch Continuity Rule",
         True, check_pitch(parent_outlet, child_inlet, tolerances,
                           parent_inner_radius_mm, child_inner_radius_mm,
                           module_a_id, module_b_id)),
    ]
    return checks
