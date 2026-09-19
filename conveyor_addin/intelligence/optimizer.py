"""Optimizer — duty-class sizing as DATA (wraps the legacy heuristic).

Returns plain spec dicts. Never touches CAD. Output must still pass
``rules_engine.gate`` before any generator consumes it.
"""

from __future__ import annotations

from typing import Any, Dict

try:
    from modules import adapters as _ad
except ImportError:
    from conveyor_addin.modules import adapters as _ad  # type: ignore[no-redef]

__all__ = ["optimize_spec"]


def optimize_spec(length_mm: float, width_mm: float, height_mm: float,
                  target_load_kg: float, side_guards: bool = True,
                  duty_class: str = "auto") -> Dict[str, Any]:
    """Optimal spec for a target load (legacy heuristic, data only)."""
    legacy = _ad.optimize_inputs(
        target_load_kg=target_load_kg, length_mm=length_mm,
        width_mm=width_mm, height_mm=height_mm,
        side_guards=side_guards, duty_class=duty_class)
    return {
        "length_mm": legacy.length_mm,
        "width_mm": legacy.width_mm,
        "height_mm": legacy.height_mm,
        "roller_diameter_mm": legacy.roller_diameter_mm,
        "roller_spacing_mm": legacy.roller_spacing_mm,
        "support_spacing_mm": legacy.support_spacing_mm,
        "side_guard_height_mm": legacy.side_guard_height_mm,
        "side_guards": legacy.side_guards,
        "cross_bracing": legacy.cross_bracing,
        "target_load_capacity_kg": legacy.target_load_capacity_kg,
        "source": "autonomous_optimize_conveyor",
    }
