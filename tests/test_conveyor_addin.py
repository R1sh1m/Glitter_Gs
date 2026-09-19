"""Offline tests for the conveyor add-in dialog helpers (no Fusion needed)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "conveyor_addin"))

import conveyor_addin as addin  # noqa: E402
from fusion_conveyor_generator import RANGES  # noqa: E402


class ConveyorAddinHelperTests(unittest.TestCase):
    def test_dialog_defaults_in_range(self):
        defaults = addin.dialog_defaults()
        self.assertTrue(defaults[addin.GUARDS_ID])
        for _sid, _label, _unit, key, _tip in addin.INPUT_SPECS:
            lo, hi = RANGES[key]
            self.assertGreaterEqual(defaults[_sid], lo)
            self.assertLessEqual(defaults[_sid], hi)

    def test_values_round_trip_and_guard_strings(self):
        params = addin.values_to_input(addin.dialog_defaults())
        self.assertTrue(params.side_guards)
        yes_vals = dict(addin.dialog_defaults(), **{addin.GUARDS_ID: "Yes"})
        no_vals = dict(addin.dialog_defaults(), **{addin.GUARDS_ID: "no"})
        self.assertTrue(addin.values_to_input(yes_vals).side_guards)
        self.assertFalse(addin.values_to_input(no_vals).side_guards)

    def test_values_reject_out_of_range(self):
        bad = dict(addin.dialog_defaults(), in_length=100.0)
        with self.assertRaises(ValueError):
            addin.values_to_input(bad)

    def test_preview_text_reports_counts(self):
        params = addin.values_to_input(addin.dialog_defaults())
        text = addin.preview_text(params)
        self.assertIn("Rollers:", text)
        self.assertIn("Leg stations:", text)
        self.assertIn("Est. steel mass:", text)

    def test_addin_module_imports_without_fusion(self):
        self.assertFalse(addin._HAS_ADSK)
        self.assertEqual(addin.ADDIN_ID, "GlitterGsConveyorAddin")
        self.assertEqual(addin.DOCK_CMD_ID, "GlitterGsDockingTool")

    def test_presets_loaded_and_valid(self):
        presets = addin.load_presets()
        self.assertIn("C1: Compact (No Guards)", presets)
        self.assertIn("C2: Medium Standard (With Guards)", presets)
        self.assertIn("C3: Long Heavy (With Guards)", presets)
        self.assertIn("Curve 90° Standard Ri800", presets)

        c2 = presets["C2: Medium Standard (With Guards)"]
        self.assertEqual(c2["in_length"], 1400.0)
        self.assertEqual(c2["in_width"], 450.0)

    def test_curve_input_and_preview(self):
        defaults = addin.dialog_defaults()
        defaults["in_radius"] = 800.0
        defaults["in_angle"] = 90.0
        curve_p = addin.values_to_curve_input(defaults)
        self.assertEqual(curve_p.inner_radius_mm, 800.0)
        self.assertEqual(curve_p.curve_angle_deg, 90.0)

        prev = addin.preview_curve_text(curve_p)
        self.assertIn("[CURVED MODULE]", prev)
        self.assertIn("Rollers:", prev)
        self.assertIn("Tapered", prev)

    def test_dialog_read_applies_no_double_conversion(self):
        """evaluateExpression already returns requested units (regression).

        A second convert() multiplied lengths x10 (1400 -> 14000, rejected)
        and angles x57.3 (90 -> 5156 deg, rejected). Faked units manager
        follows real Fusion semantics.
        """
        import re

        real_adsk = addin.adsk

        class FakeUnits:
            @staticmethod
            def _split(expr):
                m = re.match(r"\s*([0-9.]+)\s*([A-Za-z]*)\s*$", expr)
                return float(m.group(1)), (m.group(2) or "mm")

            def evaluateExpression(self, expr, unit):
                val, frm = self._split(expr)
                # Real Fusion 360 UnitsManager returns internal database units:
                # Length -> cm, Angle -> radians
                to_cm = {"mm": 0.1, "cm": 1.0, "m": 100.0}
                to_rad = {"deg": math.radians(1.0), "rad": 1.0}
                if frm in to_cm or unit in ("mm", "cm", "m"):
                    return val * to_cm.get(frm, 0.1)
                return val * to_rad.get(frm, math.radians(1.0))

            def convert(self, v, frm, to):
                if frm == "cm" and to == "mm":
                    return v * 10.0
                if frm in ("rad", "radian") and to in ("deg", "degree"):
                    return math.degrees(v)
                return v

        class FakeProduct:
            unitsManager = FakeUnits()

        class FakeApp:
            activeProduct = FakeProduct()

            @staticmethod
            def get():
                return FakeApp()

        class FakeCore:
            Application = FakeApp

        class FakeAdsk:
            core = FakeCore()

        class Item:
            def __init__(self, expression="", value=None, selected=None):
                self.expression = expression
                self.value = value
                self.selectedItem = (
                    type("S", (), {"name": selected})() if selected else None
                )

        table = {
            addin.MODULE_TYPE_ID: Item(selected="Straight Section"),
            addin.PRESET_ID: Item(selected="Custom"),
            addin.GUARDS_ID: Item(value=True),
            "in_length": Item(expression="1400 mm"),
            "in_width": Item(expression="450 mm"),
            "in_height": Item(expression="750 mm"),
            "in_dia": Item(expression="60 mm"),
            "in_pitch": Item(expression="110 mm"),
            "in_leg": Item(expression="700 mm"),
            "in_guard": Item(expression="100 mm"),
            "in_radius": Item(expression="800 mm"),
            "in_angle": Item(expression="90 deg"),
        }

        class FakeInputs:
            def itemById(self, i):
                return table.get(i)

        addin.adsk = FakeAdsk()
        try:
            values = addin._read_dialog_values(FakeInputs())
        finally:
            addin.adsk = real_adsk
        self.assertEqual(values["in_length"], 1400.0)
        self.assertEqual(values["in_width"], 450.0)
        self.assertEqual(values["in_angle"], 90.0)
        self.assertEqual(values["in_radius"], 800.0)
        # And the values validate end to end
        addin.values_to_input(values)
        addin.values_to_curve_input(values)

    def test_preview_text_contains_capacity_and_safety_factor(self):
        params = addin.values_to_input(addin.dialog_defaults())
        text = addin.preview_text(params)
        self.assertIn("Rated Safe Load:", text)
        self.assertIn("Structural Safety Factor", text)
        self.assertIn("Cross-Struts:", text)

    def test_read_dialog_values_names_failing_field(self):
        """A bad expression must raise ValueError naming the field id."""
        real_adsk = addin.adsk

        class FakeUnits:
            def evaluateExpression(self, expr, unit):
                if expr == "bogus":
                    raise RuntimeError("bad expression")
                return 1400.0

        class FakeProduct:
            unitsManager = FakeUnits()

        class FakeApp:
            activeProduct = FakeProduct()

            @staticmethod
            def get():
                return FakeApp()

        class FakeCore:
            Application = FakeApp

        class FakeAdsk:
            core = FakeCore()

        class Item:
            def __init__(self, expression="", value=None, selected=None):
                self.expression = expression
                self.value = value
                self.selectedItem = (
                    type("S", (), {"name": selected})() if selected else None
                )

        table = {
            addin.MODULE_TYPE_ID: Item(selected="Straight Section"),
            addin.PRESET_ID: Item(selected="Custom"),
            addin.GUARDS_ID: Item(value=True),
            "in_length": Item(expression="bogus"),
            "in_width": Item(expression="450 mm"),
        }

        class FakeInputs:
            def itemById(self, i):
                return table.get(i)

        addin.adsk = FakeAdsk()
        try:
            with self.assertRaises(ValueError) as ctx:
                addin._read_dialog_values(FakeInputs())
        finally:
            addin.adsk = real_adsk
        self.assertIn("in_length", str(ctx.exception))

    def test_duty_presets_contain_capacity_and_cross_brace(self):
        presets = addin.load_presets()
        for p in presets.values():
            if p.get("module_type") == "straight":
                self.assertIn("in_cross_brace", p)
                self.assertIn("in_target_load", p)

    def test_preset_applies_native_input_properties(self):
        class Item:
            def __init__(self, name="", value=False):
                self.name = name
                self.value = value
                self.expression = ""
                self.isSelected = False

        class ListItems:
            def __init__(self, names):
                self._items = [Item(name) for name in names]

            @property
            def count(self):
                return len(self._items)

            def item(self, index):
                return self._items[index]

        class DropDown:
            def __init__(self, names):
                self.listItems = ListItems(names)

            @property
            def selectedItem(self):
                return next((item for item in self.listItems._items if item.isSelected), None)

        class Inputs:
            def __init__(self):
                self.items = {
                    addin.MODULE_TYPE_ID: DropDown(["Straight Section", "Curved 90° Section"]),
                    addin.DUTY_CLASS_ID: DropDown(["Custom (Manual Specs)", "Medium Duty (450 kg - Boxes & Parts)"]),
                    addin.GUARDS_ID: Item(value=False),
                    addin.CROSS_BRACE_ID: Item(value=False),
                    addin.TARGET_LOAD_ID: Item(),
                    "in_length": Item(),
                    "in_angle": Item(),
                }

            def itemById(self, ident):
                return self.items.get(ident)

        inputs = Inputs()
        addin._apply_preset_to_inputs(inputs, {
            "module_type": "curve",
            "in_duty_class": "Medium Duty (450 kg - Boxes & Parts)",
            "in_guards": True,
            "in_cross_brace": True,
            "in_target_load": 450.0,
            "in_length": 1400.0,
            "in_angle": 90.0,
        })
        self.assertEqual(inputs.itemById(addin.TARGET_LOAD_ID).value, "450 kg")
        self.assertTrue(inputs.itemById(addin.GUARDS_ID).value)
        self.assertTrue(inputs.itemById(addin.CROSS_BRACE_ID).value)
        self.assertEqual(inputs.itemById("in_length").expression, "1400.0 mm")
        self.assertEqual(inputs.itemById("in_angle").expression, "90.0 deg")
        self.assertEqual(inputs.itemById(addin.MODULE_TYPE_ID).selectedItem.name, "Curved 90° Section")

    def test_module_sync_updates_visibility_and_curve_angle(self):
        class Item:
            def __init__(self, name="", selected=False):
                self.name = name
                self.isSelected = selected
                self.expression = "0 deg"
                self.isVisible = True

        class ListItems:
            def __init__(self, items):
                self._items = items

            @property
            def count(self):
                return len(self._items)

            def item(self, index):
                return self._items[index]

        class DropDown:
            def __init__(self):
                self.listItems = ListItems([
                    Item("Straight Section", selected=False),
                    Item("Curved 45° Section", selected=True),
                ])

            @property
            def selectedItem(self):
                return next(item for item in self.listItems._items if item.isSelected)

        class Inputs:
            def __init__(self):
                self.items = {
                    addin.MODULE_TYPE_ID: DropDown(),
                    "group_straight": Item(),
                    "group_curved": Item(),
                    "in_angle": Item(),
                }

            def itemById(self, ident):
                return self.items.get(ident)

        inputs = Inputs()
        addin._sync_module_inputs(inputs)
        self.assertTrue(inputs.itemById("group_straight").isVisible)
        self.assertTrue(inputs.itemById("group_curved").isVisible)
        self.assertEqual(inputs.itemById("in_angle").expression, "45 deg")


if __name__ == "__main__":
    unittest.main()
