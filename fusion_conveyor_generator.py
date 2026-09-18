from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

try:
    import adsk.core  # type: ignore
    import adsk.fusion  # type: ignore
except ImportError:  # pragma: no cover - allows unit tests outside Fusion
    adsk = None


@dataclass(frozen=True)
class ConveyorInput:
    length_mm: float
    width_mm: float
    height_mm: float
    roller_diameter_mm: float
    roller_spacing_mm: float
    support_spacing_mm: float
    side_guard_height_mm: float
    side_guards: bool


@dataclass(frozen=True)
class ConveyorDerived:
    roller_count: int
    roller_positions_mm: Tuple[float, ...]
    actual_roller_spacing_mm: float
    support_pair_count: int
    support_positions_mm: Tuple[float, ...]
    actual_support_spacing_mm: float
    overall_length_mm: float
    overall_width_mm: float
    overall_height_mm: float


def _compute_repeated_positions(total_length_mm: float, max_spacing_mm: float, edge_offset_mm: float) -> Tuple[Tuple[float, ...], float]:
    start = edge_offset_mm
    end = total_length_mm - edge_offset_mm
    span = end - start
    if span < 0:
        raise ValueError("Invalid span computed for repeated positions.")
    if span <= max_spacing_mm:
        positions = (start, end) if span > 1e-9 else (start,)
        spacing = span if len(positions) > 1 else 0.0
        return positions, spacing

    interval_count = max(math.ceil(span / max_spacing_mm), 1)
    count = interval_count + 1
    spacing = span / interval_count
    positions = tuple(start + i * spacing for i in range(count))
    return positions, spacing


def validate_inputs(params: ConveyorInput) -> None:
    if not (800.0 <= params.length_mm <= 2000.0):
        raise ValueError("length_mm must be within 800-2000 mm.")
    if not (300.0 <= params.width_mm <= 600.0):
        raise ValueError("width_mm must be within 300-600 mm.")
    if not (500.0 <= params.height_mm <= 900.0):
        raise ValueError("height_mm must be within 500-900 mm.")
    if not (40.0 <= params.roller_diameter_mm <= 80.0):
        raise ValueError("roller_diameter_mm must be within 40-80 mm.")
    if not (80.0 <= params.roller_spacing_mm <= 150.0):
        raise ValueError("roller_spacing_mm must be within 80-150 mm.")
    if not (500.0 <= params.support_spacing_mm <= 1000.0):
        raise ValueError("support_spacing_mm must be within 500-1000 mm.")
    if not (0.0 <= params.side_guard_height_mm <= 150.0):
        raise ValueError("side_guard_height_mm must be within 0-150 mm.")
    if not params.side_guards and params.side_guard_height_mm > 1e-9:
        raise ValueError("side_guard_height_mm must be 0 when side_guards is False.")


def derive_configuration(params: ConveyorInput) -> ConveyorDerived:
    validate_inputs(params)

    roller_positions, roller_spacing = _compute_repeated_positions(
        total_length_mm=params.length_mm,
        max_spacing_mm=params.roller_spacing_mm,
        edge_offset_mm=params.roller_diameter_mm / 2.0,
    )
    support_positions, support_spacing = _compute_repeated_positions(
        total_length_mm=params.length_mm,
        max_spacing_mm=params.support_spacing_mm,
        edge_offset_mm=0.0,
    )
    effective_guard_height = params.side_guard_height_mm if params.side_guards else 0.0

    return ConveyorDerived(
        roller_count=len(roller_positions),
        roller_positions_mm=roller_positions,
        actual_roller_spacing_mm=roller_spacing,
        support_pair_count=len(support_positions),
        support_positions_mm=support_positions,
        actual_support_spacing_mm=support_spacing,
        overall_length_mm=params.length_mm,
        overall_width_mm=params.width_mm,
        overall_height_mm=params.height_mm + effective_guard_height,
    )


