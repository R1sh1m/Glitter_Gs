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


if __name__ == "__main__":
    unittest.main()
