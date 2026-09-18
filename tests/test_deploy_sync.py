"""Deploy-copy sync guard (no Fusion needed).

conveyor_addin/ ships byte-copies of the root engines so the add-in folder
is self-contained. Python resolves them FIRST (sys.path.insert in the
add-in tests), so a stale copy silently shadows new root APIs and breaks
unrelated tests. This test fails loudly with the exact fix instead.

Rule (see Docs/INTEGRATION.md lessons): after every root engine edit,
refresh the copies (Copy-Item root -> conveyor_addin/).
"""
import hashlib
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDIN = os.path.join(ROOT, "conveyor_addin")
SYNCED = (
    "fusion_conveyor_generator.py",
    "fusion_curve_module.py",
    "fusion_docking_system.py",
)


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class DeploySyncTests(unittest.TestCase):
    def test_deploy_copies_match_root(self):
        for name in SYNCED:
            root_p = os.path.join(ROOT, name)
            copy_p = os.path.join(ADDIN, name)
            self.assertTrue(os.path.exists(root_p), f"root {name} missing")
            self.assertTrue(os.path.exists(copy_p), f"deploy copy {name} missing")
            self.assertEqual(
                _sha(root_p), _sha(copy_p),
                f"STALE COPY: conveyor_addin/{name} differs from root. "
                f"Fix: Copy-Item \"{name}\" \"conveyor_addin\\{name}\" -Force",
            )


if __name__ == "__main__":
    unittest.main()
