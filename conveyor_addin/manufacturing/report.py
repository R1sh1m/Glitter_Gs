"""Manufacturing report — one JSON + Markdown bundle for the shop floor."""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List

try:
    from manufacturing import bom as _bom
except ImportError:
    from conveyor_addin.manufacturing import bom as _bom  # type: ignore[no-redef]

try:
    from manufacturing import cutlist as _cuts
except ImportError:
    from conveyor_addin.manufacturing import cutlist as _cuts  # type: ignore[no-redef]

try:
    from manufacturing import instructions as _instr
except ImportError:
    from conveyor_addin.manufacturing import instructions as _instr  # type: ignore[no-redef]

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

__all__ = ["build_report", "render_markdown", "write_outputs"]


def build_report(line_name: str, modules: List[ConveyorModule],
                 validation: Dict[str, Any] | None = None) -> Dict[str, Any]:
    per_module = []
    for module in modules:
        per_module.append({
            "module_id": module.module_id,
            "module_type": module.module_type,
            "envelope_mm": {"L": module.length, "W": module.width,
                            "H": module.height},
            "bom": _bom.fabrication_bom(module),
            "cut_list": _cuts.cut_list(module),
            "instructions": _instr.assembly_instructions(module),
        })
    return {
        "line_name": line_name,
        "module_count": len(modules),
        "modules": per_module,
        "line_bom": _bom.line_bom(modules),
        "line_cut_list": _cuts.line_cut_list(modules),
        "line_instructions": _instr.line_instructions(modules),
        "validation": validation or {"valid": None, "note": "not supplied"},
    }


def render_markdown(report: Dict[str, Any]) -> str:
    out = [f"# Manufacturing Report — {report['line_name']}", "",
           f"Modules: {report['module_count']}", ""]
    out.append("## Modules")
    for module in report["modules"]:
        env = module["envelope_mm"]
        out.append(f"- **{module['module_id']}** ({module['module_type']}) — "
                   f"{env['L']:.0f} x {env['W']:.0f} x {env['H']:.0f} mm")
    out.append("")
    out.append("## Line BOM")
    out.append("| Part | Material | Spec | Unit | Qty |")
    out.append("|---|---|---|---|---|")
    for row in report["line_bom"]:
        out.append(f"| {row['part']} | {row['material']} | {row['spec']} "
                   f"| {row['unit']} | {row['quantity']} |")
    out.append("")
    out.append("## Cut List")
    out.append("| Part | Material | Length (mm) | Qty |")
    out.append("|---|---|---|---|")
    for cut in report["line_cut_list"]:
        out.append(f"| {cut['part']} | {cut['material']} "
                   f"| {cut['length_mm']} | {cut['quantity']} |")
    out.append("")
    out.append("## Assembly Sequence")
    for item in report["line_instructions"]:
        mod = item.get("module_id", "")
        prefix = f"[{mod}] " if mod not in ("*line*", "") else ""
        out.append(f"{prefix}**{item['title']}** — {item['detail']}")
    out.append("")
    out.append(f"## Layout Validation: "
               f"{'PASS' if report['validation'].get('valid') else 'SEE REPORT JSON'}")
    return "\n".join(out) + "\n"


def write_outputs(report: Dict[str, Any], output_dir: str,
                  tag: str) -> Dict[str, str]:
    """Write ``{tag}_report.{json,md}`` + ``{tag}_bom.csv`` + cut CSV."""
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    json_path = os.path.join(output_dir, f"{tag}_report.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
    paths["json"] = os.path.abspath(json_path)
    md_path = os.path.join(output_dir, f"{tag}_report.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(report))
    paths["markdown"] = os.path.abspath(md_path)
    bom_path = os.path.join(output_dir, f"{tag}_bom.csv")
    with open(bom_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["part", "material", "spec", "unit", "quantity"])
        writer.writeheader()
        writer.writerows(report["line_bom"])
    paths["bom_csv"] = os.path.abspath(bom_path)
    cut_path = os.path.join(output_dir, f"{tag}_cutlist.csv")
    with open(cut_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["part", "material", "length_mm", "quantity"])
        writer.writeheader()
        writer.writerows(report["line_cut_list"])
    paths["cutlist_csv"] = os.path.abspath(cut_path)
    return paths
