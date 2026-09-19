"""6-DOF docking math suite — Fusion-independent (no ``adsk`` import).

Gate: NO Fusion geometry integration until every test here passes.
Cases (§6 of the mission + §8 worked values in Docs/COORDINATE_SYSTEM.md):
  1. Straight -> Straight (identity + advance by L)
  2. Straight -> Curve 90° (-90° yaw)
  3. Curve -> Straight (tangent alignment)
  4. Opposite-direction (reversed flow) -> overlap rejected via collision gate
  5. Height offset 850 -> 700 -> DockingError with +150mm riser correction
  6. Width mismatch 450 -> 500 -> DockingError
  7. Rotation hygiene: orthonormal, det=+1, quaternion round-trip
  8. Full line S2000 + Curve90 + S3000 chained (golden fixture)
  9. Solution dict round-trip (serialization of the transform itself)
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "conveyor_addin",
    ),
)

from core import frames as F  # noqa: E402
from core.errors import DockingError  # noqa: E402
from docking import validators as V  # noqa: E402
from docking.port import ConveyorPort  # noqa: E402
from docking.solver import DockingSolver  # noqa: E402
from modules._port_helpers import straight_port_pair  # noqa: E402
from modules.base import ConveyorModule  # noqa: E402
from modules.curve import create_curve_module  # noqa: E402
from modules.straight import create_straight_module  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN_LINE = os.path.join(
    REPO_ROOT, "tests", "fixtures", "golden_layouts", "line_S2000_C90_S3000.json"
)

W, H, P = 450.0, 750.0, 110.0


def _straight(length, width=W, height=H, pitch=P):
    return create_straight_module(length, width, height, 60.0, pitch,
                                  700.0, 100.0, True)


def _curve():
    return create_curve_module(800.0, 90.0, W, H, 50.0, P, 700.0, 100.0, True)


def _assert_mat_almost(test, got, want, places=9):
    test.assertEqual(len(got), 3)
    for row_g, row_w in zip(got, want):
        for g, w in zip(row_g, row_w):
            test.assertAlmostEqual(g, w, places=places)


class DockingMathTests(unittest.TestCase):
    # 1 ------------------------------------------------------------------
    def test_straight_to_straight(self):
        a = _straight(1400.0)
        b = _straight(1000.0)
        sol = DockingSolver.solve(a.outlet_port, b.inlet_port,
                                  child_outlet=b.outlet_port)
        _assert_mat_almost(self, sol.rotation, F.mat_identity())
        self.assertAlmostEqual(sol.translation_mm[0], 1400.0)
        self.assertAlmostEqual(sol.translation_mm[1], 0.0)
        self.assertAlmostEqual(sol.translation_mm[2], 0.0)
        inlet = sol.transform_point_mm(b.inlet_port.origin)
        self.assertAlmostEqual(inlet[0], 1400.0)
        self.assertAlmostEqual(inlet[1], 225.0)
        self.assertAlmostEqual(inlet[2], 750.0)
        outlet = sol.transform_point_mm(b.outlet_port.origin)
        self.assertAlmostEqual(outlet[0], 2400.0)
        self.assertAlmostEqual(outlet[1], 225.0)
        # quaternion of identity is (±1, 0, 0, 0)
        w, x, y, z = sol.quaternion_wxyz
        self.assertAlmostEqual(abs(w), 1.0)
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(y, 0.0)
        self.assertAlmostEqual(z, 0.0)

    # 2 ------------------------------------------------------------------
    def test_straight_to_curve_90(self):
        a = _straight(1400.0)
        c = _curve()
        sol = DockingSolver.solve(a.outlet_port, c.inlet_port,
                                  child_outlet=c.outlet_port)
        _assert_mat_almost(
            self, sol.rotation,
            [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            places=5,
        )
        inlet = sol.transform_point_mm(c.inlet_port.origin)
        self.assertAlmostEqual(inlet[0], 1400.0, places=3)
        self.assertAlmostEqual(inlet[1], 225.0, places=3)
        self.assertAlmostEqual(inlet[2], 750.0, places=3)
        # carry plane preserved through the curve
        outlet = sol.transform_point_mm(c.outlet_port.origin)
        self.assertAlmostEqual(outlet[2], 750.0, places=6)

    # 3 ------------------------------------------------------------------
    def test_curve_to_straight(self):
        c = _curve()
        b = _straight(1000.0)
        sol = DockingSolver.solve(c.outlet_port, b.inlet_port,
                                  child_outlet=b.outlet_port)
        # curve outlet tangent (-1,0,0); child +X must map onto it: 180° yaw
        _assert_mat_almost(
            self, sol.rotation,
            [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]],
            places=5,
        )
        inlet = sol.transform_point_mm(b.inlet_port.origin)
        for got, want in zip(inlet, c.outlet_port.origin):
            self.assertAlmostEqual(got, want, places=6)

    # 4 ------------------------------------------------------------------
    def test_opposite_direction_rejected_by_collision(self):
        """Reversed flow (inlet facing -X) solves to a 180° flip whose
        footprint lands inside the parent — the collision gate rejects it."""
        a = _straight(1400.0)
        flipped = ConveyorPort(
            id="reversed:inlet", origin=(0.0, 225.0, 750.0),
            direction=(-1.0, 0.0, 0.0), lateral_axis=(0.0, -1.0, 0.0),
            up=(0.0, 0.0, 1.0), width=450.0, height=750.0,
            roller_pitch=110.0, conveyor_type="Straight",
        )
        sol = DockingSolver.solve(a.outlet_port, flipped)
        # child local x∈[0,1000] maps into x∈[400,1400]: inside the parent
        lo = sol.transform_point_mm((0.0, 0.0, 0.0))
        hi = sol.transform_point_mm((1000.0, 450.0, 850.0))
        child_min = tuple(min(x, y) for x, y in zip(lo, hi))
        child_max = tuple(max(x, y) for x, y in zip(lo, hi))
        with self.assertRaises(DockingError) as ctx:
            V.check_collision_aabb((0.0, 0.0, 0.0), (1400.0, 450.0, 850.0),
                                   child_min, child_max)
        self.assertEqual(ctx.exception.reason, "collision")

    # 5 ------------------------------------------------------------------
    def test_height_offset_reports_riser(self):
        a = _straight(1400.0, height=850.0)
        b = _straight(1000.0, height=700.0)
        with self.assertRaises(DockingError) as ctx:
            V.validate_joint(a.outlet_port, b.inlet_port)
        err = ctx.exception
        self.assertEqual(err.reason, "height_mismatch")
        self.assertIn("150", err.required_correction)
        self.assertIn("riser", err.required_correction)
        self.assertIn("850", err.message)
        self.assertIn("700", err.message)

    # 6 ------------------------------------------------------------------
    def test_width_mismatch_rejected(self):
        a = _straight(1400.0, width=450.0)
        b = _straight(1000.0, width=500.0)
        with self.assertRaises(DockingError) as ctx:
            V.validate_joint(a.outlet_port, b.inlet_port)
        self.assertEqual(ctx.exception.reason, "width_mismatch")

    # 7 ------------------------------------------------------------------
    def test_rotation_hygiene_and_quaternion(self):
        a = _straight(1400.0)
        c = _curve()
        sol = DockingSolver.solve(a.outlet_port, c.inlet_port)
        self.assertTrue(F.is_rotation(sol.rotation))
        self.assertAlmostEqual(F.mat_det(sol.rotation), 1.0, places=9)
        back = F.quat_to_rot(sol.quaternion_wxyz)
        _assert_mat_almost(self, back, sol.rotation, places=9)

    # 8 ------------------------------------------------------------------
    def test_full_line_chain_matches_golden(self):
        with open(GOLDEN_LINE, encoding="utf-8") as fh:
            golden = json.load(fh)["expected"]
        s1 = _straight(2000.0)
        curve = _curve()
        # 3000mm exceeds the straight spec range (800-2000), so the demo
        # carrier is composed as a straight-geometry module directly —
        # ports identical, no spec validation bypassed silently.
        pair = straight_port_pair("S3000-demo", "Straight", 3000.0, W, H, P)
        s3 = ConveyorModule(
            module_id="S3000-demo", module_type="Straight",
            length=3000.0, width=W, height=H,
            inlet_port=pair["inlet"], outlet_port=pair["outlet"],
            engineering_parameters={"length_mm": 3000.0, "demo_carrier": True},
        )
        j1 = DockingSolver.solve(s1.outlet_port, curve.inlet_port,
                                 child_outlet=curve.outlet_port)
        _assert_mat_almost(self, j1.rotation, golden["joint1_R"], places=9)
        for got, want in zip(j1.translation_mm, golden["joint1_t_mm"]):
            self.assertAlmostEqual(got, want, places=6)
        placed_curve = curve.with_world_transform(j1.rotation,
                                                  j1.translation_mm)
        j2 = DockingSolver.solve(placed_curve.outlet_port, s3.inlet_port,
                                 child_outlet=s3.outlet_port)
        _assert_mat_almost(self, j2.rotation, golden["joint2_R"], places=9)
        for got, want in zip(j2.translation_mm, golden["joint2_t_mm"]):
            self.assertAlmostEqual(got, want, places=6)
        placed_s3 = s3.with_world_transform(j2.rotation, j2.translation_mm)
        final = placed_s3.outlet_port.origin
        for got, want in zip(final, golden["final_outlet_world_mm"]):
            self.assertAlmostEqual(
                got, want, delta=golden["final_outlet_world_mm_tol"])
        # engineering gates pass on both joints (pitch step carries at most
        # a bridging warning, never a failure)
        checks1 = V.validate_joint(s1.outlet_port, curve.inlet_port,
                                   child_inner_radius_mm=800.0)
        self.assertTrue(all(ok for _, ok, _ in checks1))
        checks2 = V.validate_joint(placed_curve.outlet_port, s3.inlet_port,
                                   parent_inner_radius_mm=800.0)
        self.assertTrue(all(ok for _, ok, _ in checks2))

    # 9 ------------------------------------------------------------------
    def test_solution_dict_round_trip(self):
        a = _straight(1400.0)
        c = _curve()
        sol = DockingSolver.solve(a.outlet_port, c.inlet_port,
                                  child_outlet=c.outlet_port)
        data = sol.to_dict()
        self.assertEqual(
            sorted(data),
            ["child_inlet_world_mm", "child_outlet_world_mm",
             "direction_error_deg", "matrix_4x4", "quaternion_wxyz",
             "rotation_3x3", "translation_mm", "up_error_deg"],
        )
        text = json.dumps(data)
        back = json.loads(text)
        for row_g, row_w in zip(back["rotation_3x3"], sol.rotation):
            for g, w in zip(row_g, row_w):
                self.assertAlmostEqual(g, w, places=12)


if __name__ == "__main__":
    unittest.main()
