"""Assembly instructions — ordered shop-floor steps per module and per line."""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

__all__ = ["assembly_instructions", "line_instructions"]


def assembly_instructions(module: ConveyorModule) -> List[Dict[str, Any]]:
    """Canonical 4 steps + type-specific extras (taper/grade/branch)."""
    eng = module.engineering_parameters
    rollers = eng.get("roller_count", "?")
    supports = eng.get("support_pair_count", eng.get("support_count", "?"))
    steps = [
        {"step": 1, "title": "Install side rails",
         "detail": "Square the 2 side rails on a flat table; "
                   "torque rail splice bolts to spec."},
        {"step": 2, "title": "Install roller bearings",
         "detail": f"Press 6002 bearings into all {rollers} roller tubes "
                   f"(2 per roller); verify free spin."},
        {"step": 3, "title": "Install rollers",
         "detail": f"Seat {rollers} rollers with dia14 shafts into rail "
                   f"bores at the specified pitch; check carry-plane flatness."},
        {"step": 4, "title": "Install supports",
         "detail": f"Fit {supports} leg stations with foot plates; "
                   f"level carry height to {module.height:.0f}mm; anchor."},
    ]
    n = 5
    if module.module_type == "Curved":
        steps.append({
            "step": n, "title": "Verify taper orientation",
            "detail": f"Small roller dia faces the inner radius "
                      f"(Ri {eng.get('inner_radius_mm', '?')}mm); "
                      f"confirm surface-speed match by hand spin."})
        n += 1
    if module.module_type == "Incline":
        steps.append({
            "step": n, "title": "Set grade and head height",
            "detail": f"Raise head to +{eng.get('rise_mm', '?')}mm "
                      f"(grade {eng.get('grade_deg', '?'):.1f}°); "
                      f"re-torque after first load cycle."})
        n += 1
    if module.module_type == "Merge":
        steps.append({
            "step": n, "title": "Align branch inlet",
            "detail": f"Set branch angle "
                      f"{eng.get('branch_angle_deg', '?')}°; gap branch "
                      f"rollers to main bed within pitch slack."})
        n += 1
    if bool(eng.get("side_guards", False)):
        steps.append({
            "step": n, "title": "Fit side guards",
            "detail": "Bolt guard plates; verify no pinch points per ISO 13857."})
    return steps


def line_instructions(modules: List[ConveyorModule]) -> List[Dict[str, Any]]:
    """Line build order: per-module steps prefixed, then joint torque pass."""
    ordered: List[Dict[str, Any]] = []
    for module in modules:
        for step in assembly_instructions(module):
            item = dict(step)
            item["module_id"] = module.module_id
            item["title"] = f"[{module.module_type}] {step['title']}"
            ordered.append(item)
    ordered.append({"step": 0, "module_id": "*line*",
                    "title": "Joint torque + IF-060 pin pass",
                    "detail": "After all modules are docked: insert 2 locating "
                              "pins per joint board, torque the 40mm-grid "
                              "connection boards, re-verify carry heights "
                              "±1mm across every joint."})
    return ordered
