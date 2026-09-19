"""6-DOF docking solver — full orthonormal alignment (NOT yaw-only).

Given parent outlet port A and child inlet port B (both expressed in the
same world frame — parent already placed, child at identity), compute the
rigid ``(R, t)`` with ``B_A = basis(A)``, ``B_B = basis(B)``,
``R = B_A · B_Bᵀ``, ``t = O_A − R·O_B``.

Verifies: ``R·x_B ≈ x_A``, ``R·z_B ≈ z_A``, ``R·O_B + t == O_A``,
``R`` orthonormal with ``det = +1``. Raises ``DockingError`` with the
required correction on any failure. Pure Python — no Fusion dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core import frames as _frames
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core import frames as _frames  # type: ignore[no-redef]

try:
    from core.errors import DockingError
except ImportError:
    from conveyor_addin.core.errors import DockingError  # type: ignore[no-redef]

try:
    from core.invariants import (
        DEFAULT_TOLERANCES,
        EPS_COINCIDENT_MM,
        Tolerances,
    )
except ImportError:
    from conveyor_addin.core.invariants import DEFAULT_TOLERANCES, EPS_COINCIDENT_MM, Tolerances  # type: ignore[no-redef]

try:
    from docking.connection_rules import check_connection_allowed
except ImportError:
    from conveyor_addin.docking.connection_rules import check_connection_allowed  # type: ignore[no-redef]

try:
    from docking.port import ConveyorPort
except ImportError:
    from conveyor_addin.docking.port import ConveyorPort  # type: ignore[no-redef]

__all__ = ["DockingSolution", "DockingSolver"]


@dataclass(frozen=True)
class DockingSolution:
    """Solved rigid placement for the child module (lengths: mm)."""

    rotation: _frames.Mat3
    translation_mm: _frames.Vec3
    quaternion_wxyz: Tuple[float, float, float, float]
    direction_error_deg: float
    up_error_deg: float
    child_inlet_world_mm: _frames.Vec3
    child_outlet_world_mm: _frames.Vec3 | None = None

    @property
    def matrix_4x4(self):
        r, (tx, ty, tz) = self.rotation, self.translation_mm
        return [
            [r[0][0], r[0][1], r[0][2], tx],
            [r[1][0], r[1][1], r[1][2], ty],
            [r[2][0], r[2][1], r[2][2], tz],
            [0.0, 0.0, 0.0, 1.0],
        ]

    def transform_point_mm(self, pt: _frames.Vec3) -> _frames.Vec3:
        return _frames.apply_transform(self.rotation, self.translation_mm, pt)

    def to_dict(self):
        return {
            "rotation_3x3": [list(row) for row in self.rotation],
            "translation_mm": list(self.translation_mm),
            "quaternion_wxyz": list(self.quaternion_wxyz),
            "matrix_4x4": [list(row) for row in self.matrix_4x4],
            "direction_error_deg": self.direction_error_deg,
            "up_error_deg": self.up_error_deg,
            "child_inlet_world_mm": list(self.child_inlet_world_mm),
            "child_outlet_world_mm": (
                list(self.child_outlet_world_mm)
                if self.child_outlet_world_mm is not None
                else None
            ),
        }


class DockingSolver:
    """Stateless 6-DOF docking solver."""

    @staticmethod
    def solve(
        parent_outlet: ConveyorPort,
        child_inlet: ConveyorPort,
        child_outlet: ConveyorPort | None = None,
        tolerances: Tolerances = DEFAULT_TOLERANCES,
    ) -> DockingSolution:
        a = parent_outlet.normalized()
        b = child_inlet.normalized()
        # Reject degenerate / non-right-handed triads before solving.
        # (Roll/pitch/twist misuse arrives here as an inconsistent triad;
        #  pure yaw differences are legitimate and solved, not rejected.)
        try:
            a.validate()
        except ValueError as exc:
            raise DockingError(
                reason="invalid_port",
                message=f"Parent outlet port invalid: {exc}",
                module_a={"port_id": a.id},
                module_b={"port_id": b.id},
            ) from exc
        try:
            b.validate()
        except ValueError as exc:
            raise DockingError(
                reason="invalid_port",
                message=f"Child inlet port invalid: {exc}",
                module_a={"port_id": a.id},
                module_b={"port_id": b.id},
            ) from exc

        allowed, reason = check_connection_allowed(
            a.conveyor_type, b.conveyor_type,
            a.connection_rules, b.connection_rules,
        )
        if not allowed:
            raise DockingError(
                reason="connection_forbidden",
                message=f"{a.conveyor_type} outlet -> {b.conveyor_type} inlet "
                f"forbidden: {reason}",
                module_a={"port_id": a.id, "conveyor_type": a.conveyor_type},
                module_b={"port_id": b.id, "conveyor_type": b.conveyor_type},
                details={"rule": reason},
            )

        try:
            basis_a = a.basis()
            basis_b = b.basis()
        except ValueError as exc:
            raise DockingError(
                reason="invalid_port",
                message=f"Cannot build port frame: {exc}",
                module_a={"port_id": a.id},
                module_b={"port_id": b.id},
            ) from exc

        r = _frames.mat_mul(basis_a, _frames.mat_transpose(basis_b))
        rb_origin = _frames.mat_vec(r, b.origin)
        t = (a.origin[0] - rb_origin[0],
             a.origin[1] - rb_origin[1],
             a.origin[2] - rb_origin[2])

        if not _frames.is_rotation(r):
            raise DockingError(
                reason="invalid_rotation",
                message="Solved matrix is not a proper rotation "
                f"(det={_frames.mat_det(r):.6f})",
                module_a={"port_id": a.id},
                module_b={"port_id": b.id},
            )

        dir_err = _frames.vangle_deg(_frames.mat_vec(r, b.direction), a.direction)
        up_err = _frames.vangle_deg(_frames.mat_vec(r, b.up), a.up)
        if dir_err > tolerances.direction_tol_deg:
            raise DockingError(
                reason="direction_mismatch",
                message=f"Flow direction mismatch {dir_err:.2f}° "
                f"(tolerance {tolerances.direction_tol_deg}°): "
                f"outlet {tuple(round(v, 3) for v in a.direction)} vs "
                f"inlet {tuple(round(v, 3) for v in b.direction)}",
                module_a={"port_id": a.id, "direction": list(a.direction)},
                module_b={"port_id": b.id, "direction": list(b.direction)},
                required_correction=(
                    "rotate child module 180° (opposite-direction docking)"
                    if dir_err > 170.0
                    else f"re-orient child by {dir_err:.2f}°"
                ),
                details={"direction_error_deg": dir_err},
            )
        if up_err > tolerances.up_tol_deg:
            raise DockingError(
                reason="up_mismatch",
                message=f"Up-vector mismatch {up_err:.2f}° "
                f"(tolerance {tolerances.up_tol_deg}°): twisted install",
                module_a={"port_id": a.id},
                module_b={"port_id": b.id},
                required_correction="level child module; check riser heights",
                details={"up_error_deg": up_err},
            )

        inlet_world = _frames.apply_transform(r, t, b.origin)
        residual = _frames.vlen(_frames.vsub(inlet_world, a.origin))
        if residual > EPS_COINCIDENT_MM:
            raise DockingError(  # defensive: construction guarantees ~0
                reason="alignment_failed",
                message=f"Docked inlet misses outlet by {residual:.6f}mm",
                module_a={"port_id": a.id},
                module_b={"port_id": b.id},
                details={"residual_mm": residual},
            )

        outlet_world = None
        if child_outlet is not None:
            outlet_world = _frames.apply_transform(r, t, child_outlet.origin)

        return DockingSolution(
            rotation=r,
            translation_mm=t,
            quaternion_wxyz=_frames.rot_to_quat_wxyz(r),
            direction_error_deg=dir_err,
            up_error_deg=up_err,
            child_inlet_world_mm=inlet_world,
            child_outlet_world_mm=outlet_world,
        )
