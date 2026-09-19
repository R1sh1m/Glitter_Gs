"""Conveyor Intelligence panel — six commands, pure actions (OBJECTIVE 6).

Panel buttons and the pure function behind each one:

    [Create Module]       -> create_module(spec)
    [Connect Modules]     -> connect_modules(graph, outlet_id, inlet_id)
    [Validate Layout]     -> validate_layout(graph)
    [Generate Assembly]   -> generate_assembly(graph)
    [Generate BOM]        -> generate_bom(modules)
    [Manufacturing Report]-> manufacturing_report(line_name, modules, graph)

``register_panel`` is the ONE wiring point for the live Add-In toolbar:
call it from ``conveyor_addin.py`` `run()` (it no-ops to ``False`` outside
Fusion so offline/tests stay safe).
"""

from __future__ import annotations

from typing import Any, Dict, List

try:
    import adsk.core  # type: ignore
    import adsk.fusion  # type: ignore
    _HAS_ADSK = True
except ImportError:
    adsk = None  # type: ignore
    _HAS_ADSK = False

try:  # pytest / Add-In dir on sys.path (repo convention)
    from graph.layout import ConveyorGraph
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.graph.layout import ConveyorGraph  # type: ignore[no-redef]

try:
    from manufacturing import bom as _bom
except ImportError:
    from conveyor_addin.manufacturing import bom as _bom  # type: ignore[no-redef]

try:
    from manufacturing import report as _report
except ImportError:
    from conveyor_addin.manufacturing import report as _report  # type: ignore[no-redef]

try:
    from modules import incline as _incline
except ImportError:
    from conveyor_addin.modules import incline as _incline  # type: ignore[no-redef]

try:
    from modules import merge as _merge
except ImportError:
    from conveyor_addin.modules import merge as _merge  # type: ignore[no-redef]

try:
    from modules import transfer as _transfer
except ImportError:
    from conveyor_addin.modules import transfer as _transfer  # type: ignore[no-redef]

try:
    from modules.base import ConveyorModule
except ImportError:
    from conveyor_addin.modules.base import ConveyorModule  # type: ignore[no-redef]

try:
    from modules.curve import create_curve_module
except ImportError:
    from conveyor_addin.modules.curve import create_curve_module  # type: ignore[no-redef]

try:
    from modules.straight import create_straight_module
except ImportError:
    from conveyor_addin.modules.straight import create_straight_module  # type: ignore[no-redef]

__all__ = [
    "COMMANDS",
    "create_module",
    "connect_modules",
    "validate_layout",
    "generate_assembly",
    "generate_bom",
    "manufacturing_report",
    "register_panel",
]

_CREATORS = {
    "Straight": lambda s: create_straight_module(
        s["length_mm"], s["width_mm"], s["height_mm"],
        s.get("roller_diameter_mm", 60.0),
        s.get("roller_spacing_mm", 110.0),
        s.get("support_spacing_mm", 700.0),
        s.get("side_guard_height_mm", 0.0),
        bool(s.get("side_guards", False))),
    "Curved": lambda s: create_curve_module(
        s["inner_radius_mm"], s["curve_angle_deg"],
        s["width_mm"], s["height_mm"],
        s.get("roller_dia_inner_mm", 50.0),
        s.get("roller_pitch_outer_mm", 110.0),
        s.get("support_spacing_mm", 700.0),
        s.get("side_guard_height_mm", 0.0),
        bool(s.get("side_guards", False))),
    "Merge": lambda s: _merge.create_merge_module(
        s["length_mm"], s["width_mm"], s["height_mm"],
        s.get("roller_pitch_mm", 110.0),
        s.get("branch_angle_deg", 30.0)),
    "Transfer": lambda s: _transfer.create_transfer_module(
        s["length_mm"], s["width_mm"], s["height_mm"],
        s.get("roller_pitch_mm", 110.0)),
    "Incline": lambda s: _incline.create_incline_module(
        s["length_mm"], s["width_mm"], s["height_in_mm"],
        s["rise_mm"], s.get("roller_pitch_mm", 110.0)),
}


def create_module(spec: Dict[str, Any]) -> ConveyorModule:
    """[Create Module] — validated intelligent module from a spec dict."""
    kind = spec.get("module_type", "Straight")
    if kind == "Custom":
        raise ValueError("Custom modules require explicit ports; "
                         "use modules.custom.create_custom_module")
    if kind not in _CREATORS:
        raise ValueError(f"Unknown module_type {kind!r}")
    return _CREATORS[kind](spec)


def connect_modules(graph: ConveyorGraph, outlet_id: str,
                    inlet_id: str) -> Dict[str, Any]:
    """[Connect Modules] — solve + gate + place; returns the edge record."""
    return graph.connect_modules(outlet_id, inlet_id)


def validate_layout(graph: ConveyorGraph) -> Dict[str, Any]:
    """[Validate Layout] — joint gates + collision report."""
    return graph.validate_layout()


def generate_assembly(graph: ConveyorGraph) -> Dict[str, Any]:
    """[Generate Assembly] — placed modules + joints + BOM roll-up."""
    return graph.generate_assembly()


def generate_bom(modules: List[ConveyorModule]) -> List[Dict[str, Any]]:
    """[Generate BOM] — rolled-up fabrication BOM rows."""
    return _bom.line_bom(modules)


def manufacturing_report(line_name: str, modules: List[ConveyorModule],
                         graph: ConveyorGraph | None = None) -> Dict[str, Any]:
    """[Manufacturing Report] — full shop-floor bundle (JSON-serializable)."""
    validation = graph.validate_layout() if graph is not None else None
    return _report.build_report(line_name, modules, validation)


COMMANDS = [
    {"id": "GlitterGs_CreateModule", "title": "Create Module",
     "action": "create_module"},
    {"id": "GlitterGs_ConnectModules", "title": "Connect Modules",
     "action": "connect_modules"},
    {"id": "GlitterGs_ValidateLayout", "title": "Validate Layout",
     "action": "validate_layout"},
    {"id": "GlitterGs_GenerateAssembly", "title": "Generate Assembly",
     "action": "generate_assembly"},
    {"id": "GlitterGs_GenerateBOM", "title": "Generate BOM",
     "action": "generate_bom"},
    {"id": "GlitterGs_ManufacturingReport", "title": "Manufacturing Report",
     "action": "manufacturing_report"},
]


def register_panel(app=None) -> bool:
    """Wire the Conveyor Intelligence panel into the Add-In toolbar.

    Wiring point: call ``fusion.commands.register_panel(app)`` from
    ``conveyor_addin.py`` `run()` after the existing commands register.
    Returns False outside Fusion (offline-safe).
    """
    if not _HAS_ADSK or app is None:
        return False
    try:
        ui = app.userInterface
        panel = ui.allToolbarPanels.itemById("SolidCreatePanel")
        if panel is None:
            return False
        for cmd in COMMANDS:
            if panel.controls.itemById(cmd["id"]) is None:
                control = panel.controls.addCommand(
                    ui.commandDefinitions.itemById(cmd["id"]))
                control.isPromoted = False
        return True
    except Exception:
        return False
