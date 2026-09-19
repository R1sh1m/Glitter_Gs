"""Fabrication BOM — bought-out + fabricated parts per module and per line.

Quantities derive from the module's engineering parameters (model-read
counts via the adapter layer), so BOM can never drift from the validated
spec. Rows: ``{part, material, spec, unit, quantity, length_mm?}``.
"""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

__all__ = ["fabrication_bom", "line_bom", "rollup_rows"]


def _get(eng: Dict[str, Any], *keys: str, default: Any = 0) -> Any:
    for key in keys:
        if key in eng:
            return eng[key]
    return default


def fabrication_bom(module: ConveyorModule) -> List[Dict[str, Any]]:
    """Fabrication-grade BOM rows for one module."""
    eng = module.engineering_parameters
    kind = module.module_type
    length = _get(eng, "length_mm", default=module.length)
    rollers = int(_get(eng, "roller_count", default=0))
    supports = int(_get(eng, "support_pair_count",
                        _get(eng, "support_count", default=0)))
    guards = bool(_get(eng, "side_guards", default=False))
    guard_h = float(_get(eng, "side_guard_height_mm", default=0.0))
    dia = float(_get(eng, "roller_diameter_mm",
                     _get(eng, "roller_dia_inner_mm", default=50.0)))
    rows: List[Dict[str, Any]] = []
    if kind == "Curved":
        arc_in = float(_get(eng, "arc_inner_mm", default=0.0))
        arc_out = float(_get(eng, "arc_outer_mm", default=0.0))
        rows.append({"part": "Arc side rail, inner", "material": "Steel",
                     "spec": "20x40 profile", "unit": "m",
                     "quantity": round(arc_in / 1000.0, 3)})
        rows.append({"part": "Arc side rail, outer", "material": "Steel",
                     "spec": "20x40 profile", "unit": "m",
                     "quantity": round(arc_out / 1000.0, 3)})
        rows.append({"part": f"Tapered roller dia {dia:.0f} (inner)",
                     "material": "Steel", "spec": "tapered tube",
                     "unit": "pcs", "quantity": rollers})
    else:
        rows.append({"part": "Side rail 20x40", "material": "Steel",
                     "spec": "20x40 profile", "unit": "m",
                     "quantity": round(2.0 * length / 1000.0, 3)})
        rows.append({"part": f"Roller dia {dia:.0f}",
                     "material": "Steel", "spec": "tube + dia14 shaft",
                     "unit": "pcs", "quantity": rollers})
    rows.append({"part": "Roller shaft dia14", "material": "Steel",
                 "spec": "stepped, M8x15 ends", "unit": "pcs",
                 "quantity": rollers})
    rows.append({"part": "Bearing 6002-2RZ", "material": "Bought-out",
                 "spec": "15x32x9", "unit": "pcs", "quantity": 2 * rollers})
    rows.append({"part": "Leg post 40x40", "material": "Aluminium 6063-T5",
                 "spec": "T-slot extrusion", "unit": "pcs",
                 "quantity": 2 * supports})
    rows.append({"part": "Foot plate 100x100x8 + anchors",
                 "material": "Steel kit", "spec": "plate + 4x anchor",
                 "unit": "pcs", "quantity": 2 * supports})
    rows.append({"part": "Docking board 40x80x10 + locating pins",
                 "material": "Aluminium", "spec": "40mm grid + 2 pins",
                 "unit": "pcs", "quantity": 4})
    if guards and guard_h > 0:
        rows.append({"part": "Side guard plate", "material": "Steel",
                     "spec": f"{guard_h:.0f}mm high, 5mm plate",
                     "unit": "pcs", "quantity": 2})
    return [r for r in rows if r["quantity"] > 0]


def rollup_rows(all_rows: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Sum BOM rows across modules (same part+material+spec+unit merge)."""
    merged: Dict[tuple, Dict[str, Any]] = {}
    for rows in all_rows:
        for row in rows:
            key = (row["part"], row["material"], row["spec"], row["unit"])
            if key not in merged:
                merged[key] = dict(row)
                if "length_mm" in merged[key]:
                    del merged[key]["length_mm"]
            else:
                merged[key]["quantity"] += row["quantity"]
                if isinstance(merged[key]["quantity"], float):
                    merged[key]["quantity"] = round(merged[key]["quantity"], 3)
    return sorted(merged.values(), key=lambda r: (r["part"], r["spec"]))


def line_bom(modules: List[ConveyorModule]) -> List[Dict[str, Any]]:
    """Rolled-up fabrication BOM for a full line."""
    return rollup_rows([fabrication_bom(m) for m in modules])
