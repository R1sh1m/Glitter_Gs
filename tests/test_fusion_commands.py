"""Fusion command tests — pure panel actions + adapter maps (offline)."""

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

from fusion import commands as C  # noqa: E402
from fusion import generators as G  # noqa: E402
from fusion import viz as V  # noqa: E402
from graph.layout import ConveyorGraph  # noqa: E402

W, H, P = 450.0, 750.0, 110.0


class FusionCommandTests(unittest.TestCase):
    def test_panel_has_six_commands(self):
        self.assertEqual(len(C.COMMANDS), 6)
        titles = [c["title"] for c in C.COMMANDS]
        self.assertEqual(titles, ["Create Module", "Connect Modules",
                                  "Validate Layout", "Generate Assembly",
                                  "Generate BOM", "Manufacturing Report"])

    def test_create_module_all_types(self):
        straight = C.create_module({"module_type": "Straight",
                                    "length_mm": 1400.0, "width_mm": W,
                                    "height_mm": H, "roller_diameter_mm": 60.0,
                                    "roller_spacing_mm": P,
                                    "support_spacing_mm": 700.0,
                                    "side_guard_height_mm": 100.0,
                                    "side_guards": True})
        self.assertEqual(straight.module_type, "Straight")
        curve = C.create_module({"module_type": "Curved",
                                 "inner_radius_mm": 800.0,
                                 "curve_angle_deg": 90.0, "width_mm": W,
                                 "height_mm": H, "roller_dia_inner_mm": 50.0,
                                 "roller_pitch_outer_mm": P})
        self.assertEqual(curve.module_type, "Curved")
        for kind, extra in (
                ("Merge", {}), ("Transfer", {"length_mm": 600.0}),
                ("Incline", {"height_in_mm": 750.0, "rise_mm": 200.0})):
            spec = {"module_type": kind, "length_mm": 1400.0, "width_mm": W,
                    "height_mm": H, "roller_pitch_mm": P}
            spec.update(extra)
            module = C.create_module(spec)
            self.assertEqual(module.module_type, kind)

    def test_full_panel_flow_offline(self):
        graph = ConveyorGraph()
        s1 = C.create_module({"module_type": "Straight", "length_mm": 2000.0,
                              "width_mm": W, "height_mm": H,
                              "roller_spacing_mm": P,
                              "side_guard_height_mm": 100.0,
                              "side_guards": True})
        c1 = C.create_module({"module_type": "Curved",
                              "inner_radius_mm": 800.0,
                              "curve_angle_deg": 90.0, "width_mm": W,
                              "height_mm": H, "roller_pitch_outer_mm": P,
                              "side_guard_height_mm": 100.0,
                              "side_guards": True})
        graph.add_module(s1)
        graph.add_module(c1)
        edge = C.connect_modules(graph, s1.module_id, c1.module_id)
        fatal = [c for c in edge["checks"]
                 if not c["passed"] and not c["message"].startswith("WARNING")]
        self.assertEqual(fatal, [])
        report = C.validate_layout(graph)
        self.assertTrue(report["valid"], report)
        assembly = C.generate_assembly(graph)
        self.assertEqual(assembly["module_count"], 2)
        bom = C.generate_bom([s1, c1])
        self.assertGreater(len(bom), 5)
        mrep = C.manufacturing_report("panel-line", [s1, c1], graph)
        self.assertEqual(mrep["line_name"], "panel-line")

    def test_generators_round_trip_inputs(self):
        s1 = C.create_module({"module_type": "Straight", "length_mm": 1400.0,
                              "width_mm": W, "height_mm": H,
                              "roller_spacing_mm": P})
        legacy = G.module_to_straight_inputs(s1)
        self.assertAlmostEqual(legacy.length_mm, 1400.0)
        self.assertAlmostEqual(legacy.roller_spacing_mm, P)
        c1 = C.create_module({"module_type": "Curved",
                              "inner_radius_mm": 800.0,
                              "curve_angle_deg": 90.0, "width_mm": W,
                              "height_mm": H})
        legacy_c = G.module_to_curve_inputs(c1)
        self.assertAlmostEqual(legacy_c.inner_radius_mm, 800.0)
        plan = G.describe_build_plan(c1)
        self.assertIn("revolve_tapered_master", plan)
        self.assertIn("pattern_rollers", G.describe_build_plan(s1))

    def test_viz_specs_offline(self):
        s1 = C.create_module({"module_type": "Straight", "length_mm": 1400.0,
                              "width_mm": W, "height_mm": H})
        spec = V.triad_spec(s1.outlet_port)
        self.assertEqual(len(spec["shafts"]), 3)
        self.assertFalse(V.draw_triad(None, s1.outlet_port))
        self.assertFalse(C.register_panel(None))

    def test_register_panel_offline_safe(self):
        self.assertFalse(C.register_panel())


if __name__ == "__main__":
    unittest.main()