def verify_configuration(params: ConveyorInput, derived: Optional[ConveyorDerived] = None, tol: float = 1e-6) -> Dict[str, bool]:
    d = derived or derive_configuration(params)
    checks = {
        "overall_length": abs(d.overall_length_mm - params.length_mm) <= tol,
        "overall_width": abs(d.overall_width_mm - params.width_mm) <= tol,
        "roller_spacing_limit": d.actual_roller_spacing_mm <= params.roller_spacing_mm + tol,
        "support_spacing_limit": d.actual_support_spacing_mm <= params.support_spacing_mm + tol,
        "roller_count_matches_positions": d.roller_count == len(d.roller_positions_mm),
        "support_count_matches_positions": d.support_pair_count == len(d.support_positions_mm),
        "roller_positions_in_range": all(0.0 - tol <= x <= params.length_mm + tol for x in d.roller_positions_mm),
        "support_positions_in_range": all(0.0 - tol <= x <= params.length_mm + tol for x in d.support_positions_mm),
        "guard_feature_consistency": (params.side_guards and params.side_guard_height_mm >= 0.0) or (
            not params.side_guards and abs(params.side_guard_height_mm) <= tol
        ),
    }
    checks["all"] = all(checks.values())
    return checks


def build_bom(derived: ConveyorDerived, side_guards: bool) -> Dict[str, int]:
    return {
        "frame_side_rails": 2,
        "frame_cross_members": 2,
        "rollers": derived.roller_count,
        "support_leg_pairs": derived.support_pair_count,
        "support_legs_total": derived.support_pair_count * 2,
        "side_guards": 2 if side_guards else 0,
    }


def deterministic_signature(params: ConveyorInput, derived: Optional[ConveyorDerived] = None) -> str:
    d = derived or derive_configuration(params)
    roller_pos = ",".join(f"{p:.4f}" for p in d.roller_positions_mm)
    support_pos = ",".join(f"{p:.4f}" for p in d.support_positions_mm)
    return "|".join(
        [
            f"L={params.length_mm:.4f}",
            f"W={params.width_mm:.4f}",
            f"H={params.height_mm:.4f}",
            f"D={params.roller_diameter_mm:.4f}",
            f"P={params.roller_spacing_mm:.4f}",
            f"S={params.support_spacing_mm:.4f}",
            f"G={params.side_guard_height_mm:.4f}",
            f"guards={int(params.side_guards)}",
            f"rollers={d.roller_count}",
            f"supports={d.support_pair_count}",
            f"rpos={roller_pos}",
            f"spos={support_pos}",
        ]
    )


def summarize_configuration(params: ConveyorInput) -> Dict[str, object]:
    derived = derive_configuration(params)
    checks = verify_configuration(params, derived)
    if not checks["all"]:
        raise ValueError(f"Validation failed: {checks}")
    return {
        "inputs": params,
        "derived": derived,
        "bom": build_bom(derived, params.side_guards),
        "verification": checks,
        "signature": deterministic_signature(params, derived),
    }


def demo_configurations() -> Dict[str, ConveyorInput]:
    return {
        "C1_compact_no_guards": ConveyorInput(
            length_mm=900.0,
            width_mm=350.0,
            height_mm=520.0,
            roller_diameter_mm=45.0,
            roller_spacing_mm=100.0,
            support_spacing_mm=600.0,
            side_guard_height_mm=0.0,
            side_guards=False,
        ),
        "C2_medium_with_guards": ConveyorInput(
            length_mm=1400.0,
            width_mm=450.0,
            height_mm=700.0,
            roller_diameter_mm=60.0,
            roller_spacing_mm=120.0,
            support_spacing_mm=700.0,
            side_guard_height_mm=75.0,
            side_guards=True,
        ),
        "C3_long_with_guards": ConveyorInput(
            length_mm=1950.0,
            width_mm=580.0,
            height_mm=880.0,
            roller_diameter_mm=80.0,
            roller_spacing_mm=145.0,
            support_spacing_mm=950.0,
            side_guard_height_mm=120.0,
            side_guards=True,
        ),
    }


def generate_three_configurations() -> Dict[str, Dict[str, object]]:
    return {name: summarize_configuration(cfg) for name, cfg in demo_configurations().items()}


