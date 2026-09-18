import os
import unittest

from fusion_conveyor_generator import (
    ConveyorInput,
    build_bom_from_model,
    demo_configurations,
    derive_configuration,
    deterministic_signature,
    generate_three_configurations,
    leg_count_for,
    roller_count_for,
    roller_margin_mm,
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

    def test_invalid_out_of_range_input_is_rejected(self):
        params = ConveyorInput(
            length_mm=500.0,  # below allowed 800-2000
            width_mm=400.0,
            height_mm=600.0,
            roller_diameter_mm=50.0,
            roller_spacing_mm=100.0,
            support_spacing_mm=700.0,
            side_guard_height_mm=40.0,
            side_guards=True,
        )
        with self.assertRaises(ValueError):
            validate_inputs(params)

    def test_guard_visibility_independent_of_height(self):
        # Brief edge case: suppression controls visibility, height stays as
        # modelled. False + G>0 must be accepted (previously rejected).
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
        validate_inputs(params)  # must not raise
        derived = derive_configuration(params)
        self.assertTrue(verify_configuration(params, derived)["all"])

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
        self.assertNotIn("frame_cross_members", bom)  # no such geometry exists
        self.assertEqual(bom["side_guards"], 2)
        self.assertGreater(bom["rollers"], 0)

    def test_bom_from_model_matches_derived_when_in_sync(self):
        for cfg in demo_configurations().values():
            derived = derive_configuration(cfg)
            model_bom = build_bom_from_model(derived.roller_count, derived.support_pair_count, cfg.side_guards)
            offline_bom = summarize_configuration(cfg)["bom"]
            self.assertEqual(model_bom, offline_bom)

    def test_floor_pitch_counts_match_fusion_formulas(self):
        for cfg in demo_configurations().values():
            derived = derive_configuration(cfg)
            self.assertEqual(derived.roller_count, roller_count_for(cfg.length_mm, cfg.roller_diameter_mm, cfg.roller_spacing_mm))
            self.assertEqual(derived.support_pair_count, leg_count_for(cfg.length_mm, cfg.support_spacing_mm))
            # Fixed pitch (Spacing type): spacing equals requested pitch when >1 instance.
            if derived.roller_count > 1:
                self.assertAlmostEqual(derived.actual_roller_spacing_mm, cfg.roller_spacing_mm)
            if derived.support_pair_count > 1:
                # Min-2 fallback may clamp spacing below pitch only when the
                # usable span is shorter than one pitch; otherwise equals pitch.
                self.assertLessEqual(derived.actual_support_spacing_mm, cfg.support_spacing_mm + 1e-9)
            # Roller margin matches Fusion RollerMargin = D/2 + 10.
            self.assertAlmostEqual(roller_margin_mm(cfg.roller_diameter_mm), cfg.roller_diameter_mm / 2.0 + 10.0)

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
                self.assertEqual(rows[0], ["Part Name", "Quantity", "Mass (kg)", "Dimensions / Notes"])
                self.assertEqual(len(rows), 5)  # Header + Rails + Rollers + Legs + Guards
                for row in rows[1:]:
                    self.assertGreaterEqual(float(row[2]), 0.0)

    def test_mass_estimates_positive_and_guards_add_mass(self):
        from fusion_conveyor_generator import estimate_part_masses_kg

        guarded = demo_configurations()["C2_medium_with_guards"]
        bare = demo_configurations()["C1_compact_no_guards"]
        masses_guarded = estimate_part_masses_kg(guarded, derive_configuration(guarded))
        masses_bare = estimate_part_masses_kg(bare, derive_configuration(bare))
        for part in ("Side Rails", "Rollers", "Support Leg Posts"):
            self.assertGreater(masses_guarded[part], 0.0)
            self.assertGreater(masses_bare[part], 0.0)
        self.assertGreater(masses_guarded["Side Guards"], 0.0)
        self.assertEqual(masses_bare["Side Guards"], 0.0)

    def test_hygiene_helpers_classify_sketches(self):
        from fusion_conveyor_generator import (
            _api_count,
            _is_sketch_empty,
            clean_for_export,
            find_empty_sketches,
        )

        class Coll:
            def __init__(self, n):
                self._n = n

            @property
            def count(self):
                return self._n

        class Curves:
            def __init__(self, n):
                for attr in ("sketchLines", "sketchArcs", "sketchCircles", "sketchPoints"):
                    setattr(self, attr, Coll(n))

        class Profiles:
            def __init__(self, n):
                self._n = n

            @property
            def count(self):
                return self._n

        class Sketch:
            def __init__(self, name, curves, dims, texts, profs):
                self.name = name
                self.sketchCurves = curves
                self.sketchDimensions = dims
                self.sketchTexts = texts
                self.profiles = profs
                self.deleted = False

            def deleteMe(self):
                self.deleted = True

        class Sketches:
            def __init__(self, items):
                self._items = items

            @property
            def count(self):
                return len(self._items)

            def item(self, i):
                return self._items[i]

        class Comp:
            def __init__(self, items):
                self.sketches = Sketches(items)

        full = Sketch("Full", Curves(4), Coll(3), Coll(0), Profiles(2))
        empty = Sketch("Empty", Curves(0), Coll(0), Coll(0), Profiles(0))
        comp = Comp([full, empty])

        self.assertEqual(_api_count(Coll(3)), 3)
        self.assertEqual(_api_count(None), 0)
        self.assertFalse(_is_sketch_empty(full))
        self.assertTrue(_is_sketch_empty(empty))
        self.assertEqual(find_empty_sketches(comp), ["Empty"])
        self.assertEqual(clean_for_export(None, comp), ["Empty"])
        self.assertTrue(empty.deleted)
        self.assertFalse(full.deleted)

    def test_snapshot_writers_emit_index_and_compare_page(self):
        import csv
        import tempfile
        from fusion_conveyor_generator import write_snapshot_compare_page, write_snapshots_csv

        rows = [
            {"config": "C1", "L_mm": 900.0, "rollers": 10, "stations": 2,
             "validation_pass": True, "bom_file": "C1_BOM.csv",
             "step_file": "C1.step", "params_line": "L=900 | 10 rollers",
             "image": "", "passed": True},
            {"config": "C2", "L_mm": 1400.0, "rollers": 13, "stations": 2,
             "validation_pass": True, "bom_file": "C2_BOM.csv",
             "step_file": "C2.step", "params_line": "L=1400 | 13 rollers",
             "image": "C2.png", "passed": True},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = write_snapshots_csv(tmpdir, rows)
            with open(csv_path, "r", encoding="utf-8") as f:
                read_rows = list(csv.DictReader(f))
            self.assertEqual(len(read_rows), 2)
            self.assertEqual(read_rows[0]["config"], "C1")
            self.assertEqual(read_rows[1]["rollers"], "13")

            page_path = write_snapshot_compare_page(tmpdir, rows)
            with open(page_path, "r", encoding="utf-8") as f:
                page = f.read()
            self.assertIn("C1", page)
            self.assertIn("C2.png", page)
            self.assertIn("No viewport capture", page)

    def test_label_and_etch_helpers_never_raise_offline(self):
        from fusion_conveyor_generator import (
            _try_capture_viewport,
            clear_etch_sketch,
            etch_text_label,
            label_model_for_config,
        )

        class Named:
            def __init__(self, name=""):
                self.name = name

        refs = {"occurrence": Named("occ"), "component": Named("comp")}
        self.assertEqual(label_model_for_config(refs, "C2"), "ParametricConveyor_C2")
        self.assertEqual(refs["occurrence"].name, "ParametricConveyor_C2")
        self.assertEqual(label_model_for_config({}, "C2"), "ParametricConveyor_C2")

        class BareComp:
            sketches = None
            features = None

        self.assertFalse(clear_etch_sketch(BareComp()))
        ok, reason = etch_text_label(BareComp(), "C2")
        self.assertFalse(ok)
        self.assertTrue(len(reason) > 0)
        self.assertIn("skipped", _try_capture_viewport("/nonexistent/x.png"))

    def test_formula_parameter_calculations(self):
        for name, cfg in demo_configurations().items():
            expected_rc = roller_count_for(cfg.length_mm, cfg.roller_diameter_mm, cfg.roller_spacing_mm)
            expected_lc = leg_count_for(cfg.length_mm, cfg.support_spacing_mm)
            self.assertGreater(expected_rc, 0)
            self.assertGreater(expected_lc, 0)
            # Lock CAD<->BOM<->Brief sync: derived positions must equal formulas.
            derived = derive_configuration(cfg)
            self.assertEqual(derived.roller_count, expected_rc, f"{name} roller drift")
            self.assertEqual(derived.support_pair_count, expected_lc, f"{name} leg drift")


if __name__ == "__main__":
    unittest.main()
