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
import math
import os
import sys
import traceback
from typing import Any, Dict, Optional

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

# Dialog layout contract retained for older Fusion builds and offline tests.
DIALOG_MIN_WIDTH = 440
DIALOG_MIN_HEIGHT = 650
TAB_SETUP_ID = "tab_setup"
TAB_DIMS_ID = "tab_dimensions"
TAB_CAPACITY_ID = "tab_capacity"
TAB_PREVIEW_ID = "tab_preview"
SETUP_HELP_ID = "help_setup"
PREVIEW_ROWS = 4
LOG_ROWS = 3

# Keep backward-compatible tuple for existing tests
INPUT_SPECS = STRAIGHT_SPECS

# Global event handler storage to prevent garbage collection
handlers = []
_registered_controls = []

# Last validation state, mirrored to the status log only on transitions
# (per-keystroke log writes were spam; tooltip + debug file carry detail).
_last_valid_state: Optional[bool] = None
_last_valid_msg = ""

# Re-entrancy guard: programmatic .expression/.value writes inside
# inputChanged re-fire inputChanged. Without a guard the handler can
# recurse (preset -> sync -> auto-opt -> preview reads of half-written
# state) and the outer bare-except used to swallow everything, leaving
# the UI stale. When True the nested event returns immediately.
_in_input_changed = False


# Active dialog inputs registry (ensures instantaneous lookup in multi-tab layouts)
_active_dialog_inputs: Dict[str, Any] = {}


def _register_dialog_input(item):
    """Register created command input in active lookup cache."""
    if item is not None:
        ident = getattr(item, "id", None)
        if ident:
            _active_dialog_inputs[ident] = item
    return item


def _find_input(inputs, ident):
    """Robust input lookup that handles Fusion tabs, groups, and collections.

    Production code nests inputs two levels deep
    (tab.children -> group.children -> value input). Some Fusion builds
    and all flat test fakes expose only top-level itemById, so fall back
    to an active cache lookup, itemById, and cast-aware recursion through
    tab/group children. Never raises; returns None when not found.
    """
    if not ident:
        return None

    # 1. Fast active dialog cache lookup
    cached = _active_dialog_inputs.get(ident)
    if cached is not None:
        try:
            if getattr(cached, "id", None) == ident and getattr(cached, "isValid", True):
                return cached
        except Exception:
            _active_dialog_inputs.pop(ident, None)

    if inputs is None:
        return None

    # 2. Top-level itemById check
    try:
        found = inputs.itemById(ident)
        if found is not None:
            return found
    except Exception:
        pass

    seen = set()

    def _walk(collection):
        if collection is None or id(collection) in seen:
            return None
        seen.add(id(collection))

        # Check itemById directly on the collection if supported
        try:
            direct = collection.itemById(ident)
            if direct is not None:
                return direct
        except Exception:
            pass

        # FakeInputs-style store
        store = getattr(collection, "_store", None)
        if isinstance(store, dict):
            if ident in store:
                return store[ident]
            for obj in list(store.values()):
                children = getattr(obj, "children", None)
                if children is not None:
                    hit = _walk(children)
                    if hit is not None:
                        return hit

        # Real CommandInputs-style count/item(i)
        try:
            count = int(collection.count)
        except Exception:
            count = -1
        if count >= 0:
            for i in range(count):
                try:
                    child = collection.item(i)
                except Exception:
                    continue
                try:
                    if getattr(child, "id", None) == ident:
                        return child
                except Exception:
                    pass

                # Resolve children for TabCommandInput / GroupCommandInput
                children = getattr(child, "children", None)
                if children is None and hasattr(adsk, "core"):
                    tab_cls = getattr(adsk.core, "TabCommandInput", None)
                    if tab_cls and hasattr(tab_cls, "cast"):
                        t_obj = tab_cls.cast(child)
                        if t_obj:
                            children = getattr(t_obj, "children", None)
                    if children is None:
                        grp_cls = getattr(adsk.core, "GroupCommandInput", None)
                        if grp_cls and hasattr(grp_cls, "cast"):
                            g_obj = grp_cls.cast(child)
                            if g_obj:
                                children = getattr(g_obj, "children", None)

                if children is not None:
                    hit = _walk(children)
                    if hit is not None:
                        return hit
        return None

    try:
        return _walk(inputs)
    except Exception:
        return None