class FusionConveyorGenerator:
    def __init__(self, app: "adsk.core.Application"):
        self.app = app
        self.ui = app.userInterface
        self.design = adsk.fusion.Design.cast(app.activeProduct)
        if not self.design:
            raise RuntimeError("Active product must be a Fusion design.")
        self.root = self.design.rootComponent

    @staticmethod
    def _mm(value_mm: float) -> "adsk.core.ValueInput":
        return adsk.core.ValueInput.createByReal(value_mm / 10.0)

    @staticmethod
    def _point_mm(x_mm: float, y_mm: float, z_mm: float = 0.0) -> "adsk.core.Point3D":
        return adsk.core.Point3D.create(x_mm / 10.0, y_mm / 10.0, z_mm / 10.0)

    def _delete_stale(self) -> None:
        stale_occurrences = [
            occ
            for occ in self.root.occurrences
            if (occ.component and occ.component.name.startswith("GG_")) or occ.name.startswith("GG_")
        ]
        for occ in stale_occurrences:
            occ.deleteMe()

    def _new_component(
        self,
        name: str,
        x_mm: float,
        y_mm: float = 0.0,
        z_mm: float = 0.0,
        parent: Optional["adsk.fusion.Component"] = None,
    ) -> Tuple["adsk.fusion.Component", "adsk.fusion.Occurrence"]:
        owner = parent if parent is not None else self.root
        transform = adsk.core.Matrix3D.create()
        transform.translation = adsk.core.Vector3D.create(x_mm / 10.0, y_mm / 10.0, z_mm / 10.0)
        occurrence = owner.occurrences.addNewComponent(transform)
        component = occurrence.component
        component.name = name
        occurrence.name = name
        return component, occurrence

    def _create_box(
        self,
        component: "adsk.fusion.Component",
        x_mm: float,
        y_mm: float,
        width_x_mm: float,
        width_y_mm: float,
        height_z_mm: float,
    ) -> None:
        sketch = component.sketches.add(component.xYConstructionPlane)
        lines = sketch.sketchCurves.sketchLines
        p0 = self._point_mm(x_mm, y_mm)
        p1 = self._point_mm(x_mm + width_x_mm, y_mm + width_y_mm)
        lines.addTwoPointRectangle(p0, p1)
        profile = sketch.profiles.item(0)
        extrudes = component.features.extrudeFeatures
        ext_input = extrudes.createInput(profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_input.setDistanceExtent(False, self._mm(height_z_mm))
        extrudes.add(ext_input)

    def _create_roller_body(
        self,
        component: "adsk.fusion.Component",
        roller_radius_mm: float,
        roller_width_mm: float,
    ) -> None:
        sketch = component.sketches.add(component.xZConstructionPlane)
        sketch.sketchCurves.sketchCircles.addByCenterRadius(self._point_mm(0.0, 0.0, 0.0), roller_radius_mm / 10.0)
        profile = sketch.profiles.item(0)
        extrudes = component.features.extrudeFeatures
        ext_input = extrudes.createInput(profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_input.setDistanceExtent(False, self._mm(roller_width_mm))
        extrudes.add(ext_input)

    def _build_frame(self, module_component: "adsk.fusion.Component", params: ConveyorInput) -> None:
        rail_thickness = max(20.0, params.roller_diameter_mm * 0.35)
        rail_height = max(45.0, params.roller_diameter_mm * 0.8)
        frame_component, _ = self._new_component("GG_Frame", 0.0, 0.0, params.height_mm - rail_height, parent=module_component)

        self._create_box(frame_component, 0.0, -params.width_mm / 2.0, params.length_mm, rail_thickness, rail_height)
        self._create_box(
            frame_component,
            0.0,
            params.width_mm / 2.0 - rail_thickness,
            params.length_mm,
            rail_thickness,
            rail_height,
        )
        self._create_box(frame_component, 0.0, -params.width_mm / 2.0, rail_thickness, params.width_mm, rail_height)
        self._create_box(
            frame_component,
            params.length_mm - rail_thickness,
            -params.width_mm / 2.0,
            rail_thickness,
            params.width_mm,
            rail_height,
        )

    def _build_rollers(self, module_component: "adsk.fusion.Component", params: ConveyorInput, derived: ConveyorDerived) -> None:
        roller_radius = params.roller_diameter_mm / 2.0
        for idx, x_pos in enumerate(derived.roller_positions_mm):
            roller_component, _ = self._new_component(
                f"GG_Roller_{idx + 1:03d}",
                x_pos,
                -params.width_mm / 2.0,
                params.height_mm + roller_radius,
                parent=module_component,
            )
            self._create_roller_body(roller_component, roller_radius, params.width_mm)

    def _build_supports(self, module_component: "adsk.fusion.Component", params: ConveyorInput, derived: ConveyorDerived) -> None:
        leg_size = 40.0
        y_offset = params.width_mm / 2.0 - leg_size
        for idx, x_pos in enumerate(derived.support_positions_mm):
            left_component, _ = self._new_component(
                f"GG_Support_L_{idx + 1:03d}",
                x_pos - leg_size / 2.0,
                -y_offset - leg_size,
                0.0,
                parent=module_component,
            )
            right_component, _ = self._new_component(
                f"GG_Support_R_{idx + 1:03d}",
                x_pos - leg_size / 2.0,
                y_offset,
                0.0,
                parent=module_component,
            )
            self._create_box(left_component, 0.0, 0.0, leg_size, leg_size, params.height_mm)
            self._create_box(right_component, 0.0, 0.0, leg_size, leg_size, params.height_mm)

    def _build_side_guards(self, module_component: "adsk.fusion.Component", params: ConveyorInput) -> None:
        if not params.side_guards or params.side_guard_height_mm <= 0.0:
            return
        guard_thickness = 5.0
        z_origin = params.height_mm
        left_component, _ = self._new_component(
            "GG_SideGuard_Left",
            0.0,
            -params.width_mm / 2.0 - guard_thickness,
            z_origin,
            parent=module_component,
        )
        right_component, _ = self._new_component(
            "GG_SideGuard_Right",
            0.0,
            params.width_mm / 2.0,
            z_origin,
            parent=module_component,
        )
        self._create_box(left_component, 0.0, 0.0, params.length_mm, guard_thickness, params.side_guard_height_mm)
        self._create_box(right_component, 0.0, 0.0, params.length_mm, guard_thickness, params.side_guard_height_mm)

    def generate(self, params: ConveyorInput) -> Dict[str, object]:
        summary = summarize_configuration(params)
        self._delete_stale()
        module_component, _ = self._new_component("GG_ConveyorModule", 0.0, 0.0, 0.0)
        derived = summary["derived"]

        self._build_frame(module_component, params)
        self._build_rollers(module_component, params, derived)
        self._build_supports(module_component, params, derived)
        self._build_side_guards(module_component, params)
        return summary


def _to_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"yes", "y", "true", "1"}:
        return True
    if normalized in {"no", "n", "false", "0"}:
        return False
    raise ValueError("side_guards must be Yes/No.")


def _parse_csv_input(raw_csv: str) -> ConveyorInput:
    parts = [part.strip() for part in raw_csv.split(",")]
    if len(parts) != 8:
        raise ValueError("Expected 8 comma-separated values: L,W,H,D,P,S,G,side_guards")
    return ConveyorInput(
        length_mm=float(parts[0]),
        width_mm=float(parts[1]),
        height_mm=float(parts[2]),
        roller_diameter_mm=float(parts[3]),
        roller_spacing_mm=float(parts[4]),
        support_spacing_mm=float(parts[5]),
        side_guard_height_mm=float(parts[6]),
        side_guards=_to_bool(parts[7]),
    )


def run(context):
    if adsk is None:
        raise RuntimeError("This script must be executed inside Autodesk Fusion.")

    app = adsk.core.Application.get()
    ui = app.userInterface
    default = demo_configurations()["C2_medium_with_guards"]
    try:
        generator = FusionConveyorGenerator(app)
        prompt = (
            "Enter conveyor config: "
            "L,W,H,D,P,S,G,side_guards(Yes/No)\n"
            "Example: 1400,450,700,60,120,700,75,Yes"
        )
        default_text = (
            f"{default.length_mm:.0f},{default.width_mm:.0f},{default.height_mm:.0f},"
            f"{default.roller_diameter_mm:.0f},{default.roller_spacing_mm:.0f},"
            f"{default.support_spacing_mm:.0f},{default.side_guard_height_mm:.0f},"
            f"{'Yes' if default.side_guards else 'No'}"
        )
        text, cancelled = ui.inputBox(prompt, "Roller Conveyor Configuration", default_text)
        if cancelled:
            return

        params = _parse_csv_input(text)
        summary = generator.generate(params)
        derived = summary["derived"]
        bom = summary["bom"]
        ui.messageBox(
            "Generated adjustable roller conveyor\n"
            f"LxW: {params.length_mm:.1f} x {params.width_mm:.1f} mm\n"
            f"Frame height: {params.height_mm:.1f} mm\n"
            f"Rollers: {derived.roller_count} @ {derived.actual_roller_spacing_mm:.2f} mm\n"
            f"Support leg pairs: {derived.support_pair_count} @ {derived.actual_support_spacing_mm:.2f} mm\n"
            f"Side guards: {'Yes' if params.side_guards else 'No'}\n"
            f"BOM: {bom}"
        )
    except Exception as exc:
        ui.messageBox(f"Failed: {exc}")


def stop(context):
    return
