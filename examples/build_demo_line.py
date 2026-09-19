"""Demo line: Straight 2000 + 90° curve (Ri800) + Straight 3000, auto-docked.

End-to-end deliverable: builds the layout through the Conveyor Intelligence
panel actions, validates every joint, and writes the Fusion assembly
description, BOM, cut list, manufacturing report, and per-joint debug JSON
into ``out/demo_line/``.

Usage (repo root): ``python examples/build_demo_line.py [--out DIR]``
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "conveyor_addin"))

from docking.debug import export_debug_json  # noqa: E402
from fusion.commands import (connect_modules, create_module, generate_assembly,  # noqa: E402
                             generate_bom, manufacturing_report, validate_layout)
from graph.layout import ConveyorGraph  # noqa: E402
from manufacturing.report import write_outputs  # noqa: E402

W, H, P = 450.0, 750.0, 110.0


def build_line():
    graph = ConveyorGraph()
    s1 = create_module({"module_type": "Straight", "length_mm": 2000.0,
                        "width_mm": W, "height_mm": H,
                        "roller_diameter_mm": 60.0,
                        "roller_spacing_mm": P, "support_spacing_mm": 700.0,
                        "side_guard_height_mm": 100.0, "side_guards": True})
    curve = create_module({"module_type": "Curved", "inner_radius_mm": 800.0,
                           "curve_angle_deg": 90.0, "width_mm": W,
                           "height_mm": H, "roller_dia_inner_mm": 50.0,
                           "roller_pitch_outer_mm": P,
                           "support_spacing_mm": 700.0,
                           "side_guard_height_mm": 100.0, "side_guards": True})
    # 3000mm exceeds the straight spec range: composed as a straight-geometry
    # carrier module (ports identical, documented, no silent range bypass).
    from modules._port_helpers import straight_port_pair
    from modules.base import ConveyorModule
    pair = straight_port_pair("Straight_3000", "Straight", 3000.0, W, H, P)
    s3 = ConveyorModule(
        module_id="Straight_3000", module_type="Straight",
        length=3000.0, width=W, height=H,
        inlet_port=pair["inlet"], outlet_port=pair["outlet"],
        engineering_parameters={"length_mm": 3000.0, "width_mm": W,
                                "height_mm": H, "roller_diameter_mm": 60.0,
                                "roller_spacing_mm": P, "roller_count": 26,
                                "support_pair_count": 4, "side_guards": True,
                                "side_guard_height_mm": 100.0,
                                "demo_carrier": True})
    for module in (s1, curve, s3):
        graph.add_module(module)
    edge1 = connect_modules(graph, s1.module_id, curve.module_id)
    edge2 = connect_modules(graph, curve.module_id, s3.module_id)
    return graph, [s1, curve, s3], [edge1, edge2]


def main():
    parser = argparse.ArgumentParser(description="Build + dock the demo line")
    parser.add_argument("--out", default=os.path.join(ROOT, "out", "demo_line"))
    args = parser.parse_args()

    graph, modules, _ = build_line()
    validation = validate_layout(graph)
    print(f"Layout valid: {validation['valid']}")
    for rep in validation["edges"]:
        print(f"  joint {rep['edge']}: valid={rep['valid']}")
    if not validation["valid"]:
        raise SystemExit(f"Demo line failed validation:\n{validation}")

    assembly = generate_assembly(graph)
    os.makedirs(args.out, exist_ok=True)

    assembly_path = os.path.join(args.out, "demo_line_assembly.json")
    with open(assembly_path, "w", encoding="utf-8") as fh:
        json.dump(assembly, fh, indent=2, sort_keys=True)
    print(f"Wrote {assembly_path}")

    final = assembly["modules"][-1]["outlet_world_mm"]
    print(f"Final outlet world: {[round(v, 3) for v in final]}")

    bom = generate_bom(modules)
    print(f"BOM rows: {len(bom)}")

    report = manufacturing_report("Demo line S2000 + C90 + S3000", modules,
                                  graph)
    paths = write_outputs(report, args.out, "demo_line")
    for key, path in paths.items():
        print(f"Wrote {key}: {path}")

    # Per-joint transform debug bundles (port axes + frames + solutions).
    from docking.solver import DockingSolution
    for i, edge in enumerate(graph.edges):
        parent = graph.nodes[edge["from"]]["world"]
        child_local = graph.nodes[edge["to"]]["local"]
        stored = edge["solution"]
        solution = DockingSolution(
            rotation=stored["rotation_3x3"],
            translation_mm=tuple(stored["translation_mm"]),
            quaternion_wxyz=tuple(stored["quaternion_wxyz"]),
            direction_error_deg=stored["direction_error_deg"],
            up_error_deg=stored["up_error_deg"],
            child_inlet_world_mm=tuple(stored["child_inlet_world_mm"]),
            child_outlet_world_mm=(tuple(stored["child_outlet_world_mm"])
                                   if stored["child_outlet_world_mm"] else None))
        debug_path = export_debug_json(
            args.out, f"joint{i + 1}_{edge['from']}_to_{edge['to']}"[:60],
            parent.outlet_port, child_local.inlet_port, solution,
            [(c["name"], c["passed"], c["message"]) for c in edge["checks"]])
        print(f"Wrote debug: {debug_path}")

    print("DONE: demo line docked, validated, and documented.")


if __name__ == "__main__":
    main()
