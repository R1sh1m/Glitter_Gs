"""Adapter regression: new module layer MUST equal legacy engine outputs.

Gate: root ``fusion_conveyor_generator.py`` / ``fusion_curve_module.py``
must NOT be deleted until this suite is green. Covers the demo configs
C1/C2/C3 + Curve90/45: roller counts, port origins, BOM, signatures.
"""

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

import fusion_conveyor_generator as legacy_straight  # noqa: E402
import fusion_curve_module as legacy_curve  # noqa: E402
from modules import adapters as ad  # noqa: E402
from modules.curve import create_curve_module  # noqa: E402
from modules.straight import create_straight_module  # noqa: E402

CASES = [
    # (L, W, H, D, P, S, G, guards)
    (900.0, 350.0, 600.0, 50.0, 90.0, 500.0, 0.0, False),  # C1
    (1400.0, 450.0, 750.0, 60.0, 110.0, 700.0, 100.0, True),  # C2
    (2000.0, 600.0, 900.0, 80.0, 150.0, 1000.0, 150.0, True),  # C3
]

CURVE_CASES = [
    # (Ri, angle, W, H, D_in, P_out, S, G, guards)
    (800.0, 90.0, 450.0, 750.0, 50.0, 110.0, 700.0, 100.0, True),
    (1000.0, 45.0, 500.0, 750.0, 60.0, 100.0, 700.0, 100.0, True),
]


class AdapterRegressionTests(unittest.TestCase):
    def test_ranges_match_legacy(self):
        self.assertEqual(ad.legacy_ranges(), legacy_straight.RANGES)
        self.assertEqual(ad.legacy_curve_ranges(), legacy_curve.CURVE_RANGES)

    def test_straight_counts_ports_bom_signature(self):
        for spec in CASES:
            with self.subTest(spec=spec):
                params = legacy_straight.ConveyorInput(
                    length_mm=spec[0], width_mm=spec[1], height_mm=spec[2],
                    roller_diameter_mm=spec[3], roller_spacing_mm=spec[4],
                    support_spacing_mm=spec[5], side_guard_height_mm=spec[6],
                    side_guards=spec[7],
                )
                legacy_derived = legacy_straight.derive_configuration(params)
                legacy_ports = legacy_straight.get_module_ports(params)
                legacy_bom = legacy_straight.build_bom(
                    legacy_derived, params.side_guards)
                legacy_sig = legacy_straight.deterministic_signature(
                    params, legacy_derived)

                module = create_straight_module(*spec)
                eng = module.engineering_parameters
                self.assertEqual(eng["roller_count"], legacy_derived.roller_count)
                self.assertEqual(eng["support_pair_count"],
                                 legacy_derived.support_pair_count)
                self.assertEqual(list(eng["roller_positions_mm"]),
                                 list(legacy_derived.roller_positions_mm))
                self.assertEqual(module.bom_data, legacy_bom)
                self.assertEqual(module.module_id, legacy_sig)
                for key, legacy_key in (("inlet_port", "inlet_port"),
                                        ("outlet_port", "outlet_port")):
                    port = getattr(module, key)
                    legacy_port = legacy_ports[legacy_key]
                    for got, want in zip(port.origin,
                                         legacy_port["origin_mm"]):
                        self.assertAlmostEqual(got, want, places=9)
                    self.assertAlmostEqual(port.roller_pitch,
                                           legacy_port["pitch_mm"])

    def test_curve_counts_ports(self):
        for spec in CURVE_CASES:
            with self.subTest(spec=spec):
                params = legacy_curve.CurveInput(
                    inner_radius_mm=spec[0], curve_angle_deg=spec[1],
                    width_mm=spec[2], height_mm=spec[3],
                    roller_dia_inner_mm=spec[4],
                    roller_pitch_outer_mm=spec[5],
                    support_spacing_mm=spec[6],
                    side_guard_height_mm=spec[7], side_guards=spec[8])
                legacy_derived = legacy_curve.derive_curve_configuration(params)
                legacy_ports = legacy_curve.get_curve_module_ports(
                    params, legacy_derived)
                module = create_curve_module(*spec)
                eng = module.engineering_parameters
                self.assertEqual(eng["roller_count"], legacy_derived.roller_count)
                self.assertEqual(eng["support_count"],
                                 legacy_derived.support_count)
                self.assertAlmostEqual(
                    eng["roller_dia_outer_mm"],
                    legacy_derived.roller_dia_outer_mm, places=9)
                for key, legacy_key in (("inlet_port", "inlet_port"),
                                        ("outlet_port", "outlet_port")):
                    port = getattr(module, key)
                    legacy_port = legacy_ports[legacy_key]
                    for got, want in zip(port.origin,
                                         legacy_port["origin_mm"]):
                        self.assertAlmostEqual(got, want, places=6)


if __name__ == "__main__":
    unittest.main()
