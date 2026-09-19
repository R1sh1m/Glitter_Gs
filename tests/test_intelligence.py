"""Intelligence tests — recommend-only contract + deterministic gates."""

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

from intelligence import knowledge_base as KB  # noqa: E402
from intelligence import optimizer as OPT  # noqa: E402
from intelligence import recommender as REC  # noqa: E402
from intelligence import rules_engine as RE  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The recommender must NEVER reach CAD: ban Fusion/builder references.
CAD_TOKENS = ("adsk", "build_parametric", "build_curve", "occurrences",
              "Matrix3D", "execute_api")


class IntelligenceTests(unittest.TestCase):
    def test_recommendation_passes_gate(self):
        rec = REC.recommend(120.0, 400.0, 350.0)
        self.assertTrue(rec["gate_accepted"], rec["gate_findings"])
        self.assertEqual(rec["cad_actions"], [])
        self.assertTrue(rec["must_validate"])
        self.assertLessEqual(rec["spec"]["roller_spacing_mm"], 400.0 / 3.0)
        json.dumps(rec)

    def test_gate_rejects_out_of_range(self):
        with self.assertRaises(RE.RecommendationRejected):
            RE.gate({"length_mm": 5000.0, "roller_spacing_mm": 110.0},
                    box_len_mm=400.0)

    def test_gate_rejects_pitch_violation(self):
        with self.assertRaises(RE.RecommendationRejected):
            RE.gate({"length_mm": 1400.0, "width_mm": 450.0,
                     "roller_spacing_mm": 150.0}, box_len_mm=300.0)

    def test_optimizer_returns_data_only(self):
        spec = OPT.optimize_spec(1400.0, 450.0, 750.0, 450.0)
        self.assertEqual(spec["source"], "autonomous_optimize_conveyor")
        findings = RE.gate(spec, box_mass_kg=450.0, box_len_mm=400.0,
                           box_wid_mm=350.0)
        self.assertTrue(RE.is_acceptable(findings))

    def test_knowledge_base_lookups(self):
        self.assertAlmostEqual(KB.pitch_for_box(400.0), 400.0 / 3.0)
        self.assertAlmostEqual(KB.width_for_box(350.0), 400.0)
        self.assertAlmostEqual(KB.width_for_box(350.0, curved=True), 450.0)
        self.assertEqual(KB.duty_for_load(100.0), "Light")
        self.assertEqual(KB.duty_for_load(2000.0), "Pallet")
        score = KB.score_spec({"roller_spacing_mm": 110.0,
                               "roller_diameter_mm": 60.0,
                               "support_spacing_mm": 700.0}, 450.0)
        self.assertEqual(score["score_0_1"], 1.0)

    def test_recommender_cannot_reach_cad(self):
        path = os.path.join(REPO_ROOT, "conveyor_addin", "intelligence",
                            "recommender.py")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        hits = [tok for tok in CAD_TOKENS if tok in source]
        self.assertEqual(hits, [], f"CAD tokens in recommender: {hits}")
        import subprocess  # noqa: E402
        res = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'conveyor_addin'); "
             "import intelligence.recommender; print(sorted(sys.modules))"],
            cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("adsk", res.stdout)


if __name__ == "__main__":
    unittest.main()
