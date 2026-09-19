"""Serialization tests: round-trips, schema migration, golden fixtures."""

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

from core import serialization as ser  # noqa: E402
from docking.port import ConveyorPort  # noqa: E402
from modules.base import ConveyorModule  # noqa: E402
from modules.straight import create_straight_module  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO_ROOT, "tests", "fixtures", "golden_layouts")


class SerializationTests(unittest.TestCase):
    def test_port_round_trip(self):
        port = ConveyorPort(
            id="p1:inlet", origin=(0.0, 225.0, 750.0),
            direction=(1.0, 0.0, 0.0), lateral_axis=(0.0, 1.0, 0.0),
            up=(0.0, 0.0, 1.0), width=450.0, height=750.0,
            roller_pitch=110.0, conveyor_type="Straight",
        )
        clone = ConveyorPort.from_dict(port.to_dict())
        self.assertEqual(clone, port)

    def test_module_round_trip(self):
        module = create_straight_module(1400.0, 450.0, 750.0, 60.0, 110.0,
                                        700.0, 100.0, True)
        clone = ConveyorModule.from_dict(module.to_dict())
        self.assertEqual(clone.module_id, module.module_id)
        self.assertEqual(clone.module_type, "Straight")
        self.assertEqual(clone.inlet_port, module.inlet_port)
        self.assertEqual(clone.outlet_port, module.outlet_port)
        self.assertEqual(clone.engineering_parameters,
                         module.engineering_parameters)

    def test_module_json_round_trip(self):
        module = create_straight_module(1400.0, 450.0, 750.0, 60.0, 110.0,
                                        700.0, 100.0, True)
        clone = ConveyorModule.from_json(module.to_json())
        self.assertEqual(clone, module)

    def test_legacy_v0_port_migrates_normal_to_lateral(self):
        legacy = {
            "origin_mm": (0.0, 225.0, 750.0),
            "direction": (1.0, 0.0, 0.0),
            "normal": (0.0, 1.0, 0.0),  # legacy key
            "up": (0.0, 0.0, 1.0),
            "width_mm": 450.0,
            "height_mm": 750.0,
            "pitch_mm": 110.0,
        }
        migrated = ser.migrate_dict(legacy)
        self.assertEqual(migrated["schema_version"], "1.0")
        self.assertEqual(migrated["migrated_from"], "0")
        self.assertNotIn("normal", migrated)
        self.assertEqual(tuple(migrated["lateral_axis"]), (0.0, 1.0, 0.0))
        port = ConveyorPort.from_dict(legacy)  # migration inside
        self.assertEqual(port.lateral_axis, (0.0, 1.0, 0.0))

    def test_loads_auto_migrates_and_records_origin(self):
        text = json.dumps({"origin_mm": [0, 0, 0], "direction": [1, 0, 0],
                           "normal": [0, 1, 0], "up": [0, 0, 1],
                           "width_mm": 450, "height_mm": 750, "pitch_mm": 110})
        data = ser.loads(text)
        self.assertEqual(data["migrated_from"], "0")
        self.assertIn("lateral_axis", data)

    def test_unknown_schema_version_rejected(self):
        with self.assertRaises(ValueError):
            ser.migrate_dict({"origin_mm": [0, 0, 0], "direction": [1, 0, 0],
                              "lateral_axis": [0, 1, 0], "up": [0, 0, 1],
                              "width_mm": 1, "height_mm": 1, "pitch_mm": 1,
                              "schema_version": "99.0"})
        with self.assertRaises(ValueError):
            ser.migrate_dict({"not": "a port or module"})

    def test_golden_straight_ports_fixture(self):
        with open(os.path.join(FIXTURES, "straight_1400W450H750_ports.json"),
                  encoding="utf-8") as fh:
            golden = json.load(fh)
        module = create_straight_module(1400.0, 450.0, 750.0, 60.0, 110.0,
                                        700.0, 100.0, True)
        for key in ("inlet_port", "outlet_port"):
            live = module.to_dict()[key]
            for coord in ("origin_mm", "direction", "lateral_axis", "up"):
                for got, want in zip(live[coord], golden[key][coord]):
                    self.assertAlmostEqual(got, want, places=9)
            for scalar in ("width_mm", "height_mm", "pitch_mm"):
                self.assertAlmostEqual(live[scalar], golden[key][scalar])


if __name__ == "__main__":
    unittest.main()
