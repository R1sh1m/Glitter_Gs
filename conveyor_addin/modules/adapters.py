"""Legacy adapters — wrap (never fork) the proven generators.

``fusion_conveyor_generator`` (straight) and ``fusion_curve_module`` (curve)
remain the ONLY owners of derivation/BOM/port math until the regression
gate (``tests/test_regression_legacy.py``) passes. New ``modules/`` code
calls into them through this module so there is exactly one math path.

Deletion of the root files is FORBIDDEN until that suite is green.
"""

from __future__ import annotations

from typing import Any, Dict

import fusion_conveyor_generator as _fcg
import fusion_curve_module as _fcm

__all__ = [
    "straight_derive",
    "straight_verify",
    "straight_bom",
    "straight_ports",
    "straight_signature",
    "straight_inputs",
    "curve_derive",
    "curve_verify",
    "curve_ports",
    "curve_inputs",
    "optimize_inputs",
    "legacy_ranges",
    "legacy_curve_ranges",
]


def legacy_ranges() -> Dict[str, tuple]:
    return dict(_fcg.RANGES)


def legacy_curve_ranges() -> Dict[str, tuple]:
    return dict(_fcm.CURVE_RANGES)


def straight_inputs(
    length_mm: float,
    width_mm: float,
    height_mm: float,
    roller_diameter_mm: float,
    roller_spacing_mm: float,
    support_spacing_mm: float,
    side_guard_height_mm: float,
    side_guards: bool,
) -> Any:
    return _fcg.ConveyorInput(
        length_mm=length_mm,
        width_mm=width_mm,
        height_mm=height_mm,
        roller_diameter_mm=roller_diameter_mm,
        roller_spacing_mm=roller_spacing_mm,
        support_spacing_mm=support_spacing_mm,
        side_guard_height_mm=side_guard_height_mm,
        side_guards=side_guards,
    )


def straight_derive(params: Any) -> Any:
    return _fcg.derive_configuration(params)


def straight_verify(params: Any, derived: Any = None) -> Dict[str, bool]:
    return _fcg.verify_configuration(params, derived)


def straight_bom(derived: Any, side_guards: bool) -> Dict[str, int]:
    return _fcg.build_bom(derived, side_guards)


def straight_ports(params: Any) -> Dict[str, Dict[str, Any]]:
    return _fcg.get_module_ports(params)


def straight_signature(params: Any, derived: Any = None) -> str:
    return _fcg.deterministic_signature(params, derived)


def curve_inputs(
    inner_radius_mm: float,
    curve_angle_deg: float,
    width_mm: float,
    height_mm: float,
    roller_dia_inner_mm: float,
    roller_pitch_outer_mm: float,
    support_spacing_mm: float,
    side_guard_height_mm: float,
    side_guards: bool,
) -> Any:
    return _fcm.CurveInput(
        inner_radius_mm=inner_radius_mm,
        curve_angle_deg=curve_angle_deg,
        width_mm=width_mm,
        height_mm=height_mm,
        roller_dia_inner_mm=roller_dia_inner_mm,
        roller_pitch_outer_mm=roller_pitch_outer_mm,
        support_spacing_mm=support_spacing_mm,
        side_guard_height_mm=side_guard_height_mm,
        side_guards=side_guards,
    )


def curve_derive(params: Any) -> Any:
    return _fcm.derive_curve_configuration(params)


def curve_verify(params: Any, derived: Any) -> Dict[str, bool]:
    return _fcm.verify_curve_configuration(params, derived)


def curve_ports(params: Any, derived: Any) -> Dict[str, Dict[str, Any]]:
    return _fcm.get_curve_module_ports(params, derived)


def optimize_inputs(
    target_load_kg: float,
    length_mm: float,
    width_mm: float,
    height_mm: float,
    side_guards: bool = True,
    duty_class: str = "auto",
) -> Any:
    """Legacy ``autonomous_optimize_conveyor`` — returns a ConveyorInput.

    Data only (no CAD). Consumed by ``intelligence/optimizer.py``.
    """
    return _fcg.autonomous_optimize_conveyor(
        target_load_kg=target_load_kg,
        length_mm=length_mm,
        width_mm=width_mm,
        height_mm=height_mm,
        side_guards=side_guards,
        duty_class=duty_class,
    )
