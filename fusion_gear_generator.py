from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

try:
    import adsk.core  # type: ignore
    import adsk.fusion  # type: ignore
except ImportError:  # pragma: no cover - allows unit tests outside Fusion
    adsk = None


DEG_TO_RAD = math.pi / 180.0


@dataclass(frozen=True)
class GearInput:
    gear_type: str
    mn: float
    z1: int
    z2: int
    pressure_angle_deg: float
    face_width: float
    helix_angle_deg: float = 0.0


@dataclass(frozen=True)
class GearDerived:
    ratio: float
    beta_rad: float
    mt: float
    d1: float
    d2: float
    center_distance: float


def _canonical_gear_type(gear_type: str) -> str:
    normalized = gear_type.strip().lower()
    if normalized not in {"spur", "helical"}:
        raise ValueError("gear_type must be 'spur' or 'helical'.")
    return normalized


def validate_inputs(params: GearInput) -> None:
    gear_type = _canonical_gear_type(params.gear_type)
    if not (1.5 <= params.mn <= 3.0):
        raise ValueError("mn must be within 1.5-3.0 mm.")
    if not (18 <= params.z1 <= 40):
        raise ValueError("z1 must be within 18-40.")
    if not (30 <= params.z2 <= 80):
        raise ValueError("z2 must be within 30-80.")
    if abs(params.pressure_angle_deg - 20.0) > 1e-6:
        raise ValueError("pressure_angle_deg must be 20 degrees.")
    if not (6.0 <= params.face_width <= 15.0):
        raise ValueError("face_width must be within 6-15 mm.")
    if not (0.0 <= params.helix_angle_deg <= 30.0):
        raise ValueError("helix_angle_deg must be within 0-30 degrees.")
    if gear_type == "spur" and abs(params.helix_angle_deg) > 1e-6:
        raise ValueError("spur gears must use helix_angle_deg=0.")


def derive_geometry(params: GearInput) -> GearDerived:
    validate_inputs(params)
    beta_rad = params.helix_angle_deg * DEG_TO_RAD

    # Normal-module convention for both types:
    # transverse module mt = mn / cos(beta), pitch diameter d = mt * z.
    mt = params.mn / max(math.cos(beta_rad), 1e-9)
    d1 = mt * params.z1
    d2 = mt * params.z2
    ratio = params.z2 / params.z1
    center_distance = (d1 + d2) / 2.0

    return GearDerived(
        ratio=ratio,
        beta_rad=beta_rad,
        mt=mt,
        d1=d1,
        d2=d2,
        center_distance=center_distance,
    )


def verify_pair(params: GearInput, derived: Optional[GearDerived] = None, tol: float = 1e-6) -> Dict[str, bool]:
    d = derived or derive_geometry(params)
    checks = {
        "tooth_count_driver": params.z1 >= 18,
        "tooth_count_driven": params.z2 >= 30,
        "ratio": abs(d.ratio - (params.z2 / params.z1)) <= tol,
        "pitch_diameter_driver": abs(d.d1 - (d.mt * params.z1)) <= tol,
        "pitch_diameter_driven": abs(d.d2 - (d.mt * params.z2)) <= tol,
        "center_distance": abs(d.center_distance - ((d.d1 + d.d2) / 2.0)) <= tol,
        "pressure_angle": abs(params.pressure_angle_deg - 20.0) <= tol,
        "helix_consistency": (
            abs(params.helix_angle_deg) <= tol if _canonical_gear_type(params.gear_type) == "spur" else params.helix_angle_deg > tol
        ),
    }
    checks["all"] = all(checks.values())
    return checks


