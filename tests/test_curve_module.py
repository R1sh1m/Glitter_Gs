"""Offline tests for fusion_curve_module (no Fusion needed)."""
import unittest

from fusion_curve_module import (
    CurveInput,
    arc_length_mm,
    calculate_load_advisory,
    curve_angular_pitch_deg,
    curve_bom,
    curve_roller_count_for,
    derive_curve_configuration,
    taper_outer_dia,
    validate_curve_inputs,
    verify_curve_configuration,
)


def demo_curve():
    return CurveInput(800.0, 90.0, 450.0, 750.0, 50.0, 110.0, 700.0, 100.0, True)


class CurveModuleTests(unittest.TestCase):
    def test_taper_kinematics(self):
        self.assertAlmostEqual(taper_outer_dia(50.0, 800.0, 450.0), 50.0 * 1250.0 / 800.0)
        # d_in/Ri == d_out/Ro
        d_out = taper_outer_dia(50.0, 800.0, 450.0)
        self.assertAlmostEqual(50.0 / 800.0, d_out / 1250.0)

    def test_arc_and_count(self):
        self.assertAlmostEqual(arc_length_mm(800.0, 90.0), 800.0 * 3.14159265 / 2, places=3)
        n = curve_roller_count_for(90.0, 800.0, 450.0, 50.0, 110.0)
        self.assertGreaterEqual(n, 3)
        # 5-deg cap enforced: 90deg needs >= 19
        self.assertGreaterEqual(n, 19)
        self.assertLessEqual(curve_angular_pitch_deg(90.0, n), 5.0 + 1e-9)

    def test_derive_verify_all_pass(self):
        d = derive_curve_configuration(demo_curve())
        self.assertEqual(d.roller_count, 19)
        self.assertAlmostEqual(d.angular_pitch_deg, 5.0)
        self.assertTrue(verify_curve_configuration(demo_curve(), d)["all"])
        bom = curve_bom(d, True)
        self.assertEqual(bom["tapered_rollers"], 19)
        self.assertEqual(bom["frame_arc_rails"], 2)

    def test_rejects_bad_taper(self):
        bad = CurveInput(400.0, 90.0, 600.0, 750.0, 80.0, 150.0, 700.0, 100.0, True)
        # d_out = 80*1000/400 = 200 > 120 -> reject
        with self.assertRaises(ValueError):
            validate_curve_inputs(bad)

    def test_advisory_clamps_to_spec(self):
        a = calculate_load_advisory(50.0, 600.0, 400.0)
        self.assertEqual(a.p_recommended_mm, 150.0)  # 600/3=200 clamped to 150
        self.assertEqual(a.d_recommended_mm, 50.0)
        self.assertEqual(a.w_recommended_mm, 500.0)
        b = calculate_load_advisory(200.0, 300.0, 200.0)
        self.assertEqual(b.d_recommended_mm, 80.0)
        self.assertEqual(b.s_recommended_mm, 500.0)

    def test_fusion_formula_idioms(self):
        """Live-proven Fusion expression rules (2026-09-18): /1 rad strip,
        no pi, no max(). create_curve_parameters must obey them."""
        import inspect
        import fusion_curve_module as m
        src = inspect.getsource(m.create_curve_parameters)
        self.assertIn("/ 1 rad", src)
        self.assertNotIn("pi / 180", src)
        self.assertIn("C_RollerCountMin", src)
        self.assertIn('ceil(C_CurveAngle / 5 deg)', src)

    def test_hole_stations_follow_angle_and_band_rule(self):
        from fusion_curve_module import curve_hole_stations
        d = derive_curve_configuration(demo_curve())
        st = curve_hole_stations(demo_curve(), d)
        self.assertEqual(len(st), 2 * d.roller_count)
        import math
        angs = sorted({round(a, 9) for a, _, _ in st})
        self.assertEqual(len(angs), d.roller_count)
        self.assertAlmostEqual(angs[0], 0.0)
        self.assertAlmostEqual(angs[-1], math.pi / 2)
        for _, r, rail in st:
            if rail == "inner":
                self.assertAlmostEqual(r, 800.0 + 20.0 / 2.0)
            else:
                self.assertAlmostEqual(r, 1250.0 - 20.0 / 2.0)

    def test_hole_area_gate(self):
        import math
        from fusion_curve_module import keeps_hole_profile
        self.assertTrue(keeps_hole_profile(math.pi * 0.8 ** 2))
        self.assertFalse(keeps_hole_profile(254.47))  # face loop, live value
        self.assertFalse(keeps_hole_profile(0.05))    # sliver

    def test_hole_verifier_honesty(self):
        from fusion_curve_module import verify_curve_holes
        d = derive_curve_configuration(demo_curve())
        ok = verify_curve_holes(18, 18, d)
        self.assertTrue(ok["all"])  # 18/19 live result passes (open ends)
        bad = verify_curve_holes(10, 18, d)
        self.assertFalse(bad["all"])

    def test_p2_hardware_math_matches_live(self):
        import math
        from fusion_curve_module import (
            bearing_ring_volume_mm3,
            curve_bom_full,
            estimate_hardware_masses_kg,
            frustum_volume_mm3,
            hollow_tube_volume_mm3,
            shaft_length_for,
            shaft_volume_mm3,
            verify_drivetrain_counts,
        )
        d = derive_curve_configuration(demo_curve())
        # Live anchors (cm3): tube 240.6, shaft 73.0, ring 5.6
        self.assertAlmostEqual(hollow_tube_volume_mm3(demo_curve(), d) / 1000.0, 240.6, delta=1.0)
        self.assertAlmostEqual(shaft_volume_mm3(450.0) / 1000.0, 76.7, delta=0.5)
        self.assertAlmostEqual(bearing_ring_volume_mm3() / 1000.0, 5.6, delta=0.5)
        self.assertEqual(shaft_length_for(450.0), 498.0)        # Frustum degenerates to cylinder when d0 == d1
        self.assertAlmostEqual(
            frustum_volume_mm3(50.0, 50.0, 100.0), math.pi * 25.0 ** 2 * 100.0)
        self.assertTrue(verify_drivetrain_counts(19, 38, d)["all"])
        self.assertFalse(verify_drivetrain_counts(19, 37, d)["all"])
        bom = curve_bom_full(demo_curve(), d, {"inner": 18, "outer": 18})
        self.assertEqual(bom["shafts_dia14"], 19)
        self.assertEqual(bom["bearing_rings_6002"], 38)
        self.assertEqual(bom["rail_seat_bores"], 36)
        self.assertEqual(bom["dock_boards"], 4)
        masses = estimate_hardware_masses_kg(demo_curve(), d)
        for part, kg in masses.items():
            self.assertGreater(kg, 0.0, part)

    def test_belt_and_housing_math(self):
        from fusion_curve_module import (
            belt_band_radii_mm,
            belt_volume_mm3,
            curve_bom_drive,
            housing_positions_mm,
            verify_housings,
        )
        d = derive_curve_configuration(demo_curve())
        r0, r1 = belt_band_radii_mm(d)
        self.assertAlmostEqual(r0, 1010.0)
        self.assertAlmostEqual(r1, 1040.0)
        self.assertGreater(belt_volume_mm3(d), 0.0)
        hp = housing_positions_mm(demo_curve(), d)
        self.assertEqual(hp["inner"], (776.0, 788.0))
        self.assertEqual(hp["outer"], (1262.0, 1274.0))
        self.assertTrue(verify_housings(38, 38, d)["all"])
        self.assertFalse(verify_housings(38, 36, d)["all"])
        bom = curve_bom_drive(demo_curve(), d)
        self.assertEqual(bom["bearing_housings"], 38)
        self.assertEqual(bom["drive_belt_band"], 1)

    def test_export_curve_step_writes_file(self):
        import os
        import tempfile
        from fusion_curve_module import export_curve_step

        class FakeExportManager:
            def __init__(self):
                self.calls = []

            def createSTEPExportOptions(self, path, comp):
                self.calls.append((path, comp))
                return ("opts", path)

            def execute(self, options):
                with open(options[1], "w", encoding="utf-8") as f:
                    f.write("ISO-10303-21; mock curve STEP\n")

        class FakeDesign:
            def __init__(self):
                self.exportManager = FakeExportManager()

        with tempfile.TemporaryDirectory() as tmpdir:
            out = export_curve_step(FakeDesign(), object(), "Curve90_Test", tmpdir)
            self.assertTrue(out.endswith("Curve90_Test.step"))
            self.assertTrue(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