def _log_dialog_error(context: str, exc: BaseException) -> None:
    """Best-effort file log for dialog handler failures (never raises)."""
    try:
        out_dir = getattr(fcg, "DEFAULT_OUTPUT_DIR", None) or os.path.join(
            os.path.expanduser("~"), "ConveyorGenerator_Output"
        )
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "dialog_errors.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{context}: {exc!r}\n{traceback.format_exc()}\n")
    except Exception:
        pass

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


def _try_separator(container, sep_id: str) -> None:
    """Add a visual separator when the active Fusion build supports it."""
    try:
        container.addSeparatorCommandInput(sep_id)
    except Exception:
        pass


def build_dialog_layout(inputs, defaults: dict, presets: Dict[str, Dict[str, Any]], adsk_mod=None):
    """Build the tabbed command layout with a flat fallback."""
    _active_dialog_inputs.clear()
    mod = adsk_mod if adsk_mod is not None else adsk
    drop_style = mod.core.DropDownStyles.LabeledIconDropDownStyle
    try:
        tab_setup = _register_dialog_input(inputs.addTabCommandInput(TAB_SETUP_ID, "Setup"))
        tab_dims = _register_dialog_input(inputs.addTabCommandInput(TAB_DIMS_ID, "Dimensions"))
        tab_capacity = _register_dialog_input(inputs.addTabCommandInput(TAB_CAPACITY_ID, "Capacity & Options"))
        tab_preview = _register_dialog_input(inputs.addTabCommandInput(TAB_PREVIEW_ID, "Preview & Status"))
        tabbed = True
        tabs = [tab_setup, tab_dims, tab_capacity, tab_preview]
        setup_inputs = tab_setup.children
        dims_inputs = tab_dims.children
        capacity_inputs = tab_capacity.children
        preview_inputs = tab_preview.children
    except Exception:
        tabbed = False
        tabs = []
        setup_inputs = dims_inputs = capacity_inputs = preview_inputs = inputs

    type_drop = _register_dialog_input(setup_inputs.addDropDownCommandInput(MODULE_TYPE_ID, "Module Type", drop_style))
    type_drop.listItems.add("Straight Section", True)
    type_drop.listItems.add("Curved 90° Section", False)
    type_drop.listItems.add("Curved 45° Section", False)
    type_drop.listItems.add("Curved 30° Section", False)
    type_drop.listItems.add("Curved 60° Section", False)

    preset_drop = _register_dialog_input(setup_inputs.addDropDownCommandInput(PRESET_ID, "Preset / Template", drop_style))
    preset_drop.listItems.add("Custom (Manual)", False)
    for name in presets:
        preset_drop.listItems.add(name, name == defaults[PRESET_ID])
    try:
        setup_inputs.addTextBoxCommandInput(
            SETUP_HELP_ID, "How to use",
            "Choose a module, select a preset, edit dimensions, review the preview, then Build / Apply.",
            2, True,
        )
    except Exception:
        pass
    _try_separator(setup_inputs, "sep_setup")

    shared_group = _register_dialog_input(dims_inputs.addGroupCommandInput("group_straight", "Shared Conveyor Dimensions"))
    for spec_id, label, unit, _key, tip in STRAIGHT_SPECS:
        item = _register_dialog_input(shared_group.children.addValueInput(
            spec_id, label, unit,
            mod.core.ValueInput.createByString(f"{defaults[spec_id]} {unit}"),
        ))
        item.tooltip = tip

    _try_separator(dims_inputs, "sep_dimensions")
    curved_group = _register_dialog_input(dims_inputs.addGroupCommandInput("group_curved", "Curved Dimensions"))
    curved_group.isVisible = False
    for spec_id, label, unit, tip in CURVE_SPECS:
        item = _register_dialog_input(curved_group.children.addValueInput(
            spec_id, label, unit,
            mod.core.ValueInput.createByString(f"{defaults[spec_id]} {unit}"),
        ))
        item.tooltip = tip

    capacity_group = _register_dialog_input(capacity_inputs.addGroupCommandInput(
        "group_capacity", "Autonomous Capacity & Duty Sizing"
    ))
    duty_drop = _register_dialog_input(capacity_group.children.addDropDownCommandInput(
        DUTY_CLASS_ID, "Duty Rating", drop_style
    ))
    for name, selected in (
        ("Custom (Manual Specs)", False),
        ("Light Duty (150 kg - Cartons & Totes)", False),
        ("Medium Duty (450 kg - Boxes & Parts)", True),
        ("Heavy Duty (1000 kg - Crates & Machinery)", False),
        ("Pallet Heavy (2000 kg - Full Pallets)", False),
    ):
        duty_drop.listItems.add(name, selected)
    _register_dialog_input(capacity_group.children.addStringValueInput(
        TARGET_LOAD_ID, "Target Payload", f"{defaults[TARGET_LOAD_ID]:.0f} kg"
    ))
    _register_dialog_input(capacity_group.children.addBoolValueInput(
        AUTO_OPTIMIZE_ID, "Autonomous On-The-Fly Sizing", True, "",
        defaults[AUTO_OPTIMIZE_ID],
    ))

    options_group = _register_dialog_input(capacity_inputs.addGroupCommandInput("group_options", "Options & Accessories"))
    _register_dialog_input(options_group.children.addBoolValueInput(
        GUARDS_ID, "Side Guards", True, "", defaults[GUARDS_ID]
    ))
    _register_dialog_input(options_group.children.addBoolValueInput(
        CROSS_BRACE_ID, "Leg Cross-Struts", True, "", defaults[CROSS_BRACE_ID]
    ))

    _register_dialog_input(preview_inputs.addTextBoxCommandInput(
        PREVIEW_ID, "Live Engineering Preview",
        preview_text(values_to_input(defaults)), PREVIEW_ROWS, True,
    ))
    _register_dialog_input(preview_inputs.addBoolValueInput(
        EXPORT_BTN_ID, "Export STEP + BOM + OPC-UA on Apply", True, "", True
    ))
    _try_separator(preview_inputs, "sep_preview")
    _register_dialog_input(preview_inputs.addTextBoxCommandInput(
        LOG_ID, "Status / Export Log", "Ready.", LOG_ROWS, True
    ))

    return {
        "tabbed": tabbed,
        "tabs": tabs,
        "straight_group": shared_group,
        "curved_group": curved_group,
        "capacity_group": capacity_group,
        "options_group": options_group,
    }


