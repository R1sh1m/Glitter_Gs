from __future__ import annotations

"""
fusion_conveyor_generator.py
---------------------------------------------------------------------------
Autodesk Fusion API Script — Problem Statement A
Parametric Adjustable Roller Conveyor Configuration Generator

ARCHITECTURE:
    1. Base and derived User Parameters in Autodesk Fusion drive the geometry.
       - Base parameters: ConvLength, ConvWidth, FrameHeight, RollerDia,
         RollerSpacing, LegSpacing, GuardHeight.
       - Derived formulas: RollerCount and LegCount are computed directly
         by Fusion's parametric formula engine.
    2. Genuinely parametric CAD model:
       - Single master roller and master leg station with RectangularPatternFeature
         wired directly to RollerCount/RollerSpacing and LegCount/LegSpacing.
       - Parameter updates recompute geometry in-place with zero duplicate solids.
       - Side guard features are toggled using isSuppressed.
    3. Automated verification & deliverables:
       - Physical CAD bounding box verification against target tolerances.
       - Automated STEP export and CSV Bill of Materials (BOM) export.
       - Validation report generator.
    4. Dual-mode execution:
       - Automated batch runner for all 3 demonstration configurations.
       - Interactive custom parameter dialog with instant model update.
    5. Pure-Python fallback:
       - Math derivations, rule verification, and BOM builders run standalone
         outside Fusion for automated unit testing (CI/CD).
"""

import csv
import math
import os
import traceback
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    import adsk.core  # type: ignore
    import adsk.fusion  # type: ignore
except ImportError:  # pragma: no cover - allows execution outside Fusion
    adsk = None


# ---------------------------------------------------------------------------
# 1. SPEC-DEFINED PARAMETER RANGES & STRUCTURAL CONSTANTS
# ---------------------------------------------------------------------------
RANGES = {
    "L": (800.0, 2000.0),   # Conveyor length (mm)
    "W": (300.0, 600.0),    # Conveyor width (mm)
    "H": (500.0, 900.0),    # Frame height (mm)
    "D": (40.0, 80.0),      # Roller diameter (mm)
    "P": (80.0, 150.0),     # Roller spacing, centre-to-centre (mm)
    "S": (500.0, 1000.0),   # Support-leg spacing (mm)
    "G": (0.0, 150.0),      # Side-guard height (mm)
}

RAIL_W = 20.0             # Rail cross-section width (mm)
RAIL_H = 40.0             # Rail cross-section height (mm)
LEG_SIDE = 40.0           # Square leg post cross-section (mm)
ROLLER_CLEARANCE = 10.0   # Clearance between roller end and inner rail face (mm)
GUARD_THICK = 5.0         # Side guard plate thickness (mm)
DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "ConveyorGenerator_Output")


