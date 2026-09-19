"""Immutable engineering tolerances and global constants.

All docking/validation thresholds live here and NOWHERE else. Values are
frozen at import time — mutating them requires a code change + test update,
never a runtime assignment. Intent is documented in
``Docs/COORDINATE_SYSTEM.md`` §7; this module holds the numbers.

Hard-coded ``1.0`` / ``0.5`` tolerances in new ``docking/`` or ``modules/``
code are forbidden — import from here (checked in review; legacy
``fusion_docking_system.py`` keeps its own copies until adapters replace it
and is explicitly excluded from the ban).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Current serialization schema version written by ``core/serialization.py``.
SCHEMA_VERSION: Final[str] = "1.0"

#: Schema versions this codebase can read (older ones migrate, see
#: ``core/serialization.migrate_dict``). ``"0"`` = legacy pre-schema dicts.
READABLE_SCHEMA_VERSIONS: Final[tuple] = ("0", "1.0")

# --- Docking tolerances (mm / deg) -----------------------------------------
#: Carry-surface height agreement, parent vs child (±).
HEIGHT_TOL_MM: Final[float] = 1.0
#: Rail width agreement, parent vs child (±).
WIDTH_TOL_MM: Final[float] = 1.0
#: Flow-direction angular agreement (deg).
DIRECTION_TOL_DEG: Final[float] = 0.5
#: Up-vector angular agreement (deg) — rejects twisted installs.
UP_TOL_DEG: Final[float] = 0.5
#: Slack added to max(parent, child) equivalent pitch for the joint gap.
PITCH_JOINT_SLACK_MM: Final[float] = 10.0
#: Curve roller angular cap (Damon/Interroll ≤5°, see ENGINEERING.md).
MAX_ANGULAR_PITCH_DEG: Final[float] = 5.0
#: Minimum rollers on any module (stability).
MIN_ROLLERS: Final[int] = 2
#: Minimum rollers on a curve module.
MIN_CURVE_ROLLERS: Final[int] = 3

# --- Math epsilons ----------------------------------------------------------
#: Zero-length vector guard.
EPS_ZERO: Final[float] = 1e-12
#: Orthonormality / determinant check tolerance.
EPS_ORTHO: Final[float] = 1e-9
#: Point coincidence tolerance for docked origins (mm).
EPS_COINCIDENT_MM: Final[float] = 1e-6


@dataclass(frozen=True)
class Tolerances:
    """Frozen snapshot of docking tolerances (injectable for tests)."""

    height_tol_mm: float = HEIGHT_TOL_MM
    width_tol_mm: float = WIDTH_TOL_MM
    direction_tol_deg: float = DIRECTION_TOL_DEG
    up_tol_deg: float = UP_TOL_DEG
    pitch_joint_slack_mm: float = PITCH_JOINT_SLACK_MM


#: Default tolerance set used by the solver/validators when none is passed.
DEFAULT_TOLERANCES = Tolerances()


__all__ = [
    "SCHEMA_VERSION",
    "READABLE_SCHEMA_VERSIONS",
    "HEIGHT_TOL_MM",
    "WIDTH_TOL_MM",
    "DIRECTION_TOL_DEG",
    "UP_TOL_DEG",
    "PITCH_JOINT_SLACK_MM",
    "MAX_ANGULAR_PITCH_DEG",
    "MIN_ROLLERS",
    "MIN_CURVE_ROLLERS",
    "EPS_ZERO",
    "EPS_ORTHO",
    "EPS_COINCIDENT_MM",
    "Tolerances",
    "DEFAULT_TOLERANCES",
]
