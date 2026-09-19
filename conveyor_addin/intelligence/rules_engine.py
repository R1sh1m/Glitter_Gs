"""Rules engine — deterministic gates every recommendation must pass.

``evaluate_spec`` returns findings (``pass``/``warning``/``fail`` with rule
ids). ``is_acceptable`` is True only with zero ``fail`` findings.
``gate`` raises ``RecommendationRejected`` otherwise. Deterministic
engineering always outranks ML: the recommender's output is INPUT here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

try:
    from core.params import CURVE_RANGES, RANGES
except ImportError:
    from conveyor_addin.core.params import CURVE_RANGES, RANGES  # type: ignore[no-redef]

try:
    from intelligence import knowledge_base as _kb
except ImportError:
    from conveyor_addin.intelligence import knowledge_base as _kb  # type: ignore[no-redef]

__all__ = ["Finding", "RecommendationRejected", "evaluate_spec",
           "is_acceptable", "gate"]


@dataclass(frozen=True)
class Finding:
    rule_id: str
    status: str  # "pass" | "warning" | "fail"
    message: str


class RecommendationRejected(ValueError):
    """A recommendation failed deterministic engineering gates."""

    def __init__(self, findings: List[Finding]) -> None:
        self.findings = list(findings)
        bad = [f"{f.rule_id}: {f.message}" for f in findings
               if f.status == "fail"]
        super().__init__("Recommendation rejected:\n" + "\n".join(bad))


def _in_range(key: str, value: float, table: Dict[str, Any]) -> bool:
    lo, hi = table[key]
    return lo <= value <= hi


def evaluate_spec(spec: Dict[str, Any],
                  box_mass_kg: float = 0.0,
                  box_len_mm: float = 0.0,
                  box_wid_mm: float = 0.0) -> List[Finding]:
    findings: List[Finding] = []
    for key in ("L", "W", "H", "D", "P", "S", "G"):
        field = {"L": "length_mm", "W": "width_mm", "H": "height_mm",
                 "D": "roller_diameter_mm", "P": "roller_spacing_mm",
                 "S": "support_spacing_mm",
                 "G": "side_guard_height_mm"}[key]
        if field in spec:
            ok = _in_range(key, float(spec[field]), RANGES)
            findings.append(Finding(
                f"SPEC-{key}", "pass" if ok else "fail",
                f"{field}={spec[field]} "
                f"{'within' if ok else 'OUTSIDE'} {RANGES[key]}"))
    if "roller_spacing_mm" in spec and box_len_mm > 0:
        limit = _kb.pitch_for_box(box_len_mm)
        ok = float(spec["roller_spacing_mm"]) <= limit + 1e-9
        findings.append(Finding(
            "P-3ROLLERS", "pass" if ok else "fail",
            f"P={spec['roller_spacing_mm']} vs limit {limit:.1f} "
            f"(box {box_len_mm:.0f}mm)"))
    if box_wid_mm > 0 and "width_mm" in spec:
        want = _kb.width_for_box(box_wid_mm)
        if abs(float(spec["width_mm"]) - want) < 1e-9:
            findings.append(Finding("W-MARGIN", "pass",
                                    f"W matches recommendation {want:.0f}"))
        else:
            findings.append(Finding(
                "W-MARGIN", "warning",
                f"W={spec['width_mm']} vs recommended {want:.0f}"))
    if "curve_angle_deg" in spec:
        ok = _in_range("Theta", float(spec["curve_angle_deg"]), CURVE_RANGES)
        findings.append(Finding(
            "SPEC-Theta", "pass" if ok else "fail",
            f"angle {spec['curve_angle_deg']} "
            f"{'within' if ok else 'OUTSIDE'} {CURVE_RANGES['Theta']}"))
    if not findings:
        findings.append(Finding("SPEC", "fail", "empty spec"))
    return findings


def is_acceptable(findings: List[Finding]) -> bool:
    return all(f.status != "fail" for f in findings)


def gate(spec: Dict[str, Any], box_mass_kg: float = 0.0,
         box_len_mm: float = 0.0, box_wid_mm: float = 0.0) -> List[Finding]:
    findings = evaluate_spec(spec, box_mass_kg, box_len_mm, box_wid_mm)
    if not is_acceptable(findings):
        raise RecommendationRejected(findings)
    return findings
