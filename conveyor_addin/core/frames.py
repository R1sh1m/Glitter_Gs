"""3D rigid-body math — pure Python, no Fusion dependency, no numpy.

All vectors are ``(x, y, z)`` float tuples in millimetres (positions) or
unitless (directions). Rotation matrices are 3x3 row-major lists.
Conventions per ``Docs/COORDINATE_SYSTEM.md`` §6: ``p' = R·p + t``.
"""

from __future__ import annotations

import math
from typing import List, Tuple

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core.invariants import EPS_ORTHO, EPS_ZERO
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core.invariants import EPS_ORTHO, EPS_ZERO  # type: ignore[no-redef]

try:
    from core.units import mm_to_cm
except ImportError:
    from conveyor_addin.core.units import mm_to_cm  # type: ignore[no-redef]

Vec3 = Tuple[float, float, float]
Mat3 = List[List[float]]

__all__ = [
    "Vec3",
    "Mat3",
    "vadd",
    "vsub",
    "vscale",
    "vdot",
    "vcross",
    "vnorm",
    "vlen",
    "vangle_deg",
    "mat_identity",
    "mat_mul",
    "mat_transpose",
    "mat_vec",
    "mat_det",
    "is_rotation",
    "orthonormal_basis",
    "rot_to_quat_wxyz",
    "quat_to_rot",
    "compose_4x4",
    "apply_transform",
    "to_fusion_cells",
]


def vadd(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vscale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def vdot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vcross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def vlen(a: Vec3) -> float:
    return math.sqrt(vdot(a, a))


def vnorm(a: Vec3) -> Vec3:
    n = vlen(a)
    if n < EPS_ZERO:
        raise ValueError(f"Cannot normalize near-zero vector {a!r}")
    return (a[0] / n, a[1] / n, a[2] / n)


def vangle_deg(a: Vec3, b: Vec3) -> float:
    """Angle between two vectors in degrees (inputs need not be unit)."""
    na, nb = vnorm(a), vnorm(b)
    c = max(-1.0, min(1.0, vdot(na, nb)))
    return math.degrees(math.acos(c))


def mat_identity() -> Mat3:
    return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def mat_mul(a: Mat3, b: Mat3) -> Mat3:
    return [
        [
            a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j]
            for j in range(3)
        ]
        for i in range(3)
    ]


def mat_transpose(m: Mat3) -> Mat3:
    return [[m[j][i] for j in range(3)] for i in range(3)]


def mat_vec(m: Mat3, v: Vec3) -> Vec3:
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def mat_det(m: Mat3) -> float:
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def is_rotation(m: Mat3, tol: float = EPS_ORTHO) -> bool:
    """True when ``m`` is orthonormal with determinant +1 (proper rotation)."""
    mt = mat_transpose(m)
    should_be_identity = mat_mul(mt, m)
    for i in range(3):
        for j in range(3):
            want = 1.0 if i == j else 0.0
            if abs(should_be_identity[i][j] - want) > tol:
                return False
    return abs(mat_det(m) - 1.0) < tol


def orthonormal_basis(direction: Vec3, up: Vec3) -> Mat3:
    """Build right-handed basis columns ``[x=dir, y=z×x, z]`` as row-major R.

    Gram-Schmidt: ``x`` follows flow exactly; ``up`` is orthogonalized so
    incline ports (``direction.z != 0``) still yield a valid frame. Raises
    ``ValueError`` when direction/up are (near-)parallel.
    Returns rows ``[x_row, y_row, z_row]`` so ``R·v`` maps basis coords.
    """
    x = vnorm(direction)
    z_raw = vsub(up, vscale(x, vdot(up, x)))
    if vlen(z_raw) < EPS_ZERO:
        raise ValueError(
            f"direction {direction!r} and up {up!r} are parallel; "
            "cannot build port frame"
        )
    z = vnorm(z_raw)
    y = vcross(z, x)
    return [[x[0], y[0], z[0]], [x[1], y[1], z[1]], [x[2], y[2], z[2]]]


def rot_to_quat_wxyz(m: Mat3) -> Tuple[float, float, float, float]:
    """Rotation matrix -> unit quaternion ``(w, x, y, z)`` (Shepperd)."""
    t = m[0][0] + m[1][1] + m[2][2]
    if t > 0.0:
        s = math.sqrt(t + 1.0) * 2.0
        w = 0.25 * s
        x = (m[2][1] - m[1][2]) / s
        y = (m[0][2] - m[2][0]) / s
        z = (m[1][0] - m[0][1]) / s
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
        w = (m[2][1] - m[1][2]) / s
        x = 0.25 * s
        y = (m[0][1] + m[1][0]) / s
        z = (m[0][2] + m[2][0]) / s
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
        w = (m[0][2] - m[2][0]) / s
        x = (m[0][1] + m[1][0]) / s
        y = 0.25 * s
        z = (m[1][2] + m[2][1]) / s
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
        w = (m[1][0] - m[0][1]) / s
        x = (m[0][2] + m[2][0]) / s
        y = (m[1][2] + m[2][1]) / s
        z = 0.25 * s
    n = math.sqrt(w * w + x * x + y * y + z * z)
    return (w / n, x / n, y / n, z / n)


def quat_to_rot(q: Tuple[float, float, float, float]) -> Mat3:
    """Unit quaternion ``(w, x, y, z)`` -> rotation matrix."""
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z)
    if n < EPS_ZERO:
        raise ValueError("Cannot convert near-zero quaternion to matrix")
    w, x, y, z = w / n, x / n, y / n, z / n
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def compose_4x4(first: List[List[float]], second: List[List[float]]) -> List[List[float]]:
    """Compose homogeneous 4x4 transforms: apply ``first``, then ``second``."""

    def _mul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        return [
            [sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)
        ]

    return _mul(second, first)


def apply_transform(r: Mat3, t: Vec3, pt: Vec3) -> Vec3:
    """Apply rigid transform (mm): ``R·pt + t``."""
    q = mat_vec(r, pt)
    return (q[0] + t[0], q[1] + t[1], q[2] + t[2])


def to_fusion_cells(r: Mat3, t_mm: Vec3) -> List[float]:
    """Pack ``(R, t_mm)`` into 16 ``Matrix3D.setWithArray`` cells (row-major).

    This is the ONLY sanctioned mm->cm packing site besides
    ``core/units.mm_to_cm``. Translation converts mm -> cm; rotation is
    unitless and passes through.
    """
    tx, ty, tz = (mm_to_cm(t_mm[0]), mm_to_cm(t_mm[1]), mm_to_cm(t_mm[2]))
    return [
        r[0][0], r[0][1], r[0][2], tx,
        r[1][0], r[1][1], r[1][2], ty,
        r[2][0], r[2][1], r[2][2], tz,
        0.0, 0.0, 0.0, 1.0,
    ]
