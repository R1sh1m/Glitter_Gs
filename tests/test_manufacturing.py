"""Manufacturing tests — BOM, cut list, instructions, report (offline)."""

import csv
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

from manufacturing import bom as B  # noqa: E402
from manufacturing import cutlist as C  # noqa: E402
from manufacturing import instructions as Instr  # noqa: E402
from manufacturing import report as R  # noqa: E402
from modules.curve import create_curve_module  # noqa: E402
from modules.straight import create_straight_module  # noqa: E402


class ManufacturingTests(unittest.TestCase):
    def setUp(self):
        self.straight = create_straight_module(2400.0 - 400.0, 450.0, 750.0,
                                               60.0, 110.0, 700.0, 100.0,
                                               True)  # L2000
        self.curve = create_curve_module(800.0, 90.0, 450.0, 750.0, 50.0,
                                         110.0, 700.0, 100.0, True)

    def _row(self, rows, part):
        matches = [r for r in rows if r["part"] == part]
        self.assertEqual(len(matches), 1, f"missing BOM row {part!r}")
        return matches[0]

    def test_fabrication_bom_example_values(self):
        rows = B.fabrication_bom(self.straight)
        # Frame: 40x40-family rails — 2 x 2000mm = 4.0m
        self.assertAlmostEqual(self._row(rows, "Side rail 20x40")["quantity"],
                               4.0)
        # Rollers: 50mm dia example shape — C2-style N rollers + shafts
        n = self.straight.engineering_parameters["roller_count"]
        self.assertEqual(self._row(rows, "Roller dia 60")["quantity"], n)
        self.assertEqual(self._row(rows, "Roller shaft dia14")["quantity"], n)
        # Bearings: 6002, 2 per roller
        self.assertEqual(self._row(rows, "Bearing 6002-2RZ")["quantity"], 2 * n)

    def test_cut_list_example_values(self):
        cuts = C.cut_list(self.straight)

        def _cut(part):
            matches = [c for c in cuts if c["part"] == part]
            self.assertEqual(len(matches), 1, f"missing cut {part!r}")
            return matches[0]

        rail = _cut("Side rail")
        self.assertAlmostEqual(rail["length_mm"], 2000.0)
        self.assertEqual(rail["quantity"], 2)
        shaft = _cut("Roller shaft dia14")
        self.assertAlmostEqual(shaft["length_mm"], 474.0)  # W + 24

    def test_instructions_canonical_steps(self):
        steps = Instr.assembly_instructions(self.straight)
        titles = [s["title"] for s in steps]
        self.assertEqual(titles[:4], ["Install side rails",
                                      "Install roller bearings",
                                      "Install rollers",
                                      "Install supports"])
        self.assertIn("Fit side guards", titles)
        curve_titles = [s["title"] for s in
                        Instr.assembly_instructions(self.curve)]
        self.assertIn("Verify taper orientation", curve_titles)

    def test_report_outputs(self):
        report = R.build_report("demo", [self.straight, self.curve],
                                validation={"valid": True})
        self.assertEqual(report["module_count"], 2)
        self.assertGreater(len(report["line_bom"]), 5)
        self.assertGreater(len(report["line_cut_list"]), 3)
        md = R.render_markdown(report)
        self.assertIn("## Line BOM", md)
        self.assertIn("## Cut List", md)
        self.assertIn("## Assembly Sequence", md)
        with tempfile.TemporaryDirectory() as tmp:
            paths = R.write_outputs(report, tmp, "demo")
            self.assertEqual(
                sorted(paths), ["bom_csv", "cutlist_csv", "json", "markdown"])
            with open(paths["bom_csv"], encoding="utf-8") as fh:
                bom_rows = list(csv.DictReader(fh))
            self.assertGreater(len(bom_rows), 5)
            with open(paths["json"], encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["line_name"], "demo")


if __name__ == "__main__":
    unittest.main()
