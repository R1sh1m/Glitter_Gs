"""ConveyorGraph — the entire factory conveyor layout (OBJECTIVE 3).

Nodes: intelligent ``ConveyorModule`` objects (stored local + world-placed).
Edges: solved docking joints (``DockingSolution`` + validation checks).

Placement is incremental: the first added module roots the layout at
identity; each ``connect_modules`` solves the child into world via the 6-DOF
solver, runs the engineering gates, and collision-checks the child AABB
against every placed module. ``remove_module`` drops the node + incident
edges and marks the layout dirty (downstream placements are stale).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core import frames as _frames
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core import frames as _frames  # type: ignore[no-redef]

try:
    from core.errors import DockingError
except ImportError:
    from conveyor_addin.core.errors import DockingError  # type: ignore[no-redef]

try:
    from core.invariants import DEFAULT_TOLERANCES, Tolerances
except ImportError:
    from conveyor_addin.core.invariants import DEFAULT_TOLERANCES, Tolerances  # type: ignore[no-redef]

try:
    from docking import validators as _V
except ImportError:
    from conveyor_addin.docking import validators as _V  # type: ignore[no-redef]

try:
    from docking.solver import DockingSolver
except ImportError:
    from conveyor_addin.docking.solver import DockingSolver  # type: ignore[no-redef]

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

__all__ = ["ConveyorGraph"]


def _module_aabb_local(module: ConveyorModule) -> Tuple[_frames.Vec3, _frames.Vec3]:
    """Local envelope: explicit ``local_aabb_mm`` override (curves: arc box),
    else the [0,L] x [0,W] x [0,H] carrier box."""
    override = module.engineering_parameters.get("local_aabb_mm")
    if isinstance(override, dict):
        return (tuple(override["min"]), tuple(override["max"]))
    return (0.0, 0.0, 0.0), (module.length, module.width, module.height)


def _aabb_in_world(module: ConveyorModule) -> Tuple[_frames.Vec3, _frames.Vec3]:
    frame = module.coordinate_frame
    origin = tuple(frame["origin_mm"])
    rot = frame["rotation_3x3"]
    (lo, hi) = _module_aabb_local(module)
    corners = [
        (x, y, z)
        for x in (lo[0], hi[0])
        for y in (lo[1], hi[1])
        for z in (lo[2], hi[2])
    ]
    moved = [_frames.apply_transform(rot, origin, c) for c in corners]
    return (
        (min(c[0] for c in moved), min(c[1] for c in moved), min(c[2] for c in moved)),
        (max(c[0] for c in moved), max(c[1] for c in moved), max(c[2] for c in moved)),
    )


def _inner_radius(module: ConveyorModule) -> float | None:
    return module.engineering_parameters.get("inner_radius_mm")


class ConveyorGraph:
    """Directed layout graph with solved world placements."""

    def __init__(self, tolerances: Tolerances = DEFAULT_TOLERANCES) -> None:
        self.tolerances = tolerances
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self.root_id: str | None = None
        self.dirty = False

    # -- structure ----------------------------------------------------------
    def add_module(self, module: ConveyorModule) -> str:
        if module.module_id in self.nodes:
            raise ValueError(f"Duplicate module_id {module.module_id!r}")
        is_root = self.root_id is None
        # Only the root is placed at add time; other modules are ghosts at
        # identity until connect_modules solves them into world. Ghosts are
        # excluded from collision gates (they have no position yet).
        self.nodes[module.module_id] = {
            "local": module, "world": module, "placed": is_root}
        if is_root:
            self.root_id = module.module_id
        return module.module_id

    def remove_module(self, module_id: str) -> None:
        if module_id not in self.nodes:
            raise KeyError(f"Unknown module {module_id!r}")
        del self.nodes[module_id]
        self.edges = [e for e in self.edges
                      if e["from"] != module_id and e["to"] != module_id]
        if self.root_id == module_id:
            self.root_id = next(iter(self.nodes), None)
        self.dirty = True  # downstream placements may be stale

    def connect_modules(self, outlet_id: str, inlet_id: str) -> Dict[str, Any]:
        """Dock ``inlet_id`` onto ``outlet_id``; returns the edge record."""
        if outlet_id not in self.nodes:
            raise KeyError(f"Unknown module {outlet_id!r}")
        if inlet_id not in self.nodes:
            raise KeyError(f"Unknown module {inlet_id!r}")
        if outlet_id == inlet_id:
            raise ValueError("Cannot dock a module to itself")
        parent = self.nodes[outlet_id]["world"]
        child = self.nodes[inlet_id]["local"]
        if parent.outlet_port is None or child.inlet_port is None:
            raise DockingError(
                reason="invalid_port",
                message="Both modules must expose outlet/inlet ports",
                module_a={"module_id": outlet_id},
                module_b={"module_id": inlet_id},
            )
        solution = DockingSolver.solve(
            parent.outlet_port, child.inlet_port,
            child_outlet=child.outlet_port, tolerances=self.tolerances,
        )
        checks = _V.validate_joint(
            parent.outlet_port, child.inlet_port,
            tolerances=self.tolerances,
            parent_inner_radius_mm=_inner_radius(parent),
            child_inner_radius_mm=_inner_radius(child),
            module_a_id=outlet_id, module_b_id=inlet_id,
        )
        placed = child.with_world_transform(
            solution.rotation, solution.translation_mm)
        new_min, new_max = _aabb_in_world(placed)
        for other_id, node in self.nodes.items():
            if other_id == inlet_id or not node.get("placed", True):
                continue  # self ghost / unplaced ghosts have no position
            # The docked parent included: butt contact at the joint plane
            # passes (zero-volume touch); real overlap raises.
            other = node["world"]
            o_min, o_max = _aabb_in_world(other)
            _V.check_collision_aabb(o_min, o_max, new_min, new_max)
        self.nodes[inlet_id]["world"] = placed
        self.nodes[inlet_id]["placed"] = True
        edge = {
            "from": outlet_id,
            "to": inlet_id,
            "solution": solution.to_dict(),
            "checks": [{"name": n, "passed": b, "message": m}
                       for n, b, m in checks],
        }
        self.edges.append(edge)
        self.dirty = False
        return edge

    # -- verification -------------------------------------------------------
    def validate_layout(self) -> Dict[str, Any]:
        """Re-run every joint gate + pairwise collision; return a report."""
        edge_reports = []
        for edge in self.edges:
            parent = self.nodes[edge["from"]]["world"]
            child = self.nodes[edge["to"]]["world"]
            try:
                checks = _V.validate_joint(
                    parent.outlet_port, child.inlet_port,
                    tolerances=self.tolerances,
                    parent_inner_radius_mm=_inner_radius(parent),
                    child_inner_radius_mm=_inner_radius(child),
                    module_a_id=edge["from"], module_b_id=edge["to"],
                )
                edge_reports.append({"edge": [edge["from"], edge["to"]],
                                     "valid": True, "checks": checks})
            except DockingError as exc:
                edge_reports.append({"edge": [edge["from"], edge["to"]],
                                     "valid": False, "error": exc.to_dict()})
        collisions = []
        ids = [i for i, n in self.nodes.items() if n.get("placed", True)]
        boxes = {i: _aabb_in_world(self.nodes[i]["world"]) for i in ids}
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                adjacent = any(
                    (e["from"] == ids[a] and e["to"] == ids[b])
                    or (e["from"] == ids[b] and e["to"] == ids[a])
                    for e in self.edges
                )
                try:
                    _V.check_collision_aabb(boxes[ids[a]][0], boxes[ids[a]][1],
                                            boxes[ids[b]][0], boxes[ids[b]][1])
                except DockingError as exc:
                    if not adjacent:
                        collisions.append(
                            {"pair": [ids[a], ids[b]],
                             "error": exc.to_dict()})
        valid = (all(e["valid"] for e in edge_reports)
                 and not collisions and not self.dirty)
        return {"valid": valid, "dirty": self.dirty,
                "edges": edge_reports, "collisions": collisions}

    # -- output -------------------------------------------------------------
    def generate_assembly(self) -> Dict[str, Any]:
        """Ordered assembly description: placed modules + joints + BOM roll-up."""
        validation = self.validate_layout()
        modules = []
        for module_id, node in self.nodes.items():
            world = node["world"]
            frame = world.coordinate_frame
            rot, org = frame["rotation_3x3"], tuple(frame["origin_mm"])
            matrix = [
                [rot[0][0], rot[0][1], rot[0][2], org[0]],
                [rot[1][0], rot[1][1], rot[1][2], org[1]],
                [rot[2][0], rot[2][1], rot[2][2], org[2]],
                [0.0, 0.0, 0.0, 1.0],
            ]
            aabb_min, aabb_max = _aabb_in_world(world)
            modules.append({
                "module_id": module_id,
                "module_type": world.module_type,
                "world_matrix_4x4": matrix,
                "world_aabb_mm": {"min": list(aabb_min), "max": list(aabb_max)},
                "inlet_world_mm": (list(world.inlet_port.origin)
                                   if world.inlet_port else None),
                "outlet_world_mm": (list(world.outlet_port.origin)
                                    if world.outlet_port else None),
            })
        rollup: Dict[str, float] = {}
        for node in self.nodes.values():
            for part, qty in node["local"].bom_data.items():
                if isinstance(qty, (int, float)):
                    rollup[part] = rollup.get(part, 0) + qty
        return {"module_count": len(modules), "modules": modules,
                "joints": self.edges, "bom_rollup": rollup,
                "validation": validation}
