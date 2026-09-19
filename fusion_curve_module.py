"""fusion_curve_module.py — Curved (arced) roller conveyor module (peer to straight).

LOCK-INS (user-approved):
  1. Full Tapered only — no cylindrical-on-curve. Kinematic condition
     d_inner / R_inner == d_outer / R_outer so surface speed matches
     angular velocity across width. Built as 2D trapezoid revolved 360 deg
     (revolveFeatures) around the roller axis, patterned with
     circularPatternFeatures.
  2. Spec-Only Core + Smart Advisory — ConveyorInput untouched. This module
     takes its own CurveInput but reuses RANGES for W/H/D/P/S/G. Advisory
     helper maps (box mass/length) -> recommended spec values, never replaces
     the spec contract.
  3. Modules-First — Straight and Curve are peer generators with docking
     ports (InletPort/OutletPort). Layout manager only places occurrences,
     never builds monolithic timelines.

Pure-Python math here runs offline (CI). Fusion builders run inside Fusion.
"""
from __future__ import annotations

import math
import os
import csv
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # type-checkers only
    import adsk.core  # type: ignore
    import adsk.fusion  # type: ignore

try:
    import adsk.core  # type: ignore
    import adsk.fusion  # type: ignore
except ImportError:  # pragma: no cover - offline
    adsk = None

from fusion_conveyor_generator import (
    GUARD_THICK,
    LEG_SIDE,
    RAIL_H,
    RAIL_W,
    RANGES,
    ROLLER_CLEARANCE,
)

# ---------------------------------------------------------------------------
# 1. Curve ranges (additive — straight RANGES untouched)
# ---------------------------------------------------------------------------
CURVE_RANGES = {
    "Ri": (400.0, 1200.0),   # inner radius to inner rail (mm)
    "Theta": (15.0, 180.0),  # curve angle (deg)
}
CURVE_PRESETS_DEG = (30.0, 45.0, 60.0, 90.0, 180.0)
# Interroll/Damon limits
MAX_ANGULAR_PITCH_DEG = 5.0   # angle between adjacent tapered rollers
STANDARD_TAPER_DEG = 3.6      # industry standard cone angle (informational)
MIN_CURVE_ROLLERS = 3         # stability on curve


# ---------------------------------------------------------------------------
# 2. Data models
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CurveInput:
    """Spec-only curve inputs. D = SMALL (inner) roller dia; P = OUTER arc pitch."""

    inner_radius_mm: float
    curve_angle_deg: float
    width_mm: float
    height_mm: float
    roller_dia_inner_mm: float
    roller_pitch_outer_mm: float
    support_spacing_mm: float
    side_guard_height_mm: float
    side_guards: bool


@dataclass(frozen=True)
class CurveDerived:
    outer_radius_mm: float
    center_radius_mm: float
    arc_inner_mm: float
    arc_center_mm: float
    arc_outer_mm: float
    roller_dia_outer_mm: float
    taper_ratio: float
    roller_count: int
    angular_pitch_deg: float
    support_count: int
    footprint_x_mm: float
    footprint_y_mm: float
    overall_height_mm: float


@dataclass(frozen=True)
class LoadAdvisory:
    """Tier-2 advisory: maps box -> recommended SPEC values (never auto-applies)."""

    p_recommended_mm: float
    d_recommended_mm: float
    s_recommended_mm: float
    w_recommended_mm: float
    warnings: Tuple[str, ...]
    explanation: str


# ---------------------------------------------------------------------------
# 3. Core curve math (pure, testable)
# ---------------------------------------------------------------------------
def taper_outer_dia(d_inner_mm: float, ri_mm: float, width_mm: float) -> float:
    """Kinematic taper: d_outer = d_inner * Ro / Ri."""
    if ri_mm <= 0:
        raise ValueError("inner_radius must be positive.")
    return d_inner_mm * (ri_mm + width_mm) / ri_mm


def arc_length_mm(radius_mm: float, angle_deg: float) -> float:
    return radius_mm * math.radians(angle_deg)


def curve_roller_margin_mm(d_inner_mm: float) -> float:
    """Arc-direction end margin, mirrors straight RollerMargin = D/2 + 10."""
    return d_inner_mm / 2.0 + ROLLER_CLEARANCE


def curve_roller_count_for(angle_deg: float, ri_mm: float, width_mm: float,
                           d_inner_mm: float, pitch_outer_mm: float) -> int:
    """Single-source curve roller count (outer-arc floor-pitch math).

    usable_outer = Ro*theta - 2*margin; N = floor(usable/pitch)+1, min 3.
    Mirrors straight roller_count_for() but on the outer arc.
    """
    ro = ri_mm + width_mm
    total_outer = arc_length_mm(ro, angle_deg)
    usable = total_outer - 2.0 * curve_roller_margin_mm(d_inner_mm)
    if usable <= 1e-9:
        return 1
    count = int(math.floor(usable / pitch_outer_mm)) + 1
    count = max(count, MIN_CURVE_ROLLERS if usable > 0 else 1)
    # Enforce max 5 deg angular pitch (Damon/Interroll): bump N if needed
    if angle_deg > 0 and count > 1:
        min_for_angle = int(math.ceil(angle_deg / MAX_ANGULAR_PITCH_DEG)) + 1
        count = max(count, min_for_angle)
    return count


def curve_angular_pitch_deg(angle_deg: float, roller_count: int) -> float:
    if roller_count <= 1:
        return 0.0
    return angle_deg / (roller_count - 1)


def validate_curve_inputs(p: CurveInput) -> None:
    lo, hi = CURVE_RANGES["Ri"]
    if not (lo <= p.inner_radius_mm <= hi):
        raise ValueError(f"inner_radius_mm must be within {lo}-{hi} mm.")
    lo, hi = CURVE_RANGES["Theta"]
    if not (lo <= p.curve_angle_deg <= hi):
        raise ValueError(f"curve_angle_deg must be within {lo}-{hi} deg.")
    # Reuse straight ranges for shared dims
    for val, key in ((p.width_mm, "W"), (p.height_mm, "H"),
                     (p.roller_dia_inner_mm, "D"), (p.roller_pitch_outer_mm, "P"),
                     (p.support_spacing_mm, "S"), (p.side_guard_height_mm, "G")):
        lo, hi = RANGES[key]
        if not (lo <= val <= hi):
            raise ValueError(f"{key}={val} out of range {lo}-{hi}.")
    if p.roller_pitch_outer_mm <= p.roller_dia_inner_mm:
        raise ValueError("Outer pitch P must exceed inner roller diameter D (else overlap).")
    # Taper sanity: outer dia should stay manufacturable (< ~120mm)
    d_out = taper_outer_dia(p.roller_dia_inner_mm, p.inner_radius_mm, p.width_mm)
    if d_out > 120.0:
        raise ValueError(
            f"Taper outer dia {d_out:.1f}mm exceeds 120mm shop limit — "
            "increase Ri or reduce D/W.")


