"""Cut list — every saw cut required to fabricate a module or line.

Rows: ``{part, material, length_mm, quantity}``. Lengths follow the same
single-source formulas as the generators (margin = D/2 + 10, rail = full
length, leg = H − 40 rail height, roller tube = W − 2·(20 + 10)).
"""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from core.params import (  # noqa: F401  (single-source constants)
        GUARD_THICK, LEG_SIDE, RAIL_H, RAIL_W, ROLLER_CLEARANCE,
    )
except ImportError:
    from conveyor_addin.core.params import (  # type: ignore[no-redef]  # noqa: F401
        GUARD_THICK, LEG_SIDE, RAIL_H, RAIL_W, ROLLER_CLEARANCE,
    )

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

__all__ = ["cut_list", "line_cut_list", "rollup_cuts"]


def cut_list(module: ConveyorModule) -> List[Dict[str, Any]]:
    eng = module.engineering_parameters
    kind = module.module_type
    length = eng.get("length_mm", module.length)
    width = eng.get("width_mm", module.width)
    height_in = eng.get("height_in_mm", eng.get("height_mm", module.height))
    rollers = int(eng.get("roller_count", 0))
    supports = int(eng.get("support_pair_count", eng.get("support_count", 0)))
    guards = bool(eng.get("side_guards", False))
    guard_h = float(eng.get("side_guard_height_mm", 0.0))
    dia = float(eng.get("roller_diameter_mm",
                        eng.get("roller_dia_inner_mm", 50.0)))
    cuts: List[Dict[str, Any]] = []
    if kind == "Curved":
        arc_in = float(eng.get("arc_inner_mm", 0.0))
        arc_out = float(eng.get("arc_outer_mm", 0.0))
        cuts.append({"part": "Side rail, inner arc", "material": "Steel 20x40",
                     "length_mm": round(arc_in, 1), "quantity": 1})
        cuts.append({"part": "Side rail, outer arc", "material": "Steel 20x40",
                     "length_mm": round(arc_out, 1), "quantity": 1})
    else:
        cuts.append({"part": "Side rail", "material": "Steel 20x40",
                     "length_mm": round(length, 1), "quantity": 2})
    leg_len = max(height_in - 40.0, 50.0)
    cuts.append({"part": "Leg post 40x40", "material": "Aluminium 6063-T5",
                 "length_mm": round(leg_len, 1), "quantity": 2 * supports})
    roller_len = width - 2.0 * (20.0 + 10.0)
    cuts.append({"part": f"Roller tube dia{dia:.0f}", "material": "Steel tube",
                 "length_mm": round(roller_len, 1), "quantity": rollers})
    cuts.append({"part": "Roller shaft dia14", "material": "Steel bar",
                 "length_mm": round(width + 24.0, 1), "quantity": rollers})
    if guards and guard_h > 0:
        cuts.append({"part": "Side guard plate", "material": "Steel 5mm",
                     "length_mm": round(length, 1), "quantity": 2})
    return [c for c in cuts if c["quantity"] > 0 and c["length_mm"] > 0]


def rollup_cuts(all_cuts: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    merged: Dict[tuple, Dict[str, Any]] = {}
    for cuts in all_cuts:
        for cut in cuts:
            key = (cut["part"], cut["material"], cut["length_mm"])
            if key not in merged:
                merged[key] = dict(cut)
            else:
                merged[key]["quantity"] += cut["quantity"]
    return sorted(merged.values(),
                  key=lambda c: (c["part"], c["length_mm"]))


def line_cut_list(modules: List[ConveyorModule]) -> List[Dict[str, Any]]:
    return rollup_cuts([cut_list(m) for m in modules])