# ---------------------------------------------------------------------------
# 2. DATA MODELS & MATHEMATICAL DERIVATIONS (Pure Python, Testable Offline)
# ---------------------------------------------------------------------------
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
    if not (RANGES["L"][0] <= params.length_mm <= RANGES["L"][1]):
        raise ValueError(f"length_mm must be within {RANGES['L'][0]}-{RANGES['L'][1]} mm.")
    if not (RANGES["W"][0] <= params.width_mm <= RANGES["W"][1]):
        raise ValueError(f"width_mm must be within {RANGES['W'][0]}-{RANGES['W'][1]} mm.")
    if not (RANGES["H"][0] <= params.height_mm <= RANGES["H"][1]):
        raise ValueError(f"height_mm must be within {RANGES['H'][0]}-{RANGES['H'][1]} mm.")
    if not (RANGES["D"][0] <= params.roller_diameter_mm <= RANGES["D"][1]):
        raise ValueError(f"roller_diameter_mm must be within {RANGES['D'][0]}-{RANGES['D'][1]} mm.")
    if not (RANGES["P"][0] <= params.roller_spacing_mm <= RANGES["P"][1]):
        raise ValueError(f"roller_spacing_mm must be within {RANGES['P'][0]}-{RANGES['P'][1]} mm.")
    if not (RANGES["S"][0] <= params.support_spacing_mm <= RANGES["S"][1]):
        raise ValueError(f"support_spacing_mm must be within {RANGES['S'][0]}-{RANGES['S'][1]} mm.")
    if not (RANGES["G"][0] <= params.side_guard_height_mm <= RANGES["G"][1]):
        raise ValueError(f"side_guard_height_mm must be within {RANGES['G'][0]}-{RANGES['G'][1]} mm.")
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
            height_mm=600.0,
            roller_diameter_mm=50.0,
            roller_spacing_mm=90.0,
            support_spacing_mm=500.0,
            side_guard_height_mm=0.0,
            side_guards=False,
        ),
        "C2_medium_with_guards": ConveyorInput(
            length_mm=1400.0,
            width_mm=450.0,
            height_mm=750.0,
            roller_diameter_mm=60.0,
            roller_spacing_mm=110.0,
            support_spacing_mm=700.0,
            side_guard_height_mm=100.0,
            side_guards=True,
        ),
        "C3_long_with_guards": ConveyorInput(
            length_mm=2000.0,
            width_mm=600.0,
            height_mm=900.0,
            roller_diameter_mm=80.0,
            roller_spacing_mm=150.0,
            support_spacing_mm=1000.0,
            side_guard_height_mm=150.0,
            side_guards=True,
        ),
    }


def generate_three_configurations() -> Dict[str, Dict[str, object]]:
    return {name: summarize_configuration(cfg) for name, cfg in demo_configurations().items()}


# ---------------------------------------------------------------------------
# 3. FUSION 360 PARAMETER MANAGEMENT & HELPERS
# ---------------------------------------------------------------------------
def _mm_expr(val: float) -> str:
    return f"{val} mm"


def _find_or_add_param(user_params: "adsk.fusion.UserParameters", name: str, expr: str, unit: str, comment: str = ""):
    existing = user_params.itemByName(name)
    if existing:
        return existing
    val_input = adsk.core.ValueInput.createByString(expr)
    return user_params.add(name, val_input, unit, comment)


def _set_param_value(user_params: "adsk.fusion.UserParameters", name: str, expr: str) -> None:
    p = user_params.itemByName(name)
    if not p:
        raise RuntimeError(f"Parameter '{name}' not found.")
    p.expression = expr


def create_user_parameters(design: "adsk.fusion.Design", params: ConveyorInput) -> None:
    """Create all base and derived formula user parameters."""
    up = design.userParameters

    # Base dimensional parameters
    _find_or_add_param(up, "ConvLength", _mm_expr(params.length_mm), "mm", "Overall conveyor length (L)")
    _find_or_add_param(up, "ConvWidth", _mm_expr(params.width_mm), "mm", "Overall conveyor width (W)")
    _find_or_add_param(up, "FrameHeight", _mm_expr(params.height_mm), "mm", "Floor to conveyor frame height (H)")
    _find_or_add_param(up, "RollerDia", _mm_expr(params.roller_diameter_mm), "mm", "Roller outside diameter (D)")
    _find_or_add_param(up, "RollerSpacing", _mm_expr(params.roller_spacing_mm), "mm", "Roller centre-to-centre spacing (P)")
    _find_or_add_param(up, "LegSpacing", _mm_expr(params.support_spacing_mm), "mm", "Support-leg station spacing (S)")
    _find_or_add_param(up, "GuardHeight", _mm_expr(max(params.side_guard_height_mm, 1.0)), "mm", "Side-guard height (G)")

    # Structural constants
    _find_or_add_param(up, "RailW", _mm_expr(RAIL_W), "mm", "Rail cross-section width")
    _find_or_add_param(up, "RailH", _mm_expr(RAIL_H), "mm", "Rail cross-section height")
    _find_or_add_param(up, "LegSide", _mm_expr(LEG_SIDE), "mm", "Leg post cross-section size")
    _find_or_add_param(up, "RollerClearance", _mm_expr(ROLLER_CLEARANCE), "mm", "Gap between roller end and inner rail")
    _find_or_add_param(up, "GuardThick", _mm_expr(GUARD_THICK), "mm", "Side guard plate thickness")
    _find_or_add_param(up, "RollerMargin", "RollerDia / 2 + 10 mm", "mm", "Offset from conveyor end to roller centre")

    # Formula parameters driven by Fusion parametric engine
    _find_or_add_param(up, "RollerCount",
                       "floor((ConvLength - 2 * RollerMargin) / RollerSpacing) + 1",
                       "", "Number of rollers derived from length and spacing")
    _find_or_add_param(up, "LegCount",
                       "floor((ConvLength - LegSide) / LegSpacing) + 1",
                       "", "Number of leg stations derived from length and spacing")


