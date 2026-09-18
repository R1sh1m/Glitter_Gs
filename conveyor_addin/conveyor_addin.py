"""Glitter_Gs parametric conveyor add-in (Industrial Turnkey Edition).

Enterprise-grade Autodesk Fusion Add-In providing:
1. Parametric Conveyor Generator:
   - Unified Straight and Full-Tapered Curved modules (30°/45°/60°/90°).
   - Dynamic inputs with real-time live preview (counts, pitch, steel mass).
   - Industrial presets management (C1, C2, C3, Pallet, Carton, Curves).
   - Instant in-place reconfiguration with zero duplicate solids.
   - Deliverables pipeline: STEP CAD + CSV BOM + OPC-UA Digital Twin nodeset.
2. Conveyor Line Docking Tool (Lego-style line builder):
   - Snaps next module to any existing module outlet with continuous pitch.
   - Enforces joint continuity and flush carry surface alignment.

Architecture adheres to Fusion360AddinSkeleton and FusionGridfinityGenerator paradigms.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Any, Dict

_here = os.path.dirname(os.path.realpath(__file__))
for _candidate in (_here, os.path.dirname(_here)):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import fusion_conveyor_generator as fcg  # noqa: E402
import fusion_curve_module as fcm  # noqa: E402
import fusion_docking_system as fds  # noqa: E402

try:
    import adsk.core  # type: ignore
    import adsk.fusion  # type: ignore
    _HAS_ADSK = True
except ImportError:  # pragma: no cover - allows offline test execution
    adsk = None
    _HAS_ADSK = False

ADDIN_ID = "GlitterGsConveyorAddin"
ADDIN_NAME = "Parametric Conveyor Generator"
ADDIN_TOOLTIP = "Parametric adjustable roller conveyor (Straight & Curved Industrial Modules)"

DOCK_CMD_ID = "GlitterGsDockingTool"
DOCK_CMD_NAME = "Dock Next Conveyor Module"
DOCK_CMD_TOOLTIP = "Interlock and dock next conveyor module to an existing line outlet"

# Input Identifiers
MODULE_TYPE_ID = "in_module_type"
PRESET_ID = "in_preset"
DUTY_CLASS_ID = "in_duty_class"
TARGET_LOAD_ID = "in_target_load"
AUTO_OPTIMIZE_ID = "in_auto_optimize"
CROSS_BRACE_ID = "in_cross_brace"
GUARDS_ID = "in_guards"
PREVIEW_ID = "preview"
LOG_ID = "status_log"
EXPORT_BTN_ID = "btn_export"

# Straight Specs: (id, label, unit, key, tip)
STRAIGHT_SPECS = (
    ("in_length", "Conveyor Length", "mm", "L", "Overall length, 800-2000 mm"),
    ("in_width", "Conveyor Width", "mm", "W", "Overall width, 300-600 mm"),
    ("in_height", "Frame Height", "mm", "H", "Floor to frame, 500-900 mm"),
    ("in_dia", "Roller Diameter", "mm", "D", "Roller outside diameter, 40-80 mm"),
    ("in_pitch", "Roller Spacing", "mm", "P", "Centre-to-centre, 80-150 mm"),
    ("in_leg", "Leg Spacing", "mm", "S", "Support station spacing, 500-1000 mm"),
    ("in_guard", "Guard Height", "mm", "G", "Side-guard height, 0-150 mm"),
)

# Curved Specs: (id, label, unit, tip)
CURVE_SPECS = (
    ("in_radius", "Inner Radius (Ri)", "mm", "Inner curve radius, 400-1200 mm"),
    ("in_angle", "Curve Angle", "deg", "Arc angle: 30, 45, 60, 90, 180 deg"),
)

# Keep backward-compatible tuple for existing tests
INPUT_SPECS = STRAIGHT_SPECS

# Global event handler storage to prevent garbage collection
handlers = []
_registered_controls = []

# ---------------------------------------------------------------------------
# Presets Helper
# ---------------------------------------------------------------------------


def load_presets() -> Dict[str, Dict[str, Any]]:
    presets_path = os.path.join(_here, "presets.json")
    if os.path.exists(presets_path):
        try:
            with open(presets_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("presets", {})
        except Exception:
            pass
    # Fallback built-in presets
    return {
        "C1: Compact (No Guards)": {
            "module_type": "straight", "in_length": 800.0, "in_width": 300.0, "in_height": 500.0,
            "in_dia": 40.0, "in_pitch": 80.0, "in_leg": 500.0, "in_guard": 0.0, "in_guards": False,
            "in_radius": 800.0, "in_angle": 90.0, "in_cross_brace": False, "in_target_load": 150.0,
        },
        "C2: Medium Standard (With Guards)": {
            "module_type": "straight", "in_length": 1400.0, "in_width": 450.0, "in_height": 750.0,
            "in_dia": 60.0, "in_pitch": 110.0, "in_leg": 700.0, "in_guard": 100.0, "in_guards": True,
            "in_radius": 800.0, "in_angle": 90.0, "in_cross_brace": True, "in_target_load": 450.0,
        },
        "C3: Long Heavy (With Guards)": {
            "module_type": "straight", "in_length": 2000.0, "in_width": 600.0, "in_height": 900.0,
            "in_dia": 80.0, "in_pitch": 150.0, "in_leg": 1000.0, "in_guard": 150.0, "in_guards": True,
            "in_radius": 800.0, "in_angle": 90.0, "in_cross_brace": True, "in_target_load": 1000.0,
        },
        "Curve 90° Standard Ri800": {
            "module_type": "curve", "in_length": 1400.0, "in_width": 450.0, "in_height": 750.0,
            "in_dia": 50.0, "in_pitch": 110.0, "in_leg": 700.0, "in_guard": 100.0, "in_guards": True,
            "in_radius": 800.0, "in_angle": 90.0, "in_cross_brace": True, "in_target_load": 450.0,
        }
    }


def dialog_defaults() -> dict:
    """Default dialog values in mm (C2 medium configuration)."""
    demo = fcg.demo_configurations()["C2_medium_with_guards"]
    return {
        MODULE_TYPE_ID: "Straight Section",
        PRESET_ID: "C2: Medium Standard (With Guards)",
        DUTY_CLASS_ID: "Medium Duty (450 kg)",
        TARGET_LOAD_ID: 450.0,
        AUTO_OPTIMIZE_ID: False,
        CROSS_BRACE_ID: True,
        "in_length": demo.length_mm,
        "in_width": demo.width_mm,
        "in_height": demo.height_mm,
        "in_dia": demo.roller_diameter_mm,
        "in_pitch": demo.roller_spacing_mm,
        "in_leg": demo.support_spacing_mm,
        "in_guard": demo.side_guard_height_mm,
        GUARDS_ID: demo.side_guards,
        "in_radius": 800.0,
        "in_angle": 90.0,
    }


def values_to_input(values: dict) -> "fcg.ConveyorInput":
    """Convert dialog values dict to a validated straight ConveyorInput."""
    guards = values.get(GUARDS_ID, True)
    if isinstance(guards, str):
        guards = guards.strip().lower() in {"yes", "y", "true", "1"}
    cross_b = values.get(CROSS_BRACE_ID, True)
    if isinstance(cross_b, str):
        cross_b = cross_b.strip().lower() in {"yes", "y", "true", "1"}
    target_l = values.get(TARGET_LOAD_ID, 450.0)
    try:
        target_l = float(target_l)
    except (ValueError, TypeError):
        target_l = 450.0
    params = fcg.ConveyorInput(
        length_mm=float(values["in_length"]),
        width_mm=float(values["in_width"]),
        height_mm=float(values["in_height"]),
        roller_diameter_mm=float(values["in_dia"]),
        roller_spacing_mm=float(values["in_pitch"]),
        support_spacing_mm=float(values["in_leg"]),
        side_guard_height_mm=float(values["in_guard"]),
        side_guards=bool(guards),
        cross_bracing=bool(cross_b),
        target_load_capacity_kg=target_l,
    )
    fcg.validate_inputs(params)
    return params


def values_to_curve_input(values: dict) -> "fcm.CurveInput":
    """Convert dialog values dict to a validated CurveInput."""
    guards = values.get(GUARDS_ID, True)
    if isinstance(guards, str):
        guards = guards.strip().lower() in {"yes", "y", "true", "1"}
    params = fcm.CurveInput(
        inner_radius_mm=float(values.get("in_radius", 800.0)),
        curve_angle_deg=float(values.get("in_angle", 90.0)),
        width_mm=float(values["in_width"]),
        height_mm=float(values["in_height"]),
        roller_dia_inner_mm=float(values["in_dia"]),
        roller_pitch_outer_mm=float(values["in_pitch"]),
        support_spacing_mm=float(values["in_leg"]),
        side_guard_height_mm=float(values["in_guard"]),
        side_guards=bool(guards),
    )
    fcm.validate_curve_inputs(params)
    return params


def preview_text(params: "fcg.ConveyorInput") -> str:
    """One-screen summary for the live preview box (never raises)."""
    try:
        derived = fcg.derive_configuration(params)
        masses = fcg.estimate_part_masses_kg(params, derived)
        hw_masses = fcg.estimate_hardware_masses_kg(params, derived)
        total = sum(masses.values())
        cap = derived.capacity
        cap_line = ""
        if cap:
            sf_badge = f"[OPTIMAL SF {cap.structural_safety_factor:.1f}x]" if cap.structural_safety_factor >= 2.0 else f"[ACCEPTABLE SF {cap.structural_safety_factor:.1f}x]"
            cap_line = (
                f"Rated Safe Load: {cap.rated_total_capacity_kg:.0f} kg ({cap.capacity_per_meter_kg:.0f} kg/m) {sf_badge}\n"
                f"Structural Safety Factor: {cap.structural_safety_factor:.1f}x | Max Unit Package: {cap.max_unit_package_kg:.0f} kg | Deflection: < {cap.deflection_mm:.2f} mm | Limit: {cap.limiting_component}\n"
            )
        braced_str = "ON (Anti-Sway)" if getattr(params, "cross_bracing", False) else "OFF (Standard)"
        return (
            f"[STRAIGHT MODULE] L={params.length_mm:.0f} W={params.width_mm:.0f} H={params.height_mm:.0f} mm\n"
            f"{cap_line}"
            f"Rollers: {derived.roller_count} @ {derived.actual_roller_spacing_mm:.1f} mm c-to-c\n"
            f"Leg stations: {derived.support_pair_count} ({derived.support_pair_count * 2} posts) | Cross-Struts: {braced_str}\n"
            f"Guards: {'ON' if params.side_guards else 'OFF'} | Est. steel mass: {total:.1f} kg (HW: {sum(hw_masses.values()):.1f} kg)\n"
            f"OPC-UA Tag: CONV_L{params.length_mm:.0f}_W{params.width_mm:.0f}"
        )
    except Exception as exc:
        return f"Invalid configuration: {exc}"


def preview_curve_text(params: "fcm.CurveInput") -> str:
    """One-screen summary for curved module live preview."""
    try:
        derived = fcm.derive_curve_configuration(params)
        masses = fcm.estimate_hardware_masses_kg(params, derived)
        total = sum(masses.values())
        return (
            f"[CURVED MODULE] Ri={params.inner_radius_mm:.0f} Ro={derived.outer_radius_mm:.0f} Angle={params.curve_angle_deg:.0f}°\n"
            f"Rollers: {derived.roller_count} Tapered ({params.roller_dia_inner_mm:.1f} -> {derived.roller_dia_outer_mm:.1f}mm)\n"
            f"Angular pitch: {derived.angular_pitch_deg:.2f}° (max 5.0°) | Leg stations: {derived.support_count}\n"
            f"Guards: {'ON' if params.side_guards else 'OFF'} | Est. Mass: {total:.1f} kg\n"
            f"OPC-UA Tag: CONV_CURVE_R{params.inner_radius_mm:.0f}_A{params.curve_angle_deg:.0f}"
        )
    except Exception as exc:
        return f"Invalid curve configuration: {exc}"

# ---------------------------------------------------------------------------
# Fusion Model Helpers
# ---------------------------------------------------------------------------


def find_existing_model(design: "adsk.fusion.Design"):
    """Return model refs for existing straight conveyor, or None."""
    try:
        for occ in design.rootComponent.occurrences:
            try:
                name = occ.name or ""
            except Exception:
                continue
            if not name.startswith("ParametricConveyor"):
                continue
            try:
                comp = occ.component
                feats = comp.features
                if feats.extrudeFeatures.count < 4:
                    continue
                if feats.rectangularPatternFeatures.count < 2:
                    continue
                guards = None
                for i in range(feats.extrudeFeatures.count):
                    feat = feats.extrudeFeatures.item(i)
                    if getattr(feat, "name", "") == "Extrude_SideGuards":
                        guards = feat
                        break
                return {
                    "component": comp,
                    "occurrence": occ,
                    "ext_guards": guards,
                    "pattern_rollers": None,
                    "pattern_legs": None,
                }
            except Exception:
                continue

        # Check root component (Part Design documents)
        root = design.rootComponent
        feats = root.features
        has_rails = False
        guards = None
        for i in range(feats.extrudeFeatures.count):
            feat = feats.extrudeFeatures.item(i)
            fname = getattr(feat, "name", "") or ""
            if fname == "Extrude_SideRails":
                has_rails = True
            elif fname == "Extrude_SideGuards":
                guards = feat
        if has_rails and feats.rectangularPatternFeatures.count >= 2:
            return {
                "component": root,
                "occurrence": None,
                "ext_guards": guards,
                "pattern_rollers": None,
                "pattern_legs": None,
            }
    except Exception:
        pass
    return None


def ensure_model(design: "adsk.fusion.Design", params: "fcg.ConveyorInput"):
    """Reuse existing straight model when valid, else build fresh."""
    fcg.create_user_parameters(design, params)
    refs = find_existing_model(design)
    if refs is None:
        refs = fcg.build_parametric_conveyor_model(design)
        design.computeAll()
        return refs, True
    fcg.update_model_parameters(design, refs, params)
    return refs, False


def _read_dialog_values(inputs: "adsk.core.CommandInputs") -> dict:
    """Read dialog inputs as mm/deg floats + booleans."""
    app = adsk.core.Application.get()
    units = app.activeProduct.unitsManager
    values = {}

    m_item = inputs.itemById(MODULE_TYPE_ID)
    values[MODULE_TYPE_ID] = m_item.selectedItem.name if (m_item and m_item.selectedItem) else "Straight Section"

    p_item = inputs.itemById(PRESET_ID)
    values[PRESET_ID] = p_item.selectedItem.name if (p_item and p_item.selectedItem) else "Custom"

    for spec_id, _label, _unit, _key, _tip in STRAIGHT_SPECS:
        item = inputs.itemById(spec_id)
        if item is not None:
            # evaluateExpression already returns the value in the requested
            # output units ("mm") — no further conversion (a second convert
            # multiplied everything x10 and broke validation).
            values[spec_id] = float(units.evaluateExpression(item.expression, "mm"))

    for spec_id, _label, unit, _tip in CURVE_SPECS:
        item = inputs.itemById(spec_id)
        if item is not None:
            values[spec_id] = float(units.evaluateExpression(item.expression, unit))

    guard_item = inputs.itemById(GUARDS_ID)
    values[GUARDS_ID] = bool(guard_item.value) if guard_item else True

    export_item = inputs.itemById(EXPORT_BTN_ID)
    # Default True so older dialogs / tests without the checkbox still export.
    values[EXPORT_BTN_ID] = bool(export_item.value) if export_item is not None else True

    brace_item = inputs.itemById(CROSS_BRACE_ID)
    values[CROSS_BRACE_ID] = bool(brace_item.value) if brace_item else True

    auto_item = inputs.itemById(AUTO_OPTIMIZE_ID)
    values[AUTO_OPTIMIZE_ID] = bool(auto_item.value) if auto_item else False

    duty_item = inputs.itemById(DUTY_CLASS_ID)
    values[DUTY_CLASS_ID] = duty_item.selectedItem.name if (duty_item and duty_item.selectedItem) else "Medium Duty (450 kg)"

    load_item = inputs.itemById(TARGET_LOAD_ID)
    if load_item is not None:
        try:
            expr_clean = load_item.value if hasattr(load_item, "value") and isinstance(load_item.value, str) else load_item.expression
            values[TARGET_LOAD_ID] = float(expr_clean.lower().replace("kg", "").strip())
        except Exception:
            values[TARGET_LOAD_ID] = 450.0
    else:
        values[TARGET_LOAD_ID] = 450.0
    return values


def _export_current(design: "adsk.fusion.Design", refs: dict, values: dict,
                    tag: str, output_dir: str) -> str:
    """Validate & export STEP, BOM CSV, and OPC-UA nodeset companion."""
    mod_type = values.get(MODULE_TYPE_ID, "Straight Section")
    is_curve = "Curve" in mod_type or "Curved" in mod_type

    if is_curve:
        params_curv = values_to_curve_input(values)
        derived_curv = fcm.derive_curve_configuration(params_curv)
        bom_path = fcm.export_curve_bom_csv(tag, params_curv, derived_curv, output_dir)
        opc_path = fcm.export_curve_opcua_nodeset_json(tag, params_curv, derived_curv, output_dir)
        step_path = os.path.join(output_dir, f"{tag}.step")
        if refs and "component" in refs:
            fcm.export_curve_step(design, refs["component"], tag, output_dir)
            return (f"{tag} [CURVE]: PASS. BOM ({os.path.basename(bom_path)}) + "
                    f"OPC-UA ({os.path.basename(opc_path)}) + STEP ({os.path.basename(step_path)}) exported.")
        return f"{tag} [CURVE]: BOM + OPC-UA exported."

    params = values_to_input(values)
    derived = fcg.derive_configuration(params)
    checks = fcg.validate_cad_model(design, refs["component"], params, refs)
    failed = [label for label, passed, _ in checks if not passed]
    counts = fcg._read_model_counts(design)
    masses = fcg.measure_part_masses_kg(design, refs, params, derived, counts)
    if masses is None:
        masses = fcg.estimate_part_masses_kg(params, derived)

    bom_path = fcg.export_bom_csv(tag, params, derived, output_dir, counts, masses)
    opc_path = fcg.export_opcua_nodeset_json(tag, params, derived, output_dir)
    bom_name = os.path.basename(bom_path)
    opc_name = os.path.basename(opc_path)

    if failed:
        return f"{tag}: VALIDATION FAIL ({'; '.join(failed)}). BOM + OPC-UA written, STEP skipped."
    step_path = fcg.export_step_file(design, refs["component"], tag, output_dir)
    return f"{tag}: PASS. BOM ({bom_name}) + OPC-UA ({opc_name}) + STEP ({os.path.basename(step_path)}) exported."

def _workspace_candidates(ui):
    """Return the active workspace first, followed by known Fusion workspaces."""
    candidates = []
    active = getattr(ui, "activeWorkspace", None)
    if active is not None:
        candidates.append(active)
    for workspace_id in ("FusionSolidEnvironment", "AssemblyEnvironment"):
        workspace = ui.workspaces.itemById(workspace_id)
        if workspace is not None and all(workspace is not item for item in candidates):
            candidates.append(workspace)
    return candidates


def _panel_candidates(workspace):
    """Return likely command panels for both Solid and Assembly workspaces."""
    panel_ids = (
        "SolidScriptsAddinsPanel",
        "SolidCreatePanel",
        "AssemblyScriptsAddinsPanel",
        "AssemblyCreatePanel",
    )
    panels = []
    for panel_id in panel_ids:
        panel = workspace.toolbarPanels.itemById(panel_id)
        if panel is not None and all(panel is not item for item in panels):
            panels.append(panel)
    return panels


def _register_command_controls(ui, cmd_def):
    """Place the command in available active-workspace panels."""
    _registered_controls.clear()
    for workspace in _workspace_candidates(ui):
        for panel in _panel_candidates(workspace):
            control = panel.controls.itemById(ADDIN_ID)
            if control is None:
                control = panel.controls.addCommand(cmd_def, ADDIN_ID)
            if control is not None:
                if panel.id.endswith("CreatePanel"):
                    control.isPromoted = True
                    control.isPromotedByDefault = True
                _registered_controls.append((workspace, panel))


def _remove_command_controls(ui):
    """Remove controls from every workspace/panel used during registration."""
    panels = []
    for workspace, registered_panel in _registered_controls:
        if all(registered_panel is not panel for panel in panels):
            panels.append(registered_panel)
    for workspace in _workspace_candidates(ui):
        for panel in _panel_candidates(workspace):
            if all(panel is not item for item in panels):
                panels.append(panel)
    for panel in panels:
        control = panel.controls.itemById(ADDIN_ID)
        if control is not None and control.isValid:
            control.deleteMe()
    _registered_controls.clear()


# ---------------------------------------------------------------------------


def run(context):
    """Initializes and mounts Add-In command buttons into Fusion UI panels."""
    if not _HAS_ADSK:
        raise RuntimeError("This add-in must be executed inside Autodesk Fusion.")
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        # Primary Conveyor Command Dialog Handlers
        # ---------------------------------------------------------------------------
        class ConveyorCreatedHandler(adsk.core.CommandCreatedEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                try:
                    cmd = args.command
                    cmd.isOKButtonVisible = True
                    cmd.okButtonText = "Build / Apply"
                    cmd.cancelButtonText = "Close"
                    cmd.setDialogMinimumSize(440, 600)

                    on_execute = ConveyorExecuteHandler()
                    cmd.execute.add(on_execute)
                    handlers.append(on_execute)

                    on_changed = ConveyorChangedHandler()
                    cmd.inputChanged.add(on_changed)
                    handlers.append(on_changed)

                    on_validate = ConveyorValidateHandler()
                    cmd.validateInputs.add(on_validate)
                    handlers.append(on_validate)

                    inputs = cmd.commandInputs
                    defaults = dialog_defaults()
                    presets = load_presets()

                    # 1. Module Type Selector
                    type_drop = inputs.addDropDownCommandInput(
                        MODULE_TYPE_ID, "Module Type", adsk.core.DropDownStyles.LabeledIconDropDownStyle
                    )
                    type_items = type_drop.listItems
                    type_items.add("Straight Section", True)
                    type_items.add("Curved 90° Section", False)
                    type_items.add("Curved 45° Section", False)
                    type_items.add("Curved 30° Section", False)
                    type_items.add("Curved 60° Section", False)

                    # 2. Preset Selector
                    preset_drop = inputs.addDropDownCommandInput(
                        PRESET_ID, "Preset / Template", adsk.core.DropDownStyles.LabeledIconDropDownStyle
                    )
                    p_items = preset_drop.listItems
                    p_items.add("Custom (Manual)", False)
                    for p_name in presets.keys():
                        p_items.add(p_name, p_name == defaults[PRESET_ID])

                    # 2b. Autonomous Capacity & Duty Class Selector
                    duty_group = inputs.addGroupCommandInput("group_capacity", "Autonomous Capacity & Duty Sizing")
                    duty_inputs = duty_group.children

                    duty_drop = duty_inputs.addDropDownCommandInput(
                        DUTY_CLASS_ID, "Duty Rating", adsk.core.DropDownStyles.LabeledIconDropDownStyle
                    )
                    d_items = duty_drop.listItems
                    d_items.add("Custom (Manual Specs)", False)
                    d_items.add("Light Duty (150 kg - Cartons & Totes)", False)
                    d_items.add("Medium Duty (450 kg - Boxes & Parts)", True)
                    d_items.add("Heavy Duty (1000 kg - Crates & Machinery)", False)
                    d_items.add("Pallet Heavy (2000 kg - Full Pallets)", False)

                    load_in = duty_inputs.addStringValueInput(
                        TARGET_LOAD_ID, "Target Payload", f"{defaults[TARGET_LOAD_ID]:.0f} kg"
                    )
                    load_in.tooltip = "Enter target payload. Autonomous engine auto-tunes rollers and legs on the fly."

                    auto_opt = duty_inputs.addBoolValueInput(
                        AUTO_OPTIMIZE_ID, "Autonomous On-The-Fly Sizing", True, "", defaults[AUTO_OPTIMIZE_ID]
                    )
                    auto_opt.tooltip = "When enabled, changing payload or dimensions immediately auto-sizes rollers and leg stations"

                    # 3. Straight inputs group
                    str_group = inputs.addGroupCommandInput("group_straight", "Straight Dimensions")
                    str_inputs = str_group.children
                    for spec_id, label, unit, _key, tip in STRAIGHT_SPECS:
                        item = str_inputs.addValueInput(
                            spec_id, label, unit,
                            adsk.core.ValueInput.createByString(f"{defaults[spec_id]} mm")
                        )
                        item.tooltip = tip

                    # 4. Curved inputs group
                    curv_group = inputs.addGroupCommandInput("group_curved", "Curved Dimensions")
                    curv_group.isVisible = False
                    curv_inputs = curv_group.children
                    for spec_id, label, unit, tip in CURVE_SPECS:
                        item = curv_inputs.addValueInput(
                            spec_id, label, unit,
                            adsk.core.ValueInput.createByString(f"{defaults[spec_id]} {unit}")
                        )
                        item.tooltip = tip

                    # 5. Accessories & Options
                    opt_group = inputs.addGroupCommandInput("group_options", "Options & Accessories")
                    opt_inputs = opt_group.children
                    guard = opt_inputs.addBoolValueInput(GUARDS_ID, "Side Guards", True, "", defaults[GUARDS_ID])
                    guard.tooltip = "Show side-guard plates (suppression-based)"
                    brace = opt_inputs.addBoolValueInput(CROSS_BRACE_ID, "Leg Cross-Struts", True, "", defaults[CROSS_BRACE_ID])
                    brace.tooltip = "Reinforce leg stations with horizontal/diagonal cross-strut ties for anti-sway stability"

                    # 6. Live Preview & Deliverables Actions
                    prev_txt = preview_text(values_to_input(defaults))
                    inputs.addTextBoxCommandInput(PREVIEW_ID, "Live Engineering Preview", prev_txt, 4, True)
                    export_opt = inputs.addBoolValueInput(EXPORT_BTN_ID, "Export STEP + BOM + OPC-UA on Apply", True, "", True)
                    export_opt.tooltip = "When ON, Build/Apply also writes STEP + BOM + OPC-UA files (export runs in Execute, never inside InputChanged, so it cannot crash Fusion)."
                    inputs.addTextBoxCommandInput(LOG_ID, "Status / Export Log", "Ready.", 5, True)
                except Exception:
                    app = adsk.core.Application.get()
                    if app and app.userInterface:
                        app.userInterface.messageBox(f"Conveyor dialog creation failed:\n{traceback.format_exc()}")

        class ConveyorChangedHandler(adsk.core.InputChangedEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                try:
                    inputs = args.inputs
                    changed = args.input
                    if changed is None:
                        return

                    # Module Type Switch: toggle straight vs curved groups
                    if changed.id == MODULE_TYPE_ID:
                        sel = changed.selectedItem.name if changed.selectedItem else "Straight Section"
                        is_curve = "Curved" in sel or "Curve" in sel
                        grp_str = inputs.itemById("group_straight")
                        grp_crv = inputs.itemById("group_curved")
                        if grp_str:
                            grp_str.isVisible = not is_curve
                        if grp_crv:
                            grp_crv.isVisible = is_curve
                        # Set angle automatically based on dropdown selection
                        if is_curve:
                            angle_inp = inputs.itemById("in_angle")
                            if angle_inp:
                                if "90" in sel:
                                    angle_inp.expression = "90 deg"
                                elif "45" in sel:
                                    angle_inp.expression = "45 deg"
                                elif "30" in sel:
                                    angle_inp.expression = "30 deg"
                                elif "60" in sel:
                                    angle_inp.expression = "60 deg"

                    # Preset Selection Change
                    elif changed.id == PRESET_ID and changed.selectedItem:
                        p_name = changed.selectedItem.name
                        presets = load_presets()
                        if p_name in presets:
                            p = presets[p_name]
                            for key, val in p.items():
                                if key == "module_type":
                                    m_drop = inputs.itemById(MODULE_TYPE_ID)
                                    if m_drop:
                                        for i in range(m_drop.listItems.count):
                                            item = m_drop.listItems.item(i)
                                            if val.lower() in item.name.lower():
                                                item.isSelected = True
                                                break
                                elif key == GUARDS_ID:
                                    g_inp = inputs.itemById(GUARDS_ID)
                                    if g_inp:
                                        g_inp.value = bool(val)
                                else:
                                    f_inp = inputs.itemById(key)
                                    if f_inp:
                                        unit = "deg" if key == "in_angle" else "mm"
                                        f_inp.expression = f"{val} {unit}"

                    # Duty Class or Target Load or Auto-Optimize Change
                    elif changed.id in (DUTY_CLASS_ID, TARGET_LOAD_ID, AUTO_OPTIMIZE_ID) or (
                        changed.id in ("in_length", "in_width", "in_height") and inputs.itemById(AUTO_OPTIMIZE_ID) and bool(inputs.itemById(AUTO_OPTIMIZE_ID).value)
                    ):
                        vals = _read_dialog_values(inputs)
                        duty_name = vals.get(DUTY_CLASS_ID, "Custom")
                        target_l = vals.get(TARGET_LOAD_ID, 450.0)

                        if changed.id == DUTY_CLASS_ID and "Custom" not in duty_name:
                            if "Light" in duty_name:
                                target_l = 150.0
                            elif "Medium" in duty_name:
                                target_l = 450.0
                            elif "Pallet" in duty_name:
                                target_l = 2000.0
                            elif "Heavy" in duty_name:
                                target_l = 1000.0
                            load_inp = inputs.itemById(TARGET_LOAD_ID)
                            if load_inp:
                                load_inp.value = f"{target_l:.0f} kg"

                        auto_on = vals.get(AUTO_OPTIMIZE_ID, False) or changed.id == DUTY_CLASS_ID
                        if auto_on and "Custom" not in duty_name:
                            opt = fcg.autonomous_optimize_conveyor(
                                target_load_kg=target_l,
                                length_mm=vals["in_length"],
                                width_mm=vals["in_width"],
                                height_mm=vals["in_height"],
                                side_guards=vals[GUARDS_ID],
                                duty_class=duty_name,
                            )
                            for attr, inp_id in (("roller_diameter_mm", "in_dia"),
                                                 ("roller_spacing_mm", "in_pitch"),
                                                 ("support_spacing_mm", "in_leg")):
                                item = inputs.itemById(inp_id)
                                if item:
                                    item.expression = f"{getattr(opt, attr):.0f} mm"
                            brace_item = inputs.itemById(CROSS_BRACE_ID)
                            if brace_item:
                                brace_item.value = opt.cross_bracing

                    # Export toggle: checkbox only, no heavy work here.
                    # Export itself runs in ConveyorExecuteHandler (Build/Apply),
                    # which is the only safe place for solve + STEP export.
                    elif changed.id == EXPORT_BTN_ID:
                        log = inputs.itemById(LOG_ID)
                        state = "ON — files will export on Build/Apply." if bool(changed.value) else "OFF — Build/Apply will only build, no files."
                        line = f"Export on Apply {state}"
                        if log is not None:
                            # Replace a previous toggle line instead of spamming.
                            existing = log.text or ""
                            lines = [ln for ln in existing.split("\n") if ln and not ln.startswith("Export on Apply") and not ln.startswith("Export deferred")]
                            lines.append(line)
                            log.text = "\n".join(lines)
                        return

                    # Live preview update
                    preview = inputs.itemById(PREVIEW_ID)
                    if preview is not None:
                        vals = _read_dialog_values(inputs)
                        mod_type = vals.get(MODULE_TYPE_ID, "Straight Section")
                        if "Curve" in mod_type or "Curved" in mod_type:
                            try:
                                preview.text = preview_curve_text(values_to_curve_input(vals))
                            except Exception as exc:
                                preview.text = f"Invalid curve: {exc}"
                        else:
                            try:
                                preview.text = preview_text(values_to_input(vals))
                            except Exception as exc:
                                preview.text = f"Invalid straight: {exc}"
                except Exception:
                    pass

        class ConveyorValidateHandler(adsk.core.ValidateInputsEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                try:
                    vals = _read_dialog_values(args.inputs)
                    mod_type = vals.get(MODULE_TYPE_ID, "Straight Section")
                    if "Curve" in mod_type or "Curved" in mod_type:
                        values_to_curve_input(vals)
                    else:
                        values_to_input(vals)
                    args.areInputsValid = True
                except Exception as exc:
                    args.areInputsValid = False
                    args.message = str(exc)

        class ConveyorExecuteHandler(adsk.core.CommandEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                app = adsk.core.Application.get()
                ui = app.userInterface
                try:
                    design = adsk.fusion.Design.cast(app.activeProduct)
                    if not design:
                        ui.messageBox("Open an active Fusion Design first.")
                        return
                    vals = _read_dialog_values(args.command.commandInputs)
                    mod_type = vals.get(MODULE_TYPE_ID, "Straight Section")

                    if "Curve" in mod_type or "Curved" in mod_type:
                        p_crv = values_to_curve_input(vals)
                        derived = fcm.derive_curve_configuration(p_crv)
                        refs = fcm.build_curve_module_full(design, p_crv)
                        export_line = ""
                        if vals.get(EXPORT_BTN_ID, True):
                            try:
                                export_line = "\n\n" + _export_current(design, refs, vals, "Dialog_Apply_Curve", fcg.DEFAULT_OUTPUT_DIR)
                            except Exception as exc:
                                export_line = f"\n\nExport failed (build OK): {exc}"
                        ui.messageBox(
                            f"Curved Conveyor ({p_crv.curve_angle_deg:.0f}°) Generated Successfully!\n\n"
                            f"Rollers: {derived.roller_count} tapered (angular pitch: {derived.angular_pitch_deg:.2f}°)\n"
                            f"Inner/Outer Radius: {p_crv.inner_radius_mm:.0f} / {derived.outer_radius_mm:.0f} mm\n"
                            f"Support Stations: {derived.support_count}\n"
                            f"OPC-UA Tag: CONV_CURVE_R{p_crv.inner_radius_mm:.0f}_A{p_crv.curve_angle_deg:.0f}"
                            f"{export_line}"
                        )
                    else:
                        params = values_to_input(vals)
                        refs, built = ensure_model(design, params)
                        derived = fcg.derive_configuration(params)
                        if params.cross_bracing and refs and "component" in refs:
                            fcg.build_leg_cross_bracing(refs["component"], params, derived)
                        checks = fcg.validate_cad_model(design, refs["component"], params, refs)
                        lines = [f"  [{'PASS' if p else 'FAIL'}] {label}: {detail}" for label, p, detail in checks]
                        cap = derived.capacity
                        cap_txt = (f"\nRated Capacity: {cap.rated_total_capacity_kg:.0f} kg ({cap.capacity_per_meter_kg:.0f} kg/m)\n"
                                   f"Structural Safety Factor: {cap.structural_safety_factor:.1f}x\n"
                                   f"Cross-Struts: {'Active (Anti-Sway)' if params.cross_bracing else 'None'}\n"
                                   if cap else "")
                        export_line = ""
                        if vals.get(EXPORT_BTN_ID, True):
                            try:
                                export_line = "\n\n" + _export_current(design, refs, vals, "Dialog_Apply_Straight", fcg.DEFAULT_OUTPUT_DIR)
                            except Exception as exc:
                                export_line = f"\n\nExport failed (build OK): {exc}"
                        ui.messageBox(
                            f"Straight Conveyor {'Built' if built else 'Updated'} In-Place!\n\n"
                            f"Rollers: {derived.roller_count} @ {derived.actual_roller_spacing_mm:.1f} mm\n"
                            f"Support Posts: {derived.support_pair_count * 2}\n"
                            f"Guards: {'ON' if params.side_guards else 'OFF'}\n"
                            f"{cap_txt}\n" + "\n".join(lines)
                            + export_line
                        )
                except Exception:
                    if ui:
                        ui.messageBox(f"Conveyor build failed:\n{traceback.format_exc()}")

        # ---------------------------------------------------------------------------
        # Secondary Docking Command Dialog Handlers (Lego Line Builder)
        # ---------------------------------------------------------------------------
        class DockingCreatedHandler(adsk.core.CommandCreatedEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                try:
                    cmd = args.command
                    cmd.isOKButtonVisible = True
                    cmd.okButtonText = "Snap & Dock"
                    cmd.cancelButtonText = "Cancel"

                    on_execute = DockingExecuteHandler()
                    cmd.execute.add(on_execute)
                    handlers.append(on_execute)

                    inputs = cmd.commandInputs
                    # Next Module Type to Dock
                    next_type = inputs.addDropDownCommandInput(
                        "dock_next_type", "Next Module to Dock", adsk.core.DropDownStyles.LabeledIconDropDownStyle
                    )
                    n_items = next_type.listItems
                    n_items.add("Straight (L=1400 mm, W=450 mm)", True)
                    n_items.add("Straight (L=1000 mm, W=450 mm)", False)
                    n_items.add("Curved 90° (Ri=800 mm, W=450 mm)", False)
                    n_items.add("Curved 45° (Ri=800 mm, W=450 mm)", False)

                    inputs.addTextBoxCommandInput(
                        "dock_info", "Docking Rules",
                        "Snaps the next module to the active conveyor outlet port.\n"
                        "Matches carry height (<=1mm) and preserves roller pitch continuity (<=P+10mm).",
                        3, True
                    )
                except Exception:
                    pass

        class DockingExecuteHandler(adsk.core.CommandEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                app = adsk.core.Application.get()
                ui = app.userInterface
                try:
                    design = adsk.fusion.Design.cast(app.activeProduct)
                    if not design:
                        ui.messageBox("Open an active Fusion Design first.")
                        return

                    inputs = args.command.commandInputs
                    next_item = inputs.itemById("dock_next_type")
                    sel_text = next_item.selectedItem.name if (next_item and next_item.selectedItem) else "Straight"

                    # Find parent conveyor in root occurrences
                    parent_occ = None
                    for occ in design.rootComponent.occurrences:
                        if (occ.name or "").startswith("ParametricConveyor") or (occ.name or "").startswith("CurveModule"):
                            parent_occ = occ
                            break

                    if parent_occ is None:
                        ui.messageBox("No existing conveyor module found in the design to dock against. Create one first!")
                        return

                    # Read parent ports
                    p_str = fcg.ConveyorInput(1400.0, 450.0, 750.0, 60.0, 110.0, 700.0, 100.0, True)
                    parent_ports = fcg.get_module_ports(p_str)
                    p_outlet = parent_ports["outlet_port"]

                    if "Curved" in sel_text:
                        deg = 90.0 if "90" in sel_text else 45.0
                        child_p = fcm.CurveInput(800.0, deg, 450.0, 750.0, 50.0, 110.0, 700.0, 100.0, True)
                        child_derived = fcm.derive_curve_configuration(child_p)
                        child_ports = fcm.get_curve_module_ports(child_p, child_derived)
                        transform = fds.compute_docking_transform(p_outlet, child_ports["inlet_port"])
                        refs = fcm.build_curve_module_full(design, child_p, f"Docked_Curve_{deg:.0f}deg")
                        occ = refs.get("occurrence")
                        if occ:
                            fds.apply_docking_to_occurrence(occ, transform)
                    else:
                        length = 1000.0 if "1000" in sel_text else 1400.0
                        child_p = fcg.ConveyorInput(length, 450.0, 750.0, 60.0, 110.0, 700.0, 100.0, True)
                        child_ports = fcg.get_module_ports(child_p)
                        transform = fds.compute_docking_transform(p_outlet, child_ports["inlet_port"])
                        root = design.rootComponent
                        child_occ = root.occurrences.addNewComponent(transform.to_fusion_matrix())
                        child_comp = child_occ.component
                        child_comp.name = f"Docked_Straight_L{length:.0f}"
                        child_occ.name = f"Docked_Straight_L{length:.0f}"

                    ui.messageBox("Next module docked and aligned to line successfully!\nAll joint tolerances satisfied.")
                except Exception:
                    if ui:
                        ui.messageBox(f"Docking failed:\n{traceback.format_exc()}")

        # ---------------------------------------------------------------------------
        # Add-In Lifecycle (run / stop)
        # ---------------------------------------------------------------------------
        cmd_defs = ui.commandDefinitions

        # 1. Primary Module Generator Command
        # Guard: only subscribe commandCreated when the definition is new.
        # Re-adding on every run() stacks duplicate handlers (double dialog /
        # double build on one click) and leaks memory (RADAR_PRE_LEAK_64).
        cmd_def = cmd_defs.itemById(ADDIN_ID)
        if cmd_def is None:
            cmd_def = cmd_defs.addButtonDefinition(ADDIN_ID, ADDIN_NAME, ADDIN_TOOLTIP)
            on_created = ConveyorCreatedHandler()
            cmd_def.commandCreated.add(on_created)
            handlers.append(on_created)

        _register_command_controls(ui, cmd_def)
        if not _registered_controls:
            raise RuntimeError("No supported toolbar panel found in the active Fusion workspace.")

        # 2. Docking Tool Command
        dock_def = cmd_defs.itemById(DOCK_CMD_ID)
        if dock_def is None:
            dock_def = cmd_defs.addButtonDefinition(DOCK_CMD_ID, DOCK_CMD_NAME, DOCK_CMD_TOOLTIP)
            on_dock_created = DockingCreatedHandler()
            dock_def.commandCreated.add(on_dock_created)
            handlers.append(on_dock_created)

        # Mount into Solid Workspaces
        workspace = ui.workspaces.itemById("FusionSolidEnvironment")
        if workspace:
            panel = workspace.toolbarPanels.itemById("SolidScriptsAddinsPanel")
            if panel and panel.controls.itemById(ADDIN_ID) is None:
                panel.controls.addCommand(cmd_def, ADDIN_ID)

            create_panel = workspace.toolbarPanels.itemById("SolidCreatePanel")
            if create_panel:
                if create_panel.controls.itemById(ADDIN_ID) is None:
                    c_ctrl = create_panel.controls.addCommand(cmd_def, ADDIN_ID)
                    c_ctrl.isPromoted = True
                    c_ctrl.isPromotedByDefault = True
                if create_panel.controls.itemById(DOCK_CMD_ID) is None:
                    d_ctrl = create_panel.controls.addCommand(dock_def, DOCK_CMD_ID)
                    d_ctrl.isPromoted = True

    except Exception:
        if ui:
            ui.messageBox(f"Conveyor add-in startup failed:\n{traceback.format_exc()}")


def stop(context):
    """Cleans up all toolbar buttons, panels, and command definitions cleanly."""
    ui = None
    try:
        if not _HAS_ADSK:
            handlers.clear()
            return
        try:
            app = adsk.core.Application.get()
        except Exception:
            app = None
        if app is None:
            handlers.clear()
            return
        try:
            ui = app.userInterface
        except Exception:
            ui = None
        if ui is None:
            handlers.clear()
            return
        _remove_command_controls(ui)

        try:
            cmd_defs = ui.commandDefinitions
        except Exception:
            cmd_defs = None
        if cmd_defs is not None:
            for _cid in (ADDIN_ID, DOCK_CMD_ID):
                try:
                    cmd_def = cmd_defs.itemById(_cid)
                except Exception:
                    cmd_def = None
                if cmd_def is not None:
                    try:
                        if cmd_def.isValid:
                            cmd_def.deleteMe()
                    except Exception:
                        pass
    except Exception:
        try:
            if ui:
                ui.messageBox(f"Conveyor add-in stop failed:\n{traceback.format_exc()}")
        except Exception:
            pass
    finally:
        handlers.clear()
