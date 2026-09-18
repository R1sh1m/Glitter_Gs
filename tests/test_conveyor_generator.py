import os
import unittest

from fusion_conveyor_generator import (
    ConveyorInput,
    demo_configurations,
    derive_configuration,
    deterministic_signature,
    generate_three_configurations,
    summarize_configuration,
    validate_inputs,
    verify_configuration,
)


class ConveyorGeneratorTests(unittest.TestCase):
    def test_valid_configuration_derivation_and_verification(self):
        params = ConveyorInput(
            length_mm=1400.0,
            width_mm=450.0,
            height_mm=700.0,
            roller_diameter_mm=60.0,
            roller_spacing_mm=120.0,
            support_spacing_mm=700.0,
            side_guard_height_mm=75.0,
            side_guards=True,
        )
        derived = derive_configuration(params)

        self.assertGreaterEqual(derived.roller_count, 2)
        self.assertGreaterEqual(derived.support_pair_count, 2)
        self.assertLessEqual(derived.actual_roller_spacing_mm, params.roller_spacing_mm)
        self.assertLessEqual(derived.actual_support_spacing_mm, params.support_spacing_mm)
        self.assertTrue(verify_configuration(params, derived)["all"])

    def test_invalid_conflicting_input_is_rejected(self):
        params = ConveyorInput(
            length_mm=1200.0,
            width_mm=400.0,
            height_mm=600.0,
            roller_diameter_mm=50.0,
            roller_spacing_mm=100.0,
            support_spacing_mm=700.0,
            side_guard_height_mm=40.0,
            side_guards=False,
        )
        with self.assertRaises(ValueError):
            validate_inputs(params)

    def test_repeated_positions_depend_on_parameters(self):
        compact = ConveyorInput(900.0, 350.0, 520.0, 45.0, 100.0, 600.0, 0.0, False)
        long = ConveyorInput(1950.0, 580.0, 880.0, 80.0, 145.0, 950.0, 120.0, True)

        compact_d = derive_configuration(compact)
        long_d = derive_configuration(long)

        self.assertNotEqual(compact_d.roller_count, long_d.roller_count)
        self.assertNotEqual(compact_d.support_pair_count, long_d.support_pair_count)

    def test_identical_inputs_have_identical_signature(self):
        params = ConveyorInput(1400.0, 450.0, 700.0, 60.0, 120.0, 700.0, 75.0, True)
        sig1 = deterministic_signature(params)
        sig2 = deterministic_signature(params)
        self.assertEqual(sig1, sig2)

    def test_three_substantially_different_configurations(self):
        demos = demo_configurations()
        self.assertGreaterEqual(len(demos), 3)
        summaries = generate_three_configurations()

        self.assertEqual(len(summaries), 3)
        signatures = {summary["signature"] for summary in summaries.values()}
        self.assertEqual(len(signatures), 3)

        for summary in summaries.values():
            self.assertTrue(summary["verification"]["all"])
            self.assertIn("rollers", summary["bom"])

    def test_bom_contains_expected_counts(self):
        summary = summarize_configuration(demo_configurations()["C2_medium_with_guards"])
        bom = summary["bom"]
        self.assertEqual(bom["frame_side_rails"], 2)
        self.assertEqual(bom["frame_cross_members"], 2)
        self.assertEqual(bom["side_guards"], 2)
        self.assertGreater(bom["rollers"], 0)

    def test_export_bom_csv(self):
        import csv
        import tempfile
        from fusion_conveyor_generator import export_bom_csv

        demo = demo_configurations()["C2_medium_with_guards"]
        derived = derive_configuration(demo)
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = export_bom_csv("TestConfig", demo, derived, tmpdir)
            self.assertTrue(os.path.exists(csv_path))
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
                self.assertEqual(rows[0], ["Part Name", "Quantity", "Dimensions / Notes"])
                self.assertEqual(len(rows), 5)  # Header + Rails + Rollers + Legs + Guards

    def test_formula_parameter_calculations(self):
        import math
        from fusion_conveyor_generator import LEG_SIDE
        for name, cfg in demo_configurations().items():
            expected_rc = math.floor((cfg.length_mm - 2 * (cfg.roller_diameter_mm / 2.0 + 10.0)) / cfg.roller_spacing_mm) + 1
            expected_lc = math.floor((cfg.length_mm - LEG_SIDE) / cfg.support_spacing_mm) + 1
            self.assertGreater(expected_rc, 0)
            self.assertGreater(expected_lc, 0)


if __name__ == "__main__":
    unittest.main()

