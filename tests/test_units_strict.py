"""Strict-units tests: conversions, value types, double-convert regression.

Also enforces the units ban: no raw mm<->cm arithmetic (``/ 10``, ``* 10``)
or ``convert(`` calls in new ``core/`` (except ``units.py`` itself),
``docking/`` (except ``apply.py``/``frames`` packing) or ``modules/``
(except ``adapters.py``, which only forwards to legacy engines).
"""

import os
import re
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

from core import units  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_PACKAGES = ("conveyor_addin/core", "conveyor_addin/docking", "conveyor_addin/modules")

# files allowed to touch raw scale factors / Fusion convert()
BAN_EXEMPT = {
    "conveyor_addin/core/units.py",
    "conveyor_addin/core/frames.py",  # to_fusion_cells packs via units.mm_to_cm
    "conveyor_addin/docking/apply.py",  # thin adsk boundary (delegates to frames)
    "conveyor_addin/modules/adapters.py",  # forwards to legacy engines only
}

RAW_SCALE_RE = re.compile(r"(/|\*)\s*10(\.0)?(?![\d.])")


class UnitsTests(unittest.TestCase):
    def test_mm_cm_round_trip(self):
        self.assertAlmostEqual(units.cm_to_mm(140.0), 1400.0)
        self.assertAlmostEqual(units.mm_to_cm(1400.0), 140.0)
        self.assertAlmostEqual(units.cm_to_mm(units.mm_to_cm(753.0)), 753.0)

    def test_deg_rad_round_trip(self):
        self.assertAlmostEqual(units.rad_to_deg(3.141592653589793), 180.0, places=9)
        self.assertAlmostEqual(units.deg_to_rad(90.0), 1.5707963267948966)
        self.assertAlmostEqual(
            units.rad_to_deg(units.deg_to_rad(37.0)), 37.0, places=12
        )

    def test_length_value_type(self):
        length = units.Length.from_mm(1400.0)
        self.assertAlmostEqual(length.to_cm(), 140.0)
        self.assertAlmostEqual(units.Length.from_cm(140.0).to_mm(), 1400.0)
        total = length + units.Length.from_mm(100.0)
        self.assertAlmostEqual(total.to_mm(), 1500.0)
        with self.assertRaises(TypeError):
            units.Length(mm="1400")  # type: ignore[arg-type]

    def test_angle_value_type(self):
        angle = units.Angle.from_deg(90.0)
        self.assertAlmostEqual(angle.to_rad(), 1.5707963267948966)
        self.assertAlmostEqual(units.Angle.from_rad(angle.to_rad()).to_deg(), 90.0)

    def test_fusion_boundary_helpers(self):
        # evaluateExpression already returns requested units: mm passes through.
        self.assertAlmostEqual(units.fusion_length_to_mm(1400.0, "mm"), 1400.0)
        self.assertAlmostEqual(units.fusion_length_to_mm(140.0, "cm"), 1400.0)
        self.assertAlmostEqual(units.fusion_angle_to_deg(90.0, "deg"), 90.0)
        self.assertAlmostEqual(
            units.fusion_angle_to_deg(1.5707963267948966, "rad"), 90.0, places=9
        )
        with self.assertRaises(ValueError):
            units.fusion_length_to_mm(1.0, "inch")

    def test_no_double_conversion_regression(self):
        """1400mm must survive a single cm->mm convert (historic 14000 bug)."""

        class _FakeUnits:
            def evaluateExpression(self, expr, unit):
                self.seen = (expr, unit)
                return 140.0  # cm

            def convert(self, value, frm, to):
                self.converted = (value, frm, to)
                return 1400.0

        fake = _FakeUnits()
        self.assertAlmostEqual(units.evaluate_to_mm(fake, "1400 mm"), 1400.0)
        self.assertEqual(fake.seen[1], "cm")
        self.assertEqual(fake.converted, (140.0, "cm", "mm"))

    def test_evaluate_without_convert_falls_back(self):
        class _OldUnits:
            def evaluateExpression(self, expr, unit):
                return 140.0

        self.assertAlmostEqual(
            units.evaluate_to_mm(_OldUnits(), "1400 mm"), 1400.0
        )

    def test_raw_scale_ban_in_new_code(self):
        offenders = []
        for package in NEW_PACKAGES:
            root = os.path.join(REPO_ROOT, *package.split("/"))
            for dirpath, _, filenames in os.walk(root):
                for name in filenames:
                    if not name.endswith(".py"):
                        continue
                    rel = os.path.relpath(os.path.join(dirpath, name), REPO_ROOT)
                    rel = rel.replace(os.sep, "/")
                    if rel in BAN_EXEMPT:
                        continue
                    with open(os.path.join(dirpath, name), encoding="utf-8") as fh:
                        for lineno, line in enumerate(fh, 1):
                            if RAW_SCALE_RE.search(line) or "convert(" in line:
                                offenders.append(f"{rel}:{lineno}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "Raw mm<->cm arithmetic outside core/units.py:\n" + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