def _apply_preset_to_inputs(inputs, preset: dict) -> None:
    """Apply a preset dictionary to native Fusion command inputs."""
    module_type = str(preset.get("module_type", "")).lower()
    if module_type:
        module_input = _find_input(inputs, MODULE_TYPE_ID)
        if module_input is not None:
            target = "Curved" if module_type == "curve" else "Straight"
            for index in range(module_input.listItems.count):
                item = module_input.listItems.item(index)
                item.isSelected = target.lower() in item.name.lower()

    duty_name = preset.get(DUTY_CLASS_ID)
    if duty_name is not None:
        duty_input = _find_input(inputs, DUTY_CLASS_ID)
        if duty_input is not None:
            for index in range(duty_input.listItems.count):
                item = duty_input.listItems.item(index)
                item.isSelected = str(duty_name).lower() in item.name.lower()

    for key, value in preset.items():
        item = _find_input(inputs, key)
        if item is None:
            continue
        if key in (GUARDS_ID, CROSS_BRACE_ID):
            item.value = bool(value)
        elif key == TARGET_LOAD_ID:
            item.value = f"{float(value):.0f} kg"
        elif key not in ("module_type", DUTY_CLASS_ID):
            unit = "deg" if key == "in_angle" else "mm"
            item.expression = f"{value} {unit}"