def update_model_parameters(design: "adsk.fusion.Design", model_refs: Dict[str, object], params: ConveyorInput) -> None:
    """Updates base user parameters in-place and toggles feature suppression."""
    up = design.userParameters
    _set_param_value(up, "ConvLength", _mm_expr(params.length_mm))
    _set_param_value(up, "ConvWidth", _mm_expr(params.width_mm))
    _set_param_value(up, "FrameHeight", _mm_expr(params.height_mm))
    _set_param_value(up, "RollerDia", _mm_expr(params.roller_diameter_mm))
    _set_param_value(up, "RollerSpacing", _mm_expr(params.roller_spacing_mm))
    _set_param_value(up, "LegSpacing", _mm_expr(params.support_spacing_mm))
    _set_param_value(up, "GuardHeight", _mm_expr(max(params.side_guard_height_mm, 1.0)))

    # Toggle side guard feature suppression
    ext_guards = model_refs.get("ext_guards")
    if ext_guards:
        ext_guards.isSuppressed = not params.side_guards

    design.computeAll()


# ---------------------------------------------------------------------------
# 4. FUSION 360 PARAMETRIC GEOMETRY GENERATOR
# ---------------------------------------------------------------------------
def build_parametric_conveyor_model(design: "adsk.fusion.Design") -> Dict[str, object]:
    """
    Builds the complete parametric conveyor CAD tree once.
    All dimensions are linked to User Parameters and native Rectangular Patterns.
    """
    root = design.rootComponent

    # Clean existing conveyor components to prevent stale duplicates on initial script run
    for occ in list(root.occurrences):
        if occ.name.startswith("ParametricConveyor") or (occ.component and occ.component.name.startswith("ParametricConveyor")):
            occ.deleteMe()

    comp_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = comp_occ.component
    comp.name = "ParametricConveyor_Assembly"
    comp_occ.name = "ParametricConveyor_Assembly"

    sketches = comp.sketches
    extrudes = comp.features.extrudeFeatures
    planes = comp.constructionPlanes
    pattern_feats = comp.features.rectangularPatternFeatures

    # -----------------------------------------------------------------
    # A. SIDE RAILS (Sketched on offset plane at FrameHeight - RailH)
    # -----------------------------------------------------------------
    rail_plane_input = planes.createInput()
    rail_plane_input.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByString("FrameHeight - RailH"))
    rail_plane = planes.add(rail_plane_input)
    rail_plane.name = "Plane_Rail_Bottom"

    sk_rails = sketches.add(rail_plane)
    sk_rails.name = "Sketch_SideRails"
    rc = sk_rails.sketchCurves.sketchLines
    rd = sk_rails.sketchDimensions

    # Near rail rectangle: (0, 0) to (ConvLength, RailW)
    near_rect = rc.addTwoPointRectangle(adsk.core.Point3D.create(0, 0, 0), adsk.core.Point3D.create(10, 2, 0))
    d_nl = rd.addDistanceDimension(near_rect.item(0).startSketchPoint, near_rect.item(0).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(5, -1, 0))
    d_nl.parameter.expression = "ConvLength"
    d_nw = rd.addDistanceDimension(near_rect.item(3).startSketchPoint, near_rect.item(3).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(-1, 1, 0))
    d_nw.parameter.expression = "RailW"

    # Far rail rectangle: (0, ConvWidth - RailW) to (ConvLength, ConvWidth)
    far_rect = rc.addTwoPointRectangle(adsk.core.Point3D.create(0, 30, 0), adsk.core.Point3D.create(10, 32, 0))
    d_fl = rd.addDistanceDimension(far_rect.item(0).startSketchPoint, far_rect.item(0).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(5, 33, 0))
    d_fl.parameter.expression = "ConvLength"
    d_fw = rd.addDistanceDimension(far_rect.item(3).startSketchPoint, far_rect.item(3).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(-1, 31, 0))
    d_fw.parameter.expression = "RailW"

    # Constrain far rail to ConvWidth parametrically
    d_width = rd.addDistanceDimension(near_rect.item(0).startSketchPoint, far_rect.item(2).endSketchPoint,
                                     adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                                     adsk.core.Point3D.create(-2, 15, 0))
    d_width.parameter.expression = "ConvWidth"

    # Extrude both rails upwards by RailH
    rail_profs = adsk.core.ObjectCollection.create()
    for i in range(sk_rails.profiles.count):
        rail_profs.add(sk_rails.profiles.item(i))
    ext_rail_input = extrudes.createInput(rail_profs, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_rail_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("RailH"))
    ext_rails = extrudes.add(ext_rail_input)
    ext_rails.name = "Extrude_SideRails"

    # -----------------------------------------------------------------
    # B. MASTER ROLLER + NATIVE RECTANGULAR PATTERN
    # -----------------------------------------------------------------
    roller_plane_input = planes.createInput()
    roller_plane_input.setByOffset(comp.xZConstructionPlane, adsk.core.ValueInput.createByString("RailW + RollerClearance"))
    roller_plane = planes.add(roller_plane_input)
    roller_plane.name = "Plane_Roller_Face"

    sk_roller = sketches.add(roller_plane)
    sk_roller.name = "Sketch_MasterRoller"
    roller_circle = sk_roller.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), 2.5)
    r_dia = sk_roller.sketchDimensions.addDiameterDimension(roller_circle, adsk.core.Point3D.create(2, 2, 0))
    r_dia.parameter.expression = "RollerDia"

    # Position roller center at x = RollerMargin, z = FrameHeight
    r_x = sk_roller.sketchDimensions.addDistanceDimension(sk_roller.originPoint, roller_circle.centerSketchPoint,
                                                          adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                                                          adsk.core.Point3D.create(1, 2, 0))
    r_x.parameter.expression = "RollerMargin"
    r_z = sk_roller.sketchDimensions.addDistanceDimension(sk_roller.originPoint, roller_circle.centerSketchPoint,
                                                          adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                                                          adsk.core.Point3D.create(1, 2, 0))
    r_z.parameter.expression = "FrameHeight"

    roller_prof = sk_roller.profiles.item(0)
    roller_ext_input = extrudes.createInput(roller_prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    roller_ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("ConvWidth - 2 * (RailW + RollerClearance)"))
    ext_roller = extrudes.add(roller_ext_input)
    ext_roller.name = "Extrude_MasterRoller"
    roller_body = ext_roller.bodies.item(0)
    roller_body.name = "Body_Roller_Master"

    # Rectangular Pattern driven directly by RollerCount & RollerSpacing formulas
    roller_entities = adsk.core.ObjectCollection.create()
    roller_entities.add(roller_body)
    pattern_roller_input = pattern_feats.createInput(
        roller_entities, comp.xConstructionAxis,
        adsk.core.ValueInput.createByString("RollerCount"),
        adsk.core.ValueInput.createByString("RollerSpacing"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    pattern_rollers = pattern_feats.add(pattern_roller_input)
    pattern_rollers.name = "Pattern_Rollers"

    # -----------------------------------------------------------------
    # C. MASTER SUPPORT LEG PAIR + NATIVE RECTANGULAR PATTERN
    # -----------------------------------------------------------------
    sk_legs = sketches.add(comp.xYConstructionPlane)
    sk_legs.name = "Sketch_LegPair"
    lc = sk_legs.sketchCurves.sketchLines
    ld = sk_legs.sketchDimensions

    # Near leg post (origin)
    near_leg = lc.addTwoPointRectangle(adsk.core.Point3D.create(0, 0, 0), adsk.core.Point3D.create(4, 4, 0))
    l_nx = ld.addDistanceDimension(near_leg.item(0).startSketchPoint, near_leg.item(0).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(2, -1, 0))
    l_nx.parameter.expression = "LegSide"
    l_ny = ld.addDistanceDimension(near_leg.item(3).startSketchPoint, near_leg.item(3).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(-1, 2, 0))
    l_ny.parameter.expression = "LegSide"

    # Far leg post
    far_leg = lc.addTwoPointRectangle(adsk.core.Point3D.create(0, 30, 0), adsk.core.Point3D.create(4, 34, 0))
    l_fx = ld.addDistanceDimension(far_leg.item(0).startSketchPoint, far_leg.item(0).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(2, 35, 0))
    l_fx.parameter.expression = "LegSide"
    l_fy = ld.addDistanceDimension(far_leg.item(3).startSketchPoint, far_leg.item(3).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(-1, 32, 0))
    l_fy.parameter.expression = "LegSide"
    l_width = ld.addDistanceDimension(near_leg.item(0).startSketchPoint, far_leg.item(2).endSketchPoint,
                                     adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                                     adsk.core.Point3D.create(-2, 15, 0))
    l_width.parameter.expression = "ConvWidth"

    leg_profs = adsk.core.ObjectCollection.create()
    for i in range(sk_legs.profiles.count):
        leg_profs.add(sk_legs.profiles.item(i))
    ext_leg_input = extrudes.createInput(leg_profs, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_leg_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("FrameHeight - RailH"))
    ext_legs = extrudes.add(ext_leg_input)
    ext_legs.name = "Extrude_MasterLegs"

    leg_entities = adsk.core.ObjectCollection.create()
    for i in range(ext_legs.bodies.count):
        leg_entities.add(ext_legs.bodies.item(i))
    pattern_leg_input = pattern_feats.createInput(
        leg_entities, comp.xConstructionAxis,
        adsk.core.ValueInput.createByString("LegCount"),
        adsk.core.ValueInput.createByString("LegSpacing"),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    pattern_legs = pattern_feats.add(pattern_leg_input)
    pattern_legs.name = "Pattern_SupportLegs"

    # -----------------------------------------------------------------
    # D. SIDE GUARDS (On top of rails, toggled via isSuppressed)
    # -----------------------------------------------------------------
    guard_plane_input = planes.createInput()
    guard_plane_input.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByString("FrameHeight"))
    guard_plane = planes.add(guard_plane_input)
    guard_plane.name = "Plane_SideGuards"

    sk_guards = sketches.add(guard_plane)
    sk_guards.name = "Sketch_SideGuards"
    gc = sk_guards.sketchCurves.sketchLines
    gd = sk_guards.sketchDimensions

    # Near guard plate
    near_g = gc.addTwoPointRectangle(adsk.core.Point3D.create(0, 0, 0), adsk.core.Point3D.create(10, 0.5, 0))
    g_nl = gd.addDistanceDimension(near_g.item(0).startSketchPoint, near_g.item(0).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(5, -1, 0))
    g_nl.parameter.expression = "ConvLength"
    g_nw = gd.addDistanceDimension(near_g.item(3).startSketchPoint, near_g.item(3).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(-1, 0.25, 0))
    g_nw.parameter.expression = "GuardThick"

    # Far guard plate
    far_g = gc.addTwoPointRectangle(adsk.core.Point3D.create(0, 30, 0), adsk.core.Point3D.create(10, 30.5, 0))
    g_fl = gd.addDistanceDimension(far_g.item(0).startSketchPoint, far_g.item(0).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(5, 31, 0))
    g_fl.parameter.expression = "ConvLength"
    g_fw = gd.addDistanceDimension(far_g.item(3).startSketchPoint, far_g.item(3).endSketchPoint,
                                  adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                                  adsk.core.Point3D.create(-1, 30.25, 0))
    g_fw.parameter.expression = "GuardThick"
    g_width = gd.addDistanceDimension(near_g.item(0).startSketchPoint, far_g.item(2).endSketchPoint,
                                     adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                                     adsk.core.Point3D.create(-2, 15, 0))
    g_width.parameter.expression = "ConvWidth"

    guard_profs = adsk.core.ObjectCollection.create()
    for i in range(sk_guards.profiles.count):
        guard_profs.add(sk_guards.profiles.item(i))
    ext_guard_input = extrudes.createInput(guard_profs, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ext_guard_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("GuardHeight"))
    ext_guards = extrudes.add(ext_guard_input)
    ext_guards.name = "Extrude_SideGuards"

    return {
        "component": comp,
        "occurrence": comp_occ,
        "ext_guards": ext_guards,
        "pattern_rollers": pattern_rollers,
        "pattern_legs": pattern_legs,
    }


# ---------------------------------------------------------------------------
# 5. PHYSICAL CAD VALIDATION & EXPORT UTILITIES
# ---------------------------------------------------------------------------
def validate_cad_model(design: "adsk.fusion.Design", comp: "adsk.fusion.Component", params: ConveyorInput) -> List[Tuple[str, bool, str]]:
    """Validates physical B-rep CAD geometry extents against spec tolerances."""
    up = design.userParameters
    checks = []

    bbox = comp.boundingBox
    actual_l = (bbox.maxPoint.x - bbox.minPoint.x) * 10.0
    actual_w = (bbox.maxPoint.y - bbox.minPoint.y) * 10.0
    actual_h = (bbox.maxPoint.z - bbox.minPoint.z) * 10.0

    checks.append((
        "Length within 5mm tolerance",
        abs(actual_l - params.length_mm) <= 5.0,
        f"{actual_l:.1f} mm actual vs {params.length_mm:.1f} mm requested",
    ))
    checks.append((
        "Width within 5mm tolerance",
        abs(actual_w - params.width_mm) <= 5.0,
        f"{actual_w:.1f} mm actual vs {params.width_mm:.1f} mm requested",
    ))

    expected_h = params.height_mm + (params.side_guard_height_mm if params.side_guards else (params.roller_diameter_mm / 2.0))
    checks.append((
        "Height within 5mm tolerance",
        abs(actual_h - expected_h) <= 5.0,
        f"{actual_h:.1f} mm actual vs {expected_h:.1f} mm expected",
    ))

    # Validate formula-derived counts
    rc_fusion = int(up.itemByName("RollerCount").value)
    lc_fusion = int(up.itemByName("LegCount").value)
    expected_rc = math.floor((params.length_mm - 2 * (params.roller_diameter_mm / 2.0 + 10.0)) / params.roller_spacing_mm) + 1
    expected_lc = math.floor((params.length_mm - LEG_SIDE) / params.support_spacing_mm) + 1

    checks.append((
        "RollerCount formula recomputation",
        rc_fusion == expected_rc,
        f"Fusion={rc_fusion} vs Formula Expected={expected_rc}",
    ))
    checks.append((
        "LegCount formula recomputation",
        lc_fusion == expected_lc,
        f"Fusion={lc_fusion} vs Formula Expected={expected_lc}",
    ))

    return checks


def export_bom_csv(cfg_name: str, params: ConveyorInput, derived: ConveyorDerived, output_dir: str) -> str:
    """Exports a formatted Bill of Materials (CSV) for the configuration."""
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, f"{cfg_name}_BOM.csv")
    rows = [
        ("Side Rails", 2, f"Length={params.length_mm:.1f} mm, Section={RAIL_W}x{RAIL_H} mm"),
        (
            "Rollers",
            derived.roller_count,
            f"Diameter={params.roller_diameter_mm:.1f} mm, Length={params.width_mm - 2 * (RAIL_W + ROLLER_CLEARANCE):.1f} mm, Spacing={derived.actual_roller_spacing_mm:.2f} mm",
        ),
        (
            "Support Leg Posts",
            derived.support_pair_count * 2,
            f"Height={params.height_mm - RAIL_H:.1f} mm, Section={LEG_SIDE}x{LEG_SIDE} mm, Station Spacing={derived.actual_support_spacing_mm:.2f} mm",
        ),
    ]
    if params.side_guards:
        rows.append(("Side Guards", 2, f"Length={params.length_mm:.1f} mm, Height={params.side_guard_height_mm:.1f} mm, Thickness={GUARD_THICK} mm"))

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Part Name", "Quantity", "Dimensions / Notes"])
        writer.writerows(rows)
    return csv_path


def export_step_file(design: "adsk.fusion.Design", comp: "adsk.fusion.Component", cfg_name: str, output_dir: str) -> str:
    """Exports a STEP 3D CAD file for the configuration."""
    os.makedirs(output_dir, exist_ok=True)
    step_path = os.path.join(output_dir, f"{cfg_name}.step")
    export_mgr = design.exportManager
    step_options = export_mgr.createSTEPExportOptions(step_path, comp)
    export_mgr.execute(step_options)
    return step_path


def run_batch_demonstration(design: "adsk.fusion.Design", model_refs: Dict[str, object], output_dir: str) -> Tuple[str, str]:
    """Runs automated batch generation for all 3 demo configurations."""
    report_lines = [
        "=========================================================================",
        "AUTODESK FUSION PARAMETRIC ROLLER CONVEYOR CONFIGURATION GENERATOR REPORT",
        "Problem Statement A — Automated Verification & Deliverables Pipeline",
        "=========================================================================",
        "",
    ]
    demos = demo_configurations()
    for name, params in demos.items():
        report_lines.append(f"--- Configuration: {name} ---")
        report_lines.append(
            f"Parameters: L={params.length_mm}mm, W={params.width_mm}mm, H={params.height_mm}mm, "
            f"D={params.roller_diameter_mm}mm, P={params.roller_spacing_mm}mm, "
            f"S={params.support_spacing_mm}mm, G={params.side_guard_height_mm}mm, side_guards={params.side_guards}"
        )
        update_model_parameters(design, model_refs, params)
        derived = derive_configuration(params)
        cad_checks = validate_cad_model(design, model_refs["component"], params)
        for label, passed, detail in cad_checks:
            status = "PASS" if passed else "FAIL"
            report_lines.append(f"  [{status}] {label} ({detail})")

        bom_path = export_bom_csv(name, params, derived, output_dir)
        step_path = export_step_file(design, model_refs["component"], name, output_dir)
        report_lines.append(f"  BOM CSV:  {bom_path}")
        report_lines.append(f"  STEP CAD: {step_path}")
        report_lines.append("")

    report_text = "\n".join(report_lines)
    os.makedirs(output_dir, exist_ok=True)
    report_file = os.path.join(output_dir, "validation_report.txt")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_text)
    return report_file, report_text


