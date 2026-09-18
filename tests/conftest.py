"""Pytest bootstrap: make the repo root importable under any runner.

`python -m pytest` puts CWD on `sys.path`, but the bare `pytest` console
script (as used in CI) does not. Inserting the root here keeps both working.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
