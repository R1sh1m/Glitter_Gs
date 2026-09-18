"""Glitter_Gs parametric conveyor add-in (Problem Statement A).

Persistent companion to ``fusion_conveyor_generator.py`` (the single-file
script). Same engine, richer shell: a typed CommandInputs dialog with live
preview, an Export button with a stay-open status log, and model reuse
(find the existing ``ParametricConveyor_Assembly`` instead of rebuilding).

Install: copy this folder AND ``fusion_conveyor_generator.py`` so that both
live side by side (the engine is imported from the sibling or parent
directory), place the folder in
``%APPDATA%\\Autodesk\\Autodesk Fusion 360\\API\\AddIns\\`` (Windows) or
``~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/``
(macOS), then enable it under Utilities -> Scripts and Add-Ins -> Add-Ins.
"""

import os
import sys
import traceback

_here = os.path.dirname(os.path.realpath(__file__))
for _candidate in (_here, os.path.dirname(_here)):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import fusion_conveyor_generator as fcg  # noqa: E402

try:
    import adsk.core  # type: ignore
    import adsk.fusion  # type: ignore
    _HAS_ADSK = True
except ImportError:  # pragma: no cover - importable outside Fusion for tests
    adsk = None
    _HAS_ADSK = False

ADDIN_ID = "GlitterGsConveyorAddin"
ADDIN_NAME = "Parametric Conveyor Generator"
ADDIN_TOOLTIP = "Parametric adjustable roller conveyor (Problem Statement A)"

# (input id, label, unit, range key, tooltip)
INPUT_SPECS = (
    ("in_length", "Conveyor Length", "mm", "L", "Overall length, 800-2000 mm"),
    ("in_width", "Conveyor Width", "mm", "W", "Overall width, 300-600 mm"),
    ("in_height", "Frame Height", "mm", "H", "Floor to frame, 500-900 mm"),
    ("in_dia", "Roller Diameter", "mm", "D", "Roller outside diameter, 40-80 mm"),
    ("in_pitch", "Roller Spacing", "mm", "P", "Centre-to-centre, 80-150 mm"),
    ("in_leg", "Leg Spacing", "mm", "S", "Support station spacing, 500-1000 mm"),
    ("in_guard", "Guard Height", "mm", "G", "Side-guard height, 0-150 mm"),
)
GUARDS_ID = "in_guards"
PREVIEW_ID = "preview"
LOG_ID = "status_log"
EXPORT_BTN_ID = "btn_export"

handlers = []
_registered_controls = []


# ---------------------------------------------------------------------------
# Pure helpers (no Fusion required — covered by offline tests)
# ---------------------------------------------------------------------------
def dialog_defaults() -> dict:
    """Default dialog values in mm (C2 medium configuration)."""
    demo = fcg.demo_configurations()["C2_medium_with_guards"]
    return {
        "in_length": demo.length_mm,
        "in_width": demo.width_mm,
        "in_height": demo.height_mm,
        "in_dia": demo.roller_diameter_mm,
        "in_pitch": demo.roller_spacing_mm,
        "in_leg": demo.support_spacing_mm,
        "in_guard": demo.side_guard_height_mm,
        GUARDS_ID: demo.side_guards,
    }


def values_to_input(values: dict) -> "fcg.ConveyorInput":
    """Convert a dialog-values dict to a validated ConveyorInput."""
    guards = values.get(GUARDS_ID, True)
    if isinstance(guards, str):
        guards = guards.strip().lower() in {"yes", "y", "true", "1"}
    params = fcg.ConveyorInput(
        length_mm=float(values["in_length"]),
        width_mm=float(values["in_width"]),
        height_mm=float(values["in_height"]),
        roller_diameter_mm=float(values["in_dia"]),
        roller_spacing_mm=float(values["in_pitch"]),
        support_spacing_mm=float(values["in_leg"]),
        side_guard_height_mm=float(values["in_guard"]),
        side_guards=bool(guards),
    )
    fcg.validate_inputs(params)
    return params


