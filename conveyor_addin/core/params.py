"""Parameter ranges + structural constants — single source of truth.

Values mirror the proven legacy ``fusion_conveyor_generator.RANGES`` and
``fusion_curve_module.CURVE_RANGES`` exactly (adapter regression tests pin
this). New code imports from here; legacy files keep their own copies until
the adapter migration completes (see ``modules/adapters.py``).
"""

from __future__ import annotations

from typing import Dict, Tuple

__all__ = [
    "RANGES",
    "CURVE_RANGES",
    "RAIL_W",
    "RAIL_H",
    "LEG_L",
    "LEG_W",
    "LEG_SIDE",
    "ROLLER_CLEARANCE",
    "GUARD_THICK",
    "STEEL_DENSITY_KG_M3",
    "ALUMINUM_DENSITY_KG_M3",
    "MODULE_TYPES",
    "validate_param",
]

#: Straight-module spec ranges (mm), Problem Statement A §2.
RANGES: Dict[str, Tuple[float, float]] = {
    "L": (800.0, 2000.0),
    "W": (300.0, 600.0),
    "H": (500.0, 900.0),
    "D": (40.0, 80.0),
    "P": (80.0, 150.0),
    "S": (500.0, 1000.0),
    "G": (0.0, 150.0),
}

#: Curve-module additive ranges (straight RANGES reused for W/H/D/P/S/G).
CURVE_RANGES: Dict[str, Tuple[float, float]] = {
    "Ri": (400.0, 1200.0),
    "Theta": (15.0, 180.0),
}

# --- Structural constants (Fusion User Parameters, reviewer-editable) -------
RAIL_W = 20.0
RAIL_H = 40.0
LEG_L = 40.0
LEG_W = 40.0
LEG_SIDE = LEG_L
ROLLER_CLEARANCE = 10.0
GUARD_THICK = 5.0
STEEL_DENSITY_KG_M3 = 7850.0
ALUMINUM_DENSITY_KG_M3 = 2700.0

#: Supported intelligent module types (OBJECTIVE 1).
MODULE_TYPES = (
    "Straight",
    "Curved",
    "Merge",
    "Transfer",
    "Incline",
    "Custom",
)


def validate_param(key: str, value: float) -> float:
    """Clamp-free strict check: raise ``ValueError`` when out of range."""
    if key not in RANGES:
        raise KeyError(f"Unknown parameter {key!r}; known: {sorted(RANGES)}")
    lo, hi = RANGES[key]
    v = float(value)
    if not (lo <= v <= hi):
        raise ValueError(
            f"Parameter {key}={v}mm out of range [{lo}, {hi}]mm"
        )
    return v
