"""Fusion occurrence applier — the ONLY docking module that touches ``adsk``.

All math arrives as a solved ``DockingSolution``; this module only packs
cells (via ``core/frames.to_fusion_cells``) and assigns
``occurrence.transform``. Returns ``False`` (never raises) when Fusion is
absent so offline/layout code paths stay safe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core import frames as _frames
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core import frames as _frames  # type: ignore[no-redef]

try:
    from docking.solver import DockingSolution
except ImportError:
    from conveyor_addin.docking.solver import DockingSolution  # type: ignore[no-redef]

if TYPE_CHECKING:  # type-checkers only
    import adsk.core  # type: ignore
    import adsk.fusion  # type: ignore

try:
    import adsk.core  # type: ignore
    import adsk.fusion  # type: ignore
    _HAS_ADSK = True
except ImportError:
    adsk = None  # type: ignore
    _HAS_ADSK = False

__all__ = ["HAS_ADSK", "to_fusion_matrix", "apply_solution_to_occurrence"]

HAS_ADSK = _HAS_ADSK


def to_fusion_matrix(solution: DockingSolution) -> "adsk.core.Matrix3D":
    """Pack a solved transform into a Fusion ``Matrix3D`` (mm -> cm inside)."""
    if not _HAS_ADSK:
        raise RuntimeError("Autodesk Fusion is required to create Matrix3D.")
    mat = adsk.core.Matrix3D.create()
    mat.setWithArray(
        _frames.to_fusion_cells(solution.rotation, solution.translation_mm)
    )
    return mat


def apply_solution_to_occurrence(occurrence: Any, solution: DockingSolution) -> bool:
    """Assign the solved transform to a Fusion occurrence (False offline)."""
    if not _HAS_ADSK or occurrence is None:
        return False
    try:
        occurrence.transform = to_fusion_matrix(solution)
        return True
    except Exception:
        return False