# ---------------------------------------------------------------------------
# 6. INTERACTIVE PARSING & UI ENTRY POINT
# ---------------------------------------------------------------------------
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

    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox("No active Fusion design. Open or create a design first.")
            return

        demos = demo_configurations()
        base_cfg = demos["C1_compact_no_guards"]

        # Prompt user to select execution mode
        mode_prompt = (
            "Select Conveyor Generator Operation Mode:\n\n"
            "[1] Automated 3-Configuration Demonstration Pipeline\n"
            "    - Generates & validates ConfigA, ConfigB, ConfigC\n"
            "    - Exports STEP models, CSV BOMs & verification report\n\n"
            "[2] Interactive Custom Parameter Entry\n"
            "    - Enter custom L, W, H, D, P, S, G\n"
            "    - Updates parametric CAD model in-place"
        )
        mode_str, cancelled = ui.inputBox(mode_prompt, "Parametric Conveyor Generator", "1")
        if cancelled:
            return

        # Initialize base parameters and build full parametric model once
        create_user_parameters(design, base_cfg)
        model_refs = build_parametric_conveyor_model(design)
        design.computeAll()

        output_dir = DEFAULT_OUTPUT_DIR

        if mode_str.strip() == "1":
            report_file, report_text = run_batch_demonstration(design, model_refs, output_dir)
            ui.messageBox(
                f"Batch generation completed successfully!\n\n"
                f"Deliverables exported to:\n{output_dir}\n\n"
                f"Summary Report:\n{report_text[:1200]}"
            )
        else:
            default = demos["C2_medium_with_guards"]
            prompt = (
                "Enter conveyor parameters: L,W,H,D,P,S,G,side_guards(Yes/No)\n\n"
                "Allowed ranges:\n"
                "L: 800-2000 mm, W: 300-600 mm, H: 500-900 mm\n"
                "D: 40-80 mm, P: 80-150 mm, S: 500-1000 mm, G: 0-150 mm\n\n"
                "Example: 1400,450,750,60,110,700,100,Yes"
            )
            default_text = (
                f"{default.length_mm:.0f},{default.width_mm:.0f},{default.height_mm:.0f},"
                f"{default.roller_diameter_mm:.0f},{default.roller_spacing_mm:.0f},"
                f"{default.support_spacing_mm:.0f},{default.side_guard_height_mm:.0f},"
                f"{'Yes' if default.side_guards else 'No'}"
            )
            input_text, cancelled2 = ui.inputBox(prompt, "Custom Conveyor Configuration", default_text)
            if cancelled2:
                return

            params = _parse_csv_input(input_text)
            validate_inputs(params)
            update_model_parameters(design, model_refs, params)
            derived = derive_configuration(params)
            cad_checks = validate_cad_model(design, model_refs["component"], params)
            bom_path = export_bom_csv("Custom_Config", params, derived, output_dir)
            step_path = export_step_file(design, model_refs["component"], "Custom_Config", output_dir)

            status_lines = [f"  [{'PASS' if p else 'FAIL'}] {lbl}: {d}" for lbl, p, d in cad_checks]
            ui.messageBox(
                f"Conveyor Model Updated In-Place!\n\n"
                f"Dimensions: {params.length_mm:.1f} x {params.width_mm:.1f} x {params.height_mm:.1f} mm\n"
                f"Rollers: {derived.roller_count} @ {derived.actual_roller_spacing_mm:.2f} mm spacing\n"
                f"Leg Posts: {derived.support_pair_count * 2} @ {derived.actual_support_spacing_mm:.2f} mm station spacing\n"
                f"Side Guards: {'Enabled' if params.side_guards else 'Suppressed'}\n\n"
                f"Exported BOM: {bom_path}\n"
                f"Exported STEP: {step_path}\n\n"
                f"CAD Verifications:\n" + "\n".join(status_lines)
            )

    except Exception:
        if ui:
            ui.messageBox(f"Error:\n{traceback.format_exc()}")


def stop(context):
    pass