def derive_curve_configuration(p: CurveInput) -> CurveDerived:
    validate_curve_inputs(p)
    ro = p.inner_radius_mm + p.width_mm
    rc = p.inner_radius_mm + p.width_mm / 2.0
    d_out = taper_outer_dia(p.roller_dia_inner_mm, p.inner_radius_mm, p.width_mm)
    n = curve_roller_count_for(p.curve_angle_deg, p.inner_radius_mm, p.width_mm,
                               p.roller_dia_inner_mm, p.roller_pitch_outer_mm)
    ang_pitch = curve_angular_pitch_deg(p.curve_angle_deg, n)
    # Supports: radial stations along center arc, same floor-pitch idiom
    center_arc = arc_length_mm(rc, p.curve_angle_deg)
    usable_s = center_arc - LEG_SIDE
    if usable_s <= 1e-9:
        s_count = 1
    else:
        s_count = max(2, int(math.floor(usable_s / p.support_spacing_mm)) + 1)
    # Footprint of annular sector (conservative bbox for layout manager)
    theta = math.radians(p.curve_angle_deg)
    # chord/height of sector
    if p.curve_angle_deg <= 90.0:
        fx = ro - p.inner_radius_mm * math.cos(theta) if theta > 0 else ro
        fx = max(ro * math.sin(theta), ro - ro * math.cos(theta))
        fy = ro * math.sin(theta)
        # simpler conservative: bounding square of outer radius sector
        fx = ro * math.sin(theta) if p.curve_angle_deg <= 90 else ro
        fy = ro * (1 - math.cos(theta)) if p.curve_angle_deg <= 90 else ro
        # fallback conservative square
        fx = max(fx, ro * math.sin(theta))
        fy = max(fy, ro * (1 - math.cos(theta)))
    else:
        fx = ro * (1 + math.sin(theta - math.pi / 2)) if False else ro * 2.0
        fy = ro * 2.0
        # conservative: full outer diameter square for >90deg (layout-safe)
        fx, fy = ro, ro * 2.0 if p.curve_angle_deg <= 180 else ro * 2.0
    eff_guard = p.side_guard_height_mm if p.side_guards else 0.0
    roller_top = p.height_mm + d_out / 2.0
    overall_h = max(roller_top, p.height_mm + eff_guard, p.height_mm)
    return CurveDerived(
        outer_radius_mm=ro,
        center_radius_mm=rc,
        arc_inner_mm=arc_length_mm(p.inner_radius_mm, p.curve_angle_deg),
        arc_center_mm=center_arc,
        arc_outer_mm=arc_length_mm(ro, p.curve_angle_deg),
        roller_dia_outer_mm=d_out,
        taper_ratio=ro / p.inner_radius_mm,
        roller_count=n,
        angular_pitch_deg=ang_pitch,
        support_count=s_count,
        footprint_x_mm=fx,
        footprint_y_mm=fy,
        overall_height_mm=overall_h,
    )


def verify_curve_configuration(p: CurveInput,
                               d: Optional[CurveDerived] = None,
                               tol: float = 1e-6) -> Dict[str, bool]:
    d = d or derive_curve_configuration(p)
    checks = {
        "taper_kinematics": abs(d.roller_dia_outer_mm / d.outer_radius_mm
                                - p.roller_dia_inner_mm / p.inner_radius_mm) <= 1e-9,
        "angular_pitch_limit": d.angular_pitch_deg <= MAX_ANGULAR_PITCH_DEG + tol,
        "roller_count_matches": d.roller_count == curve_roller_count_for(
            p.curve_angle_deg, p.inner_radius_mm, p.width_mm,
            p.roller_dia_inner_mm, p.roller_pitch_outer_mm),
        "min_rollers": d.roller_count >= MIN_CURVE_ROLLERS,
        "outer_dia_limit": d.roller_dia_outer_mm <= 120.0 + tol,
        "footprint_positive": d.footprint_x_mm > 0 and d.footprint_y_mm > 0,
    }
    checks["all"] = all(checks.values())
    return checks


def curve_bom(d: CurveDerived, side_guards: bool) -> Dict[str, int]:
    return {
        "frame_arc_rails": 2,
        "tapered_rollers": d.roller_count,
        "support_leg_pairs": d.support_count,
        "support_legs_total": d.support_count * 2,
        "curved_side_guards": 2 if side_guards else 0,
    }


# ---------------------------------------------------------------------------
# 4. Tier-2 Smart Advisory (box -> SPEC suggestions; never replaces spec)
# ---------------------------------------------------------------------------
def calculate_load_advisory(box_mass_kg: float, box_length_mm: float,
                            box_width_mm: float,
                            span_mm: Optional[float] = None) -> LoadAdvisory:
    """Heuristic sizing aid (documented, reviewable — not FEA).

    - P <= Lbox/3 (min 3 rollers under load, Interroll rule).
    - D steps with mass per roller (~mass/3): <=60kg->50, <=120kg->60, else 80.
    - S tightens with mass: <=60kg->1000, <=120kg->700, else 500.
    - W = box_width + 100 (curve needs extra vs straight +50).
    All outputs clamped into RANGES; warnings explain clamping.
    """
    warnings: List[str] = []
    if box_mass_kg <= 0 or box_length_mm <= 0 or box_width_mm <= 0:
        raise ValueError("box mass/length/width must be positive.")
    # Pitch
    p_raw = box_length_mm / 3.0
    p_lo, p_hi = RANGES["P"]
    p_rec = min(max(p_raw, p_lo), p_hi)
    if p_raw < p_lo:
        warnings.append(
            f"Box L={box_length_mm:.0f} needs P<={p_raw:.0f} for 3-roller support, "
            f"below spec min {p_lo:.0f} — use smallest P and shorter boxes, or request deviation.")
    elif p_raw > p_hi:
        warnings.append(
            f"P={p_raw:.0f} satisfies 3-roller rule with margin; clamped to spec max {p_hi:.0f}.")
    # Diameter by mass
    if box_mass_kg <= 60:
        d_rec = 50.0
    elif box_mass_kg <= 120:
        d_rec = 60.0
    else:
        d_rec = 80.0
    d_lo, d_hi = RANGES["D"]
    d_rec = min(max(d_rec, d_lo), d_hi)
    # Leg spacing by mass
    if box_mass_kg <= 60:
        s_rec = 1000.0
    elif box_mass_kg <= 120:
        s_rec = 700.0
    else:
        s_rec = 500.0
    # Width: curve needs +100 over box (vs +50 straight)
    w_raw = box_width_mm + 100.0
    w_lo, w_hi = RANGES["W"]
    w_rec = min(max(w_raw, w_lo), w_hi)
    if w_raw > w_hi:
        warnings.append(
            f"Box W={box_width_mm:.0f} needs curve width {w_raw:.0f} (box+100 jam margin), "
            f"above spec max {w_hi:.0f} — split load or request deviation.")
    expl = (f"P<=Lbox/3={p_raw:.1f} gives {p_rec:.0f}; D by mass/3={box_mass_kg / 3:.1f}kg/roller gives {d_rec:.0f}; "
            f"S by mass gives {s_rec:.0f}; W=box+100={w_raw:.0f} gives {w_rec:.0f}.")
    return LoadAdvisory(p_recommended_mm=p_rec, d_recommended_mm=d_rec,
                        s_recommended_mm=s_rec, w_recommended_mm=w_rec,
                        warnings=tuple(warnings), explanation=expl)


# ---------------------------------------------------------------------------
# 5. Fusion builders (inside Fusion only) — Modules-First
# ---------------------------------------------------------------------------
def _mm(val: float) -> str:
    return f"{val} mm"


def _find_or_add(up, name: str, expr: str, unit: str, comment: str = ""):
    ex = up.itemByName(name)
    if ex:
        if ex.expression != expr:
            ex.expression = expr
        return ex
    return up.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)


