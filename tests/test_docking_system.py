"""tests/test_docking_system.py — Offline unit tests for multi-module conveyor docking."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fusion_docking_system as fds  # noqa: E402
import fusion_conveyor_generator as fcg  # noqa: E402
import fusion_curve_module as fcm  # noqa: E402


class DockingSystemTests(unittest.TestCase):
    def test_straight_to_straight_docking(self):
        """Verify translation and 0-deg rotation when docking two straight sections."""
        p1 = fcg.ConveyorInput(1400.0, 450.0, 750.0, 60.0, 110.0, 700.0, 100.0, True)
        p2 = fcg.ConveyorInput(1000.0, 450.0, 750.0, 60.0, 110.0, 500.0, 100.0, True)

        ports1 = fcg.get_module_ports(p1)
        ports2 = fcg.get_module_ports(p2)

        transform = fds.compute_docking_transform(ports1["outlet_port"], ports2["inlet_port"])

        # Rotation matrix should be identity
        self.assertAlmostEqual(transform.r[0][0], 1.0)
        self.assertAlmostEqual(transform.r[0][1], 0.0)
        self.assertAlmostEqual(transform.r[1][0], 0.0)
        self.assertAlmostEqual(transform.r[1][1], 1.0)

        # Translation should advance by length of first module (1400 mm)
        self.assertAlmostEqual(transform.t_mm[0], 1400.0)
        self.assertAlmostEqual(transform.t_mm[1], 0.0)
        self.assertAlmostEqual(transform.t_mm[2], 0.0)

        # Module 2 inlet should land exactly on Module 1 outlet
        new_inlet = transform.transform_point_mm(ports2["inlet_port"]["origin_mm"])
        self.assertAlmostEqual(new_inlet[0], 1400.0)
        self.assertAlmostEqual(new_inlet[1], 225.0)
        self.assertAlmostEqual(new_inlet[2], 750.0)

        # Module 2 outlet should be at 2400 mm
        new_outlet = transform.transform_point_mm(ports2["outlet_port"]["origin_mm"])
        self.assertAlmostEqual(new_outlet[0], 2400.0)
        self.assertAlmostEqual(new_outlet[1], 225.0)

    def test_straight_to_curve_docking(self):
        """Verify rotation and alignment when docking straight to a 90-degree curve."""
        p_str = fcg.ConveyorInput(1400.0, 450.0, 750.0, 60.0, 110.0, 700.0, 100.0, True)
        p_curv = fcm.CurveInput(
            inner_radius_mm=800.0,
            curve_angle_deg=90.0,
            width_mm=450.0,
            height_mm=750.0,
            roller_dia_inner_mm=50.0,
            roller_pitch_outer_mm=110.0,
            support_spacing_mm=700.0,
            side_guard_height_mm=100.0,
            side_guards=True,
        )

        ports_str = fcg.get_module_ports(p_str)
        derived_curv = fcm.derive_curve_configuration(p_curv)
        ports_curv = fcm.get_curve_module_ports(p_curv, derived_curv)

        transform = fds.compute_docking_transform(ports_str["outlet_port"], ports_curv["inlet_port"])

        # Curve inlet (dir = [0, 1, 0]) must rotate to straight outlet (dir = [1, 0, 0]) -> -90 deg rotation
        # cos(-90) = 0, sin(-90) = -1
        self.assertAlmostEqual(transform.r[0][0], 0.0, places=5)
        self.assertAlmostEqual(transform.r[0][1], 1.0, places=5)
        self.assertAlmostEqual(transform.r[1][0], -1.0, places=5)
        self.assertAlmostEqual(transform.r[1][1], 0.0, places=5)

        # Transformed curve inlet should align with straight outlet
        new_inlet = transform.transform_point_mm(ports_curv["inlet_port"]["origin_mm"])
        self.assertAlmostEqual(new_inlet[0], 1400.0, places=3)
        self.assertAlmostEqual(new_inlet[1], 225.0, places=3)
        self.assertAlmostEqual(new_inlet[2], 750.0, places=3)

    def test_joint_validation_rules(self):
        """Verify joint validation detects matching vs mismatched specifications."""
        p1 = fcg.ConveyorInput(1400.0, 450.0, 750.0, 60.0, 110.0, 700.0, 100.0, True)
        p_match = fcg.ConveyorInput(1000.0, 450.0, 750.0, 60.0, 110.0, 500.0, 100.0, True)
        p_bad_h = fcg.ConveyorInput(1000.0, 450.0, 800.0, 60.0, 110.0, 500.0, 100.0, True)
        p_bad_w = fcg.ConveyorInput(1000.0, 500.0, 750.0, 60.0, 110.0, 500.0, 100.0, True)

        ports1 = fcg.get_module_ports(p1)["outlet_port"]

        # 1. Matching
        checks = fds.validate_docking_joint(ports1, fcg.get_module_ports(p_match)["inlet_port"])
        self.assertTrue(all(passed for _, passed, _ in checks))

        # 2. Mismatched Height
        checks_h = fds.validate_docking_joint(ports1, fcg.get_module_ports(p_bad_h)["inlet_port"])
        failed_h = [name for name, passed, _ in checks_h if not passed]
        self.assertIn("Carry Surface Height Match", failed_h)

        # 3. Mismatched Width
        checks_w = fds.validate_docking_joint(ports1, fcg.get_module_ports(p_bad_w)["inlet_port"])
        failed_w = [name for name, passed, _ in checks_w if not passed]
        self.assertIn("Rail Width Match", failed_w)


if __name__ == "__main__":
    unittest.main()