class FusionGearPairGenerator:
    def __init__(self, app: "adsk.core.Application"):
        self.app = app
        self.ui = app.userInterface
        self.design = adsk.fusion.Design.cast(app.activeProduct)
        if not self.design:
            raise RuntimeError("Active product must be a Fusion design.")
        self.root = self.design.rootComponent

    @staticmethod
    def _mm(value: float) -> "adsk.core.ValueInput":
        return adsk.core.ValueInput.createByReal(value / 10.0)

    def _delete_stale(self) -> None:
        stale_occurrences = [
            occ for occ in self.root.occurrences if occ.component and occ.component.name.startswith("GG_")
        ]
        for occ in stale_occurrences:
            occ.deleteMe()

        stale_joints = [joint for joint in self.root.joints if joint.name.startswith("GG_")]
        for joint in stale_joints:
            joint.deleteMe()

    def _new_component(self, name: str, x_mm: float, y_mm: float = 0.0, z_mm: float = 0.0) -> Tuple["adsk.fusion.Component", "adsk.fusion.Occurrence"]:
        transform = adsk.core.Matrix3D.create()
        transform.translation = adsk.core.Vector3D.create(x_mm / 10.0, y_mm / 10.0, z_mm / 10.0)
        occurrence = self.root.occurrences.addNewComponent(transform)
        component = occurrence.component
        component.name = name
        return component, occurrence

    def _create_gear_blank(self, component: "adsk.fusion.Component", outer_diameter_mm: float, face_width_mm: float) -> "adsk.fusion.ExtrudeFeature":
        sketch = component.sketches.add(component.xYConstructionPlane)
        center = adsk.core.Point3D.create(0, 0, 0)
        sketch.sketchCurves.sketchCircles.addByCenterRadius(center, outer_diameter_mm / 20.0)
        profile = sketch.profiles.item(0)

        extrudes = component.features.extrudeFeatures
        ext_input = extrudes.createInput(profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_input.setDistanceExtent(False, self._mm(face_width_mm))
        return extrudes.add(ext_input)

    def _build_gap_profile(self, sketch: "adsk.fusion.Sketch", root_radius_mm: float, outer_radius_mm: float, center_angle_rad: float, angular_width_rad: float) -> None:
        curves = sketch.sketchCurves
        lines = curves.sketchLines
        arcs = curves.sketchArcs

        a0 = center_angle_rad - angular_width_rad / 2.0
        a1 = center_angle_rad + angular_width_rad / 2.0

        p_outer_0 = adsk.core.Point3D.create((outer_radius_mm * math.cos(a0)) / 10.0, (outer_radius_mm * math.sin(a0)) / 10.0, 0)
        p_outer_1 = adsk.core.Point3D.create((outer_radius_mm * math.cos(a1)) / 10.0, (outer_radius_mm * math.sin(a1)) / 10.0, 0)
        p_root_0 = adsk.core.Point3D.create((root_radius_mm * math.cos(a0)) / 10.0, (root_radius_mm * math.sin(a0)) / 10.0, 0)
        p_root_1 = adsk.core.Point3D.create((root_radius_mm * math.cos(a1)) / 10.0, (root_radius_mm * math.sin(a1)) / 10.0, 0)

        lines.addByTwoPoints(p_root_0, p_outer_0)
        arcs.addByThreePoints(p_outer_0, adsk.core.Point3D.create((outer_radius_mm * math.cos(center_angle_rad)) / 10.0, (outer_radius_mm * math.sin(center_angle_rad)) / 10.0, 0), p_outer_1)
        lines.addByTwoPoints(p_outer_1, p_root_1)
        arcs.addByThreePoints(p_root_1, adsk.core.Point3D.create((root_radius_mm * math.cos(center_angle_rad)) / 10.0, (root_radius_mm * math.sin(center_angle_rad)) / 10.0, 0), p_root_0)

    def _cut_spur_teeth(self, component: "adsk.fusion.Component", z: int, pitch_diameter_mm: float, mn_mm: float, face_width_mm: float) -> None:
        addendum = mn_mm
        dedendum = 1.25 * mn_mm
        outer_radius = (pitch_diameter_mm + 2 * addendum) / 2.0
        root_radius = max((pitch_diameter_mm - 2 * dedendum) / 2.0, 0.4 * pitch_diameter_mm / 2.0)

        sketch = component.sketches.add(component.xYConstructionPlane)
        tooth_pitch_angle = 2 * math.pi / z
        gap_angle = tooth_pitch_angle * 0.5
        self._build_gap_profile(sketch, root_radius, outer_radius, 0.0, gap_angle)

        profile = sketch.profiles.item(0)
        extrudes = component.features.extrudeFeatures
        cut_input = extrudes.createInput(profile, adsk.fusion.FeatureOperations.CutFeatureOperation)
        cut_input.setDistanceExtent(False, self._mm(face_width_mm))
        tooth_gap = extrudes.add(cut_input)

        entities = adsk.core.ObjectCollection.create()
        entities.add(tooth_gap)
        axis = component.zConstructionAxis

        patterns = component.features.circularPatternFeatures
        patt_input = patterns.createInput(entities, axis)
        patt_input.quantity = adsk.core.ValueInput.createByReal(float(z))
        patt_input.totalAngle = adsk.core.ValueInput.createByString("360 deg")
        patterns.add(patt_input)

    def _cut_helical_teeth(self, component: "adsk.fusion.Component", z: int, pitch_diameter_mm: float, mn_mm: float, face_width_mm: float, beta_rad: float, opposite_hand: bool) -> None:
        addendum = mn_mm
        dedendum = 1.25 * mn_mm
        outer_radius = (pitch_diameter_mm + 2 * addendum) / 2.0
        root_radius = max((pitch_diameter_mm - 2 * dedendum) / 2.0, 0.4 * pitch_diameter_mm / 2.0)

        if abs(beta_rad) < 1e-9:
            self._cut_spur_teeth(component, z, pitch_diameter_mm, mn_mm, face_width_mm)
            return

        lead_mm = (math.pi * pitch_diameter_mm) / math.tan(abs(beta_rad))
        twist_deg = (360.0 * face_width_mm) / max(lead_mm, 1e-6)
        if opposite_hand:
            twist_deg = -twist_deg

        plane_input = component.constructionPlanes.createInput()
        plane_input.setByOffset(component.xYConstructionPlane, self._mm(face_width_mm))
        end_plane = component.constructionPlanes.add(plane_input)

        tooth_pitch_angle = 2 * math.pi / z
        gap_angle = tooth_pitch_angle * 0.5

        start_sketch = component.sketches.add(component.xYConstructionPlane)
        self._build_gap_profile(start_sketch, root_radius, outer_radius, 0.0, gap_angle)
        start_profile = start_sketch.profiles.item(0)

        end_sketch = component.sketches.add(end_plane)
        self._build_gap_profile(end_sketch, root_radius, outer_radius, math.radians(twist_deg), gap_angle)
        end_profile = end_sketch.profiles.item(0)

        loft_features = component.features.loftFeatures
        loft_input = loft_features.createInput(adsk.fusion.FeatureOperations.CutFeatureOperation)
        loft_sections = loft_input.loftSections
        loft_sections.add(start_profile)
        loft_sections.add(end_profile)
        loft = loft_features.add(loft_input)

        entities = adsk.core.ObjectCollection.create()
        entities.add(loft)
        axis = component.zConstructionAxis

        patterns = component.features.circularPatternFeatures
        patt_input = patterns.createInput(entities, axis)
        patt_input.quantity = adsk.core.ValueInput.createByReal(float(z))
        patt_input.totalAngle = adsk.core.ValueInput.createByString("360 deg")
        patterns.add(patt_input)

    def _create_revolute_joint(self, occ: "adsk.fusion.Occurrence", name: str) -> Optional["adsk.fusion.Joint"]:
        try:
            joints = self.root.joints
            geo0 = adsk.fusion.JointGeometry.createByPlanarFace(
                occ.component.bRepBodies.item(0).faces.item(0),
                None,
                adsk.fusion.JointKeyPointTypes.CenterKeyPoint,
            )
            geo1 = adsk.fusion.JointGeometry.createByPlanarFace(
                self.root.xYConstructionPlane,
                None,
                adsk.fusion.JointKeyPointTypes.CenterKeyPoint,
            )
            input_joint = joints.createInput(geo0, geo1)
            input_joint.setAsRevoluteJointMotion(adsk.fusion.JointDirections.ZAxisJointDirection)
            joint = joints.add(input_joint)
            joint.name = name
            return joint
        except Exception:
            return None

    def generate(self, params: GearInput) -> Dict[str, float]:
        geometry = derive_geometry(params)
        checks = verify_pair(params, geometry)
        if not checks["all"]:
            raise ValueError(f"Input verification failed: {checks}")

        self._delete_stale()

        g1_component, g1_occ = self._new_component("GG_driver", 0.0)
        g2_component, g2_occ = self._new_component("GG_driven", geometry.center_distance)

        outer_d1 = geometry.d1 + 2 * params.mn
        outer_d2 = geometry.d2 + 2 * params.mn

        self._create_gear_blank(g1_component, outer_d1, params.face_width)
        self._create_gear_blank(g2_component, outer_d2, params.face_width)

        gear_type = _canonical_gear_type(params.gear_type)
        if gear_type == "spur":
            self._cut_spur_teeth(g1_component, params.z1, geometry.d1, params.mn, params.face_width)
            self._cut_spur_teeth(g2_component, params.z2, geometry.d2, params.mn, params.face_width)
        else:
            self._cut_helical_teeth(g1_component, params.z1, geometry.d1, params.mn, params.face_width, geometry.beta_rad, opposite_hand=False)
            self._cut_helical_teeth(g2_component, params.z2, geometry.d2, params.mn, params.face_width, geometry.beta_rad, opposite_hand=True)

        j1 = self._create_revolute_joint(g1_occ, "GG_driver_joint")
        j2 = self._create_revolute_joint(g2_occ, "GG_driven_joint")
        if j1 and j2:
            try:
                links = self.root.jointMotionLinks
                link = links.createInput(j1, j2)
                link.gearRatio = -params.z2 / params.z1
                links.add(link)
            except Exception:
                pass

        return {
            "ratio": geometry.ratio,
            "d1_mm": geometry.d1,
            "d2_mm": geometry.d2,
            "center_distance_mm": geometry.center_distance,
            "mt_mm": geometry.mt,
        }


def demo_configurations() -> Dict[str, GearInput]:
    return {
        "A_spur_2_to_1": GearInput(
            gear_type="spur",
            mn=2.0,
            z1=20,
            z2=40,
            pressure_angle_deg=20.0,
            face_width=10.0,
            helix_angle_deg=0.0,
        ),
        "B_helical_3_to_1": GearInput(
            gear_type="helical",
            mn=2.0,
            z1=20,
            z2=60,
            pressure_angle_deg=20.0,
            face_width=12.0,
            helix_angle_deg=20.0,
        ),
    }


def run(context):
    if adsk is None:
        raise RuntimeError("This script must be executed inside Autodesk Fusion.")

    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        generator = FusionGearPairGenerator(app)
        defaults = demo_configurations()["A_spur_2_to_1"]
        text, cancelled = ui.inputBox(
            "Enter: gear_type,mn,z1,z2,pressure_angle_deg,face_width,helix_angle_deg",
            "Gear Pair Inputs",
            f"{defaults.gear_type},{defaults.mn},{defaults.z1},{defaults.z2},{defaults.pressure_angle_deg},{defaults.face_width},{defaults.helix_angle_deg}",
        )
        if cancelled:
            return

        raw = [part.strip() for part in text.split(",")]
        if len(raw) != 7:
            raise ValueError("Expected 7 comma-separated values.")
        selected = GearInput(
            gear_type=raw[0],
            mn=float(raw[1]),
            z1=int(raw[2]),
            z2=int(raw[3]),
            pressure_angle_deg=float(raw[4]),
            face_width=float(raw[5]),
            helix_angle_deg=float(raw[6]),
        )
        result = generator.generate(selected)
        ui.messageBox(
            "Generated gear pair\n"
            f"Type: {selected.gear_type}\n"
            f"Z1/Z2: {selected.z1}/{selected.z2}\n"
            f"Ratio: {result['ratio']:.3f}\n"
            f"d1={result['d1_mm']:.3f} mm, d2={result['d2_mm']:.3f} mm\n"
            f"a={result['center_distance_mm']:.3f} mm"
        )
    except Exception as exc:
        ui.messageBox(f"Failed: {exc}")


def stop(context):
    return
