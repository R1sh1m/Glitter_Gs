"""Offline tests for the conveyor add-in dialog helpers (no Fusion needed)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "conveyor_addin"))

import conveyor_addin as addin  # noqa: E402
from fusion_conveyor_generator import RANGES  # noqa: E402


class ConveyorAddinHelperTests(unittest.TestCase):
    def test_dialog_defaults_in_range(self):
        defaults = addin.dialog_defaults()
        self.assertTrue(defaults[addin.GUARDS_ID])
        for _sid, _label, _unit, key, _tip in addin.INPUT_SPECS:
            lo, hi = RANGES[key]
            self.assertGreaterEqual(defaults[_sid], lo)
            self.assertLessEqual(defaults[_sid], hi)

    def test_values_round_trip_and_guard_strings(self):
        params = addin.values_to_input(addin.dialog_defaults())
        self.assertTrue(params.side_guards)
        yes_vals = dict(addin.dialog_defaults(), **{addin.GUARDS_ID: "Yes"})
        no_vals = dict(addin.dialog_defaults(), **{addin.GUARDS_ID: "no"})
        self.assertTrue(addin.values_to_input(yes_vals).side_guards)
        self.assertFalse(addin.values_to_input(no_vals).side_guards)

    def test_values_reject_out_of_range(self):
        bad = dict(addin.dialog_defaults(), in_length=100.0)
        with self.assertRaises(ValueError):
            addin.values_to_input(bad)

    def test_preview_text_reports_counts(self):
        params = addin.values_to_input(addin.dialog_defaults())
        text = addin.preview_text(params)
        self.assertIn("Rollers:", text)
        self.assertIn("Leg stations:", text)
        self.assertIn("Est. steel mass:", text)

    def test_addin_module_imports_without_fusion(self):
        self.assertFalse(addin._HAS_ADSK)
        self.assertEqual(addin.ADDIN_ID, "GlitterGsConveyorAddin")


if __name__ == "__main__":
    unittest.main()
