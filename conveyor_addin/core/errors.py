"""Structured engineering errors — docking failures carry fixes, not just flags.

Every docking/validation failure raises (or returns, for batch checks)
``DockingError`` with the offending values AND the required correction,
e.g. ``Required correction: +150mm riser module``. Plain ``ValueError``
for engineering failures is forbidden in new code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class DockingError(Exception):
    """Detailed engineering docking failure.

    Attributes:
        reason: short machine-readable code (``"height_mismatch"``,
            ``"width_mismatch"``, ``"direction_mismatch"``,
            ``"up_mismatch"``, ``"pitch_exceeded"``, ``"collision"``,
            ``"connection_forbidden"``, ``"invalid_port"``).
        message: human-readable explanation with values.
        module_a / module_b: ``{"module_id":..., "height_mm":...,
            "width_mm":...}`` snapshots for the report (never CAD handles).
        required_correction: actionable fix string, e.g.
            ``"+150.0mm riser module"``. Empty when no fix is known.
        details: extra numeric context (diffs, angles, limits).
    """

    reason: str
    message: str
    module_a: Dict[str, Any] = field(default_factory=dict)
    module_b: Dict[str, Any] = field(default_factory=dict)
    required_correction: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:  # pragma: no cover - trivial
        base = f"Docking failed: {self.message}"
        if self.required_correction:
            base += f"\nRequired correction: {self.required_correction}"
        return base

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reason": self.reason,
            "message": self.message,
            "module_a": dict(self.module_a),
            "module_b": dict(self.module_b),
            "required_correction": self.required_correction,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ValidationIssue:
    """One non-fatal validation finding (fatal ones raise ``DockingError``)."""

    check: str
    passed: bool
    message: str
    severity: str = "error"  # "error" | "warning"


class PortDefinitionError(ValueError):
    """A port triad is degenerate / non-orthonormal / unnormalizable."""


__all__ = ["DockingError", "ValidationIssue", "PortDefinitionError"]