def preview_text(params: "fcg.ConveyorInput") -> str:
    """One-screen summary for the live preview box (never raises)."""
    try:
        derived = fcg.derive_configuration(params)
        masses = fcg.estimate_part_masses_kg(params, derived)
        total = sum(masses.values())
        return (
            f"L={params.length_mm:.0f} W={params.width_mm:.0f} H={params.height_mm:.0f} mm\n"
            f"Rollers: {derived.roller_count} @ {derived.actual_roller_spacing_mm:.1f} mm\n"
            f"Leg stations: {derived.support_pair_count} "
            f"({derived.support_pair_count * 2} posts @ {derived.actual_support_spacing_mm:.0f} mm)\n"
            f"Guards: {'on' if params.side_guards else 'off'} | "
            f"Est. steel mass: {total:.1f} kg"
        )
    except Exception as exc:
        return f"Invalid configuration: {exc}"


# ---------------------------------------------------------------------------
# Fusion model helpers (require a live design)
# ---------------------------------------------------------------------------
def find_existing_model(design: "adsk.fusion.Design"):
    """Return model refs for the existing conveyor, or None.

    A candidate counts only if it carries our extrude + pattern signature,
    so unrelated components named similarly are never hijacked.
    """
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
    except Exception:
        pass
    return None


def ensure_model(design: "adsk.fusion.Design", params: "fcg.ConveyorInput"):
    """Reuse the existing model when valid, else build fresh.

    Returns (model_refs, built_new). Parameters are always created first
    (idempotent) and values applied in place with a single compute.
    """
    fcg.create_user_parameters(design, params)
    refs = find_existing_model(design)
    if refs is None:
        refs = fcg.build_parametric_conveyor_model(design)
        design.computeAll()
        return refs, True
    fcg.update_model_parameters(design, refs, params)
    return refs, False


def _read_dialog_values(inputs: "adsk.core.CommandInputs") -> dict:
    """Read dialog inputs as mm floats + guard bool (raises on failure)."""
    app = adsk.core.Application.get()
    units = app.activeProduct.unitsManager
    values = {}
    for spec_id, _label, _unit, _key, _tip in INPUT_SPECS:
        item = inputs.itemById(spec_id)
        if item is None:
            raise ValueError(f"Dialog input '{spec_id}' is missing.")
        values[spec_id] = float(units.evaluateExpression(item.expression, "mm"))
    guard_item = inputs.itemById(GUARDS_ID)
    if guard_item is None:
        raise ValueError("Dialog input for side guards is missing.")
    values[GUARDS_ID] = bool(guard_item.value)
    return values


