"""Debug-export tests: port axes, frame markers, debug JSON bundle."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "conveyor_addin",
    ),
)

from docking import debug as D  # noqa: E402
from docking import validators as V  # noqa: E402
from docking.solver import DockingSolver  # noqa: E402
from modules.curve import create_curve_module  # noqa: E402
from modules.straight import create_straight_module  # noqa: E402


class DebugExportTests(unittest.TestCase):
    def setUp(self):
        self.straight = create_straight_module(1400.0, 450.0, 750.0, 60.0,
                                               110.0, 700.0, 100.0, True)
        self.curve = create_curve_module(800.0, 90.0, 450.0, 750.0, 50.0,
                                         110.0, 700.0, 100.0, True)

    def test_port_axes_shape_and_length(self):
        axes = D.port_axes(self.straight.outlet_port, axis_length_mm=200.0)
        self.assertEqual(sorted(axes), ["origin", "x_end", "y_end", "z_end"])
        for key in ("x_end", "y_end", "z_end"):
            dist = sum((a - b) ** 2 for a, b in
                       zip(axes[key], axes["origin"])) ** 0.5
            self.assertAlmostEqual(dist, 200.0, places=9)
        # x shaft follows flow (+X for straight outlet)
        self.assertAlmostEqual(axes["x_end"][0] - axes["origin"][0], 200.0)

    def test_debug_payload_schema(self):
        sol = DockingSolver.solve(self.straight.outlet_port,
                                  self.curve.inlet_port,
                                  child_outlet=self.curve.outlet_port)
        checks = V.validate_joint(self.straight.outlet_port,
                                  self.curve.inlet_port,
                                  child_inner_radius_mm=800.0)
        payload = D.debug_payload(self.straight.outlet_port,
                                  self.curve.inlet_port, sol, checks,
                                  self.curve.outlet_port)
        for key in ("schema_version", "parent_outlet", "child_inlet",
                    "solution", "checks", "frames", "compatibility_matrix"):
            self.assertIn(key, payload)
        self.assertEqual(len(payload["checks"]), 3)
        self.assertIn("child_inlet_axes_world", payload["frames"])
        json.dumps(payload)  # must be JSON-serializable

    def test_export_debug_json_round_trip(self):
        sol = DockingSolver.solve(self.straight.outlet_port,
                                  self.curve.inlet_port)
        with tempfile.TemporaryDirectory() as tmp:
            path = D.export_debug_json(tmp, "S1400_C90",
                                       self.straight.outlet_port,
                                       self.curve.inlet_port, sol)
            self.assertTrue(path.endswith("S1400_C90_dock_debug.json"))
            with open(path, encoding="utf-8") as fh:
                back = json.load(fh)
        self.assertEqual(back["solution"]["translation_mm"],
                         list(sol.translation_mm))


if __name__ == "__main__":
    unittest.main()
