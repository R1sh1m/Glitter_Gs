import math
import unittest

from fusion_gear_generator import GearInput, derive_geometry, verify_pair


class GearMathTests(unittest.TestCase):
    def test_spur_example_configuration(self):
        params = GearInput("spur", 2.0, 20, 40, 20.0, 10.0, 0.0)
        g = derive_geometry(params)

        self.assertAlmostEqual(g.ratio, 2.0)
        self.assertAlmostEqual(g.d1, 40.0)
        self.assertAlmostEqual(g.d2, 80.0)
        self.assertAlmostEqual(g.center_distance, 60.0)
        self.assertTrue(verify_pair(params, g)["all"])

    def test_helical_example_configuration(self):
        params = GearInput("helical", 2.0, 20, 60, 20.0, 12.0, 20.0)
        g = derive_geometry(params)

        expected_mt = 2.0 / math.cos(math.radians(20.0))
        self.assertAlmostEqual(g.mt, expected_mt)
        self.assertAlmostEqual(g.ratio, 3.0)
        self.assertTrue(verify_pair(params, g)["all"])

    def test_unseen_parameter_set(self):
        params = GearInput("helical", 2.5, 24, 72, 20.0, 14.0, 15.0)
        g = derive_geometry(params)

        self.assertAlmostEqual(g.ratio, 3.0)
        self.assertTrue(g.center_distance > 0)
        self.assertTrue(verify_pair(params, g)["all"])


if __name__ == "__main__":
    unittest.main()
