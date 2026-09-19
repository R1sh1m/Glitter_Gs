"""Knowledge base — local engineering rules data (no learning, no network).

Tier-2 heuristics sourced from Interroll/Damon practice and Problem
Statement A ranges (see ``Docs/ENGINEERING.md``). Pure data + deterministic
lookup functions; the learning-ready hook is ``score_spec`` (feature
weights live here so a future local model trains against THESE features).
"""

from __future__ import annotations

from typing import Any, Dict, List

__all__ = [
    "RULES",
    "DUTY_CLASSES",
    "FEATURES",
    "get_rule",
    "pitch_for_box",
    "width_for_box",
    "duty_for_load",
    "score_spec",
]

RULES: Dict[str, Dict[str, Any]] = {
    "P-3ROLLERS": {
        "statement": "Roller pitch P <= box length / 3 (3 rollers under load)",
        "applies_to": ["Straight", "Transfer", "Merge", "Incline"],
    },
    "W-MARGIN": {
        "statement": "Straight width = box width + 50; curve = box + 100",
        "applies_to": ["Straight", "Curved", "Merge"],
    },
    "TAPER-5DEG": {
        "statement": "Curve adjacent-roller angle <= 5 deg (Damon/Interroll)",
        "applies_to": ["Curved"],
    },
    "TAPER-SPEED": {
        "statement": "d_outer = d_inner * Ro / Ri (surface-speed match)",
        "applies_to": ["Curved"],
    },
    "D-LOAD": {
        "statement": "<=60kg D50, <=120kg D60, else D80 (shaft/bearing check governs)",
        "applies_to": ["Straight", "Transfer", "Incline"],
    },
    "S-LOAD": {
        "statement": "<=60kg S1000, <=120kg S700, else S500 leg spacing",
        "applies_to": ["Straight", "Transfer", "Incline"],
    },
    "JOINT-SLACK": {
        "statement": "Joint pitch step within 2x10mm slack band",
        "applies_to": ["Straight", "Curved", "Merge", "Transfer", "Incline"],
    },
}

DUTY_CLASSES: Dict[str, Dict[str, Any]] = {
    "Light": {"max_kg": 150.0, "dia": 40.0, "pitch": 100.0, "leg": 800.0},
    "Medium": {"max_kg": 450.0, "dia": 60.0, "pitch": 110.0, "leg": 700.0},
    "Heavy": {"max_kg": 1000.0, "dia": 80.0, "pitch": 100.0, "leg": 600.0},
    "Pallet": {"max_kg": 2000.0, "dia": 80.0, "pitch": 85.0, "leg": 500.0},
}

#: Feature vector a future LOCAL model trains on (fixed order, documented).
FEATURES = ["box_mass_kg", "box_len_mm", "box_wid_mm", "line_length_mm",
            "duty_index", "pitch_mm", "dia_mm", "leg_spacing_mm"]


def get_rule(rule_id: str) -> Dict[str, Any]:
    if rule_id not in RULES:
        raise KeyError(f"Unknown rule {rule_id!r}")
    return dict(RULES[rule_id])


def pitch_for_box(box_length_mm: float) -> float:
    """Max pitch satisfying P-3ROLLERS, clamped to spec [80, 150]."""
    return max(80.0, min(150.0, float(box_length_mm) / 3.0))


def width_for_box(box_width_mm: float, curved: bool = False) -> float:
    """W-MARGIN recommendation, clamped to spec [300, 600]."""
    want = float(box_width_mm) + (100.0 if curved else 50.0)
    return max(300.0, min(600.0, want))


def duty_for_load(box_mass_kg: float) -> str:
    for name in ("Light", "Medium", "Heavy", "Pallet"):
        if box_mass_kg <= DUTY_CLASSES[name]["max_kg"]:
            return name
    return "Pallet"


def score_spec(spec: Dict[str, Any], box_mass_kg: float) -> Dict[str, Any]:
    """Deterministic baseline score a local model must beat (v1 heuristic).

    Returns ``{score_0_1, breakdown}``. Higher = better margin within spec.
    """
    duty = duty_for_load(box_mass_kg)
    ref = DUTY_CLASSES[duty]
    parts = {
        "pitch_ok": 1.0 if spec.get("roller_spacing_mm", 0) <= ref["pitch"] + 20 else 0.0,
        "dia_ok": 1.0 if spec.get("roller_diameter_mm", 0) >= ref["dia"] - 10 else 0.0,
        "leg_ok": 1.0 if spec.get("support_spacing_mm", 1e9) <= ref["leg"] + 100 else 0.0,
    }
    score = round(sum(parts.values()) / len(parts), 3)
    return {"score_0_1": score, "breakdown": parts, "duty": duty,
            "model": "heuristic-v1-baseline"}


def rule_ids() -> List[str]:
    return sorted(RULES)