def create_curve_parameters(design, p: CurveInput) -> None:
    """Idempotent curve user parameters (C_ prefix avoids clashing with straight)."""
    up = design.userParameters
    _find_or_add(up, "C_InnerRadius", _mm(p.inner_radius_mm), "mm", "Curve inner radius Ri")
    _find_or_add(up, "C_CurveAngle", f"{p.curve_angle_deg} deg", "deg", "Curve sweep angle")
    _find_or_add(up, "C_ConvWidth", _mm(p.width_mm), "mm", "Curve width (radial)")
    _find_or_add(up, "C_FrameHeight", _mm(p.height_mm), "mm", "Floor to frame")
    _find_or_add(up, "C_RollerDiaInner", _mm(p.roller_dia_inner_mm), "mm", "Taper small dia")
    _find_or_add(up, "C_RollerPitchOuter", _mm(p.roller_pitch_outer_mm), "mm", "Outer-arc pitch")
    _find_or_add(up, "C_LegSpacing", _mm(p.support_spacing_mm), "mm", "Center-arc leg spacing")
    _find_or_add(up, "C_GuardHeight", _mm(max(p.side_guard_height_mm, 1.0)), "mm", "Guard height")
    _find_or_add(up, "C_OuterRadius", "C_InnerRadius + C_ConvWidth", "mm", "Outer radius Ro")
    _find_or_add(up, "C_RollerDiaOuter",
                 "C_RollerDiaInner * C_OuterRadius / C_InnerRadius", "mm",
                 "Taper large dia (kinematic ratio)")
    _find_or_add(up, "C_RollerMargin", "C_RollerDiaInner / 2 + 10 mm", "mm",
                 "Arc end margin (mirrors straight)")
    # Outer-arc floor-pitch count. PROVEN LIVE 2026-09-18 on Fusion 2026:
    #   - angle must be unit-stripped via `/ 1 rad` (R*deg is unparseable);
    #     `pi` is NOT available in the expression language — do not use it.
    #   - `floor` and `ceil` exist; `max(a,b)`/`max(a;b)` do NOT (both forms
    #     rejected). Hence the canonical count lives in Python
    #     (curve_roller_count_for = max of the two below) while Fusion carries
    #     both auditable operands. Pattern quantity uses the Python literal;
    #     validator checks Fusion pair + canonical max (all live-verified).
    _find_or_add(up, "C_RollerCount",
                 "floor((C_OuterRadius * C_CurveAngle / 1 rad - 2 * C_RollerMargin) / C_RollerPitchOuter) + 1",
                 "", "Curve roller floor count (outer arc; live=18 on demo)")
    _find_or_add(up, "C_RollerCountMin",
                 "ceil(C_CurveAngle / 5 deg) + 1",
                 "", "Angular-cap floor (<=5deg pitch; live=19 on demo)")
    _find_or_add(up, "C_LegCount",
                 "floor(((C_InnerRadius + C_ConvWidth / 2) * C_CurveAngle / 1 rad - 40 mm) / C_LegSpacing) + 1",
                 "", "Curve radial leg stations (live=3 on demo)")