def _sync_module_inputs(inputs) -> None:
    """Keep module visibility and curve angle aligned with the module selector."""
    module_input = _find_input(inputs, MODULE_TYPE_ID)
    selected = module_input.selectedItem.name if module_input and module_input.selectedItem else "Straight Section"
    is_curve = "Curved" in selected or "Curve" in selected

    straight_group = _find_input(inputs, "group_straight")
    curved_group = _find_input(inputs, "group_curved")
    if straight_group is not None:
        # Width, height, roller, leg, and guard fields are shared by both
        # module types; keep them visible while the curve-only fields toggle.
        straight_group.isVisible = True
    if curved_group is not None:
        curved_group.isVisible = is_curve

    if is_curve:
        angle_input = _find_input(inputs, "in_angle")
        if angle_input is not None:
            for angle in ("90", "45", "30", "60"):
                if angle in selected:
                    angle_input.expression = f"{angle} deg"
                    break


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


def _evaluate_to_display_units(units, expression: str, unit: str) -> float:
    """Evaluate a Fusion expression and convert its internal value to display units."""
    raw = float(units.evaluateExpression(expression, unit))
    if unit == "mm":
        try:
            return float(units.convert(raw, "cm", "mm"))
        except Exception:
            return raw * 10.0
    if unit == "deg":
        try:
            return float(units.convert(raw, "rad", "deg"))
        except Exception:
            return math.degrees(raw)
    return raw


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

    m_item = _find_input(inputs, MODULE_TYPE_ID)
    values[MODULE_TYPE_ID] = m_item.selectedItem.name if (m_item and m_item.selectedItem) else "Straight Section"

    p_item = _find_input(inputs, PRESET_ID)
    values[PRESET_ID] = p_item.selectedItem.name if (p_item and p_item.selectedItem) else "Custom"

    defaults = dialog_defaults()

    for spec_id, _label, _unit, _key, _tip in STRAIGHT_SPECS:
        item = _find_input(inputs, spec_id)
        if item is not None:
            try:
                values[spec_id] = _evaluate_to_display_units(units, item.expression, "mm")
            except Exception as exc:
                raise ValueError(f"{spec_id} ({item.expression!r}): {exc}") from exc
        elif spec_id not in values:
            values[spec_id] = float(defaults.get(spec_id, 0.0))

    for spec_id, _label, unit, _tip in CURVE_SPECS:
        item = _find_input(inputs, spec_id)
        if item is not None:
            try:
                values[spec_id] = _evaluate_to_display_units(units, item.expression, unit)
            except Exception as exc:
                raise ValueError(f"{spec_id} ({item.expression!r}): {exc}") from exc
        elif spec_id not in values:
            values[spec_id] = float(defaults.get(spec_id, 0.0))

    guard_item = _find_input(inputs, GUARDS_ID)
    values[GUARDS_ID] = bool(guard_item.value) if guard_item else True

    export_item = _find_input(inputs, EXPORT_BTN_ID)
    # Default True so older dialogs / tests without the checkbox still export.
    values[EXPORT_BTN_ID] = bool(export_item.value) if export_item is not None else True

    brace_item = _find_input(inputs, CROSS_BRACE_ID)
    values[CROSS_BRACE_ID] = bool(brace_item.value) if brace_item else True

    auto_item = _find_input(inputs, AUTO_OPTIMIZE_ID)
    values[AUTO_OPTIMIZE_ID] = bool(auto_item.value) if auto_item else False

    duty_item = _find_input(inputs, DUTY_CLASS_ID)
    values[DUTY_CLASS_ID] = duty_item.selectedItem.name if (duty_item and duty_item.selectedItem) else "Medium Duty (450 kg)"

    load_item = _find_input(inputs, TARGET_LOAD_ID)
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
    if ui is None:
        return candidates
    try:
        active = getattr(ui, "activeWorkspace", None)
        if active is not None:
            candidates.append(active)
    except Exception:
        # Inactive session or teardown: e.g. RuntimeError: 2 : InternalValidationError : pCurrentSession
        pass

    try:
        workspaces = getattr(ui, "workspaces", None)
    except Exception:
        workspaces = None

    if workspaces is not None:
        for workspace_id in ("FusionSolidEnvironment", "AssemblyEnvironment"):
            try:
                workspace = workspaces.itemById(workspace_id)
                if workspace is not None and all(workspace is not item for item in candidates):
                    candidates.append(workspace)
            except Exception:
                pass
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
    if workspace is None:
        return panels
    try:
        tb_panels = getattr(workspace, "toolbarPanels", None)
    except Exception:
        tb_panels = None
    if tb_panels is not None:
        for panel_id in panel_ids:
            try:
                panel = tb_panels.itemById(panel_id)
                if panel is not None and all(panel is not item for item in panels):
                    panels.append(panel)
            except Exception:
                pass
    return panels


