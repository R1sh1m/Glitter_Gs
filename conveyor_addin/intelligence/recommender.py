"""Recommender — proposes SPEC DATA ONLY. NEVER generates CAD.

Contract (enforced by tests):
  - Output is JSON-serializable data: ``{spec, reasoning, rule_ids,
    baseline_score, must_validate, cad_actions: []}``.
  - This module imports NO Fusion runtime and calls NO geometry builders.
    It cannot reach CAD even by accident (source scan enforces this).
  - Every recommendation must still pass ``rules_engine.gate``; the
    recommender runs the gate itself and attaches the findings.
"""

from __future__ import annotations

import json
from typing import Any, Dict

try:
    from intelligence import knowledge_base as _kb
except ImportError:
    from conveyor_addin.intelligence import knowledge_base as _kb  # type: ignore[no-redef]

try:
    from intelligence import rules_engine as _rules
except ImportError:
    from conveyor_addin.intelligence import rules_engine as _rules  # type: ignore[no-redef]

__all__ = ["recommend"]


def recommend(box_mass_kg: float, box_len_mm: float, box_wid_mm: float,
              length_mm: float = 1400.0, height_mm: float = 750.0,
              curved: bool = False) -> Dict[str, Any]:
    """Recommend a conveyor spec for a package (data only)."""
    duty = _kb.duty_for_load(box_mass_kg)
    ref = _kb.DUTY_CLASSES[duty]
    spec = {
        "length_mm": float(length_mm),
        "width_mm": _kb.width_for_box(box_wid_mm, curved=curved),
        "height_mm": float(height_mm),
        "roller_diameter_mm": ref["dia"],
        "roller_spacing_mm": min(ref["pitch"], _kb.pitch_for_box(box_len_mm)),
        "support_spacing_mm": ref["leg"],
        "side_guard_height_mm": 100.0,
        "side_guards": True,
    }
    findings = _rules.evaluate_spec(spec, box_mass_kg, box_len_mm, box_wid_mm)
    recommendation = {
        "spec": spec,
        "reasoning": [
            f"duty class {duty} for {box_mass_kg:.0f}kg",
            f"P-3ROLLERS: P={spec['roller_spacing_mm']:.0f} "
            f"<= box/3={box_len_mm / 3.0:.0f}",
            f"W-MARGIN: W={spec['width_mm']:.0f} for box {box_wid_mm:.0f}mm",
        ],
        "rule_ids": ["P-3ROLLERS", "W-MARGIN", "D-LOAD", "S-LOAD"],
        "gate_findings": [{"rule_id": f.rule_id, "status": f.status,
                           "message": f.message} for f in findings],
        "gate_accepted": _rules.is_acceptable(findings),
        "baseline_score": _kb.score_spec(spec, box_mass_kg),
        "must_validate": True,
        "cad_actions": [],
    }
    json.dumps(recommendation)  # contract: JSON-serializable
    return recommendation
