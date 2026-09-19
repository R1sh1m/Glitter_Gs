"""Strict units layer — the ONLY place mm<->cm and deg<->rad convert.

BACKGROUND
----------
Fusion 360 database units are centimetres (length) and radians (angle)
while all engineering math in this platform is millimetres / degrees
(``Docs/COORDINATE_SYSTEM.md`` §1). The legacy codebase scattered raw
``/ 10.0`` / ``* 10.0`` conversions across ~30 call sites (including one
prior 10x double-conversion bug: 1400mm read back as 14000mm). This module
is the single choke point for every conversion.

RULES
-----
1. New code in ``core/``, ``docking/``, ``modules/`` MUST NOT contain raw
   ``/ 10``, ``* 10``, ``/10.0`` length conversions or ``convert(`` calls.
   Import from here instead (enforced by ``tests/test_units_strict.py``).
2. Prefer the ``Length`` / ``Angle`` value types at API boundaries so unit
   mistakes become ``TypeError`` instead of silent 10x geometry errors.
3. Plain ``float`` millimetre values are still accepted everywhere for
   adapter compatibility — the types are guardrails, not walls.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Exact scale factors. NOTE: these constants may only be *used* here.
MM_PER_CM = 10.0
DEG_PER_RAD = 57.29577951308232  # 180 / pi, spelled out (Fusion exprs lack pi)

__all__ = [
    "MM_PER_CM",
    "DEG_PER_RAD",
    "Length",
    "Angle",
    "mm_to_cm",
    "cm_to_mm",
    "deg_to_rad",
    "rad_to_deg",
    "fusion_length_to_mm",
    "mm_to_fusion_length",
    "fusion_angle_to_deg",
    "deg_to_fusion_angle",
    "evaluate_to_mm",
    "evaluate_to_deg",
]


@dataclass(frozen=True)
class Length:
    """Immutable length value. Canonical unit: millimetres."""

    mm: float

    def __post_init__(self) -> None:
        if not isinstance(self.mm, (int, float)):
            raise TypeError(f"Length.mm must be numeric, got {type(self.mm)!r}")

    @staticmethod
    def from_mm(value: float) -> "Length":
        return Length(mm=float(value))

    @staticmethod
    def from_cm(value: float) -> "Length":
        return Length(mm=float(value) * MM_PER_CM)

    def to_mm(self) -> float:
        return float(self.mm)

    def to_cm(self) -> float:
        return float(self.mm) / MM_PER_CM

    def __add__(self, other: "Length") -> "Length":
        if not isinstance(other, Length):
            raise TypeError("Can only add Length to Length")
        return Length(mm=self.mm + other.mm)

    def __sub__(self, other: "Length") -> "Length":
        if not isinstance(other, Length):
            raise TypeError("Can only subtract Length from Length")
        return Length(mm=self.mm - other.mm)


@dataclass(frozen=True)
class Angle:
    """Immutable angle value. Canonical unit: degrees."""

    deg: float

    def __post_init__(self) -> None:
        if not isinstance(self.deg, (int, float)):
            raise TypeError(f"Angle.deg must be numeric, got {type(self.deg)!r}")

    @staticmethod
    def from_deg(value: float) -> "Angle":
        return Angle(deg=float(value))

    @staticmethod
    def from_rad(value: float) -> "Angle":
        return Angle(deg=float(value) * DEG_PER_RAD)

    def to_deg(self) -> float:
        return float(self.deg)

    def to_rad(self) -> float:
        return float(self.deg) / DEG_PER_RAD


# ---------------------------------------------------------------------------
# Scalar conversions (the only sanctioned arithmetic)
# ---------------------------------------------------------------------------

def mm_to_cm(value_mm: float) -> float:
    """Millimetres -> Fusion database centimetres."""
    return float(value_mm) / MM_PER_CM


def cm_to_mm(value_cm: float) -> float:
    """Fusion database centimetres -> millimetres."""
    return float(value_cm) * MM_PER_CM


def deg_to_rad(value_deg: float) -> float:
    """Degrees -> radians."""
    return float(value_deg) / DEG_PER_RAD


def rad_to_deg(value_rad: float) -> float:
    """Radians -> degrees."""
    return float(value_rad) * DEG_PER_RAD


# ---------------------------------------------------------------------------
# Fusion boundary helpers
# ---------------------------------------------------------------------------

def fusion_length_to_mm(raw_value: float, from_unit: str = "cm") -> float:
    """Convert a raw Fusion ``evaluateExpression`` length to mm.

    ``from_unit`` is the unit requested in the ``evaluateExpression`` call
    (``"cm"`` internal default or ``"mm"``). A value already in mm passes
    through unchanged — this makes double-conversion (the historic
    1400 -> 14000 bug) impossible when callers route through here.
    """
    raw = float(raw_value)
    if from_unit == "mm":
        return raw
    if from_unit == "cm":
        return cm_to_mm(raw)
    raise ValueError(f"Unsupported length unit {from_unit!r}; use 'mm' or 'cm'")


def mm_to_fusion_length(value_mm: float) -> float:
    """Millimetres -> Fusion database centimetres (for raw Point3D coords)."""
    return mm_to_cm(value_mm)


def fusion_angle_to_deg(raw_value: float, from_unit: str = "rad") -> float:
    """Convert a raw Fusion ``evaluateExpression`` angle to degrees."""
    raw = float(raw_value)
    if from_unit == "deg":
        return raw
    if from_unit == "rad":
        return rad_to_deg(raw)
    raise ValueError(f"Unsupported angle unit {from_unit!r}; use 'deg' or 'rad'")


def deg_to_fusion_angle(value_deg: float) -> float:
    """Degrees -> Fusion database radians."""
    return deg_to_rad(value_deg)


def evaluate_to_mm(units_manager, expression: str) -> float:
    """Evaluate a Fusion length expression and return millimetres.

    Uses the units-manager ``convert`` exactly once (cm -> mm). Falls back
    to ``* MM_PER_CM`` when ``convert`` is unavailable (old builds / mocks).
    ``units_manager`` may be ``None`` outside Fusion — then the expression
    must already be a plain number in mm.
    """
    if units_manager is None:
        return float(expression)  # already mm by contract
    raw = float(units_manager.evaluateExpression(expression, "cm"))
    try:
        convert = getattr(units_manager, "convert", None)
        if callable(convert):
            return float(convert(raw, "cm", "mm"))
    except Exception:
        pass
    return cm_to_mm(raw)


def evaluate_to_deg(units_manager, expression: str) -> float:
    """Evaluate a Fusion angle expression and return degrees (single convert)."""
    if units_manager is None:
        return float(expression)  # already deg by contract
    raw = float(units_manager.evaluateExpression(expression, "rad"))
    try:
        convert = getattr(units_manager, "convert", None)
        if callable(convert):
            return float(convert(raw, "rad", "deg"))
    except Exception:
        pass
    return rad_to_deg(raw)