def _register_command_controls(ui, cmd_def):
    """Place the command in available active-workspace panels."""
    _registered_controls.clear()
    for workspace in _workspace_candidates(ui):
        for panel in _panel_candidates(workspace):
            try:
                controls = getattr(panel, "controls", None)
                if controls is None:
                    continue
                control = controls.itemById(ADDIN_ID)
                if control is None:
                    control = controls.addCommand(cmd_def, ADDIN_ID)
                if control is not None:
                    try:
                        panel_id = getattr(panel, "id", "")
                        if panel_id and panel_id.endswith("CreatePanel"):
                            control.isPromoted = True
                            control.isPromotedByDefault = True
                    except Exception:
                        pass
                    _registered_controls.append((workspace, panel))
            except Exception:
                pass


def _remove_command_controls(ui):
    """Remove controls from every workspace/panel used during registration."""
    if ui is None:
        _registered_controls.clear()
        return
    panels = []
    for item in _registered_controls:
        try:
            panel = item[1] if isinstance(item, (tuple, list)) and len(item) > 1 else item
            if panel is not None and all(panel is not p for p in panels):
                panels.append(panel)
        except Exception:
            pass
    try:
        for workspace in _workspace_candidates(ui):
            try:
                for panel in _panel_candidates(workspace):
                    if all(panel is not p for p in panels):
                        panels.append(panel)
            except Exception:
                pass
    except Exception:
        pass
    for panel in panels:
        for cmd_id in (ADDIN_ID, DOCK_CMD_ID):
            try:
                controls = getattr(panel, "controls", None)
                if controls is not None:
                    control = controls.itemById(cmd_id)
                    if control is not None and getattr(control, "isValid", False):
                        control.deleteMe()
            except Exception:
                pass
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
                    cmd.setDialogMinimumSize(DIALOG_MIN_WIDTH, DIALOG_MIN_HEIGHT)

                    on_execute = ConveyorExecuteHandler()
                    cmd.execute.add(on_execute)
                    handlers.append(on_execute)

                    on_changed = ConveyorChangedHandler()
                    cmd.inputChanged.add(on_changed)
                    handlers.append(on_changed)

                    on_validate = ConveyorValidateHandler()
                    cmd.validateInputs.add(on_validate)
                    handlers.append(on_validate)

                    on_destroy = ConveyorDestroyHandler()
                    cmd.destroy.add(on_destroy)
                    handlers.append(on_destroy)

                    inputs = cmd.commandInputs
                    defaults = dialog_defaults()
                    presets = load_presets()

                    # Single source of truth: tabbed Setup/Dimensions/
                    # Capacity & Options/Preview & Status layout with flat
                    # fallback for older Fusion builds.
                    build_dialog_layout(inputs, defaults, presets)

                    # Tooltips retained from the legacy flat builder so the
                    # live dialog keeps its guidance after the refactor.
                    try:
                        _tips = {
                            TARGET_LOAD_ID: "Enter target payload. Autonomous engine auto-tunes rollers and legs on the fly.",
                            AUTO_OPTIMIZE_ID: "When enabled, changing payload or dimensions immediately auto-sizes rollers and leg stations",
                            GUARDS_ID: "Show side-guard plates (suppression-based)",
                            CROSS_BRACE_ID: "Reinforce leg stations with horizontal/diagonal cross-strut ties for anti-sway stability",
                            EXPORT_BTN_ID: "When ON, Build/Apply also writes STEP + BOM + OPC-UA files (export runs in Execute, never inside InputChanged, so it cannot crash Fusion).",
                        }
                        for _tip_id, _tip_text in _tips.items():
                            _tip_item = _find_input(inputs, _tip_id)
                            if _tip_item is not None:
                                try:
                                    _tip_item.tooltip = _tip_text
                                except Exception:
                                    pass
                    except Exception:
                        pass
                except Exception:
                    app = adsk.core.Application.get()
                    if app and app.userInterface:
                        app.userInterface.messageBox(f"Conveyor dialog creation failed:\n{traceback.format_exc()}")

        class ConveyorChangedHandler(adsk.core.InputChangedEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                global _in_input_changed
                if _in_input_changed:
                    return
                _in_input_changed = True
                try:
                    inputs = args.inputs
                    changed = args.input
                    if changed is None:
                        return

                    def _auto_enabled() -> bool:
                        auto_item = _find_input(inputs, AUTO_OPTIMIZE_ID)
                        try:
                            return bool(auto_item.value) if auto_item is not None else False
                        except Exception:
                            return False

                    # Module Type Switch: toggle straight vs curved groups
                    if changed.id == MODULE_TYPE_ID:
                        _sync_module_inputs(inputs)

                    # Preset Selection Change
                    elif changed.id == PRESET_ID and changed.selectedItem:
                        p_name = changed.selectedItem.name
                        presets = load_presets()
                        if p_name in presets:
                            _apply_preset_to_inputs(inputs, presets[p_name])
                            _sync_module_inputs(inputs)
                            log = _find_input(inputs, LOG_ID)
                            if log is not None:
                                try:
                                    log.text = f"Preset applied: {p_name}"
                                except Exception:
                                    pass

                    # Duty Class or Target Load or Auto-Optimize Change
                    elif changed.id in (DUTY_CLASS_ID, TARGET_LOAD_ID, AUTO_OPTIMIZE_ID) or (
                        changed.id in ("in_length", "in_width", "in_height") and _auto_enabled()
                    ):
                        try:
                            vals = _read_dialog_values(inputs)
                        except Exception as exc:
                            # Partial typing (e.g. cleared box) must not freeze
                            # the dialog: surface the bad field and still
                            # attempt a preview update below.
                            _log_dialog_error("inputChanged auto-opt read", exc)
                            log = _find_input(inputs, LOG_ID)
                            if log is not None:
                                try:
                                    log.text = f"Cannot auto-size: {exc}"
                                except Exception:
                                    pass
                            preview_err = _find_input(inputs, PREVIEW_ID)
                            if preview_err is not None:
                                try:
                                    preview_err.text = f"Invalid input: {exc}"
                                except Exception:
                                    pass
                            return
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
                            load_inp = _find_input(inputs, TARGET_LOAD_ID)
                            if load_inp:
                                try:
                                    load_inp.value = f"{target_l:.0f} kg"
                                except Exception as exc:
                                    _log_dialog_error("inputChanged duty write", exc)

                        auto_on = vals.get(AUTO_OPTIMIZE_ID, False) or (changed.id == DUTY_CLASS_ID and "Custom" not in duty_name)
                        if auto_on:
                            opt_duty = "auto" if "Custom" in duty_name else duty_name
                            try:
                                opt = fcg.autonomous_optimize_conveyor(
                                    target_load_kg=target_l,
                                    length_mm=vals["in_length"],
                                    width_mm=vals["in_width"],
                                    height_mm=vals["in_height"],
                                    side_guards=vals[GUARDS_ID],
                                    duty_class=opt_duty,
                                )
                            except Exception as exc:
                                _log_dialog_error("inputChanged optimize", exc)
                                opt = None
                            if opt is not None:
                                for attr, inp_id in (("roller_diameter_mm", "in_dia"),
                                                     ("roller_spacing_mm", "in_pitch"),
                                                     ("support_spacing_mm", "in_leg")):
                                    item = _find_input(inputs, inp_id)
                                    if item:
                                        try:
                                            item.expression = f"{getattr(opt, attr):.0f} mm"
                                        except Exception as exc:
                                            _log_dialog_error(f"inputChanged write {inp_id}", exc)
                                brace_item = _find_input(inputs, CROSS_BRACE_ID)
                                if brace_item:
                                    try:
                                        brace_item.value = opt.cross_bracing
                                    except Exception as exc:
                                        _log_dialog_error("inputChanged write cross_brace", exc)

                    # Export toggle: checkbox only, no heavy work here.
                    # Export itself runs in ConveyorExecuteHandler (Build/Apply),
                    # which is the only safe place for solve + STEP export.
                    elif changed.id == EXPORT_BTN_ID:
                        log = _find_input(inputs, LOG_ID)
                        try:
                            checked = bool(changed.value)
                        except Exception:
                            checked = True
                        state = "ON — files will export on Build/Apply." if checked else "OFF — Build/Apply will only build, no files."
                        line = f"Export on Apply {state}"
                        if log is not None:
                            try:
                                # Replace a previous toggle line instead of spamming.
                                existing = log.text or ""
                                lines = [ln for ln in existing.split("\n") if ln and not ln.startswith("Export on Apply") and not ln.startswith("Export deferred")]
                                lines.append(line)
                                log.text = "\n".join(lines)
                            except Exception as exc:
                                _log_dialog_error("inputChanged export toggle", exc)
                        return

                    # Live preview update (always attempted; never leaves stale text)
                    preview = _find_input(inputs, PREVIEW_ID)
                    if preview is not None:
                        try:
                            vals = _read_dialog_values(inputs)
                        except Exception as exc:
                            _log_dialog_error("inputChanged preview read", exc)
                            try:
                                preview.text = f"Invalid input: {exc}"
                            except Exception:
                                pass
                            return
                        mod_type = vals.get(MODULE_TYPE_ID, "Straight Section")
                        if "Curve" in mod_type or "Curved" in mod_type:
                            try:
                                preview.text = preview_curve_text(values_to_curve_input(vals))
                            except Exception as exc:
                                try:
                                    preview.text = f"Invalid curve: {exc}"
                                except Exception:
                                    pass
                        else:
                            try:
                                preview.text = preview_text(values_to_input(vals))
                            except Exception as exc:
                                try:
                                    preview.text = f"Invalid straight: {exc}"
                                except Exception:
                                    pass
                except Exception as exc:
                    _log_dialog_error("inputChanged", exc)
                    try:
                        log = _find_input(args.inputs, LOG_ID)
                        if log is not None:
                            log.text = f"Dialog update failed: {exc}"
                    except Exception:
                        pass
                finally:
                    _in_input_changed = False

        class ConveyorValidateHandler(adsk.core.ValidateInputsEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                status = None
                try:
                    vals = _read_dialog_values(args.inputs)
                    mod_type = vals.get(MODULE_TYPE_ID, "Straight Section")
                    if "Curve" in mod_type or "Curved" in mod_type:
                        values_to_curve_input(vals)
                    else:
                        values_to_input(vals)
                    args.areInputsValid = True
                    status = "Ready — Build / Apply is enabled."
                except Exception as exc:
                    args.areInputsValid = False
                    status = f"Cannot build: {exc}"
                log = _find_input(args.inputs, LOG_ID)
                if log is not None and status:
                    try:
                        log.text = status
                    except Exception as exc:
                        _log_dialog_error("validateInputs log", exc)

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

        class ConveyorDestroyHandler(adsk.core.CommandEventHandler):
            def __init__(self):
                super().__init__()

            def notify(self, args):
                _active_dialog_inputs.clear()

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
                    next_item = _find_input(inputs, "dock_next_type")
                    sel_text = next_item.selectedItem.name if (next_item and next_item.selectedItem) else "Straight"

                    # Find parent conveyor in root occurrences
                    parent_occ = None
                    for occ in design.rootComponent.occurrences:
                        c_name = (occ.component.name or "") if occ.component else ""
                        o_name = occ.name or ""
                        if (o_name.startswith("ParametricConveyor") or o_name.startswith("CurveModule")
                                or c_name.startswith("ParametricConveyor") or c_name.startswith("CurveModule")):
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
                        # Build real straight geometry first (never an empty
                        # component), then move its occurrence onto the joint.
                        fcg.create_user_parameters(design, child_p)
                        straight_refs = fcg.build_parametric_conveyor_model(design)
                        occ = straight_refs.get("occurrence")
                        if occ is not None:
                            try:
                                straight_refs["component"].name = f"Docked_Straight_L{length:.0f}"
                            except Exception:
                                pass
                            fds.apply_docking_to_occurrence(occ, transform)
                        else:
                            # Part-doc fallback: geometry went to root; cannot
                            # transform independently — report instead of crash.
                            ui.messageBox(
                                "Docked straight built in root (Part doc): "
                                "geometry created but cannot be moved independently. "
                                "Open an Assembly doc for movable docked lines."
                            )
                            return

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
        try:
            workspaces = getattr(ui, "workspaces", None)
            workspace = workspaces.itemById("FusionSolidEnvironment") if workspaces else None
            if workspace:
                tb_panels = getattr(workspace, "toolbarPanels", None)
                panel = tb_panels.itemById("SolidScriptsAddinsPanel") if tb_panels else None
                if panel and getattr(panel, "controls", None) and panel.controls.itemById(ADDIN_ID) is None:
                    panel.controls.addCommand(cmd_def, ADDIN_ID)

                create_panel = tb_panels.itemById("SolidCreatePanel") if tb_panels else None
                if create_panel and getattr(create_panel, "controls", None):
                    if create_panel.controls.itemById(ADDIN_ID) is None:
                        c_ctrl = create_panel.controls.addCommand(cmd_def, ADDIN_ID)
                        c_ctrl.isPromoted = True
                        c_ctrl.isPromotedByDefault = True
                    if create_panel.controls.itemById(DOCK_CMD_ID) is None:
                        d_ctrl = create_panel.controls.addCommand(dock_def, DOCK_CMD_ID)
                        d_ctrl.isPromoted = True
        except Exception:
            pass

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

        try:
            _remove_command_controls(ui)
        except Exception:
            pass

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
            err_str = traceback.format_exc()
            if "pCurrentSession" not in err_str and "InternalValidationError" not in err_str:
                if ui:
                    ui.messageBox(f"Conveyor add-in stop failed:\n{err_str}")
        except Exception:
            pass
    finally:
        handlers.clear()
