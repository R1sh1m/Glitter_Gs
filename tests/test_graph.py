"""ConveyorGraph tests — layout assembly, validation, removal (offline)."""

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

from core.errors import DockingError  # noqa: E402
from graph.layout import ConveyorGraph  # noqa: E402
from modules._port_helpers import straight_port_pair  # noqa: E402
from modules.base import ConveyorModule  # noqa: E402
from modules.curve import create_curve_module  # noqa: E402
from modules.straight import create_straight_module  # noqa: E402

W, H, P = 450.0, 750.0, 110.0


def _demo_carrier_3000():
    pair = straight_port_pair("S3000-demo", "Straight", 3000.0, W, H, P)
    return ConveyorModule(
        module_id="S3000-demo", module_type="Straight",
        length=3000.0, width=W, height=H,
        inlet_port=pair["inlet"], outlet_port=pair["outlet"],
        engineering_parameters={"length_mm": 3000.0, "demo_carrier": True},
    )


def _demo_line():
    graph = ConveyorGraph()
    s1 = create_straight_module(2000.0, W, H, 60.0, P, 700.0, 100.0, True)
    curve = create_curve_module(800.0, 90.0, W, H, 50.0, P, 700.0, 100.0, True)
    graph.add_module(s1)
    graph.add_module(curve)
    graph.add_module(_demo_carrier_3000())
    graph.connect_modules(s1.module_id, curve.module_id)
    graph.connect_modules(curve.module_id, "S3000-demo")
    return graph, s1, curve


class GraphTests(unittest.TestCase):
    def test_add_connect_validate_assembly(self):
        graph, s1, curve = _demo_line()
        report = graph.validate_layout()
        self.assertTrue(report["valid"], report)
        self.assertEqual(len(report["edges"]), 2)
        assembly = graph.generate_assembly()
        self.assertEqual(assembly["module_count"], 3)
        self.assertEqual(len(assembly["joints"]), 2)
        final = assembly["modules"][-1]["outlet_world_mm"]
        self.assertAlmostEqual(final[0], 3025.0, places=3)
        self.assertAlmostEqual(final[1], 4250.0, places=3)
        self.assertAlmostEqual(final[2], 750.0, places=6)
        self.assertGreater(assembly["bom_rollup"].get("rollers", 0), 0)

    def test_duplicate_module_rejected(self):
        graph = ConveyorGraph()
        graph.add_module(create_straight_module(
            1400.0, W, H, 60.0, P, 700.0, 100.0, True))
        with self.assertRaises(ValueError):
            graph.add_module(create_straight_module(
                1400.0, W, H, 60.0, P, 700.0, 100.0, True))

    def test_height_mismatch_blocks_connect(self):
        graph = ConveyorGraph()
        a = create_straight_module(1400.0, W, 850.0, 60.0, P, 700.0,
                                   100.0, True)
        b = create_straight_module(1000.0, W, 700.0, 60.0, P, 500.0,
                                   100.0, True)
        graph.add_module(a)
        graph.add_module(b)
        with self.assertRaises(DockingError) as ctx:
            graph.connect_modules(a.module_id, b.module_id)
        self.assertEqual(ctx.exception.reason, "height_mismatch")

    def test_remove_module_marks_dirty(self):
        graph, s1, curve = _demo_line()
        graph.remove_module("S3000-demo")
        self.assertTrue(graph.dirty)
        report = graph.validate_layout()
        self.assertFalse(report["valid"])
        self.assertEqual(graph.generate_assembly()["module_count"], 2)

    def test_self_dock_rejected(self):
        graph = ConveyorGraph()
        m = create_straight_module(1400.0, W, H, 60.0, P, 700.0, 100.0, True)
        graph.add_module(m)
        with self.assertRaises(ValueError):
            graph.connect_modules(m.module_id, m.module_id)


if __name__ == "__main__":
    unittest.main()