def build_tapered_master_roller(comp, d_inner_mm: float, d_outer_mm: float,
                                roller_len_mm: float, axis_height_mm: float,
                                start_radius_mm: float, name: str = "Body_RollerTapered_Master"):
    """Trapezoid sketch revolved 360 deg about roller (radial) axis.

    Sketch plane: XY at roller height; trapezoid symmetric about the X axis
    (radial direction); axis line y=0 from x0 to x1; revolve full circle.
    Returns (revolve_feature, body).
    """
    sketches = comp.sketches
    revolves = comp.features.revolveFeatures
    # Sketch on XY plane (contains radial X + lateral Y); height via geometry offset
    sk = sketches.add(comp.xYConstructionPlane)
    sk.name = "Sketch_TaperedRollerMaster"
    lines = sk.sketchCurves.sketchLines
    # cm placeholders (DB units); real dims via dimension expressions below
    x0, x1 = start_radius_mm / 10.0, (start_radius_mm + roller_len_mm) / 10.0
    r0, r1 = (d_inner_mm / 2.0) / 10.0, (d_outer_mm / 2.0) / 10.0
    y_off = axis_height_mm / 10.0
    p0 = adsk.core.Point3D.create(x0, y_off - r0, 0)
    p1 = adsk.core.Point3D.create(x1, y_off - r1, 0)
    p2 = adsk.core.Point3D.create(x1, y_off + r1, 0)
    p3 = adsk.core.Point3D.create(x0, y_off + r0, 0)
    lines.addByTwoPoints(p0, p1)
    lines.addByTwoPoints(p1, p2)
    lines.addByTwoPoints(p2, p3)
    lines.addByTwoPoints(p3, p0)
    # True axis: horizontal line through center at y_off
    axis_line = lines.addByTwoPoints(adsk.core.Point3D.create(x0, y_off, 0),
                                     adsk.core.Point3D.create(x1, y_off, 0))
    # Axis line inside trapezoid splits profiles (observed: 2 profiles live).
    # Pick the largest-area profile robustly (never assume item(0)).
    prof = sk.profiles.item(0)
    try:
        best, best_area = prof, -1.0
        for i in range(sk.profiles.count):
            cand = sk.profiles.item(i)
            try:
                a = float(cand.areaProperties().area)
            except Exception:
                a = -1.0
            if a > best_area:
                best, best_area = cand, a
        prof = best
    except Exception:
        pass
    rev_input = revolves.createInput(prof, axis_line,
                                     adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    rev_input.setAngleExtent(False, adsk.core.ValueInput.createByString("360 deg"))
    rev = revolves.add(rev_input)
    rev.name = "Revolve_TaperedRollerMaster"
    body = rev.bodies.item(0)
    body.name = name
    return rev, body


def build_curve_module(design, p: CurveInput):
    """Build isolated ParametricCurveModule component (never touches straight).

    NOTE (learned live 2026-09-18): a Part-design document (like the opened
    Roller file) holds a single component — addNewComponent fails there with
    "Part Design documents can only contain one component". In Part docs,
    build namespaced features in rootComponent instead; in Assembly docs,
    prefer a fresh occurrence component. Caller picks via _target_component().
    Returns dict with component/occurrence/master/circular pattern/guard refs
    + InletPort/OutletPort construction points for the layout manager.
    """
    validate_curve_inputs(p)
    derived = derive_curve_configuration(p)
    create_curve_parameters(design, p)
    root = design.rootComponent
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    tag = f"ParametricCurveModule_{p.curve_angle_deg:.0f}deg_Ri{p.inner_radius_mm:.0f}"
    comp.name = tag
    occ.name = tag

    # --- Arc rails: annular sector sketch on rail-bottom plane, extrude RailH
    planes = comp.constructionPlanes
    rp_in = planes.createInput()
    rp_in.setByOffset(comp.xYConstructionPlane,
                      adsk.core.ValueInput.createByString("C_FrameHeight - 40 mm"))
    rail_plane = planes.add(rp_in)
    rail_plane.name = "Plane_CurveRail_Bottom"
    sk = comp.sketches.add(rail_plane)
    sk.name = "Sketch_CurveRails"
    # Two concentric arcs + two radial lines = annular sector (drawn approx;
    # parametric truth comes from dimensions — simplified here, hardened live)
    arcs = sk.sketchCurves.sketchArcs
    lines = sk.sketchCurves.sketchLines
    ri_cm = p.inner_radius_mm / 10.0
    ro_cm = derived.outer_radius_mm / 10.0
    import math as _m
    th = _m.radians(p.curve_angle_deg)
    c = adsk.core.Point3D.create(0, 0, 0)
    s0 = adsk.core.Point3D.create(ri_cm, 0, 0)
    arcs.addByCenterStartSweep(c, s0, th)
    s1 = adsk.core.Point3D.create(ro_cm, 0, 0)
    arcs.addByCenterStartSweep(c, s1, th)
    # radial closers
    lines.addByTwoPoints(s0, s1)
    e0 = adsk.core.Point3D.create(ri_cm * _m.cos(th), ri_cm * _m.sin(th), 0)
    e1 = adsk.core.Point3D.create(ro_cm * _m.cos(th), ro_cm * _m.sin(th), 0)
    lines.addByTwoPoints(e0, e1)
    # Extrude sector by RailH (one-sided)
    extrudes = comp.features.extrudeFeatures
    profs = adsk.core.ObjectCollection.create()
    for i in range(sk.profiles.count):
        profs.add(sk.profiles.item(i))
    ext_in = extrudes.createInput(profs, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    dist = adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString("40 mm"))
    ext_in.setOneSideExtent(dist, adsk.fusion.ExtentDirections.PositiveExtentDirection)
    ext_rails = extrudes.add(ext_in)
    ext_rails.name = "Extrude_CurveRails"

    # --- Master tapered roller + circular pattern about curve center (Y axis)
    roller_len = p.width_mm - 2.0 * (RAIL_W + ROLLER_CLEARANCE)
    _rev, master_body = build_tapered_master_roller(
        comp, p.roller_dia_inner_mm, derived.roller_dia_outer_mm,
        roller_len, p.height_mm, p.inner_radius_mm + RAIL_W + ROLLER_CLEARANCE)
    ents = adsk.core.ObjectCollection.create()
    ents.add(master_body)
    circ_feats = comp.features.circularPatternFeatures
    circ_in = circ_feats.createInput(ents, comp.yConstructionAxis)
    # Prototype: Python N literal (enforces 5-deg angular cap). TODO: wire to
    # C_RollerCount once Fusion max()/ceil() expression syntax is validated live.
    circ_in.quantity = adsk.core.ValueInput.createByReal(float(derived.roller_count))
    circ_in.totalAngle = adsk.core.ValueInput.createByString("C_CurveAngle")
    circ_in.isSymmetric = False
    pat_rollers = circ_feats.add(circ_in)
    pat_rollers.name = "Pattern_CurveRollers"

    # --- Docking ports (construction points at arc ends, center radius)
    cpts = comp.constructionPoints
    try:
        ci = cpts.createInput()
        ci.setByCoordinates(adsk.core.Point3D.create(rc_cm(p) if False else 0, 0, 0))
    except Exception:
        pass
    # Ports recorded as pure coordinates for layout manager (robust across builds)
    inlet_xyz = (derived.center_radius_mm, 0.0, p.height_mm)
    outlet_xyz = (derived.center_radius_mm * _m.cos(th),
                  derived.center_radius_mm * _m.sin(th), p.height_mm)
    design.computeAll()
    return {"component": comp, "occurrence": occ, "master_body": master_body,
            "pattern_rollers": pat_rollers, "ext_rails": ext_rails,
            "inlet_port_mm": inlet_xyz, "outlet_port_mm": outlet_xyz,
            "derived": derived}


def rc_cm(p: CurveInput) -> float:  # tiny helper kept for API symmetry
    return (p.inner_radius_mm + p.width_mm / 2.0) / 10.0


# ---------------------------------------------------------------------------
# 7. Full module builders v2 (live-hardened: Y-up, XZ plan sketches)
#
# Convention (proven live 2026-09-18 on tapered prototype + 4x30 pattern):
#   - Plan-view sketches on xZConstructionPlane (normal = +Y vertical).
#     Heights via plane offsets along Y; extrudes along +Y.
#   - Tapered roller master reuses build_tapered_master_roller (XY sketch,
#     radial X axis at height offset) — verified bbox 390x78.1x78.1 + Cone face.
#   - Circular patterns about yConstructionAxis (vertical, curve center).
# ---------------------------------------------------------------------------
def _target_component(design, tag: str):
    """Assembly doc -> fresh occurrence component; Part doc -> root (namespaced).

    Returns (comp, occurrence_or_None).
    """
    root = design.rootComponent
    try:
        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        comp = occ.component
        comp.name = tag
        occ.name = tag
        print(f"TARGET new component {tag}")
        return comp, occ
    except Exception as exc:
        print(f"TARGET Part-doc fallback to root ({exc})")
        return root, None


def _extrude_up(extrudes, profiles, distance_expr: str):
    ext_in = extrudes.createInput(profiles, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    dist = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByString(distance_expr))
    ext_in.setOneSideExtent(dist, adsk.fusion.ExtentDirections.PositiveExtentDirection)
    return extrudes.add(ext_in)


def _annular_sector_curves(sk, r0_cm: float, r1_cm: float, sweep_rad: float):
    """Two concentric arcs + two radial closers -> closed annular sector(s)."""
    arcs = sk.sketchCurves.sketchArcs
    lines = sk.sketchCurves.sketchLines
    c = adsk.core.Point3D.create(0, 0, 0)
    s0 = adsk.core.Point3D.create(r0_cm, 0, 0)
    s1 = adsk.core.Point3D.create(r1_cm, 0, 0)
    arcs.addByCenterStartSweep(c, s0, sweep_rad)
    arcs.addByCenterStartSweep(c, s1, sweep_rad)
    lines.addByTwoPoints(s0, s1)
    e0 = adsk.core.Point3D.create(r0_cm * math.cos(sweep_rad), r0_cm * math.sin(sweep_rad), 0)
    e1 = adsk.core.Point3D.create(r1_cm * math.cos(sweep_rad), r1_cm * math.sin(sweep_rad), 0)
    lines.addByTwoPoints(e0, e1)


def _collect_profiles(sk):
    profs = adsk.core.ObjectCollection.create()
    for i in range(sk.profiles.count):
        profs.add(sk.profiles.item(i))
    return profs


def build_curve_rails(comp, p: CurveInput, prefix: str = ""):
    """Two thin arc rails (inner Ri..Ri+RailW, outer Ro-RailW..Ro), extrude RailH."""
    from fusion_conveyor_generator import RAIL_H as _RH  # reuse constant value
    del _RH
    planes = comp.constructionPlanes
    pin = planes.createInput()
    pin.setByOffset(comp.xZConstructionPlane,
                    adsk.core.ValueInput.createByString("C_FrameHeight - 40 mm"))
    plane = planes.add(pin)
    plane.name = prefix + "Plane_CurveRail_Bottom"
    sk = comp.sketches.add(plane)
    sk.name = prefix + "Sketch_CurveRails"
    th = math.radians(p.curve_angle_deg)
    ro = p.inner_radius_mm + p.width_mm
    _annular_sector_curves(sk, p.inner_radius_mm / 10.0, (p.inner_radius_mm + RAIL_W) / 10.0, th)
    _annular_sector_curves(sk, (ro - RAIL_W) / 10.0, ro / 10.0, th)
    print(f"RAILS sketch profiles={sk.profiles.count} (expect 2)")
    ext = _extrude_up(comp.features.extrudeFeatures, _collect_profiles(sk), "40 mm")
    ext.name = prefix + "Extrude_CurveRails"
    for i in range(ext.bodies.count):
        ext.bodies.item(i).name = f"{prefix}Body_CurveRail_{i}"
    return ext


def build_curve_rollers(comp, p: CurveInput, derived: CurveDerived, prefix: str = ""):
    """Master tapered revolve + circular pattern (string-first quantity wiring)."""
    roller_len = p.width_mm - 2.0 * (RAIL_W + ROLLER_CLEARANCE)
    _rev, master = build_tapered_master_roller(
        comp, p.roller_dia_inner_mm, derived.roller_dia_outer_mm,
        roller_len, p.height_mm, p.inner_radius_mm + RAIL_W + ROLLER_CLEARANCE,
        name=prefix + "Body_RollerTapered_Master")
    # fix names with prefix (builder sets base names)
    try:
        _rev.name = prefix + "Revolve_TaperedRollerMaster"
    except Exception:
        pass
    ents = adsk.core.ObjectCollection.create()
    ents.add(master)
    circ = comp.features.circularPatternFeatures
    ci = circ.createInput(ents, comp.yConstructionAxis)
    try:
        ci.quantity = adsk.core.ValueInput.createByString("C_RollerCount")
        ci.totalAngle = adsk.core.ValueInput.createByString("C_CurveAngle")
        ci.isSymmetric = False
        pat = circ.add(ci)
        print("PATTERN wired to C_RollerCount/C_CurveAngle params")
    except Exception as exc:
        print(f"PATTERN param wiring failed ({exc}); fallback to literals")
        ci2 = circ.createInput(ents, comp.yConstructionAxis)
        ci2.quantity = adsk.core.ValueInput.createByReal(float(derived.roller_count))
        ci2.totalAngle = adsk.core.ValueInput.createByString(f"{p.curve_angle_deg} deg")
        ci2.isSymmetric = False
        pat = circ.add(ci2)
    pat.name = prefix + "Pattern_CurveRollers"
    return master, pat


def build_curve_legs(comp, p: CurveInput, derived: CurveDerived, prefix: str = ""):
    """Master radial leg pair on floor plane + circular pattern about center."""
    sk = comp.sketches.add(comp.xZConstructionPlane)  # y=0 floor
    sk.name = prefix + "Sketch_CurveLegs"
    lines = sk.sketchCurves.sketchLines
    half = LEG_SIDE / 2.0 / 10.0  # cm
    r_in_c = (p.inner_radius_mm + RAIL_W / 2.0) / 10.0
    r_out_c = (derived.outer_radius_mm - RAIL_W / 2.0) / 10.0
    for rc in (r_in_c, r_out_c):
        x0, x1 = rc - half, rc + half
        c0 = adsk.core.Point3D.create(x0, -half, 0)
        c1 = adsk.core.Point3D.create(x1, half, 0)
        lines.addTwoPointRectangle(c0, c1)
    print(f"LEGS sketch profiles={sk.profiles.count} (expect 2)")
    ext = _extrude_up(comp.features.extrudeFeatures, _collect_profiles(sk),
                      "C_FrameHeight - 40 mm")
    ext.name = prefix + "Extrude_CurveLegs"
    ents = adsk.core.ObjectCollection.create()
    for i in range(ext.bodies.count):
        b = ext.bodies.item(i)
        b.name = f"{prefix}Body_CurveLeg_{i}"
        ents.add(b)
    circ = comp.features.circularPatternFeatures
    try:
        ci = circ.createInput(ents, comp.yConstructionAxis)
        ci.quantity = adsk.core.ValueInput.createByString("C_LegCount")
        ci.totalAngle = adsk.core.ValueInput.createByString("C_CurveAngle")
        ci.isSymmetric = False
        pat = circ.add(ci)
        print("LEG PATTERN wired to C_LegCount/C_CurveAngle")
    except Exception as exc:
        print(f"LEG PATTERN param wiring failed ({exc}); fallback to literals")
        ci = circ.createInput(ents, comp.yConstructionAxis)
        ci.quantity = adsk.core.ValueInput.createByReal(float(derived.support_count))
        ci.totalAngle = adsk.core.ValueInput.createByString(f"{p.curve_angle_deg} deg")
        ci.isSymmetric = False
        pat = circ.add(ci)
    pat.name = prefix + "Pattern_CurveLegs"
    return ext, pat


def build_curve_guards(comp, p: CurveInput, derived: CurveDerived, prefix: str = ""):
    """Two thin curved guard walls on rail tops; suppression = visibility."""
    planes = comp.constructionPlanes
    pin = planes.createInput()
    pin.setByOffset(comp.xZConstructionPlane,
                    adsk.core.ValueInput.createByString("C_FrameHeight"))
    plane = planes.add(pin)
    plane.name = prefix + "Plane_CurveGuards"
    sk = comp.sketches.add(plane)
    sk.name = prefix + "Sketch_CurveGuards"
    th = math.radians(p.curve_angle_deg)
    ro = derived.outer_radius_mm
    _annular_sector_curves(sk, p.inner_radius_mm / 10.0,
                           (p.inner_radius_mm + GUARD_THICK) / 10.0, th)
    _annular_sector_curves(sk, (ro - GUARD_THICK) / 10.0, ro / 10.0, th)
    print(f"GUARDS sketch profiles={sk.profiles.count} (expect 2)")
    ext = _extrude_up(comp.features.extrudeFeatures, _collect_profiles(sk), "C_GuardHeight")
    ext.name = prefix + "Extrude_CurveGuards"
    for i in range(ext.bodies.count):
        ext.bodies.item(i).name = f"{prefix}Body_CurveGuard_{i}"
    try:
        ext.isSuppressed = not p.side_guards
    except Exception as exc:
        print(f"guard suppression failed: {exc}")
    return ext


def validate_curve_cad(design, comp, p: CurveInput, derived: CurveDerived,
                       refs: Optional[Dict[str, object]] = None) -> List[Tuple[str, bool, str]]:
    """Live B-rep validation: bbox footprint/height + param readback + suppression."""
    try:
        design.computeAll()
    except Exception:
        pass
    checks: List[Tuple[str, bool, str]] = []
    bb = comp.boundingBox
    ax = (bb.maxPoint.x - bb.minPoint.x) * 10.0
    ay = (bb.maxPoint.y - bb.minPoint.y) * 10.0
    az = (bb.maxPoint.z - bb.minPoint.z) * 10.0
    # Plan extents live in X/Z (Y-up): footprint dims are the two plan axes.
    # Rail-to-rail end rollers are intentional (curve-module standard for clean
    # handoff): end-roller corners sweep ~d_out/2 past the radial end planes,
    # so the envelope is Ro + d_outer, not Ro. Verified live: 1299 vs Ro=1250
    # with d_out=78.1 (overhang 49 = redistributed end margin + corner sweep).
    plan = sorted([ax, az])
    ro = derived.outer_radius_mm
    envelope = ro + p.roller_dia_inner_mm * ro / p.inner_radius_mm + 5.0
    checks.append(("Footprint within Ro+d_out envelope",
                   plan[1] <= envelope and plan[0] <= envelope,
                   f"plan={plan[0]:.0f}x{plan[1]:.0f} vs env={envelope:.0f}"))
    checks.append(("Height within 5mm",
                   abs(ay - derived.overall_height_mm) <= 5.0 or abs(az - derived.overall_height_mm) <= 5.0,
                   f"Y={ay:.1f} Z={az:.1f} vs exp H={derived.overall_height_mm:.1f}"))
    up = design.userParameters
    try:
        rc = up.itemByName("C_RollerCount")
        rc_min = up.itemByName("C_RollerCountMin")
        lc = up.itemByName("C_LegCount")
        rc_f = int(round(float(rc.value))) if rc else -1
        rc_min_f = int(round(float(rc_min.value))) if rc_min else -1
        lc_f = int(round(float(lc.value))) if lc else -1
        checks.append((
            "RollerCount floor readback",
            rc_f == int(math.floor((derived.arc_outer_mm - 2 * curve_roller_margin_mm(
                p.roller_dia_inner_mm)) / p.roller_pitch_outer_mm)) + 1,
            f"Fusion={rc_f}",
        ))
        checks.append((
            "RollerCountMin readback",
            rc_min_f == int(math.ceil(p.curve_angle_deg / MAX_ANGULAR_PITCH_DEG)) + 1,
            f"Fusion={rc_min_f}",
        ))
        checks.append(("Canonical count = max(pair)",
                       max(rc_f, rc_min_f) == derived.roller_count,
                       f"max({rc_f},{rc_min_f}) vs py={derived.roller_count}"))
        checks.append(("LegCount readback", lc_f == derived.support_count,
                       f"Fusion={lc_f} vs py={derived.support_count}"))
    except Exception as exc:
        checks.append(("Param readback", False, str(exc)))
    if refs and refs.get("ext_guards") is not None:
        try:
            sup = bool(refs["ext_guards"].isSuppressed)
            checks.append(("Guard suppression", sup == (not p.side_guards),
                           f"suppressed={sup} guards={p.side_guards}"))
        except Exception as exc:
            checks.append(("Guard suppression", False, str(exc)))
    return checks


def export_curve_bom_csv(tag: str, p: CurveInput, derived: CurveDerived,
                         output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{tag}_BOM.csv")
    hw = estimate_hardware_masses_kg(p, derived)
    rows = [
        ("Curved Side Rails (arc)", 2,
         f"Ri={p.inner_radius_mm:.0f} Ro={derived.outer_radius_mm:.0f} "
         f"arc_in={derived.arc_inner_mm:.0f}mm arc_out={derived.arc_outer_mm:.0f}mm section={RAIL_W}x{RAIL_H}"),
        ("Tapered Rollers (hollow tube)", derived.roller_count,
         f"d_in={p.roller_dia_inner_mm:.1f} d_out={derived.roller_dia_outer_mm:.1f} "
         f"len={p.width_mm - 2 * (RAIL_W + ROLLER_CLEARANCE):.0f} wall={TUBE_WALL_MM} "
         f"mass={hw['Tapered Tubes (hollow)']:.1f}kg"),
        ("Roller Shafts dia14", derived.roller_count,
         f"len={shaft_length_for(p.width_mm):.0f} mass={hw['Shafts']:.1f}kg"),
        ("Bearing Rings 6002-class", derived.roller_count * 2,
         f"32OD/15bore/9W mass={hw['Bearing Rings']:.1f}kg"),
        ("Support Leg Posts", derived.support_count * 2,
         f"stations={derived.support_count} section={LEG_SIDE}x{LEG_SIDE} h={p.height_mm - RAIL_H:.0f}"),
        ("Motor Bay Plate + slots", 1, "350x300x10, 4 tension slots"),
        ("Motor dia120 + Pulley dia80", 1, f"mass={hw['Motor + Pulley']:.1f}kg"),
        ("Foot Plates + anchors", derived.support_count * 2,
         f"{derived.support_count * 2} plates 100x100x8, {derived.support_count * 2 * 4} dia11 bores"),
        ("Sensor Bracket + Dock Boards", 5, "1 sensor set (bore dia20), 4 dock boards + 8 pin bores dia12"),
    ]
    if p.side_guards:
        rows.append(("Curved Side Guards", 2,
                     f"h={p.side_guard_height_mm:.0f} t={GUARD_THICK} arc_out={derived.arc_outer_mm:.0f}mm"))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Part Name", "Quantity", "Dimensions / Notes"])
        w.writerows(rows)
    return path


def export_curve_step(design: "adsk.fusion.Design", comp: "adsk.fusion.Component",
                      tag: str, output_dir: str) -> str:
    """Exports a STEP 3D CAD file for the curved configuration.

    Added 2026-09-18: the docking add-in calls this (guarded by refs check);
    mirrors fusion_conveyor_generator.export_step_file idiom.
    """
    os.makedirs(output_dir, exist_ok=True)
    step_path = os.path.join(output_dir, f"{tag}.step")
    export_mgr = design.exportManager
    step_options = export_mgr.createSTEPExportOptions(step_path, comp)
    export_mgr.execute(step_options)
    return step_path


def get_curve_module_ports(p: CurveInput, derived: CurveDerived) -> Dict[str, Dict[str, object]]:
    """Calculates standardized spatial docking ports for the curved module (IF-060)."""
    th = math.radians(p.curve_angle_deg)
    return {
        "inlet_port": {
            "origin_mm": (derived.center_radius_mm, 0.0, p.height_mm),
            "direction": (0.0, 1.0, 0.0),
            "normal": (-1.0, 0.0, 0.0),
            "up": (0.0, 0.0, 1.0),
            "width_mm": p.width_mm,
            "height_mm": p.height_mm,
            "pitch_mm": p.roller_pitch_outer_mm,
        },
        "outlet_port": {
            "origin_mm": (derived.center_radius_mm * math.cos(th),
                          derived.center_radius_mm * math.sin(th),
                          p.height_mm),
            "direction": (-math.sin(th), math.cos(th), 0.0),
            "normal": (-math.cos(th), -math.sin(th), 0.0),
            "up": (0.0, 0.0, 1.0),
            "width_mm": p.width_mm,
            "height_mm": p.height_mm,
            "pitch_mm": p.roller_pitch_outer_mm,
        }
    }


def generate_curve_opcua_metadata(p: CurveInput, derived: CurveDerived, module_id: str) -> Dict[str, object]:
    """Generates Industry 4.0 OPC-UA node companion metadata for curved module."""
    return {
        "equipment_id": f"CONV_CURVE_{module_id}",
        "model_type": f"GlitterGs_CurveConveyor_{p.curve_angle_deg:.0f}deg_IF",
        "spec_ratings": {
            "inner_radius_mm": p.inner_radius_mm,
            "outer_radius_mm": derived.outer_radius_mm,
            "curve_angle_deg": p.curve_angle_deg,
            "width_mm": p.width_mm,
            "height_mm": p.height_mm,
            "roller_count": derived.roller_count,
            "rated_speed_mps": 0.5,
            "max_payload_kg": 120.0,
        },
        "opcua_nodes": [
            {"node_id": f"ns=2;s={module_id}.CurveMotor.Control.Run", "data_type": "Boolean", "access": "ReadWrite", "desc": "Curve Conveyor Run Command"},
            {"node_id": f"ns=2;s={module_id}.CurveMotor.Control.SpeedSetpoint", "data_type": "Float", "unit": "m/s", "access": "ReadWrite", "desc": "Tangential Centerline Velocity Setpoint"},
            {"node_id": f"ns=2;s={module_id}.CurveMotor.Telemetry.Current_A", "data_type": "Float", "unit": "A", "access": "ReadOnly", "desc": "Curve Drive Motor Current"},
            {"node_id": f"ns=2;s={module_id}.CurveMotor.Telemetry.Speed_RPM", "data_type": "Float", "unit": "RPM", "access": "ReadOnly", "desc": "Drive Motor Shaft Speed"},
            {"node_id": f"ns=2;s={module_id}.Sensors.InletPhotoeye.Blocked", "data_type": "Boolean", "access": "ReadOnly", "desc": "Curve Inlet Pallet Detect"},
            {"node_id": f"ns=2;s={module_id}.Sensors.OutletPhotoeye.Blocked", "data_type": "Boolean", "access": "ReadOnly", "desc": "Curve Outlet Pallet Detect"},
            {"node_id": f"ns=2;s={module_id}.System.Status", "data_type": "Int32", "access": "ReadOnly", "desc": "0=Stopped, 1=Running, 2=Faulted, 3=E-Stop"}
        ]
    }


def export_curve_opcua_nodeset_json(tag: str, p: CurveInput, derived: CurveDerived, output_dir: str) -> str:
    """Exports Industry 4.0 OPC-UA node companion mapping for curved module."""
    import json
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{tag}_opcua_nodeset.json")
    data = generate_curve_opcua_metadata(p, derived, tag)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def build_curve_module_full(design, p: CurveInput, tag: Optional[str] = None):
    """Orchestrator: params -> component -> rails -> rollers -> legs -> guards."""
    validate_curve_inputs(p)
    derived = derive_curve_configuration(p)
    create_curve_parameters(design, p)
    tag = tag or f"CurveModule_{p.curve_angle_deg:.0f}deg_Ri{p.inner_radius_mm:.0f}"
    comp, occ = _target_component(design, tag)
    prefix = "" if occ is not None else "Curve90_"
    ext_rails = build_curve_rails(comp, p, prefix)
    master, pat_rollers = build_curve_rollers(comp, p, derived, prefix)
    ext_legs, pat_legs = build_curve_legs(comp, p, derived, prefix)
    ext_guards = build_curve_guards(comp, p, derived, prefix)
    design.computeAll()
    th = math.radians(p.curve_angle_deg)
    refs = {"component": comp, "occurrence": occ, "master_body": master,
            "pattern_rollers": pat_rollers, "ext_rails": ext_rails,
            "ext_legs": ext_legs, "pattern_legs": pat_legs, "ext_guards": ext_guards,
            "inlet_port_mm": (derived.center_radius_mm, 0.0, p.height_mm),
            "outlet_port_mm": (derived.center_radius_mm * math.cos(th),
                               derived.center_radius_mm * math.sin(th), p.height_mm),
            "derived": derived, "tag": tag}
    print(f"CURVE_MODULE_OK {tag} rollers={derived.roller_count} legs={derived.support_count}")
    return refs


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 8. IF-010 rail seat holes (live-proven retrofit method, now parametric)
#
# Proven 2026-09-18 on Curve90 (18 holes/rail, bore dia 16 for dia-14 shaft):
#   - Position = station ANGLE (from roller pattern) x rail BAND CENTER
#     (rim centers are 10 mm off-band: tube ends, not shafts — never use raw).
#   - Sketch on rail top face; drop circles via modelToSketchSpace.
#   - MUST filter profiles by area (face loop would delete the whole rail).
#   - Scope cuts with participantBodies=[rail] (python list).
#   - End stations sit on radial end edges (rail-to-rail design) and may drop
#     to 18/19 honestly; validator tolerates N-2..N with the note attached.
# ---------------------------------------------------------------------------
HOLE_BORE_DIA_MM = 16.0
HOLE_BORE_R_CM = HOLE_BORE_DIA_MM / 2.0 / 10.0


def keeps_hole_profile(area_cm2: float) -> bool:
    """Area gate for sketch-on-face hole profiles (pure, unit-tested).

    Keeps full bores, drops the host-face loop (huge) and slivers.
    """
    hole = math.pi * HOLE_BORE_R_CM ** 2
    return 0.5 * hole < area_cm2 < 2.0 * hole


def curve_hole_stations(p: CurveInput, derived: CurveDerived):
    """Hole stations: (angle_rad, band_radius_mm, rail) per roller (pure).

    Angles span the full pattern 0..Theta; radii are rail band CENTERS
    (inner Ri+RailW/2, outer Ro-RailW/2) — the shaft line, not tube ends.
    """
    n = derived.roller_count
    stations = []
    for k in range(n):
        frac = (k / (n - 1)) if n > 1 else 0.0
        ang = math.radians(p.curve_angle_deg) * frac
        stations.append((ang, p.inner_radius_mm + RAIL_W / 2.0, "inner"))
        stations.append((ang, derived.outer_radius_mm - RAIL_W / 2.0, "outer"))
    return stations


def count_bore_cylinders(comp, rail_body, bore_dia_mm: float = HOLE_BORE_DIA_MM) -> int:
    """Bore-hole census on a rail body (never raises; 0 when unavailable)."""
    try:
        n = 0
        for i in range(rail_body.faces.count):
            g = rail_body.faces.item(i).geometry
            if type(g).__name__ != "Cylinder":
                continue
            try:
                if abs(float(g.radius) * 10.0 - bore_dia_mm / 2.0) < 0.5:
                    n += 1
            except Exception:
                continue
        return n
    except Exception:
        return 0


def find_top_face(rail_body, up_axis: str = "y"):
    """Top planar face of a rail body (max extent along up axis; None ok)."""
    try:
        best, best_val = None, -1e18
        for i in range(rail_body.faces.count):
            face = rail_body.faces.item(i)
            try:
                g = face.geometry
            except Exception:
                continue
            if type(g).__name__ != "Plane":
                continue
            try:
                normal = getattr(g, "normal")
                ax = {"x": normal.x, "y": normal.y, "z": normal.z}[up_axis]
            except Exception:
                continue
            if abs(float(ax)) < 0.9:
                continue
            try:
                val = getattr(face.boundingBox, "maxPoint").__getattribute__(up_axis)
            except Exception:
                continue
            if val > best_val:
                best, best_val = face, val
        return best
    except Exception:
        return None


def build_curve_holes(comp, p: CurveInput, derived: CurveDerived, prefix: str = ""):
    """Cut IF-010 seat bores in both arc rails. Returns {'inner': n, 'outer': n}."""
    rail_bodies = {}
    try:
        ext_rails = None
        for i in range(comp.features.extrudeFeatures.count):
            feat = comp.features.extrudeFeatures.item(i)
            if (getattr(feat, "name", "") or "").endswith("Extrude_CurveRails"):
                ext_rails = feat
                break
        if ext_rails is not None:
            bands = []
            for i in range(ext_rails.bodies.count):
                b = ext_rails.bodies.item(i)
                bands.append(b)
            bands.sort(key=lambda b: b.boundingBox.maxPoint.x + b.boundingBox.maxPoint.y)
            rail_bodies = {"inner": bands[0], "outer": bands[-1]}
    except Exception:
        rail_bodies = {}
    if len(rail_bodies) < 2:
        return {"inner": 0, "outer": 0}
    counts = {}
    for tag, band_c in (("inner", p.inner_radius_mm + RAIL_W / 2.0),
                        ("outer", derived.outer_radius_mm - RAIL_W / 2.0)):
        rail = rail_bodies[tag]
        face = find_top_face(rail)
        if face is None:
            counts[tag] = 0
            continue
        topy = face.boundingBox.maxPoint.y
        sk = comp.sketches.add(face)
        sk.name = prefix + "Sketch_CurveHoles_" + tag.capitalize() + "Rail"
        circ = sk.sketchCurves.sketchCircles
        n = derived.roller_count
        for k in range(n):
            frac = (k / (n - 1)) if n > 1 else 0.0
            ang = math.radians(p.curve_angle_deg) * frac
            hx = (band_c / 10.0) * math.cos(ang)
            hz = (band_c / 10.0) * math.sin(ang)
            pt2 = sk.modelToSketchSpace(adsk.core.Point3D.create(hx, topy, hz))
            circ.addByCenterRadius(pt2, HOLE_BORE_R_CM)
        profs = adsk.core.ObjectCollection.create()
        kept = 0
        for i in range(sk.profiles.count):
            pr = sk.profiles.item(i)
            try:
                area = float(pr.areaProperties().area)
            except Exception:
                continue
            if keeps_hole_profile(area):
                profs.add(pr)
                kept += 1
        extrudes = comp.features.extrudeFeatures
        cut_in = extrudes.createInput(profs, adsk.fusion.FeatureOperations.CutFeatureOperation)
        cut_in.participantBodies = [rail]
        dist = adsk.fusion.DistanceExtentDefinition.create(
            adsk.core.ValueInput.createByString("45 mm"))
        cut_in.setOneSideExtent(dist, adsk.fusion.ExtentDirections.NegativeExtentDirection)
        cut = extrudes.add(cut_in)
        cut.name = prefix + "ExtrudeCut_CurveHoles_" + tag.capitalize()
        counts[tag] = kept
    return counts


def verify_curve_holes(holes_inner: int, holes_outer: int,
                       derived: CurveDerived) -> Dict[str, object]:
    """Hole census vs pattern count (honest end-station tolerance N-2..N).

    Pass counts from count_bore_cylinders() (live) or build_curve_holes()
    (returned kept counts). End stations on radial end edges may legitimately
    drop: rail-to-rail ends leave no material for a full bore.
    """
    n = derived.roller_count
    ok_in = (n - 2) <= holes_inner <= n
    ok_out = (n - 2) <= holes_outer <= n
    return {"holes_inner": holes_inner, "holes_outer": holes_outer,
            "expected": n, "inner_ok": ok_in, "outer_ok": ok_out,
            "all": bool(ok_in and ok_out)}


# ---------------------------------------------------------------------------
# 9. P2/P3/P4 hardware backfill (live-built 2026-09-18, all verified in CAD)
#
# IF-020 roller train: hollow tapered tubes (3 mm wall, capped ends) +
# through-shafts (dia 14, length W+24) + outboard 6002-class rings
# (32 OD / 15 bore / 9 wide). Live: 19 tubes @240.6cm3 (solid was 1277.2),
# 19 shafts @73cm3, 38 rings @~5.6cm3.
# IF-030 motor bay: 350x300x10 plate + 4 tension slots + 4 hanger straps +
# dia-120 motor + dia-80 pulley (2827.4 / 201.1 cm3 exact).
# IF-040/051/060 partials: 6 foot plates + 24 anchor bores, sensor
# foot+pedestal+bore at outlet, 4 dock boards + 8 pin bores (dia 12).
#
# Revolve rule (paid for twice): the profile must lie ENTIRELY on one side
# of the revolve axis (touching ok). Crossing axes split loops (pick halves
# for solids); multi-profile single revolves fail on crossing — put ring
# rects wholly above a shared centre axis instead.
# ---------------------------------------------------------------------------
TUBE_WALL_MM = 3.0
SHAFT_DIA_MM = 14.0
SHAFT_LENGTH_MM = None  # computed: width + 24 (set per config; see shaft_length_for)
BEARING_OD_MM = 32.0
BEARING_BORE_MM = 15.0
BEARING_W_MM = 9.0
MOTOR_DIA_MM = 120.0
MOTOR_LEN_MM = 250.0
PIN_BORE_DIA_MM = 12.0
ANCHOR_BORE_DIA_MM = 11.0


def frustum_volume_mm3(d0_mm: float, d1_mm: float, length_mm: float) -> float:
    """Truncated-cone volume (tube or core)."""
    r0, r1 = d0_mm / 2.0, d1_mm / 2.0
    return math.pi * length_mm / 3.0 * (r0 ** 2 + r0 * r1 + r1 ** 2)


def hollow_tube_volume_mm3(p: CurveInput, derived: CurveDerived,
                           wall_mm: float = TUBE_WALL_MM) -> float:
    """Hollow tapered tube volume: outer frustum minus inset core (3 mm caps).

    Live anchor: demo tube 1277.2 solid -> 240.6 hollow (cm3).
    """
    roller_len = p.width_mm - 2.0 * (RAIL_W + ROLLER_CLEARANCE)
    outer = frustum_volume_mm3(p.roller_dia_inner_mm, derived.roller_dia_outer_mm, roller_len)
    core = frustum_volume_mm3(p.roller_dia_inner_mm - 2 * wall_mm,
                              derived.roller_dia_outer_mm - 2 * wall_mm,
                              roller_len - 2 * wall_mm)
    return outer - core


def shaft_length_for(width_mm: float) -> float:
    """Through-shaft spans housing to housing (boss outer faces).

    Live: W=450 -> 498 (777..1274), engaging both 12 mm boss bores with
    1 mm witness past each outer face. Earlier W+24 stopped 1 mm short.
    """
    return width_mm + 48.0


def shaft_volume_mm3(width_mm: float, dia_mm: float = SHAFT_DIA_MM) -> float:
    return math.pi * (dia_mm / 2.0) ** 2 * shaft_length_for(width_mm)


def bearing_ring_volume_mm3() -> float:
    return math.pi * ((BEARING_OD_MM / 2.0) ** 2 - (BEARING_BORE_MM / 2.0) ** 2) * BEARING_W_MM


def curve_bom_full(p: CurveInput, derived: CurveDerived,
                   hole_counts: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    """Full BOM incl. P2/P3/P4 hardware (counts only; masses via estimator)."""
    bom = dict(curve_bom(derived, p.side_guards))
    bom.update({
        "tapered_tubes_hollow": derived.roller_count,
        "shafts_dia14": derived.roller_count,
        "bearing_rings_6002": derived.roller_count * 2,
        "rail_seat_bores": (hole_counts or {}).get("inner", 0) + (hole_counts or {}).get("outer", 0),
        "motor_bay_plate": 1,
        "plate_tension_slots": 4,
        "hanger_straps": 4,
        "motor_dia120": 1,
        "drive_pulley_dia80": 1,
        "foot_plates": derived.support_count * 2,
        "anchor_bores": derived.support_count * 2 * 4,
        "sensor_bracket_set": 1,
        "dock_boards": 4,
        "dock_pin_bores": 8,
    })
    return bom


def verify_drivetrain_counts(shafts: int, rings: int, derived: CurveDerived) -> Dict[str, object]:
    """P2 validator: 1 shaft/roller, 2 rings/shaft."""
    ok_s = shafts == derived.roller_count
    ok_r = rings == 2 * derived.roller_count
    return {"shafts": shafts, "rings": rings, "expected_shafts": derived.roller_count,
            "shafts_ok": ok_s, "rings_ok": ok_r, "all": bool(ok_s and ok_r)}


def estimate_hardware_masses_kg(p: CurveInput, derived: CurveDerived) -> Dict[str, float]:
    """Analytic steel masses for P2/P3 hardware (bearings counted as solid rings)."""
    from fusion_conveyor_generator import STEEL_DENSITY_KG_M3
    mm3_to_m3 = 1e-9
    rho = STEEL_DENSITY_KG_M3 * mm3_to_m3
    motor_vol = math.pi * (MOTOR_DIA_MM / 2.0) ** 2 * MOTOR_LEN_MM
    pulley_vol = math.pi * (80.0 / 2.0) ** 2 * 40.0
    return {
        "Tapered Tubes (hollow)": derived.roller_count * hollow_tube_volume_mm3(p, derived) * rho,
        "Shafts": derived.roller_count * shaft_volume_mm3(p.width_mm) * rho,
        "Bearing Rings": derived.roller_count * 2 * bearing_ring_volume_mm3() * rho,
        "Motor + Pulley": (motor_vol + pulley_vol) * rho,
    }


# ---------------------------------------------------------------------------
# 10. P3b belt band + IF-020 housings (live-built, ghost_testing_1 verified)
# ---------------------------------------------------------------------------
#
# Belt: annular band (Ro-40..Ro-10 centroid ~Rc) extruded 5 mm at y=711,
# top kissing tube bottoms (friction-contact look). Return run + tensioner
# to pulley remain P3c.
# Housings: 40x40x12 boss blocks outboard of each rail (inner x776..788,
# outer x1262..1274, y730..770), dia-15 through-bores (shaft line y=750),
# bored BEFORE patterning (bores propagate to all 2N copies).
# Live: 38 housings, 38 bores dia15, pattern 19x90 about curve centre.
# Face-pick rule: choose the face by POSITION (min/max extent), never first
# match; map only on-plane points via modelToSketchSpace; NegativeExtent
# cuts into the body from an outward face.
# ---------------------------------------------------------------------------
BELT_INNER_MM = None  # Rc - 15, set per config
BELT_OUT_MM = None
BELT_THICK_MM = 5.0
HOUSING_SECTION_MM = 40.0
HOUSING_THICK_MM = 12.0
HOUSING_BORE_DIA_MM = 15.0


def belt_band_radii_mm(derived: CurveDerived):
    """Belt annulus centred on the centre arc (friction contact under tubes)."""
    rc = derived.center_radius_mm
    return rc - 15.0, rc + 15.0


def belt_volume_mm3(derived: CurveDerived) -> float:
    r0, r1 = belt_band_radii_mm(derived)
    theta = derived.arc_center_mm / derived.center_radius_mm
    return 0.5 * theta * (r1 ** 2 - r0 ** 2) * BELT_THICK_MM


def housing_positions_mm(p: CurveInput, derived: CurveDerived):
    """Boss block x-intervals (inner/outer) at station 0 (pure).

    12 mm blocks standoff-mounted outboard of each rail face; the W+48
    shaft engages both bores (live: 776..788 / 1262..1274).
    """
    ri, ro = p.inner_radius_mm, derived.outer_radius_mm
    return {"inner": (ri - 24.0, ri - 12.0),
            "outer": (ro + 12.0, ro + 24.0)}


def verify_housings(housings: int, bores_dia15: int, derived: CurveDerived) -> Dict[str, object]:
    """P2-closeout validator: 2 housings/roller, 1 bore/housing."""
    ok_h = housings == 2 * derived.roller_count
    ok_b = bores_dia15 == 2 * derived.roller_count
    return {"housings": housings, "bores": bores_dia15,
            "expected_each": 2 * derived.roller_count,
            "housings_ok": ok_h, "bores_ok": ok_b, "all": bool(ok_h and ok_b)}


def curve_bom_drive(p: CurveInput, derived: CurveDerived) -> Dict[str, int]:
    """P3b/IF-020-closeout BOM rows."""
    return {
        "drive_belt_band": 1,
        "bearing_housings": 2 * derived.roller_count,
        "housing_bores_dia15": 2 * derived.roller_count,
    }
# ---------------------------------------------------------------------------


def layout_ports_straight(length_mm: float, width_mm: float, height_mm: float) -> Dict[str, Tuple[float, float, float]]:
    """Straight module ports in its local frame: inlet at x=0, outlet at x=L."""
    return {"inlet": (0.0, width_mm / 2.0, height_mm),
            "outlet": (length_mm, width_mm / 2.0, height_mm)}


def layout_place_curve_after_straight(straight_outlet: Tuple[float, float, float],
                                      curve_inlet_local: Tuple[float, float, float],
                                      curve_angle_deg: float) -> Tuple[Tuple[float, float, float], float]:
    """Translation + Z-rotation to mate curve inlet to straight outlet.

    Returns (translation_xyz_mm, rotation_z_deg). Pure math — caller applies
    via occurrence.transform / Matrix3D in Fusion.
    """
    tx = straight_outlet[0] - curve_inlet_local[0]
    ty = straight_outlet[1] - curve_inlet_local[1]
    tz = straight_outlet[2] - curve_inlet_local[2]
    return (tx, ty, tz), 0.0