def _export_current(design: "adsk.fusion.Design", refs: dict, params: "fcg.ConveyorInput",
                    tag: str, output_dir: str) -> str:
    """Validate + export BOM/STEP for the current dialog values; return log line."""
    derived = fcg.derive_configuration(params)
    checks = fcg.validate_cad_model(design, refs["component"], params, refs)
    failed = [label for label, passed, _ in checks if not passed]
    counts = fcg._read_model_counts(design)
    masses = fcg.measure_part_masses_kg(design, refs, params, derived, counts)
    if masses is None:
        masses = fcg.estimate_part_masses_kg(params, derived)
    bom_path = fcg.export_bom_csv(tag, params, derived, output_dir, counts, masses)
    bom_name = os.path.basename(bom_path)
    if failed:
        return f"{tag}: VALIDATION FAIL ({'; '.join(failed)}). BOM ({bom_name}) written, STEP skipped."
    step_path = fcg.export_step_file(design, refs["component"], tag, output_dir)
    return f"{tag}: PASS. BOM ({bom_name}) + STEP ({os.path.basename(step_path)}) exported."


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
# Add-in entry points (Fusion only)
# ---------------------------------------------------------------------------
def run(context):
    if not _HAS_ADSK:
        raise RuntimeError("This add-in must be executed inside Autodesk Fusion.")
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        class ConveyorCreatedHandler(adsk.core.CommandCreatedEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                try:
                    cmd = args.command
                    cmd.isOKButtonVisible = True
                    cmd.okButtonText = "Apply && Close"
                    cmd.cancelButtonText = "Close"
                    cmd.setDialogMinimumSize(420, 560)

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
                    for spec_id, label, unit, _key, tip in INPUT_SPECS:
                        item = inputs.addValueInput(
                            spec_id, label, unit,
                            adsk.core.ValueInput.createByString(f"{defaults[spec_id]} mm"))
                        item.tooltip = tip
                    guard = inputs.addBoolValueInput(GUARDS_ID, "Side Guards", True, "", defaults[GUARDS_ID])
                    guard.tooltip = "Show side-guard plates (suppression, independent of height)"
                    preview_default = preview_text(values_to_input(defaults))
                    inputs.addTextBoxCommandInput(PREVIEW_ID, "Live Preview", preview_default, 4, True)
                    inputs.addBoolValueInput(EXPORT_BTN_ID, "Export STEP + BOM Now", False, "", False)
                    inputs.addTextBoxCommandInput(LOG_ID, "Status Log", "Ready.", 6, True)
                except Exception:
                    if ui:
                        ui.messageBox(f"Conveyor dialog failed:\n{traceback.format_exc()}")

        class ConveyorChangedHandler(adsk.core.InputChangedEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                try:
                    inputs = args.inputs
                    changed = args.input
                    if changed is not None and changed.id == EXPORT_BTN_ID and bool(changed.value):
                        changed.value = False
                        app = adsk.core.Application.get()
                        design = adsk.fusion.Design.cast(app.activeProduct)
                        log = inputs.itemById(LOG_ID)
                        try:
                            if not design:
                                raise RuntimeError("Open a Fusion model design first.")
                            params = values_to_input(_read_dialog_values(inputs))
                            refs, _built = ensure_model(design, params)
                            line = _export_current(design, refs, params, "Dialog_Export", fcg.DEFAULT_OUTPUT_DIR)
                        except Exception as exc:
                            line = f"Export failed: {exc}"
                        if log is not None:
                            log.text = (log.text + "\n" + line) if log.text else line
                        adsk.doEvents()
                        return
                    preview = inputs.itemById(PREVIEW_ID)
                    if preview is not None:
                        try:
                            preview.text = preview_text(values_to_input(_read_dialog_values(inputs)))
                        except Exception as exc:
                            preview.text = f"Invalid configuration: {exc}"
                except Exception:
                    pass

        class ConveyorValidateHandler(adsk.core.ValidateInputsEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                try:
                    values_to_input(_read_dialog_values(args.inputs))
                    args.areInputsValid = True
                except Exception as exc:
                    args.areInputsValid = False
                    args.message = str(exc)

        class ConveyorExecuteHandler(adsk.core.CommandEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                try:
                    app = adsk.core.Application.get()
                    design = adsk.fusion.Design.cast(app.activeProduct)
                    if not design:
                        ui.messageBox("Open a Fusion model design first.")
                        return
                    params = values_to_input(_read_dialog_values(args.command.commandInputs))
                    refs, built = ensure_model(design, params)
                    derived = fcg.derive_configuration(params)
                    checks = fcg.validate_cad_model(design, refs["component"], params, refs)
                    lines = [f"  [{'PASS' if p else 'FAIL'}] {label}: {detail}" for label, p, detail in checks]
                    ui.messageBox(
                        f"Conveyor {'built' if built else 'updated'} in place!\n\n"
                        f"Rollers: {derived.roller_count} @ {derived.actual_roller_spacing_mm:.1f} mm\n"
                        f"Leg posts: {derived.support_pair_count * 2}\n"
                        f"Guards: {'on' if params.side_guards else 'off'}\n\n" + "\n".join(lines))
                except Exception:
                    if ui:
                        ui.messageBox(f"Conveyor apply failed:\n{traceback.format_exc()}")

        cmd_defs = ui.commandDefinitions
        cmd_def = cmd_defs.itemById(ADDIN_ID)
        if cmd_def is None:
            cmd_def = cmd_defs.addButtonDefinition(ADDIN_ID, ADDIN_NAME, ADDIN_TOOLTIP)
        on_created = ConveyorCreatedHandler()
        cmd_def.commandCreated.add(on_created)
        handlers.append(on_created)

        _register_command_controls(ui, cmd_def)
        if not _registered_controls:
            raise RuntimeError("No supported toolbar panel found in the active Fusion workspace.")
    except Exception:
        if ui:
            ui.messageBox(f"Conveyor add-in failed:\n{traceback.format_exc()}")


def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        _remove_command_controls(ui)
        cmd_def = ui.commandDefinitions.itemById(ADDIN_ID)
        if cmd_def is not None and cmd_def.isValid:
            cmd_def.deleteMe()
    except Exception:
        if ui:
            ui.messageBox(f"Conveyor add-in stop failed:\n{traceback.format_exc()}")
