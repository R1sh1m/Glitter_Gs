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
        long = ConveyorInput(1950.0, 580.0, 880.0, 80.0, 145.0, 700.0, 120.0, True)

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


class StraightHoleTests(unittest.TestCase):
    def test_hole_stations_equal_roller_positions(self):
        from fusion_conveyor_generator import (
            derive_configuration,
            demo_configurations,
            straight_hole_stations,
        )
        cfg = demo_configurations()["C2_medium_with_guards"]
        derived = derive_configuration(cfg)
        stations = straight_hole_stations(cfg, derived)
        self.assertEqual(len(stations), derived.roller_count)
        self.assertEqual(list(stations), list(derived.roller_positions_mm))

    def test_thin_axis_detection(self):
        from fusion_conveyor_generator import thin_axis_of_bbox
        # Rail-like bbox: long x, 40 mm thin y, mid z (cm units)
        self.assertEqual(
            thin_axis_of_bbox((0.0, 71.0, 0.0), (140.0, 75.0, 45.0)), "y")
        self.assertEqual(
            thin_axis_of_bbox((0.0, 0.0, -79.3), (82.0, 125.0, -75.3)), "z")

    def test_hole_gate_and_verifier(self):
        import math
        from fusion_conveyor_generator import (
            derive_configuration,
            demo_configurations,
            keeps_hole_profile_straight,
            verify_straight_holes,
        )
        self.assertTrue(keeps_hole_profile_straight(math.pi * 0.8 ** 2))
        self.assertFalse(keeps_hole_profile_straight(2500.0))
        derived = derive_configuration(demo_configurations()["C2_medium_with_guards"])
        n = derived.roller_count
        self.assertTrue(verify_straight_holes(n, n, derived)["all"])
        self.assertTrue(verify_straight_holes(n - 2, n, derived)["all"])
        self.assertFalse(verify_straight_holes(n - 3, n, derived)["all"])

    def test_subset_helpers(self):
        from fusion_conveyor_generator import (
            subset_extents_mm,
            validate_straight_subset,
            derive_configuration,
            demo_configurations,
        )
        self.assertIsNone(subset_extents_mm([]))
        boxes = [((0.0, 0.0, 0.0), (140.0, 85.0, 45.0))]
        ext = subset_extents_mm(boxes)
        self.assertIsNotNone(ext)
        assert ext is not None
        self.assertEqual(ext[0], (0.0, 0.0, 0.0))
        self.assertEqual(ext[1], (1400.0, 850.0, 450.0))
        cfg = demo_configurations()["C2_medium_with_guards"]
        derived = derive_configuration(cfg)
        checks = validate_straight_subset(cfg, derived, ext)
        self.assertTrue(checks["all"])
        bad = validate_straight_subset(cfg, derived, None)
        self.assertFalse(bad["all"])

    def test_rect_measured_edges_and_single_direction(self):
        from types import SimpleNamespace as NS
        from fusion_conveyor_generator import _rect_long_short, _single_pattern_direction

        def pt(x, y):
            return NS(x=x, y=y, z=0.0)

        def ln(a, b):
            return NS(startSketchPoint=NS(geometry=a), endSketchPoint=NS(geometry=b))

        # Long edge along X regardless of item order (reversed input order)
        lines = [ln(pt(10, 32), pt(0, 32)), ln(pt(0, 32), pt(0, 30)),
                 ln(pt(0, 30), pt(10, 30)), ln(pt(10, 30), pt(10, 32))]
        coll = NS(count=4, item=lambda i: lines[i])
        long_e, short_e = _rect_long_short(coll)
        la = long_e.startSketchPoint.geometry
        lb = long_e.endSketchPoint.geometry
        self.assertAlmostEqual(abs(lb.x - la.x) + abs(lb.y - la.y), 10.0)
        sa = short_e.startSketchPoint.geometry
        sb = short_e.endSketchPoint.geometry
        self.assertAlmostEqual(abs(sb.x - sa.x) + abs(sb.y - sa.y), 2.0)

        # Single-direction pinning never raises, sets when supported
        _single_pattern_direction(object())
        import fusion_conveyor_generator as fcg_mod
        real_adsk = fcg_mod.adsk
        marker = object()

        class FakeVI:
            @staticmethod
            def createByReal(v):
                return ("real", v, marker)

            @staticmethod
            def createByString(s):
                return ("str", s, marker)

        class FakeCore:
            ValueInput = FakeVI

        class FakeAdsk:
            core = FakeCore()

        fcg_mod.adsk = FakeAdsk()
        try:
            holder = {}
            from types import SimpleNamespace as NS2
            holder = NS2(quantityTwo=None, distanceTwo=None, isSymmetricInDirectionTwo=True)
            _single_pattern_direction(holder)
            self.assertEqual(holder.quantityTwo[0], "real")
            self.assertEqual(holder.distanceTwo[0], "str")
            self.assertFalse(holder.isSymmetricInDirectionTwo)
        finally:
            fcg_mod.adsk = real_adsk

    def test_frame_proof_validator_detects_axes(self):
        from fusion_conveyor_generator import (
            derive_configuration,
            demo_configurations,
            validate_straight_subset,
        )
        cfg = demo_configurations()["C2_medium_with_guards"]
        derived = derive_configuration(cfg)
        # Z-up layout (length X, height Z) as built live
        checks = validate_straight_subset(cfg, derived, ((0.0, 0.0, 0.0), (1400.0, 450.0, 850.0)))
        self.assertTrue(checks["all"])
        self.assertEqual(checks["axes"]["height"], "z")
        # Y-up layout maps the same way
        checks2 = validate_straight_subset(cfg, derived, ((0.0, 0.0, 0.0), (1400.0, 850.0, 450.0)))
        self.assertTrue(checks2["all"])
        self.assertEqual(checks2["axes"]["height"], "y")

    def test_conveyor_capacity_calculation(self):
        from fusion_conveyor_generator import (
            ConveyorInput,
            derive_configuration,
            calculate_conveyor_capacity,
        )
        c2 = ConveyorInput(1400.0, 450.0, 750.0, 60.0, 110.0, 700.0, 100.0, True, cross_bracing=True)
        derived = derive_configuration(c2)
        self.assertIsNotNone(derived.capacity)
        cap = derived.capacity
        self.assertGreater(cap.rated_total_capacity_kg, 100.0)
        self.assertGreater(cap.roller_capacity_kg, 40.0)
        self.assertGreater(cap.max_unit_package_kg, 100.0)
        self.assertGreaterEqual(cap.structural_safety_factor, 1.2)
        self.assertIn(cap.limiting_component, ("Rollers", "Side Rails", "Leg Supports"))

        # Cross-bracing improves leg capacity
        unbraced = ConveyorInput(1400.0, 450.0, 750.0, 60.0, 110.0, 700.0, 100.0, True, cross_bracing=False)
        cap_unbraced = calculate_conveyor_capacity(unbraced, derive_configuration(unbraced))
        self.assertGreater(cap.total_support_capacity_kg, cap_unbraced.total_support_capacity_kg)

    def test_autonomous_optimization_engine(self):
        from fusion_conveyor_generator import (
            autonomous_optimize_conveyor,
            derive_configuration,
            validate_inputs,
        )
        # Light duty: small rollers, unbraced low frame
        light = autonomous_optimize_conveyor(150.0, 1000.0, 400.0, 600.0, side_guards=True, duty_class="light")
        validate_inputs(light)
        self.assertEqual(light.roller_diameter_mm, 40.0)
        self.assertFalse(light.cross_bracing)

        # Pallet heavy duty: large rollers, tight pitch, cross-braced
        heavy = autonomous_optimize_conveyor(1800.0, 2000.0, 600.0, 850.0, side_guards=True, duty_class="pallet")
        validate_inputs(heavy)
        self.assertEqual(heavy.roller_diameter_mm, 80.0)
        self.assertTrue(heavy.cross_bracing)
        d_heavy = derive_configuration(heavy)
        self.assertGreaterEqual(d_heavy.capacity.rated_total_capacity_kg, 500.0)

    def test_cross_bracing_bom_and_mass(self):
        from fusion_conveyor_generator import (
            ConveyorInput,
            derive_configuration,
            build_bom,
            estimate_part_masses_kg,
            estimate_hardware_masses_kg,
        )
        braced = ConveyorInput(1400.0, 450.0, 750.0, 60.0, 110.0, 700.0, 100.0, True, cross_bracing=True)
        d_braced = derive_configuration(braced)
        bom = build_bom(d_braced, True)
        self.assertIn("leg_cross_struts", bom)
        self.assertEqual(bom["leg_cross_struts"], d_braced.support_pair_count)

        masses = estimate_part_masses_kg(braced, d_braced)
        self.assertIn("Leg Cross-Struts", masses)
        self.assertGreater(masses["Leg Cross-Struts"], 0.0)

        hw = estimate_hardware_masses_kg(braced, d_braced)
        self.assertIn("Leg Cross-Struts (RHS 40x20)", hw)
        self.assertIn("Cross-Strut Hardware M8", hw)

    def test_opcua_telemetry_contains_capacity(self):
        from fusion_conveyor_generator import (
            ConveyorInput,
            derive_configuration,
            generate_opcua_metadata,
        )
        cfg = ConveyorInput(1400.0, 450.0, 750.0, 60.0, 110.0, 700.0, 100.0, True, cross_bracing=True)
        derived = derive_configuration(cfg)
        meta = generate_opcua_metadata(cfg, derived, "TEST_CAP")
        ratings = meta["spec_ratings"]
        self.assertIn("rated_capacity_kg", ratings)
        self.assertIn("safety_factor", ratings)
        self.assertTrue(ratings["cross_bracing_enabled"])


if __name__ == "__main__":
    unittest.main()
